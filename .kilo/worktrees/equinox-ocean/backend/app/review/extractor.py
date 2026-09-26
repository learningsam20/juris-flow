"""Clause and entity extraction with grounded document spans (PRD §5.2).

Combine deterministic pattern matches (always grounded to exact spans) with an
LLM review pass. Every highlighted finding must cite a real span in the source
document; anything that cannot be grounded is abstained and reported as such
(PRD §15.2.1, §15.3 output guardrails).
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass

from app.core.errors import LLMUnavailableError
from app.llm.base import LLMProvider
from app.review.remediation import propose_clause_remediation

logger = logging.getLogger(__name__)

CLAUSE_TYPES = [
    "parties",
    "effective_date",
    "termination",
    "renewal",
    "payment",
    "penalties",
    "indemnity",
    "liability_cap",
    "dispute_resolution",
    "confidentiality",
    "ip_ownership",
    "non_compete",
    "non_solicit",
    "notice",
    "force_majeure",
    "governing_law",
]

RISK_LEVELS = ("high", "medium", "low")

# Deterministic keyword patterns for grounding (normalized matching on lower text).
KEYWORD_MAP: dict[str, list[str]] = {
    "termination": [
        "termination",
        "sack ",
        "rescind",
        "cancellation",
        "terminate",
        "upon termination",
    ],
    "renewal": ["renew", "renewal", "automatic renewal"],
    "payment": ["payable", "payment", "invoic", "remit", "salary", "consideration"],
    "penalties": ["penalty", "late fee", "interest", "liquidated damages", "penal"],
    "indemnity": ["indemnif", "indemnity", "hold harmless", "defend"],
    "liability_cap": [
        "liability cap",
        "limit of liability",
        "maximum liability",
        "aggregate liability",
    ],
    "dispute_resolution": [
        "arbitration",
        "jurisdiction",
        "venue",
        "dispute resolution",
        "choice of law",
        "governing law",
    ],
    "confidentiality": ["confidential", "non-disclosure", "nondisclosure"],
    "ip_ownership": [
        "intellectual property",
        "ip ownership",
        "ownership of",
        "works made for hire",
    ],
    "non_compete": [
        "non-compet",
        "noncompet",
        "competition clause",
        "restrictive covenant",
    ],
    "non_solicit": ["non-solicit", "nonsolicit", "solicit"],
    "notice": [
        "notice period",
        "written notice",
        "notice requirements",
        "provide notice",
    ],
    "effective_date": [
        "effective date",
        "commencement date",
        "commencement",
        "in effect",
    ],
    "force_majeure": ["force majeure", "act of god", "unforeseeable"],
    "governing_law": ["governed by", "governing law", "laws of"],
    "parties": [
        "hereinafter",
        "party",
        "the vendor",
        "the company",
        "the client",
        "the lessor",
        "the lessee",
    ],
}


@dataclass
class Span:
    start: int
    end: int
    text: str


@dataclass
class ClauseExtraction:
    clause_type: str
    risk_level: str
    text: str
    span: Span | None = None
    explanation: str = ""
    plain_language: str = ""
    obligation: bool = False
    grounded: bool = True
    abstained: bool = False
    proposed_change: str = ""
    change_rationale: str = ""


def _find_span(text: str, needle: str, search_from: int = 0) -> Span | None:
    if not needle:
        return None
    norm_text = text.lower()
    norm_needle = needle.lower().strip()
    for window in (0, 20):
        try:
            start = norm_text.index(norm_needle, search_from)
            # expand to surrounding sentence
            return _expand_to_sentence(text, start, len(norm_needle), window)
        except ValueError:
            pass
    return None


def _expand_to_sentence(text: str, start: int, length: int, window: int) -> Span:
    s = max(
        text.rfind(".", 0, start), text.rfind("\n", 0, start), text.rfind(";", 0, start)
    )
    sent_start = 0 if s == -1 or start - s > 800 else s + 1
    e = start + length
    e_candidates = [text.find(".", e), text.find("\n", e), text.find(";", e)]
    valid = [x for x in e_candidates if x != -1]
    sent_end = min(valid) + 1 if valid else len(text)
    if window and (sent_end - sent_start) > 400:
        sent_start = max(0, start - window)
        sent_end = min(len(text), e + window)
    return Span(sent_start, sent_end, text[sent_start:sent_end])


def pattern_clauses(text: str) -> list[ClauseExtraction]:
    """Deterministic grounded extraction independent of the LLM."""
    findings: list[ClauseExtraction] = []
    lower = text.lower()
    for clause_type, keywords in KEYWORD_MAP.items():
        scan_from = 0
        for kw in keywords:
            idx = lower.find(kw, scan_from)
            while idx != -1:
                span = _expand_to_sentence(text, idx, len(kw), 0)
                if not any(f.span == span for f in findings):
                    findings.append(
                        ClauseExtraction(
                            clause_type=clause_type,
                            risk_level="low",
                            text=span.text.strip(),
                            span=span,
                            grounded=True,
                        )
                    )
                scan_from = idx + 1
                idx = lower.find(kw, scan_from)
    return findings


EXTRACTION_SYSTEM = (
    "You are a legal document reviewer. Analyze the supplied document section(s) and identify "
    "the 8 most important clauses and obligations. Return ONLY a JSON object with the shape "
    '{"findings": [{"clause_type": "<one of: parties, effective_date, termination, renewal, '
    "payment, penalties, indemnity, liability_cap, dispute_resolution, confidentiality, "
    'ip_ownership, non_compete, non_solicit, notice, force_majeure, governing_law>", '
    '"risk_level": "high|medium|low", "excerpt": "<short verbatim text from the document>", '
    '"explanation": "<why it matters>", "obligation": true|false, '
    '"proposed_change": "<specific contractual amendment/replacement wording to balance or remediate this clause in the context of the contract>", '
    '"change_rationale": "<why this amendment balances the contract>"}]}. '
    "Constraints: return at most 8 findings; keep excerpts under 400 characters and explanations "
    "under 120 characters; no plain_language field; use excerpts VERBATIM from the provided text; "
    'do not invent clauses or laws. If no clauses can be identified, return {"findings": []}. '
    "This output is educational and informational, not legal advice."
)


def llm_clauses(text: str, llm: LLMProvider) -> list[ClauseExtraction]:
    user = (
        "Document text:\n\n"
        f"{text[:12000]}\n\n"
        "Return the JSON findings array described in the system prompt."
    )
    raw = llm.chat(EXTRACTION_SYSTEM, [{"role": "user", "content": user}])
    return parse_extraction_json(raw)


def parse_extraction_json(raw: str) -> list[ClauseExtraction]:
    try:
        start = raw.find("{")
        end = raw.rfind("}")
        if start == -1 or end == -1:
            raise ValueError("no JSON object found")
        data = json.loads(raw[start : end + 1])
        findings = data.get("findings", [])
    except Exception:
        logger.warning("LLM clause extraction returned non-JSON output; abstaining")
        return []
    out: list[ClauseExtraction] = []
    for f in findings[:40]:
        clause_type = str(f.get("clause_type", "")).strip()
        risk_level = str(f.get("risk_level", "low")).strip().lower()
        if risk_level not in RISK_LEVELS:
            risk_level = "low"
        excerpt = str(f.get("excerpt", "")).strip()
        out.append(
            ClauseExtraction(
                clause_type=clause_type or "general",
                risk_level=risk_level,
                text=excerpt,
                explanation=str(f.get("explanation", "")),
                plain_language=str(f.get("plain_language", "")),
                obligation=bool(f.get("obligation", False)),
                grounded=bool(excerpt),
                proposed_change=str(f.get("proposed_change", "")).strip(),
                change_rationale=str(f.get("change_rationale", "")).strip(),
            )
        )
    return out


def merge_extractions(
    source_text: str, pattern: list[ClauseExtraction], llm: list[ClauseExtraction]
) -> list[ClauseExtraction]:
    merged = list(pattern)
    seen_keys = {(f.clause_type, f.text) for f in merged}
    for f in llm:
        # ground the LLM excerpt in the source or abstain
        span = _find_span(source_text, f.text[:120])
        if span is None:
            f.grounded = False
            f.abstained = True
            f.text = f"Could not be grounded in the source text: {f.text[:120]}"
        else:
            f.span = span
            if not f.text:
                f.text = span.text.strip()
        key = (f.clause_type, f.text[:80])
        if key not in seen_keys:
            merged.append(f)
            seen_keys.add(key)
    return merged


def review_document_text(
    text: str, llm: LLMProvider | None = None
) -> list[ClauseExtraction]:
    """Full extraction pipeline. Raises LLMUnavailableError if an LLM is required and unavailable."""
    pattern = pattern_clauses(text)
    if llm is None:
        return pattern
    try:
        llm_findings = llm_clauses(text, llm)
    except LLMUnavailableError:
        raise
    except Exception:
        logger.exception("LLM clause review failed")
        llm_findings = []
    return merge_extractions(text, pattern, llm_findings)


def assign_default_risk(findings: list[ClauseExtraction], source_text: str) -> None:
    HIGH_TYPES = {
        "termination",
        "penalties",
        "indemnity",
        "non_compete",
        "confidentiality",
        "liability_cap",
    }
    MEDIUM_TYPES = {
        "payment",
        "dispute_resolution",
        "ip_ownership",
        "non_solicit",
        "notice",
        "renewal",
    }
    for f in findings:
        if not f.grounded:
            f.risk_level = "low"
            continue
        if f.clause_type in HIGH_TYPES:
            f.risk_level = "high"
        elif f.clause_type in MEDIUM_TYPES:
            f.risk_level = "medium"
        # one-sidedness heuristic
        between = source_text.lower().count("either party") + source_text.lower().count(
            "each party"
        )
        if f.obligation and between == 0:
            f.risk_level = "high" if f.risk_level == "high" else "medium"

        if not f.proposed_change:
            change, rationale = propose_clause_remediation(
                clause_type=f.clause_type,
                risk_level=f.risk_level,
                text=f.text,
                document_context=source_text[:1000],
            )
            f.proposed_change = change
            f.change_rationale = rationale
