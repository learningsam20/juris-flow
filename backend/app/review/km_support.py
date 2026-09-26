"""KM-artefact support checks for review findings.

A finding is only treated as a confirmed risk when Knowledge Hub artefacts
(statutes, precedents, policies) support it. LLM/pattern flags without KM hits
are reclassified as ``manual_review`` advisories and reported separately.
"""

from __future__ import annotations

import logging
from typing import Any

from app.core.constants import DOCS_COLLECTION
from app.embeddings.base import EmbeddingProvider
from app.review.extractor import ClauseExtraction
from app.vectorstore.base import SearchHit, VectorStore

logger = logging.getLogger(__name__)

SUPPORT_KM_CONFIRMED = "km_confirmed"
SUPPORT_MANUAL_REVIEW = "manual_review"
SUPPORT_DOC_UNGROUNDED = "doc_ungrounded"

# Cosine / similarity floor for treating a KM hit as supportive evidence.
DEFAULT_KM_SCORE_THRESHOLD = 0.42
DEFAULT_TOP_K = 4


def _is_knowledge_artefact(meta: dict[str, Any] | None) -> bool:
    meta = meta or {}
    cat = (meta.get("doc_category") or meta.get("document_category") or "").lower()
    dtype = (meta.get("doc_type") or "").lower()
    if cat == "contract_review" or dtype in (
        "contract",
        "agreement",
        "nda",
        "lease",
        "contract_review",
    ):
        return False
    return True


def retrieve_km_hits(
    *,
    query: str,
    organization_id: str,
    store: VectorStore,
    embedder: EmbeddingProvider,
    jurisdiction: str = "",
    domain: str = "",
    top_k: int = DEFAULT_TOP_K,
) -> list[SearchHit]:
    """Semantic search restricted to knowledge artefacts (not contracts under review)."""
    if not query.strip() or not organization_id:
        return []
    try:
        vector = embedder.embed_one(query.strip()[:1200])
    except Exception:
        logger.warning("KM embed failed for review support check", exc_info=True)
        return []

    filters: dict[str, Any] = {"organization_id": organization_id}
    if jurisdiction:
        filters["jurisdiction"] = jurisdiction
    if domain:
        filters["domain"] = domain

    try:
        raw = store.search(DOCS_COLLECTION, vector, filters=filters, top_k=top_k * 3)
    except Exception:
        logger.warning("KM search failed for review support check", exc_info=True)
        return []

    artefacts = [h for h in raw if _is_knowledge_artefact(h.metadata)]
    if artefacts:
        return artefacts[:top_k]
    # Soft fallback: still exclude explicit contract_review category.
    return [
        h
        for h in raw
        if (h.metadata or {}).get("doc_category") != "contract_review"
    ][:top_k]


def _citation(hit: SearchHit) -> dict[str, Any]:
    meta = hit.metadata or {}
    return {
        "document_id": meta.get("document_id") or hit.document_id,
        "score": round(float(hit.score), 4),
        "text": (hit.text or "")[:280],
        "jurisdiction": meta.get("jurisdiction") or "",
        "doc_type": meta.get("doc_type") or "",
        "title": meta.get("title") or meta.get("filename") or "",
    }


def attach_km_support(
    findings: list[ClauseExtraction],
    *,
    organization_id: str,
    store: VectorStore,
    embedder: EmbeddingProvider,
    jurisdiction: str = "",
    domain: str = "",
    score_threshold: float = DEFAULT_KM_SCORE_THRESHOLD,
) -> dict[str, int]:
    """Classify each finding against KM artefacts.

    Returns counts: ``km_confirmed``, ``manual_review``, ``doc_ungrounded``.
    """
    counts = {
        SUPPORT_KM_CONFIRMED: 0,
        SUPPORT_MANUAL_REVIEW: 0,
        SUPPORT_DOC_UNGROUNDED: 0,
    }

    for f in findings:
        if f.abstained or not f.grounded:
            f.support_status = SUPPORT_DOC_UNGROUNDED
            f.suggested_risk_level = f.risk_level or "low"
            f.km_citations = []
            counts[SUPPORT_DOC_UNGROUNDED] += 1
            continue

        # Low / informational clauses don't need KM confirmation to stay low.
        if (f.risk_level or "low") == "low" and not f.obligation:
            f.support_status = SUPPORT_KM_CONFIRMED
            f.suggested_risk_level = f.risk_level or "low"
            f.km_citations = []
            counts[SUPPORT_KM_CONFIRMED] += 1
            continue

        query = (
            f"{(f.clause_type or 'clause').replace('_', ' ')} risk: "
            f"{(f.text or '')[:400]} "
            f"{(f.explanation or '')[:200]}"
        ).strip()
        hits = retrieve_km_hits(
            query=query,
            organization_id=organization_id,
            store=store,
            embedder=embedder,
            jurisdiction=jurisdiction,
            domain=domain,
        )
        supportive = [h for h in hits if float(h.score) >= score_threshold]
        f.suggested_risk_level = f.risk_level or "low"

        if supportive:
            f.support_status = SUPPORT_KM_CONFIRMED
            f.km_citations = [_citation(h) for h in supportive[:3]]
            counts[SUPPORT_KM_CONFIRMED] += 1
        else:
            # LLM/pattern wanted a flag, but no KM artefact backs it.
            f.support_status = SUPPORT_MANUAL_REVIEW
            f.km_citations = [_citation(h) for h in hits[:2]]  # weak/near misses for transparency
            # Do not treat as confirmed risk in rollups.
            f.risk_level = "low"
            f.explanation = (
                (f.explanation or "").rstrip()
                + (
                    "\n\n[Manual review advised] The model flagged this clause, but no "
                    "matching Knowledge Hub artefact (statute, precedent, or policy) "
                    "was found to substantiate the risk. Treat as an advisory only."
                )
            ).strip()
            counts[SUPPORT_MANUAL_REVIEW] += 1

    return counts
