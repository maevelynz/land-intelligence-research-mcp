# Relational Data Model

```text
counties
   |
   +----< parcels ----< transactions
   |         |
   |         +---- parcel_infrastructure ----> infrastructure
   |         |
   |         +---- development_outcomes
   |
   +----< infrastructure
```

## Runtime model

v2 does **not** create a persistent DuckDB database during MCP startup.

Each governed tool opens a short-lived in-memory DuckDB connection and creates views over the checked-in CSVs using absolute paths derived from `server.py`.

```text
CSV tables
   ↓
DuckDB views
   ↓
parcel feature CTE
   ↓
transparent optionality score
   ↓
governed MCP tools
```

This is intentionally the same simple runtime philosophy as the working G2 Product Analytics MCP exercise.

## Table grains

- `counties`: one row per synthetic county
- `parcels`: one row per synthetic parcel
- `infrastructure`: one row per synthetic infrastructure asset
- `parcel_infrastructure`: one row per parcel × infrastructure type nearest-asset relationship
- `transactions`: one row per synthetic parcel transaction
- `development_outcomes`: one row per parcel synthetic five-year outcome

See `DATA_DICTIONARY.csv` for columns and key relationships.
