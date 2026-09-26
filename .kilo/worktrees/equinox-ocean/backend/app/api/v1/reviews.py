"""Document review endpoints: run, list, report, publish, annotations, Q&A (PRD §5.2, §6.5)."""

from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.audit import audit
from app.core.deps import CurrentUser, require_module
from app.core.ratelimit import rate_limit
from app.db.session import SessionLocal, get_db
from app.models import (
    Annotation,
    DocumentReview,
    ReviewFinding,
    ReviewTemplate,
)
from app.queue import enqueue
from app.queue import get as get_job
from app.review.risk import risk_insight
from app.review.service import run_review
from app.services.document import get_document

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/reviews", tags=["reviews"])


def _risk_insight_for_finding(f: ReviewFinding) -> dict[str, str]:
    return risk_insight(
        clause_type=str(getattr(f, "clause_type", "general") or "general"),
        risk_level=str(getattr(f, "risk_level", "low") or "low"),
        obligation=bool(getattr(f, "obligation", False)),
        grounded=True,
    )


# --- Pydantic request schemas ------------------------------------------------


class ReviewRequest(BaseModel):
    document_id: str
    template_id: str | None = None


class TemplateCreate(BaseModel):
    name: str = Field(min_length=1)
    description: str = ""
    document_types: list[str] = Field(default_factory=list)
    focus_clause_types: list[str] = Field(default_factory=list)
    is_default: bool = False


class AnnotationCreate(BaseModel):
    body: str = Field(min_length=1)


class AnnotationResolve(BaseModel):
    resolution: str = "resolved"


class Question(BaseModel):
    question: str = Field(min_length=1)


class PublishBody(BaseModel):
    risk_level: str | None = None
    obligation_load: int | None = None
    balance_score: float | None = None


class ProposeChangeRequest(BaseModel):
    stance: str = "balanced"  # balanced | protective | aggressive


# --- Static routes (registered BEFORE /{review_id} to avoid shadowing) --------


@router.post("", status_code=202)
def create_review(
    body: ReviewRequest,
    user: CurrentUser = Depends(require_module("review", "review.run")),
    db: Session = Depends(get_db),
    _: None = Depends(rate_limit("reviews.create")),
) -> dict:
    try:
        get_document(
            document_id=body.document_id, organization_id=user.organization_id, db=db
        )
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    def _work(document_id: str, organization_id: str, user_id: str) -> dict:
        result = run_review(
            document_id,
            organization_id=organization_id,
            user_id=user_id,
            db=SessionLocal(),
            template_id=body.template_id,
        )
        return {
            "review_id": result.review_id,
            "risk_summary": result.risk_summary,
            "executive_summary": result.executive_summary,
            "findings": [
                {
                    "clause_type": f.clause_type,
                    "risk_level": f.risk_level,
                    "text": f.text[:400],
                    "explanation": (f.explanation or "")[:400],
                    "abstained": f.abstained,
                    "proposed_change": getattr(f, "proposed_change", "") or "",
                    "change_rationale": getattr(f, "change_rationale", "") or "",
                    **risk_insight(
                        clause_type=f.clause_type,
                        risk_level=f.risk_level,
                        obligation=f.obligation,
                        grounded=f.grounded,
                    ),
                }
                for f in result.findings
            ],
        }

    job_id = enqueue(_work, body.document_id, user.organization_id, user.id)
    audit(
        db,
        action="review_started",
        actor=user.id,
        organization_id=user.organization_id,
        resource_type="document",
        resource_id=body.document_id,
        detail={"job_id": job_id},
    )
    return {"job_id": job_id, "status": "queued"}


@router.get("/jobs/{job_id}")
def review_job(
    job_id: str, user: CurrentUser = Depends(require_module("review", "report.view"))
) -> dict:
    job = get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found or expired")
    d = job.to_dict()
    if isinstance(d.get("result"), dict) and "review_id" in d["result"]:
        d["review_id"] = d["result"]["review_id"]
    return d


@router.get("")
def list_reviews(
    user: CurrentUser = Depends(require_module("review", "report.view")),
    db: Session = Depends(get_db),
    limit: int = 50,
) -> dict:
    rows = (
        db.query(DocumentReview)
        .filter(DocumentReview.organization_id == user.organization_id)
        .order_by(DocumentReview.generated_at.desc())
        .limit(min(limit, 200))
        .all()
    )
    return {"reviews": [_review_dict(r) for r in rows]}


