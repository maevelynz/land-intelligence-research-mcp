#!/usr/bin/env python3
"""Dependency-free repository preflight.

Checks the things that caused v1 pain *before* MCP is launched:
- Python version
- required source/data files
- data checksums
- expected row counts
- uv availability
- Claude CLI availability
- no stale project-local .venv/.mcp.json shipped in the repo
"""
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"

EXPECTED_ROWS = {
    "counties.csv": 8,
    "parcels.csv": 3200,
    "infrastructure.csv": 89,
    "parcel_infrastructure.csv": 19200,
    "transactions.csv": 3496,
    "development_outcomes.csv": 3200,
}

REQUIRED = [
    ROOT / "src" / "land_intelligence_mcp" / "server.py",
    ROOT / "pyproject.toml",
    DATA / "MANIFEST.json",
    *[DATA / name for name in EXPECTED_ROWS],
]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def row_count(path: Path) -> int:
    with path.open(newline="") as f:
        return sum(1 for _ in csv.reader(f)) - 1


def ok(label: str, value: str = ""):
    print(f"✓ {label}" + (f": {value}" if value else ""))


def fail(label: str, value: str = ""):
    print(f"✗ {label}" + (f": {value}" if value else ""))


def main() -> int:
    failures = 0

    print("Land Intelligence MCP v2 — preflight")
    print("------------------------------------")

    if sys.version_info >= (3, 10):
        ok("Python", sys.version.split()[0])
    else:
        fail("Python >=3.10 required", sys.version.split()[0])
        failures += 1

    for path in REQUIRED:
        if path.exists():
            ok("exists", str(path.relative_to(ROOT)))
        else:
            fail("missing", str(path.relative_to(ROOT)))
            failures += 1

    if failures:
        return 1

    manifest = json.loads((DATA / "MANIFEST.json").read_text())
    for name, expected_rows in EXPECTED_ROWS.items():
        path = DATA / name
        actual_rows = row_count(path)
        if actual_rows == expected_rows:
            ok(f"{name} rows", f"{actual_rows:,}")
        else:
            fail(f"{name} rows", f"expected {expected_rows:,}, got {actual_rows:,}")
            failures += 1

        expected_hash = manifest["sha256"][name]
        actual_hash = sha256(path)
        if actual_hash == expected_hash:
            ok(f"{name} checksum")
        else:
            fail(f"{name} checksum")
            failures += 1

    uv = shutil.which("uv")
    if uv:
        ok("uv", uv)
    else:
        fail("uv not found", "install uv before MCP launch")
        failures += 1

    claude = shutil.which("claude")
    if claude:
        ok("Claude Code", claude)
    else:
        print("! Claude Code not found (data/MCP dev can still run; Claude connection cannot).")

    if (ROOT / ".mcp.json").exists():
        print("! .mcp.json exists. This is okay locally, but the downloadable repo ships without one.")
    else:
        ok("no stale .mcp.json shipped")

    if (ROOT / ".venv").exists():
        print("! .venv exists locally. Never copy an old venv between project versions.")
    else:
        ok("no stale .venv shipped")

    print()
    if failures:
        print(f"PREFLIGHT FAILED ({failures} issue(s))")
        return 1

    print("PREFLIGHT PASSED")
    print()
    print("Next command:")
    print("  ./scripts/run_mcp_dev.sh")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
