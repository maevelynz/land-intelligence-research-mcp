from __future__ import annotations

from pathlib import Path

import duckdb
import pandas as pd
from mcp.server import MCPServer


ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"

mcp = MCPServer("Land Intelligence Research")


def conn():
    """Create an in-memory DuckDB connection over deterministic local CSVs.

    This mirrors the known-good G2 MCP pattern:
    - no package installation assumptions
    - no database rebuild during MCP startup
    - no current-working-directory assumptions
    - absolute paths derived from __file__
    """
    c = duckdb.connect()
    c.execute(f"CREATE VIEW counties AS SELECT * FROM read_csv_auto('{DATA / 'counties.csv'}', header=true)")
    c.execute(f"CREATE VIEW parcels AS SELECT * FROM read_csv_auto('{DATA / 'parcels.csv'}', header=true)")
    c.execute(f"CREATE VIEW infrastructure AS SELECT * FROM read_csv_auto('{DATA / 'infrastructure.csv'}', header=true)")
    c.execute(f"CREATE VIEW parcel_infrastructure AS SELECT * FROM read_csv_auto('{DATA / 'parcel_infrastructure.csv'}', header=true)")
    c.execute(f"CREATE VIEW transactions AS SELECT * FROM read_csv_auto('{DATA / 'transactions.csv'}', header=true)")
    c.execute(f"CREATE VIEW development_outcomes AS SELECT * FROM read_csv_auto('{DATA / 'development_outcomes.csv'}', header=true)")
    return c


def catalog() -> pd.DataFrame:
    return pd.read_csv(DATA / "research_catalog.csv")


PARCEL_FEATURE_SQL = r"""
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
features AS (
    SELECT
        p.*,
        c.county_name,
        c.region,
        c.cash_rent_per_acre,
        c.farmland_cap_rate,
        c.cash_rent_per_acre / NULLIF(c.farmland_cap_rate, 0) AS current_use_value_per_acre,
        i.transmission_km,
        i.substation_km,
        i.fiber_km,
        i.water_km,
        i.highway_km,
        i.data_center_km
    FROM parcels p
    JOIN counties c USING(county_id)
    LEFT JOIN infra i USING(parcel_id)
),
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
"""


