# Land Intelligence Research MCP

**Can an AI research analyst reason about land without inventing the evidence?**

Land Intelligence Research MCP is an independent research prototype exploring how governed analytics and Model Context Protocol (MCP) can support research on land development optionality.

The project is motivated by a broader research interest in **land economics, energy and infrastructure development, and long-duration land stewardship**. It asks:

> How should landowners, investors, and developers reason about development optionality when a parcel has simultaneous economic, infrastructure, and environmental value?

The current implementation focuses on **development optionality screening** using a deterministic synthetic dataset. It combines parcel characteristics, infrastructure proximity, land-use constraints, and synthetic outcomes into a governed analytical layer that an LLM can access through MCP tools.

> **Research disclaimer:** This repository uses synthetic data and transparent screening heuristics for research and demonstration purposes. Optionality scores are not appraisals, forecasts, causal estimates, probabilities of development, or investment recommendations.

## Why this project

A common failure mode in AI analytics is allowing the language model to become the analytics engine: it reads raw files, writes ad hoc queries, silently changes definitions, and produces numbers that are difficult to govern or reproduce.

This project takes a different approach:

```text
LLM / research agent
        |
        | reasoning, question framing, synthesis
        v
Model Context Protocol
        |
        | governed tool surface
        v
DuckDB analytical layer
        |
        | joins, scoring, aggregation, validation
        v
deterministic synthetic land data
```

The LLM is responsible for reasoning. The analytical layer is responsible for quantitative evidence.

If the MCP does not expose evidence needed to answer a question, the desired behavior is to **surface the analytical gap rather than bypass the system or invent a result**.

## Research lenses

The same governed evidence can support different decisions depending on the stakeholder.

### Institutional landowner / TIMO-style owner

A long-duration owner may ask which assets have meaningful development optionality, whether optionality is broad or concentrated, and which assets warrant strategic diligence before a hold, sale, lease, entitlement, or development-partnership decision.

### Investor / capital allocator

An investor may ask where diligence or capital should be deployed, whether optionality is already reflected in current-use value, and what underwriting evidence is still missing.

### Developer

A developer may ask which parcels deserve deeper feasibility work and whether favorable infrastructure-proximity signals survive parcel-level physical constraints.

## MCP analytical surface

The server exposes five governed tools:

- `list_research_questions`
- `compare_counties`
- `rank_land_optionality`
- `explain_parcel_score`
- `evaluate_optionality_signal`

It also exposes:

- Resource: `research://catalog`
- Prompt: `land_research_investigation`

## Data model

The project ships with six deterministic synthetic relational tables:

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

The synthetic fixture is reproducible with seed `42`. A manifest and SHA256 checksums are included.

## Optionality signal

The optionality score is a **transparent screening heuristic** that incorporates signals such as parcel acreage, zoning, slope, flood risk, wetland share, and proximity to substations, transmission, fiber, highways, and data-center infrastructure.

The score is intentionally not framed as a valuation or predictive probability.

The `evaluate_optionality_signal` tool checks whether the score separates synthetic development outcomes by score decile. This is useful for testing the research workflow, but it is **not evidence of real-world predictive validity**.

## Local setup

Recommended prerequisites:

- Python 3.11+
- `uv`
- Claude Code if you want to test the LLM + MCP workflow

From the repository root:

```bash
python3.11 scripts/preflight.py
```

Then launch MCP development mode:

```bash
./scripts/run_mcp_dev.sh
```

Register with Claude Code:

```bash
./scripts/register_claude.sh
```

Then:

```bash
claude
```

Inside Claude:

```text
/mcp
```

Approve `land-intelligence` if prompted.

## Example agent prompt

```text
Act as a research analyst supporting a long-duration institutional landowner.

Use the land-intelligence MCP as your only quantitative data and analytics interface. Do not inspect the underlying CSVs, database, SQL, Python files, manifests, or other repository artifacts directly.

Determine which markets and parcels appear to have the strongest development optionality, what evidence supports that conclusion, and what evidence should make the investment team cautious.

Every material numerical claim should come from an MCP tool result. If an important question cannot be answered through the current MCP analytical surface, identify the gap rather than bypassing the MCP or guessing.
```

See `PROMPTS.md` for additional investor, developer, red-team, and cross-stakeholder prompts.

## Broader research direction

The current implementation focuses on development optionality and infrastructure/land constraints.

Future research could extend into power-market and interconnection data, zoning and entitlement histories, development comps, lease and option structures, conservation easements, habitat quality and fragmentation, biodiversity constraints, carbon and natural-capital economics, water availability, NPV / IRR scenarios, and spatial portfolio optimization.

Habitat preservation is part of the broader research motivation, but the current synthetic model should **not** be interpreted as a habitat-quality model.

## Independence and attribution

This is an **independent research project**. It was informed by public research into institutional land ownership and firms working at the intersection of land, infrastructure, energy, and long-duration asset management.

It is not affiliated with, endorsed by, or representative of any specific company, investment manager, developer, landowner, or data provider. All included datasets and outcomes are synthetic.

## License

MIT
