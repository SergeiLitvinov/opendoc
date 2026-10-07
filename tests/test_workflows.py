"""End-to-end model workflows combining structure, dependencies and safe edits."""

from pathlib import Path
from socket import socket

import pytest

from opendoc_model import (
    Anchor,
    ArtifactLimitError,
    DocumentLimits,
    DocumentModel,
    Image,
    IntegrationModel,
    InternalLink,
    Paragraph,
    Resource,
    ResourceKind,
    Section,
    Table,
    TableCell,
    TableRow,
    TextPosition,
    TextRange,
    TextRun,
    TextStyle,
    compare_documents,
    document_from_json,
    document_to_json,
    edit_anchored_text,
    extract_document,
    extract_text,
    get_integration,
    get_internal_link,
    iter_elements,
    iter_internal_links,
    merge_documents,
    remove_node,
    resolve_anchor,
    set_anchor,
    set_integration,
    set_internal_link,
    transform_elements,
)


def _report():
    target = Paragraph([TextRun("Приложение — 概要")], style_id="body")
    set_anchor(target, Anchor("appendix"))
    link = TextRun("См. приложение")
    set_internal_link(link, InternalLink("appendix"))
    text = TextRun("Цена: 100 ₽; e\u0301; 👩\u200d💻")
    set_anchor(text, Anchor("amount"))
    detail = Paragraph([text, link, Image("diagram", "Схема")], style_id="body")
    nested = Table([TableRow([TableCell([detail]), TableCell()])])
    table = Table([TableRow([TableCell([nested], column_span=2)])])
    return DocumentModel(
        sections=[Section(blocks=[table]), Section(blocks=[target])],
        resources={"diagram": Resource("diagram", ResourceKind.RASTER_IMAGE, "image/png", b"opaque image bytes")},
        styles={"body": TextStyle(properties={"base_style_id": "base"}), "base": TextStyle(bold=True)},
    )


def test_nested_report_roundtrip_extraction_and_merge_keep_dependency_closure():
    original = _report()
    before = document_to_json(original)
    restored = document_from_json(before)
    assert restored.validate() == []
    assert compare_documents(original, restored).lossless
    detail = next(iter_elements(restored, Paragraph))
    extracted = extract_document(restored, detail)
    assert extracted.validate() == []
    assert resolve_anchor(extracted, "appendix") is not None
    assert set(extracted.styles) == {"body", "base"}
    assert extracted.resources["diagram"].data == b"opaque image bytes"
    assert "概要" in extract_text(extracted)

    merged = merge_documents([original, restored], conflicts="rename")
    assert merged.document.validate() == []
    assert merged.id_maps[1].anchors == {"amount": "amount~2", "appendix": "appendix~2"}
    assert [get_internal_link(item.node).target_id for item in iter_internal_links(merged.document)] == ["appendix", "appendix~2"]
    second = resolve_anchor(merged.document, "amount~2").node
    second.text = "Изменено"
    assert resolve_anchor(merged.document, "amount").node.text == resolve_anchor(original, "amount").node.text
    assert document_to_json(original) == before == document_to_json(restored)


@pytest.mark.parametrize("replacement", ["150 ₽", "e\u0301", "👩\u200d💻", "概要", ""])
def test_unicode_edit_in_nested_table_preserves_links_bytes_and_tracked_range(replacement):
    original = _report()
    run = resolve_anchor(original, "amount").node
    start, end = run.text.index("100"), run.text.index("100") + 3
    set_integration(
        original,
        IntegrationModel(ranges=(TextRange("price", TextPosition("amount", start, "before"), TextPosition("amount", end)),)),
    )
    before = document_to_json(original)
    edited = edit_anchored_text(original, "amount", start, end, replacement)
    restored = document_from_json(document_to_json(edited))
    assert restored.validate() == []
    changed = resolve_anchor(restored, "amount").node
    assert changed.text == run.text[:start] + replacement + run.text[end:]
    interval = get_integration(restored).ranges[0]
    assert changed.text[interval.start.offset : interval.end.offset] == replacement
    assert restored.resources["diagram"].data == original.resources["diagram"].data
    assert resolve_anchor(restored, "appendix") is not None

    def unsafe_edit(item):
        item.node.text = "unsafe"
        return item.node

    with pytest.raises(ValueError, match="edit_anchored_text"):
        transform_elements(original, TextRun, unsafe_edit)
    location = next(item for item in iter_elements(original, TextRun) if item.node is run)
    with pytest.raises(ValueError):
        remove_node(original, location)
    assert document_to_json(original) == before


def test_external_resource_stays_unmeasured_without_implicit_io(monkeypatch):
    original = _report()
    original.resources["diagram"].data = None
    original.resources["diagram"].source = "https://example.invalid/diagram.png"

    def forbidden(*args, **kwargs):
        raise AssertionError("Model operations must not read external resources")

    monkeypatch.setattr(Path, "open", forbidden)
    monkeypatch.setattr(Path, "stat", forbidden)
    monkeypatch.setattr(socket, "connect", forbidden)
    restored = document_from_json(document_to_json(original))
    extracted = extract_document(restored, next(iter_elements(restored, Paragraph)))
    assert extracted.resources["diagram"].source == original.resources["diagram"].source
    assert extracted.resources["diagram"].data is None
    result = compare_documents(original, restored)
    assert any(issue.code == "measurement.unavailable" and issue.reason == "external-data-not-loaded" for issue in result.issues)
    resources = result.metrics["source"]["resources"]
    assert resources[0]["sha256"] is None


def test_large_unicode_report_roundtrip_edit_and_quota_failure_keep_input():
    paragraphs = [Paragraph([TextRun(f"Строка {index}: 概要 😀 e\u0301")]) for index in range(2048)]
    original = DocumentModel(sections=[Section(blocks=paragraphs)])
    before = document_to_json(original)
    restored = document_from_json(before)
    assert extract_text(restored) == "\n".join(item.plain_text for item in paragraphs)
    edited = transform_elements(restored, TextRun, lambda item: TextRun(item.node.text.replace("Строка", "Запись")))
    assert len(list(iter_elements(edited, Paragraph))) == 2048
    assert extract_text(edited).startswith("Запись 0:")
    with pytest.raises(ArtifactLimitError, match="nodes"):
        transform_elements(original, TextRun, lambda item: TextRun("changed"), limits=DocumentLimits(max_nodes=1000))
    assert document_to_json(original) == before == document_to_json(restored)