def parcel_scores(c: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    return c.execute(PARCEL_FEATURE_SQL).df()


@mcp.resource("research://catalog")
def research_catalog() -> str:
    """Governed research capability catalog with definitions and limitations."""
    return catalog().to_json(orient="records", indent=2)


@mcp.tool()
def list_research_questions() -> dict:
    """Return decision-relevant questions that the current synthetic dataset can support."""
    return {
        "questions": [
            "Which counties deserve deeper diligence based on parcel optionality and concentration of high-signal sites?",
            "Which parcels combine high optionality signals with relatively low current-use value?",
            "Which infrastructure distances distinguish the highest-ranked parcels?",
            "Does the optionality signal separate parcels with higher synthetic five-year conversion rates?",
            "Which high-scoring parcels are most exposed to flood, wetland, slope, or zoning constraints?",
        ],
        "scope_note": "These are screening/research questions on synthetic data, not appraisal or investment recommendations.",
    }


@mcp.tool()
def compare_counties(limit: int = 20) -> dict:
    """Rank counties by average optionality signal and concentration of high-signal parcels."""
    c = conn()
    try:
        c.register("parcel_scores_df", parcel_scores(c))
        df = c.execute(
            """
            SELECT
                county_name,
                COUNT(*) AS parcels,
                AVG(optionality_signal) AS avg_optionality_signal,
                SUM(CASE WHEN optionality_signal >= 60 THEN 1 ELSE 0 END) AS high_signal_parcels,
                AVG(current_use_value_per_acre) AS avg_current_use_value_per_acre
            FROM parcel_scores_df
            GROUP BY county_name
            ORDER BY avg_optionality_signal DESC
            LIMIT ?
            """,
            [limit],
        ).df()
        return {
            "rows": df.round(4).to_dict(orient="records"),
            "definition": "County screening summary based on the transparent synthetic optionality signal.",
            "limitation": "Synthetic screening only; not an investment recommendation.",
        }
    finally:
        c.close()


@mcp.tool()
def rank_land_optionality(limit: int = 20, county_name: str | None = None) -> dict:
    """Return the highest optionality-screening parcels, optionally within one county."""
    c = conn()
    try:
        df = parcel_scores(c)
        if county_name:
            df = df[df["county_name"] == county_name]
        cols = [
            "parcel_id","county_name","acres","current_land_use","zoning_class",
            "current_use_value_per_acre","substation_km","fiber_km",
            "transmission_km","highway_km","data_center_km","flood_risk",
            "wetland_share","slope_pct","optionality_signal",
        ]
        out = df.sort_values("optionality_signal", ascending=False)[cols].head(limit)
        return {
            "rows": out.round(4).to_dict(orient="records"),
            "definition": "Transparent screening heuristic; higher scores indicate stronger synthetic optionality signals.",
            "limitation": "The score is not an appraisal, causal estimate, or probability of development.",
        }
    finally:
        c.close()


@mcp.tool()
def explain_parcel_score(parcel_id: str) -> dict:
    """Return one parcel's screening features so an analyst can explain its rank without inventing evidence."""
    c = conn()
    try:
        df = parcel_scores(c)
        row = df[df["parcel_id"] == parcel_id]
        if row.empty:
            return {"error": f"Parcel '{parcel_id}' not found."}
        r = row.iloc[0]
        return {
            "parcel_id": r["parcel_id"],
            "county_name": r["county_name"],
            "optionality_signal": round(float(r["optionality_signal"]), 4),
            "current_use_value_per_acre": round(float(r["current_use_value_per_acre"]), 2),
            "positive_screening_features": {
                "acres": round(float(r["acres"]), 2),
                "substation_km": round(float(r["substation_km"]), 4),
                "fiber_km": round(float(r["fiber_km"]), 4),
                "transmission_km": round(float(r["transmission_km"]), 4),
                "highway_km": round(float(r["highway_km"]), 4),
                "data_center_km": round(float(r["data_center_km"]), 4),
                "zoning_class": r["zoning_class"],
            },
            "constraints": {
                "slope_pct": round(float(r["slope_pct"]), 4),
                "flood_risk": round(float(r["flood_risk"]), 4),
                "wetland_share": round(float(r["wetland_share"]), 4),
            },
            "limitation": "Feature contributions are screening descriptors, not causal effects.",
        }
    finally:
        c.close()


@mcp.tool()
def evaluate_optionality_signal() -> dict:
    """Evaluate score separation against synthetic five-year conversion labels by decile."""
    c = conn()
    try:
        c.register("parcel_scores_df", parcel_scores(c))
        df = c.execute(
            """
            WITH x AS (
                SELECT
                    s.parcel_id,
                    s.optionality_signal,
                    o.observed_conversion_5yr,
                    NTILE(10) OVER (ORDER BY s.optionality_signal) AS score_decile
                FROM parcel_scores_df s
                JOIN development_outcomes o USING(parcel_id)
            )
            SELECT
                score_decile,
                COUNT(*) AS parcels,
                AVG(optionality_signal) AS avg_signal,
                AVG(observed_conversion_5yr) AS conversion_rate
            FROM x
            GROUP BY score_decile
            ORDER BY score_decile DESC
            """
        ).df()

        top = float(df.loc[df["score_decile"] == 10, "conversion_rate"].iloc[0])
        bottom = float(df.loc[df["score_decile"] == 1, "conversion_rate"].iloc[0])
        lift = None if bottom == 0 else top / bottom

        return {
            "rows": df.round(6).to_dict(orient="records"),
            "top_decile_conversion_rate": round(top, 6),
            "bottom_decile_conversion_rate": round(bottom, 6),
            "top_vs_bottom_lift": None if lift is None else round(lift, 4),
            "interpretation": "Higher synthetic conversion rates in upper score deciles indicate separation within the simulated data-generating process.",
            "limitation": "This is synthetic validation only and is not evidence of real-world predictive performance.",
        }
    finally:
        c.close()


@mcp.prompt()
def land_research_investigation(question: str) -> str:
    """Reusable instructions for a calibrated land-intelligence research investigation."""
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


if __name__ == "__main__":
    mcp.run()
