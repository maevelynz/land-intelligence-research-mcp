# Code Walkthrough

## `src/land_intelligence_mcp/server.py`

This is intentionally the only runtime application file.

### Imports

```python
from pathlib import Path
import duckdb
import pandas as pd
from mcp.server import MCPServer
```

This mirrors the known-good G2 MCP 2.x server pattern.

### Paths

```python
ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
```

The server finds the repository from its own file location. It does not depend on the terminal's current directory.

### MCP server

```python
mcp = MCPServer("Land Intelligence Research")
```

There is no FastMCP 1.x compatibility layer.

### `conn()`

Creates an in-memory DuckDB connection and views over the six deterministic CSV tables.

Important: this function is called only when a tool needs analytics. The MCP process does not build/delete a persistent database during handshake.

### Governed tools

- `list_research_questions`
- `compare_counties`
- `rank_land_optionality`
- `explain_parcel_score`
- `evaluate_optionality_signal`

### Resource

`research://catalog` exposes research definitions and limitations.

### Prompt

`land_research_investigation` tells an LLM to distinguish evidence, interpretation, hypotheses, and limitations.

### Runtime

```python
if __name__ == "__main__":
    mcp.run()
```

Claude and MCP dev both execute this same file directly.
