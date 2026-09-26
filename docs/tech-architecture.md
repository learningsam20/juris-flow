# JurisFlow — Tech Architecture

Hardened choices for an enterprise AI legal stack: **private where it matters**,
**swappable where it scales**, **policy-first everywhere**.

## System shape

```
React UI ──► FastAPI ──► OPA/Rego (default deny)
                │
                ├── Knowledge Hub ──► Qdrant
                ├── Grounded Review ──► KM confirm
                ├── LangGraph fleet ──► MCP tools (OPA-gated)
                │     Orchestrator · Policy Reviewer · Plaintiff · Defendant
                │     Judge · Informer · Witness
                └── edge-tts ──► overview + hearing MP3s
                │
                └── LLM adapters (per use-case)
                      ├── Ollama      local / private / cost
                      ├── OpenRouter  stronger cloud models
                      └── Vertex      GCP optional
```

## Tech bets

| Rationale | Choice | Not selected |
|---|---|---|
| No lock-in · private vs cloud | Ollama + OpenRouter (+ Vertex optional) | Single-vendor LLM |
| HITL state · multi-agent graph | LangGraph | Ad-hoc prompt chains |
| Org-filtered vectors | Qdrant | Chroma |
| Default-deny tenancy & tools | OPA / Rego | App-only RBAC |
| Multi-voice · unbounded narration | edge-tts | Cloud TTS lock-in |
| Ship FOSS · thin meta store | FastAPI · React · SQLite→Postgres | Heavyweight CLM suite day one |

## LLM routing

| Use case | Prefer | Why |
|---|---|---|
| Sim turns / Ask AI on sensitive KM | Ollama | Data stays local |
| Harder reasoning / judge verdict | OpenRouter (or Vertex) | Stronger models on demand |
| Embeddings | Ollama `all-minilm` (dev) | Cheap · fast · offline |
| Training audio | edge-tts | Distinct voices · no quota wall |

Configured via `JAIL_LLM_PROVIDER` / model overrides — **unavailable provider fails loud** (no silent fallback).

## Agent fleet

| Agent | Role |
|---|---|
| Orchestrator | Turn order · phase · budget |
| Policy Reviewer | Contract/policy audit · KM-grounded findings · risk feed |
| Plaintiff / Defendant | Adversarial argument · citations via MCP |
| Judge | Inquiry · LLM-as-judge verdict |
| Informer / Witness | Scenario evidence injection |

HITL: pause · resume · inject fact · steer · clarify.

## Security & tenancy

- Rego packs: `rbac` · `tenant` · `mcp` · `a2a` · `export`
- Upload guardrails: injection quarantine · PII redaction hooks
- Audit: structured logs + analytics events
- Exports: educational disclaimer mandatory

## Eval & quality (near-term)

- DeepEval RAG / faithfulness metrics (`make eval`)
- promptfoo regression
- Rego policy matrix (25 cases)
- Roadmap: DeepEvals in the trust loop · AI watermarking · HITL repair of reviews

## Related

- [`docs/architecture.md`](./architecture.md) — component topology · flows · config
- [`docs/tech-architecture.md`](./tech-architecture.md) — tech bets · LLM routing · agents
- [`docs/proposition.md`](./proposition.md) — presentation notes · Showcase link
- Showcase deck — `/#/showcase` or `frontend/public/showcase/index.html`
