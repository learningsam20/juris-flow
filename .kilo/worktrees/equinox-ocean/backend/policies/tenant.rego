package jurislab.tenant

default allow := false
default reason := "denied_by_policy"

# Organization / tenant isolation for every API, document, simulation,
# report and analytics request (PRD §15.4).
allow if {
    input.resource.organization_id == input.user.organization_id
}

allow if {
    member("platform_admin", input.user.platform_roles)
}

reason := "cross_tenant_access" if {
    input.resource.organization_id != input.user.organization_id
    not member("platform_admin", input.user.platform_roles)
}