#!/usr/bin/env bash
set -euo pipefail

export PATH="$HOME/.opencode/bin:$HOME/.local/bin:$HOME/.bun/bin:$PATH"

if command -v opencode >/dev/null 2>&1; then
  echo "OpenCode already installed: $(command -v opencode)"
  opencode --version || true
  exit 0
fi

echo "Installing OpenCode..."
if command -v curl >/dev/null 2>&1; then
  curl -fsSL https://opencode.ai/install | bash
fi

export PATH="$HOME/.opencode/bin:$HOME/.local/bin:$HOME/.bun/bin:$PATH"

if ! command -v opencode >/dev/null 2>&1; then
  echo "Install script did not expose opencode in PATH; trying npm fallback..."
  npm install -g opencode-ai
fi

if ! command -v opencode >/dev/null 2>&1; then
  echo "OpenCode install failed. Restart the terminal or add its bin directory to PATH."
  exit 1
fi

if ! grep -q 'opencode/bin' "$HOME/.bashrc" 2>/dev/null; then
  {
    echo ""
    echo "# OpenCode"
    echo 'export PATH="$HOME/.opencode/bin:$HOME/.local/bin:$HOME/.bun/bin:$PATH"'
  } >> "$HOME/.bashrc"
fi

echo "OpenCode installed: $(command -v opencode)"
opencode --version || true
