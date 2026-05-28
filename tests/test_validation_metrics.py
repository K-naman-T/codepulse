"""Tests for precision, recall, F1 metrics and golden manifest comparison."""

import os
import tempfile
from pathlib import Path

import pytest
import yaml

from codepulse.db import GraphDB, Node, Edge
from codepulse.validation import MetricSet, GoldenComparison, compare_to_golden


# ---------------------------------------------------------------------------
# MetricSet math
# ---------------------------------------------------------------------------

class TestMetricSetFormula:
    def test_perfect_precision_recall_f1(self):
        m = MetricSet(name="test", true_positives=10, false_positives=0, false_negatives=0)
        assert m.precision == 1.0
        assert m.recall == 1.0
        assert m.f1 == 1.0

    def test_precision_only(self):
        m = MetricSet(name="test", true_positives=10, false_positives=5, false_negatives=0)
        assert m.precision == pytest.approx(10 / 15)
        assert m.recall == 1.0
        assert m.f1 == pytest.approx(2 * (10 / 15) * 1.0 / ((10 / 15) + 1.0))

    def test_recall_only(self):
        m = MetricSet(name="test", true_positives=10, false_positives=0, false_negatives=5)
        assert m.precision == 1.0
        assert m.recall == pytest.approx(10 / 15)
        assert m.f1 == pytest.approx(2 * 1.0 * (10 / 15) / (1.0 + (10 / 15)))

    def test_half_precision_half_recall(self):
        m = MetricSet(name="test", true_positives=5, false_positives=5, false_negatives=5)
        assert m.precision == 0.5
        assert m.recall == 0.5
        assert m.f1 == 0.5

    def test_no_emitted_with_expected_items_zeroes_metrics(self):
        m = MetricSet(name="test", true_positives=0, false_positives=0, false_negatives=10)
        assert m.precision == 0.0
        assert m.recall == 0.0
        assert m.f1 == 0.0

    def test_empty_expected_and_emitted(self):
        m = MetricSet(name="test", true_positives=0, false_positives=0, false_negatives=0)
        assert m.precision == 1.0
        assert m.recall == 1.0
        assert m.f1 == 1.0

    def test_only_false_positives(self):
        m = MetricSet(name="test", true_positives=0, false_positives=5, false_negatives=0)
        assert m.precision == 0.0
        assert m.recall == 0.0
        assert m.f1 == 0.0

    def test_only_false_negatives(self):
        m = MetricSet(name="test", true_positives=0, false_positives=0, false_negatives=5)
        assert m.precision == 0.0
        assert m.recall == 0.0
        assert m.f1 == 0.0


# ---------------------------------------------------------------------------
# compare_to_golden - unit tests with controlled data
# ---------------------------------------------------------------------------

def _fresh_db(nodes: list[Node], edges: list[Edge]) -> GraphDB:
    db = GraphDB(":memory:")
    db.initialize()
    if nodes or edges:
        db.bulk_import(nodes, edges)
    return db


def _manifest(**kw) -> dict:
    defaults = {"symbols": [], "edges": [], "allowed_external": []}
    defaults.update(kw)
    return defaults


