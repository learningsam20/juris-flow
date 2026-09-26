"""Risk aggregation, obligation load, and balance score (PRD §5.2)."""

from __future__ import annotations

from dataclasses import dataclass

from app.review.extractor import (
    HIGH_RISK_CLAUSE_TYPES,
    MEDIUM_RISK_CLAUSE_TYPES,
    ClauseExtraction,
)

PARTY_MARKERS = {
    "plaintiff_side": [
        "the buyer",
        "the tenant",
        "the client",
        "the customer",
        "the borrower",
        "the lessee",
    ],
    "defendant_side": [
        "the seller",
        "the landlord",
        "the vendor",
        "the supplier",
        "the lender",
        "the lessor",
    ],
}


@dataclass
class RiskSummary:
    high_count: int = 0
    medium_count: int = 0
    low_count: int = 0
    obligation_count: int = 0
    obligations_by_party: dict[str, int] | None = None
    balance_score: float = 0.0  # -1 (single-sided against) .. 0 (balanced) .. 1


def compute_risk_summary(findings: list[ClauseExtraction]) -> RiskSummary:
    """Aggregate *confirmed* risk only (KM-backed or low informational).

    Findings with ``support_status == manual_review`` are excluded from
    high/medium rollups — they are advisories, not confirmed problems.
    """
    summary = RiskSummary()
    for f in findings:
        if f.clause_type == "general":
            continue
        support = getattr(f, "support_status", "") or ""
        if support == "manual_review":
            # Advisory only — do not inflate confirmed risk counts.
            continue
        if support == "doc_ungrounded" or not getattr(f, "grounded", True):
            summary.low_count += 1
            continue
        if f.risk_level == "high":
            summary.high_count += 1
        elif f.risk_level == "medium":
            summary.medium_count += 1
        else:
            summary.low_count += 1
        if f.obligation and support != "manual_review":
            summary.obligation_count += 1
    # Balance score uses grounded, non-advisory obligations only.
    balance_inputs = [
        f
        for f in findings
        if f.obligation
        and getattr(f, "grounded", True)
        and (getattr(f, "support_status", "") or "")
        not in ("manual_review", "doc_ungrounded")
    ]
    summary.balance_score = _balance_score(balance_inputs)
    return summary


def effective_risk_level(
    risk_level: str | None, implementation_status: str | None
) -> str:
    """Residual risk after remediation: applied mitigations drop to low."""
    status = (implementation_status or "not_started").strip().lower()
    if status == "applied":
        return "low"
    level = (risk_level or "low").strip().lower()
    return level if level in {"high", "medium", "low"} else "low"


def review_risk_level_from_counts(*, high: int, medium: int) -> str:
    if high > 0:
        return "high"
    if medium > 0:
        return "medium"
    return "low"


def compute_residual_risk_summary(findings: list) -> RiskSummary:
    """Aggregate open (non-applied) risk from persisted ReviewFinding-like objects."""
    summary = RiskSummary()

    class _Proxy:
        def __init__(self, src: object) -> None:
            from app.review.extractor import is_abstained_text

            self.text = str(getattr(src, "text", "") or "")
            self.obligation = True
            self.grounded = not is_abstained_text(self.text)

    balance_sources: list[_Proxy] = []
    for f in findings:
        clause = str(getattr(f, "clause_type", "general") or "general")
        if clause == "general":
            continue
        # Manual-review advisories are not confirmed residual risk.
        if str(getattr(f, "support_status", "") or "") == "manual_review":
            continue
        status = str(getattr(f, "implementation_status", "not_started") or "not_started")
        level = effective_risk_level(getattr(f, "risk_level", "low"), status)
        if level == "high":
            summary.high_count += 1
        elif level == "medium":
            summary.medium_count += 1
        else:
            summary.low_count += 1
        if bool(getattr(f, "obligation", False)) and status != "applied":
            summary.obligation_count += 1
            balance_sources.append(_Proxy(f))
    summary.balance_score = _balance_score(balance_sources) if balance_sources else 0.0
    return summary


def recompute_review_metrics(review: object, findings: list) -> dict:
    """Update review risk/obligation/balance from residual finding state.

    Finding ``risk_level`` stays as originally flagged; residual is derived from
    ``implementation_status == applied``.
    """
    residual = compute_residual_risk_summary(findings)
    risk_level = review_risk_level_from_counts(
        high=residual.high_count, medium=residual.medium_count
    )
    setattr(review, "risk_level", risk_level)
    setattr(review, "obligation_load", residual.obligation_count)
    setattr(review, "balance_score", residual.balance_score)
    remediated = sum(
        1
        for f in findings
        if str(getattr(f, "implementation_status", "") or "") == "applied"
    )
    return {
        "risk_level": risk_level,
        "obligation_load": residual.obligation_count,
        "balance_score": residual.balance_score,
        "residual_high": residual.high_count,
        "residual_medium": residual.medium_count,
        "residual_low": residual.low_count,
        "remediated_count": remediated,
        "findings_count": len(findings),
    }


