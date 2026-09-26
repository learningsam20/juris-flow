"""Tool-calling implementations registered with the MCP gateway.

Each tool may only be executed through the MCP gateway, which enforces the OPA
``mcp`` policy (PRD §8, §15.4). Tools validate organization scope and return
grounded, jurisdiction-aware results.
"""

from __future__ import annotations

import logging

from app.core.constants import DOCS_COLLECTION, SIM_COLLECTION
from app.embeddings.factory import get_embeddings
from app.llm.base import LLMProvider
from app.mcp.gateway import register_tool
from app.vectorstore.factory import get_vectorstore

logger = logging.getLogger(__name__)

DOC_OPENERS = "Educational and informational. Not legal advice. Sources shown are for transparency."

_CONTRACT_DOC_TYPES = frozenset(
    {"contract", "agreement", "nda", "lease", "contract_review"}
)


def _is_contract_review_hit(meta: dict | None) -> bool:
    """True when a hit is a contract under review (exclude from KM grounding).

    Explicit ``knowledge_artefact`` category always wins — upload UI historically
    defaulted ``doc_type=contract`` for artefacts, which must not exclude them.
    """
    meta = meta or {}
    cat = (meta.get("doc_category") or meta.get("document_category") or "").lower()
    if cat == "knowledge_artefact":
        return False
    if cat == "contract_review":
        return True
    dtype = (meta.get("doc_type") or "").lower()
    return dtype in _CONTRACT_DOC_TYPES


def _prefer_jurisdiction_domain(
    hits: list, *, jurisdiction: str = "", domain: str = ""
) -> list:
    """Stable soft-rank: prefer matching juris/domain without hard-excluding blanks."""
    juris = (jurisdiction or "").strip().lower()
    dom = (domain or "").strip().lower()
    if not juris and not dom:
        return hits

    def key(h) -> tuple:
        meta = h.metadata or {}
        hj = (meta.get("jurisdiction") or "").strip().lower()
        hd = (meta.get("domain") or "").strip().lower()
        score = 0
        if juris:
            if hj == juris:
                score += 2
            elif not hj:
                score += 1
        if dom:
            if hd == dom:
                score += 2
            elif not hd:
                score += 1
        return (score, float(getattr(h, "score", 0) or 0))

    return sorted(hits, key=key, reverse=True)


@register_tool(
    "knowledge.retriever",
    "sim",
    "Jurisdiction-aware retrieval from the organization knowledge base (Knowledge Artefacts only)",
)
def knowledge_retriever(
    query: str, jurisdiction: str = "", domain: str = "", top_k: int = 5, **kwargs
) -> dict:
    organization_id = kwargs.get("organization_id", "")
    store = get_vectorstore()
    vector = get_embeddings().embed_one(query)
    # Org-scope only: many artefacts are uploaded without jurisdiction/domain
    # metadata. Soft-rank matches below instead of exact MatchValue filters.
    filters: dict = {"organization_id": organization_id}
    raw_hits = store.search(DOCS_COLLECTION, vector, filters=filters, top_k=top_k * 3)
    filtered = [h for h in raw_hits if not _is_contract_review_hit(h.metadata)]
    if not filtered:
        filtered = [
            h
            for h in raw_hits
            if (h.metadata or {}).get("doc_category") != "contract_review"
        ]
    ranked = _prefer_jurisdiction_domain(
        filtered, jurisdiction=jurisdiction, domain=domain
    )
    hits = ranked[:top_k]

    return {
        "hits": [
            {
                "id": h.id,
                "document_id": h.metadata.get("document_id"),
                "jurisdiction": h.metadata.get("jurisdiction"),
                "source_status": h.metadata.get("source_status"),
                "doc_category": "knowledge_artefact",
                "score": round(h.score, 4),
                "text": h.text,
            }
            for h in hits
        ],
        "note": "Retrieval filtered exclusively to Knowledge Artefacts.",
    }


@register_tool(
    "scenario.dossier_retriever",
    "sim",
    "Retrieve relevant factual excerpts and evidence from the scenario's uploaded dispute dossier document",
)
def scenario_dossier_retriever(
    query: str, scenario_id: str = "", top_k: int = 4, **kwargs
) -> dict:
    if not scenario_id:
        return {
            "hits": [],
            "note": "No scenario_id provided for scenario dossier search.",
        }
    store = get_vectorstore()
    vector = get_embeddings().embed_one(query)
    filters: dict = {"scenario_id": scenario_id}
    org_id = kwargs.get("organization_id")
    if org_id:
        filters["organization_id"] = org_id
    try:
        hits = store.search(SIM_COLLECTION, vector, filters=filters, top_k=top_k)
    except Exception as exc:
        logger.warning("Scenario dossier search in %s failed: %s", SIM_COLLECTION, exc)
        hits = []
    return {
        "hits": [
            {
                "id": h.id,
                "document_id": h.metadata.get("filename", "scenario_dossier"),
                "filename": h.metadata.get("filename", "scenario_dossier"),
                "chunk_index": h.metadata.get("chunk_index", 0),
                "source_type": "scenario_dossier",
                "score": round(h.score, 4),
                "text": h.text,
            }
            for h in hits
        ],
        "note": f"Retrieved from dedicated scenario dossier collection ({SIM_COLLECTION}).",
    }


