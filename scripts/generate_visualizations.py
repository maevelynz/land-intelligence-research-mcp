"""Regenerate the documentation PNGs in docs/assets/ from checked-in synthetic data.

This script is deterministic: it reads the seed-42 CSVs already checked into
data/ and calls the real analytical functions in
src/land_intelligence_mcp/server.py directly (`parcel_scores`,
`compare_counties`, `evaluate_optionality_signal`) rather than re-deriving
their SQL. That means every chart is generated from the same governed
definitions the MCP tools actually return -- there is no second, silently
divergent copy of the scoring or aggregation logic, with one narrow and
explicitly-guarded exception (see `_score_components` below).

Requires the optional `viz` dependency group (matplotlib), which is not part
of the MCP server's runtime dependencies:

    uv sync --extra viz
    uv run python scripts/generate_visualizations.py

Regenerating is safe to run repeatedly: it always overwrites the same four
files in docs/assets/ with byte-identical output for unchanged input data.
"""
from __future__ import annotations

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from land_intelligence_mcp.server import (  # noqa: E402
    compare_counties,
    conn,
    evaluate_optionality_signal,
    parcel_scores,
)

ASSETS = ROOT / "docs" / "assets"

# Palette: validated against dataviz-skill CVD/contrast gates for a light
# surface (blue+orange+violet+green passes all-pairs; see PR discussion).
BLUE = "#2a78d6"     # primary series / deterministic formula output
ORANGE = "#eb6834"   # secondary series / concentration or outcome measure
VIOLET = "#4a3aa7"   # reference line (mean)
GREEN = "#008300"    # reference line (median)
INK = "#0b0b0b"
MUTED = "#898781"
GRID = "#e1e0d9"

SYNTHETIC_NOTE = (
    "Synthetic research fixture (seed 42) — not real land, market, or "
    "investment data."
)


def _style_axes(ax) -> None:
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color(MUTED)
    ax.spines["bottom"].set_color(MUTED)
    ax.tick_params(colors=INK, labelsize=9)
    ax.xaxis.label.set_color(INK)
    ax.yaxis.label.set_color(INK)
    ax.title.set_color(INK)
    ax.grid(axis="x", color=GRID, linewidth=0.8, zorder=0)
    ax.set_axisbelow(True)


def _add_caveat(fig, extra: str = "") -> None:
    text = f"{SYNTHETIC_NOTE} {extra}".strip()
    fig.text(
        0.5,
        0.005,
        text,
        ha="center",
        va="bottom",
        fontsize=7.8,
        color=MUTED,
        wrap=True,
    )


def _save(fig, filename: str) -> None:
    ASSETS.mkdir(parents=True, exist_ok=True)
    path = ASSETS / filename
    fig.savefig(path, dpi=140, bbox_inches="tight", pad_inches=0.35, facecolor="white")
    plt.close(fig)
    print(f"wrote {path.relative_to(ROOT)}")


# ---------------------------------------------------------------------------
# B — optionality_signal distribution
# ---------------------------------------------------------------------------

def make_distribution_chart() -> None:
    c = conn()
    try:
        df = parcel_scores(c)
    finally:
        c.close()
    scores = df["optionality_signal"].to_numpy()

    mean = float(scores.mean())
    median = float(np.median(scores))
    std = float(scores.std())

    fig, ax = plt.subplots(figsize=(9, 5))
    ax.hist(scores, bins=40, color=BLUE, edgecolor="white", linewidth=0.4, zorder=2)
    ax.axvline(mean, color=VIOLET, linestyle="--", linewidth=1.6, zorder=3,
               label=f"Mean = {mean:.1f}")
    ax.axvline(median, color=GREEN, linestyle="--", linewidth=1.6, zorder=3,
               label=f"Median = {median:.1f}")
    ax.set_xlabel("optionality_signal  (0–100 transparent screening heuristic)")
    ax.set_ylabel("Parcel count")
    ax.set_title(f"Distribution of optionality_signal across all {len(scores):,} synthetic parcels")

    stats_text = (
        f"n = {len(scores):,}\n"
        f"mean = {mean:.2f}\n"
        f"median = {median:.2f}\n"
        f"std = {std:.2f}\n"
        f"min = {scores.min():.2f}\n"
        f"max = {scores.max():.2f}"
    )
    ax.text(
        0.98, 0.97, stats_text, transform=ax.transAxes, ha="right", va="top",
        fontsize=9, family="monospace", color=INK,
        bbox=dict(boxstyle="round", facecolor="white", edgecolor=MUTED, alpha=0.9),
    )
    ax.legend(loc="upper left", frameon=False, fontsize=9)
    _style_axes(ax)
    fig.tight_layout(rect=[0, 0.05, 1, 1])
    _add_caveat(
        fig,
        "optionality_signal is a transparent weighted-sum screening heuristic "
        "computed by PARCEL_FEATURE_SQL in server.py — not an appraisal, "
        "probability, or investment recommendation.",
    )
    _save(fig, "optionality_distribution.png")


