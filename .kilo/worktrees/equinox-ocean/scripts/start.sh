#!/usr/bin/env bash
# JurisLab local dev startup.
# Starts the FastAPI backend (and the Vite frontend in dev mode when present).
# PID files are written to backend/.jurislab.pid and frontend/.jurislab.pid.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND="$ROOT/backend"
VENV="$ROOT/.venv"
HOST="${JURISLAB_HOST:-127.0.0.1}"
PORT="${JURISLAB_PORT:-5273}"
FRONTEND_PORT="${JURISLAB_FRONTEND_PORT:-5274}"
PYTHON="${PYTHON:-$VENV/bin/python}"

log() { printf '[start] %s\n' "$*"; }

if [[ ! -x "$PYTHON" ]]; then
  log "virtualenv python not found at $PYTHON"
  log "create it with:  python3.14 -m venv .venv"
  exit 1
fi

# --- Backend ----------------------------------------------------------------
if [[ -f "$BACKEND/.jurislab.pid" ]] && kill -0 "$(cat "$BACKEND/.jurislab.pid")" 2>/dev/null; then
  log "backend already running (pid $(cat "$BACKEND/.jurislab.pid"))"
else
  log "installing/validating python deps"
  "$PYTHON" -m pip install -q -r "$BACKEND/requirements.txt" -r "$BACKEND/requirements-dev.txt" || true

  if [[ ! -f "$BACKEND/.env" ]]; then
    log "no backend/.env found; copying .env.example"
    cp "$BACKEND/.env.example" "$BACKEND/.env"
  fi

  log "starting backend: uvicorn app.main:app on $HOST:$PORT --reload"
  ( cd "$BACKEND" && nohup "$PYTHON" -m uvicorn app.main:app --host "$HOST" --port "$PORT" --reload > "$BACKEND/jurislab.log" 2>&1 & echo $! > "$BACKEND/.jurislab.pid" )
  for _ in {1..20}; do [[ -s "$BACKEND/.jurislab.pid" ]] && break; sleep 0.1; done
  log "backend pid $(cat "$BACKEND/.jurislab.pid" 2>/dev/null || echo unknown); logs -> backend/jurislab.log"
fi

# --- Frontend (dev mode, when the skeleton is populated) ---------------------
if [[ -d "$ROOT/frontend" && -f "$ROOT/frontend/package.json" ]]; then
  if [[ -f "$ROOT/frontend/.jurislab.pid" ]] && kill -0 "$(cat "$ROOT/frontend/.jurislab.pid")" 2>/dev/null; then
    log "frontend already running (pid $(cat "$ROOT/frontend/.jurislab.pid"))"
  else
    log "starting frontend dev server on port $FRONTEND_PORT"
    ( cd "$ROOT/frontend" && if [[ ! -d node_modules ]]; then npm install; fi
      nohup npm run dev -- --port "$FRONTEND_PORT" > "$ROOT/frontend/frontend.log" 2>&1 & echo $! > "$ROOT/frontend/.jurislab.pid" )
    for _ in {1..20}; do [[ -s "$ROOT/frontend/.jurislab.pid" ]] && break; sleep 0.1; done
    log "frontend pid $(cat "$ROOT/frontend/.jurislab.pid" 2>/dev/null || echo unknown); logs -> frontend/frontend.log"
  fi
else
  log "frontend skeleton not built yet; skipping"
fi

log "done. API: http://$HOST:$PORT  (health: http://$HOST:$PORT/api/v1/health)"