class TestCompareToGoldenSymbols:
    def test_exact_match(self):
        db = _fresh_db(
            nodes=[Node(id="/p/accuracy.py:User", name="User", kind="class",
                         file_path="/p/accuracy.py", line_start=1, line_end=10,
                         language="python")],
            edges=[],
        )
        manifest = _manifest(
            symbols=[{"id_suffix": "User", "name": "User", "kind": "class",
                       "file": "accuracy.py", "line_start": 1, "line_end": 10}],
        )
        result = compare_to_golden(db, manifest)
        assert result.symbols.true_positives == 1
        assert result.symbols.false_positives == 0
        assert result.symbols.false_negatives == 0
        assert result.symbols.precision == 1.0
        assert result.symbols.recall == 1.0

    def test_false_positive_extra_symbol(self):
        db = _fresh_db(
            nodes=[
                Node(id="/p/accuracy.py:User", name="User", kind="class",
                     file_path="/p/accuracy.py", line_start=1, line_end=10,
                     language="python"),
                Node(id="/p/accuracy.py:Extra", name="Extra", kind="class",
                     file_path="/p/accuracy.py", line_start=20, line_end=25,
                     language="python"),
            ],
            edges=[],
        )
        manifest = _manifest(
            symbols=[{"id_suffix": "User", "name": "User", "kind": "class",
                       "file": "accuracy.py", "line_start": 1, "line_end": 10}],
        )
        result = compare_to_golden(db, manifest)
        assert result.symbols.true_positives == 1
        assert result.symbols.false_positives == 1
        assert result.symbols.false_negatives == 0

    def test_false_negative_missing_symbol(self):
        db = _fresh_db(
            nodes=[Node(id="/p/accuracy.py:User", name="User", kind="class",
                         file_path="/p/accuracy.py", line_start=1, line_end=10,
                         language="python")],
            edges=[],
        )
        manifest = _manifest(
            symbols=[
                {"id_suffix": "User", "name": "User", "kind": "class",
                 "file": "accuracy.py", "line_start": 1, "line_end": 10},
                {"id_suffix": "missing", "name": "missing", "kind": "function",
                 "file": "accuracy.py", "line_start": 30, "line_end": 35},
            ],
        )
        result = compare_to_golden(db, manifest)
        assert result.symbols.true_positives == 1
        assert result.symbols.false_positives == 0
        assert result.symbols.false_negatives == 1

    def test_wrong_kind_detected(self):
        db = _fresh_db(
            nodes=[Node(id="/p/accuracy.py:User", name="User", kind="class",
                         file_path="/p/accuracy.py", line_start=1, line_end=10,
                         language="python")],
            edges=[],
        )
        manifest = _manifest(
            symbols=[{"id_suffix": "User", "name": "User", "kind": "function",
                       "file": "accuracy.py", "line_start": 1, "line_end": 10}],
        )
        result = compare_to_golden(db, manifest)
        # wrong kind means the (file, name) pair exists but kinds differ
        assert result.symbols.wrong_kind == ["User"]
        # The key (accuracy.py, User, class) is in DB but not in manifest
        # The key (accuracy.py, User, function) is in manifest but not in DB
        # So: 0 TP, 1 FP, 1 FN
        assert result.symbols.true_positives == 0
        assert result.symbols.false_positives == 1
        assert result.symbols.false_negatives == 1

    def test_external_symbols_do_not_count_as_fp(self):
        db = _fresh_db(
            nodes=[Node(id="external:module:os", name="os", kind="external_module",
                         file_path="/p/accuracy.py", line_start=1, line_end=1,
                         language="python")],
            edges=[],
        )
        manifest = _manifest(symbols=[], allowed_external=["os"])
        result = compare_to_golden(db, manifest)
        # external_module nodes are already filtered out, should not appear
        assert result.symbols.true_positives == 0
        assert result.symbols.false_positives == 0

    def test_allowed_external_does_not_hide_user_symbols(self):
        db = _fresh_db(
            nodes=[Node(id="/p/accuracy.py:print", name="print", kind="function",
                         file_path="/p/accuracy.py", line_start=1, line_end=2,
                         language="python")],
            edges=[],
        )
        manifest = _manifest(symbols=[], allowed_external=["print"])
        result = compare_to_golden(db, manifest)
        assert result.symbols.false_positives == 1


