"""Behavioral tests for the five MCP tool functions.

These tests call the tool functions directly as plain Python callables
(`compare_counties(...)`, `explain_parcel_score(...)`, etc.) -- they do not
go through the MCP protocol boundary. That is intentional: the `@mcp.tool()`
decorator in this codebase returns the function unchanged, so the tools are
importable and callable exactly like any other function. See
tests/test_tool_boundary.py for the small set of tests that instead go
through `mcp.call_tool(...)`, exercising schema validation and result
serialization.

For every data-bearing analytical tool, the expected values are derived
independently in pandas/numpy directly from the checked-in CSVs in `data/`.
This deliberately does NOT import or re-derive PARCEL_FEATURE_SQL from
server.py: the goal is to catch a real regression in the production SQL
(wrong join, wrong weight, wrong column), not merely confirm that the
production code agrees with itself.

Assertions are labeled as either:
  - "Invariant": true for any dataset shape (sorting, error handling, etc).
  - "Regression guard" / "Regression fixture": pinned to the current
    checked-in synthetic dataset's actual values. These would need updating
    if data/*.csv changes, and that is by design.
"""

from __future__ import annotations

import sys
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from land_intelligence_mcp.server import (  # noqa: E402
    compare_counties,
    evaluate_optionality_signal,
    explain_parcel_score,
    list_research_questions,
    rank_land_optionality,
)

DATA = ROOT / "data"
TOL = 1e-6  # float tolerance for comparisons against raw (unrounded) oracle values
ROUND_TOL = 5e-5  # tolerance for comparisons against production's rounded (4dp) output


@pytest.fixture(scope="module")
def oracle() -> pd.DataFrame:
    """Independently derive per-parcel optionality_signal etc. from the CSVs.

    Reimplements the scoring formula documented in server.py's
    PARCEL_FEATURE_SQL using plain pandas/numpy, without importing that SQL
    string. This is the ground truth the behavioral tests check production
    output against.
    """
    counties = pd.read_csv(DATA / "counties.csv")
    parcels = pd.read_csv(DATA / "parcels.csv")
    parcel_infra = pd.read_csv(DATA / "parcel_infrastructure.csv")

    piv = parcel_infra.pivot_table(
        index="parcel_id", columns="infra_type", values="distance_km", aggfunc="max"
    )
    piv = piv.rename(
        columns={
            "transmission_line": "transmission_km",
            "substation": "substation_km",
            "fiber_node": "fiber_km",
            "water_source": "water_km",
            "highway_interchange": "highway_km",
            "data_center": "data_center_km",
        }
    )

    df = parcels.merge(counties, on="county_id").merge(piv, on="parcel_id", how="left")
    df["current_use_value_per_acre"] = df["cash_rent_per_acre"] / df["farmland_cap_rate"].replace(
        0, np.nan
    )

    zoning_weight = {"INDUSTRIAL": 1.0, "MIXED": 0.75, "RURAL": 0.40}
    zoning_score = df["zoning_class"].map(zoning_weight).fillna(0.20)

    df["optionality_signal"] = 100 * (
        0.22 * np.exp(-df["substation_km"] / 8.0)
        + 0.18 * np.exp(-df["fiber_km"] / 10.0)
        + 0.12 * np.exp(-df["transmission_km"] / 10.0)
        + 0.10 * np.exp(-df["highway_km"] / 15.0)
        + 0.08 * np.exp(-df["data_center_km"] / 20.0)
        + 0.10 * np.minimum(df["acres"] / 500.0, 1.0)
        + 0.06 * np.clip((8.0 - df["slope_pct"]) / 8.0, 0.0, 1.0)
        + 0.06 * (1 - df["flood_risk"])
        + 0.04 * (1 - df["wetland_share"])
        + 0.04 * zoning_score
    )
    return df


# ---------------------------------------------------------------------------
# list_research_questions
# ---------------------------------------------------------------------------


def test_list_research_questions_shape():
    """Invariant: static catalog always has this shape, regardless of dataset."""
    result = list_research_questions()
    assert isinstance(result["questions"], list)
    assert len(result["questions"]) == 5
    assert all(isinstance(q, str) and q for q in result["questions"])
    assert isinstance(result["scope_note"], str) and result["scope_note"]


# ---------------------------------------------------------------------------
# compare_counties
# ---------------------------------------------------------------------------


def test_compare_counties_returns_all_counties_when_limit_exceeds_count(oracle):
    """Regression fixture: this dataset currently has exactly 8 counties."""
    result = compare_counties(limit=100)
    assert len(result["rows"]) == oracle["county_name"].nunique() == 8


def test_compare_counties_sorted_descending_by_signal():
    """Invariant: rows are ordered by avg_optionality_signal descending."""
    rows = compare_counties(limit=100)["rows"]
    signals = [r["avg_optionality_signal"] for r in rows]
    assert signals == sorted(signals, reverse=True)


