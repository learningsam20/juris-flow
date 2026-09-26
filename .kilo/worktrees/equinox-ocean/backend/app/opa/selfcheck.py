"""Startup policy self-check: verify all policy bundles compile and baseline decisions resolve."""

from __future__ import annotations

import logging
from pathlib import Path

from app.opa.engine import OPADecisionEngine

logger = logging.getLogger(__name__)

POLICIES_DIR = Path(__file__).resolve().parents[3] / "policies"

_CHECKS: list[tuple[str, dict]] = [
    (
        "rbac",
        {
            "action": "module",
            "user": {"platform_roles": [], "module_roles": ["sim.sim_educator"]},
            "resource": {"module": "sim", "permission": "scenario.view"},
        },
    ),
    (
        "rbac",
        {
            "action": "role",
            "user": {"platform_roles": ["org_admin"], "module_roles": []},
            "resource": {},
        },
    ),
    (
        "tenant",
        {
            "user": {"organization_id": "org-a"},
            "resource": {"organization_id": "org-a"},
        },
    ),
    (
        "mcp",
        {
            "agent_id": "any",
            "tool": "knowledge.retriever",
            "user": {
                "organization_id": "org-a",
                "platform_roles": [],
                "module_roles": ["sim.sim_educator"],
            },
            "agent": {"role": "plaintiff", "module": "sim", "organization_id": "org-a"},
            "scope": {
                "resource_type": "document",
                "resource_id": "d1",
                "module": "sim",
                "organization_id": "org-a",
            },
        },
    ),
]

_NEED_DENY: list[tuple[str, dict]] = [
    (
        "rbac",
        {
            "action": "module",
            "user": {"platform_roles": [], "module_roles": []},
            "resource": {"module": "sim", "permission": "scenario.view"},
        },
    ),
    (
        "tenant",
        {
            "user": {"organization_id": "org-a"},
            "resource": {"organization_id": "org-b"},
        },
    ),
    (
        "mcp",
        {
            "agent_id": "any",
            "tool": "case_study.generator",
            "user": {
                "organization_id": "org-a",
                "platform_roles": [],
                "module_roles": ["sim.sim_educator"],
            },
            "agent": {"role": "plaintiff", "module": "sim", "organization_id": "org-a"},
            "scope": {
                "resource_type": "case_study",
                "resource_id": "c1",
                "module": "sim",
                "organization_id": "org-b",
            },
        },
    ),
]


def policy_selfcheck() -> dict:
    engine = OPADecisionEngine(
        policies_dir=POLICIES_DIR, data_file=str(POLICIES_DIR / "data.json")
    )
    failures = []
    for policy, input_data in _CHECKS:
        try:
            decision = engine.decide(policy, input_data)
            if not decision.allow:
                failures.append(f"{policy}: expected allow")
        except Exception as exc:
            failures.append(f"{policy}: {exc}")
    for policy, input_data in _NEED_DENY:
        try:
            decision = engine.decide(policy, input_data)
            if decision.allow:
                failures.append(f"{policy}: expected deny")
        except Exception as exc:
            failures.append(f"{policy}: {exc}")
    return {
        "ok": not failures,
        "failures": failures,
        "policies_loaded": list(engine.rego_files),
    }
