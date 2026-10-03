"""List membership survives JSON and remains independent during composition."""

from opendoc import (
    DocumentModel,
    ListItem,
    Paragraph,
    Section,
    TextRun,
    document_from_json,
    document_to_json,
    iter_list_numbers,
    merge_documents,
    set_list_item,
)

paragraphs = [Paragraph([TextRun(text)]) for text in ("First", "Nested", "Second")]
for paragraph, level in zip(paragraphs, (0, 1, 0), strict=True):
    set_list_item(paragraph, ListItem("tasks", level=level))
document = DocumentModel(sections=[Section(blocks=paragraphs)])
assert [item.number for item in iter_list_numbers(document)] == [1, 1, 2]
restored = document_from_json(document_to_json(document))
merged = merge_documents([document, restored], conflicts="rename")
assert merged.id_maps[1].lists == {"tasks": "tasks~2"}
assert [item.number for item in iter_list_numbers(merged.document)] == [1, 1, 2, 1, 1, 2]
print("Lists: numbering, JSON and independent composition OK")
