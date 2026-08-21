# Architecture

```mermaid
flowchart TD
    CC["Claude Code"] -->|"MCP stdio"| MS["MCPServer 2.0"]
    MS --> T1["list_research_questions"]
    MS --> T2["compare_counties"]
    MS --> T3["rank_land_optionality"]
    MS --> T4["explain_parcel_score"]
    MS --> T5["evaluate_optionality_signal"]
    T2 --> DB["DuckDB in-memory connection"]
    T3 --> DB
    T4 --> DB
    T5 --> DB
    DB --> CSV["deterministic relational CSVs (data/)"]
```

`list_research_questions` is the exception: it returns a static list and never opens a
DuckDB connection.

## Request lifecycle and the deterministic/LLM boundary

Every tool call follows the same path, and the deterministic half (shaded) is where
`server.py`, not the LLM, owns the answer:

```mermaid
flowchart TD
    Q["Research question"] --> S["LLM selects an MCP tool"]
    subgraph DET["Deterministic system — Python + DuckDB (server.py)"]
        direction TB
        V["Validated structured arguments<br/>(MCP typed interface)"] --> D["Governed DuckDB query / scoring<br/>(PARCEL_FEATURE_SQL)"]
        D --> R["Structured JSON result"]
    end
    S --> V
    R --> I["LLM interprets the result for the user"]

    style DET fill:#eef3fb,stroke:#2a78d6,stroke-width:1px
```

See [`docs/CODE_WALKTHROUGH.md`](CODE_WALKTHROUGH.md) for exactly where this boundary
sits in code, table-by-table, and for the visualizations (score distribution, county
comparison, score anatomy, decile validation) generated from the checked-in synthetic
data.

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
