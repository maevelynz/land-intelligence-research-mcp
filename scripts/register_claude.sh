#!/bin/zsh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if ! command -v claude >/dev/null 2>&1; then
  echo "ERROR: Claude Code CLI is not installed or not on PATH." >&2
  exit 127
fi

claude mcp remove land-intelligence -s project >/dev/null 2>&1 || true

claude mcp add \
  --transport stdio \
  --scope project \
  land-intelligence \
  -- "$ROOT/scripts/run_mcp_stdio.sh"

echo
claude mcp get land-intelligence
