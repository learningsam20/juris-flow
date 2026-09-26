"""Case study generation (PRD §5.1, §6.6)."""

from __future__ import annotations

import logging

from app.core.constants import DISCLAIMER_CASE_STUDY
from app.llm.base import LLMProvider

logger = logging.getLogger(__name__)


def build_case_study(
    *,
    scenario_title: str,
    scenario_facts: str,
    messages: list[dict],
    jurisdiction: str = "",
    domain: str = "",
    incident_date: str | None = None,
    proceedings_date: str | None = None,
    llm: LLMProvider | None = None,
) -> str:
    transcript = "\n\n".join(
        f"### {m.get('agent_role', m.get('role', 'agent')).title()} ({m.get('phase', '')})\n{m.get('text', '')}"
        for m in messages
    )
    sections = f"# Case Study — {scenario_title or 'Untitled Simulation'}\n\n"
    if incident_date or proceedings_date or jurisdiction or domain:
        meta_parts = []
        if jurisdiction:
            meta_parts.append(f"**Jurisdiction:** {jurisdiction}")
        if domain:
            meta_parts.append(f"**Domain:** {domain.title()}")
        if incident_date:
            meta_parts.append(f"**Date of Incident:** {incident_date}")
        if proceedings_date:
            meta_parts.append(f"**Date of Proceedings:** {proceedings_date}")
        sections += " | ".join(meta_parts) + "\n\n"

    sections += _section(
        "Summary",
        _generate_text(
            "Provide an exhaustive, complete executive summary of this case in 3 structured paragraphs: "
            "1) Background & Parties, 2) Core Factual Controversy & Contested Legal Claims, "
            "3) Practical & Legal Teaching Value. Ensure the summary is thorough, articulate, and complete.",
            transcript,
            llm,
            fallback="A simulated case explored the dispute through structured legal argumentation between the parties.",
            max_tokens=1200,
        ),
    )
    sections += _section("Facts", scenario_facts or "_No fact pattern was provided._")
    sections += _section("Issues", _issues_section(transcript, llm))
    sections += _section("Arguments by Side", _arguments_section(transcript))
    sections += _section(
        "Outcome & Reasoning",
        _generate_text(
            "Provide a comprehensive, authoritative judicial determination, holding, and detailed legal reasoning "
            "resolving each contested claim grounded in the arguments above. Analyze the evidence, apply relevant legal standards, "
            "and state the definitive outcome, allocation of liability, and remedies. Ensure the determination is thorough and completely concluded.",
            transcript,
            llm,
            fallback="The judge's outcome is an educational simulation exercise, resolving claims based on the arguments presented.",
            max_tokens=1500,
        ),
    )
    principles = _generate_text(
        "List 4-6 key legal principles highlighted by this case, marked general vs jurisdiction-aware, with complete explanatory notes.",
        transcript,
        llm,
        fallback="- Principles must be derived from cited statutory provisions and scenario facts.",
        max_tokens=800,
    )
    sections += _section("Legal Principles Highlighted", principles)

    # Local knowledge grounding and citations audit
    citations: list[dict] = []
    for m in messages:
        c_list = m.get("citations")
        if isinstance(c_list, list):
            for item in c_list:
                if isinstance(item, dict):
                    citations.append(item)
    grounded_messages = [m for m in messages if m.get("citations")]
    total_messages = len(messages)
    grounding_rate = (
        round((len(grounded_messages) / total_messages * 100), 1)
        if total_messages > 0
        else 0
    )
    grounding_body = (
        f"- **Local Knowledge Passages Cited:** {len(citations)} cited source(s)\n"
        f"- **Turn Grounding Fidelity:** {len(grounded_messages)} of {total_messages} turns ({grounding_rate}%) grounded with verified local knowledge.\n"
    )
    if citations:
        grounding_body += "- **Cited Sources:**\n"
        for c in citations[:8]:
            prov = c.get("legal_provision") or c.get("document_id") or "Local Document"
            exc = (c.get("excerpt") or "")[:120].replace("\n", " ").strip()
            grounding_body += f'  - *{prov}*: "{exc}..."\n'
    else:
        grounding_body += "- *⚠️ Note: Simulation executed without local knowledge base retrieval grounding. Arguments rely upon baseline model reasoning and scenario facts.*\n"
    sections += _section("Local Knowledge & Evidentiary Grounding", grounding_body)

    sections += _section("What a Real Lawyer Would Do Next", _checklist)
    sections += _section("Reflection Questions", _reflection_questions)
    sections += _section(
        "Jurisdiction & Domain",
        f"- Jurisdiction: {jurisdiction or 'not specified'}\n- Domain: {domain or 'not specified'}",
    )
    return sections + "\n\n" + DISCLAIMER_CASE_STUDY


def _section(heading: str, body: str) -> str:
    return f"\n\n## {heading}\n\n{body}"


def _generate_text(
    prompt: str,
    context: str,
    llm: LLMProvider | None,
    fallback: str,
    max_tokens: int = 1200,
) -> str:
    if llm is None:
        return fallback
    try:
        result = llm.chat(
            "You produce authoritative, educational case-study analysis grounded in the provided transcript. "
            "Provide exhaustive, structured, and complete legal output without cutting off sentences. "
            "Informational, not legal advice.",
            [
                {
                    "role": "user",
                    "content": f"{prompt}\n\nTranscript:\n{context[:28000]}",
                }
            ],
            max_tokens=max_tokens,
        ).strip()
        return result or fallback
    except Exception:
        logger.exception("case study LLM generation failed")
        return fallback


def _issues_section(transcript: str, llm: LLMProvider | None) -> str:
    return _generate_text(
        "List the principal legal issues and procedural questions as a comprehensive bullet list grounded in the transcript.",
        transcript,
        llm,
        fallback="- Issue 1: identify the core legal question.\n- Issue 2: identify the procedural or contractual question.",
        max_tokens=800,
    )


def _arguments_section(transcript: str) -> str:
    return _organize_arguments(transcript)


def _organize_arguments(transcript: str) -> str:
    blocks: dict[str, list[str]] = {
        "Plaintiff": [],
        "Defendant": [],
        "Judge": [],
        "Informer": [],
        "Witness": [],
    }
    current = None
    for raw in transcript.split("\n\n"):
        line = raw.strip()
        for role in blocks:
            if line.lower().startswith(
                f"### {role.lower()}"
            ) or line.lower().startswith(f"**{role.lower()}"):
                current = role
            elif line.lower().startswith("###") or line.lower().startswith("**"):
                current = None
        if current:
            blocks[current].append(raw)
    out = []
    for role, parts in blocks.items():
        if parts:
            body = "\n\n".join(
                p
                for p in parts
                if not p.lower().startswith(f"### {role.lower()}") and "### " not in p
            )
            out.append(
                f"**{role}:**\n\n{body or '_No statements recorded for this role._'}"
            )
    return (
        "\n\n".join(out) if out else "_Arguments are available in the full transcript._"
    )


_checklist = """- Verify the controlling law and any procedural deadlines in the real jurisdiction.
- Identify who bears the burden of proof and what evidence is needed.
- Evaluate settlement or alternative dispute resolution options and their costs.
- Assess enforceability of the key clauses and possible defenses.
- Obtain client instructions and preserve privilege before taking any step."""

_reflection_questions = """1. Which argument was strongest, and why?
2. What extra facts would change the outcome?
3. How would this case play out differently in another jurisdiction?
4. When should a party seek settlement versus litigate?"""