@router.get("/intelligence")
def review_intelligence(
    user: CurrentUser = Depends(require_module("review", "report.view")),
    db: Session = Depends(get_db),
) -> dict:
    """Aggregate cross-document intelligence across all audit reports for the organization."""
    from app.models import LegalDocument

    docs = (
        db.query(LegalDocument)
        .filter(LegalDocument.organization_id == user.organization_id)
        .all()
    )
    doc_map = {d.id: d for d in docs}
    total_docs = len(docs)

    reviews = (
        db.query(DocumentReview)
        .filter(DocumentReview.organization_id == user.organization_id)
        .order_by(DocumentReview.generated_at.desc())
        .all()
    )

    audited_doc_ids = {r.document_id for r in reviews}
    audited_docs_count = len(audited_doc_ids)
    coverage_pct = (
        round((audited_docs_count / total_docs * 100), 1) if total_docs > 0 else 0.0
    )

    # Risk level distribution
    risk_counts = {"high": 0, "medium": 0, "low": 0}
    total_obligations = 0
    balance_scores: list[float] = []

    for r in reviews:
        lvl = (r.risk_level or "low").lower()
        if lvl in risk_counts:
            risk_counts[lvl] += 1
        else:
            risk_counts["low"] += 1
        total_obligations += int(getattr(r, "obligation_load", 0) or 0)
        if r.balance_score is not None:
            balance_scores.append(float(getattr(r, "balance_score", 0.0) or 0.0))

    avg_balance = (
        round(sum(balance_scores) / len(balance_scores), 2) if balance_scores else 1.0
    )
    avg_obligations = round(total_obligations / len(reviews), 1) if reviews else 0.0

    # Cross-document findings aggregation
    review_ids = [r.id for r in reviews]
    findings = []
    if review_ids:
        findings = (
            db.query(ReviewFinding)
            .filter(ReviewFinding.review_id.in_(review_ids))
            .all()
        )

    rev_lookup = {r.id: r for r in reviews}
    clause_stats: dict[str, dict] = {}
    for f in findings:
        ctype = (f.clause_type or "general").strip().lower()
        if ctype not in clause_stats:
            clause_stats[ctype] = {
                "clause_type": ctype,
                "total": 0,
                "high_risk": 0,
                "medium_risk": 0,
                "low_risk": 0,
                "obligations": 0,
                "sample_explanation": "",
                "affected_contracts": [],
            }
        clause_stats[ctype]["total"] += 1
        rlvl = (f.risk_level or "low").lower()
        if rlvl == "high":
            clause_stats[ctype]["high_risk"] += 1
        elif rlvl == "medium":
            clause_stats[ctype]["medium_risk"] += 1
        else:
            clause_stats[ctype]["low_risk"] += 1

        if f.obligation:
            clause_stats[ctype]["obligations"] += 1
        if not clause_stats[ctype]["sample_explanation"] and f.explanation:
            clause_stats[ctype]["sample_explanation"] = f.explanation[:200]

        r_item = rev_lookup.get(f.review_id)
        if r_item:
            d_item = doc_map.get(r_item.document_id)
            d_name = (d_item.title or d_item.filename if d_item else None) or "Contract Precedent"
            existing = next((c for c in clause_stats[ctype]["affected_contracts"] if c["review_id"] == f.review_id), None)
            if not existing and len(clause_stats[ctype]["affected_contracts"]) < 12:
                clause_stats[ctype]["affected_contracts"].append({
                    "review_id": f.review_id,
                    "document_id": r_item.document_id,
                    "document_name": d_name,
                    "risk_level": f.risk_level,
                    "finding_id": f.id,
                    "explanation": f.explanation[:180] if f.explanation else "",
                    "clause_text": (f.text or "")[:140],
                    "template_name": r_item.template_name or "Contract Audit",
                })

    # Rank clause vulnerabilities
    top_vulnerabilities = sorted(
        clause_stats.values(),
        key=lambda x: (x["high_risk"], x["medium_risk"], x["total"]),
        reverse=True,
    )[:8]

    # High-risk watchlist
    watchlist = []
    for r in reviews:
        lvl = (r.risk_level or "low").lower()
        if (
            lvl == "high"
            or (r.obligation_load and r.obligation_load >= 8)
            or (r.balance_score and r.balance_score < 0.6)
        ):
            doc = doc_map.get(r.document_id)
            watchlist.append(
                {
                    "review_id": r.id,
                    "document_id": r.document_id,
                    "document_title": doc.title if doc else r.document_id,
                    "filename": (doc.metadata_json or {}).get(
                        "filename", getattr(doc, "title", "")
                    )
                    if doc
                    else "",
                    "risk_level": r.risk_level,
                    "obligation_load": r.obligation_load,
                    "balance_score": r.balance_score,
                    "generated_at": r.generated_at.isoformat()
                    if r.generated_at
                    else None,
                    "summary": (r.executive_summary or "")[:180],
                }
            )

    # Portfolio health assessment
    if risk_counts["high"] > 0:
        health_status = "Elevated Exposure"
    elif risk_counts["medium"] > risk_counts["low"]:
        health_status = "Moderate Risk"
    else:
        health_status = "Stable & Balanced"

    return {
        "total_documents": total_docs,
        "audited_documents": audited_docs_count,
        "unaudited_documents": max(0, total_docs - audited_docs_count),
        "total_reviews": len(reviews),
        "coverage_percentage": coverage_pct,
        "risk_distribution": risk_counts,
        "health_status": health_status,
        "total_obligations": total_obligations,
        "avg_obligations_per_doc": avg_obligations,
        "avg_balance_score": avg_balance,
        "top_vulnerabilities": top_vulnerabilities,
        "watchlist": watchlist[:10],
    }


