# Architecture

```text
Claude Code
     |
     | MCP stdio
     v
MCPServer 2.0
     |
     +-- list_research_questions
     +-- compare_counties
     +-- rank_land_optionality
     +-- explain_parcel_score
     +-- evaluate_optionality_signal
     |
     v
DuckDB in-memory connection
     |
     v
deterministic relational CSVs
```

## Runtime boundary

The MCP process performs **no dataset generation, no package installation, and no persistent DuckDB rebuild** during startup.

Each analytical tool opens a short-lived in-memory DuckDB connection over explicit absolute file paths. This keeps MCP startup small and predictable.

## Reasoning vs computation

Claude handles:
- user intent;
- question generation;
- tool selection;
- synthesis;
- explanation.

The MCP/DuckDB layer handles:
- joins;
- governed definitions;
- score computation;
- aggregations;
- evaluation.

This separation prevents the LLM from silently redefining research metrics.
