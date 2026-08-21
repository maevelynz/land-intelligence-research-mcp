# v2 Review Checklist

## Verified before packaging

- Python source compiles syntactically.
- Six source-table files are present.
- Expected row counts match the known deterministic fixture.
- SHA256 checksums match the manifest.
- No `.venv` is shipped.
- No `.mcp.json` is shipped.
- No `*.dist-info` or `*.egg-info` is shipped.
- MCP runtime is pinned to `mcp[cli]==2.0.0`.
- Server uses `from mcp.server import MCPServer`, matching the known-good G2 runtime pattern.
- Server does not call a database build on import/startup.
- Server derives data paths from `__file__`.
- Claude and MCP dev launch the same `server.py`.
- Launcher scripts resolve repository root from their own location.

## Environment-dependent validation

This build environment cannot reach PyPI, so it cannot download and execute MCP 2.0/DuckDB for a live transport test here.

The local runbook therefore makes `./scripts/run_mcp_dev.sh` the first dependency-backed gate on the user's Mac. Do not register Claude until that gate succeeds.

This is deliberate: one failing gate, one layer to debug.
