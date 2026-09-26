"""MCP tool registry and gateway.

Every tool call is authorized by the ``mcp`` OPA policy before the tool
implementation runs (default-deny; unauthorized calls never reach the tool).
Tool calls and results are logged and counted for telemetry (PRD §8, §15.4).
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from app.core.errors import PolicyDeniedError
from app.core.telemetry import incr
from app.opa.engine import get_engine

logger = logging.getLogger(__name__)


class Tool:
    def __init__(
        self, name: str, module: str, fn: Callable[..., Any], description: str = ""
    ) -> None:
        self.name = name
        self.module = module
        self.fn = fn
        self.description = description


_registry: dict[str, Tool] = {}


def register(tool: Tool) -> None:
    _registry[tool.name] = tool


def register_tool(name: str, module: str, description: str = "") -> Callable[..., Any]:
    def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        register(Tool(name, module, fn, description))
        return fn

    return decorator


def list_tools() -> list[dict]:
    return [
        {"name": t.name, "module": t.module, "description": t.description}
        for t in _registry.values()
    ]


def execute(
    tool_name: str,
    *,
    agent_role: str,
    agent_organization: str,
    actor_organization: str,
    actor_platform_roles: list[str],
    module: str,
    **kwargs: Any,
) -> Any:
    tool = _registry.get(tool_name)
    if tool is None:
        raise PolicyDeniedError(f"MCP tool `{tool_name}` is not registered")
    decision_input = {
        "agent": {
            "role": agent_role,
            "organization_id": agent_organization,
            "module": module,
        },
        "tool": tool_name,
        "scope": {
            "organization_id": actor_organization,
            "module": module,
            "resource_type": "document_or_scenario",
        },
        "user": {
            "organization_id": actor_organization,
            "platform_roles": actor_platform_roles,
        },
    }
    decision = get_engine().decide("mcp", decision_input)
    if not decision.allow:
        incr("mcp.denied")
        raise PolicyDeniedError(
            f"MCP tool `{tool_name}` denied for agent `{agent_role}`: {decision.reason}"
        )
    incr(f"mcp.tool.{tool_name}")

    scope_organization = kwargs.pop("organization_id", actor_organization)
    if (
        scope_organization != actor_organization
        and "platform_admin" not in actor_platform_roles
    ):
        raise PolicyDeniedError("MCP tool called with cross-organization scope")

    result = tool.fn(**kwargs)
    logger.info(
        "mcp.tool_call",
        extra={
            "tool_name": tool_name,
            "agent_role": agent_role,
            "tool_module": module,
            "ok": True,
        },
    )
    return result
