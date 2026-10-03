"""Explicit consumer namespaces and per-call validation of preserved JSON extensions."""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable, Iterator, Mapping, MutableMapping
from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Literal, TypeAlias

from opendoc._json_validation import _json_tree
from opendoc.diagnostics import CheckResult, DiagnosticIssue, IssueSeverity, _DiagnosticError
from opendoc.document_model import DocumentModel, Footnote, TextRun
from opendoc.limits import DocumentLimits, _quota, _resolve_limits
from opendoc.traversal import _walk_locations

ExtensionScope: TypeAlias = Literal["metadata", "properties"]
UnknownExtensionPolicy: TypeAlias = Literal["error", "preserve"]
_KEY = re.compile(r"[a-z][a-z0-9_-]*(?:\.[a-z][a-z0-9_-]*)+")
_BUILTINS = {
    "opendoc.heading",
    "opendoc.list-item",
    "opendoc.anchor",
    "opendoc.internal-link",
    "opendoc.footnotes",
    "opendoc.footnote-reference",
}
_BUILTIN_OWNERS = {
    "opendoc.heading": {"Paragraph"},
    "opendoc.list-item": {"Paragraph"},
    "opendoc.anchor": {"Paragraph", "Table", "TextRun", "Formula", "Image"},
    "opendoc.internal-link": {"TextRun"},
    "opendoc.footnote-reference": {"TextRun"},
    "opendoc.footnotes": {"DocumentModel"},
}


def _key(value: Any) -> str:
    if not isinstance(value, str) or _KEY.fullmatch(value) is None or value.startswith("opendoc."):
        raise ValueError("extension key must be a dotted consumer namespace outside opendoc.*")
    return value


@dataclass(frozen=True)
class ExtensionValue:
    """Independent JSON data and unknown envelope fields; reading is not semantic verification."""

    key: str
    version: int
    data: Any
    extensions: dict[str, Any]


@dataclass(frozen=True)
class ExtensionContext:
    """A validator receives independent data and a location ending in .data."""

    key: str
    version: int
    data: Any
    location: str
    scope: ExtensionScope
    owner_type: str


ExtensionCallback: TypeAlias = Callable[[ExtensionContext], Iterable[DiagnosticIssue] | None]


@dataclass(frozen=True)
class ExtensionSchema:
    """One consumer key, explicit supported versions and optional trusted validation code."""

    key: str
    versions: frozenset[int]
    validator: ExtensionCallback | None = None
    scopes: frozenset[ExtensionScope] = frozenset({"metadata", "properties"})

    def __post_init__(self) -> None:
        _key(self.key)
        if not isinstance(self.versions, frozenset) or not self.versions:
            raise ValueError("versions must be a nonempty frozenset of positive integers")
        if any(type(version) is not int or version < 1 for version in self.versions):
            raise ValueError("extension versions must be positive integers")
        if self.validator is not None and not callable(self.validator):
            raise ValueError("validator must be callable or None")
        if not isinstance(self.scopes, frozenset) or not self.scopes or not self.scopes <= {"metadata", "properties"}:
            raise ValueError("scopes must be a nonempty frozenset of metadata/properties")


def _value(raw: Any, key: str, path: str) -> ExtensionValue | None:
    if not isinstance(raw, dict) or raw.get("format") != key:
        return None
    if type(raw.get("version")) is not int or raw["version"] < 1:
        raise _DiagnosticError(f"{path}.version", "expected a positive integer extension version", "extension.version")
    if "data" not in raw:
        raise _DiagnosticError(f"{path}.data", "missing extension data", "extension.data")
    return ExtensionValue(
        key,
        raw["version"],
        deepcopy(raw["data"]),
        deepcopy({name: item for name, item in raw.items() if name not in {"format", "version", "data"}}),
    )