def test_compare_counties_matches_independent_pandas_rollup(oracle):
    """Regression guard: county rollup must match an independent pandas
    groupby over the checked-in CSVs, not just internal SQL self-consistency.
    """
    expected = oracle.groupby("county_name").agg(
        parcels=("parcel_id", "count"),
        avg_optionality_signal=("optionality_signal", "mean"),
        high_signal_parcels=("optionality_signal", lambda s: int((s >= 60).sum())),
        avg_current_use_value_per_acre=("current_use_value_per_acre", "mean"),
    )
    result = {r["county_name"]: r for r in compare_counties(limit=100)["rows"]}
    assert set(result) == set(expected.index)
    for county, exp in expected.iterrows():
        got = result[county]
        assert got["parcels"] == exp["parcels"]
        assert got["high_signal_parcels"] == exp["high_signal_parcels"]
        # compare_counties rounds its output to 4dp (df.round(4)) before returning,
        # so compare against the oracle's value rounded the same way.
        assert got["avg_optionality_signal"] == pytest.approx(
            round(exp["avg_optionality_signal"], 4), abs=ROUND_TOL
        )
        assert got["avg_current_use_value_per_acre"] == pytest.approx(
            round(exp["avg_current_use_value_per_acre"], 4), abs=ROUND_TOL
        )


def test_compare_counties_limit_is_honored():
    """Invariant: limit truncates to the top-N by avg_optionality_signal."""
    top3 = compare_counties(limit=3)["rows"]
    top8 = compare_counties(limit=100)["rows"]
    assert [r["county_name"] for r in top3] == [r["county_name"] for r in top8[:3]]


def test_compare_counties_limit_zero_returns_empty():
    """Edge case (current behavior): limit=0 returns an empty list, no error."""
    assert compare_counties(limit=0)["rows"] == []


def test_compare_counties_negative_limit_raises():
    """Characterization test: pins the current duckdb error for a negative
    limit. This documents existing behavior; it is not an endorsement that
    this is the ideal error surface for a negative limit, and it would need
    to be updated if that surface is ever intentionally changed.
    """
    with pytest.raises(duckdb.BinderException):
        compare_counties(limit=-1)


# ---------------------------------------------------------------------------
# rank_land_optionality
# ---------------------------------------------------------------------------


def test_rank_land_optionality_matches_independent_top_n(oracle):
    """Regression guard: top-N parcels and their scores must match an
    independent pandas ranking over the checked-in CSVs.
    """
    expected = oracle.sort_values("optionality_signal", ascending=False).head(10)
    got = rank_land_optionality(limit=10)["rows"]
    assert [r["parcel_id"] for r in got] == expected["parcel_id"].tolist()
    for r, (_, exp) in zip(got, expected.iterrows()):
        # rank_land_optionality rounds its output to 4dp before returning.
        assert r["optionality_signal"] == pytest.approx(
            round(exp["optionality_signal"], 4), abs=ROUND_TOL
        )


def test_rank_land_optionality_sorted_descending():
    """Invariant: returned rows are ordered by optionality_signal descending."""
    rows = rank_land_optionality(limit=50)["rows"]
    signals = [r["optionality_signal"] for r in rows]
    assert signals == sorted(signals, reverse=True)


def test_rank_land_optionality_county_filter_matches_oracle(oracle):
    """Regression guard: county_name filtering + ranking matches an
    independent pandas filter+sort over the checked-in CSVs."""
    county = "Loudoun County"
    expected_ids = (
        oracle[oracle["county_name"] == county]
        .sort_values("optionality_signal", ascending=False)
        .head(10)["parcel_id"]
        .tolist()
    )
    got = rank_land_optionality(limit=10, county_name=county)["rows"]
    assert all(r["county_name"] == county for r in got)
    assert [r["parcel_id"] for r in got] == expected_ids


def test_rank_land_optionality_unknown_county_returns_empty():
    """Edge case: an unrecognized county_name yields an empty list, not an error."""
    assert rank_land_optionality(limit=5, county_name="Nowhere County")["rows"] == []


def test_rank_land_optionality_limit_exceeds_available_rows(oracle):
    """Edge case: limit larger than the filtered subset returns all matches
    for that subset, with no padding and no error."""
    county = "Clarke County"
    county_count = int((oracle["county_name"] == county).sum())
    got = rank_land_optionality(limit=100_000, county_name=county)["rows"]
    assert len(got) == county_count


