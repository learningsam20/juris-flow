package jurislab.mcp

import data.jurislab.roles

default allow := false
default reason := "denied_by_policy"

# Every MCP tool call must be authorized before execution (PRD §15.4).
# input: { agent: { role, module, organization_id },
#          tool: "name", scope: { resource_type, resource_id, module },
#          user: { organization_id, platform_roles } }
allow if {
    member("platform_admin", input.user.platform_roles)
}

allow if {
    # organization isolation: agent and tool scope belong to the acting user's org
    input.agent.organization_id == input.user.organization_id
    input.scope.organization_id == input.user.organization_id
    # role has this tool entitlement, and the agent's module matches the scope
    agent_tool_allowed(input.agent.role, input.tool, input.scope.module)
}

reason := "mcp_tool_not_authorized" if {
    not member("platform_admin", input.user.platform_roles)
    not agent_tool_allowed(input.agent.role, input.tool, input.scope.module)
}

reason := "mcp_agent_scope_denied" if {
    not member("platform_admin", input.user.platform_roles)
    agent_tool_allowed(input.agent.role, input.tool, input.scope.module)
    input.agent.organization_id != input.user.organization_id
}