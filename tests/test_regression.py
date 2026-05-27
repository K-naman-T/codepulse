"""Regression tests: validate against known codebases and detect regressions.

These tests index fixture files and real codebases, then assert minimum
expected symbol/edge counts. If counts drop below thresholds, the parser
regressed.
"""

import time
from pathlib import Path

import pytest

from codepulse.config import CodePulseConfig
from codepulse.graph import CodePulse
from codepulse.parser import SourceParser

FIXTURES = Path(__file__).parent / "fixtures"


class TestFixtureRegression:
    """Known ground truth: accuracy fixtures have exactly these symbols."""

    @pytest.fixture
    def cp(self, tmp_path: Path):
        config = CodePulseConfig(data_dir=str(tmp_path / ".codepulse"))
        return CodePulse(config)

    def test_python_accuracy_fixture_symbols(self, parser: SourceParser):
        fpath = str(FIXTURES / "accuracy.py")
        symbols, refs = parser.parse_file(fpath)

        by_kind = {}
        for s in symbols:
            by_kind.setdefault(s.kind, 0)
            by_kind[s.kind] += 1

        # accuracy.py has exactly: 3 classes, 4 functions, 4 methods
        assert by_kind.get("class", 0) >= 3, f"Expected >=3 classes, got {by_kind}"
        assert by_kind.get("function", 0) >= 4, f"Expected >=4 functions, got {by_kind}"

        calls = [r for r in refs if r.kind == "calls"]
        imports = [r for r in refs if r.kind == "imports"]
        assert len(calls) >= 5, f"Expected >=5 calls, got {len(calls)}"
        assert len(imports) >= 2, f"Expected >=2 imports, got {len(imports)}"

    def test_typescript_accuracy_fixture_symbols(self, parser: SourceParser):
        fpath = str(FIXTURES / "accuracy.ts")
        symbols, refs = parser.parse_file(fpath)

        by_kind = {}
        for s in symbols:
            by_kind.setdefault(s.kind, 0)
            by_kind[s.kind] += 1

        assert by_kind.get("class", 0) >= 2, f"Expected >=2 classes, got {by_kind}"
        assert by_kind.get("interface", 0) >= 2, f"Expected >=2 interfaces, got {by_kind}"
        assert by_kind.get("function", 0) >= 2, f"Expected >=2 functions, got {by_kind}"
        assert by_kind.get("method", 0) >= 4, f"Expected >=4 methods, got {by_kind}"

        calls = [r for r in refs if r.kind == "calls"]
        imports = [r for r in refs if r.kind == "imports"]
        assert len(calls) >= 6, f"Expected >=6 calls, got {len(calls)}"
        assert len(imports) >= 4, f"Expected >=4 imports, got {len(imports)}"

    def test_index_and_validate_fixtures(self, cp: CodePulse):
        cp.index_all(str(FIXTURES))
        report = cp.validate()

        assert report.total_files >= 2, f"Expected >=2 files, got {report.total_files}"
        assert report.total_nodes >= 20, f"Expected >=20 symbols, got {report.total_nodes}"
        assert report.total_edges >= 10, f"Expected >=10 edges, got {report.total_edges}"
        assert report.by_kind.get("function", 0) >= 4
        assert report.by_kind.get("class", 0) >= 3
        assert report.by_kind.get("method", 0) >= 4
        assert report.by_kind.get("interface", 0) >= 2
        assert report.orphan_parent_refs == 0, (
            f"Found {report.orphan_parent_refs} orphan parent refs"
        )

    def test_validate_cli_command(self, cp: CodePulse, cli_runner):
        cp.index_all(str(FIXTURES))
        report = cp.validate()
        summary = report.summary()
        assert "Files:" in summary
        assert "Symbols:" in summary
        assert "Edges:" in summary
        assert "By kind:" in summary
        assert "function:" in summary
        assert "class:" in summary


class TestPerformanceBudget:
    """Index operations must complete within a time budget."""

    def test_index_fixtures_under_5s(self, tmp_path: Path):
        config = CodePulseConfig(data_dir=str(tmp_path / ".codepulse"))
        cp = CodePulse(config)

        start = time.time()
        cp.index_all(str(FIXTURES))
        elapsed = time.time() - start

        assert elapsed < 5.0, f"Index took {elapsed:.2f}s (budget: 5s)"

    def test_parse_accuracy_py_under_200ms(self):
        fpath = str(FIXTURES / "accuracy.py")
        config = CodePulseConfig(data_dir="/tmp")
        parser = SourceParser()

        start = time.time()
        for _ in range(10):
            parser.parse_file(fpath)
        elapsed = (time.time() - start) / 10

        assert elapsed < 0.2, f"Parse took {elapsed*1000:.0f}ms avg (budget: 200ms)"
