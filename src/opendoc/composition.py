"""Dependency-complete extraction and explicit, independent document merging."""

from __future__ import annotations

from collections import deque
from collections.abc import Collection, Iterable, Iterator
from copy import deepcopy
from dataclasses import dataclass, field, replace
from typing import Literal, TypeAlias, cast

from opendoc._validation import _validate_model
from opendoc.document_model import (
    Block,
    ConversionMode,
    DocumentModel,
    Formula,
    Image,
    PackageGraph,
    Paragraph,
    Section,
    Table,
    TableCell,
    TableRow,
    TextRun,
    TextStyle,
)
from opendoc.limits import DocumentLimits, _guard_model, _quota, _resolve_limits
from opendoc.lists import LIST_PROPERTY, get_list_item, iter_list_items
from opendoc.operations import _attached
from opendoc.storage import ArtifactLimitError
from opendoc.traversal import (
    SECTION_CONTENT_FIELDS,
    ModelNode,
    NodeLocation,
    _set_resource_reference,
    _walk_locations,
    iter_resource_references,
)

IdentifierConflictPolicy: TypeAlias = Literal["error", "rename"]
MetadataConflictPolicy: TypeAlias = Literal["error", "keep_first", "keep_last"]
PackagePolicy: TypeAlias = Literal["error", "preserve", "drop"]


@dataclass(frozen=True)
class DocumentIdMap:
    """Original-to-result identifiers for one input, including unchanged IDs."""

    styles: dict[str, str]
    resources: dict[str, str]
    lists: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class DocumentMerge:
    """Independent merged model and per-input identifier snapshots."""

    document: DocumentModel
    id_maps: tuple[DocumentIdMap, ...]


@dataclass(frozen=True)
class _StyleLink:
    owner: Paragraph | Table | TextStyle
    field: str
    identifier: str
    path: str

    def set(self, identifier: str) -> None:
        if self.field == "style_id" and isinstance(self.owner, (Paragraph, Table)):
            self.owner.style_id = identifier
        else:
            self.owner.properties[self.field] = identifier


def _link(owner: Paragraph | Table | TextStyle, field: str, value: object, path: str) -> Iterator[_StyleLink]:
    if value is not None:
        if not isinstance(value, str) or not value:
            raise ValueError(f"{path}: expected nonempty style identifier")
        yield _StyleLink(owner, field, value, path)


def _text_style_links(style: TextStyle, path: str) -> Iterator[_StyleLink]:
    for name in ("base_style_id", "numbering_source_style_id"):
        yield from _link(style, name, style.properties.get(name), f"{path}.properties.{name}")


def _model_style_links(root: ModelNode, limits: DocumentLimits) -> Iterator[_StyleLink]:
    for reference in _walk_locations(root, limits):
        node, path = reference.node, reference.path
        if isinstance(node, (Paragraph, Table)):
            yield from _link(node, "style_id", node.style_id, f"{path}.style_id")
        if isinstance(node, Paragraph):
            name = "numbering_source_style_id"
            yield from _link(node, name, node.properties.get(name), f"{path}.properties.{name}")
        elif isinstance(node, TextRun):
            yield from _text_style_links(node.style, f"{path}.style")


def _all_style_links(document: DocumentModel, limits: DocumentLimits) -> Iterator[_StyleLink]:
    yield from _model_style_links(document, limits)
    for identifier, style in document.styles.items():
        yield from _text_style_links(style, f"styles[{identifier!r}]")


def _require_document(document: DocumentModel, limits: DocumentLimits, label: str) -> tuple[int, int]:
    if not isinstance(document, DocumentModel):
        raise ValueError(f"{label}: expected DocumentModel")
    try:
        size = _guard_model(document, limits)
    except ArtifactLimitError as error:
        raise ArtifactLimitError(f"{label}: {error}") from error
    except ValueError as error:
        raise ValueError(f"{label}: {error}") from error
    errors = _validate_model(document, limits, preflight=False)
    if errors:
        raise ValueError(f"{label}: {'; '.join(errors)}")
    return size


def _policy(value: str, choices: tuple[str, ...], name: str) -> None:
    if value not in choices:
        raise ValueError(f"{name}: expected {', '.join(choices)}")


