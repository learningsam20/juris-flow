#!/usr/bin/env bash
# JurisLab: stop backend + frontend processes started by scripts/start.sh.
# Sends SIGTERM for graceful shutdown; SIGKILL fallback after 5 seconds.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

stop_one() {
  local pidfile="$1" name="$2"
  if [[ -f "$pidfile" ]]; then
    local pid
    pid="$(cat "$pidfile")"
    if kill -0 "$pid" 2>/dev/null; then
      printf '[stop] %s (pid %s)...' "$name" "$pid"
      kill "$pid" 2>/dev/null || true
      for _ in $(seq 1 5); do
        kill -0 "$pid" 2>/dev/null || break
        sleep 1
      done
      if kill -0 "$pid" 2>/dev/null; then
        printf ' force-killing\n'
        kill -9 "$pid" 2>/dev/null || true
      else
        printf ' stopped\n'
      fi
    else
      printf '[stop] %s already stopped (stale pid file removed)\n' "$name"
    fi
    rm -f "$pidfile"
  else
    printf '[stop] %s not running\n' "$name"
  fi
}

stop_one "$ROOT/backend/.jurislab.pid" "backend"
stop_one "$ROOT/frontend/.jurislab.pid" "frontend"

# Clean up any remaining listener on default ports
PORT="${JURISLAB_PORT:-5273}"
FRONTEND_PORT="${JURISLAB_FRONTEND_PORT:-5274}"
for p in "$PORT" "$FRONTEND_PORT"; do
  pids=$(lsof -ti ":$p" 2>/dev/null || true)
  if [[ -n "$pids" ]]; then
    printf '[stop] cleaning up remaining listener on port %s (pid %s)\n' "$p" "$pids"
    kill $pids 2>/dev/null || true
  fi
done

printf '[stop] done\n'