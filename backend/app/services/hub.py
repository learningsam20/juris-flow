"""Knowledge Hub service: hybrid search, detail views, collections, insights (PRD §5.3, §6.7)."""

from __future__ import annotations

import logging
import time
import uuid
from typing import Any

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.analytics.events import emit
from app.config import get_settings
from app.core.constants import DOCS_COLLECTION
from app.core.errors import NotFoundError, ValidationError
from app.embeddings.factory import get_embeddings
from app.llm.factory import get_llm
from app.models import (
    CollectionItem,
    DocumentReview,
    KnowledgeCollection,
    LegalDocument,
    Scenario,
    ScenarioVersion,
    Simulation,
)
from app.services.document import document_to_dict
from app.vectorstore.factory import get_vectorstore

logger = logging.getLogger(__name__)


def search_documents(
    *,
    query: str,
    organization_id: str,
    db: Session,
    jurisdiction: str = "",
    domain: str = "",
    doc_type: str = "",
    source_status: str = "",
    limit: int = 20,
    user_id: str = "",
) -> dict:
    t0 = time.perf_counter()
    query = (query or "").strip()
    query_lower = query.lower()

    doc_ids: set[str] = set()
    score_map: dict[str, float] = {}
    snippet_map: dict[str, str] = {}
    if query:
        # semantic
        store = get_vectorstore()
        emb = get_embeddings()
        filters: dict[str, Any] = {"organization_id": organization_id}
        if jurisdiction:
            filters["jurisdiction"] = jurisdiction
        if domain:
            filters["domain"] = domain
        try:
            hits = store.search(
                DOCS_COLLECTION,
                emb.embed_one(query),
                filters=filters,
                top_k=max(limit, 20),
            )
            for h in hits:
                did = h.metadata.get("document_id")
                if did:
                    doc_ids.add(did)
                    if did not in score_map or h.score > score_map[did]:
                        score_map[did] = h.score
                    if h.text and (
                        did not in snippet_map or h.score >= score_map.get(did, 0.0)
                    ):
                        snippet_map[did] = h.text
        except Exception:
            logger.exception("semantic search failed; keyword results only")

        # keyword
        like = f"%{query_lower}%"
        keyword_rows = (
            db.query(LegalDocument)
            .filter(LegalDocument.organization_id == organization_id)
            .filter(
                or_(
                    LegalDocument.title.ilike(like),
                    LegalDocument.text.ilike(like),
                    LegalDocument.domain.ilike(like),
                )
            )
            .limit(50)
            .all()
        )
        for doc in keyword_rows:
            doc_ids.add(doc.id)
            score_map.setdefault(doc.id, 0.5)
            if doc.id not in snippet_map and doc.text:
                lower_text = doc.text.lower()
                pos = lower_text.find(query_lower)
                if pos != -1:
                    start = max(0, pos - 60)
                    end = min(len(doc.text), pos + len(query_lower) + 140)
                    prefix = "..." if start > 0 else ""
                    suffix = "..." if end < len(doc.text) else ""
                    snippet_map[doc.id] = (
                        f"{prefix}{doc.text[start:end].strip()}{suffix}"
                    )

    base = db.query(LegalDocument).filter(
        LegalDocument.organization_id == organization_id
    )
    if jurisdiction:
        base = base.filter(LegalDocument.jurisdiction == jurisdiction)
    if domain:
        base = base.filter(LegalDocument.domain == domain)
    if doc_type:
        base = base.filter(LegalDocument.doc_type == doc_type)
    if source_status:
        base = base.filter(LegalDocument.source_status == source_status)

    if doc_ids:
        base = base.filter(LegalDocument.id.in_(doc_ids))
    rows = base.order_by(LegalDocument.created_at.desc()).limit(limit).all()
    results = []
    for row in rows:
        data = document_to_dict(row)
        data["score"] = round(score_map.get(row.id, 0.0), 4)
        snippet = snippet_map.get(row.id)
        if not snippet and row.text:
            cleaned = row.text.strip()
            snippet = cleaned[:240] + ("..." if len(cleaned) > 240 else "")
        data["text"] = snippet or ""
        data["snippet"] = snippet or ""
        results.append(data)
    results.sort(key=lambda r: r["score"], reverse=True)
    emit(
        db,
        "knowledge.search",
        organization_id=organization_id,
        user_id=user_id,
        module="hub",
        payload={
            "query": query[:200],
            "jurisdiction": jurisdiction,
            "domain": domain,
            "duration_ms": round((time.perf_counter() - t0) * 1000, 2),
            "hits": len(results),
        },
    )
    return {
        "results": results,
        "query": query,
        "filters": {
            "jurisdiction": jurisdiction,
            "domain": domain,
            "doc_type": doc_type,
            "source_status": source_status,
        },
    }


