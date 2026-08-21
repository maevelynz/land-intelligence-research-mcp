#!/bin/zsh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if ! command -v uv >/dev/null 2>&1; then
  echo "ERROR: uv is not installed or not on PATH." >&2
  exit 127
fi

exec uv run \
  --with "mcp[cli]==2.0.0" \
  --with "duckdb>=1.1,<2" \
  --with "pandas>=2.2,<4" \
  mcp dev "$ROOT/src/land_intelligence_mcp/server.py"
