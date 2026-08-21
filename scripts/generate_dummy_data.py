"""Regenerate the complete relational offline research fixture.

The generator is deterministic: seed=42 reproduces the same relationship
structure every time. The synthetic future label is generated from an
explicit data-generating process so evaluation has known ground truth.

Run:
    python scripts/generate_dummy_data.py
"""
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data"
OUT.mkdir(parents=True, exist_ok=True)
rng = np.random.default_rng(42)

COUNTIES = [
    ("VA001","Loudoun County",39.0768,-77.6536,"Northern Virginia"),
    ("VA002","Frederick County",39.2037,-78.2632,"Shenandoah"),
    ("VA003","Clarke County",39.1120,-77.9961,"Shenandoah"),
    ("VA004","Fauquier County",38.7440,-77.8211,"Northern Virginia"),
    ("VA005","Prince William County",38.7023,-77.4789,"Northern Virginia"),
    ("VA006","Culpeper County",38.4850,-77.9560,"Piedmont"),
    ("VA007","Warren County",38.9080,-78.2100,"Shenandoah"),
    ("VA008","Rappahannock County",38.6840,-78.1600,"Piedmont"),
]

def haversine(lat1, lon1, lat2, lon2):
    r = 6371.0
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dp, dl = np.radians(lat2-lat1), np.radians(lon2-lon1)
    a = np.sin(dp/2)**2 + np.cos(p1)*np.cos(p2)*np.sin(dl/2)**2
    return 2*r*np.arcsin(np.sqrt(a))


def _sha256(path: Path) -> str:
    h = __import__("hashlib").sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def write_manifest():
    version = (ROOT / "DATASET_VERSION").read_text().strip()
    files = sorted(OUT.glob("*.csv"))
    table_rows = {}
    checksums = {}
    for path in files:
        import pandas as _pd
        table_rows[path.name] = int(len(_pd.read_csv(path)))
        checksums[path.name] = _sha256(path)

    manifest = {
        "dataset_name": "Land Intelligence Synthetic Research Fixture",
        "dataset_version": version,
        "random_seed": 42,
        "generator": "scripts/generate_dummy_data.py",
        "deterministic": True,
        "tables": table_rows,
        "sha256": checksums,
        "note": "Synthetic methods fixture only; not empirical land-market data."
    }
    (OUT / "MANIFEST.json").write_text(__import__("json").dumps(manifest, indent=2) + "\n")

    lines = [
        "# Synthetic Dataset Manifest",
        "",
        f"- Dataset version: `{version}`",
        "- Random seed: `42`",
        "- Generator: `scripts/generate_dummy_data.py`",
        "- Deterministic: `yes`",
        "",
        "## Generated tables",
        "",
        "| File | Rows | SHA256 |",
        "|---|---:|---|",
    ]
    for name in sorted(table_rows):
        lines.append(f"| `{name}` | {table_rows[name]:,} | `{checksums[name]}` |")
    lines += [
        "",
        "The listed CSV files are generated artifacts. They may be deleted and recreated with:",
        "",
        "```bash",
        "python scripts/generate_dummy_data.py",
        "```",
        "",
        "The SHA256 values allow a reviewer to verify byte-for-byte reproducibility.",
    ]
    (OUT / "MANIFEST.md").write_text("\n".join(lines) + "\n")

    checksum_lines = [f"{checksums[name]}  {name}" for name in sorted(checksums)]
    (OUT / "CHECKSUMS.sha256").write_text("\n".join(checksum_lines) + "\n")


