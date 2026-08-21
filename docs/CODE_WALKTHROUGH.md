# Code Walkthrough

This document explains how `src/land_intelligence_mcp/server.py` actually works: how data
gets loaded, how the optionality score is computed, what each MCP tool does, and — the
central architectural point of this repository — where the boundary sits between
deterministic Python/DuckDB computation and LLM reasoning.

It is a code-level companion to the other docs in this repository, not a replacement for
them:

- [`docs/DATA_MODEL.md`](DATA_MODEL.md) — table grains and relationships
- [`docs/RESEARCH_METHODS.md`](RESEARCH_METHODS.md) — why the score is shaped the way it is
- [`docs/ARCHITECTURE.md`](ARCHITECTURE.md) — the runtime diagram at a glance
- [`docs/LIMITATIONS.md`](LIMITATIONS.md) — what the research method does and does not support

## The governed analytical boundary

Every tool call in this system follows the same path:

```text
research question
      │
      ▼
LLM selects an MCP tool
      │
      ▼
MCP typed interface (function signature, argument types)
      │
      ▼
deterministic Python/DuckDB analytical definition
      │
      ▼
structured JSON result
      │
      ▼
LLM interprets the result for the user
```

The two halves of this path have different owners, and the split is deliberate:

| Owned by MCP / Python / DuckDB (deterministic) | Owned by the LLM (interpretive) |
|---|---|
| Which tables exist and how they join | Which tool answers the user's question |
| The `optionality_signal` formula and its weights | How to phrase the question as tool arguments |
| Aggregation, ranking, and decile logic | Synthesizing multiple tool results into an answer |
| Null handling (e.g. `NULLIF`, `LEFT JOIN`) | Distinguishing evidence from interpretation |
| Rounding and output types | Naming limitations relevant to the user's question |
| Argument types (`limit: int`, `county_name: str \| None`) | Declining to answer what the tools can't support |

The value MCP provides here is **not** merely "the LLM can reach the data." An LLM could
already read the CSVs directly — DuckDB has no privileged access a subprocess couldn't
replicate. The value is that MCP exposes one *governed definition* of each analytical
concept instead of leaving the LLM to reconstruct it.

Concretely, if an LLM were instead handed the raw CSVs and asked to "compute an
optionality score," each conversation could independently and silently redefine:

- **Joins** — whether `parcel_infrastructure` is pivoted per `infra_type` before or after
  joining to `parcels`, and whether the join to `counties` is inner or left.
- **Null handling** — whether a parcel missing a `water_source` distance is dropped,
  zero-filled, or excluded from an average; whether `farmland_cap_rate == 0` divides
  cleanly (the real query guards this with `NULLIF(c.farmland_cap_rate, 0)`).
- **Decay functions** — whether proximity is scored as linear distance, inverse distance,
  or exponential decay, and with what decay constant.
- **Weights** — how much acreage should matter relative to substation proximity; the real
  weights (below) are fixed and sum to exactly 1.0, but an LLM re-deriving them from
  scratch has no reason to land on the same numbers twice.
- **Rounding and aggregation** — mean vs. median county-level summaries, and how many
  decimal places to report.
- **Ranking logic** — ties, sort direction, and whether `LIMIT` is applied before or after
  a filter (e.g. filtering to one county before or after ranking changes which parcels
  appear).

Because every tool in this repository calls the same underlying `parcel_scores()`
function (see below), there is exactly one place `optionality_signal` is defined. An LLM
using the tools inherits that single definition instead of re-deriving — and potentially
drifting from — it on every conversation.

## Server startup

```python
from __future__ import annotations
from pathlib import Path
import duckdb
import pandas as pd
from mcp.server import MCPServer

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"

mcp = MCPServer("Land Intelligence Research")
```