def get_extension(bag: Mapping[str, Any], key: str, *, limits: DocumentLimits | None = None) -> ExtensionValue | None:
    """Read a consumer envelope without inferring semantics or executing validation code."""
    _key(key)
    if not isinstance(bag, Mapping):
        raise ValueError("bag must be a mapping")
    resolved = _resolve_limits(limits)
    raw = bag.get(key)
    _json_tree(raw, f"[{key!r}]", resolved)
    return _value(raw, key, f"[{key!r}]")


def set_extension(
    bag: MutableMapping[str, Any], key: str, data: Any, *, version: int = 1, limits: DocumentLimits | None = None
) -> None:
    """Set independent JSON data atomically, retaining unknown tagged envelope fields."""
    existing = get_extension(bag, key, limits=limits)
    if not isinstance(bag, MutableMapping):
        raise ValueError("bag must be mutable")
    if key in bag and existing is None:
        raise ValueError("extension key is occupied by an opaque value")
    raw = deepcopy(bag[key]) if existing is not None else {}
    raw.update(format=key, version=version, data=data)
    _json_tree(raw, f"[{key!r}]", _resolve_limits(limits))
    _value(raw, key, f"[{key!r}]")
    bag[key] = deepcopy(raw)


def remove_extension(bag: MutableMapping[str, Any], key: str, *, limits: DocumentLimits | None = None) -> None:
    """Remove only a recognized envelope; opaque values are preserved by refusal."""
    existing = get_extension(bag, key, limits=limits)
    if not isinstance(bag, MutableMapping):
        raise ValueError("bag must be mutable")
    if key in bag and existing is None:
        raise ValueError("extension key is occupied by an opaque value")
    if existing is not None:
        del bag[key]


def _schemas(schemas: Iterable[ExtensionSchema], limits: DocumentLimits) -> dict[str, ExtensionSchema]:
    try:
        iterator = iter(schemas)
    except TypeError as error:
        raise ValueError("schemas must be an iterable of ExtensionSchema") from error
    result = {}
    for index, schema in enumerate(iterator):
        if index >= limits.max_nodes:
            _quota("schemas", "nodes", limits.max_nodes)
        if not isinstance(schema, ExtensionSchema):
            raise ValueError("schemas must contain ExtensionSchema")
        if schema.key in result:
            raise ValueError(f"duplicate extension schema {schema.key!r}")
        result[schema.key] = schema
    return result


def _bags(document: DocumentModel, limits: DocumentLimits) -> Iterator[tuple[Mapping[str, Any], str, ExtensionScope, str]]:
    yield document.metadata, "metadata", "metadata", "DocumentModel"
    yield document.footnote_properties, "footnote_properties", "metadata", "DocumentModel"
    yield document.footnote_extensions, "footnote_extensions", "metadata", "DocumentModel"
    for key, style in document.styles.items():
        yield style.properties, f"styles[{key!r}].properties", "properties", "TextStyle"
    for key, resource in document.resources.items():
        yield resource.properties, f"resources[{key!r}].properties", "properties", "Resource"
    for location in _walk_locations(document, limits):
        node = location.node
        if isinstance(node, DocumentModel):
            continue
        yield node.properties, f"{location.path}.properties", "properties", type(node).__name__
        if isinstance(node, Footnote):
            yield node.extensions, f"{location.path}.extensions", "properties", "Footnote"
        if isinstance(node, TextRun):
            yield node.style.properties, f"{location.path}.style.properties", "properties", "TextStyle"


