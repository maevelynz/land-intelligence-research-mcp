from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]


def test_required_files_exist():
    required = [
        "src/land_intelligence_mcp/server.py",
        "scripts/preflight.py",
        "scripts/run_mcp_dev.sh",
        "scripts/run_mcp_stdio.sh",
        "scripts/register_claude.sh",
        "data/MANIFEST.json",
        "README.md",
        "pyproject.toml",
    ]
    for rel in required:
        assert (ROOT / rel).exists(), rel


def test_mcp_runtime_is_pinned():
    text = (ROOT / "pyproject.toml").read_text()
    assert 'mcp[cli]==2.0.0' in text

    for rel in ["scripts/run_mcp_dev.sh", "scripts/run_mcp_stdio.sh"]:
        assert 'mcp[cli]==2.0.0' in (ROOT / rel).read_text()


def test_no_project_specific_mcp_config_is_shipped():
    assert not (ROOT / ".mcp.json").exists()