# ---------------------------------------------------------------------------
# C — county comparison
# ---------------------------------------------------------------------------

def make_county_comparison_chart() -> None:
    result = compare_counties(limit=20)
    df = pd.DataFrame(result["rows"]).sort_values("avg_optionality_signal", ascending=True)

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11.5, 5), sharey=True)
    y = np.arange(len(df))

    ax1.barh(y, df["avg_optionality_signal"], color=BLUE, zorder=2)
    ax1.set_yticks(y)
    ax1.set_yticklabels(df["county_name"], fontsize=9)
    ax1.set_xlabel("Average optionality_signal")
    ax1.set_title("Average signal by county")
    for yi, v in zip(y, df["avg_optionality_signal"]):
        ax1.text(v + 0.4, yi, f"{v:.1f}", va="center", fontsize=8, color=INK)

    ax2.barh(y, df["high_signal_parcels"], color=ORANGE, zorder=2)
    ax2.set_xlabel("Parcels with optionality_signal ≥ 60")
    ax2.set_title("Concentration of high-signal parcels")
    for yi, v in zip(y, df["high_signal_parcels"]):
        ax2.text(v + 0.4, yi, f"{int(v)}", va="center", fontsize=8, color=INK)

    for ax in (ax1, ax2):
        _style_axes(ax)

    fig.suptitle("County-level screening summary (compare_counties)", fontsize=12, color=INK)
    fig.tight_layout(rect=[0, 0.07, 1, 0.93])
    _add_caveat(
        fig,
        "Synthetic screening only; not an investment recommendation. A county "
        "average can mask concentration — the right panel shows how many "
        "parcels actually clear the >=60 threshold used by compare_counties.",
    )
    _save(fig, "county_comparison.png")


# ---------------------------------------------------------------------------
# D — score anatomy / formula decomposition
# ---------------------------------------------------------------------------

# These constants mirror PARCEL_FEATURE_SQL in server.py term-for-term. If
# that formula ever changes, the self-check below will fail loudly rather
# than silently rendering a stale chart.
_ZONING_MULTIPLIER = {"INDUSTRIAL": 1.0, "MIXED": 0.75, "RURAL": 0.40}
_ZONING_DEFAULT = 0.20  # AG and any other zoning class


def _score_components(row: pd.Series) -> dict[str, float]:
    zoning_val = _ZONING_MULTIPLIER.get(row["zoning_class"], _ZONING_DEFAULT)
    weighted = {
        "Substation proximity": 0.22 * np.exp(-row["substation_km"] / 8.0),
        "Fiber proximity": 0.18 * np.exp(-row["fiber_km"] / 10.0),
        "Transmission proximity": 0.12 * np.exp(-row["transmission_km"] / 10.0),
        "Highway proximity": 0.10 * np.exp(-row["highway_km"] / 15.0),
        "Data-center proximity": 0.08 * np.exp(-row["data_center_km"] / 20.0),
        "Acreage (capped at 500ac)": 0.10 * min(row["acres"] / 500.0, 1.0),
        "Slope window (<=8%)": 0.06 * max(min((8.0 - row["slope_pct"]) / 8.0, 1.0), 0.0),
        "Flood risk (inverse)": 0.06 * (1 - row["flood_risk"]),
        "Wetland share (inverse)": 0.04 * (1 - row["wetland_share"]),
        "Zoning class": 0.04 * zoning_val,
    }
    return {k: v * 100 for k, v in weighted.items()}


def _select_representative_parcel(df: pd.DataFrame) -> pd.Series:
    """Deterministically pick the parcel nearest the dataset median score.

    Ties (float distance-to-median equal) are broken by ascending parcel_id.
    No manual selection: this is a reproducible function of the checked-in
    data, so re-running the generator on unchanged data always picks the
    same parcel.
    """
    median = df["optionality_signal"].median()
    ordered = df.assign(_dist=(df["optionality_signal"] - median).abs()).sort_values(
        ["_dist", "parcel_id"]
    )
    return ordered.iloc[0]


