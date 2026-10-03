"""Deliberate static errors; checked but never executed."""

from opendoc import CheckResult, ColorValue, DocumentComparison, DocumentInspection, MatchingLimits, TextRun


def incorrect(inspection: DocumentInspection, comparison: DocumentComparison, result: CheckResult) -> None:
    TextRun(123)  # type-error: arg-type
    MatchingLimits(max_work="many")  # type-error: arg-type
    ColorValue.from_hex("#123456", alpha="opaque")  # type-error: arg-type
    inspection.to_dict()["valid"] = "yes"  # type-error: typeddict-item
    comparison.to_dict()["retention"]["characters"]["ratio"] = "complete"  # type-error: assignment
    result.to_dict()["issues"][0]["reason"] = 42  # type-error: typeddict-item
