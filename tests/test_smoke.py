"""Real-repo smoke tests: index actual codebases and verify expected results.

These tests require the real repos to exist on disk. They're tagged
as 'smoke' because they're slower and depend on external state.
"""

import os
from pathlib import Path

import pytest

from codepulse.config import CodePulseConfig
from codepulse.graph import CodePulse

RAFTAAIR_DIR = Path(os.environ.get("RAFTAAIR_DIR", "/home/knamant/raftaar-ai"))
CODEPULSE_DIR = Path(os.environ.get("CODEPULSE_DIR", "/home/knamant/codepulse"))


def pytest_collection_modifyitems(items):
    for item in items:
        if "smoke" in item.keywords:
            item.add_marker(pytest.mark.smoke)


@pytest.mark.smoke
class TestRaftaarAi:
    """Index raftaar-ai and assert minimum expected structure."""

    @pytest.fixture
    def cp(self, tmp_path: Path):
        config = CodePulseConfig(data_dir=str(tmp_path / ".codepulse"))
        return CodePulse(config)

    def test_raftaar_indexes_without_errors(self, cp: CodePulse):
        if not RAFTAAIR_DIR.exists():
            pytest.skip(f"raftaar-ai not found at {RAFTAAIR_DIR}")
        result = cp.index_all(str(RAFTAAIR_DIR))
        assert result.files_indexed > 0, "No files indexed"
        assert result.symbols_found > 0, "No symbols found"
        assert len(result.errors) == 0, f"Index errors: {result.errors[:5]}"

    def test_raftaar_has_expected_structure(self, cp: CodePulse):
        if not RAFTAAIR_DIR.exists():
            pytest.skip(f"raftaar-ai not found at {RAFTAAIR_DIR}")
        cp.index_all(str(RAFTAAIR_DIR))
        report = cp.validate()

        assert report.total_files >= 20, f"Expected >=20 files, got {report.total_files}"
        assert report.total_nodes >= 100, f"Expected >=100 symbols, got {report.total_nodes}"
        assert report.total_edges >= 500, f"Expected >=500 edges, got {report.total_edges}"

        assert report.by_kind.get("function", 0) >= 20, (
            f"Expected >=20 functions, got {report.by_kind.get('function', 0)}"
        )
        assert report.by_kind.get("class", 0) >= 2, (
            f"Expected >=2 classes, got {report.by_kind.get('class', 0)}"
        )

        assert report.by_edge_kind.get("calls", 0) >= 100, (
            f"Expected >=100 call edges, got {report.by_edge_kind.get('calls', 0)}"
        )
        assert report.by_edge_kind.get("imports", 0) >= 100, (
            f"Expected >=100 import edges, got {report.by_edge_kind.get('imports', 0)}"
        )

    def test_raftaar_index_under_10s(self, cp: CodePulse):
        if not RAFTAAIR_DIR.exists():
            pytest.skip(f"raftaar-ai not found at {RAFTAAIR_DIR}")
        import time
        start = time.time()
        cp.index_all(str(RAFTAAIR_DIR))
        elapsed = time.time() - start
        assert elapsed < 10.0, f"Index took {elapsed:.2f}s (budget: 10s)"


@pytest.mark.smoke
class TestCodePulseSelf:
    """Index CodePulse's own codebase."""

    @pytest.fixture
    def cp(self, tmp_path: Path):
        config = CodePulseConfig(data_dir=str(tmp_path / ".codepulse"))
        return CodePulse(config)

    def test_self_index_symbols(self, cp: CodePulse):
        src = CODEPULSE_DIR / "src"
        if not src.exists():
            pytest.skip(f"codepulse src not found at {src}")
        cp.index_all(str(src))
        report = cp.validate()
        assert report.total_nodes >= 50, (
            f"Expected >=50 symbols in own codebase, got {report.total_nodes}"
        )
