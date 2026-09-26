"""Document review orchestration (PRD §5.2, §6.5, §8.6)."""

from __future__ import annotations

import logging
import re
import time
import uuid
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.analytics.events import emit
from app.core.telemetry import incr
from app.db.session import SessionLocal
from app.embeddings.factory import get_embeddings
from app.llm.base import LLMProvider
from app.llm.factory import get_llm
from app.models import DocumentReview, LegalDocument, ReviewFinding, ReviewTemplate
from app.review.extractor import (
    ClauseExtraction,
    assign_default_risk,
    review_document_text,
)
from app.review.km_support import attach_km_support
from app.review.plain_language import explain_clause
from app.review.report import build_review_markdown
from app.review.risk import compute_risk_summary
from app.vectorstore.base import VectorStore
from app.vectorstore.factory import get_vectorstore

logger = logging.getLogger(__name__)


@dataclass
class ReviewResult:
    review_id: str
    markdown_report: str
    findings: list[ClauseExtraction]
    risk_summary: dict
    executive_summary: str


def _clean_summary_text(text: str) -> str:
    cleaned = re.sub(r"<think>.*?</think>", "", text or "", flags=re.DOTALL).strip()
    return cleaned


def _executive_summary(findings: list[ClauseExtraction], llm: LLMProvider) -> str:
    clauses = [f for f in findings if f.clause_type != "general"][:12]
    high_risks = [f for f in clauses if f.risk_level == "high"]
    med_risks = [f for f in clauses if f.risk_level == "medium"]
    obligations = [f for f in clauses if f.obligation]

    if clauses:
        bullet = "\n".join(
            f"- {f.clause_type} ({f.risk_level}): {f.text[:110]}" for f in clauses
        )
        try:
            raw = llm.chat(
                "You write concise executive summaries of legal document reviews. "
                "Ground every statement in the listed clauses. Educational, not advice.",
                [{"role": "user", "content": f"Summarize the key risks:\n{bullet}"}],
            )
            cleaned = _clean_summary_text(raw)
            if cleaned:
                return cleaned
        except Exception:
            logger.warning(
                "executive summary LLM failed; falling back to structured synthesis",
                exc_info=True,
            )

    summary_parts = [
        f"**Comprehensive Audit Assessment**: A total of {len(findings)} clause provisions were extracted and evaluated across this contract.",
    ]
    if high_risks:
        clause_names = ", ".join({f.clause_type.title() for f in high_risks})
        summary_parts.append(
            f"- **Critical Risk Exposures**: {len(high_risks)} high-risk provisions detected in {clause_names}. These clauses introduce unilateral liability, non-standard indemnification, or termination asymmetries requiring immediate legal review."
        )
    if med_risks:
        summary_parts.append(
            f"- **Operational & Governance Considerations**: {len(med_risks)} medium-risk terms identified concerning governing law, audit obligations, and dispute resolution mechanisms."
        )
    if obligations:
        summary_parts.append(
            f"- **Obligation Load**: {len(obligations)} mandatory compliance duties and covenants mapped for ongoing tracking."
        )
    if not clauses:
        summary_parts.append(
            "The review did not identify high-risk non-standard clauses. Standard terms observed; human legal review recommended prior to execution."
        )
    else:
        summary_parts.append(
            "*Recommendation*: Conduct targeted negotiation on flagged high-risk clauses prior to contract signature."
        )
    return "\n\n".join(summary_parts)


