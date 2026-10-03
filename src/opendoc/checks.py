"""In-memory structural checks and comparison through the existing policies."""

from __future__ import annotations

from collections.abc import Iterable
from copy import deepcopy
from dataclasses import replace
from typing import TypeAlias

from opendoc._validation import _model_issues
from opendoc.diagnostics import CheckResult, ConversionIssue, DiagnosticIssue, IssueSeverity
from opendoc.document_model import DocumentModel
from opendoc.emphasis_quality import EmphasisLossPolicy
from opendoc.formula_quality_policy import FormulaLossPolicy
from opendoc.inspection import DocumentComparison, DocumentInspection, compare_inspections, inspect_document_model
from opendoc.limits import DocumentLimits, _quota, _resolve_limits
from opendoc.object_quality_policy import ObjectLossPolicy
from opendoc.quality_policy import QualityPolicy
from opendoc.text_quality_policy import TextPreservationPolicy

CheckPolicy: TypeAlias = QualityPolicy | TextPreservationPolicy | ObjectLossPolicy | FormulaLossPolicy | EmphasisLossPolicy


def _inspect(document: DocumentModel, limits: DocumentLimits) -> tuple[DocumentInspection, list[DiagnosticIssue]]:
    issues = _model_issues(document, limits)
    if issues:
        inspection = DocumentInspection(
            None,
            "document-model",
            issues=[ConversionIssue(issue.severity, "model-validation", issue.message, issue.location) for issue in issues],
        )
        return inspection, issues
    inspection = inspect_document_model(document, limits=limits, check_external_sources=False)
    issues.extend(DiagnosticIssue(issue.feature, issue.severity, issue.message, issue.location) for issue in inspection.issues)
    return inspection, issues


def check_document(document: DocumentModel, *, limits: DocumentLimits | None = None) -> CheckResult:
    """Validate and inspect without any filesystem lookup or output path.

    Structural errors have machine codes/paths; invalid models have no metrics.
    Valid external-only resources remain structurally valid with unknown sizes
    and hashes. DocumentLimits exhaustion continues to raise ArtifactLimitError.
    """
    inspection, issues = _inspect(document, _resolve_limits(limits))
    return CheckResult(issues, {"inspection": deepcopy(inspection.to_dict())})


def _policies(policies: Iterable[CheckPolicy] | None, limits: DocumentLimits) -> list[CheckPolicy]:
    if policies is None:
        return []
    try:
        iterator = iter(policies)
    except TypeError as error:
        raise ValueError("policies must be an iterable of supported policies") from error
    selected: list[CheckPolicy] = []
    for index, policy in enumerate(iterator):
        if index >= limits.max_nodes:
            _quota("policies", "nodes", limits.max_nodes)
        if not isinstance(
            policy, (QualityPolicy, TextPreservationPolicy, ObjectLossPolicy, FormulaLossPolicy, EmphasisLossPolicy)
        ):
            raise ValueError("unsupported check policy")
        selected.append(policy)
    return selected


def _comparison_issue(issue: ConversionIssue, comparison: DocumentComparison) -> DiagnosticIssue:
    measurement = None
    if issue.feature.startswith("retention-"):
        measurement = comparison.retention.get(issue.feature.removeprefix("retention-"))
    elif issue.feature.startswith("page-geometry"):
        measurement = comparison.geometry_summary
    elif issue.feature == "resource-loss":
        measurement = comparison.resource_comparison
    elif issue.feature == "package-part-loss":
        measurement = comparison.package_comparison
    elif issue.feature == "font-substitution":
        measurement = comparison.font_comparison
    elif issue.feature == "object-loss":
        measurement = {"available": comparison.object_diff.get("available"), "location": issue.location}
    elif issue.feature.startswith(("list-", "heading-")):
        change = next(
            (item for item in comparison.object_diff.get("changed", []) if item["source"].get("location") == issue.location), None
        )
        if change is not None:
            field = "heading" if issue.feature.startswith("heading-") else "list_item"
            measurement = {"source": change["source"].get(field), "target": change["target"].get(field)}
            if field == "list_item":
                measurement.update(
                    source_number=change["source"].get("list_number"), target_number=change["target"].get("list_number")
                )
    return DiagnosticIssue(issue.feature, issue.severity, issue.message, issue.location, deepcopy(measurement))


def compare_documents(
    source: DocumentModel,
    target: DocumentModel,
    *,
    policies: Iterable[CheckPolicy] | None = None,
    limits: DocumentLimits | None = None,
) -> CheckResult:
    """Compare entire models in memory and apply explicit policies in order.

    No policy is implicit. LOSS differs from ERROR; a selected policy may turn
    loss or unavailable evidence into rejection. Both model issues and complete
    comparison snapshots are retained; reasons are obtained from measurements.
    Existing ConversionReport usage and policy return values remain supported.
    """
    resolved = _resolve_limits(limits)
    selected = _policies(policies, resolved)
    before, source_issues = _inspect(source, resolved)
    after, target_issues = _inspect(target, resolved)
    comparison = compare_inspections(before, after)
    issues = [
        replace(issue, location=f"{side}.{issue.location}" if issue.location else side)
        for side, side_issues in (("source", source_issues), ("target", target_issues))
        for issue in side_issues
    ]
    issues.extend(_comparison_issue(issue, comparison) for issue in comparison.issues)
    for name, measurement in (
        ("resources", comparison.resource_comparison),
        ("package", comparison.package_comparison),
        ("fonts", comparison.font_comparison),
        ("objects", comparison.object_diff),
        ("geometry", comparison.geometry_summary),
    ):
        if measurement.get("available") is False:
            reason = "invalid-model" if not comparison.valid else "no-pages" if name == "geometry" else "external-data-not-loaded"
            issues.append(
                DiagnosticIssue(
                    "measurement.unavailable",
                    IssueSeverity.INFO,
                    f"{name} measurement is unavailable",
                    f"comparison.{name}",
                    {"name": name, "available": False},
                    reason,
                )
            )
    result = CheckResult(
        issues, deepcopy({"source": before.to_dict(), "target": after.to_dict(), "comparison": comparison.to_dict()})
    )
    for policy in selected:
        if isinstance(policy, QualityPolicy):
            policy.evaluate(result)
        else:
            policy.evaluate(result, comparison)
    return result


__all__ = ["CheckPolicy", "check_document", "compare_documents"]