def _inputs(documents: Iterable[DocumentModel], limits: DocumentLimits) -> list[DocumentModel]:
    try:
        iterator = iter(documents)
    except TypeError as error:
        raise ValueError("documents: expected an iterable of DocumentModel") from error
    result: list[DocumentModel] = []
    nodes, embedded = 0, 0
    for index, document in enumerate(iterator):
        if nodes == limits.max_nodes:
            _quota("documents", "nodes", limits.max_nodes)
        remaining = replace(limits, max_nodes=limits.max_nodes - nodes, max_embedded_bytes=limits.max_embedded_bytes - embedded)
        count, byte_count = _require_document(document, remaining, f"documents[{index}]")
        nodes += count
        embedded += byte_count
        for link in _all_style_links(document, limits):
            if link.identifier not in document.styles:
                raise ValueError(f"documents[{index}].{link.path}: unknown style {link.identifier!r}")
        result.append(document)
    if not result:
        raise ValueError("documents: expected at least one document")
    return result


def _definition_ids(
    document: DocumentModel, domain: Literal["styles", "resources", "lists"], limits: DocumentLimits | None = None
) -> Iterable[str]:
    if domain == "lists":
        identifiers: dict[str, None] = {}
        for location in iter_list_items(document, limits=limits):
            item = get_list_item(location.node, limits=limits)
            assert item is not None
            identifiers[item.list_id] = None
        return identifiers
    return document.styles if domain == "styles" else document.resources


def _id_maps(
    documents: list[DocumentModel],
    domain: Literal["styles", "resources", "lists"],
    policy: IdentifierConflictPolicy,
    limits: DocumentLimits | None = None,
) -> list[dict[str, str]]:
    reserved = {identifier for document in documents for identifier in _definition_ids(document, domain, limits)}
    used: set[str] = set()
    next_suffix: dict[str, int] = {}
    maps: list[dict[str, str]] = []
    for index, document in enumerate(documents):
        identifiers: dict[str, str] = {}
        for identifier in _definition_ids(document, domain, limits):
            target = identifier
            if target in used:
                if policy == "error":
                    raise ValueError(f"documents[{index}].{domain}[{identifier!r}]: identifier conflict")
                suffix = next_suffix.get(identifier, 2)
                while f"{identifier}~{suffix}" in reserved or f"{identifier}~{suffix}" in used:
                    suffix += 1
                target = f"{identifier}~{suffix}"
                next_suffix[identifier] = suffix + 1
            identifiers[identifier] = target
            used.add(target)
        maps.append(identifiers)
    return maps


def _package(documents: list[DocumentModel], policy: PackagePolicy) -> PackageGraph | None:
    if policy == "drop":
        return None
    packages = [document.package for document in documents]
    if not any(package is not None for package in packages):
        return None
    if len(documents) == 1:
        return packages[0]
    if policy == "error":
        raise ValueError("package: merging opaque packages requires an explicit preserve/drop policy")
    first = packages[0]
    if first is None or any(package is None or package != first for package in packages[1:]):
        raise ValueError("package: preserve requires identical graphs in every input; parts cannot be renamed safely")
    return first


def _rewrite(document: DocumentModel, identifiers: DocumentIdMap, limits: DocumentLimits) -> None:
    # Snapshot values before writing: repeated nodes and shared property bags
    # must not apply a mapping again to an already rewritten identifier.
    styles = list(_all_style_links(document, limits))
    resources = list(iter_resource_references(document, limits=limits))
    lists = [
        (location.node.properties[LIST_PROPERTY], get_list_item(location.node, limits=limits))
        for location in iter_list_items(document, limits=limits)
    ]
    for value, item in lists:
        assert item is not None
        value["list_id"] = identifiers.lists[item.list_id]
    for link in styles:
        link.set(identifiers.styles[link.identifier])
    for link in resources:
        _set_resource_reference(link, identifiers.resources[link.resource_id])
    document.styles = {identifiers.styles[identifier]: style for identifier, style in document.styles.items()}
    remapped_resources = {}
    for identifier, resource in document.resources.items():
        resource.id = identifiers.resources[identifier]
        remapped_resources[resource.id] = resource
    document.resources = remapped_resources