def run_review(
    document_id: str,
    *,
    organization_id: str,
    user_id: str,
    llm: LLMProvider | None = None,
    store: VectorStore | None = None,
    embedder=None,
    db: Session | None = None,
    template_id: str | None = None,
) -> ReviewResult:
    own_db = db is None
    db = db or SessionLocal()  # type: ignore[assignment]
    llm = llm or get_llm()
    store = store or get_vectorstore()
    embedder = embedder or get_embeddings()
    t0 = time.perf_counter()

    try:
        document = (
            db.query(LegalDocument)
            .filter(LegalDocument.id == document_id)
            .one_or_none()
        )
        if document is None or document.organization_id != organization_id:
            raise LookupError(f"document {document_id} not found in this organization")

        template = None
        if template_id:
            template = (
                db.query(ReviewTemplate)
                .filter(
                    ReviewTemplate.id == template_id,
                    ReviewTemplate.organization_id == organization_id,
                )
                .one_or_none()
            )
            if template is None:
                raise LookupError(f"review template {template_id} not found")

        doc_text = document.text or ""
        findings = review_document_text(doc_text, llm=llm)
        if template:
            focus_types = getattr(template, "focus_clause_types", None) or []
            if focus_types:
                focus = set(focus_types)
                findings = [f for f in findings if f.clause_type in focus]
        assign_default_risk(findings, doc_text)
        km_counts = attach_km_support(
            findings,
            organization_id=organization_id,
            store=store,
            embedder=embedder,
            jurisdiction=document.jurisdiction or "",
            domain=document.domain or "",
        )
        # Grounding: attach plain-language explanation when available and not user-generated
        for f in findings:
            if f.abstained:
                continue
            if not f.plain_language and f.explanation:
                try:
                    f.plain_language = explain_clause(f.explanation, llm=None)
                except Exception:
                    f.plain_language = ""

        risk = compute_risk_summary(findings)
        summary = _executive_summary(findings, llm)
        suggested_questions = _default_questions(findings)
        abstentions = [f.text for f in findings if f.abstained]
        manual_review = [
            f for f in findings if getattr(f, "support_status", "") == "manual_review"
        ]

        warning_bits = []
        if abstentions:
            warning_bits.append(
                "Findings marked as not grounded could not be verified against the document text."
            )
        if manual_review:
            warning_bits.append(
                f"{len(manual_review)} clause(s) were suggested by the model but lack "
                "supporting Knowledge Hub artefacts — reported as manual-review advisories, "
                "not confirmed risks."
            )

        report_md = build_review_markdown(
            document_title=document.title or "",
            executive_summary=summary,
            findings=findings,
            risk=risk,
            suggested_questions=suggested_questions,
            abstentions=abstentions,
            analysis_warning=" ".join(warning_bits),
        )

        review_id = uuid.uuid4().hex
        review = DocumentReview(
            id=review_id,
            organization_id=organization_id,
            document_id=document_id,
            reviewer_id=user_id,
            template_id=template.id if template else None,
            template_name=template.name if template else "",
            markdown_report=report_md,
            executive_summary=summary,
            risk_level="high"
            if risk.high_count
            else "medium"
            if risk.medium_count
            else "low",
            obligation_load=risk.obligation_count,
            balance_score=risk.balance_score,
            status="draft",
        )
        db.add(review)
        db.flush()
        for i, f in enumerate(findings):
            if f.clause_type == "general" and not f.text:
                continue
            db.add(
                ReviewFinding(
                    id=uuid.uuid4().hex,
                    review_id=review_id,
                    clause_type=f.clause_type,
                    risk_level=f.risk_level,
                    span_start=f.span.start if f.span else None,
                    span_end=f.span.end if f.span else None,
                    text=f.text[:4000],
                    explanation=f.explanation[:4000],
                    plain_language=f.plain_language[:4000],
                    obligation=f.obligation,
                    proposed_change=getattr(f, "proposed_change", "")[:4000],
                    change_rationale=getattr(f, "change_rationale", "")[:4000],
                    support_status=getattr(f, "support_status", "") or "",
                    suggested_risk_level=getattr(f, "suggested_risk_level", "") or "",
                    km_citations=list(getattr(f, "km_citations", None) or []),
                )
            )
        db.commit()
        incr("reviews.created")
        emit(
            db,
            "review.created",
            organization_id=organization_id,
            user_id=user_id,
            module="review",
            review_id=review_id,
            document_id=document_id,
            duration_ms=(time.perf_counter() - t0) * 1000,
            payload={
                "findings": len(findings),
                "risk_level": review.risk_level,
                "km_confirmed": km_counts.get("km_confirmed", 0),
                "manual_review": km_counts.get("manual_review", 0),
                "doc_ungrounded": km_counts.get("doc_ungrounded", 0),
            },
        )
        return ReviewResult(
            review_id=review_id,
            markdown_report=report_md,
            findings=findings,
            risk_summary={  # type: ignore[arg-type]
                "high": risk.high_count,
                "medium": risk.medium_count,
                "low": risk.low_count,
                "obligations": risk.obligation_count,
                "balance_score": risk.balance_score,
                "km_confirmed": km_counts.get("km_confirmed", 0),
                "manual_review": km_counts.get("manual_review", 0),
                "doc_ungrounded": km_counts.get("doc_ungrounded", 0),
            },
            executive_summary=summary,
        )
    finally:
        if own_db:
            db.close()


def _default_questions(findings: list[ClauseExtraction]) -> list[str]:
    questions = []
    for f in findings[:6]:
        if f.clause_type in ("termination", "penalties", "indemnity", "liability_cap"):
            questions.append(
                f"What are the financial and practical consequences of the {f.clause_type} clause: "
                f"“{f.text[:100]}”?"
            )
        elif f.clause_type == "dispute_resolution":
            questions.append(
                "Is the dispute-resolution clause (arbitration/jurisdiction) favorable, and is it enforceable?"
            )
        elif f.clause_type == "confidentiality":
            questions.append(
                "How long do my confidentiality obligations last, and what is covered?"
            )
    if not questions:
        questions = [
            "Which clause in this document is most burdensome for my side?",
            "What obligations have deadlines, and what happens if I miss them?",
        ]
    return questions
