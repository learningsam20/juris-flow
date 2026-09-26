"""KM artefact support checks for review findings."""

from __future__ import annotations

from app.review.extractor import ClauseExtraction
from app.review.km_support import (
    SUPPORT_KM_CONFIRMED,
    SUPPORT_MANUAL_REVIEW,
    attach_km_support,
)
from app.review.risk import compute_risk_summary
from app.vectorstore.base import SearchHit


class _Store:
    def __init__(self, hits: list[SearchHit]) -> None:
        self._hits = hits

    def search(self, *args, **kwargs):
        return list(self._hits)


class _Emb:
    def embed_one(self, text: str):
        return [0.1] * 8


def test_no_km_hits_become_manual_review_not_confirmed_risk():
    findings = [
        ClauseExtraction(
            clause_type="indemnity",
            risk_level="high",
            text="Seller shall indemnify Buyer for all losses without cap.",
            grounded=True,
            obligation=True,
        )
    ]
    counts = attach_km_support(
        findings, organization_id="org", store=_Store([]), embedder=_Emb()
    )
    assert counts[SUPPORT_MANUAL_REVIEW] == 1
    assert findings[0].support_status == SUPPORT_MANUAL_REVIEW
    assert findings[0].suggested_risk_level == "high"
    assert findings[0].risk_level == "low"
    summary = compute_risk_summary(findings)
    assert summary.high_count == 0
    assert summary.medium_count == 0


def test_km_hit_confirms_risk():
    hit = SearchHit(
        id="1",
        score=0.9,
        text="Uncapped indemnity is generally considered high risk in commercial contracts.",
        metadata={
            "doc_category": "knowledge_artefact",
            "document_id": "statute-1",
            "doc_type": "statute",
        },
    )
    findings = [
        ClauseExtraction(
            clause_type="indemnity",
            risk_level="high",
            text="Seller shall indemnify Buyer for all losses without cap.",
            grounded=True,
            obligation=True,
        )
    ]
    counts = attach_km_support(
        findings, organization_id="org", store=_Store([hit]), embedder=_Emb()
    )
    assert counts[SUPPORT_KM_CONFIRMED] == 1
    assert findings[0].support_status == SUPPORT_KM_CONFIRMED
    assert findings[0].risk_level == "high"
    assert findings[0].km_citations
    summary = compute_risk_summary(findings)
    assert summary.high_count == 1