def ask_question(
    *,
    query: str,
    organization_id: str,
    db: Session,
    jurisdiction: str = "",
    domain: str = "",
    doc_type: str = "",
    source_status: str = "",
    user_id: str = "",
    top_k: int = 8,
) -> dict:
    """Ask AI: retrieve the most relevant passages, then answer via the LLM.

    Hybrid retrieval (semantic vectors with keyword fallback) is grounded by
    construction: the LLM has no sources beyond the retrieved excerpts and is
    told to cite them inline as [n] and abstain when the answer is absent.
    """
    t0 = time.perf_counter()
    query = (query or "").strip()
    if not query:
        raise ValidationError("question is required")

    store = get_vectorstore()
    emb = get_embeddings()
    filters: dict[str, Any] = {"organization_id": organization_id}
    if jurisdiction:
        filters["jurisdiction"] = jurisdiction
    if domain:
        filters["domain"] = domain

    passages: list[dict[str, Any]] = []
    try:
        hits = store.search(
            DOCS_COLLECTION,
            emb.embed_one(query),
            filters=filters,
            top_k=max(top_k, 10),
        )
        for h in hits:
            did = h.metadata.get("document_id")
            if not did:
                continue
            passages.append(
                {
                    "document_id": did,
                    "text": h.text or "",
                    "score": float(h.score or 0.0),
                }
            )
    except Exception:
        logger.exception("semantic retrieval failed for ask; keyword fallback")

    if not passages:
        # keyword fallback: surface the best matching passages from stored text
        query_lower = query.lower()
        like = f"%{query_lower}%"
        rows = (
            db.query(LegalDocument)
            .filter(LegalDocument.organization_id == organization_id)
            .filter(
                or_(
                    LegalDocument.text.ilike(like),
                    LegalDocument.title.ilike(like),
                )
            )
            .limit(10)
            .all()
        )
        for doc in rows:
            text = doc.text or ""
            pos = text.lower().find(query_lower)
            if pos != -1:
                start = max(0, pos - 200)
                end = min(len(text), pos + len(query_lower) + 400)
                passages.append(
                    {"document_id": doc.id, "text": text[start:end], "score": 0.5}
                )
            elif text:
                passages.append(
                    {"document_id": doc.id, "text": text[:800], "score": 0.4}
                )

    doc_counts: dict[str, int] = {}
    seen_texts: set[str] = set()
    ordered: list[dict[str, Any]] = []
    for p in passages:
        did = p["document_id"]
        txt = (p.get("text") or "").strip()
        if not txt or txt in seen_texts:
            continue
        # Allow up to 3 high-scoring passages per document so multi-section answers are covered
        if doc_counts.get(did, 0) >= 3:
            continue
        seen_texts.add(txt)
        doc_counts[did] = doc_counts.get(did, 0) + 1
        ordered.append(p)
    passages = ordered[:top_k]
    retrieval_ms = (time.perf_counter() - t0) * 1000

    titles: dict[str, str] = {}
    filenames: dict[str, str] = {}
    if passages:
        ids = [p["document_id"] for p in passages]
        for d in (
            db.query(LegalDocument)
            .filter(
                LegalDocument.id.in_(ids),
                LegalDocument.organization_id == organization_id,
            )
            .all()
        ):
            titles[d.id] = d.title or (d.metadata_json or {}).get("filename") or d.id
            filenames[d.id] = (d.metadata_json or {}).get("filename") or ""

    context_parts: list[str] = []
    sources: list[dict[str, Any]] = []
    for i, p in enumerate(passages, start=1):
        title = titles.get(p["document_id"], p["document_id"])
        context_parts.append(f'[{i}] (from "{title}")\n{p["text"]}')
        sources.append(
            {
                "index": i,
                "document_id": p["document_id"],
                "title": title,
                "filename": filenames.get(p["document_id"], ""),
                "snippet": p["text"],
                "score": round(p["score"], 4),
            }
        )

    context = "\n\n---\n\n".join(context_parts)
    if not context:
        emit(
            db,
            "knowledge.ask",
            organization_id=organization_id,
            user_id=user_id,
            module="hub",
            payload={
                "query": query[:200],
                "jurisdiction": jurisdiction,
                "domain": domain,
                "duration_ms": round((time.perf_counter() - t0) * 1000, 2),
                "retrieval_ms": round(retrieval_ms, 2),
                "llm_ms": 0.0,
                "used": 0,
            },
        )
        return {
            "query": query,
            "answer": (
                "I could not find anything relevant in your knowledge library yet. "
                "Upload documents first, then ask again."
            ),
            "sources": [],
            "used": 0,
            "filters": {
                "jurisdiction": jurisdiction,
                "domain": domain,
                "doc_type": doc_type,
                "source_status": source_status,
            },
        }

    system = (
        "You are an expert retrieval-grounded legal research assistant.\n"
        "GUIDELINES:\n"
        "1. Base your answer directly on the numbered document excerpts provided below. They are marked [1], [2], ... with their source title.\n"
        "2. Do NOT invent legal statutes, sections, or provisions that are absent from the excerpts.\n"
        "3. When the excerpts answer the question (fully or partially), provide a clear, structured, and factual legal explanation, citing the supporting excerpts inline with their citation numbers like [1], [2].\n"
        "4. When the excerpts DO NOT contain the specific statute or subject asked about (for example, if asked about an Act or topic not present in the excerpts), clearly explain that the requested statute or document is not present in the uploaded library. Then, if the retrieved excerpts contain related provisions, summarize what is found and cite it inline as [n], or advise what documents are available.\n"
        "5. Output is educational and informational legal analysis, not legal advice."
    )
    user = f"Question: {query}\n\nRelevant document excerpts:\n{context}"
    settings = get_settings()
    llm_t0 = time.perf_counter()
    try:
        llm = get_llm(
            model=settings.ask_llm_model,
            temperature=settings.ask_llm_temperature,
        )
        answer = llm.chat(
            system,
            [{"role": "user", "content": user}],
            max_tokens=settings.ask_llm_max_tokens,
        )
    except Exception:
        logger.exception("LLM answer generation failed")
        answer = (
            "I retrieved the passages below but could not generate an answer right now "
            "(the language model endpoint is unavailable). Review the cited sections directly."
        )
    llm_ms = (time.perf_counter() - llm_t0) * 1000

    emit(
        db,
        "knowledge.ask",
        organization_id=organization_id,
        user_id=user_id,
        module="hub",
        payload={
            "query": query[:200],
            "jurisdiction": jurisdiction,
            "domain": domain,
            "duration_ms": round((time.perf_counter() - t0) * 1000, 2),
            "retrieval_ms": round(retrieval_ms, 2),
            "llm_ms": round(llm_ms, 2),
            "used": len(sources),
        },
    )
    return {
        "query": query,
        "answer": answer,
        "sources": sources,
        "used": len(sources),
        "filters": {
            "jurisdiction": jurisdiction,
            "domain": domain,
            "doc_type": doc_type,
            "source_status": source_status,
        },
    }


