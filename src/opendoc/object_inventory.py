"""Recursive inventory of model objects, independent of run segmentation."""

import hashlib
from collections.abc import Iterator
from dataclasses import asdict
from typing import Any

from opendoc.document_model import Footnote, Formula, Image, Paragraph, Resource, Table, TextRun
from opendoc.emphasis_quality import EmphasisInventory
from opendoc.lists import LIST_PROPERTY, _list_payload
from opendoc.semantics import HEADING_PROPERTY, _heading_payload
from opendoc.text_flow import TextFlowFingerprint
from opendoc.traversal import ModelNode, NodeLocation, walk_model

OBJECT_INVENTORY_SCOPE = "model-recursive-objects-v1"


def inspect_objects(
    value: Any,
    location: str,
    page_index: int,
    resources: dict[str, Resource],
    *,
    parent: str | None = None,
    text_flow: TextFlowFingerprint | None = None,
    emphasis: EmphasisInventory | None = None,
) -> Iterator[dict[str, Any]]:
    for reference in walk_model(value):
        node = reference.node
        if isinstance(node, Footnote):
            continue
        if not isinstance(node, (Paragraph, Table, Formula, Image)) and reference.parent is not None:
            continue
        local = f"{location}.{reference.path}" if reference.path else location
        ancestor = reference.parent
        owner = parent
        while ancestor is not None:
            if isinstance(ancestor.node, (Paragraph, Table)):
                owner = f"{location}.{ancestor.path}" if ancestor.path else location
                break
            ancestor = ancestor.parent
        yield _object_entry(node, local, page_index, resources, parent=owner, text_flow=text_flow, emphasis=emphasis)


def _inventory_parent(reference: NodeLocation[ModelNode]) -> str | None:
    ancestor = reference.parent
    while ancestor is not None:
        if isinstance(ancestor.node, (Paragraph, Table)):
            return ancestor.path
        ancestor = ancestor.parent
    return None


def _object_entry(
    value: Any,
    location: str,
    page_index: int | None,
    resources: dict[str, Resource],
    *,
    parent: str | None = None,
    text_flow: TextFlowFingerprint | None = None,
    emphasis: EmphasisInventory | None = None,
) -> dict[str, Any]:
    provenance = getattr(value, "provenance", None)
    provenance_data = None
    if provenance is not None:
        identity = (
            "|".join(
                str(item if item is not None else "")
                for item in (
                    provenance.source_format,
                    provenance.source_path,
                    provenance.page,
                    provenance.package_part,
                    provenance.object_id,
                )
            )
            if provenance.object_id is not None
            else None
        )
        provenance_data = {
            "identity": identity,
            "source_format": provenance.source_format,
            "source_path": provenance.source_path,
            "page": provenance.page,
            "object_id": provenance.object_id,
            "package_part": provenance.package_part,
        }
    box = getattr(value, "box", None)
    geometry = (
        None
        if box is None
        else {
            "x": round(box.x, 3),
            "y": round(box.y, 3),
            "width": round(box.width, 3),
            "height": round(box.height, 3),
            "rotation": round(box.rotation, 3),
        }
    )
    content = _object_content(value, resources)
    # Runs may split/merge during serialization without changing the paragraph.
    text = "".join(item.text for item in value.content if isinstance(item, TextRun)) if isinstance(value, Paragraph) else None
    # Formula values may be LaTeX/OMML source, not comparable visible text.
    if text is not None and text_flow is not None:
        text_flow.add(text)
    if isinstance(value, Paragraph) and emphasis is not None:
        for run in value.content:
            if isinstance(run, TextRun):
                emphasis.add(run)
    formula_data = {}
    if isinstance(value, Formula):
        from opendoc.formula_quality_policy import FORMULA_FINGERPRINT_VERSION, formula_fingerprint

        formula_data = {"formula_hash": formula_fingerprint(value), "formula_fingerprint_version": FORMULA_FINGERPRINT_VERSION}
    semantic_data = {}
    if isinstance(value, Paragraph):
        heading = _heading_payload(value.properties.get(HEADING_PROPERTY), f"{location}.properties[{HEADING_PROPERTY!r}]")
        semantic_data["heading"] = heading.level if heading is not None else None
        item = _list_payload(value.properties.get(LIST_PROPERTY), f"{location}.properties[{LIST_PROPERTY!r}]")
        semantic_data["list_item"] = asdict(item) if item is not None else None
        if item is None or item.kind == "unordered":
            semantic_data["list_number"] = None
    return {
        **semantic_data,
        **formula_data,
        "location": location,
        "parent_location": parent,
        "page": page_index,
        "type": type(value).__name__.lower(),
        "content_hash": hashlib.sha256(content.encode("utf-8")).hexdigest() if content is not None else None,
        "geometry": geometry,
        "style_id": getattr(value, "style_id", None),
        "provenance": provenance_data,
        "text_characters": len(text) if text is not None else None,
        "text_hash": hashlib.sha256(text.encode("utf-8")).hexdigest() if text is not None else None,
    }


def _object_content(value: Any, resources: dict[str, Resource]) -> str | None:
    if isinstance(value, Paragraph):
        return value.plain_text
    if isinstance(value, Formula):
        return value.value
    if isinstance(value, Image):
        resource = resources.get(value.resource_id)
        return hashlib.sha256(resource.data).hexdigest() if resource is not None and resource.data is not None else None
    if isinstance(value, Table):
        rows = []
        for row in value.rows:
            cells = []
            for cell in row.cells:
                blocks = []
                for block in cell.blocks:
                    content = _object_content(block, resources)
                    if content is None:
                        return None
                    blocks.append(content)
                cells.append(" ".join(blocks))
            rows.append("\t".join(cells))
        return "\n".join(rows)
    return ""
