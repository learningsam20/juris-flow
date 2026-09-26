"""Risk aggregation, obligation load, and balance score (PRD §5.2)."""

from __future__ import annotations

from dataclasses import dataclass

from app.review.extractor import ClauseExtraction

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
    summary = RiskSummary()
    for f in findings:
        if f.clause_type == "general":
            continue
        if f.risk_level == "high":
            summary.high_count += 1
        elif f.risk_level == "medium":
            summary.medium_count += 1
        else:
            summary.low_count += 1
        if f.obligation:
            summary.obligation_count += 1
    summary.balance_score = _balance_score(findings)
    return summary


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
) -> dict[str, str]:
    """Rule-based rationale for a finding's risk level plus the action it calls for."""
    clause_type = (clause_type or "general").lower()
    risk_level = (risk_level or "low").lower()

    if not grounded:
        return {
            "risk_rationale": (
                "This finding could not be verified against the document text, so it is "
                "conservatively graded low. It needs human review before it can be relied on."
            ),
            "recommended_action": (
                "Re-run the review to verify, or check the clause manually against the full document."
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

    return {
        "risk_rationale": why,
        "recommended_action": RECOMMENDED_ACTION[risk_level],
    }
