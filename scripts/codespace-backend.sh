#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PATH="$HOME/.bun/bin:$PATH"

if ! command -v bun >/dev/null 2>&1; then
  echo "bun no esta instalado o no esta en PATH."
  exit 1
fi

cd "$ROOT/backend"

if command -v lsof >/dev/null 2>&1 && lsof -i tcp:3001 -sTCP:LISTEN >/dev/null 2>&1; then
  echo "Claudy backend already appears to be listening on port 3001."
  exit 0
fi

if [ ! -d node_modules ]; then
  bun install
fi

echo "Starting Claudy backend on port 3001"
exec bun run src/server.ts
