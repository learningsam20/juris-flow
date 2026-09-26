# JurisLab Threat Model

Scope: the JurisLab monorepo (backend `/api/v1`, agents/MCP/A2A, policies, frontend,
DB/vector/storage adapters). Threat classes follow OWASP ASVS v4 tiers appropriate to a
development-tier deployment of an educational legal platform.

## Assets

| Asset | Protection goal |
|---|---|
| User accounts + session tokens | Integrity, confidentiality, rotation on compromise |
| Organization legal documents | Tenant-confidential; must never cross org boundaries |
| Agent message/tool traffic | CCI (confidentiality, integrity, availability) within a simulation |
| Policy decisions + audit log | Integrity and non-repudiation of allow/deny decisions |
| LLM prompt/response content | No prompt leakage, no unauthorized retrieval |
| Exported reports/case studies | Only role-permitted, only after disclaimer/citation checks |

## Trust boundaries

1. **Browser → API** — untrusted input. JWT on `Authorization`, CORS restricted, Pydantic validation.
2. **API → LLM/embedding/vector adapters** — local Ollama (trusted LAN) or GCP service accounts (Vertex).
3. **Agent → MCP tools** — every tool call must pass OPA default-deny.
4. **Agent → Agent (A2A)** — schema-validated and role/phase-authorized before delivery.
5. **Tenant boundary** — org scoping on every query (service-layer filters + `tenant.rego`).

## Threats & mitigations

| ID | Threat | Likelihood | Severity | Mitigation | Status |
|---|---|---|---|---|---|
| T1 | Stolen access token replay | Medium | High | 15-min access tokens; refresh rotation; logout invalidation; JWT validated on every request | Implemented |
| T2 | Privilege escalation via role tampering | Medium | High | Module/platform roles resolved from DB via `UserRole`, not from the JWT claims alone; Rego RBAC | Implemented |
| T3 | Cross-tenant document/search/simulation access | High | High | Org-scoped queries in services; `tenant.rego`; search filters by org metadata; test `other_org` 404/empty assertions | Implemented |
| T4 | Prompt injection via uploaded document | High | High | `scanner.py` heuristic isolation; flagged metadata; content never executed | Implemented (heuristic) |
| T5 | PII leakage in retrieval/exports | Medium | High | PII detection + redaction at ingestion; disclaimers; citations validated against allowed sources | Implemented |
| T6 | Unauthorized MCP tool execution | Medium | High | Default-deny `mcp.rego` gate before execution; every call audited | Implemented |
| T7 | A2A message spoofing / phase violation | Medium | Medium | A2A schema validation + `a2a.rego` sender/recipient/phase authz | Implemented |
| T8 | Unauthorized export (missing role / no citations) | Medium | Medium | `export.rego` artifact-type-aware denial; `enforce_export` normalization; role fixtures tested | Implemented |
| T9 | LLM hallucination presented as authority | High | High | Grounding instructions, citation validation, disclaimers, abstention fallbacks; eval gates (Faithfulness) | Implemented |
| T10 | Log injection / audit tampering | Low | Medium | JSON structured logs w/ correlation ID; immutable-ish append-only audit via `AnalyticsEvent` | Implemented |
| T11 | Brute-force login / credential stuffing | High | Medium | bcrypt + short-lived tokens | Partially (rate limiting deferred to proxy/P2) |
| T12 | Upload zip-bomb / oversized payload | Medium | Medium | `max_upload_mb=20`, type allow-list, malware-scan hook | Partial (scan is placeholder) |
| T13 | Exploitation of untyped Markdown in exports | Low | Medium | `bleach` sanitization on rendered Markdown; `.md`/`.pdf` via reportlab | Implemented |
| T14 | Secret leakage in repo | Medium | High | `.gitignore` for `.env`/keys; `.env.example` only; CI secret scan (planned) | Implemented |
| T15 | Dependency CVE | Medium | High | requirements with version floors; SBOM + SCA deferred to CI hardening | Partial |
| T16 | Denial of service on vector/LLM endpoints | Medium | Medium | Local adapters; explicit 503 on LLM outages | Partial |

## Controls by layer (PRD §15.3)

- **Input:** type/size validation, prompt-injection heuristic isolation, PII detection/redaction,
  jurisdiction/domain/role/ownership validation before processing.
- **Retrieval:** org/tenant + jurisdiction/domain metadata filters; sources labeled; non-authority
  sources not presented as controlling.
- **Agent:** grounding + role adherence + uncertainty disclosure in role prompts; no prompt/tool/CoT
  leakage instructions; abstention/clarification on insufficient facts.
- **Output:** Pydantic schemas; citation existence checks; disclaimers on simulations, reviews,
  case studies, and exports; draft-through-publish approval.
- **Human oversight:** draft unless published by `review.review_lead` / `sim.sim_professional`;
  immutable audit of source material, agent actions, policy decisions, interventions.

## Security-critical code paths

- `backend/app/core/deps.py` — `require_module()`, `enforce_export()` (check normalization).
- `backend/app/opa/engine.py` + `policies/*.rego` — single decision point; `parents[3]` resolves policy dir.
- `backend/app/mcp/gateway.py` — OPA-before-tool-execution.
- `backend/app/ingestion/scanner.py` — prompt-injection / PII guardrails.
- `backend/app/services/*{auth,simulation,document,hub}` — tenant-scoped queries.
- `backend/app/main.py` — CORS, exception handlers (403 policy-denied with reason), policy self-check.

## Validation coverage

Backend pytest suite (64 tests) exercises: auth sessions, RBAC / cross-tenant isolation,
policy decision matrix (40 Rego cases), simulation lifecycle incl. finished-sim rejections
and the LLM-as-judge winner verdict, export role+check enforcement, knowledge search + Ask AI
isolation. See `docs/acceptance.md`.

## Known gaps (deferred / P2)

- **Multi-instance rate limiting** — in-memory sliding window today (per-process); move to
  Redis or the WAF/proxy for horizontally scaled deployments.
- **Real malware scanning** (currently a placeholder hook).
- **Keycloak OIDC** (form auth enabled; Keycloak adapter stubbed).
- **CSP/secure-header injection for the frontend production server** (nginx config).
- **Encryption at rest for PostgreSQL; signed-URLs document access** (production config).