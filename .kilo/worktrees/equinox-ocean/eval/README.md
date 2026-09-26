# Eval scaffolding

Two complementary suites, both exercised via `make eval` (from repo root):

- **`deepeval/`** — RAG/Legal-answer quality metrics (`AnswerRelevancy`, `Faithfulness`)
  over the live JurisLab knowledge base. Each test registers a throwaway org,
  hits `POST /api/v1/knowledge/search` for retrieval context, generates an answer
  through the local model, and asserts the metrics clear configurable thresholds.

- **`promptfoo/`** — prompt regression suite for the local model. Deterministic
  string assertions (disclaimer present, no unqualified guarantees, names a real
  dispute mechanism). No live backend required; only Ollama on `:11434`.

## Prerequisites

- JurisLab backend running on `:5273` (`make start`) — required for DeepEval only.
- A local Ollama model reachable at `:11434` (default `granite4.2:8b`).
- Node 22 (promptfoo runs via `npx`).

## Run

```bash
make eval            # runs both suites
make -C eval deepeval      # RAG metrics only
make -C eval promptfoo     # prompt regression only
```

## Configuration

| Env var | Default | Purpose |
|---|---|---|
| `JAIL_API_BASE` | `http://localhost:5273/api/v1` | DeepEval API base |
| `JAIL_OLLAMA_API` | `http://localhost:11434` | Ollama base URL |
| `JAIL_OLLAMA_MODEL` | `granite4.2:8b` | Model used as judge/answerer |

DeepEval's judge metrics read `OPENAI_BASE_URL`/`OPENAI_API_KEY`/`MODEL`
(points at the Ollama OpenAI-compatible endpoint).

## Adding cases

- DeepEval: add questions to `deepeval/tests/test_rag.py#QUESTIONS`.
- promptfoo: add a `- vars: { question, description }` block to `promptfoo/promptfooconfig.yaml`.

## Thresholds

`AnswerRelevancy ≥ 0.5`, `Faithfulness ≥ 0.5`. When swapping judge models,
raise/lower these in `deepeval/tests/test_rag.py#THRESHOLDS` deliberately and
record the change in commit history.