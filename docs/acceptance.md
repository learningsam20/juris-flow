# JurisFlow Acceptance Walkthrough

Validates the implementation against PRD §12 (system-level acceptance) and §15.8
(delivery acceptance). Evidence = files, endpoints, Makefile targets, and the test
suites. Run everything below from the repo root with `.venv` active.

```bash
make lint          # ruff check + format   → "All checks passed!"
make typecheck     # mypy app              → "Success: no issues found"
make test          # backend pytest + Rego → 44 + 25 passed
(cd frontend && npm run build)   # Vite build OK (also runs in CI)
```

## §12 Acceptance Criteria — status

| Criterion | Status | Evidence |
|---|---|---|
| Users log in with assigned roles | Met | `POST /api/v1/auth/register|login|refresh`; `tests/test_auth.py` (session + refresh rotation + logout) |
| Module access restricted by module-level roles | Met | `require_module()` in `app/core/deps.py`; `rbac.rego`; `tests/test_rbac.py` (403 on insufficient module role) |
| Scenarios create/edit/version | Met | `POST|GET|PUT /scenarios`, versioning = latest-version model; `tests/test_scenarios.py` |
| Simulation starts from a scenario | Met | `POST /simulations {scenario_id}`; `tests/test_simulations.py` |
| ≥ Plaintiff, Defendant, Judge agents | Met | `MIN_CORE_AGENTS` in `app/agents`; sim run verified to completion |
| Pause / inject facts / resume | Met | `POST …/pause|resume|inject_fact`; HITL + finished-sim rejection tests |
| Agent messages include citations | Met | citations aggregated into case study; MCP/A2A authz tested |
| Case study Markdown generated, viewable/downloadable | Met | `GET …/case_study`, `POST …/export`, `GET /exports/case_studies/{id}`; `test_case_study_export` |
| Upload legal documents | Met | `POST /documents/upload` (PDF/DOCX/TXT/MD); `test_documents.py` |
| Clause extraction | Met | Review Analyst: `app/review/extractor.py`; 4 finding families |
| Risk/obligation highlights | Met | severity + obligation_load + balance_score in findings (API/export) |
| Plain-language summaries | Met | `plain_language` per finding; `contains_plain_language` feeds export policy |
| Review report Markdown viewable/downloadable | Met | `GET /reviews/{id}/report`, `GET /exports/reviews/{id}`; `test_review_report_export` |
| Search and filter documents | Met | `POST /knowledge/search` (semantic + keyword, org-scoped); `test_knowledge.py` |
| Detail view: text, metadata, linked sims/reviews | Met | `GET /documents/{id}/detail` → `linked.{reviews,scenarios,simulations}` |
| Dashboards show usage metrics | Met | `GET /analytics/dashboard`; `test_ops.py` |
| Agent telemetry visible | Partial–Met | `GET /analytics/events` + dashboard turns/tool calls; not yet surfaced in the frontend |
| All endpoints enforce authn/authz | Met | default-deny OPA + guards; policy matrix 25 cases |
| Audit logs capture key actions | Met | `AnalyticsEvent` + JSON structured logs with correlation IDs |
| No critical vulns in standard scan | GAP | No scanning CI step yet (§15.8/SCA deferred); see threat model gaps |
| Lint/format/typecheck pass in CI | Met | `.github/workflows/ci.yml` runs ruff, mypy, tests, Rego, Vite build |
| Min test coverage thresholds | Partial | Suites exist (44 backend + 25 policy); numeric coverage-gate not enforced in CI |
| UI component library + a11y baseline | Partial | MUI component library in use; WCAG AA pass not yet completed (deferred) |
| Dark/light theme toggle | GAP | Deferred to P2 (single light theme implemented) |

## §15.8 Delivery Acceptance — status

| Criterion | Status | Evidence |
|---|---|---|
| README configures LLM/DB/vector/auth/storage without undocumented steps | Met | `.env.example` + `README.md`; adapters selected purely by `JAIL_*` |
| Dev runs on SQLite + embedded Qdrant (or local equivalent) | Met | Defaults in `backend/app/config.py`; smoke-tested live |
| Production supports PostgreSQL + GCS + Vertex Vector Search/Qdrant | Met (config) | `database_url`, `storage_backend=gcs`, `vector_provider=vertex` prepared; not yet exercised end-to-end |
| Review workflow: ingest → analyze → cited report | Met | Verified via `test_reviews.py` + export tests (grounded citations) |
| Sim workflow: scenario → authorized A2A/MCP → cited case study | Met | `test_simulations.py` (completes → case study with citations) |
| Policy-denied requests blocked and logged | Met | OPA reason codes + audit; policy matrix 100% pass |
| Unauthorized MCP calls never reach the tool | Met | Default-deny `mcp.rego` gate verified via policy tests |
| Eval/security/accessibility reproducible locally + CI | Partial | `make eval` local (DeepEval + promptfoo + Rego); CI runs Rego + pytest + build; security/a11y suites deferred |
| Clear non-advice disclosure at decision points | Met | Disclaimers on simulations, reviews, case studies, exports; abstention language in prompts |

## Workflow smoke run (both primary flows)

**JurisFlow Review**
```
POST /auth/register {email,password,organization_name} → token
POST /documents/upload  (multipart file)        → {id, status}
POST /reviews {document_id}                     → {job_id}
GET  /reviews/jobs/{job_id}                     → completed
GET  /reviews/{id}                              → findings (severity, quote, plain_language)
GET  /reviews/{id}/report                       → Markdown report
```

**JurisFlow Sim**
```
POST /scenarios {title, fact_pattern, jurisdiction, domain, focus_areas}
POST /simulations {scenario_id}                 → {id,...}
POST /simulations/{id}/advance  (loop to completed)
GET  /simulations/{id}                          → transcript (agent_role, text, citations)
GET  /simulations/{id}/case_study               → Markdown case study
POST /simulations/{id}/export                   → export record → GET /exports/case_studies/{id}
```

## Gates before a release is considered "acceptable"

1. `make lint` + `make typecheck` + `make test` all green.
2. Policy matrix 100%; authz default-deny enforced.
3. Both primary workflows produce cited Markdown with disclaimers.
4. Eval thresholds (DeepEval ≥0.5 relevancy/faithfulness, promptfoo assertions) pass against the
   pinned model (see `eval/README.md`).
5. Remaining GAP items above (rate limiting, scans, WCAG/dark-mode, provider production exercise)
   are explicitly tracked as P2 — see `plan.md` and `docs/threat-model.md`.