def _check_extensions(
    document: DocumentModel, schemas: dict[str, ExtensionSchema], unknown: UnknownExtensionPolicy, limits: DocumentLimits
) -> CheckResult:
    if unknown not in ("error", "preserve"):
        raise ValueError("unknown must be error or preserve")
    issues: list[DiagnosticIssue] = []
    counts = {"checked": 0, "unknown": 0, "opaque": 0}

    def add(issue: DiagnosticIssue) -> None:
        if len(issues) >= limits.max_nodes:
            _quota("extension issues", "nodes", limits.max_nodes)
        _json_tree(
            {
                "code": issue.code,
                "severity": issue.severity.value,
                "message": issue.message,
                "location": issue.location,
                "measurement": issue.measurement,
                "reason": issue.reason,
            },
            "extension issue",
            limits,
        )
        issues.append(deepcopy(issue))

    for bag, path, scope, owner in _bags(document, limits):
        for key, raw in bag.items():
            schema = schemas.get(key)
            location = f"{path}[{key!r}]"
            builtin = key in _BUILTINS
            tagged = isinstance(raw, dict) and raw.get("format") == key
            if builtin:
                if tagged and (owner not in _BUILTIN_OWNERS[key] or key == "opendoc.footnotes" and path != "metadata"):
                    add(
                        DiagnosticIssue(
                            "extension.builtin-scope",
                            IssueSeverity.ERROR,
                            "built-in extension is declared on an unsupported carrier",
                            location,
                        )
                    )
                continue
            if schema is None and (_KEY.fullmatch(key) is None or not tagged):
                continue
            if not tagged:
                counts["opaque"] += 1
                add(DiagnosticIssue("extension.opaque", IssueSeverity.ERROR, "registered extension is opaque", location))
                continue
            try:
                value = _value(raw, key, location)
            except _DiagnosticError as error:
                add(DiagnosticIssue(error.code, IssueSeverity.ERROR, error.message, error.location))
                continue
            assert value is not None
            if schema is None:
                counts["unknown"] += 1
                add(
                    DiagnosticIssue(
                        "extension.unknown",
                        IssueSeverity.ERROR if unknown == "error" else IssueSeverity.INFO,
                        "no schema is registered for this extension",
                        location,
                        {"key": key, "version": value.version},
                        "unknown-extension",
                    )
                )
                continue
            if value.version not in schema.versions:
                add(
                    DiagnosticIssue(
                        "extension.unsupported-version",
                        IssueSeverity.ERROR,
                        "unsupported extension version",
                        f"{location}.version",
                        {"version": value.version, "supported": sorted(schema.versions)},
                    )
                )
                continue
            if scope not in schema.scopes:
                add(DiagnosticIssue("extension.scope", IssueSeverity.ERROR, "extension is not allowed in this scope", location))
                continue
            counts["checked"] += 1
            if schema.validator is None:
                continue
            context = ExtensionContext(key, value.version, value.data, f"{location}.data", scope, owner)
            output = schema.validator(context)
            if output is None:
                continue
            try:
                iterator = iter(output)
            except TypeError as error:
                raise ValueError("extension validator must return diagnostics or None") from error
            for issue in iterator:
                if not isinstance(issue, DiagnosticIssue):
                    raise ValueError("extension validator must return DiagnosticIssue values")
                suffix = f".{issue.location}" if issue.location else ""
                add(
                    DiagnosticIssue(
                        issue.code, issue.severity, issue.message, context.location + suffix, issue.measurement, issue.reason
                    )
                )
    result = CheckResult(issues, {"extensions": counts})
    result.to_dict(limits=limits)
    return result


def check_extensions(
    document: DocumentModel,
    schemas: Iterable[ExtensionSchema],
    *,
    unknown: UnknownExtensionPolicy = "error",
    limits: DocumentLimits | None = None,
) -> CheckResult:
    """Check the whole model plus declared extension schemas, without global registration.

    Callback data/diagnostics are independent snapshots. Callback exceptions
    propagate; no executable names are loaded from JSON. Opaque bytes remain opaque.
    """
    from opendoc._validation import _model_issues

    resolved = _resolve_limits(limits)
    selected = _schemas(schemas, resolved)
    if unknown not in ("error", "preserve"):
        raise ValueError("unknown must be error or preserve")
    issues = _model_issues(document, resolved)
    if issues:
        return CheckResult(issues, {"extensions": {"checked": None, "unknown": None, "opaque": None}})
    return _check_extensions(document, selected, unknown, resolved)


__all__ = [
    "ExtensionCallback",
    "ExtensionContext",
    "ExtensionSchema",
    "ExtensionScope",
    "ExtensionValue",
    "UnknownExtensionPolicy",
    "check_extensions",
    "get_extension",
    "remove_extension",
    "set_extension",
]