# --- Templates (static, before /{review_id} to prevent path-param shadowing) --


@router.get("/templates")
def list_templates(
    user: CurrentUser = Depends(require_module("review", "report.view")),
    db: Session = Depends(get_db),
) -> dict:
    rows = (
        db.query(ReviewTemplate)
        .filter(ReviewTemplate.organization_id == user.organization_id)
        .order_by(ReviewTemplate.created_at)
        .all()
    )
    return {
        "templates": [
            {
                "id": t.id,
                "name": t.name,
                "description": t.description,
                "document_types": t.document_types or [],
                "focus_clause_types": t.focus_clause_types or [],
                "is_default": t.is_default,
            }
            for t in rows
        ]
    }


@router.post("/templates", status_code=201)
def create_template(
    body: TemplateCreate,
    user: CurrentUser = Depends(require_module("review", "review.run")),
    db: Session = Depends(get_db),
) -> dict:
    template_id = uuid.uuid4().hex
    template = ReviewTemplate(
        id=template_id,
        organization_id=user.organization_id,
        name=body.name,
        description=body.description,
        document_types=body.document_types,
        focus_clause_types=body.focus_clause_types,
        is_default=body.is_default,
        created_by=user.id,
    )
    db.add(template)
    db.commit()
    audit(
        db,
        action="review_template_created",
        actor=user.id,
        organization_id=user.organization_id,
        resource_type="review_template",
        resource_id=template_id,
    )
    return {"id": template_id, "name": template.name}


@router.delete("/templates/{template_id}")
def delete_template(
    template_id: str,
    user: CurrentUser = Depends(require_module("review", "review.run")),
    db: Session = Depends(get_db),
) -> dict:
    template = (
        db.query(ReviewTemplate)
        .filter(
            ReviewTemplate.id == template_id,
            ReviewTemplate.organization_id == user.organization_id,
        )
        .one_or_none()
    )
    if template is None:
        raise HTTPException(status_code=404, detail="template not found")
    db.delete(template)
    db.commit()
    audit(
        db,
        action="review_template_deleted",
        actor=user.id,
        organization_id=user.organization_id,
        resource_type="review_template",
        resource_id=template_id,
    )
    return {"ok": True}


# --- Annotations (PATCH/DELETE without /review_id prefix, before /{review_id}) --


@router.patch("/annotations/{annotation_id}")
def resolve_annotation(
    annotation_id: str,
    body: AnnotationResolve,
    user: CurrentUser = Depends(require_module("review", "report.view")),
    db: Session = Depends(get_db),
) -> dict:
    annotation = (
        db.query(Annotation)
        .filter(
            Annotation.id == annotation_id,
            Annotation.organization_id == user.organization_id,
        )
        .one_or_none()
    )
    if annotation is None:
        raise HTTPException(status_code=404, detail="annotation not found")
    annotation.resolution = body.resolution
    db.commit()
    return _annotation_dict(annotation)


@router.delete("/annotations/{annotation_id}")
def delete_annotation(
    annotation_id: str,
    user: CurrentUser = Depends(require_module("review", "report.view")),
    db: Session = Depends(get_db),
) -> dict:
    annotation = (
        db.query(Annotation)
        .filter(
            Annotation.id == annotation_id,
            Annotation.organization_id == user.organization_id,
            Annotation.author_id == user.id,
        )
        .one_or_none()
    )
    if annotation is None:
        raise HTTPException(status_code=404, detail="annotation not found")
    db.delete(annotation)
    db.commit()
    return {"ok": True}