def merge_documents(
    documents: Iterable[DocumentModel],
    *,
    conflicts: IdentifierConflictPolicy = "error",
    metadata_conflicts: MetadataConflictPolicy = "error",
    package_policy: PackagePolicy = "error",
    mode: ConversionMode | None = None,
    limits: DocumentLimits | None = None,
) -> DocumentMerge:
    """Concatenate sections, preserving independent definitions and known links.

    Conflicting IDs either fail or get deterministic reserved-name-safe suffixes.
    All definitions, including unused ones, are retained. Metadata overlap and
    differing modes require explicit decisions. Opaque packages are never rewritten.
    Input value/embedded-byte counts share a budget; output is validated separately.
    """
    _policy(conflicts, ("error", "rename"), "conflicts")
    _policy(metadata_conflicts, ("error", "keep_first", "keep_last"), "metadata_conflicts")
    _policy(package_policy, ("error", "preserve", "drop"), "package_policy")
    if mode is not None and not isinstance(mode, ConversionMode):
        raise ValueError("mode: expected ConversionMode or None")
    budget = _resolve_limits(limits)
    inputs = _inputs(documents, budget)
    result_mode = mode or inputs[0].mode
    if mode is None and any(document.mode != result_mode for document in inputs[1:]):
        raise ValueError("mode: input modes differ; select an explicit result mode")
    package = _package(inputs, package_policy)
    style_maps = _id_maps(inputs, "styles", conflicts)
    resource_maps = _id_maps(inputs, "resources", conflicts)
    list_maps = _id_maps(inputs, "lists", conflicts, budget)
    maps = tuple(
        DocumentIdMap(styles, resources, lists)
        for styles, resources, lists in zip(style_maps, resource_maps, list_maps, strict=True)
    )
    result = DocumentModel(mode=result_mode, source_format=inputs[0].source_format, package=deepcopy(package))
    if any(document.source_format != result.source_format for document in inputs[1:]):
        result.source_format = None
    for index, document in enumerate(inputs):
        copied = deepcopy(document)
        _rewrite(copied, maps[index], budget)
        result.sections.extend(copied.sections)
        result.styles.update(copied.styles)
        result.resources.update(copied.resources)
        for key, value in copied.metadata.items():
            if key in result.metadata:
                if metadata_conflicts == "error":
                    raise ValueError(f"documents[{index}].metadata[{key!r}]: metadata conflict")
                if metadata_conflicts == "keep_first":
                    continue
            result.metadata[key] = value
    _require_document(result, budget, "result")
    return DocumentMerge(result, maps)


def _ancestor(location: NodeLocation[ModelNode], expected: type[ModelNode]) -> ModelNode:
    current = location.parent
    while current is not None:
        if isinstance(current.node, expected):
            return current.node
        current = current.parent
    raise ValueError(f"{location.path}: missing structural ancestor {expected.__name__}")


def _section_shell(location: NodeLocation[ModelNode]) -> tuple[Section, str]:
    section = location.section
    if section is None:
        raise ValueError(f"{location.path}: missing containing section")
    top = location
    while top.parent is not None and not isinstance(top.parent.node, Section):
        top = top.parent
    field = cast(str, top.field)
    return replace(section, **{name: [] for name in SECTION_CONTENT_FIELDS}), field


def _selected_sections(location: NodeLocation[ModelNode]) -> list[Section]:
    node = location.node
    if isinstance(node, Section):
        return [node]
    section, field = _section_shell(location)
    block: Block
    if isinstance(node, TableCell):
        row = replace(cast(TableRow, _ancestor(location, TableRow)), cells=[node])
        block = replace(cast(Table, _ancestor(location, Table)), rows=[row])
    elif isinstance(node, TableRow):
        block = replace(cast(Table, _ancestor(location, Table)), rows=[node])
    elif isinstance(node, TextRun) or isinstance(node, (Image, Formula)) and location.kind == "inline":
        block = replace(cast(Paragraph, _ancestor(location, Paragraph)), content=[node])
    elif isinstance(node, (Paragraph, Table, Image, Formula)):
        block = node
    else:
        raise ValueError(f"{location.path}: unsupported extraction node")
    getattr(section, field).append(block)
    return [section]