def main():
    counties = pd.DataFrame(COUNTIES, columns=[
        "county_id","county_name","centroid_lat","centroid_lon","region"
    ])
    counties["cash_rent_per_acre"] = np.round(rng.uniform(65,140,len(counties)),2)
    counties["farmland_cap_rate"] = np.round(rng.uniform(.020,.035,len(counties)),4)
    counties.to_csv(OUT/"counties.csv", index=False)

    infra_types = [
        "transmission_line","substation","fiber_node",
        "water_source","highway_interchange","data_center"
    ]
    infrastructure_rows, iid = [], 1
    for _, c in counties.iterrows():
        for infra_type in infra_types:
            count = {
                "transmission_line":3, "substation":2, "fiber_node":2,
                "water_source":1, "highway_interchange":2,
                "data_center":2 if c.county_id=="VA001" else 1,
            }[infra_type]
            for _ in range(count):
                infrastructure_rows.append((
                    f"I{iid:05d}", c.county_id, infra_type,
                    c.centroid_lat+rng.normal(0,.12),
                    c.centroid_lon+rng.normal(0,.12),
                    int(rng.choice([115,230,500])) if infra_type=="transmission_line" else "",
                    int(rng.integers(40,100)) if infra_type in {"substation","fiber_node","water_source"} else "",
                ))
                iid += 1
    infrastructure = pd.DataFrame(infrastructure_rows, columns=[
        "infra_id","county_id","infra_type","lat","lon","voltage_kv","capacity_score"
    ])
    infrastructure.to_csv(OUT/"infrastructure.csv", index=False)

    uses = ["timber","pasture","cropland","mixed_ag"]
    zoning = ["AG","RURAL","INDUSTRIAL","MIXED"]
    parcel_rows, pid = [], 1
    for _, c in counties.iterrows():
        for _ in range(400):
            parcel_rows.append((
                f"P{pid:07d}", c.county_id,
                float(np.clip(rng.lognormal(np.log(120),.75),10,1800)),
                c.centroid_lat+rng.normal(0,.10),
                c.centroid_lon+rng.normal(0,.10),
                rng.choice(uses,p=[.35,.20,.25,.20]),
                float(np.clip(rng.normal(65,15),10,100)),
                float(np.clip(rng.gamma(2,2.5),0,30)),
                float(np.clip(rng.beta(1.5,8),0,1)),
                float(np.clip(rng.beta(1.2,10),0,.8)),
                float(np.clip(rng.normal(4.6,.35),3.5,5.7)),
                rng.choice(zoning,p=[.62,.18,.08,.12]),
            ))
            pid += 1
    parcels = pd.DataFrame(parcel_rows, columns=[
        "parcel_id","county_id","acres","lat","lon","current_land_use",
        "soil_quality","slope_pct","flood_risk","wetland_share",
        "solar_irradiance","zoning_class"
    ])
    parcels.to_csv(OUT/"parcels.csv", index=False)

    bridge = []
    for _, p in parcels.iterrows():
        local = infrastructure[infrastructure.county_id==p.county_id]
        for infra_type in infra_types:
            assets = local[local.infra_type==infra_type]
            distances = haversine(
                p.lat,p.lon,assets.lat.to_numpy(),assets.lon.to_numpy()
            )
            j = int(np.argmin(distances))
            asset = assets.iloc[j]
            bridge.append((p.parcel_id,infra_type,asset.infra_id,float(distances[j])))
    parcel_infra = pd.DataFrame(bridge, columns=[
        "parcel_id","infra_type","nearest_infra_id","distance_km"
    ])
    parcel_infra.to_csv(OUT/"parcel_infrastructure.csv", index=False)

    transactions, tid = [], 1
    for _, p in parcels.sample(frac=.55,random_state=42).iterrows():
        for year in sorted(rng.choice(np.arange(2019,2026),
                                      size=int(rng.integers(1,4)),replace=False)):
            baseline = 4500 + p.soil_quality*25 + max(0,300-p.slope_pct*20)
            ppa = max(1500, baseline*(1+.055*(year-2019))*rng.lognormal(0,.16))
            transactions.append((
                f"T{tid:08d}",p.parcel_id,
                f"{year}-{int(rng.integers(1,13)):02d}-15",
                round(ppa*p.acres,2),round(ppa,2),"arms_length"
            ))
            tid += 1
    pd.DataFrame(transactions, columns=[
        "transaction_id","parcel_id","sale_date",
        "sale_price","price_per_acre","sale_type"
    ]).to_csv(OUT/"transactions.csv", index=False)

    wide = parcel_infra.pivot(
        index="parcel_id",columns="infra_type",values="distance_km"
    ).reset_index()
    truth = parcels.merge(wide,on="parcel_id")
    zoning_bonus = truth.zoning_class.map({
        "INDUSTRIAL":1.2,"MIXED":.6,"RURAL":.1,"AG":-.3
    }).astype(float)
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
    pd.DataFrame({
        "parcel_id":truth.parcel_id,
        "observed_conversion_5yr":converted,
        "synthetic_conversion_probability":np.round(probability,4),
        "conversion_type":[
            rng.choice(["data_center","solar","industrial"]) if x else "none"
            for x in converted
        ],
    }).to_csv(OUT/"development_outcomes.csv", index=False)

    print("Generated relational synthetic fixture:")
    print(f"  counties: {len(counties):,}")
    print(f"  parcels: {len(parcels):,}")
    print(f"  parcel-infrastructure rows: {len(parcel_infra):,}")
    print(f"  transactions: {len(transactions):,}")
    print(f"  outcomes: {len(truth):,}")
    write_manifest()
    print("  manifest/checksums: written")

if __name__ == "__main__":
    main()
