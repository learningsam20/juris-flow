"""Contextual contract remediation and proposed amendment engine (PRD §5.2).

Generates actionable contractual language modifications and strategic rationale
to remediate identified legal risks in the context of the reviewed contract.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from app.llm.base import LLMProvider

logger = logging.getLogger(__name__)

STANDARD_REMEDIATIONS: dict[str, dict[str, Any]] = {
    "indemnity": {
        "proposed_change": (
            'Each party ("Indemnifying Party") agrees to defend, indemnify, and hold harmless the other party '
            '("Indemnified Party") from and against third-party claims arising solely out of the Indemnifying Party\'s '
            "gross negligence, willful misconduct, or material breach of this Agreement; provided that the Indemnifying "
            "Party's aggregate liability under this Section shall be subject to the limitations set forth in Section "
            "[Limitation of Liability], and neither party shall be liable for indirect, special, or consequential damages."
        ),
        "change_rationale": (
            "Establishes mutual, reciprocal indemnification, limits indemnity strictly to direct damages and material breach, "
            "subjects it to the contract's overall liability cap, and expressly excludes consequential or punitive damages."
        ),
    },
    "termination": {
        "proposed_change": (
            "Either party may terminate this Agreement: (a) for convenience upon thirty (30) days' prior written notice "
            "to the other party; or (b) immediately upon written notice if the other party commits a material breach of "
            "this Agreement and fails to cure such breach within thirty (30) days after receipt of written notice specifying the breach."
        ),
        "change_rationale": (
            "Creates balanced bilateral termination rights and establishes a mandatory 30-day notice-and-cure window, "
            "preventing sudden or arbitrary cancellation without an opportunity to remediate default."
        ),
    },
    "liability_cap": {
        "proposed_change": (
            "Except for gross negligence, willful misconduct, or breach of Section [Confidentiality], in no event shall "
            "either party's aggregate cumulative liability arising out of or related to this Agreement exceed the total "
            "amounts actually paid or payable by Client hereunder in the twelve (12) months immediately preceding the event "
            "giving rise to liability. In no event shall either party be liable for lost profits, loss of business, or "
            "consequential damages."
        ),
        "change_rationale": (
            "Institutes a standard mutual liability cap tied to 12 months of contract value, preventing uncapped enterprise "
            "exposure while adding standard market exclusions for indirect losses."
        ),
    },
    "penalties": {
        "proposed_change": (
            "In the event of a delayed payment or milestone, late fees shall be limited to simple interest at the rate of "
            "1.0% per month (or the maximum statutory rate permitted by applicable law, whichever is lower) calculated on "
            "undisputed overdue amounts commencing thirty (30) days after written notice of delinquency. Neither party shall "
            "be subject to punitive liquidated damages or disproportionate forfeiture."
        ),
        "change_rationale": (
            "Replaces punitive or unilateral liquidated damages with reasonable simple interest on undisputed sums and requires "
            "prior written delinquency notice."
        ),
    },
    "payment": {
        "proposed_change": (
            "All properly submitted and undisputed invoices shall be payable within thirty (30) calendar days of receipt (Net 30). "
            "In the event of a good faith dispute regarding any invoiced item, the paying party shall remit payment for the "
            "undisputed portion and provide written notice describing the disputed portion within fifteen (15) days."
        ),
        "change_rationale": (
            "Implements standard Net-30 commercial payment terms and protects the client from default or interest charges on "
            "amounts legitimately disputed in good faith."
        ),
    },
    "dispute_resolution": {
        "proposed_change": (
            "In the event of any dispute arising out of or relating to this Agreement, designated executive representatives of "
            "both parties shall first attempt in good faith to resolve the dispute through direct negotiation for thirty (30) days. "
            "If unresolved, the dispute shall be submitted to confidential mediation before either party may initiate binding "
            "arbitration or judicial proceedings in a mutually agreed neutral venue."
        ),
        "change_rationale": (
            "Introduces a multi-stage dispute escalation framework (negotiation followed by mediation) to minimize legal costs "
            "and avoid premature or aggressive litigation in an unfavorable venue."
        ),
    },
    "confidentiality": {
        "proposed_change": (
            "The receiving party shall hold the disclosing party's Confidential Information in confidence using at least the same "
            "degree of care as it uses for its own confidential materials (and no less than reasonable care). Obligations under this "
            "Section shall survive for a period of three (3) years from disclosure. Confidential Information shall exclude information "
            "that is publicly known, already known to the recipient without breach, or independently developed without reference to the disclosure."
        ),
        "change_rationale": (
            "Limits confidentiality liability to a realistic 3-year term rather than indefinite exposure and includes standard commercial "
            "carve-outs for public, pre-existing, and independently created information."
        ),
    },
    "ip_ownership": {
        "proposed_change": (
            'Each party retains all right, title, and interest in and to its pre-existing Intellectual Property ("Background IP"). '
            "Client shall own all rights in specific custom deliverables developed solely for Client under an executed Statement of Work, "
            "upon full payment. Provider is granted a limited, non-exclusive, revocable license solely to utilize such deliverables "
            "as strictly necessary to perform the Services."
        ),
        "change_rationale": (
            "Protects client ownership of paid custom work product while safeguarding existing background IP and precluding accidental "
            "surrender of proprietary technology or know-how."
        ),
    },
    "non_compete": {
        "proposed_change": (
            "Any restrictive covenant shall be limited strictly to the direct solicitation of active customers with whom the "
            "individual directly dealt during the twelve (12) months preceding termination, for a period not to exceed six (6) months "
            "post-termination within the primary operating market. This provision shall not restrict general business operations, "
            "passive investments, or employment in non-competing capacities."
        ),
        "change_rationale": (
            "Narrows an overreaching restraint of trade into an enforceable, reasonable non-solicitation covenant with narrow duration "
            "and geographic scope."
        ),
    },
    "non_solicit": {
        "proposed_change": (
            "During the Term and for a period of six (6) months thereafter, neither party shall directly solicit for employment any "
            "key employee of the other party actively involved in this engagement; provided that general public advertisements, job postings, "
            "or non-targeted recruiter outreach shall not be deemed a breach of this restriction."
        ),
        "change_rationale": (
            "Protects operational stability while carving out ordinary public job postings and unsolicited employee applications."
        ),
    },
    "notice": {
        "proposed_change": (
            "All formal notices required under this Agreement shall be given in writing and delivered via certified mail or via email "
            "to the designated representatives with confirmation of transmission. Notices shall be deemed delivered on the date of "
            "confirmed receipt or three (3) business days after mailing."
        ),
        "change_rationale": (
            "Modernizes notice delivery to include email with confirmation and provides clear, unambiguous delivery timelines."
        ),
    },
    "renewal": {
        "proposed_change": (
            "This Agreement shall renew for successive one (1) year terms only upon mutual written agreement, or automatically renewed "
            "only if the Provider delivers written reminder notice at least sixty (60) days prior to the expiration date and the Client "
            "does not provide written notice of non-renewal at least thirty (30) days prior to expiration."
        ),
        "change_rationale": (
            "Prevents silent, inadvertent contract extensions by obligating advance reminder notices and providing a clear non-renewal opt-out window."
        ),
    },
    "force_majeure": {
        "proposed_change": (
            "Neither party shall be liable for delay or default caused by events beyond reasonable control (including acts of God, "
            "severe natural disasters, or war). The affected party shall provide prompt written notice and exercise diligent efforts "
            "to mitigate impact. If a force majeure condition persists for more than thirty (30) days, either party may terminate "
            "this Agreement without penalty upon written notice."
        ),
        "change_rationale": (
            "Mandates prompt notice and mitigation efforts, while preserving the right to exit gracefully if disruption continues past 30 days."
        ),
    },
    "governing_law": {
        "proposed_change": (
            "This Agreement and any dispute arising out of or related to it shall be governed by and construed in accordance with "
            "the laws of [Agreed Neutral Jurisdiction], excluding its conflict of law principles. The parties agree to submit to "
            "the exclusive jurisdiction of the state and federal courts located therein."
        ),
        "change_rationale": (
            "Establishes a predictable, neutral jurisdiction and venue, avoiding costly legal proceedings in unfamiliar or distant jurisdictions."
        ),
    },
}

DEFAULT_REMEDIATION = {
    "proposed_change": (
        "The parties agree to amend this clause to establish bilateral, commercially reasonable terms consistent with standard "
        "industry practice, ensuring neither party assumes unilateral exposure without appropriate reciprocal protections."
    ),
    "change_rationale": (
        "Restores contractual balance, eliminates unilateral legal risk, and aligns obligations with customary commercial standards."
    ),
}

REMEDIATION_PROMPT = (
    "You are a senior contract attorney drafting precise, actionable redline amendments for a legal contract review. "
    "Based on the extracted clause text, its risk rating, and the contract context, propose: "
    "1. 'proposed_change': Concrete, ready-to-insert contractual replacement or amendment wording that mitigates the risk and protects the party. "
    "2. 'change_rationale': A concise 1-2 sentence explanation of why this specific change balances the contract and benefits the client. "
    'Respond ONLY with a JSON object of the form: {"proposed_change": "...", "change_rationale": "..."}.'
)


def propose_clause_remediation(
    clause_type: str,
    risk_level: str,
    text: str,
    document_context: str = "",
    llm: LLMProvider | None = None,
    stance: str = "balanced",
) -> tuple[str, str]:
    """Return (proposed_change, change_rationale) for an extracted clause finding."""
    clause_norm = (clause_type or "general").strip().lower()

    if llm and text.strip():
        user_prompt = (
            f"Clause Type: {clause_norm}\n"
            f"Risk Level: {risk_level}\n"
            f"Negotiation Stance: {stance}\n"
            f'Current Clause Text:\n"""{text[:1000]}"""\n'
        )
        if document_context:
            user_prompt += f"\nContract Context Summary:\n{document_context[:500]}\n"
        user_prompt += "\nReturn the JSON proposed_change and change_rationale."

        try:
            raw = llm.chat(
                REMEDIATION_PROMPT, [{"role": "user", "content": user_prompt}]
            )
            start = raw.find("{")
            end = raw.rfind("}")
            if start != -1 and end != -1:
                data = json.loads(raw[start : end + 1])
                change = str(data.get("proposed_change", "")).strip()
                rationale = str(data.get("change_rationale", "")).strip()
                if change:
                    return change, rationale
        except Exception:
            logger.warning(
                "LLM clause remediation failed; using market standard fallback",
                exc_info=True,
            )

    # Fallback to standard market remediation template
    std = STANDARD_REMEDIATIONS.get(clause_norm, DEFAULT_REMEDIATION)
    return str(std["proposed_change"]), str(std["change_rationale"])