# --- Path-parameter routes (/{review_id}) ---------------------------------------


@router.get("/{review_id}")
def get_review(
    review_id: str,
    user: CurrentUser = Depends(require_module("review", "report.view")),
    db: Session = Depends(get_db),
) -> dict:
    review = (
        db.query(DocumentReview).filter(DocumentReview.id == review_id).one_or_none()
    )
    if review is None or review.organization_id != user.organization_id:
        raise HTTPException(status_code=404, detail="review not found")
    data = _review_dict(review)
    findings = (
        db.query(ReviewFinding)
        .filter(ReviewFinding.review_id == review_id)
        .order_by(ReviewFinding.span_start)
        .all()
    )
    data["findings"] = [
        {
            "id": f.id,
            "clause_type": f.clause_type,
            "risk_level": f.risk_level,
            "span_start": f.span_start,
            "span_end": f.span_end,
            "text": f.text,
            "explanation": f.explanation,
            "plain_language": f.plain_language,
            "obligation": f.obligation,
            "proposed_change": getattr(f, "proposed_change", "") or "",
            "change_rationale": getattr(f, "change_rationale", "") or "",
            **_risk_insight_for_finding(f),
        }
        for f in findings
    ]
    return data


@router.delete("/{review_id}", status_code=204)
def delete_review(
    review_id: str,
    user: CurrentUser = Depends(require_module("review", "report.view")),
    db: Session = Depends(get_db),
) -> None:
    review = (
        db.query(DocumentReview).filter(DocumentReview.id == review_id).one_or_none()
    )
    if review is None or review.organization_id != user.organization_id:
        raise HTTPException(status_code=404, detail="review not found")
    db.query(ReviewFinding).filter(ReviewFinding.review_id == review_id).delete()
    db.query(Annotation).filter(Annotation.target_id == review_id).delete()
    db.delete(review)
    db.commit()


@router.post("/{review_id}/publish")
def publish_review(
    review_id: str,
    body: PublishBody,
    user: CurrentUser = Depends(require_module("review", "review.publish")),
    db: Session = Depends(get_db),
    _: None = Depends(rate_limit("reviews.publish")),
) -> dict:
    review = (
        db.query(DocumentReview).filter(DocumentReview.id == review_id).one_or_none()
    )
    if review is None or review.organization_id != user.organization_id:
        raise HTTPException(status_code=404, detail="review not found")
    if review.status == "published":
        raise HTTPException(
            status_code=409, detail="review already published, create a new revision"
        )
    review.status = "published"
    if body.risk_level:
        review.risk_level = body.risk_level
    if body.obligation_load is not None:
        review.obligation_load = body.obligation_load
    if body.balance_score is not None:
        review.balance_score = body.balance_score
    db.commit()
    audit(
        db,
        action="review_published",
        actor=user.id,
        organization_id=user.organization_id,
        resource_type="review",
        resource_id=review_id,
    )
    return _review_dict(review)


@router.get("/{review_id}/report")
def get_report(
    review_id: str,
    user: CurrentUser = Depends(require_module("review", "report.view")),
    db: Session = Depends(get_db),
) -> dict:
    review = (
        db.query(DocumentReview).filter(DocumentReview.id == review_id).one_or_none()
    )
    if review is None or review.organization_id != user.organization_id:
        raise HTTPException(status_code=404, detail="review not found")
    return {"review_id": review.id, "markdown_report": review.markdown_report}


@router.post("/{review_id}/qna")
def qna(
    review_id: str,
    body: Question,
    user: CurrentUser = Depends(require_module("review", "report.view")),
    db: Session = Depends(get_db),
    _: None = Depends(rate_limit("reviews.qna")),
) -> dict:
    review = (
        db.query(DocumentReview).filter(DocumentReview.id == review_id).one_or_none()
    )
    if review is None or review.organization_id != user.organization_id:
        raise HTTPException(status_code=404, detail="review not found")
    try:
        from app.core.constants import DOCS_COLLECTION
        from app.llm.factory import get_llm
        from app.models import LegalDocument
        from app.review.plain_language import answer_grounded
        from app.vectorstore.factory import get_vectorstore

        doc = (
            db.query(LegalDocument)
            .filter(LegalDocument.id == review.document_id)
            .one_or_none()
        )
        if doc is None or doc.organization_id != user.organization_id:
            raise HTTPException(status_code=404, detail="document not found")
        result = answer_grounded(
            body.question,
            doc.text or "",
            get_vectorstore(),
            DOCS_COLLECTION,
            get_llm(),
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"grounded Q&A unavailable: {exc}")
    return {"answer": result["answer"], "citations": result["citations"]}