class TestCompareToGoldenEdges:
    def test_exact_call_edge_match(self):
        db = _fresh_db(
            nodes=[
                Node(id="/p/accuracy.py:create_user", name="create_user",
                     kind="function", file_path="/p/accuracy.py",
                     line_start=1, line_end=5, language="python"),
                Node(id="/p/accuracy.py:get_logger", name="get_logger",
                     kind="function", file_path="/p/accuracy.py",
                     line_start=10, line_end=12, language="python"),
            ],
            edges=[Edge(source_id="/p/accuracy.py:create_user",
                        target_id="/p/accuracy.py:get_logger",
                        kind="calls", file_path="/p/accuracy.py",
                        line_number=3)],
        )
        manifest = _manifest(
            symbols=[
                {"id_suffix": "create_user", "name": "create_user",
                 "kind": "function", "file": "accuracy.py"},
                {"id_suffix": "get_logger", "name": "get_logger",
                 "kind": "function", "file": "accuracy.py"},
            ],
            edges=[{"source_name": "create_user", "target_name": "get_logger",
                     "kind": "calls", "file": "accuracy.py",
                     "line_number": 3, "resolution_status": "resolved"}],
        )
        result = compare_to_golden(db, manifest)
        assert result.calls.true_positives == 1
        assert result.calls.false_positives == 0
        assert result.calls.false_negatives == 0
        assert result.calls.precision == 1.0
        assert result.calls.recall == 1.0

    def test_missing_call_edge(self):
        db = _fresh_db(
            nodes=[
                Node(id="/p/accuracy.py:create_user", name="create_user",
                     kind="function", file_path="/p/accuracy.py",
                     line_start=1, line_end=5, language="python"),
                Node(id="/p/accuracy.py:get_logger", name="get_logger",
                     kind="function", file_path="/p/accuracy.py",
                     line_start=10, line_end=12, language="python"),
            ],
            edges=[],
        )
        manifest = _manifest(
            symbols=[
                {"id_suffix": "create_user", "name": "create_user",
                 "kind": "function", "file": "accuracy.py"},
                {"id_suffix": "get_logger", "name": "get_logger",
                 "kind": "function", "file": "accuracy.py"},
            ],
            edges=[{"source_name": "create_user", "target_name": "get_logger",
                     "kind": "calls", "file": "accuracy.py",
                     "line_number": 3, "resolution_status": "resolved"}],
        )
        result = compare_to_golden(db, manifest)
        assert result.calls.true_positives == 0
        assert result.calls.false_positives == 0
        assert result.calls.false_negatives == 1
        assert result.calls.recall == 0.0

    def test_import_edge_detected(self):
        db = _fresh_db(
            nodes=[
                Node(id="/p/accuracy.py:__file__",
                     name="/p/accuracy.py", kind="file",
                     file_path="/p/accuracy.py", line_start=1, line_end=1,
                     language="python"),
            ],
            edges=[Edge(source_id="/p/accuracy.py:__file__",
                        target_id="external:module:os",
                        kind="imports", file_path="/p/accuracy.py",
                        line_number=3)],
        )
        manifest = _manifest(
            symbols=[],
            edges=[{"source_name": "accuracy.py", "target_name": "os",
                     "kind": "imports", "file": "accuracy.py",
                     "line_number": 3, "resolution_status": "resolved"}],
            allowed_external=["os"],
        )
        result = compare_to_golden(db, manifest)
        assert result.imports.true_positives == 1
        assert result.imports.false_positives == 0
        assert result.imports.false_negatives == 0

    def test_allowed_external_suppresses_external_edge_fp(self):
        db = _fresh_db(
            nodes=[
                Node(id="/p/accuracy.py:main", name="main", kind="function",
                     file_path="/p/accuracy.py", line_start=1, line_end=3),
                Node(id="unresolved:calls:print", name="print", kind="unresolved_symbol",
                     file_path="/p/accuracy.py", line_start=1, line_end=1),
            ],
            edges=[Edge(source_id="/p/accuracy.py:main", target_id="unresolved:calls:print",
                        kind="calls", file_path="/p/accuracy.py", line_number=2)],
        )
        manifest = _manifest(symbols=[], edges=[], allowed_external=["print"])
        result = compare_to_golden(db, manifest)
        assert result.calls.false_positives == 0

    def test_allowed_external_does_not_hide_user_edge_fp(self):
        db = _fresh_db(
            nodes=[
                Node(id="/p/accuracy.py:main", name="main", kind="function",
                     file_path="/p/accuracy.py", line_start=1, line_end=3),
                Node(id="/p/accuracy.py:print", name="print", kind="function",
                     file_path="/p/accuracy.py", line_start=5, line_end=7),
            ],
            edges=[Edge(source_id="/p/accuracy.py:main", target_id="/p/accuracy.py:print",
                        kind="calls", file_path="/p/accuracy.py", line_number=2)],
        )
        manifest = _manifest(symbols=[], edges=[], allowed_external=["print"])
        result = compare_to_golden(db, manifest)
        assert result.calls.false_positives == 1


class TestCompareToGoldenParentLinks:
    def test_correct_parent(self):
        db = _fresh_db(
            nodes=[
                Node(id="/p/accuracy.py:User", name="User", kind="class",
                     file_path="/p/accuracy.py", line_start=1, line_end=10,
                     language="python"),
                Node(id="/p/accuracy.py:User.__init__", name="User.__init__",
                     kind="method", file_path="/p/accuracy.py",
                     line_start=2, line_end=5, language="python",
                     parent_id="/p/accuracy.py:User"),
            ],
            edges=[],
        )
        manifest = _manifest(
            symbols=[
                {"id_suffix": "User", "name": "User", "kind": "class",
                 "file": "accuracy.py", "line_start": 1, "line_end": 10},
                {"id_suffix": "User.__init__", "name": "User.__init__",
                 "kind": "method", "file": "accuracy.py",
                 "parent_name": "User", "line_start": 2, "line_end": 5},
            ],
        )
        result = compare_to_golden(db, manifest)
        assert result.parent_links.true_positives == 1
        assert result.parent_links.precision == 1.0
        assert result.parent_links.recall == 1.0

    def test_wrong_parent(self):
        db = _fresh_db(
            nodes=[
                Node(id="/p/accuracy.py:User", name="User", kind="class",
                     file_path="/p/accuracy.py", line_start=1, line_end=10,
                     language="python"),
                Node(id="/p/accuracy.py:AdminUser", name="AdminUser", kind="class",
                     file_path="/p/accuracy.py", line_start=20, line_end=30,
                     language="python"),
                Node(id="/p/accuracy.py:User.__init__", name="User.__init__",
                     kind="method", file_path="/p/accuracy.py",
                     line_start=2, line_end=5, language="python",
                     parent_id="/p/accuracy.py:AdminUser"),
            ],
            edges=[],
        )
        manifest = _manifest(
            symbols=[
                {"id_suffix": "User", "name": "User", "kind": "class",
                 "file": "accuracy.py"},
                {"id_suffix": "AdminUser", "name": "AdminUser", "kind": "class",
                 "file": "accuracy.py"},
                {"id_suffix": "User.__init__", "name": "User.__init__",
                 "kind": "method", "file": "accuracy.py",
                 "parent_name": "User"},
            ],
        )
        result = compare_to_golden(db, manifest)
        # DB says parent=AdminUser, manifest says parent=User, so both metrics miss
        assert result.parent_links.true_positives == 0
        assert result.parent_links.false_positives == 1  # DB has parent, but wrong
        assert result.parent_links.false_negatives == 1  # manifest expects parent, wrong
        assert result.parent_links.precision == 0.0
        assert result.parent_links.recall == 0.0