def document_detail(*, document_id: str, organization_id: str, db: Session) -> dict:
    doc = db.query(LegalDocument).filter(LegalDocument.id == document_id).one_or_none()
    if doc is None or doc.organization_id != organization_id:
        raise NotFoundError("document not found")

    # linked scenarios (any version references this document)
    versions = [
        v
        for v in db.query(ScenarioVersion).all()
        if document_id in (v.document_ids or [])
    ]
    version_ids = [v.id for v in versions]
    scenarios = []
    for v in versions:
        scenario = db.query(Scenario).filter(Scenario.id == v.scenario_id).one_or_none()
        if scenario and scenario.organization_id == organization_id:
            scenarios.append(
                {
                    "scenario_id": scenario.id,
                    "scenario_title": scenario.title,
                    "version_id": v.id,
                    "version": v.version,
                }
            )

    simulations = (
        db.query(Simulation)
        .filter(Simulation.organization_id == organization_id)
        .filter(Simulation.scenario_version_id.in_(version_ids))
        .all()
        if version_ids
        else []
    )
    review = (
        db.query(DocumentReview)
        .filter(DocumentReview.document_id == document_id)
        .first()
    )

    data = document_to_dict(doc)
    data["text"] = doc.text[:20000]
    data["metadata_visibility"] = {
        "filename": (doc.metadata_json or {}).get("filename", ""),
        "prompt_injection_detected": (doc.metadata_json or {}).get(
            "prompt_injection_detected", False
        ),
    }
    data["linked"] = {
        "scenarios": scenarios,
        "simulations": [
            {"id": s.id, "status": s.status, "phase": s.phase} for s in simulations
        ],
        "reviews": [{"id": review.id, "status": review.status}] if review else [],
    }
    return data