# --- Per-review annotations (/{review_id}/annotations) -------------------------


@router.get("/{review_id}/annotations")
def list_review_annotations(
    review_id: str,
    user: CurrentUser = Depends(require_module("review", "report.view")),
    db: Session = Depends(get_db),
) -> dict:
    review = (
        db.query(DocumentReview).filter(DocumentReview.id == review_id).one_or_none()
    )
    if review is None or review.organization_id != user.organization_id:
        raise HTTPException(status_code=404, detail="review not found")
    rows = (
        db.query(Annotation)
        .filter(
            Annotation.organization_id == user.organization_id,
            Annotation.target_type == "review_report",
            Annotation.target_id == review_id,
        )
        .order_by(Annotation.created_at.desc())
        .all()
    )
    return {"annotations": [_annotation_dict(a) for a in rows]}


@router.post("/{review_id}/annotations", status_code=201)
def add_review_annotation(
    review_id: str,
    body: AnnotationCreate,
    user: CurrentUser = Depends(require_module("review", "report.view")),
    db: Session = Depends(get_db),
) -> dict:
    review = (
        db.query(DocumentReview).filter(DocumentReview.id == review_id).one_or_none()
    )
    if review is None or review.organization_id != user.organization_id:
        raise HTTPException(status_code=404, detail="review not found")
    annotation = Annotation(
        id=uuid.uuid4().hex,
        organization_id=user.organization_id,
        author_id=user.id,
        target_type="review_report",
        target_id=review_id,
        body=body.body,
        resolution="open",
    )
    db.add(annotation)
    db.commit()
    return _annotation_dict(annotation)


@router.post("/{review_id}/findings/{finding_id}/propose-change")
def propose_change_for_finding(
    review_id: str,
    finding_id: str,
    body: ProposeChangeRequest = ProposeChangeRequest(),
    user: CurrentUser = Depends(require_module("review", "report.view")),
    db: Session = Depends(get_db),
) -> dict:
    """Generate or customize proposed contractual amendments for a specific finding."""
    from app.llm.factory import get_llm
    from app.review.remediation import propose_clause_remediation

    review = (
        db.query(DocumentReview).filter(DocumentReview.id == review_id).one_or_none()
    )
    if review is None or review.organization_id != user.organization_id:
        raise HTTPException(status_code=404, detail="review not found")

    finding = (
        db.query(ReviewFinding)
        .filter(ReviewFinding.id == finding_id, ReviewFinding.review_id == review_id)
        .one_or_none()
    )
    if finding is None:
        raise HTTPException(status_code=404, detail="finding not found")

    llm = None
    try:
        llm = get_llm()
    except Exception:
        logger.debug(
            "LLM not available for propose_change; using fallback", exc_info=True
        )

    proposed_change, rationale = propose_clause_remediation(
        clause_type=finding.clause_type,
        risk_level=finding.risk_level,
        text=finding.text,
        document_context=review.executive_summary or "",
        llm=llm,
        stance=body.stance,
    )
    finding.proposed_change = proposed_change
    finding.change_rationale = rationale
    db.commit()

    return {
        "finding_id": finding.id,
        "clause_type": finding.clause_type,
        "risk_level": finding.risk_level,
        "proposed_change": proposed_change,
        "change_rationale": rationale,
        "stance": body.stance,
    }


# --- Serialisation helpers ---------------------------------------------------


def _review_dict(r: DocumentReview) -> dict:
    findings_list = getattr(r, "findings", None) or []
    top_findings = [
        {
            "id": f.id,
            "clause_type": (f.clause_type or "general").strip(),
            "risk_level": f.risk_level or "low",
            "obligation": bool(f.obligation),
            "explanation": (f.explanation or "")[:140],
        }
        for f in findings_list[:5]
    ]
    return {
        "id": r.id,
        "document_id": r.document_id,
        "status": r.status,
        "risk_level": r.risk_level,
        "obligation_load": r.obligation_load,
        "balance_score": r.balance_score,
        "executive_summary": r.executive_summary,
        "markdown_report": r.markdown_report,
        "template_id": r.template_id,
        "template_name": r.template_name,
        "findings_count": len(findings_list),
        "top_findings": top_findings,
        "generated_at": r.generated_at.isoformat() if r.generated_at else None,
    }


def _annotation_dict(a: Annotation) -> dict:
    return {
        "id": a.id,
        "author_id": a.author_id,
        "body": a.body,
        "resolution": a.resolution,
        "created_at": a.created_at.isoformat() if a.created_at else None,
    }
