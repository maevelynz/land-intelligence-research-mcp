from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVER = (ROOT / "src" / "land_intelligence_mcp" / "server.py").read_text()


def test_mcp2_contract_is_explicit():
    assert "from mcp.server import MCPServer" in SERVER
    assert 'mcp = MCPServer("Land Intelligence Research")' in SERVER
    assert "if __name__ == \"__main__\":" in SERVER
    assert "mcp.run()" in SERVER


def test_server_does_not_build_database_on_startup():
    assert "build()" not in SERVER
    assert "DB.unlink" not in SERVER


def test_paths_are_repo_relative_not_cwd_relative():
    assert 'ROOT = Path(__file__).resolve().parents[2]' in SERVER
    assert 'DATA = ROOT / "data"' in SERVER