# ---------------------------------------------------------------------------
# explain_parcel_score
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("parcel_id", ["P0000165", "P0000001", "P0000998"])
def test_explain_parcel_score_matches_oracle(oracle, parcel_id):
    """Regression guard: explain_parcel_score's numbers must match the
    independent pandas oracle for several known parcels -- this is checked
    against the CSVs directly, not merely for agreement with
    rank_land_optionality's own computation of the same parcel."""
    exp = oracle[oracle["parcel_id"] == parcel_id].iloc[0]
    result = explain_parcel_score(parcel_id)

    assert result["parcel_id"] == parcel_id
    assert result["optionality_signal"] == pytest.approx(
        round(float(exp["optionality_signal"]), 4), abs=TOL
    )
    assert result["current_use_value_per_acre"] == pytest.approx(
        round(float(exp["current_use_value_per_acre"]), 2), abs=TOL
    )

    features = result["positive_screening_features"]
    assert features["substation_km"] == pytest.approx(round(float(exp["substation_km"]), 4), abs=TOL)
    assert features["fiber_km"] == pytest.approx(round(float(exp["fiber_km"]), 4), abs=TOL)
    assert features["transmission_km"] == pytest.approx(
        round(float(exp["transmission_km"]), 4), abs=TOL
    )
    assert features["highway_km"] == pytest.approx(round(float(exp["highway_km"]), 4), abs=TOL)
    assert features["data_center_km"] == pytest.approx(
        round(float(exp["data_center_km"]), 4), abs=TOL
    )
    assert features["zoning_class"] == exp["zoning_class"]

    constraints = result["constraints"]
    assert constraints["slope_pct"] == pytest.approx(round(float(exp["slope_pct"]), 4), abs=TOL)
    assert constraints["flood_risk"] == pytest.approx(round(float(exp["flood_risk"]), 4), abs=TOL)
    assert constraints["wetland_share"] == pytest.approx(
        round(float(exp["wetland_share"]), 4), abs=TOL
    )


def test_explain_parcel_score_unknown_parcel_returns_error_dict():
    """Invariant: unknown parcel_id is a business-level error dict, not a
    raised exception."""
    result = explain_parcel_score("NOPE")
    assert result == {"error": "Parcel 'NOPE' not found."}


# ---------------------------------------------------------------------------
# evaluate_optionality_signal
# ---------------------------------------------------------------------------


def test_evaluate_optionality_signal_decile_sizes_are_exact():
    """Regression fixture: 3200 parcels / 10 deciles == 320 each exactly for
    the current dataset size. This is dataset-size-dependent, not a general
    property of NTILE (it would not hold if the parcel count weren't evenly
    divisible by 10)."""
    rows = evaluate_optionality_signal()["rows"]
    assert len(rows) == 10
    assert {r["score_decile"] for r in rows} == set(range(1, 11))
    assert all(r["parcels"] == 320 for r in rows)


def test_evaluate_optionality_signal_avg_signal_monotonic_by_decile():
    """Invariant: NTILE(10) ordered by optionality_signal must produce
    non-decreasing avg_signal from decile 1 to decile 10."""
    rows = {r["score_decile"]: r["avg_signal"] for r in evaluate_optionality_signal()["rows"]}
    ordered = [rows[d] for d in range(1, 11)]
    assert ordered == sorted(ordered)


def test_evaluate_optionality_signal_lift_matches_reported_rates():
    """Invariant: reported lift must equal top/bottom conversion rate to
    4 decimal places, given the tool's own reported rates."""
    result = evaluate_optionality_signal()
    top = result["top_decile_conversion_rate"]
    bottom = result["bottom_decile_conversion_rate"]
    assert result["top_vs_bottom_lift"] == pytest.approx(round(top / bottom, 4), abs=TOL)


def test_evaluate_optionality_signal_matches_independent_conversion_rollup(oracle):
    """Regression guard: decile-level conversion rates must match an
    independent pandas rank + bucket + groupby over development_outcomes.csv,
    not just internal SQL self-consistency."""
    outcomes = pd.read_csv(DATA / "development_outcomes.csv")
    merged = oracle.merge(outcomes, on="parcel_id")
    merged = merged.sort_values("optionality_signal", kind="mergesort").reset_index(drop=True)

    n = len(merged)
    merged["score_decile"] = (np.arange(n) * 10 // n) + 1
    expected = merged.groupby("score_decile")["observed_conversion_5yr"].mean()

    result_rows = {r["score_decile"]: r["conversion_rate"] for r in evaluate_optionality_signal()["rows"]}
    for decile, exp_rate in expected.items():
        assert result_rows[decile] == pytest.approx(exp_rate, abs=TOL)


def test_evaluate_optionality_signal_bottom_decile_zero_branch_not_covered():
    """Documented limitation, not a test: the `lift is None` branch in
    evaluate_optionality_signal (taken only when the bottom decile's
    conversion rate is exactly 0) is never exercised by the checked-in
    synthetic dataset -- its current bottom-decile conversion rate is
    0.003125, not 0. Forcing that branch would require editing the
    synthetic dataset or refactoring the ratio guard out of server.py into a
    separately-testable helper, both out of scope for this change. This test
    only pins that the bottom decile rate is (still) non-zero, so if that
    ever changes, this test starts failing as a signal to revisit the gap
    rather than silently leaving it unnoticed.
    """
    result = evaluate_optionality_signal()
    assert result["bottom_decile_conversion_rate"] != 0
    assert result["top_vs_bottom_lift"] is not None