class TestCompareToGoldenLineRanges:
    def test_wrong_line_range(self):
        db = _fresh_db(
            nodes=[Node(id="/p/accuracy.py:User", name="User", kind="class",
                         file_path="/p/accuracy.py", line_start=1, line_end=99,
                         language="python")],
            edges=[],
        )
        manifest = _manifest(
            symbols=[{"id_suffix": "User", "name": "User", "kind": "class",
                       "file": "accuracy.py", "line_start": 1, "line_end": 10}],
        )
        result = compare_to_golden(db, manifest)
        assert result.symbols.wrong_line_range == ["User"]

    def test_correct_line_range_no_warning(self):
        db = _fresh_db(
            nodes=[Node(id="/p/accuracy.py:User", name="User", kind="class",
                         file_path="/p/accuracy.py", line_start=1, line_end=10,
                         language="python")],
            edges=[],
        )
        manifest = _manifest(
            symbols=[{"id_suffix": "User", "name": "User", "kind": "class",
                       "file": "accuracy.py", "line_start": 1, "line_end": 10}],
        )
        result = compare_to_golden(db, manifest)
        assert result.symbols.wrong_line_range == []


# ---------------------------------------------------------------------------
# Integration test with the real golden manifest and accuracy.py fixture
# ---------------------------------------------------------------------------

HERE = Path(__file__).parent
MANIFEST_PATH = HERE / "golden" / "accuracy.yml"
FIXTURES = HERE / "fixtures"


@pytest.fixture(scope="module")
def python_golden_manifest():
    with open(MANIFEST_PATH) as f:
        return yaml.safe_load(f)


@pytest.fixture
def golden_db_for_python(db):
    from codepulse.parser import SourceParser
    parser = SourceParser()
    fpath = FIXTURES / "accuracy.py"
    symbols, edges = parser.parse_file(str(fpath))
    db.bulk_import(symbols, edges)
    return db


class TestAccuracyPythonIntegration:
    def test_all_symbols_high_precision(self, golden_db_for_python, python_golden_manifest):
        result = compare_to_golden(golden_db_for_python, python_golden_manifest)
        assert result.symbols.true_positives == 18, (
            f"Expected 18 TP symbols, got {result.symbols.true_positives}"
        )
        assert result.symbols.false_positives == 0
        assert result.symbols.false_negatives == 0
        assert result.symbols.precision >= 0.98
        assert result.symbols.recall >= 0.98

    def test_calls_imports_detected(self, golden_db_for_python, python_golden_manifest):
        result = compare_to_golden(golden_db_for_python, python_golden_manifest)
        # Expected: 18 calls and 2 imports; require at least the 0.85 recall threshold.
        assert result.calls.true_positives >= 15, (
            f"calls TP: {result.calls.true_positives}"
        )
        assert result.imports.true_positives == 2, (
            f"imports TP: {result.imports.true_positives}"
        )

    def test_wrong_kind_empty(self, golden_db_for_python, python_golden_manifest):
        result = compare_to_golden(golden_db_for_python, python_golden_manifest)
        assert result.symbols.wrong_kind == [], (
            f"Unexpected wrong kinds: {result.symbols.wrong_kind}"
        )

    def test_wrong_parent_empty(self, golden_db_for_python, python_golden_manifest):
        result = compare_to_golden(golden_db_for_python, python_golden_manifest)
        assert result.symbols.wrong_parent == [], (
            f"Unexpected wrong parents: {result.symbols.wrong_parent}"
        )
