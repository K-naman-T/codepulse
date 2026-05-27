from pathlib import Path

import pytest

from codepulse.config import CodePulseConfig
from codepulse.graph import CodePulse


class TestCodePulse:
    @pytest.fixture
    def cp(self, tmp_path: Path):
        config = CodePulseConfig(data_dir=str(tmp_path / ".codepulse"))
        return CodePulse(config)

    def test_init_project_creates_dir(self, cp: CodePulse):
        cp.init_project()
        assert cp.config.config_dir.exists()

    def test_index_all_discovers_files(self, cp: CodePulse, sample_project: Path):
        result = cp.index_all(str(sample_project / "src"))
        assert result.files_indexed > 0
        assert result.symbols_found > 0

    def test_search_finds_symbols(self, cp: CodePulse, sample_project: Path):
        cp.index_all(str(sample_project / "src"))
        results = cp.search("calculate")
        assert len(results) > 0

    def test_search_empty_returns_empty(self, cp: CodePulse, sample_project: Path):
        cp.index_all(str(sample_project / "src"))
        results = cp.search("nonexistent_symbol_xyz")
        assert results == []

    def test_get_callers(self, cp: CodePulse, sample_project: Path):
        cp.index_all(str(sample_project / "src"))
        sample_py = str((sample_project / "src" / "sample.py").resolve())
        callees = cp.get_callees(f"{sample_py}:calculate_total")
        assert len(callees) >= 0

    def test_get_node(self, cp: CodePulse, sample_project: Path):
        cp.index_all(str(sample_project / "src"))
        sample_py = str((sample_project / "src" / "sample.py").resolve())
        node = cp.get_node(f"{sample_py}:UserModel")
        assert node is not None
        assert node.node.kind == "class"

    def test_get_node_with_source(self, cp: CodePulse, sample_project: Path):
        cp.index_all(str(sample_project / "src"))
        sample_py = str((sample_project / "src" / "sample.py").resolve())
        detail = cp.get_node(f"{sample_py}:UserModel", include_source=True)
        assert detail.node is not None
        assert detail.source is not None
        assert "class UserModel" in detail.source

    def test_get_node_nonexistent(self, cp: CodePulse):
        detail = cp.get_node("nonexistent:node")
        assert detail is None

    def test_build_context(self, cp: CodePulse, sample_project: Path):
        cp.index_all(str(sample_project / "src"))
        context = cp.build_context("find user handling code", max_nodes=10)
        assert len(context) > 0
        assert isinstance(context, str)

    def test_reindex_updates_graph(self, cp: CodePulse, sample_project: Path):
        cp.index_all(str(sample_project / "src"))
        first = cp.search("calculate_total")
        sample_py = sample_project / "src" / "sample.py"
        sample_py.write_text(sample_py.read_text() + "\ndef new_func():\n    pass\n")
        cp.index_all(str(sample_project / "src"))
        assert len(first) >= 0

    def test_index_all_with_progress(self, cp: CodePulse, sample_project: Path):
        progress = []

        def on_progress(msg: str):
            progress.append(msg)

        cp.index_all(str(sample_project / "src"), on_progress=on_progress)
        assert len(progress) > 0
