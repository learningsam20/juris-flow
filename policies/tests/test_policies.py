"""Policy decision-matrix tests for the embedded OPA engine.

Runs the same Rego sources shipped under ``policies/*.rego`` against a matrix of
inputs, asserting allow/deny + reason for RBAC, tenant isolation, MCP tool
authorization, A2A messaging, and export control. Can be executed standalone
(``scripts/rego_test.sh``) or as part of the backend pytest suite.
"""
from __future__ import annotations

import pytest

from app.opa.engine import get_engine

ORG_A = "org-a"
ORG_B = "org-b"

ROLES = {
    "platform_admin": {"platform_roles": ["platform_admin"], "module_roles": []},
    "org_admin": {"platform_roles": ["org_admin"], "module_roles": []},
    "member": {"platform_roles": ["member"], "module_roles": []},
    "sim_educator": {"platform_roles": ["member"], "module_roles": ["sim.sim_educator"]},
    "review_lead": {"platform_roles": ["member"], "module_roles": ["review.review_lead"]},
    "sim_pro": {"platform_roles": ["member"], "module_roles": ["sim.sim_professional"]},
}


def _user(role: str, org: str = ORG_A) -> dict:
    u = dict(ROLES[role])
    u["organization_id"] = org
    return u


CASES = [
    # ---------------- RBAC ----------------
    ("rbac", "org_admin", {
        "action": "module",
        "user": _user("org_admin"),
        "resource": {"module": "sim", "permission": "scenario.view"},
    }, True, None),
    ("rbac", "platform_admin", {
        "action": "module",
        "user": _user("platform_admin"),
        "resource": {"module": "any", "permission": "any.view"},
    }, True, None),
    ("rbac", "member_denied_view", {
        "action": "module",
        "user": _user("member"),
        "resource": {"module": "sim", "permission": "scenario.view"},
    }, False, "missing_module_permission"),
    ("rbac", "wrong_module_role", {
        "action": "module",
        "user": _user("review_lead"),
        "resource": {"module": "sim", "permission": "scenario.view"},
    }, False, "missing_module_permission"),
    ("rbac", "module_role_allows", {
        "action": "module",
        "user": _user("sim_educator"),
        "resource": {"module": "sim", "permission": "scenario.edit"},
    }, True, None),
    ("rbac", "module_role_denied", {
        "action": "module",
        "user": _user("sim_educator"),
        "resource": {"module": "review", "permission": "report.export"},
    }, False, "missing_module_permission"),

    # ---------------- Tenant ----------------
    ("tenant", "same_org", {
        "user": _user("member"),
        "resource": {"organization_id": ORG_A},
    }, True, None),
    ("tenant", "cross_org", {
        "user": _user("member"),
        "resource": {"organization_id": ORG_B},
    }, False, "cross_tenant_access"),
    ("tenant", "platform_admin_global", {
        "user": _user("platform_admin"),
        "resource": {"organization_id": ORG_B},
    }, True, None),


    # ---------------- MCP ----------------
    ("mcp", "platform_admin_any_tool", {
        "agent": {"role": "plaintiff", "module": "sim", "organization_id": ORG_A},
        "tool": "any.tool",
        "scope": {"organization_id": ORG_B, "module": "sim"},
        "user": _user("platform_admin"),
    }, True, None),
    ("mcp", "allowed_agent_tool", {
        "agent": {"role": "plaintiff", "module": "sim", "organization_id": ORG_A},
        "tool": "knowledge.retriever",
        "scope": {"organization_id": ORG_A, "module": "sim"},
        "user": _user("member"),
    }, True, None),
    ("mcp", "tool_not_in_role", {
        "agent": {"role": "plaintiff", "module": "sim", "organization_id": ORG_A},
        "tool": "case_study.generator",
        "scope": {"organization_id": ORG_A, "module": "sim"},
        "user": _user("member"),
    }, False, "mcp_tool_not_authorized"),
    ("mcp", "agent_org_mismatch", {
        "agent": {"role": "plaintiff", "module": "sim", "organization_id": ORG_B},
        "tool": "knowledge.retriever",
        "scope": {"organization_id": ORG_A, "module": "sim"},
        "user": _user("member"),
    }, False, "mcp_agent_scope_denied"),
    ("mcp", "scope_org_mismatch", {
        "agent": {"role": "plaintiff", "module": "sim", "organization_id": ORG_A},
        "tool": "knowledge.retriever",
        "scope": {"organization_id": ORG_B, "module": "sim"},
        "user": _user("member"),
    }, False, None),

    # ---------------- A2A ----------------
    ("a2a", "enrolled_pair", {
        "organization": {"organization_id": ORG_A, "participants": ["plaintiff", "defendant", "judge"],
                         "phases": ["opening", "arguments", "judge_questions", "outcome"], "phase": "opening"},
        "message": {"organization_id": ORG_A, "from_agent": "plaintiff", "to_agent": "defendant",
                    "message_type": "simulation.turn"},
        "user": _user("member"),
    }, True, None),
    ("a2a", "recipient_not_enrolled", {
        "organization": {"organization_id": ORG_A, "participants": ["plaintiff", "defendant", "judge"],
                         "phases": ["opening", "arguments", "judge_questions", "outcome"], "phase": "opening"},
        "message": {"organization_id": ORG_A, "from_agent": "plaintiff", "to_agent": "witness",
                    "message_type": "simulation.turn"},
        "user": _user("member"),
    }, False, "a2a_recipient_not_enrolled"),
    ("a2a", "self_message_denied", {
        "organization": {"organization_id": ORG_A, "participants": ["plaintiff", "defendant", "judge"],
                         "phases": ["opening", "arguments", "judge_questions", "outcome"], "phase": "opening"},
        "message": {"organization_id": ORG_A, "from_agent": "plaintiff", "to_agent": "plaintiff",
                    "message_type": "simulation.turn"},
        "user": _user("member"),
    }, False, None),
    ("a2a", "org_mismatch", {
        "organization": {"organization_id": ORG_B, "participants": ["plaintiff", "defendant", "judge"],
                         "phases": ["opening"], "phase": "opening"},
        "message": {"organization_id": ORG_A, "from_agent": "plaintiff", "to_agent": "defendant",
                    "message_type": "simulation.turn"},
        "user": _user("member"),
    }, False, None),

    # ---------------- Export ----------------
    ("export", "platform_admin_export", {
        "user": _user("platform_admin"),
        "artifact": {"type": "case_study", "organization_id": ORG_A},
        "checks": {"disclaimers": True, "citations": True},
    }, True, None),
    ("export", "educator_case_study", {
        "user": _user("sim_educator"),
        "artifact": {"type": "case_study", "organization_id": ORG_A},
        "checks": {"disclaimers": True, "citations": True},
    }, True, None),
    ("export", "professional_case_study_no_cites", {
        "user": _user("sim_pro"),
        "artifact": {"type": "case_study", "organization_id": ORG_A},
        "checks": {"disclaimers": True, "citations": False},
    }, True, None),
    ("export", "review_lead_report", {
        "user": _user("review_lead"),
        "artifact": {"type": "review_report", "organization_id": ORG_A},
        "checks": {"disclaimers": True, "citations": True},
    }, True, None),
    ("export", "educator_cannot_report", {
        "user": _user("sim_educator"),
        "artifact": {"type": "review_report", "organization_id": ORG_A},
        "checks": {"disclaimers": True, "citations": True},
    }, False, "export_role_not_permitted"),
    ("export", "missing_disclaimer", {
        "user": _user("platform_admin"),
        "artifact": {"type": "case_study", "organization_id": ORG_A},
        "checks": {"disclaimers": False, "citations": False},
    }, False, "export_requires_disclaimers"),
    ("export", "member_denied", {
        "user": _user("member"),
        "artifact": {"type": "case_study", "organization_id": ORG_A},
        "checks": {"disclaimers": True, "citations": True},
    }, False, "export_role_not_permitted"),

    # ---------------- RBAC (extended) ----------------
    ("rbac", "sim_pro_view_scenarios", {
        "action": "module",
        "user": _user("sim_pro"),
        "resource": {"module": "sim", "permission": "scenario.view"},
    }, True, None),
    ("rbac", "review_lead_view_reports", {
        "action": "module",
        "user": _user("review_lead"),
        "resource": {"module": "review", "permission": "report.view"},
    }, True, None),
    ("rbac", "sim_educator_denied_hub", {
        "action": "module",
        "user": _user("sim_educator"),
        "resource": {"module": "hub", "permission": "document.upload"},
    }, False, "missing_module_permission"),
    ("rbac", "org_admin_manage_hub", {
        "action": "module",
        "user": _user("org_admin"),
        "resource": {"module": "hub", "permission": "knowledge.view"},
    }, True, None),

    # ---------------- Tenant (extended) ----------------
    ("tenant", "org_admin_cross_org_denied", {
        "user": _user("org_admin"),
        "resource": {"organization_id": ORG_B},
    }, False, "cross_tenant_access"),
    ("tenant", "sim_pro_same_org", {
        "user": _user("sim_pro"),
        "resource": {"organization_id": ORG_A},
    }, True, None),

    # ---------------- MCP (extended) ----------------
    ("mcp", "fact_validator_allowed", {
        "agent": {"role": "plaintiff", "module": "sim", "organization_id": ORG_A},
        "tool": "fact.validator",
        "scope": {"organization_id": ORG_A, "module": "sim"},
        "user": _user("sim_educator"),
    }, True, None),
    ("mcp", "case_study_generator_member_denied", {
        "agent": {"role": "plaintiff", "module": "sim", "organization_id": ORG_A},
        "tool": "case_study.generator",
        "scope": {"organization_id": ORG_A, "module": "sim"},
        "user": _user("sim_educator"),
    }, False, "mcp_tool_not_authorized"),
    ("mcp", "invalid_tool_name_denied", {
        "agent": {"role": "plaintiff", "module": "sim", "organization_id": ORG_A},
        "tool": "nonexistent.tool",
        "scope": {"organization_id": ORG_A, "module": "sim"},
        "user": _user("sim_educator"),
    }, False, "mcp_tool_not_authorized"),

    # ---------------- A2A (extended) ----------------
    ("a2a", "judge_questions_phase", {
        "organization": {"organization_id": ORG_A, "participants": ["plaintiff", "defendant", "judge"],
                         "phases": ["opening", "arguments", "judge_questions", "outcome"], "phase": "judge_questions"},
        "message": {"organization_id": ORG_A, "from_agent": "judge", "to_agent": "plaintiff",
                    "message_type": "simulation.turn"},
        "user": _user("member"),
    }, True, None),
    ("a2a", "cross_org_message_denied", {
        "organization": {"organization_id": ORG_A, "participants": ["plaintiff", "defendant", "judge"],
                         "phases": ["opening", "arguments", "judge_questions", "outcome"], "phase": "opening"},
        "message": {"organization_id": ORG_B, "from_agent": "plaintiff", "to_agent": "defendant",
                    "message_type": "simulation.turn"},
        "user": _user("member"),
    }, False, None),

    # ---------------- Export (extended) ----------------
    ("export", "export_org_agnostic", {
        "user": _user("sim_educator"),
        "artifact": {"type": "case_study", "organization_id": ORG_B},
        "checks": {"disclaimers": True, "citations": True},
    }, True, None),
    ("export", "review_lead_case_study_denied", {
        "user": _user("review_lead"),
        "artifact": {"type": "case_study", "organization_id": ORG_A},
        "checks": {"disclaimers": True, "citations": True},
    }, False, "denied_by_policy"),
    ("export", "sim_pro_review_report_denied", {
        "user": _user("sim_pro"),
        "artifact": {"type": "review_report", "organization_id": ORG_A},
        "checks": {"disclaimers": True, "citations": True},
    }, False, "export_role_not_permitted"),
    ("export", "missing_citations_check", {
        "user": _user("review_lead"),
        "artifact": {"type": "review_report", "organization_id": ORG_A},
        "checks": {"disclaimers": True, "citations": False},
    }, False, "export_requires_citations"),
]


@pytest.mark.parametrize(
    ("policy", "name", "payload", "expected_allow", "expected_reason"),
    [(p, n, i, a, r) for p, n, i, a, r in CASES],
    ids=[f"{p}:{n}" for p, n, _, _, _ in CASES],
)
def test_policy_decision(policy, name, payload, expected_allow, expected_reason):
    decision = get_engine().decide(policy, payload)
    assert decision.allow is expected_allow, f"{name}: {decision}"
    if expected_reason:
        assert decision.reason == expected_reason, f"{name}: {decision}"