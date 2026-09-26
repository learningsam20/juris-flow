#!/usr/bin/env bash
# JurisLab: stop everything, then start fresh (in case the stack is wedged).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

"$ROOT/scripts/stop.sh"
sleep 1
exec "$ROOT/scripts/start.sh"