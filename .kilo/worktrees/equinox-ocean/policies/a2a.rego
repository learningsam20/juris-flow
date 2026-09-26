package jurislab.a2a

default allow := false
default reason := "denied_by_policy"

# A2A message authorization: schema-validated, sender/recipient enrolled in
# the active simulation, phase valid, and org-scoped (PRD §15.4).
# input: { organization: { organization_id, participants, phase },
#          message: { from_agent, to_agent, message_type },
#          user: { organization_id, platform_roles } }
allow if {
    member("platform_admin", input.user.platform_roles)
}

allow if {
    input.message.organization_id == input.organization.organization_id
    input.message.organization_id == input.user.organization_id
    sim_member(input.organization.participants, input.message.from_agent)
    sim_member(input.organization.participants, input.message.to_agent)
    input.message.from_agent != input.message.to_agent
    phase_valid(input.organization.phases, input.organization.phase)
}

reason := "a2a_not_simulation_member" if {
    not sim_member(input.organization.participants, input.message.from_agent)
}

reason := "a2a_recipient_not_enrolled" if {
    sim_member(input.organization.participants, input.message.from_agent)
    not sim_member(input.organization.participants, input.message.to_agent)
}