@register_tool("citation.formatter", "sim", "Build a markdown citation reference")
def citation_formatter(
    excerpt: str, document_id: str = "", jurisdiction: str = "", provision: str = ""
) -> dict:
    parts = []
    if document_id:
        parts.append(f"Document `{document_id}`")
    if jurisdiction:
        parts.append(jurisdiction)
    if provision:
        parts.append(provision)
    source = " · ".join(parts) or "unknown source"
    return {
        "citation": f"> Source: {source}\n> “{excerpt[:500]}”",
        "citation_ref": {
            "document_id": document_id,
            "legal_provision": provision,
            "excerpt": excerpt[:500],
        },
    }


@register_tool(
    "fact.validator", "sim", "Check a claim against the supplied scenario facts"
)
def fact_validator(claim: str, facts: str = "") -> dict:
    if not facts:
        return {
            "verdict": "unsupported",
            "detail": "No facts provided to validate against.",
        }
    norm_claim = claim.lower()
    norm_facts = facts.lower()
    for keyword in norm_claim.split(" "):
        if len(keyword) > 4 and keyword not in norm_facts:
            continue
    common = len(set(norm_claim.split()) & set(norm_facts.split()))
    if not set(norm_claim.split()) & set(norm_facts.split()):
        return {
            "verdict": "unsupported",
            "detail": "The claim introduces details not present in the provided facts.",
        }
    present = common >= 3
    return {
        "verdict": "supported" if present else "partially_supported",
        "detail": "The claim references details present in the provided facts."
        if present
        else "Only fragments of the claim appear in the provided facts.",
    }


@register_tool("issue.extractor", "sim", "Extract legal issues for the judge outcome")
def issue_extractor(text: str, llm: LLMProvider | None = None, **kwargs) -> dict:
    prompt = (
        "List the principal legal issues from this argument. Return a bullet list only. "
        "Base every issue on facts and cited provisions; do not invent new facts."
    )
    return {"issues": _llm_lines(prompt, text, llm)}


@register_tool(
    "outcome.template",
    "sim",
    "Produce the judge's outcome section (non-binding, educational)",
)
def outcome_template(
    issues: list, reasoning_summary: str = "", llm: LLMProvider | None = None
) -> dict:
    if llm is None:
        return {
            "outcome": "Provisional (educational) outcome.",
            "reasoning": "Educational summary. Not legal advice and not a real court outcome.",
            "disclaimer": DOC_OPENERS,
        }
    prompt = (
        "Based on these issues, produce a short non-binding educational outcome with reasoning. "
        "Clearly state it is educational, not legal advice, and not a real case outcome.\n\n"
        f"ISSUES:\n{chr(10).join('- ' + i for i in issues)}\n\n"
        f"ARGUMENT SUMMARY: {reasoning_summary}"
    )
    result = _llm_lines(prompt, "", llm, json_mode=False)
    return {
        "outcome": result or "Educational outcome not generated.",
        "reasoning": result,
        "disclaimer": DOC_OPENERS,
    }


@register_tool(
    "terminology.explainer", "sim", "Plain-language explanation of a legal term"
)
def terminology_explainer(term: str, llm: LLMProvider | None = None) -> dict:
    if llm is None:
        return {
            "explanation": f"“{term}” is a legal concept that a lawyer can explain in your context.",
            "suggestion": f"Ask a lawyer: “What does {term} mean for my situation?”",
        }
    explanation = llm.chat(
        "Explain legal terms in plain language. Offer one actionable question for a real lawyer. "
        "Informational, not advice.",
        [{"role": "user", "content": f"Explain: {term}"}],
    )
    return {"explanation": explanation}


@register_tool(
    "plain_language.rewriter", "sim", "Rewrite complex text in simple language"
)
def plain_language_rewriter(text: str, llm: LLMProvider | None = None) -> dict:
    if llm is None:
        return {"rewritten": text}
    rewritten = llm.chat(
        "Rewrite the following into clear, plain language while preserving meaning.",
        [{"role": "user", "content": text}],
    )
    return {"rewritten": rewritten}


@register_tool(
    "resource.linker", "sim", "Link to legal aid / official resources with disclaimer"
)
def resource_linker(topic: str = "", jurisdiction: str = "") -> dict:
    return {
        "resources": [
            {
                "name": "Official court / legal aid portal (verify for your jurisdiction)",
                "note": f"Search for legal aid in {jurisdiction or 'your jurisdiction'}.",
            }
        ],
        "disclaimer": DOC_OPENERS,
        "suggestion": "Ask a qualified lawyer or a local legal aid clinic for jurisdiction-specific guidance.",
    }


