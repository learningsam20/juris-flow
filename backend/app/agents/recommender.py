"""LLM recommender agent for the insights report (PRD §6.8).

Turns the dashboard/analytics metric pack into a structured report:
executive summary, timeline-phased recommendations, best practices already
followed, and gaps that need improvement. The LLM output is validated and
clamped into a fixed schema so the UI can render it deterministically.
"""

from __future__ import annotations

import json
import logging

logger = logging.getLogger(__name__)

# Delivery horizons the report is organised by (nearest first).
TIMELINES: tuple[str, ...] = ("immediate", "30_days", "90_days", "180_days")

TIMELINE_LABELS: dict[str, str] = {
    "immediate": "Immediate (0–7 days)",
    "30_days": "30 Days",
    "90_days": "90 Days",
    "180_days": "180 Days",
}

PRIORITIES: tuple[str, ...] = ("critical", "high", "medium", "low")

MAX_RECOMMENDATIONS = 12
MAX_BEST_PRACTICES = 8
MAX_GAPS = 8
MAX_ITEM_CHARS = 600

RECOMMENDER_SYSTEM = (
    "You are JurisFlow's contract-operations recommender agent. You review a JSON pack of "
    "operating metrics for a legal education & contract-review platform (documents ingested, "
    "contract audits, audit publication rate, simulation completion, knowledge-base usage, "
    "risk distribution across flagged clauses, balance scores, and telemetry latency) and you "
    "produce an actionable management report.\n"
    "Return ONLY a JSON object with this exact shape:\n"
    '{"executive_summary": "<3-5 sentence assessment of the current operating posture>", '
    '"recommendations": [{"title": "<short action>", "detail": "<what to do and why, 1-3 sentences>", '
    '"category": "governance|content|quality|operations|adoption|risk", '
    '"priority": "critical|high|medium|low", "timeline": "immediate|30_days|90_days|180_days"}], '
    '"best_practices": [{"title": "<practice>", "evidence": "<metric that shows it is working>", '
    '"timeline": "immediate|30_days|90_days|180_days"}], '
    '"needs_improvement": [{"title": "<gap>", "gap": "<what is missing>", '
    '"recommendation": "<concrete fix>", "timeline": "immediate|30_days|90_days|180_days"}]}\n'
    "Rules: 3-6 recommendations, 2-5 best practices, 2-5 needs-improvement items; every item "
    "must cite the metrics it is based on; timelines must reflect real urgency (use "
    "`immediate` only for issues that block or materially mislead users today); never invent "
    "metrics that are not in the pack; be specific about the contract-management workflow "
    "(ingest → audit → remediate → publish → review cycle). This output is educational and "
    "informational, not legal advice."
)


def build_user_prompt(metrics: dict) -> str:
    """Compact the metric pack so it fits comfortably in the prompt."""
    compact = {
        "kpis": metrics.get("kpis", {}),
        "risk_signals": metrics.get("risk_signals", {}),
        "coverage": metrics.get("coverage", {}),
        "activity": metrics.get("activity", {}),
        "telemetry": metrics.get("telemetry", {}),
    }
    return (
        "Metric pack (JSON):\n"
        f"{json.dumps(compact, sort_keys=True, default=str)}\n\n"
        "Return the JSON report object described in the system prompt."
    )


def _clean_text(value: object, limit: int = MAX_ITEM_CHARS) -> str:
    text = str(value or "").strip()
    return text[:limit]


def _clean_timeline(value: object, default: str = "30_days") -> str:
    key = str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
    if key in ("immediate", "now", "asap", "0_days", "0"):
        return "immediate"
    if key in ("30_days", "30", "30d", "month", "monthly"):
        return "30_days"
    if key in ("90_days", "90", "90d", "quarter", "quarterly"):
        return "90_days"
    if key in ("180_days", "180", "180d", "half_year", "6_months"):
        return "180_days"
    return default if default in TIMELINES else "30_days"


def _clean_priority(value: object, default: str = "medium") -> str:
    key = str(value or "").strip().lower()
    return key if key in PRIORITIES else default


def parse_recommender_json(raw: str) -> dict | None:
    """Parse the agent's JSON envelope; returns None when unusable."""
    try:
        start = raw.find("{")
        end = raw.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise ValueError("no JSON object found")
        data = json.loads(raw[start : end + 1])
    except Exception:
        logger.warning("recommender agent returned non-JSON output")
        return None
    if not isinstance(data, dict):
        return None
    return data


def normalize_report(data: dict) -> dict:
    """Clamp an agent payload into the report schema the UI renders."""
    recommendations: list[dict] = []
    for item in (data.get("recommendations") or [])[:MAX_RECOMMENDATIONS]:
        if not isinstance(item, dict):
            continue
        title = _clean_text(item.get("title"), 160)
        if not title:
            continue
        recommendations.append(
            {
                "title": title,
                "detail": _clean_text(item.get("detail")),
                "category": _clean_text(item.get("category"), 32) or "operations",
                "priority": _clean_priority(item.get("priority")),
                "timeline": _clean_timeline(item.get("timeline")),
            }
        )

    best_practices: list[dict] = []
    for item in (data.get("best_practices") or [])[:MAX_BEST_PRACTICES]:
        if not isinstance(item, dict):
            continue
        title = _clean_text(item.get("title"), 160)
        if not title:
            continue
        best_practices.append(
            {
                "title": title,
                "evidence": _clean_text(item.get("evidence")),
                "timeline": _clean_timeline(item.get("timeline"), "immediate"),
            }
        )

    needs_improvement: list[dict] = []
    for item in (data.get("needs_improvement") or [])[:MAX_GAPS]:
        if not isinstance(item, dict):
            continue
        title = _clean_text(item.get("title"), 160)
        if not title:
            continue
        needs_improvement.append(
            {
                "title": title,
                "gap": _clean_text(item.get("gap")),
                "recommendation": _clean_text(item.get("recommendation")),
                "timeline": _clean_timeline(item.get("timeline")),
            }
        )

    return {
        "executive_summary": _clean_text(data.get("executive_summary"), 2000)
        or "No executive summary was produced for this metric pack.",
        "recommendations": recommendations,
        "best_practices": best_practices,
        "needs_improvement": needs_improvement,
        "timeline_labels": dict(TIMELINE_LABELS),
    }
