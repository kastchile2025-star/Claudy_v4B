#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="$ROOT/.tmp"
mkdir -p "$LOG_DIR"

start_service() {
  local name="$1"
  local script="$2"
  local log="$LOG_DIR/${name}.log"

  echo "Starting ${name}. Log: ${log}"
  bash "$script" >"$log" 2>&1 &
  echo "$!" >"$LOG_DIR/${name}.pid"
}

start_service opencode "$ROOT/scripts/codespace-opencode.sh"
start_service backend "$ROOT/scripts/codespace-backend.sh"
start_service frontend "$ROOT/scripts/codespace-frontend.sh"

echo ""
echo "Claudy services starting:"
echo "  OpenCode: http://127.0.0.1:4096"
echo "  Backend:  http://127.0.0.1:3001"
echo "  Frontend: http://127.0.0.1:3000"
echo ""
echo "Logs:"
echo "  tail -f .tmp/opencode.log"
echo "  tail -f .tmp/backend.log"
echo "  tail -f .tmp/frontend.log"
echo ""
echo "Open the forwarded port 3000 in Codespaces."
echo "Stop everything with: bash scripts/codespace-stop.sh"
