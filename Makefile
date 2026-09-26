# JurisFlow developer Makefile
# Targets mirror the PRD §11/§15 workflow. Default stack is local dev
# (SQLite + embedded Qdrant + Ollama on the host).

SHELL := /bin/bash
ROOT  := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))
VENV  := $(ROOT)/.venv
PY    := $(VENV)/bin/python
BACKEND := $(ROOT)/backend

.DEFAULT_GOAL := help

.PHONY: help install seed run stop restart test lint typecheck rego docker-up docker-down eval clean

help: ## List targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

install: ## Create venv and install backend deps
	python3.14 -m venv $(VENV)
	$(PY) -m pip install -U pip
	$(PY) -m pip install -r $(BACKEND)/requirements.txt -r $(BACKEND)/requirements-dev.txt

seed: ## Seed the dev database (idempotent; --force to reset)
	cd $(BACKEND) && $(PY) -m app.db.seed

run: start ## Alias for start

start: ## Start backend (+ frontend dev server if present)
	$(ROOT)/scripts/start.sh

stop: ## Stop backend + frontend
	$(ROOT)/scripts/stop.sh

restart: ## Kill everything and start fresh
	$(ROOT)/scripts/kill_all_and_start.sh

test: ## Backend + policy test suites
	cd $(BACKEND) && $(PY) -m pytest tests -q
	$(ROOT)/scripts/rego_test.sh

lint: ## Ruff lint + format check
	cd $(BACKEND) && $(PY) -m ruff check app tests
	cd $(BACKEND) && $(PY) -m ruff format --check app tests

typecheck: ## mypy static checks
	cd $(BACKEND) && $(PY) -m mypy app

rego: ## Rego policy tests
	$(ROOT)/scripts/rego_test.sh

docker-up: ## Build + start full stack (backend, frontend, qdrant, postgres)
	docker compose up --build -d

docker-down: ## Stop + remove containers
	docker compose down

telemetry-up: ## Start OTel collector (profile: traces + metrics + logs)
	docker compose --profile telemetry up -d otel-collector

telemetry-down: ## Stop OTel collector
	docker compose --profile telemetry down

eval: ## Run eval suites (requires API on :5600)
	cd eval && make run

sbom: ## Generate CycloneDX SBOM for the backend environment
	cd $(BACKEND) && $(PY) -m cyclonedx_py environment -o $(ROOT)/docs/sbom.json

lock: ## Freeze backend dependency lockfile
	$(PY) -m pip freeze > $(BACKEND)/requirements-lock.txt

scan: ## Scan backend dependencies for known vulnerabilities
	$(PY) -m pip_audit --requirement $(BACKEND)/requirements.txt \
		--requirement $(BACKEND)/requirements-dev.txt \
		--requirement $(BACKEND)/requirements-lock.txt

sast: ## Bandit static analysis (backend)
	cd $(BACKEND) && $(PY) -m bandit -q -ll -r app

secretscan: ## Gitleaks secret scan (full repo history)
ifeq ($(shell command -v gitleaks 2>/dev/null),)
	@echo "gitleaks not installed; skipping (install via 'brew install gitleaks' or run CI)"
else
	gitleaks detect --source $(ROOT) --redact --exit-code 1
endif

clean: ## Remove caches, build artifacts and generated data
	rm -rf $(BACKEND)/data/qdrant $(BACKEND)/data/uploads $(BACKEND)/.pytest_cache
	rm -rf $(ROOT)/frontend/dist $(ROOT)/frontend/node_modules
	find $(ROOT) -name __pycache__ -type d -prune -exec rm -rf {} \;

.PHONY: help install seed run stop restart test lint typecheck rego docker-up docker-down telemetry-up telemetry-down eval sbom lock scan clean