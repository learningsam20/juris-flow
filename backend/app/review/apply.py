"""Merge review findings back into the source contract.

Powers the dashboard's "Apply on existing contract" action: one Markdown file
containing the original contract text with every flagged clause replaced by its
proposed amendment (risks marked as remediated), followed by an appendix listing
each finding, its risk level and its implementation status.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.exports.markdown import with_disclaimer
from app.review.extractor import is_abstained_text

# Inline marker shown in the merged text for a finding's implementation state.
STATUS_MARKER = {
    "applied": "✅ REMEDIATED",
    "in_progress": "⏳ IMPLEMENTATION IN PROGRESS",
    "not_started": "📝 PROPOSED — NOT YET APPLIED",
}

STATUS_ORDER = ("applied", "in_progress", "not_started")

RISK_FLAG = {"high": "🔴 High", "medium": "🟡 Medium", "low": "🟢 Low"}


@dataclass
class ApplyFinding:
    id: str
    clause_type: str
    risk_level: str
    text: str
    span_start: int | None
    span_end: int | None
    proposed_change: str
    implementation_status: str
    obligation: bool = False


def _marker(f: ApplyFinding, status: str) -> str:
    label = STATUS_MARKER.get(status, STATUS_MARKER["not_started"])
    clause = (f.clause_type or "general").replace("_", " ")
    risk = RISK_FLAG.get(f.risk_level, f.risk_level.title())
    return f"> **[{label} · {clause} · {risk} risk]**"


def build_applied_markdown(
    *,
    document_title: str,
    document_text: str,
    findings: list[ApplyFinding],
    applied_ids: set[str],
) -> tuple[str, dict]:
    """Return ``(markdown, summary)`` for the merged contract document.

    Findings in ``applied_ids`` have their source span replaced by the proposed
    amendment and are marked remediated; findings still in progress keep their
    original text and carry an in-progress marker.
    """
    body_parts: list[str] = []
    cursor = 0
    amendments = 0
    marked = 0

    spans = [f for f in findings if f.span_start is not None and f.span_end is not None]
    for f in sorted(spans, key=lambda x: int(x.span_start or 0)):
        start, end = int(f.span_start or 0), int(f.span_end or 0)
        if start < cursor or start >= end or end > len(document_text):
            continue  # overlapping or stale span: leave the source untouched
        body_parts.append(document_text[cursor:start])
        original = document_text[start:end]
        status = _status_for(f, applied_ids)
        if f.id in applied_ids and f.proposed_change:
            body_parts.append(_marker(f, "applied"))
            body_parts.append("\n\n")
            body_parts.append(f.proposed_change.strip())
            body_parts.append("\n")
            amendments += 1
            marked += 1
        else:
            body_parts.append(original)
            if status == "in_progress":
                body_parts.append("\n\n")
                body_parts.append(_marker(f, "in_progress"))
                body_parts.append("\n")
                marked += 1
        cursor = end
    body_parts.append(document_text[cursor:])
    body = "".join(body_parts).strip()

    summary = _summary(findings, applied_ids, amendments, marked)
    appendix = _appendix(findings, applied_ids)

    parts = [
        f"# Remediated Contract — {document_title}",
        "",
        f"**Generated from review findings:** {summary['total']} flagged",
        f"**Remediated in this document:** {summary['applied']}",
        f"**Implementation in progress:** {summary['in_progress']}",
        f"**Awaiting implementation:** {summary['not_started']}",
        f"**Amendments applied to the text below:** {summary['amendments']}",
        "",
        (
            "Each flagged clause below is replaced by its proposed amendment and "
            "tagged with its implementation status, so every risk in this document "
            "reads as remediated, in progress, or proposed."
        ),
        "",
        "## Remediated Contract Text",
        "",
        body,
        "",
        "## Remediation Appendix",
        "",
        appendix,
    ]
    return with_disclaimer("\n".join(parts), kind="Remediated Contract"), summary


def _status_for(f: ApplyFinding, applied_ids: set[str]) -> str:
    if f.id in applied_ids:
        return "applied"
    status = (f.implementation_status or "not_started").strip()
    return status if status in STATUS_MARKER else "not_started"


def _summary(
    findings: list[ApplyFinding], applied_ids: set[str], amendments: int, marked: int
) -> dict:
    counts = {key: 0 for key in STATUS_ORDER}
    for f in findings:
        counts[_status_for(f, applied_ids)] += 1
    return {
        "total": len(findings),
        "applied": counts["applied"],
        "in_progress": counts["in_progress"],
        "not_started": counts["not_started"],
        "amendments": amendments,
        "marked": marked,
    }


def _appendix(findings: list[ApplyFinding], applied_ids: set[str]) -> str:
    if not findings:
        return "_No findings recorded for this review._"
    rows = [
        "| # | Clause | Risk | Status | Grounded |",
        "| --- | --- | --- | --- | --- |",
    ]
    for i, f in enumerate(sorted(findings, key=lambda x: x.clause_type), start=1):
        status = _status_for(f, applied_ids)
        marker = STATUS_MARKER[status]
        clause = (f.clause_type or "general").replace("_", " ").title()
        risk = RISK_FLAG.get(f.risk_level, str(f.risk_level).title())
        grounded = "No — needs human check" if is_abstained_text(f.text) else "Yes"
        rows.append(f"| {i} | {clause} | {risk} | {marker} | {grounded} |")
    rows.append("")
    rows.append(
        "Status meanings: ✅ remediated (amendment merged into the text above) · "
        "⏳ implementation in progress (tracked on the dashboard) · "
        "📝 proposed, not yet applied."
    )
    return "\n".join(rows)
