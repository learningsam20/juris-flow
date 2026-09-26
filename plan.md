# JurisFlow — Implementation Plan

> Living plan. Kept in sync with `prd.md`. Statuses: `pending` → `in_progress` → `completed` / `cancelled`.
> Updated after every implementation step.

## Decisions (from design review)

| Area | Decision | Rationale |
| --- | --- | --- |
| Auth | Form-based JWT (bcrypt + short-lived access + refresh rotation), behind a provider interface | PRD §6.1 P1 allows Keycloak OR form-based; adapter keeps Keycloak addable |
| LLM | `.env`-driven adapter: `Ollama` (default) or `Vertex AI Model Garden`; **no fallback** — explicit failure | PRD §7.1, §10.2, §15.1 |
| Vector store | `.env`-driven adapter: `Qdrant` (embedded local in dev) or `Vertex AI Vector Search` | PRD §7.1, §15.8 |
| DB | SQLite (dev) / PostgreSQL (prod) — SQLAlchemy 2 + Alembic | PRD §7.1, §15.8 |
| Frontend | React + Vite (JS/JSX), Material UI, Zustand, dark/light tokens | PRD §7.1 |
| Agents | LangGraph nodes; A2A structured messaging; MCP tool registry gated by OPA/Rego | PRD §8, §15.4 |
| Policy | OPA/Rego embedded decision engine; versioned with code; tested in CI | PRD §15.4 |
| Observability | JSON structured logs + correlation IDs; OTel traces, metrics, and logs exported via OTLP (additive to console) | PRD §7.3 |
| Eval | DeepEval (pytest) + promptfoo + Rego tests; release thresholds per §15.2.2 | PRD §15.2 |

**Monorepo layout**

```
legalassistant/
├── plan.md, prd.md, README.md, .env.example, .gitignore, Makefile, docker-compose.yml
├── backend/         FastAPI + LangGraph + SQLAlchemy + adapters
├── frontend/        React + Vite + MUI + Zustand
├── policies/        OPA/Rego policies (+ tests)
├── eval/            DeepEval + promptfoo suites
├── scripts/         start.sh / stop.sh / kill_all_and_start.sh
├── k8s/             Kubernetes manifests (namespace, config, api/agent/telemetry)
└── .github/         CI workflow
```

---

## Phase 1 — Repository Foundation
- [x] Root artifacts (README, .env.example, Makefile, docker-compose, .gitignore, CI workflow)
- [x] `git init` + initial commit + branch policy (single default branch, PR-based CI)

**Status: completed** (`git init -b main`, initial commit `5039c24`, branch policy in `CONTRIBUTING.md`)

## Phase 2 — Backend Foundation (PRD §7, §9)
- [x] FastAPI app factory + pydantic-settings `.env` config
- [x] JSON structured logging with correlation IDs; error handling with LLM-unavailable states
- [x] SQLAlchemy models for all PRD §9 entities (User, Organization, UserRole, Scenario, ScenarioVersion, LegalDocument, Simulation, SimulationTurn, CaseStudy, DocumentReview, AnalyticsEvent + annotations/collections)
- [x] SQLite dev session + Alembic migration scaffolding + seed data
- [x] `/health` + readiness, CORS, middleware

**Status: completed** (Alembic scaffolding deferred in favor of `Base.metadata.create_all` for the MVP; seed data verified)

## Phase 3 — Auth & RBAC (PRD §6.1, §7.2)
- [x] bcrypt hashing, short-lived JWT access + refresh-rotation endpoint
- [x] Auth-provider interface (form-first; Keycloak-ready)
- [x] Platform + module-level roles; org/tenant isolation
- [x] Dependency injection guards for APIs & UI routes; CCR audit events (login, changes, runs, exports)
- [x] Rate limiting on auth, upload, simulation, review, export endpoints (sliding-window, in-memory)

**Status: completed** (backend guards + audit wired; sliding-window rate limiter with 9 scopes; config flag
`JAIL_RATE_LIMIT_ENABLED`; 429 responses covered by tests)

## Phase 4 — OPA Policy Engine (PRD §15.4)
- [x] Rego: RBAC/module authorization, tenant isolation, MCP tool authz (default-deny), A2A message authz, export/publication control
- [x] Embedded Rego decision engine with allow/deny + reason codes + decision audit events
- [x] Rego policy tests (CI)

**Status: completed** (embedded engine + 5 policy packs; self-check passes at startup; 25-case Rego matrix runs in CI)

## Phase 5 — LLM / Embeddings / Vector Adapters (PRD §7.1)
- [x] LLM provider interface: Ollama + Vertex AI Model Garden; explicit no-fallback failures
- [x] Embedding API: Ollama embedding (all-minilm) + Vertex text-embedding
- [x] Vector store interface: Qdrant (embedded local) + Vertex AI Vector Search; metadata (org/jurisdiction/domain/date)
- [x] Model registry with per-environment selection

**Status: completed** (live smoke-tested against Ollama + embedded Qdrant)

## Phase 6 — Document Ingestion & Review (PRD §5.2, §6.5, §8.6)
- [x] Upload (PDF/DOCX/TXT/MD): type/size validation, OCR hook, malware-placeholder, PII detection, prompt-injection scan
- [x] Chunking, embedding, indexing with org/jurisdiction/domain metadata
- [x] Review Analyst Agent: clause/entity extraction, risk/obligation highlighting, balance score, plain-language, grounded Q&A
- [x] Review report generation (Markdown) + disclaimers + draft/publish approval; export .md/.pdf
- [x] Review templates (customizable by document type; focus-clause filtering) + collaborative annotations

