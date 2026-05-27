from pathlib import Path

import pytest

from codepulse.graph import CodePulse
from codepulse.mcp import create_mcp_server


class TestMCPServer:
    @pytest.fixture
    def cp(self, tmp_path: Path, sample_project: Path):
        from codepulse.config import CodePulseConfig
        config = CodePulseConfig(data_dir=str(tmp_path / ".codepulse"))
        instance = CodePulse(config)
        instance.index_all(str(sample_project / "src"))
        return instance

    def test_search_symbols_tool(self, cp: CodePulse):
        server = create_mcp_server(cp)
        result = server.search_symbols("UserModel")
        assert result is not None
        assert "UserModel" in result

    def test_search_symbols_no_results(self, cp: CodePulse):
        server = create_mcp_server(cp)
        result = server.search_symbols("nonexistent_garbage_xyz")
        assert "No symbols found" in result or "result" in result.lower()

    def test_find_code_tool(self, cp: CodePulse):
        server = create_mcp_server(cp)
        result = server.find_code("find user model handling", max_nodes=10)
        assert result is not None
        assert len(result) > 0

    def test_get_callers_tool(self, cp: CodePulse, sample_project: Path):
        server = create_mcp_server(cp)
        sample_py = str((sample_project / "src" / "sample.py").resolve())
        result = server.get_callers(f"{sample_py}:calculate_total")
        assert result is not None

    def test_get_callers_invalid_node(self, cp: CodePulse):
        server = create_mcp_server(cp)
        result = server.get_callers("nonexistent:symbol")
        assert "not found" in result.lower() or "no" in result.lower()

    def test_get_impact_radius_tool(self, cp: CodePulse, sample_project: Path):
        server = create_mcp_server(cp)
        sample_py = str((sample_project / "src" / "sample.py").resolve())
        result = server.get_impact_radius(f"{sample_py}:UserModel", depth=2)
        assert result is not None

    def test_server_functions_registered(self, cp: CodePulse):
        server = create_mcp_server(cp)
        assert hasattr(server, "search_symbols")
        assert hasattr(server, "find_code")
        assert hasattr(server, "get_callers")
        assert hasattr(server, "get_impact_radius")

    def test_server_error_on_no_data(self):
        from codepulse.config import CodePulseConfig
        import tempfile
        config = CodePulseConfig(data_dir=tempfile.mkdtemp())
        empty_cp = CodePulse(config)
        server = create_mcp_server(empty_cp)
        result = server.search_symbols("anything")
        assert result is not None