def _balance_score(findings: list[ClauseExtraction]) -> float:
    obligations = [f for f in findings if f.obligation and f.grounded]
    if not obligations:
        return 0.0
    burdens: dict[str, int] = {"plaintiff_side": 0, "defendant_side": 0, "either": 0}
    for f in obligations:
        lower = f.text.lower()
        if any(m in lower for m in PARTY_MARKERS["plaintiff_side"]):
            burdens["plaintiff_side"] += 1
        elif any(m in lower for m in PARTY_MARKERS["defendant_side"]):
            burdens["defendant_side"] += 1
        else:
            burdens["either"] += 1
    p = burdens["plaintiff_side"]
    d = burdens["defendant_side"]
    total = p + d
    if total == 0:
        return 0.0
    # negative when defendant-side burden dominates, positive when plaintiff-side
    return round((p - d) / total, 3)


RISK_WHY = {
    "high": {
        "termination": "Termination rights can end the agreement early — often unilaterally or on short notice — disrupting operations and revenue.",
        "indemnity": "Indemnity obligations may require one party to compensate the other for losses, sometimes without a cap.",
        "penalties": "Penalty or liquidated-damages provisions could impose disproportionate charges for breach or late payment.",
        "liability_cap": "Liability limits set the maximum financial exposure; one-sided or absent caps concentrate the downside on a party.",
        "confidentiality": "Broad confidentiality duties without carve-outs can trigger breach claims for routine or required disclosures.",
        "non_compete": "Non-compete restrictions can prevent the party from operating or competing after the relationship ends.",
    },
    "medium": {
        "payment": "Payment timing, late fees, and default triggers directly affect cash flow and can accelerate termination or penalties.",
        "dispute_resolution": "Forum and arbitration terms determine where and how a dispute is resolved, often in a costly or inconvenient venue.",
        "ip_ownership": "IP ownership and licensing terms decide who keeps the work product and any future developments.",
        "non_solicit": "Non-solicit restrictions can block hiring or client contact with the other party's people and customers.",
        "notice": "Notice periods define how rights are exercised; short or one-sided notice can strip negotiating leverage.",
        "renewal": "Auto-renewal or evergreen terms can silently extend the commitment beyond the intended term.",
    },
}

RECOMMENDED_ACTION = {
    "high": "Negotiate before signing — add caps, carve-outs, or reciprocal rights, and have counsel review the clause.",
    "medium": "Clarify the intended position with the other party and tighten the wording before finalizing.",
    "low": "No immediate action required — monitor when the document is next revised.",
}


def risk_insight(
    *,
    clause_type: str,
    risk_level: str,
    obligation: bool,
    grounded: bool = True,
    support_status: str = "",
    suggested_risk_level: str = "",
) -> dict[str, str]:
    """Rule-based rationale for a finding's risk level plus the action it calls for."""
    clause_type = (clause_type or "general").lower()
    risk_level = (risk_level or "low").lower()
    support = (support_status or "").strip().lower()
    suggested = (suggested_risk_level or risk_level).lower()

    if not grounded or support == "doc_ungrounded":
        return {
            "risk_rationale": (
                "This finding could not be verified against the document text, so it is "
                "conservatively graded low. It needs human review before it can be relied on."
            ),
            "recommended_action": (
                "Re-run the review to verify, or check the clause manually against the full document."
            ),
        }

    if support == "manual_review":
        return {
            "risk_rationale": (
                f"The model suggested a {suggested} risk on this {(clause_type or 'clause').replace('_', ' ')} "
                "provision, but no Knowledge Hub artefact (statute, precedent, or policy) "
                "substantiates that assessment. It is reported as an advisory for manual review, "
                "not as a confirmed risk."
            ),
            "recommended_action": (
                "Advise counsel to review this clause manually and, if appropriate, "
                "add supporting knowledge artefacts so future reviews can confirm the risk."
            ),
        }

    if risk_level == "high":
        why = RISK_WHY["high"].get(
            clause_type,
            "This clause carries materially greater risk to the party shouldering it and "
            "typically needs negotiation before execution.",
        )
    elif risk_level == "medium":
        why = RISK_WHY["medium"].get(
            clause_type,
            "This clause affects the balance of the arrangement and should be reviewed against "
            "the intended commercial position.",
        )
    else:
        why = "This clause aligns with balanced or low-exposure terms; no material risk was flagged."

    if obligation:
        why += " It also imposes a binding obligation on a party, not just a right."
    if support == "km_confirmed":
        why += " Confirmed against Knowledge Hub artefacts."

    return {
        "risk_rationale": why,
        "recommended_action": RECOMMENDED_ACTION[risk_level],
    }


LEVEL_FLAG = {"high": "🔴", "medium": "🟡", "low": "🟢"}

