"""Input guardrails scanner: PII detection/redaction + prompt-injection scan.

Implements PRD §15.3 input guardrails: detect prompt-injection content embedded
in uploaded documents and isolate it (mark it, never treat it as instructions),
and detect/redact PII/sensitive data.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# --- PII patterns ---------------------------------------------------------
EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
PHONE_RE = re.compile(
    r"\b(?:\+?\d{1,3}[-.\s]?)?\(?\d{2,4}\)?[-.\s]?\d{3,4}[-.\s]?\d{3,4}\b"
)
PAN_RE = re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b")  # India PAN
SSN_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
AADHAAR_RE = re.compile(r"\b\d{4}[\s-]?\d{4}[\s-]?\d{4}\b")

PII_PATTERNS = {
    "email": EMAIL_RE,
    "phone": PHONE_RE,
    "india_pan": PAN_RE,
    "us_ssn": SSN_RE,
    "india_aadhaar": AADHAAR_RE,
}

# --- Prompt injection heuristics ------------------------------------------
INJECTION_MARKERS = [
    r"ignore (all )?(previous|prior|above|the above|system) instructions",
    r"ignore (all )?(previous|prior) (rules|prompts|messages)",
    r"you are now",
    r"act as (a )?system",
    r"disregard (earlier|previous|all) instructions",
    r"\*\*system\*\*",
    r"<\|system\|>",
    r"developer ?message",
    r"jailbreak",
    r"forget everything",
    r"moral ?bypass",
    r"output (only|just) ",
]
INJECTION_RE = re.compile("|".join(INJECTION_MARKERS), re.IGNORECASE)


@dataclass
class ScanReport:
    pii: dict[str, list[str]] = field(default_factory=dict)
    has_pii: bool = False
    injection_matches: list[str] = field(default_factory=list)
    injection_isolated: bool = False
    redacted_text: str = ""
    passed: bool = True

    @property
    def has_injection(self) -> bool:
        return bool(self.injection_matches)


def scan_text(text: str) -> ScanReport:
    report = ScanReport()
    redacted = text
    for label, pattern in PII_PATTERNS.items():
        matches = list(dict.fromkeys(pattern.findall(text)))
        if matches:
            report.pii[label] = matches
            for m in matches:
                redacted = redacted.replace(m, "[REDACTED:" + label.upper() + "]")
    report.has_pii = bool(report.pii)
    report.redacted_text = redacted

    seen: set[str] = set()
    for idx, line in enumerate(text.splitlines()):
        for marker_re in INJECTION_MARKERS:
            if re.search(marker_re, line, re.IGNORECASE):
                snippet = line.strip()[:160]
                if snippet not in seen:
                    seen.add(snippet)
                    report.injection_matches.append(snippet)
    report.injection_isolated = report.has_injection
    if report.has_injection:
        report.passed = False
        # The flagged lines are recorded and isolated: system instructions never
        # include document text verbatim, and agents treat documents as data.
    return report