def make_score_anatomy_chart() -> None:
    c = conn()
    try:
        df = parcel_scores(c)
    finally:
        c.close()

    row = _select_representative_parcel(df)
    components = _score_components(row)

    reconstructed_total = sum(components.values())
    actual_total = float(row["optionality_signal"])
    tolerance = 1e-6
    if abs(reconstructed_total - actual_total) > tolerance:
        raise RuntimeError(
            "Score anatomy self-check failed for parcel "
            f"{row['parcel_id']!r}: reconstructed component sum "
            f"{reconstructed_total!r} does not match parcel_scores() "
            f"optionality_signal {actual_total!r} within tolerance "
            f"{tolerance!r}. The component weights/decay constants in "
            "_score_components() have drifted from PARCEL_FEATURE_SQL in "
            "server.py and must be updated to match."
        )

    items = sorted(components.items(), key=lambda kv: kv[1], reverse=True)
    labels = [k for k, _ in items]
    values = [v for _, v in items]

    fig, ax = plt.subplots(figsize=(9.5, 5.8))
    y = np.arange(len(labels))
    bars = ax.barh(y, values, color=BLUE, zorder=2)
    ax.set_yticks(y)
    ax.set_yticklabels(labels, fontsize=9)
    ax.invert_yaxis()
    ax.set_xlabel("Contribution to optionality_signal (points, 0–100 scale)")
    ax.set_title(
        f"Score anatomy — parcel {row['parcel_id']} ({row['county_name']})\n"
        f"Formula decomposition of optionality_signal = {actual_total:.2f}  "
        "(parcel nearest the dataset median score)",
        fontsize=11,
    )
    for bar, v in zip(bars, values):
        ax.text(bar.get_width() + 0.25, bar.get_y() + bar.get_height() / 2,
                 f"{v:.2f}", va="center", fontsize=8, color=INK)
    _style_axes(ax)
    fig.tight_layout(rect=[0, 0.08, 1, 1])
    _add_caveat(
        fig,
        "These are the ten weighted terms of PARCEL_FEATURE_SQL for one "
        "representative parcel — a formula decomposition, not a statistical "
        "feature-importance or causal-effect measure.",
    )
    _save(fig, "score_anatomy.png")


# ---------------------------------------------------------------------------
# F — decile validation
# ---------------------------------------------------------------------------

def make_decile_validation_chart() -> None:
    result = evaluate_optionality_signal()
    df = pd.DataFrame(result["rows"]).sort_values("score_decile")

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11.5, 5.2))

    ax1.bar(df["score_decile"], df["avg_signal"], color=BLUE, zorder=2)
    ax1.set_xlabel("optionality_signal decile (1 = lowest, 10 = highest)")
    ax1.set_ylabel("Average optionality_signal")
    ax1.set_title("Deterministic formula output\noptionality_signal — from server.py", fontsize=10)
    ax1.set_xticks(df["score_decile"])

    ax2.bar(df["score_decile"], df["conversion_rate"], color=ORANGE, zorder=2)
    ax2.set_xlabel("optionality_signal decile (1 = lowest, 10 = highest)")
    ax2.set_ylabel("observed_conversion_5yr rate")
    ax2.set_title(
        "Independent synthetic DGP output\nobserved_conversion_5yr — from generate_dummy_data.py",
        fontsize=10,
    )
    ax2.set_xticks(df["score_decile"])

    for ax in (ax1, ax2):
        _style_axes(ax)

    fig.suptitle(
        "Decile validation: does the score separate an independently-generated synthetic outcome?",
        fontsize=12, color=INK,
    )

    lift = result.get("top_vs_bottom_lift")
    lift_str = f"{lift:.2f}x" if lift is not None else "undefined (bottom-decile rate = 0)"
    fig.tight_layout(rect=[0, 0.10, 1, 0.90])
    _add_caveat(
        fig,
        f"Top-vs-bottom decile lift = {lift_str} within this synthetic dataset "
        "only; this is synthetic validation, not evidence of real-world "
        "predictive performance. The two panels are independent quantities "
        "from unrelated formulas, plotted separately on purpose — not two "
        "views of the same number.",
    )
    _save(fig, "decile_validation.png")


def main() -> None:
    make_distribution_chart()
    make_county_comparison_chart()
    make_score_anatomy_chart()
    make_decile_validation_chart()
    print("All four visualizations regenerated deterministically from data/ and server.py.")


if __name__ == "__main__":
    main()