`ROOT` is derived from `__file__`, not the process's current working directory, so the
server resolves the same data path regardless of where it's launched from. Nothing at
import time reads a CSV, opens a database connection, or performs any I/O — `mcp =
MCPServer(...)` only registers an empty server object. The `@mcp.tool()`, `@mcp.resource()`,
and `@mcp.prompt()` decorators (seen further down the file) attach functions to that
object at import time, but none of those functions *run* until a client actually calls them.

## `conn()`: the view layer over CSVs

```python
def conn():
    c = duckdb.connect()
    c.execute(f"CREATE VIEW counties AS SELECT * FROM read_csv_auto('{DATA / 'counties.csv'}', header=true)")
    c.execute(f"CREATE VIEW parcels AS SELECT * FROM read_csv_auto('{DATA / 'parcels.csv'}', header=true)")
    # ... four more views ...
    return c
```

Each call to `conn()` opens a fresh **in-memory** DuckDB connection (`duckdb.connect()`
with no path argument) and defines six `VIEW`s, one per CSV file, using absolute paths
built from `DATA`. A `VIEW` is not a copy of the data — it's a saved query that DuckDB
re-executes against the CSV each time it's referenced, so the tables always reflect
whatever is currently on disk in `data/`.

This function is called once per tool invocation, not once per server process. Each of
the four data-bearing analytical tools below opens its own connection and closes it in a
`finally` block:

```python
c = conn()
try:
    ...
finally:
    c.close()
```

Consequences of this design, stated plainly:

- **No persistent database is built or torn down during MCP startup or handshake.**
  Startup cost is just registering Python functions; the first real I/O happens on the
  first tool call.
- **No caching.** Every tool call re-reads the CSVs and recomputes `optionality_signal`
  from scratch. At the current data scale (3,200 parcels) this is fast, but it's a real
  tradeoff, not a free abstraction — a much larger dataset would make per-call
  recomputation the dominant cost.
- **No shared state between calls.** Two tool calls in the same conversation can't
  observe a half-updated view or a connection left open by a previous call.

## The optionality score: `PARCEL_FEATURE_SQL`

This is the analytical core of the repository. It is one SQL string, executed by every
tool that needs parcel-level data, via:

```python
def parcel_scores(c: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    return c.execute(PARCEL_FEATURE_SQL).df()
```

### Step 1 — pivot infrastructure distances per parcel

`parcel_infrastructure` stores one row per `(parcel_id, infra_type)` pair (the nearest
asset of each type and its distance). The first CTE pivots that long table into one row
per parcel with one distance column per infrastructure type:

```sql
WITH infra AS (
    SELECT
        parcel_id,
        MAX(CASE WHEN infra_type='transmission_line' THEN distance_km END) AS transmission_km,
        MAX(CASE WHEN infra_type='substation' THEN distance_km END) AS substation_km,
        MAX(CASE WHEN infra_type='fiber_node' THEN distance_km END) AS fiber_km,
        MAX(CASE WHEN infra_type='water_source' THEN distance_km END) AS water_km,
        MAX(CASE WHEN infra_type='highway_interchange' THEN distance_km END) AS highway_km,
        MAX(CASE WHEN infra_type='data_center' THEN distance_km END) AS data_center_km
    FROM parcel_infrastructure
    GROUP BY parcel_id
),
```

`MAX(CASE WHEN ... THEN distance_km END)` is a standard SQL pivot idiom: for each
`infra_type`, only rows matching that type contribute a non-null value, and `MAX` picks
it out (each parcel has exactly one row per `infra_type` in this dataset, so this is
equivalent to a direct lookup — `MAX` is just the mechanism for pivoting rows into
columns).

### Step 2 — join parcel, county, and infrastructure features

```sql
features AS (
    SELECT
        p.*,
        c.county_name,
        c.region,
        c.cash_rent_per_acre,
        c.farmland_cap_rate,
        c.cash_rent_per_acre / NULLIF(c.farmland_cap_rate, 0) AS current_use_value_per_acre,
        i.transmission_km, i.substation_km, i.fiber_km,
        i.water_km, i.highway_km, i.data_center_km
    FROM parcels p
    JOIN counties c USING(county_id)
    LEFT JOIN infra i USING(parcel_id)
),
```

