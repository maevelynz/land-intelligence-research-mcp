"""Fast local data/analytics smoke test. No Claude required."""
from pathlib import Path
import duckdb

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"

c = duckdb.connect()
for table, filename in {
    "counties": "counties.csv",
    "parcels": "parcels.csv",
    "parcel_infrastructure": "parcel_infrastructure.csv",
    "development_outcomes": "development_outcomes.csv",
}.items():
    c.execute(f"CREATE VIEW {table} AS SELECT * FROM read_csv_auto('{DATA / filename}', header=true)")

print("Land Intelligence MCP v2 smoke test")
print("-----------------------------------")
print("counties:", c.execute("SELECT COUNT(*) FROM counties").fetchone()[0])
print("parcels:", c.execute("SELECT COUNT(*) FROM parcels").fetchone()[0])
print("relationships:", c.execute("SELECT COUNT(*) FROM parcel_infrastructure").fetchone()[0])
print("outcomes:", c.execute("SELECT COUNT(*) FROM development_outcomes").fetchone()[0])
print("status: DATA LAYER OK")
