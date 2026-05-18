#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PATH="$HOME/.bun/bin:$PATH"

if ! command -v bun >/dev/null 2>&1; then
  echo "bun no esta instalado o no esta en PATH."
  exit 1
fi

cd "$ROOT/frontend"

if command -v lsof >/dev/null 2>&1 && lsof -i tcp:3000 -sTCP:LISTEN >/dev/null 2>&1; then
  echo "Claudy frontend already appears to be listening on port 3000."
  exit 0
fi

if [ ! -d node_modules ]; then
  bun install
fi

echo "Starting Claudy frontend on port 3000"
exec bun run dev --host 0.0.0.0 --port 3000 --strictPort
