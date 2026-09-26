package jurisflow.export

import data.jurisflow.roles

default allow := false
default reason := "denied_by_policy"

# Export / publication control: only authorized roles may export or publish,
# and only after disclaimer + citation checks pass (PRD §15.4).
# input: { user: { platform_roles, module_roles },
#          artifact: { type: "case_study" | "review_report", organization_id },
#          checks: { disclaimers, citations } }
allow if {
    member("platform_admin", input.user.platform_roles)
    input.checks.disclaimers == true
}

# Educator exports/publishes case studies
allow if {
    member("sim.sim_educator", input.user.module_roles)
    input.artifact.type == "case_study"
    input.checks.disclaimers == true
    input.checks.citations == true
}

# Sim professional exports case studies for internal use
allow if {
    member("sim.sim_professional", input.user.module_roles)
    input.artifact.type == "case_study"
    input.checks.disclaimers == true
}

# Review lead exports/publishes client-facing reports
allow if {
    member("review.review_lead", input.user.module_roles)
    input.artifact.type == "review_report"
    input.checks.disclaimers == true
    input.checks.citations == true
}

reason := "export_requires_disclaimers" if {
    input.checks.disclaimers == false
}

reason := "export_requires_citations" if {
    input.checks.disclaimers == true
    input.checks.citations == false
}

reason := "export_role_not_permitted" if {
    input.checks.disclaimers == true
    input.checks.citations == true
    not member("platform_admin", input.user.platform_roles)
    not member("sim.sim_educator", input.user.module_roles)
    not member("sim.sim_professional", input.user.module_roles)
    not member("review.review_lead", input.user.module_roles)
}

# Role holds an export entitlement but not for this artifact type (e.g. an
# educator requesting a client-facing review report).
reason := "export_role_not_permitted" if {
    input.checks.disclaimers == true
    input.checks.citations == true
    not member("platform_admin", input.user.platform_roles)
    input.artifact.type == "review_report"
    not member("review.review_lead", input.user.module_roles)
}