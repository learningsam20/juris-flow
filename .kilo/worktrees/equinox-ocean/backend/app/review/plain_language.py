"""Plain-language explanations and grounded Q&A (PRD §5.2, §8.5)."""

from __future__ import annotations

import logging

from app.core.errors import LLMUnavailableError
from app.llm.base import LLMProvider
from app.vectorstore.base import VectorStore

logger = logging.getLogger(__name__)

PLAIN_LANGUAGE_SYSTEM = (
    "You are the Informer, a legal aid agent. Explain legal clauses and rights in plain, simple "
    "language. Always end with at least one actionable suggestion or question the person could "
    "ask a real lawyer. Never give legal advice as fact; mark advice as informational and "
    "educational. Do not invent laws or cite authorities that are not provided."
)


def explain_clause(text: str, llm: LLMProvider | None = None) -> str:
    if llm is None:
        return _rule_based_explanation(text)
    try:
        return llm.chat(
            PLAIN_LANGUAGE_SYSTEM,
            [
                {
                    "role": "user",
                    "content": f"Explain this clause in simple terms:\n\n{text}",
                }
            ],
        )
    except LLMUnavailableError:
        raise
    except Exception:
        logger.exception("plain-language LLM call failed")
        return _rule_based_explanation(text)


def _rule_based_explanation(text: str) -> str:
    lower = text.lower()
    points: list[str] = []
    if "terminat" in lower:
        points.append(
            "This appears to cover termination — the right or obligation to end the agreement, and any notice required."
        )
    if "payable" in lower or "payment" in lower:
        points.append("This covers payment terms — who pays whom, how much, and when.")
    if "indemnif" in lower or "indemnity" in lower:
        points.append(
            "This is an indemnity — one party may be required to compensate the other for losses."
        )
    if "arbitration" in lower or "dispute" in lower:
        points.append(
            "This covers dispute resolution — arbitration, jurisdiction, and venue."
        )
    if "confidential" in lower:
        points.append(
            "This covers confidentiality — what information must be kept secret."
        )
    if "non-compet" in lower:
        points.append(
            "This appears to restrict competition after the relationship ends."
        )
    if "penalty" in lower or "interest" in lower:
        points.append("This covers penalties or interest for late payment.")
    if not points:
        points.append(
            "This clause governs rights and obligations that require case-by-case review."
        )
    return (
        "\n".join(f"- {p}" for p in points)
        + "\n\nThis explanation is informational and educational, not legal advice. "
        "Consider asking a qualified lawyer how this clause applies to your situation."
    )


def grounded_qa(
    question: str,
    document_text: str,
    store: VectorStore,
    collection: str,
    top_k: int = 4,
) -> dict:
    """Answer a question grounded only in the provided document (PRD §5.2, §6.5).

    Uses the Review Analyst pipeline: retrieve best-matching chunks, then ask the
    configured LLM to answer with explicit citations to chunk text.
    """
    from app.embeddings.factory import get_embeddings

    logger.info(
        "grounded_qa.query",
        extra={"question": question[:120], "collection": collection},
    )
    vector = get_embeddings().embed_one(question)
    hits = store.search(collection, vector, top_k=top_k)
    context = "\n\n---\n\n".join(
        f"[Chunk {h.metadata.get('chunk_index', h.id)}] {h.text}" for h in hits
    )
    return {
        "question": question,
        "context": context,
        "hits": hits,
        "document_text": document_text,
    }


def answer_grounded(
    question: str,
    document_text: str,
    store: VectorStore,
    collection: str,
    llm: LLMProvider,
) -> dict:
    ctx = grounded_qa(question, document_text, store, collection)
    system = (
        "You answer questions ONLY using the provided document chunks. If the answer is not in "
        "the chunks, say so clearly and abstain. Cite the exact chunk you relied on by quoting "
        "the source text. Output is educational and informational, not legal advice."
    )
    user = f"Question: {question}\n\nRelevant document chunks:\n{ctx['context']}"
    answer = llm.chat(system, [{"role": "user", "content": user}])
    citations = [h.id for h in ctx["hits"][:3]]
    return {"answer": answer, "citations": citations, "hits": ctx["hits"]}