def create_collection(
    *, name: str, description: str, organization_id: str, owner_id: str, db: Session
) -> dict:
    if not name.strip():
        from app.core.errors import ValidationError

        raise ValidationError("collection name is required")
    coll = KnowledgeCollection(
        id=uuid.uuid4().hex,
        organization_id=organization_id,
        name=name.strip(),
        description=description,
        owner_id=owner_id,
    )
    db.add(coll)
    db.commit()
    return collection_to_dict(coll)


def add_to_collection(
    *,
    collection_id: str,
    organization_id: str,
    item_type: str,
    item_id: str,
    note: str = "",
    db: Session,
) -> dict:
    coll = (
        db.query(KnowledgeCollection)
        .filter(KnowledgeCollection.id == collection_id)
        .one_or_none()
    )
    if coll is None or coll.organization_id != organization_id:
        raise NotFoundError("collection not found")
    db.add(
        CollectionItem(
            id=uuid.uuid4().hex,
            collection_id=collection_id,
            item_type=item_type,
            item_id=item_id,
            note=note,
        )
    )
    db.commit()
    return collection_to_dict(coll)


def list_collections(*, organization_id: str, db: Session) -> list[dict]:
    colls = (
        db.query(KnowledgeCollection)
        .filter(KnowledgeCollection.organization_id == organization_id)
        .all()
    )
    return [collection_to_dict(c) for c in colls]


def collection_to_dict(coll: KnowledgeCollection) -> dict:
    return {
        "id": coll.id,
        "name": coll.name,
        "description": coll.description,
        "owner_id": coll.owner_id,
        "items": [
            {"id": i.id, "item_type": i.item_type, "item_id": i.item_id, "note": i.note}
            for i in coll.items
        ],
        "created_at": coll.created_at.isoformat() if coll.created_at else None,
    }


