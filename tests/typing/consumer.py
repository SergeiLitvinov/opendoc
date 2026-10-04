"""Typed consumer of the installed library; also executed in its empty environment."""

from pathlib import Path
from typing import Any, assert_type

from opendoc import (
    Anchor,
    CapabilityProfile,
    CheckData,
    CheckResult,
    ColorValue,
    ComparisonData,
    ConversionIssueData,
    ConversionReport,
    ConversionReportData,
    DiagnosticData,
    DiagnosticIssue,
    DocumentComparison,
    DocumentInspection,
    DocumentModel,
    Footnote,
    InspectionData,
    IntegrationModel,
    IssueSeverity,
    NodeLocation,
    Paragraph,
    ParagraphProperties,
    PreservationState,
    Section,
    TextPosition,
    TextRange,
    TextRun,
    check_document,
    clone_model,
    compare_inspections,
    document_from_json,
    document_to_json,
    edit_anchored_text,
    get_integration,
    inspect_document_model,
    iter_elements,
    iter_footnotes,
    negotiate_capabilities,
    preservation_result,
    set_anchor,
    set_integration,
)
from opendoc.object_matching import ObjectMatch, match_objects
from opendoc.text_flow import TextFlowData, TextFlowFingerprint


def main() -> None:
    paragraph = Paragraph([TextRun("Typed consumer")], properties=ParagraphProperties({"custom": {"revision": 3}}))
    document = DocumentModel(sections=[Section(blocks=[paragraph])], footnotes=[Footnote("note")])
    assert_type(clone_model(document), DocumentModel)
    assert_type(document_from_json(document_to_json(document)), DocumentModel)
    location = next(iter_elements(document, Paragraph))
    assert_type(location, NodeLocation[Paragraph])
    assert_type(location.node, Paragraph)
    assert_type(next(iter_footnotes(document)), NodeLocation[Footnote])
    color = ColorValue.from_hex("#123456", alpha=0.5, blend_mode="normal")
    assert_type(color, ColorValue)
    inspection = inspect_document_model(document)
    assert_type(inspection, DocumentInspection)
    snapshot = inspection.to_dict()
    assert_type(snapshot, InspectionData)
    assert_type(snapshot["valid"], bool)
    assert_type(snapshot["source_path"], str | None)
    assert_type(snapshot["metrics"]["paragraphs"], int)
    assert_type(snapshot["issues"], list[ConversionIssueData])
    # Open consumer schemas remain dynamic; the checker does not infer their fields.
    assert_type(paragraph.properties["custom"], Any)
    comparison = compare_inspections(inspection, inspection)
    assert_type(comparison, DocumentComparison)
    measured = comparison.to_dict()
    assert_type(measured, ComparisonData)
    assert_type(measured["has_losses"], bool)
    assert_type(measured["retention"]["characters"]["ratio"], float | int | None)
    assert_type(measured["matching_resource_hashes"], int)
    result = check_document(document)
    assert_type(result, CheckResult)
    checked = result.to_dict()
    assert_type(checked, CheckData)
    assert_type(checked["version"], int)
    assert_type(checked["success"], bool)
    issue = DiagnosticIssue("consumer.info", IssueSeverity.INFO, "Typed diagnostic")
    result.issues.append(issue)
    assert_type(result.to_dict()["issues"][0], DiagnosticData)
    assert_type(result.to_dict()["issues"][0]["reason"], str | None)
    report = ConversionReport(Path("consumer-output"))
    report.add(IssueSeverity.INFO, "consumer", "Typed conversion report")
    assert_type(report.to_dict(), ConversionReportData)
    assert_type(report.to_dict()["output_path"], str)
    assert_type(report.to_dict()["issues"][0], ConversionIssueData)
    objects = [{"type": "paragraph", "content_hash": "same", "location": "one"}]
    matches, _, _ = match_objects(objects, objects)
    assert_type(matches, list[ObjectMatch])
    assert_type(matches[0]["source_index"], int)
    flow = TextFlowFingerprint()
    flow.add("typed text")
    assert_type(flow.to_dict(), TextFlowData)
    assert_type(flow.to_dict()["tokens"], list[str] | None)
    assert result.success and snapshot["valid"] and measured["valid"]
    run = paragraph.content[0]
    assert isinstance(run, TextRun)
    set_anchor(run, Anchor("typed-run"))
    model = IntegrationModel(
        ranges=(TextRange("typed-range", TextPosition("typed-run", 0), TextPosition("typed-run", len(run.text))),)
    )
    set_integration(document, model)
    assert_type(get_integration(document), IntegrationModel | None)
    assert_type(edit_anchored_text(document, "typed-run", 0, 1, "x"), DocumentModel)
    assert_type(preservation_result(model), CheckResult)
    profile = CapabilityProfile("typed-profile", 1)
    assert_type(negotiate_capabilities(profile, profile), dict[str, tuple[PreservationState, ...]])
    print("Installed typed consumer: runtime and named result fields OK")


if __name__ == "__main__":
    main()
