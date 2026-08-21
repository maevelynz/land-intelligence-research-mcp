from pathlib import Path

import duckdb
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"


def conn():
    c = duckdb.connect()
    for table, filename in {
        "counties": "counties.csv",
        "parcels": "parcels.csv",
        "infrastructure": "infrastructure.csv",
        "parcel_infrastructure": "parcel_infrastructure.csv",
        "transactions": "transactions.csv",
        "development_outcomes": "development_outcomes.csv",
    }.items():
        c.execute(
            f"CREATE VIEW {table} AS SELECT * FROM read_csv_auto('{DATA / filename}', header=true)"
        )
    return c


def test_source_counts():
    c = conn()
    try:
        assert c.execute("SELECT COUNT(*) FROM counties").fetchone()[0] == 8
        assert c.execute("SELECT COUNT(*) FROM parcels").fetchone()[0] == 3200
        assert c.execute("SELECT COUNT(*) FROM parcel_infrastructure").fetchone()[0] == 19200
        assert c.execute("SELECT COUNT(*) FROM development_outcomes").fetchone()[0] == 3200
    finally:
        c.close()


def test_relationship_integrity():
    c = conn()
    try:
        orphan_parcels = c.execute("""
            SELECT COUNT(*)
            FROM parcel_infrastructure pi
            LEFT JOIN parcels p USING(parcel_id)
            WHERE p.parcel_id IS NULL
        """).fetchone()[0]
        orphan_infra = c.execute("""
            SELECT COUNT(*)
            FROM parcel_infrastructure pi
            LEFT JOIN infrastructure i
              ON pi.nearest_infra_id = i.infra_id
            WHERE i.infra_id IS NULL
        """).fetchone()[0]
        assert orphan_parcels == 0
        assert orphan_infra == 0
    finally:
        c.close()


def test_every_parcel_has_six_infrastructure_relationships():
    c = conn()
    try:
        bad = c.execute("""
            SELECT COUNT(*) FROM (
                SELECT parcel_id, COUNT(*) AS n
                FROM parcel_infrastructure
                GROUP BY parcel_id
                HAVING n != 6
            )
        """).fetchone()[0]
        assert bad == 0
    finally:
        c.close()
