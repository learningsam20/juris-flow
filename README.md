# JurisFlow — Educational Legal Simulation & Document Review Platform

Multi-agent legal simulation, grounded document review, and a knowledge hub with
OPA/Rego-enforced authorization. **Educational only — nothing here is legal advice.**

## Quick start (local dev)

Prerequisites: Python 3.14, Node 20+ (for the frontend), [Ollama](https://ollama.com) running
with a chat model (`llama3.2:latest` default, `gemma4:latest` for Ask AI) and an embedding
model (`all-minilm`).

```bash
make install                 # create .venv + install backend deps
make seed                    # seed admin@jurisflow.dev / ChangeMe#2026 + sample org/scenario/doc
make start                   # backend on :5600 (+ Vite frontend on :5601 when built)
open http://127.0.0.1:5600/api/v1/health
```

## Configuration

All configuration is `.env`-driven with the `JAIL_` prefix
(copy `.env.example` → `backend/.env`). Key settings:

| Area | Default | Notes |
| --- | --- | --- |
| LLM | Ollama `llama3.2:latest` | `JAIL_ASK_LLM_MODEL=gemma4:latest` for grounded Q&A; `JAIL_LLM_PROVIDER=vertex` for GenAI; **no fallback** |
| Embeddings | Ollama `all-minilm` (384d) | `JAIL_EMBEDDING_PROVIDER=vertex` |
| Vector store | Qdrant embedded local | `JAIL_VECTOR_PROVIDER=vertex` or `JAIL_QDRANT_URL` for a server |
| DB | SQLite `data/jurisflow.db` | `JAIL_DATABASE_URL` for Postgres |
| Policy | Embedded OPA engine | `JAIL_OPA_URL` to use a real OPA server |

## Workflows

- **Simulations**: scenario → shared fact pattern → `POST /api/v1/simulations` runs the
  LangGraph orchestrator (Plaintiff/Defendant/Judge ± Informer/Witness). Human-in-the-loop:
  pause/resume, inject facts, ask for clarification, steer focus. After N litigant exchanges
  the LLM-as-judge rules on the winner (`JAIL_SIM_JUDGE_EFFORT`, `JAIL_SIM_JUDGE_MAX_ROUNDS`).
  Case study generated on completion and exportable as Markdown.
- **Review**: upload a document (PDF/DOCX/TXT/MD; scanned image PDFs are OCR'd via Tesseract)
  → chunked, embedded, indexed → review job extracts clauses/risk, produces a report, grounded
  Q&A over the document, publish/export.
- **Knowledge hub**: hybrid semantic + keyword search with org/jurisdiction/domain filters,
  curated collections and teaching packs, AI-augmented insights, and "Ask AI" grounded Q&A
  (dedicated `JAIL_ASK_LLM_MODEL`, low temperature, citations to the source passages).
- **Analytics**: usage KPIs (simulations, reviews, searches, exports) + agent telemetry.

## Auth & Authorization

Form-based registration/login with short-lived JWT access + refresh rotation. Role model:
platform roles (`org_admin`, `platform_admin`, `billing_admin`) and module roles
(`sim.sim_educator`, `dashboard.reviewer`, …). Every operation (including MCP tool calls,
A2A messages, and exports) is authorized by the OPA/Rego policy packs in `policies/` —
default deny.

## Repo layout

```
backend/     FastAPI + LangGraph + SQLAlchemy + providers (Ollama/Vertex/Qdrant)
frontend/    React + Vite + MUI + Zustand
policies/    OPA/Rego authorization policies (+ data + tests)
eval/        DeepEval + promptfoo suites
scripts/     start.sh / stop.sh / kill_all_and_start.sh
infra/       Docker + Kubernetes manifests
.github/     CI workflows
docs/        requirements, architecture, threat model, acceptance, OpenAPI
```

## Docs

- `docs/architecture.md` — component + runtime topology (Mermaid), key flows, config surface
- `docs/threat-model.md` — assets, trust boundaries, threats ⇄ mitigations, known gaps
- `docs/acceptance.md` — walkthrough against PRD §12 / §15.8 acceptance criteria
- `docs/openapi.json` — generated OpenAPI contract (44 paths) for the `/api/v1` surface
- `eval/README.md` — evaluation guide and reproducible `make eval` commands

## Verification

```bash
make test          # backend pytest + rego policy tests
make lint          # ruff
make typecheck     # mypy
make eval          # DeepEval + promptfoo (requires live API + Ollama)
```

## Assumptions & limitations

- Local Ollama latency is hardware-bound; simulations on small models can take seconds
  per turn and occasional empty responses degrade (not fail) a single turn.
- OCR is fully integrated (Tesseract + pypdfium2 for image-only PDFs); malware scanning is
  still a placeholder hook (see PRD §5.2).
- Auth/upload/simulation/review/export endpoints are rate-limited via an in-memory
  sliding window (`JAIL_RATE_LIMIT_ENABLED`); move to Redis or the edge for multi-instance.
- SQLite is for dev only; Postgres is the production target (see docker-compose).

---
JurisFlow output is **educational and informational, not legal advice**.