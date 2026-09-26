#!/usr/bin/env bash
# Rego policy test runner: executes the decision-matrix suite under
# policies/tests using the embedded OPA engine (PRD §15.4).
#
# Usage: scripts/rego_test.sh [pytest-args...]
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND="$ROOT/backend"

PY=""
if [ -x "$ROOT/.venv/bin/python" ]; then
    PY="$ROOT/.venv/bin/python"
elif [ -n "${VIRTUAL_ENV:-}" ] && [ -x "$VIRTUAL_ENV/bin/python" ]; then
    PY="$VIRTUAL_ENV/bin/python"
elif command -v python3 >/dev/null 2>&1; then
    PY="$(command -v python3)"
elif command -v python >/dev/null 2>&1; then
    PY="$(command -v python)"
else
    echo "error: no python interpreter found; run 'make venv' or activate a virtualenv first" >&2
    exit 1
fi

cd "$ROOT"
PYTHONPATH="$BACKEND" "$PY" -m pytest policies/tests "$@"