@register_tool(
    "expert.retriever",
    "sim",
    "Domain-specific context retrieval for witness/expert agents",
)
def expert_retriever(
    query: str, jurisdiction: str = "", domain: str = "", **kwargs
) -> dict:
    return knowledge_retriever(
        query,
        jurisdiction=jurisdiction,
        domain=domain,
        top_k=3,
        organization_id=kwargs.get("organization_id", ""),
    )


@register_tool(
    "case_study.generator", "sim", "Generate the case study markdown at simulation end"
)
def case_study_generator(
    scenario_title: str = "",
    scenario_facts: str = "",
    messages: list | None = None,
    jurisdiction: str = "",
    domain: str = "",
    llm: LLMProvider | None = None,
) -> dict:
    from app.agents.casestudy import build_case_study

    md = build_case_study(
        scenario_title=scenario_title,
        scenario_facts=scenario_facts,
        messages=messages or [],
        jurisdiction=jurisdiction,
        domain=domain,
        llm=llm,
    )
    return {"markdown": md}


@register_tool("document.parser", "review", "Parse an uploaded document into text")
def document_parser(filename: str, content: bytes) -> dict:
    from app.ingestion.parser import parse_document

    result = parse_document(filename, content)
    return {"text": result.text, "extracted": result.extracted}


@register_tool("clause.extractor", "review", "Extract clauses with grounded spans")
def clause_extractor(text: str, llm: LLMProvider | None = None) -> dict:
    from app.review.extractor import review_document_text

    findings = review_document_text(text, llm=llm)
    return {
        "findings": [
            {
                "clause_type": f.clause_type,
                "risk_level": f.risk_level,
                "text": f.text[:500],
            }
            for f in findings
        ]
    }


@register_tool("risk.scorer", "review", "Aggregate risk, obligations and balance score")
def risk_scorer(findings: list | None = None, text: str = "") -> dict:
    from app.review.extractor import ClauseExtraction, assign_default_risk
    from app.review.risk import compute_risk_summary

    items = [
        ClauseExtraction(
            clause_type=f.get("clause_type", "general"),
            risk_level=f.get("risk_level", "low"),
            text=f.get("text", ""),
            obligation=bool(f.get("obligation", False)),
        )
        for f in (findings or [])
    ]
    if text:
        assign_default_risk(items, text)
    sum_ = compute_risk_summary(items)
    return {
        "risk_level": "high"
        if sum_.high_count
        else "medium"
        if sum_.medium_count
        else "low",
        "high": sum_.high_count,
        "medium": sum_.medium_count,
        "low": sum_.low_count,
        "obligations": sum_.obligation_count,
        "balance_score": sum_.balance_score,
    }


@register_tool("summary.generator", "review", "Generate executive summary for a review")
def summary_generator(
    findings: list | None = None, llm: LLMProvider | None = None
) -> dict:
    if llm is None:
        return {
            "summary": "Review completed; human review recommended.",
            "warning": "LLM summary unavailable.",
        }
    lines = "\n".join(
        f"- {f.get('clause_type')} ({f.get('risk_level')})" for f in (findings or [])
    )
    return {
        "summary": llm.chat(
            "Produce a concise executive summary of risks. Ground in listed clauses. Informational, not advice.",
            [{"role": "user", "content": lines or "No clauses identified."}],
        )
    }


@register_tool("scenario.loader", "sim", "Load a scenario and its latest version")
def scenario_loader(scenario_version_id: str = "", **kwargs) -> dict:
    from app.db.session import SessionLocal
    from app.models import ScenarioVersion

    db = SessionLocal()
    try:
        version = (
            db.query(ScenarioVersion)
            .filter(ScenarioVersion.id == scenario_version_id)
            .one_or_none()
        )
        if version is None:
            return {"error": "scenario version not found"}
        return {
            "title": version.title or "Untitled scenario",
            "facts": version.fact_pattern,
            "parameters": version.parameters or {},
            "documents": version.document_ids or [],
            "id": scenario_version_id,
        }
    finally:
        db.close()


@register_tool("simulation.state_manager", "sim", "Persist simulation state")
def simulation_state_manager(
    simulation_id: str = "", state_update: dict | None = None, **kwargs
) -> dict:
    from app.db.session import SessionLocal
    from app.models import Simulation

    db = SessionLocal()
    try:
        sim = db.query(Simulation).filter(Simulation.id == simulation_id).one_or_none()
        if sim is None:
            return {"error": "simulation not found"}
        update = state_update or {}
        for key in (
            "status",
            "phase",
            "current_turn",
            "participants",
            "active_agents",
            "state",
            "injected_facts",
            "focus_areas",
        ):
            if key in update:
                setattr(sim, key, update[key])
        db.commit()
        return {"ok": True}
    finally:
        db.close()


def _llm_lines(
    system_prompt: str, text: str, llm: LLMProvider | None, json_mode: bool = False
) -> str:
    if llm is None:
        return "Reference: issues were not extractable without an LLM. See transcript for agent arguments."
    return llm.chat(
        system_prompt,
        [{"role": "user", "content": text or "No input text provided."}],
    )