LEVEL_SUMMARY = {
    "high": (
        "Material exposure: the clause can cut the agreement short, create uncapped "
        "financial liability, or restrict how the party operates. Negotiate before signing."
    ),
    "medium": (
        "Meaningful commercial effect: the clause shapes cash flow, forum, ownership, or "
        "notice leverage. Clarify the position and tighten the wording before finalizing."
    ),
    "low": (
        "Standard or balanced wording with no material exposure detected. Monitor it at "
        "the next revision rather than renegotiating."
    ),
}

ASSIGNMENT_RULES = [
    {
        "rule": "The LLM grades each clause using these rules as examples",
        "detail": (
            "The extraction prompt hands the model this exact ruleset — the HIGH and "
            "MEDIUM clause lists, worked examples, and the one-sidedness test — and "
            "asks it to return high/medium/low per finding, so the grade reflects the "
            "clause in its context rather than its type alone."
        ),
    },
    {
        "rule": "Ungrounded findings are always low",
        "detail": (
            "A finding that cannot be located verbatim in the document text is graded "
            "'low' and flagged 'not grounded' instead of being trusted at its "
            "self-reported level."
        ),
    },
    {
        "rule": "Clause type sets a severity floor",
        "detail": (
            "Termination, penalties, indemnity, non-compete, confidentiality and "
            "liability cap are never shown below HIGH. Payment, dispute resolution, IP "
            "ownership, non-solicit, notice and renewal are never shown below MEDIUM. "
            "Everything else (parties, effective date, force majeure, governing law) "
            "defaults to LOW."
        ),
    },
    {
        "rule": "One-sided obligations escalate",
        "detail": (
            "If a finding is an obligation and the document never contains 'either "
            "party' or 'each party', the level is raised to at least MEDIUM because "
            "nothing signals reciprocal treatment."
        ),
    },
    {
        "rule": "The model may grade higher, never lower",
        "detail": (
            "When the LLM judges a clause worse than its default (a payment clause it "
            "reads as severe), that higher grade stands. When the LLM is unavailable, "
            "the clause-type defaults above produce the same levels on their own."
        ),
    },
    {
        "rule": "Every flag carries a rationale",
        "detail": (
            "Each finding returns risk_rationale (why this level) and "
            "recommended_action (what to do next), both derived from the clause type "
            "and the level above."
        ),
    },
]


def risk_guidelines() -> dict:
    """The complete high/medium/low flagging ruleset, exposed to the UI and report."""
    return {
        "levels": [
            {
                "level": "high",
                "flag": LEVEL_FLAG["high"],
                "label": "High risk",
                "summary": LEVEL_SUMMARY["high"],
                "clause_types": sorted(HIGH_RISK_CLAUSE_TYPES),
                "why_it_matters": dict(RISK_WHY["high"]),
                "recommended_action": RECOMMENDED_ACTION["high"],
                "triggers": [
                    "Clause type is one of "
                    + ", ".join(sorted(HIGH_RISK_CLAUSE_TYPES))
                    + " — these are never shown below high.",
                    (
                        "The LLM graded this clause high in context (one-sided wording, no "
                        "cap, short notice period)."
                    ),
                    "An obligation with no reciprocal wording anywhere in the document.",
                ],
            },
            {
                "level": "medium",
                "flag": LEVEL_FLAG["medium"],
                "label": "Medium risk",
                "summary": LEVEL_SUMMARY["medium"],
                "clause_types": sorted(MEDIUM_RISK_CLAUSE_TYPES),
                "why_it_matters": dict(RISK_WHY["medium"]),
                "recommended_action": RECOMMENDED_ACTION["medium"],
                "triggers": [
                    "Clause type is one of "
                    + ", ".join(sorted(MEDIUM_RISK_CLAUSE_TYPES))
                    + " — these are never shown below medium.",
                    "The LLM graded this clause medium in context.",
                    "A low-graded obligation with no reciprocal wording in the document.",
                ],
            },
            {
                "level": "low",
                "flag": LEVEL_FLAG["low"],
                "label": "Low risk",
                "summary": LEVEL_SUMMARY["low"],
                "clause_types": [
                    "parties",
                    "effective_date",
                    "force_majeure",
                    "governing_law",
                    "general",
                ],
                "why_it_matters": {},
                "recommended_action": RECOMMENDED_ACTION["low"],
                "triggers": [
                    (
                        "Clause type outside the high and medium lists, and the LLM saw "
                        "nothing in the wording that raises it."
                    ),
                    "Finding could not be grounded in the document text (always low).",
                    "Clause reads as balanced and imposes no obligation.",
                ],
            },
        ],
        "assignment_rules": ASSIGNMENT_RULES,
        "disclaimer": (
            "Risk levels are generated by rule-based and model-assisted analysis for "
            "educational and informational purposes only, and are not legal advice."
        ),
    }
