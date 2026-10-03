"""Explicit list membership and deterministic per-level numbering."""

from __future__ import annotations

from collections.abc import Iterator, Mapping, MutableMapping
from copy import deepcopy
from dataclasses import asdict, dataclass
from typing import Any, Literal, TypeAlias

from opendoc.diagnostics import _DiagnosticError
from opendoc.document_model import Paragraph
from opendoc.limits import DocumentLimits, _resolve_limits
from opendoc.traversal import ModelNode, NodeLocation, iter_elements

LIST_PROPERTY = "opendoc.list-item"
ListKind: TypeAlias = Literal["ordered", "unordered"]


def _list_fields(values: dict[str, Any], path: str) -> None:
    identifier = values.get("list_id")
    if not isinstance(identifier, str) or not identifier or any(0xD800 <= ord(char) <= 0xDFFF for char in identifier):
        raise _DiagnosticError(f"{path}.list_id", "expected a nonempty UTF-8 list ID", "semantic.list.id")
    if type(values.get("level")) is not int or not 0 <= values["level"] <= 8:
        raise _DiagnosticError(f"{path}.level", "list level must be an integer between 0 and 8", "semantic.list.level")
    if values.get("kind") not in ("ordered", "unordered"):
        raise _DiagnosticError(f"{path}.kind", "unsupported list kind", "semantic.list.kind")
    for field in ("start", "restart"):
        value = values.get(field)
        if field == "restart" and value is None:
            continue
        if type(value) is not int or value < 1:
            raise _DiagnosticError(f"{path}.{field}", "expected a positive integer", "semantic.list.number")
    if values["kind"] == "unordered" and (values["start"] != 1 or values["restart"] is not None):
        raise _DiagnosticError(path, "unordered lists cannot specify numbering", "semantic.list.number")


@dataclass(frozen=True)
class ListItem:
    """Membership in an implicit list group; levels are 0–8.

    Kind/start must agree within (list_id, level). Restart applies to this
    occurrence only. A shallower item resets deeper counters of the same list.
    IDs describe groups, not references to a consuming application's task store.
    """

    list_id: str
    level: int = 0
    kind: ListKind = "ordered"
    start: int = 1
    restart: int | None = None

    def __post_init__(self) -> None:
        _list_fields(
            {"list_id": self.list_id, "level": self.level, "kind": self.kind, "start": self.start, "restart": self.restart},
            "list_item",
        )


@dataclass(frozen=True)
class ListNumber:
    """One occurrence and its decimal number; unordered items have number None."""

    location: NodeLocation[Paragraph]
    item: ListItem
    number: int | None


def _list_payload(value: Any, path: str) -> ListItem | None:
    if not isinstance(value, dict) or value.get("format") != "opendoc.list-item":
        return None
    if type(value.get("version")) is not int or value["version"] != 1:
        raise _DiagnosticError(f"{path}.version", "unsupported list item version", "semantic.version")
    fields = {
        "list_id": value.get("list_id"),
        "level": value.get("level", 0),
        "kind": value.get("kind", "ordered"),
        "start": value.get("start", 1),
        "restart": value.get("restart"),
    }
    _list_fields(fields, path)
    return ListItem(**fields)


def _list_inventory_valid(value: Any) -> bool:
    if value is None:
        return True
    if not isinstance(value, dict) or not {"list_id", "level", "kind", "start", "restart"} <= value.keys():
        return False
    try:
        _list_fields(value, "inventory")
    except ValueError:
        return False
    return True


def get_list_item(paragraph: Paragraph, *, limits: DocumentLimits | None = None) -> ListItem | None:
    """Read only the explicitly tagged list-item bag, preserving opaque extensions."""
    from opendoc._json_validation import _json_tree

    if not isinstance(paragraph, Paragraph) or not isinstance(paragraph.properties, Mapping):
        raise ValueError("paragraph must be Paragraph with property mapping")
    resolved = _resolve_limits(limits)
    if LIST_PROPERTY not in paragraph.properties:
        return None
    value = paragraph.properties[LIST_PROPERTY]
    path = f"properties[{LIST_PROPERTY!r}]"
    _json_tree(value, path, resolved)
    return _list_payload(value, path)


def set_list_item(paragraph: Paragraph, item: ListItem | None, *, limits: DocumentLimits | None = None) -> None:
    """Set/remove membership in place after checking; do not overwrite opaque data."""
    from opendoc._json_validation import _json_tree

    if not isinstance(paragraph, Paragraph) or not isinstance(paragraph.properties, MutableMapping):
        raise ValueError("paragraph must be Paragraph with property mapping")
    if item is not None and not isinstance(item, ListItem):
        raise ValueError("item must be ListItem or None")
    resolved = _resolve_limits(limits)
    existing = get_list_item(paragraph, limits=resolved)
    if LIST_PROPERTY in paragraph.properties and existing is None:
        raise ValueError("list property is occupied by an opaque extension")
    if item is None:
        if existing is not None:
            del paragraph.properties[LIST_PROPERTY]
        return
    value = deepcopy(paragraph.properties[LIST_PROPERTY]) if existing is not None else {}
    value.update(format="opendoc.list-item", version=1, **asdict(item))
    path = f"properties[{LIST_PROPERTY!r}]"
    _json_tree(value, path, resolved)
    _list_payload(value, path)
    paragraph.properties[LIST_PROPERTY] = value


def iter_list_items(root: ModelNode, *, limits: DocumentLimits | None = None) -> Iterator[NodeLocation[Paragraph]]:
    """Find marked list paragraphs in the common traversal order."""
    for location in iter_elements(root, Paragraph, limits=limits):
        if get_list_item(location.node, limits=limits) is not None:
            yield location


def iter_list_numbers(root: ModelNode, *, limits: DocumentLimits | None = None) -> Iterator[ListNumber]:
    """Compute occurrence numbers in traversal order, validating all groups first.

    Groups can interleave and resume across sections. Plain paragraphs do not
    reset them. Levels need not have a parent occurrence; only the current
    level's decimal number is returned, never a guessed hierarchical label.
    """
    selected: list[tuple[NodeLocation[Paragraph], ListItem]] = []
    configs: dict[tuple[str, int], tuple[str, int]] = {}
    for location in iter_list_items(root, limits=limits):
        item = get_list_item(location.node, limits=limits)
        assert item is not None
        key = (item.list_id, item.level)
        config = (item.kind, item.start)
        if key in configs and configs[key] != config:
            raise _DiagnosticError(location.path, "conflicting list kind/start for the same level", "semantic.list.config")
        configs[key] = config
        selected.append((location, item))
    counters: dict[str, dict[int, int]] = {}
    for location, item in selected:
        levels = counters.setdefault(item.list_id, {})
        for level in tuple(levels):
            if level > item.level:
                del levels[level]
        number = None
        if item.kind == "ordered":
            number = item.restart if item.restart is not None else levels.get(item.level, item.start - 1) + 1
            levels[item.level] = number
        yield ListNumber(location, item, number)


__all__ = [
    "LIST_PROPERTY",
    "ListItem",
    "ListKind",
    "ListNumber",
    "get_list_item",
    "iter_list_items",
    "iter_list_numbers",
    "set_list_item",
]