def _extra_ids(values: Iterable[str], available: Collection[str], name: str, limits: DocumentLimits) -> set[str]:
    if isinstance(values, (str, bytes)):
        raise ValueError(f"{name}: expected an iterable of identifiers, not a string")
    try:
        iterator = iter(values)
    except TypeError as error:
        raise ValueError(f"{name}: expected an iterable of identifiers") from error
    identifiers: set[str] = set()
    for index, identifier in enumerate(iterator):
        if index >= limits.max_nodes:
            _quota(name, "nodes", limits.max_nodes)
        if not isinstance(identifier, str) or not identifier:
            raise ValueError(f"{name}[{index}]: expected nonempty identifier")
        if identifier not in available:
            raise ValueError(f"{name}[{index}]: unknown identifier {identifier!r}")
        identifiers.add(identifier)
    return identifiers


def _dependencies(
    selected: DocumentModel,
    source: DocumentModel,
    additional_styles: set[str],
    additional_resources: set[str],
    limits: DocumentLimits,
) -> tuple[set[str], set[str]]:
    _guard_model(selected, limits)
    needed_styles: set[str] = set()
    pending = deque((link.identifier, link.path) for link in _model_style_links(selected, limits))
    pending.extend((identifier, f"additional_styles[{identifier!r}]") for identifier in sorted(additional_styles))
    while pending:
        identifier, path = pending.popleft()
        if identifier in needed_styles:
            continue
        if identifier not in source.styles:
            raise ValueError(f"{path}: unknown style {identifier!r}")
        needed_styles.add(identifier)
        pending.extend(
            (link.identifier, link.path) for link in _text_style_links(source.styles[identifier], f"styles[{identifier!r}]")
        )
    needed_resources = {
        reference.resource_id for reference in iter_resource_references(selected, limits=limits)
    } | additional_resources
    return needed_styles, needed_resources


def extract_document(
    document: DocumentModel,
    location: NodeLocation[ModelNode],
    *,
    package_policy: PackagePolicy = "error",
    additional_styles: Iterable[str] = (),
    additional_resources: Iterable[str] = (),
    limits: DocumentLimits | None = None,
) -> DocumentModel:
    """Extract a dependency-complete independent document from a live occurrence.

    Sections retain all content; smaller subtrees get minimal container shells
    preserving page/section, paragraph or row/table context and header collection.
    Used styles (including transitive links) and resources are copied. Metadata is
    retained; unused definitions are omitted. Package preservation is explicit for
    partial extraction and keeps the entire opaque graph, without pruning bytes.
    """
    _policy(package_policy, ("error", "preserve", "drop"), "package_policy")
    budget = _resolve_limits(limits)
    _require_document(document, budget, "document")
    _attached(document, location)
    extra_styles = _extra_ids(additional_styles, document.styles, "additional_styles", budget)
    extra_resources = _extra_ids(additional_resources, document.resources, "additional_resources", budget)
    if isinstance(location.node, DocumentModel):
        selected = replace(document, version=2, package=_package([document], package_policy))
    else:
        if document.package is not None and package_policy == "error":
            raise ValueError("package: partial extraction requires an explicit preserve/drop policy")
        selected = DocumentModel(
            sections=_selected_sections(location),
            metadata=document.metadata,
            package=None if package_policy == "drop" else document.package,
            mode=document.mode,
            source_format=document.source_format,
        )
        styles, resources = _dependencies(selected, document, extra_styles, extra_resources, budget)
        selected.styles = {identifier: style for identifier, style in document.styles.items() if identifier in styles}
        selected.resources = {
            identifier: resource for identifier, resource in document.resources.items() if identifier in resources
        }
    _require_document(selected, budget, "result")
    return deepcopy(selected)


__all__ = [
    "DocumentIdMap",
    "DocumentMerge",
    "IdentifierConflictPolicy",
    "MetadataConflictPolicy",
    "PackagePolicy",
    "extract_document",
    "merge_documents",
]