**Status: completed** (templates CRUD + `template_id` on review run with focus filtering; seeded defaults;
annotation add/list/resolve/delete on review reports with tenant isolation; Tesseract OCR + pypdfium2 fully
integrated and active for scanned image-only PDFs)

## Phase 7 — Knowledge Hub (PRD §5.3, §6.7)
- [x] KB ingestion + metadata (jurisdiction, domain, type, dates, version)
- [x] Hybrid search (semantic + keyword) + filters; document detail with links
- [x] Curated collections / teaching packs
- [x] Cluster summaries + AI-augmented insights (P2 baseline)

**Status: completed** (search verified live; collections + teaching packs wired)

## Phase 8 — JurisFlow Sim (PRD §5.1, §6.3–6.6, §8.1–8.5)
- [x] Scenario CRUD + versioning, fact pattern editor, doc linkage, params, tags
- [x] LangGraph graph: Orchestrator/Plaintiff/Defendant/Judge (+Informer/Witness)
- [x] A2A structured messaging (from/to/message_type/payload/citations) with authz
- [x] Tools: jurisdiction-aware retriever, citation formatter, fact validator, issue extractor, outcome template
- [x] MCP tool registry + OPA gate + audit
- [x] Human-in-the-loop: pause/resume, inject facts, clarification, steer focus
- [x] Case study generation on completion + export .md/.pdf ($218)

**Status: completed** (full sim run verified: completes → case study generated; scenario versioning = latest-version model)

## Phase 9 — Analytics & Telemetry (PRD §6.8, §7.3)
- [x] AnalyticsEvent capture across modules
- [x] Usage dashboards: simulations run, reviews performed, top searches, exports
- [x] Agent telemetry: turns, tool calls, retrieval hits; latency metrics; OTel traces + metrics + logs (OTLP)

**Status: completed**

## Phase 10 — API Surface (PRD §6, §7.4)
- [x] v1 routes: /auth, /users, /orgs, /scenarios, /simulations, /documents, /reviews, /knowledge, /analytics, /exports
- [x] OAuth/OpenAPI; enforces authz on all endpoints; Pydantic validation; disclaimers in outputs

**Status: completed** (orgs folded into users/tenant scoping; endpoint-level smoke-tested end-to-end)

## Phase 11 — Frontend Foundation (PRD §6.2, §15.6)
- [x] Vite + React + MUI; Zustand auth store + route guards
- [x] Left-side nav (Dashboard, Sim, Review, Hub, Analytics, Settings) + top-bar profile/logout
- [x] Auth/role guards; loading/error states; login + register
- [x] WCAG 2.1 AA baseline (keyboard, focus, contrast, labels)

**Status: completed** (frontend WCAG 2.1 AA baseline: dark/light toggle with localStorage persistence and system `prefers-color-scheme` fallback, focus-visible outlines, skip-link, ARIA labels on all interactive elements, keyboard-navigable navigation, minimum 44px touch targets)

## Phase 12 — Frontend Modules
- [x] Dashboard (health); Sim (scenario mgmt + run + transcript + case-study viewer)
- [x] Review (upload-driven reviews + findings), Hub (upload + search), Analytics, Settings

**Status: completed** (working screens wired to the live API; live-transcript and reported-counts
refinements optional)

## Phase 13 — Evaluation & Quality (PRD §15.2, §15.7)
- [x] DeepEval suites: retrieval, document review, simulation, safety/reliability
- [x] promptfoo suites: prompt-injection, output regression, disclaimer/policy asserts
- [x] pytest suite (backend 55 + policy 40) with ruff + mypy gates (all clean)
- [x] CI: lint, format, type-check, backend tests, Rego tests, frontend build validation, dependency vulnerability scan, SBOM generation, eval static validation

**Status: completed** (DeepEval/promptfoo run against the live stack via `make eval`; ESLint/Vitest/axe added and now in CI; CI includes pip-audit + cyclonedx-bom SBOM generation + npm audit, with Dependabot configured for pip/npm/actions)

## Phase 14 — Packaging & Deployment (PRD §11)
- [x] backend/Dockerfile, frontend/Dockerfile, docker-compose (ollama/qdrant as profiles)
- [x] Kubernetes manifests (API, agent runtime, telemetry)
- [x] SBOM + dependency lockfiles

**Status: completed** (Docker + compose delivered; K8s manifests in `k8s/` (namespace, config, secret, PVC, api/agent/telemetry deployments, services, HPA, ingress, hardening quota/PDB), SBOM in `docs/sbom.json`, lockfile in `backend/requirements-lock.txt`; CI integrates SBOM generation, pip-audit, npm audit, and Dependabot keeps both ecosystems updated)

## Phase 15 — Operations Scripts
- [x] `scripts/start.sh`, `scripts/stop.sh`, `scripts/kill_all_and_start.sh`, Makefile targets

**Status: completed** (start/stop/restart/test/lint/typecheck/rego/docker-up/docker-down/eval/sbom/lock/scan)

## Phase 16 — Docs & Acceptance Validation (PRD §12, §15.8)
- [x] README walkthrough (setup, LLM/DB/vector/auth config, workflows, assumptions, limitations)
- [x] Architecture diagram (Mermaid), OpenAPI contract, threat model, eval guide
- [x] Final check against §12 acceptance criteria and §15.8 delivery gates

**Status: completed** (`docs/architecture.md`, `docs/threat-model.md`, `docs/acceptance.md`,
`docs/openapi.json`, `eval/README.md`; GAP items tracked as P2 in the threat model + acceptance docs)