`current_use_value_per_acre` is a capitalization proxy — annual cash rent divided by a
cap rate — guarded with `NULLIF` so a zero cap rate produces `NULL` rather than a
division error. The join to `counties` is inner (every parcel has a county in this
dataset); the join to the infrastructure pivot is `LEFT JOIN`, so a parcel would still
appear even if it had no infrastructure rows at all — see [Limitations](#implementation-level-limitations)
for what that implies.

### Step 3 — compute the weighted score

```sql
scores AS (
    SELECT
        *,
        100 * (
              0.22 * EXP(-substation_km/8.0)
            + 0.18 * EXP(-fiber_km/10.0)
            + 0.12 * EXP(-transmission_km/10.0)
            + 0.10 * EXP(-highway_km/15.0)
            + 0.08 * EXP(-data_center_km/20.0)
            + 0.10 * LEAST(acres/500.0,1.0)
            + 0.06 * GREATEST(LEAST((8.0-slope_pct)/8.0,1.0),0.0)
            + 0.06 * (1-flood_risk)
            + 0.04 * (1-wetland_share)
            + 0.04 * CASE zoning_class
                WHEN 'INDUSTRIAL' THEN 1.0
                WHEN 'MIXED' THEN 0.75
                WHEN 'RURAL' THEN 0.40
                ELSE 0.20 END
        ) AS optionality_signal
    FROM features
)
SELECT * FROM scores
```

Reading the terms by transformation type:

- **Exponential proximity decay** (five terms — substation, fiber, transmission, highway,
  data center): `EXP(-distance_km / k)` equals 1.0 at zero distance and decays smoothly
  toward 0 as distance grows, with `k` controlling how quickly. A larger `k` (fiber's 10,
  data center's 20) means that infrastructure type's contribution decays more slowly with
  distance than a smaller `k` (substation's 8) — i.e. the score stays more tolerant of
  farther data-center or fiber distances than of farther substation distances.
- **Capped linear size term**: `LEAST(acres/500.0, 1.0)` scales acreage up to a 500-acre
  cap, beyond which additional acreage adds nothing further.
- **Bounded slope window**: `GREATEST(LEAST((8.0-slope_pct)/8.0, 1.0), 0.0)` is 1.0 at zero
  slope, falls linearly to 0.0 at 8% slope, and is clamped to exactly 0.0 beyond that —
  slope above 8% contributes nothing rather than going negative.
- **Linear inverse-risk terms**: `(1 - flood_risk)` and `(1 - wetland_share)`, each already
  a 0–1 proportion in the source data.
- **Categorical zoning map**: a fixed lookup from `zoning_class` to a 0.20–1.0 multiplier
  via `CASE`.

The ten weights — `0.22, 0.18, 0.12, 0.10, 0.08, 0.10, 0.06, 0.06, 0.04, 0.04` — sum to
exactly `1.00`, so `optionality_signal` is bounded to the `[0, 100]` range before
accounting for floating-point rounding. See
[`docs/RESEARCH_METHODS.md`](RESEARCH_METHODS.md) for the reasoning behind choosing this
transparent weighted-sum design over a fitted model.

## The five MCP tools

All four data-bearing tools funnel through the same `parcel_scores()` call, so they
share one definition of `optionality_signal`. They differ only in how they slice,
aggregate, or filter the result.

### `list_research_questions()`

- **Purpose:** Advertise the set of decision-relevant questions the current dataset can
  actually support, so an LLM (or a human) doesn't ask something the tool surface can't
  answer.
- **Inputs:** none.
- **Analytical operation:** none — returns a static list embedded in the function.
- **Output shape:** `{"questions": [...], "scope_note": "..."}`.
- **Relationship to other tools:** a starting point; it points toward, but doesn't call,
  the other four tools.
- **Limitations:** the list is hand-maintained, not derived from the schema — it can fall
  out of sync with what the other tools actually support if either side changes without
  the other being updated.

### `compare_counties(limit: int = 20)`

- **Purpose:** County-level screening summary — where is optionality highest on average,
  and where is it most concentrated in high-scoring parcels?
- **Inputs:** `limit` (max rows returned, default 20).
- **Analytical operation:** calls `parcel_scores()`, registers the resulting DataFrame
  back into DuckDB as `parcel_scores_df`, then runs a `GROUP BY county_name` aggregation:
  parcel count, `AVG(optionality_signal)`, a count of parcels scoring `>= 60`, and average
  current-use value per acre — ordered by average signal descending.
- **Output shape:** `{"rows": [...], "definition": "...", "limitation": "..."}`, values
  rounded to 4 decimal places.
- **Relationship to other tools:** aggregates the same per-parcel scores that
  `rank_land_optionality` and `explain_parcel_score` expose at finer grain.
- **Limitations:** the `>= 60` threshold for "high-signal" is a fixed constant in the
  query, not something the caller can adjust; a mean can hide a county with one extreme
  parcel and otherwise weak inventory.

### `rank_land_optionality(limit: int = 20, county_name: str | None = None)`

- **Purpose:** Return the highest-scoring individual parcels, optionally scoped to one
  county.
- **Inputs:** `limit` (default 20); `county_name` (optional exact-match filter).
- **Analytical operation:** calls `parcel_scores()`, filters by `county_name` in Pandas if
  provided, sorts by `optionality_signal` descending, and selects a fixed column subset
  (parcel id, county, acres, land use, zoning, current-use value, the five returned
  proximity-distance fields — substation, fiber, transmission, highway, and data center
  (`water_km` is computed in the infra pivot but is not part of this tool's output),
  flood/wetland/slope, and the score itself) before taking the top `limit`
  rows.
- **Output shape:** `{"rows": [...], "definition": "...", "limitation": "..."}`.
- **Relationship to other tools:** the parcel-level counterpart to `compare_counties`;
  `explain_parcel_score` drills into one row from this tool's output.
- **Limitations:** `county_name` must match `counties.county_name` exactly (no fuzzy
  matching); as with all tools here, the score is a screening signal, not an appraisal or
  a probability.

### `explain_parcel_score(parcel_id: str)`

- **Purpose:** Let an analyst (human or LLM) see exactly which features drove one
  parcel's score, without inventing a rationale.
- **Inputs:** `parcel_id` (exact match, required).
- **Analytical operation:** calls `parcel_scores()`, filters to the matching row. If no
  row matches, returns `{"error": "Parcel '...' not found."}` instead of raising — a
  "not found" case is a governed result, not an unhandled exception the caller has to
  interpret from a stack trace.
- **Output shape (on success):** `parcel_id`, `county_name`, `optionality_signal`,
  `current_use_value_per_acre`, a `positive_screening_features` object (acreage, the five
  proximity distances used in the score, and zoning class), a `constraints` object
  (slope, flood risk, wetland share), and a `limitation` string.
- **Relationship to other tools:** the per-parcel detail view behind a row surfaced by
  `rank_land_optionality` or `compare_counties`.
- **Limitations:** it reports the *inputs* that feed the score, not each input's
  individual point contribution — a reader still has to reason about the weights and
  decay functions above to understand how much each feature actually moved the score.
  The tool's own output states this: "Feature contributions are screening descriptors,
  not causal effects."

### `evaluate_optionality_signal()`

- **Purpose:** Check whether `optionality_signal` separates parcels by the dataset's
  synthetic five-year conversion outcome — a self-check on the scoring method against the
  synthetic data, not a real-world backtest.
- **Inputs:** none.
- **Analytical operation:** joins `parcel_scores()` to `development_outcomes` on
  `parcel_id`, buckets parcels into ten groups with `NTILE(10) OVER (ORDER BY
  optionality_signal)`, then for each decile computes parcel count, average score, and
  average `observed_conversion_5yr`. It also computes a top-decile-vs-bottom-decile
  "lift" ratio (`None` if the bottom decile's conversion rate is zero, to avoid a
  division error).
- **Output shape:** `{"rows": [...], "top_decile_conversion_rate": ..., "bottom_decile_conversion_rate": ..., "top_vs_bottom_lift": ..., "interpretation": "...", "limitation": "..."}`.
- **Relationship to other tools:** the only tool that touches `development_outcomes`;
  the other four never reference that table.
- **Limitations:** stated directly in the tool's own output — "This is synthetic
  validation only and is not evidence of real-world predictive performance."

### Why `observed_conversion_5yr` is not circular with `optionality_signal`

It's important that these two quantities come from genuinely independent formulas,
otherwise `evaluate_optionality_signal` would just be checking the score against itself.

- `optionality_signal` is computed in `server.py`, from `PARCEL_FEATURE_SQL`, at **query
  time** — it doesn't exist anywhere in the CSVs.
- `observed_conversion_5yr` is generated in `scripts/generate_dummy_data.py`, at
  **dataset-generation time**, from a separate logistic data-generating process:

  ```python
  logit = (
      -2.8 + .006*truth.acres
      - .09*truth.substation
      - .06*truth.fiber_node
      - .025*truth.highway_interchange
      + .35*(truth.solar_irradiance-4.5)
      - 1.2*truth.flood_risk
      - .8*truth.wetland_share
      + zoning_bonus
  )
  probability = 1/(1+np.exp(-np.clip(logit,-10,10)))
  converted = rng.binomial(1,probability)
  ```

  This logistic model shares some inputs with `optionality_signal` (acreage, substation,
  fiber, and highway proximity, flood risk, wetland share, zoning) but combines them with different
  coefficients, omits some scoring inputs (transmission, data-center, slope), and adds one
  input the score never sees (`solar_irradiance`). The result — `observed_conversion_5yr`
  — is then sampled as a Bernoulli draw (`rng.binomial(1, probability)`), so it's not even
  a deterministic function of the logit; it's a stochastic outcome from one.

Because the two formulas are independent, `evaluate_optionality_signal` finding that
top-decile parcels have a higher conversion rate than bottom-decile parcels is a
meaningful (if narrow) check — it shows the score is systematically correlated with the
synthetic dataset's designed outcome, not a guaranteed identity between two views of the
same number. But it validates only that the score behaves sensibly against a synthetic,
author-specified data-generating process. It says nothing about how `optionality_signal`
would perform against real transactions, permits, or development activity — the dataset
has none. See [`docs/LIMITATIONS.md`](LIMITATIONS.md) and
[`docs/RESEARCH_METHODS.md`](RESEARCH_METHODS.md) for the fuller discussion of this
boundary.

## Resource: `research://catalog`

```python
@mcp.resource("research://catalog")
def research_catalog() -> str:
    return catalog().to_json(orient="records", indent=2)
```

`catalog()` reads `data/research_catalog.csv` — a small table of governed research
capability definitions (one row per analytical concept: `county_screening`,
`parcel_ranking`, `parcel_explanation`, `synthetic_backtest`, `current_use_proxy`), each
with a `business_definition`, `grain`, `source_tables`, and `limitation` column — and
serves it as JSON. This gives an LLM (or a human) a machine-readable index of what the
tool surface means and how it's scoped, separate from calling any tool.

## Prompt: `land_research_investigation`

```python
@mcp.prompt()
def land_research_investigation(question: str) -> str:
    return f"""You are a land-intelligence research analyst.

Question: {question}

Rules:
1. Use the governed MCP tools for quantitative evidence.
2. Distinguish synthetic observations from real-world claims.
3. Treat optionality_signal as a screening heuristic, never as appraisal or development probability.
4. Report the evidence that supports each conclusion.
5. Separate observed evidence, interpretation, hypotheses, and limitations.
6. Do not make causal claims from this dataset.
7. If the available tools cannot support the requested conclusion, narrow the conclusion rather than inventing evidence.
"""
```

This is a reusable instruction template an MCP client can request, parameterized by the
user's actual research question. It's the explicit statement, in the code itself, of the
interpretive discipline expected from the LLM side of the boundary described above.

## Runtime entry point

```python
if __name__ == "__main__":
    mcp.run()
```

`scripts/run_mcp_dev.sh` (MCP Inspector / dev mode) and `scripts/run_mcp_stdio.sh` (the
stdio transport Claude Code connects to) both execute this same file directly with the
same pinned dependency versions — there is one server implementation, not a dev variant
and a production variant.

## End-to-end example

This is a real tool call and a real result, produced by executing the repository's own
`compare_counties` logic (same SQL, same rounding) against the checked-in data in
`data/`, with `limit=3`:

**Research question:** *"Which counties look most interesting for deeper diligence?"*

**LLM tool selection:** `compare_counties(limit=3)` — a county-level question, so the
LLM should reach for the county-aggregation tool rather than `rank_land_optionality`
(parcel-level) or `explain_parcel_score` (single-parcel).

**MCP typed interface:** `limit` is validated as an `int`; no other arguments are
accepted.

**Deterministic analytical result** (from `PARCEL_FEATURE_SQL` → `GROUP BY county_name`):

```json
{
  "rows": [
    {
      "county_name": "Loudoun County",
      "parcels": 400,
      "avg_optionality_signal": 44.6505,
      "high_signal_parcels": 31.0,
      "avg_current_use_value_per_acre": 5618.7215
    },
    {
      "county_name": "Rappahannock County",
      "parcels": 400,
      "avg_optionality_signal": 42.8567,
      "high_signal_parcels": 16.0,
      "avg_current_use_value_per_acre": 5297.0085
    },
    {
      "county_name": "Culpeper County",
      "parcels": 400,
      "avg_optionality_signal": 40.6149,
      "high_signal_parcels": 1.0,
      "avg_current_use_value_per_acre": 4277.709
    }
  ],
  "definition": "County screening summary based on the transparent synthetic optionality signal.",
  "limitation": "Synthetic screening only; not an investment recommendation."
}
```

**LLM interpretation:** this is where the deterministic system's job ends. The LLM can
report that Loudoun County has both the highest average signal and the largest
concentration of high-signal parcels (31, versus 16 and 1 in the next two counties) in
this synthetic dataset, and should attach the tool's own `limitation` field verbatim
rather than upgrading the finding into an investment claim. It should not, for example,
assert that Loudoun is a *better real-world investment* — the tool result supports a
screening-level observation about the synthetic dataset, nothing about actual land
markets. What the LLM should *not* do is compute this ranking itself from `counties.csv`
and `parcels.csv` — doing so would require re-deriving the exponential decay constants,
the weight vector, the `NULLIF` guard, and the `>= 60` threshold shown above, with no
guarantee of reproducing them correctly or consistently across conversations.

## What the test suite actually protects

The test suite is deliberately narrow, and it's worth being precise about what each file
does and does not cover.

- **`tests/test_data.py` — data integrity.** Asserts exact row counts for `counties`,
  `parcels`, `parcel_infrastructure`, and `development_outcomes`; asserts zero orphan rows
  in the `parcel_infrastructure` bridge table (every `parcel_id` exists in `parcels`,
  every `nearest_infra_id` exists in `infrastructure`); asserts every parcel has exactly
  six rows in the bridge table. The generator (not this test) guarantees those six rows
  are one per `infra_type` — the test only checks the total count per `parcel_id`. This
  is what guarantees the `LEFT JOIN infra i USING(parcel_id)` step in `PARCEL_FEATURE_SQL`
  never silently drops or duplicates rows.
- **`tests/test_repository_contract.py` — packaging/runtime contract.** Asserts required
  files exist, that `mcp[cli]==2.0.0` appears identically in `pyproject.toml` and both
  launcher scripts (so `pyproject.toml` and the two launcher scripts can't drift apart
  from each other — this is a textual consistency check; CI itself never installs or
  executes the `mcp` package), and that no `.mcp.json` ships in the repository.
- **`tests/test_runtime_contract.py` — source-text assertions, not behavioral tests.**
  This file reads `server.py` as a string and asserts substrings are present or absent —
  for example, that `"from mcp.server import MCPServer"` and `'mcp = MCPServer("Land
  Intelligence Research")'` appear, and that `"build()"` and `"DB.unlink"` do **not**
  appear (guarding against a persistent-database-rebuild pattern being reintroduced). It
  never imports or executes `server.py`, never starts the MCP server, and never calls a
  `@mcp.tool()` function. It catches *pattern regressions* — someone reintroducing a
  cwd-relative path or a startup database rebuild — but nothing about actual tool output;
  that is now covered by the two files below.
- **`tests/test_tool_behavior.py` — behavioral tests, direct function calls.** Imports and
  directly calls all five `@mcp.tool()` functions (`list_research_questions`,
  `compare_counties`, `rank_land_optionality`, `explain_parcel_score`,
  `evaluate_optionality_signal`) as plain Python callables against the checked-in
  synthetic dataset in `data/`. Expected values are computed independently in
  pandas/numpy directly from the CSVs — deliberately without importing or re-deriving
  `PARCEL_FEATURE_SQL` — so a regression in the production SQL (a wrong join, a wrong
  weight, a dropped column) would be caught rather than the test merely confirming the
  code agrees with itself. These calls go through the plain Python function, not the MCP
  transport; see the next entry for that boundary.
- **`tests/test_tool_boundary.py` — a focused subset of the actual MCP `call_tool`
  boundary.** Goes through `mcp.call_tool(name, arguments)` rather than calling the
  Python functions directly, to check the parts of the contract only the MCP layer
  provides: that a valid call's serialized result matches the direct function call
  exactly, that schema validation actually rejects a malformed argument type and a
  missing required argument, and that a business-level "not found" result is a
  successful MCP response (`is_error=False`) rather than being conflated with a
  schema/protocol failure. This is deliberately narrow — it does not re-check every
  analytical assertion already covered by `test_tool_behavior.py`.

  Together, `test_tool_behavior.py` and `test_tool_boundary.py` give the five MCP tools
  real behavioral coverage: their outputs are checked against the dataset rather than
  only against their own SQL, and the MCP call boundary itself is exercised. This is
  **not** comprehensive end-to-end coverage. Still untested: the `research://catalog`
  resource, the `land_research_investigation` prompt, real stdio/transport behavior (the
  boundary tests call `call_tool` in-process and never launch the server via
  `scripts/run_mcp_*.sh` or talk over an actual stdio/SSE connection), and the
  `top_vs_bottom_lift is None` branch in `evaluate_optionality_signal` (taken only when
  the bottom decile's conversion rate is exactly zero, which the current dataset never
  produces).

## Implementation-level limitations

These are limitations of the current *implementation*, distinct from the research-scope
limitations covered in [`docs/LIMITATIONS.md`](LIMITATIONS.md):

- No caching — every tool call recomputes `parcel_scores()` from the CSVs.
- Behavioral test coverage exists for the five tools (direct calls plus a narrow
  MCP-boundary subset) but not for the resource, the prompt, or the transport layer —
  see above.
- `LEFT JOIN infra i USING(parcel_id)` means a parcel with no rows in
  `parcel_infrastructure` would still appear in `parcel_scores()`, with `NULL` distance
  columns; the `EXP(-distance_km/k)` terms would then evaluate to `NULL`, which would
  propagate to a `NULL` `optionality_signal` for that parcel. `tests/test_data.py`
  currently guarantees this situation doesn't occur in the checked-in dataset (every
  parcel has exactly six infrastructure relationships), but the SQL itself has no
  explicit guard against it.
- `county_name` and `parcel_id` filters are exact-match only; there's no fuzzy or
  case-insensitive matching in `rank_land_optionality` or `explain_parcel_score`.
