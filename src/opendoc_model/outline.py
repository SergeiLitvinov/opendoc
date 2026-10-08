"""Inert, format-neutral outline entries with explicit hierarchy and destinations."""

from __future__ import annotations

import math
from copy import deepcopy
from dataclasses import dataclass, replace
from typing import Any, Literal

from opendoc_model._integration_codec import _convert
from opendoc_model._json_validation import _json_tree
from opendoc_model.diagnostics import _DiagnosticError
from opendoc_model.document_model import DocumentModel, Provenance
from opendoc_model.integration_types import IntegrationModel, IntegrationRecord
from opendoc_model.limits import DocumentLimits, _guard_model, _quota, _resolve_limits
from opendoc_model.units import Point2D

OUTLINE_PROPERTY = "opendoc.outline"


def _error(path: str, message: str) -> Any:
    raise _DiagnosticError(path, message, "outline.invalid")


def _identifier(value: str | None, path: str) -> None:
    if type(value) is not str or not value:
        _error(path, "expected a nonempty identifier")


def _finite(value: float, path: str) -> None:
    if type(value) not in (int, float):
        _error(path, "expected a finite number")
    try:
        valid = math.isfinite(value)
    except OverflowError:
        _error(path, "number exceeds floating point range")
    if not valid:
        _error(path, "expected a finite number")


@dataclass(frozen=True)
class OutlineTarget(IntegrationRecord):
    """Anchor/page ID or inert external URI; page points are source coordinates in pt.

    Zoom is a positive ratio, not a percentage. Missing point/zoom means unknown.
    No URI, action, layout or destination is executed or resolved externally.
    """

    kind: Literal["anchor", "page", "external"]
    target_id: str | None = None
    uri: str | None = None
    point: Point2D | None = None
    zoom: float | None = None

    def __post_init__(self) -> None:
        if self.kind not in ("anchor", "page", "external"):
            _error("outline.target.kind", "unsupported destination kind")
        if self.kind == "external":
            _identifier(self.uri, "outline.target.uri")
            if self.target_id is not None:
                _error("outline.target.target_id", "external destination has no local ID")
        else:
            _identifier(self.target_id, "outline.target.target_id")
            if self.uri is not None:
                _error("outline.target.uri", "local destination has no external URI")
        if self.kind != "page" and (self.point is not None or self.zoom is not None):
            _error("outline.target", "point and zoom require a page destination")
        if self.point is not None:
            if type(self.point) is not Point2D:
                _error("outline.target.point", "expected Point2D")
            _finite(self.point.x, "outline.target.point.x")
            _finite(self.point.y, "outline.target.point.y")
        if self.zoom is not None:
            _finite(self.zoom, "outline.target.zoom")
            if self.zoom <= 0:
                _error("outline.target.zoom", "zoom must be positive")


@dataclass(frozen=True)
class OutlineEntry(IntegrationRecord):
    """Stable outline-local ID, plain title and explicit nonnegative sibling order."""

    id: str
    title: str
    order: int
    parent_id: str | None = None
    target: OutlineTarget | None = None
    provenance: Provenance | None = None

    def __post_init__(self) -> None:
        _identifier(self.id, "outline.entry.id")
        if type(self.title) is not str:
            _error("outline.entry.title", "expected text (empty title is allowed)")
        if type(self.order) is not int or self.order < 0:
            _error("outline.entry.order", "expected a nonnegative integer")
        if self.parent_id is not None:
            _identifier(self.parent_id, "outline.entry.parent_id")


@dataclass(frozen=True)
class Outline(IntegrationRecord):
    """Entries are stored independently of tuple order; roots have parent_id=None."""

    entries: tuple[OutlineEntry, ...] = ()


def _hierarchy(outline: Outline, limits: DocumentLimits) -> None:
    entries: dict[str, OutlineEntry] = {}
    positions: set[tuple[str | None, int]] = set()
    for index, entry in enumerate(outline.entries):
        path = f"outline.entries[{index}]"
        if entry.id in entries:
            _error(path, "duplicate entry ID")
        position = (entry.parent_id, entry.order)
        if position in positions:
            _error(path, "duplicate sibling order")
        entries[entry.id] = entry
        positions.add(position)
    depths: dict[str, int] = {}
    for entry in outline.entries:
        current: str | None = entry.id
        chain: list[str] = []
        seen: set[str] = set()
        while current is not None and current not in depths:
            if current not in entries:
                _error("outline.parent_id", f"unknown parent {current!r}")
            if current in seen:
                _error("outline.parent_id", "cyclic hierarchy")
            if len(chain) >= limits.max_depth:
                _quota("outline", "hierarchy depth", limits.max_depth)
            seen.add(current)
            chain.append(current)
            current = entries[current].parent_id
        depth = 0 if current is None else depths[current]
        for identifier in reversed(chain):
            depth += 1
            if depth > limits.max_depth:
                _quota("outline", "hierarchy depth", limits.max_depth)
            depths[identifier] = depth


