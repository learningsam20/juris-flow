"""Embedded Rego-subset decision engine.

Policies are authored as standard Rego files under ``policies/*.rego`` (the
versioned source of truth) and are parsed by this engine at runtime. The
engine implements a documented, deterministic subset of Rego sufficient for the
RBAC / tenant / MCP / A2A / export policies shipped with JurisFlow.

When a full OPA server is available (set ``JAIL_OPA_URL``), ``RemoteOPAClient``
can evaluate the same policy files with the full Rego runtime instead. The
decision contract (allow / reason / policy version) is identical.

Supported subset
----------------
- ``package <name>``
- ``default <rule> := <literal>``
- ``<rule> := <true|false|string|number> if { <clause> ... }``
- boolean clauses:  ``a OP b``, ``not a OP b``, ``func(args)``, ``not func(args)``
- operators: ``== != in < > <= >=``
- terms: literals, ``input.a.b``, ``data.a.b``, integers, strings
- builtin predicates/functions: member, startswith, endswith, contains,
  concat, any_prefix, has_any, has_all, length
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.core.errors import PolicyDeniedError

logger = logging.getLogger(__name__)

POLICIES_DIR = Path(__file__).resolve().parents[3] / "policies"

_HEADER = re.compile(r"^([\w.]+)\s*(?::=\s*(.+?))?\s+if\s*\{\s*$")
_DEFAULT_RE = re.compile(r"^default\s+([\w.]+)\s*:=\s*(.+)\s*$")
_LITERAL_RE = re.compile(r'^(true|false|-?\d+|".*")\s*$')
_FUNC_CALL = re.compile(r"^([\w.]+)\s*\((.*)\)\s*$")
_OP_SPLIT = re.compile(r"\s*(==|!=|<=|>=|<|>|\bin\b)\s*")
_FIELD = re.compile(r"^(input|data)((?:\.[A-Za-z0-9_]+)+)$")


class ParseError(ValueError):
    pass


def _strip_comment(line: str) -> str:
    return line.split("#", 1)[0].strip()


def _parse_term(raw: str) -> Any:
    raw = raw.strip()
    if raw in ("true", "false"):
        return raw == "true"
    if re.fullmatch(r"-?\d+", raw):
        return int(raw)
    if raw.startswith('"') and raw.endswith('"'):
        return raw[1:-1]
    m = _FUNC_CALL.match(raw)
    if m:
        name, args = m.group(1), m.group(2)
        return (
            "call",
            name,
            [a.strip() for a in args.split(",")] if args.strip() else [],
        )
    m = _FIELD.match(raw)
    if m:
        scope = m.group(1)
        path = [p for p in m.group(2).split(".") if p]
        return (f"{scope}_field", path)
    raise ParseError(f"unsupported term: {raw}")


@dataclass
class Rule:
    """A named Rego rule. Repeated rule bodies (e.g. multiple ``reason := ...``
    blocks) are kept as disjuncts, each pairing a value with its conditions."""

    name: str
    default: Any | None = None
    bodies: list[tuple[Any | None, list[list[tuple]]]] = field(default_factory=list)


def _parse_condition(raw: str) -> tuple[bool, tuple]:
    """Return (negated, condition-tuple)."""
    raw = raw.strip()
    neg = False
    if raw.startswith("not "):
        neg = True
        raw = raw[4:].strip()
    parts = _OP_SPLIT.split(raw)
    if len(parts) == 1:  # bare predicate such as member(...)
        call = _parse_term(raw)
        if call[0] != "call":
            raise ParseError(f"expected predicate: {raw}")
        return neg, call
    if len(parts) != 3:
        raise ParseError(f"cannot parse condition: {raw}")
    lhs, op, rhs = parts
    if op == "in":  # `value in list`
        return neg, ("call", "_in", [lhs.strip(), rhs.strip()])
    return neg, (lhs.strip(), op, rhs.strip())


class RegoRules:
    def __init__(self, package: str, rules: dict[str, Rule]) -> None:
        self.package = package
        self.rules = rules

    @classmethod
    def parse(cls, source: str) -> RegoRules:
        rules: dict[str, Rule] = {}
        package = "main"
        current: Rule | None = None
        condition_buffer: list[tuple] = []
        for line in source.splitlines():
            line = _strip_comment(line)
            if not line:
                continue
            if line.startswith("package "):
                package = line.split(None, 1)[1].strip()
                continue
            if line.startswith("import "):
                continue
            if current is not None:
                if line == "}":
                    if condition_buffer:
                        value, conditions = current.bodies[-1]
                        current.bodies[-1] = (value, conditions + [condition_buffer])
                        condition_buffer = []
                    current = None
                    continue
                condition_buffer.append(_parse_condition(line))
                continue
            dm = _DEFAULT_RE.match(line)
            if dm:
                name = dm.group(1)
                rules.setdefault(name, Rule(name)).default = _parse_term(dm.group(2))
                continue
            hm = _HEADER.match(line)
            if hm:
                name = hm.group(1)
                rule = rules.setdefault(name, Rule(name))
                literal = (hm.group(2) or "").strip()
                if not literal:
                    rule.bodies.append((None, []))
                elif _LITERAL_RE.match(literal):
                    rule.bodies.append((_parse_term(literal), []))
                else:  # body rule whose value is derived from conditions
                    rule.bodies.append((_parse_term(literal), []))
                    condition_buffer.append(_parse_condition(literal))
                current = rule
                continue
            raise ParseError(f"cannot parse line: {line}")
        if current is not None:
            raise ParseError("unterminated rule body")
        return cls(package, rules)

    def evaluate(self, name: str, input_data: dict, data: dict) -> Any:
        rule = self.rules.get(name)
        if rule is None:
            raise KeyError(f"unknown rule {name}")
        for value, conditions in rule.bodies:
            for group in conditions:
                if all(self._eval_condition(c, input_data, data) for c in group):
                    return value if value is not None else True
        return rule.default if rule.default is not None else False

    def _resolve(self, term: Any, input_data: dict, data: dict) -> Any:
        if isinstance(term, tuple):
            kind, value = term[0], term[1]
            if kind == "input_field":
                node: Any = input_data
                for part in value:
                    if isinstance(node, dict):
                        node = node.get(part)
                    else:
                        node = None
                        break
                return node
            if kind == "data_field":
                node = data
                for part in value:
                    if isinstance(node, dict):
                        node = node.get(part)
                    else:
                        node = None
                        break
                return node
            if kind == "call":
                return self._builtin(value, term[2], input_data, data)
            raise ParseError(f"unsupported tuple term {term}")
        return term

    def _eval_condition(self, cond: tuple, input_data: dict, data: dict) -> bool:
        neg, condition = cond
        if condition[0] == "call":
            res = self._builtin(condition[1], condition[2], input_data, data)
            return not res if neg else bool(res)
        lhs, op, rhs = condition
        left = self._resolve(_parse_term(lhs), input_data, data)
        right = self._resolve(_parse_term(rhs), input_data, data)
        result = self._compare(left, op, right)
        return not result if neg else result

    @staticmethod
    def _compare(left: Any, op: str, right: Any) -> bool:
        if op == "==":
            return left == right
        if op == "!=":
            return left != right
        if op in ("<", ">", "<=", ">="):
            try:
                return {
                    "<": left < right,
                    ">": left > right,
                    "<=": left <= right,
                    ">=": left >= right,
                }[op]
            except TypeError:
                return False
        raise ParseError(f"unsupported op {op}")

    def _builtin(
        self, name: str, args_text: list[str], input_data: dict, data: dict
    ) -> Any:
        args = [self._resolve(_parse_term(a), input_data, data) for a in args_text]
        if name in ("member", "_in"):
            return args[0] in (args[1] or [])
        if name == "startswith":
            return str(args[0]).startswith(str(args[1]))
        if name == "endswith":
            return str(args[0]).endswith(str(args[1]))
        if name == "contains":
            return str(args[1]) in str(args[0])
        if name == "length":
            return len(args[0])
        if name == "concat":
            return str(args[1]).join(str(x) for x in (args[0] or []))
        if name == "any_prefix":
            return any(str(r).startswith(str(args[1])) for r in (args[0] or []))
        if name == "has_any":
            return bool(set(args[0] or []) & set(args[1] or []))
        if name == "has_all":
            return set(args[1] or []).issubset(set(args[0] or []))
        if name == "is_admin":
            roles = args[0] or []
            return "platform_admin" in roles or "org_admin" in roles
        if name == "permitted":
            module, permission, user_roles = args[0], args[1], args[2] or []
            roles_map = (
                data.get("jurisflow", {}).get("roles", {}).get("permissions", {}) or {}
            )
            required = roles_map.get(module, {}).get(permission) or []
            normalized = {str(r).split(".", 1)[-1] for r in user_roles}
            return bool(set(required) & normalized)
        if name == "agent_tool_allowed":
            agent_role, tool, agent_module = args[0], args[1], args[2]
            agent_tools = (
                data.get("jurisflow", {}).get("roles", {}).get("agent_tools", {}) or {}
            )
            mapping = (
                data.get("jurisflow", {}).get("roles", {}).get("agent_modules", {}) or {}
            )
            return arg_in(tool, agent_tools.get(agent_role, [])) and member_of(
                agent_module, mapping.get(agent_role, [])
            )
        if name == "sim_member":
            participants, agent = args[0] or [], args[1]
            return agent in participants
        if name == "phase_valid":
            phases = args[0] or []
            return args[1] in phases
        raise ParseError(f"unknown builtin {name}")


def arg_in(value: Any, collection: Any) -> bool:
    return value in (collection or [])


def member_of(value: Any, collection: Any) -> bool:
    return value in (collection or [])


@dataclass
class PolicyDecision:
    allow: bool
    reason: str
    policy: str
    version: str


class OPADecisionEngine:
    VERSION = "1.0.0"

    def __init__(
        self, policies_dir: Path = POLICIES_DIR, data_file: str | None = None
    ) -> None:
        self.policies_dir = policies_dir
        self.rego_files: dict[str, RegoRules] = {}
        self.data: dict[str, Any] = {}
        if data_file:
            self.data = json.loads(Path(data_file).read_text())
        self._load()

    def _load(self) -> None:
        for path in sorted(self.policies_dir.glob("*.rego")):
            try:
                self.rego_files[path.stem] = RegoRules.parse(path.read_text())
            except ParseError:
                logger.exception("Failed to parse policy %s", path.name)
                raise

    def decide(self, policy: str, input_data: dict) -> PolicyDecision:
        rules = self.rego_files.get(policy)
        if rules is None:
            return PolicyDecision(False, "unknown_policy", policy, self.VERSION)
        try:
            allow = bool(rules.evaluate("allow", input_data, self.data))
        except Exception:
            logger.exception("Policy %s evaluation error", policy)
            allow = False
        reason = "allowed" if allow else self._reason(rules, input_data)
        return PolicyDecision(allow, reason, policy, self.VERSION)

    def _reason(self, rules: RegoRules, input_data: dict) -> str:
        for name in ("reason",):
            if name in rules.rules:
                val = rules.evaluate(name, input_data, self.data)
                if isinstance(val, str):
                    return val
        return "denied_by_policy"

    def require(
        self, policy: str, input_data: dict, *, actor: str, action: str
    ) -> None:
        decision = self.decide(policy, input_data)
        if not decision.allow:
            raise PolicyDeniedError(
                f"policy `{decision.policy}` denied {action} for {actor}: {decision.reason}",
                code=f"{decision.policy}.{decision.reason}",
            )


class RemoteOPAClient:
    """Bridges to a full OPA server when JAIL_OPA_URL is configured (PRD §15.4)."""

    def __init__(self, url: str) -> None:
        import requests

        self._requests = requests
        self.url = url.rstrip("/")

    def decide(self, policy: str, input_data: dict) -> PolicyDecision:
        try:
            resp = self._requests.post(
                f"{self.url}/v1/data/jurisflow/{policy}",
                json={"input": input_data},
                timeout=5,
            )
            body = resp.json()
            allow = bool(body.get("result", {}).get("allow", False))
        except Exception:  # pragma: no cover
            logger.exception("Remote OPA unavailable")
            return PolicyDecision(False, "opa_unreachable", policy, "remote")
        reason = "allowed" if allow else "denied_by_policy"
        return PolicyDecision(allow, reason, policy, "remote")


@lru_cache(maxsize=1)
def get_engine() -> OPADecisionEngine:
    data_path = POLICIES_DIR / "data.json"
    if data_path.exists():
        return OPADecisionEngine(data_file=str(data_path))
    return OPADecisionEngine()
