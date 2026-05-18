#!/usr/bin/env bash
set -euo pipefail

PORT="${OPENCODE_PORT:-4096}"
HOST="${OPENCODE_HOST:-127.0.0.1}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

export PATH="$HOME/.opencode/bin:$HOME/.local/bin:$HOME/.bun/bin:$PATH"

if command -v lsof >/dev/null 2>&1 && lsof -i tcp:"$PORT" -sTCP:LISTEN >/dev/null 2>&1; then
  echo "OpenCode already appears to be listening on port ${PORT}."
  exit 0
fi

if ! command -v opencode >/dev/null 2>&1; then
  bash "$ROOT/scripts/codespace-install-opencode.sh"
  export PATH="$HOME/.opencode/bin:$HOME/.local/bin:$HOME/.bun/bin:$PATH"
fi

echo "Starting OpenCode on http://${HOST}:${PORT}"
exec opencode serve --port "$PORT" --hostname "$HOST"
