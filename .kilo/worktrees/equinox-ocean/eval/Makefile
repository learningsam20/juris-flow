# Eval scaffolding — DeepEval (RAG/LLM metrics) + promptfoo (prompt regression).
# Root `make eval` delegates here.

BACKEND ?= ..
VENV ?= ../.venv/bin/python

OLLAMA_API ?= http://localhost:11434
OLLAMA_MODEL ?= granite4.2:8b

# DeepEval judge wiring (OpenAI-compatible Ollama endpoint).
export OPENAI_BASE_URL ?= $(OLLAMA_API)/v1
export OPENAI_API_KEY ?= ollama

.PHONY: help run deepeval deepeval-install promptfoo promptfoo-install requirements

help:
	@echo "Targets: run (deepeval + promptfoo), deepeval, promptfoo, install"

requirements:
	$(VENV) -m pip install -r ../backend/requirements-dev.txt -r deepeval/requirements.txt

run: deepeval promptfoo

deepeval-install:
	$(VENV) -m pip install -r deepeval/requirements.txt

deepeval:
	cd deepeval && $(VENV) -m deepeval test run tests --verbose

promptfoo-install:
	cd promptfoo && npm install --no-audit --no-fund

promptfoo:
	cd promptfoo && npx promptfoo@latest eval && npx promptfoo@latest view --no-open