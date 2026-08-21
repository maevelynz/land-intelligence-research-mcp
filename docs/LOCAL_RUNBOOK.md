# Local Runbook

## Golden path

Unzip into a fresh folder. Do not copy `.venv` or `.mcp.json` from v1.

```bash
cd /path/to/land-intelligence-research-mcp
python3 scripts/preflight.py
```

Expected:

```text
PREFLIGHT PASSED
```

Then:

```bash
./scripts/run_mcp_dev.sh
```

Do not proceed until MCP dev loads the server.

Next:

```bash
./scripts/register_claude.sh
```

Then launch:

```bash
claude
```

Inside Claude:

```text
/mcp
```

Approve `land-intelligence` if prompted.

## Minimal end-to-end test

Ask Claude:

> Use the land-intelligence MCP server. Call list_research_questions. Do not inspect the CSV files directly.

Then:

> Call compare_counties and explain the top two counties. Clearly state that the dataset is synthetic.

## Why this version avoids the v1 failures

- MCP API is the same `MCPServer` 2.x pattern as the working G2 repo.
- MCP version is pinned to `2.0.0`.
- Claude launches `server.py` directly.
- No editable install is required.
- No Python package discovery is required at runtime.
- No old virtualenv is required.
- No `PYTHONPATH` is required.
- Data paths derive from `server.py`, not the shell cwd.
- No database is deleted/rebuilt during MCP handshake.
- Claude and MCP dev use the same launcher/runtime.