def _read_outline(model: IntegrationModel, limits: DocumentLimits) -> Outline | None:
    raw = model.extra.get(OUTLINE_PROPERTY)
    if raw is None:
        return None
    _json_tree(raw, "outline", limits)
    if not isinstance(raw, dict) or raw.get("format") != OUTLINE_PROPERTY:
        return None
    if type(raw.get("version")) is not int or raw["version"] != 1:
        _error("outline.version", "unsupported outline schema version")
    try:
        result: Outline = _convert(
            {key: value for key, value in raw.items() if key not in {"format", "version"}}, Outline, "outline", encode=False
        )
    except _DiagnosticError as error:
        raise _DiagnosticError(error.location, error.message, "outline.invalid") from error
    _hierarchy(result, limits)
    return result


def _with_outline(model: IntegrationModel, outline: Outline | None, limits: DocumentLimits) -> IntegrationModel:
    previous = _read_outline(model, limits)
    if model.extra.get(OUTLINE_PROPERTY) is not None and previous is None:
        _error("outline", "occupied outline key contains opaque data")
    extra = deepcopy(model.extra)
    if outline is None:
        extra.pop(OUTLINE_PROPERTY, None)
    else:
        _guard_model(outline, limits)
        if type(outline) is not Outline:
            _error("outline", "expected Outline or None")
        if not isinstance(outline.extra, dict) or {"format", "version"}.intersection(outline.extra):
            _error("outline.extra", "unknown fields cannot shadow envelope fields")
        if previous is not None:
            outline = replace(outline, extra={**previous.extra, **outline.extra})
        encoded = _convert(outline, Outline, "outline", encode=True)
        _json_tree(encoded, "outline", limits)
        _hierarchy(outline, limits)
        extra[OUTLINE_PROPERTY] = {**encoded, "format": OUTLINE_PROPERTY, "version": 1}
    result = replace(model, extra=extra)
    _guard_model(result, limits)
    return result


def get_outline(document: DocumentModel, *, limits: DocumentLimits | None = None) -> Outline | None:
    """Read independent declarations and hierarchy; document validation checks targets."""
    from opendoc_model.integration import get_integration

    budget = _resolve_limits(limits)
    model = get_integration(document, limits=budget)
    return _read_outline(model, budget) if model is not None else None


def set_outline(document: DocumentModel, outline: Outline | None, *, limits: DocumentLimits | None = None) -> None:
    """Validate and atomically replace declarations in the existing integration envelope."""
    from opendoc_model.integration import get_integration, set_integration

    budget = _resolve_limits(limits)
    model = get_integration(document, limits=budget)
    if model is None and outline is None:
        return
    set_integration(document, _with_outline(model or IntegrationModel(), outline, budget), limits=budget)


def _validate_outline(model: IntegrationModel, anchors: dict[str, Any], limits: DocumentLimits) -> None:
    outline = _read_outline(model, limits)
    if outline is None:
        return
    pages = {page.id for page in model.pages}
    for index, entry in enumerate(outline.entries):
        target = entry.target
        if target is not None:
            available = anchors if target.kind == "anchor" else pages
            if target.kind != "external" and target.target_id not in available:
                _error(f"outline.entries[{index}].target", f"unknown {target.kind} destination {target.target_id!r}")
        if entry.provenance is not None:
            if not entry.provenance.source_format:
                _error(f"outline.entries[{index}].provenance", "expected source format")
            if entry.provenance.page is not None and (type(entry.provenance.page) is not int or entry.provenance.page < 0):
                _error(f"outline.entries[{index}].provenance.page", "expected nonnegative source page")


def remap_outline(
    outline: Outline,
    *,
    entry_ids: dict[str, str] | None = None,
    anchor_ids: dict[str, str] | None = None,
    page_ids: dict[str, str] | None = None,
    limits: DocumentLimits | None = None,
) -> Outline:
    """Independently remap explicit IDs; missing map keys retain their IDs.

    This checks hierarchy and budgets, not destination existence in a document.
    It neither combines outlines nor modifies external URI or private extra fields.
    """
    budget = _resolve_limits(limits)
    checked = _read_outline(_with_outline(IntegrationModel(), outline, budget), budget)
    assert checked is not None
    for mapping in (entry_ids, anchor_ids, page_ids):
        if mapping is not None:
            _json_tree(mapping, "outline.id_map", budget)
            if not isinstance(mapping, dict):
                _error("outline.id_map", "expected string ID mapping")
            for key, value in mapping.items():
                _identifier(key, "outline.id_map.key")
                _identifier(value, "outline.id_map.value")
    entries = []
    identifiers = entry_ids or {}
    for entry in checked.entries:
        target = entry.target
        if target is not None and target.kind != "external":
            assert target.target_id is not None
            mapping = (anchor_ids if target.kind == "anchor" else page_ids) or {}
            target = replace(target, target_id=mapping.get(target.target_id, target.target_id))
        entries.append(
            replace(
                entry,
                id=identifiers.get(entry.id, entry.id),
                parent_id=identifiers.get(entry.parent_id, entry.parent_id) if entry.parent_id is not None else None,
                target=target,
            )
        )
    result = replace(checked, entries=tuple(entries))
    _read_outline(_with_outline(IntegrationModel(), result, budget), budget)
    return result


__all__ = ["OUTLINE_PROPERTY", "Outline", "OutlineEntry", "OutlineTarget", "get_outline", "set_outline", "remap_outline"]
