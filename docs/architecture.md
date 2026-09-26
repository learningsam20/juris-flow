# JurisFlow Architecture

JurisFlow is a multi-agent legal education and document-analysis platform. It is a
stateless API backend (FastAPI + LangGraph), an OPA/Rego-policy-guarded agent/tool
layer (MCP + A2A), adapter-based AI infrastructure (Ollama / Vertex AI), a React
frontend, and a local evaluation pipeline (DeepEval + promptfoo + Rego tests).

```mermaid
flowchart TB
  subgraph Client
    UI[React + MUI frontend<br/>Vite dev server :5601]
  end

  subgraph Backend[FastAPI backend :5600]
    API1_API[API v1 routes<br/>auth users scenarios simulations<br/>documents reviews knowledge analytics exports]
    AUTH[Auth: JWT access/refresh<br/>bcrypt · RBAC guards]
    OPA[OPA/Rego engine<br/>rbac · tenant · mcp · a2a · export]
    MCP[MCP gateway<br/>tool registry + audit]
    A2A[A2A messaging<br/>schema + authz]
    GRAPH[LangGraph simulation graph<br/>Orchestrator · Plaintiff · Defendant<br/>Judge · Informer · Witness]
    HUB[Knowledge Hub services<br/>ingestion · hybrid search · collections]
    REVIEW[Review Analyst<br/>extraction · findings · report]
    EXPORT[Exports<br/>Markdown / PDF + disclaimers]
    ANALYTICS[Analytics · telemetry · audit]
  end

  subgraph Infra[Adapters (JAIL_-driven)]
    LLM[LLM: Ollama or Vertex AI Model Garden]
    EMB[Embeddings: all-minilm / text-embedding]
    VEC[Vector: Qdrant embedded/local or Vertex]
    DB[(SQLite dev / PostgreSQL prod)]
    STORE[(Local storage / GCS)]
    OLLAMA[Ollama :11434]
  end

  subgraph Eval[Evaluation]
    PVAL[policy tests · backend pytest · ruff · mypy]
    DEV[DeepEval RAG metrics]
    PF[promptfoo regression]
  end

  UI -- "/api/v1 (proxied)" --> API1_API
  API1_API --> AUTH
  API1_API --> OPA
  API1_API --> MCP
  API1_API --> A2A
  API1_API --> GRAPH
  API1_API --> HUB
  API1_API --> REVIEW
  API1_API --> EXPORT
  API1_API --> ANALYTICS

  GRAPH --> MCP
  GRAPH --> A2A
  MCP --> OPA
  A2A --> OPA
  API1_API --> OPA

  LLM --> OLLAMA
  EMB --> OLLAMA
  HUB --> EMB
  HUB --> VEC
  REVIEW --> LLM
  GRAPH --> LLM
  EXPORT --> DB
  REVIEW --> DB
  HUB --> DB
  API1_API --> DB
  STORE --> DB

  PVAL -. CI .-> API1_API
  DEV -. make eval .-> API1_API
  PF -. make eval .-> OLLAMA
```

## Runtime topology

- **API** — one process (`uvicorn app.main:app`), stateless except the SQLite DB,
  embedded Qdrant path, and in-memory audit/telemetry. Multi-worker safe with
  PostgreSQL + local/store-backed Qdrant.
- **Frontend** — Vite dev server proxies `/api` to `:5600`; production build served
  via nginx (see `frontend/Dockerfile`).
- **AI adapters** — never called with a silent fallback. A configured provider that
  is unavailable fails the affected operation explicitly (`LLMUnavailableError` 503).
- **Policy engine** — Rego files in `policies/` are the single authorization point
  for RBAC, tenant isolation, MCP tool calls, A2A messages, and exports. Every
  `decide()` emits a decision audit event. Startup runs `policy_selfcheck()`.

## Key flows

1. **Review:** upload (PDF/DOCX/TXT/MD) → input guardrails (`scanner.py`: prompt-injection
   isolation, PII redaction) → chunk/embed/index (org/jurisdiction/domain metadata) →
   Review Analyst extraction → findings + grounded citations → Markdown report (draft) →
   publish by `review.review_lead` → export .md/.pdf.
2. **Simulation:** scenario CRUD + versioning → start → LangGraph drives turns with A2A
   messages; agents retrieve only authorized documents via the MCP gateway (OPA-gated);
   human controls pause/resume/inject/clarify/steer; on completion a cited **case study**
   is generated; export requires `sim.sim_professional`.
3. **Knowledge Hub:** hybrid search (semantic + keyword) with tenant isolation, document
   detail with linked scenarios/reviews, curated collections and teaching packs.

## Configuration surface

All runtime behavior is `.env`-driven with the `JAIL_` prefix (see `.env.example` and
`backend/app/config.py`): `llm_provider`, `embedding_provider`, `vector_provider`,
`database_url`, `storage_backend`, `auth_provider`, token lifetimes, limits
(max upload MB, chunk size, turn limits), and moderation/review thresholds.

## Repository map

| Path | Purpose |
|---|---|
| `backend/app` | FastAPI app: API v1, agents (LangGraph), review, hub, ingestion, exports, OPA engine, MCP/A2A, core (logging/errors/telemetry) |
| `policies/` | OPA/Rego policies + decision data + `policies/tests` (25-case matrix) |
| `frontend/` | React + Vite + MUI + Zustand |
| `eval/` | DeepEval + promptfoo suites (`make eval`) |
| `scripts/` | start/stop/kill-remake + rego test runner |
| `infra/` | (deferred) Docker/K8s manifests |
| `docs/` | Architecture, threat model, acceptance, OpenAPI contract |