def teaching_pack(*, topic: str, organization_id: str, db: Session) -> dict:
    """Auto-assemble a teaching pack from related documents, scenarios and reviews."""
    results = search_documents(
        query=topic, organization_id=organization_id, db=db, limit=8
    )
    related_scenarios = (
        db.query(Scenario)
        .filter(Scenario.organization_id == organization_id)
        .filter(
            or_(
                Scenario.title.ilike(f"%{topic}%"),
                Scenario.domain.ilike(f"%{topic}%"),
                Scenario.jurisdiction.ilike(f"%{topic}%"),
            )
        )
        .limit(5)
        .all()
    )
    doc_ids = [r["id"] for r in results["results"]]
    reviews = (
        db.query(DocumentReview)
        .filter(
            DocumentReview.organization_id == organization_id,
            DocumentReview.document_id.in_(doc_ids)
            if doc_ids
            else DocumentReview.document_id == "",
        )
        .limit(5)
        .all()
    )
    return {
        "topic": topic,
        "documents": results["results"],
        "scenarios": [
            {"id": s.id, "title": s.title, "jurisdiction": s.jurisdiction}
            for s in related_scenarios
        ],
        "reviews": [
            {"id": r.id, "document_id": r.document_id, "status": r.status}
            for r in reviews
        ],
        "note": "Teaching pack assembled from approved materials; verify jurisdiction and currency before use.",
    }


def insights(*, organization_id: str, db: Session) -> dict:
    """AI-augmented insights baseline: cluster summaries and gap signals (PRD §6.8).

    Practice Intelligence coverage is scoped to Knowledge Artefacts only
    (statutes, regulations, policies, precedents) — not commercial contracts
    under review.
    """
    docs = (
        db.query(LegalDocument)
        .filter(LegalDocument.organization_id == organization_id)
        .all()
    )
    artefacts = [d for d in docs if d.document_category == "knowledge_artefact"]
    contracts = [d for d in docs if d.document_category == "contract_review"]

    by_jurisdiction: dict[str, int] = {}
    by_domain: dict[str, int] = {}
    by_type: dict[str, int] = {}
    for d in artefacts:
        by_jurisdiction[d.jurisdiction or "unspecified"] = (
            by_jurisdiction.get(d.jurisdiction or "unspecified", 0) + 1
        )
        by_domain[d.domain or "unspecified"] = (
            by_domain.get(d.domain or "unspecified", 0) + 1
        )
        by_type[d.doc_type or "other"] = by_type.get(d.doc_type or "other", 0) + 1
    top_domain = max(by_domain, key=lambda k: by_domain[k], default="")
    scenarios = (
        db.query(Scenario).filter(Scenario.organization_id == organization_id).all()
    )
    top_topics: dict[str, int] = {}
    for s in scenarios:
        for t in (s.tags or []) + ([s.domain] if s.domain else []):
            top_topics[t] = top_topics.get(t, 0) + 1
    return {
        "document_clusters": {
            "by_jurisdiction": by_jurisdiction,
            "by_domain": by_domain,
            "by_type": by_type,
            "knowledge_artefacts": len(artefacts),
            "contract_reviews": len(contracts),
            "total_documents": len(docs),
        },
        "suggested_new_scenarios": _suggestions(artefacts, scenarios),
        "community_topics": dict(
            sorted(top_topics.items(), key=lambda kv: -kv[1])[:10]
        ),
        "coverage_gap": f"No knowledge artefacts found for the most common domain `{top_domain}`."
        if top_domain and not by_domain.get(top_domain)
        else "Coverage appears representative of ingested knowledge artefacts.",
    }


def _suggestions(docs: list[LegalDocument], scenarios: list[Scenario]) -> list[str]:
    domains = {d.domain for d in docs if d.domain}
    scenario_domains = {s.domain for s in scenarios if s.domain}
    missing = sorted(domains - scenario_domains)
    out = []
    for m in missing[:4]:
        out.append(
            f"A scenario exploring a {m} dispute would reuse existing knowledge materials."
        )
    if not out:
        out.append(
            "Create a new comparative scenario across jurisdictions to exercise the knowledge base."
        )
    return out
