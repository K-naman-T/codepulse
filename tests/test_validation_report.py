"""Structured validation tests: issue codes, ok property, validate_graph()."""

import tempfile
from pathlib import Path
from typing import Generator

import pytest

from codepulse.db import GraphDB, Node, Edge
from codepulse.schema import CURRENT_SCHEMA_VERSION
from codepulse.validation import ValidationReport, validate_graph, ValidationIssue


@pytest.fixture
def db() -> Generator[GraphDB, None, None]:
    tmp = tempfile.mkdtemp()
    gdb = GraphDB(str(Path(tmp) / "test.db"))
    gdb.initialize()
    yield gdb
    gdb.close()


class TestOkProperty:
    def test_ok_on_clean_graph(self, db: GraphDB):
        report = validate_graph(db)
        assert isinstance(report, ValidationReport)
        assert report.ok is True

    def test_ok_false_with_error_issue(self, db: GraphDB):
        db.conn.execute(
            "INSERT INTO edges (source_id, target_id, kind) VALUES (?, ?, ?)",
            ["missing", "also_missing", "calls"],
        )
        db.conn.commit()
        report = validate_graph(db)
        assert report.ok is False

    def test_ok_true_with_warning_issue(self, db: GraphDB):
        """If we lower severity to warning, ok stays True."""
        report = ValidationReport(
            issues=[ValidationIssue(code="STALE_FILE", severity="warning", message="test")]
        )
        assert report.ok is True


class TestOrphanEdgeSource:
    def test_orphan_edge_source_detected(self, db: GraphDB):
        db.upsert_node(Node(id="a.py:foo", name="foo", kind="function", file_path="a.py", line_start=1))
        db.conn.execute(
            "INSERT INTO edges (source_id, target_id, kind) VALUES (?, ?, ?)",
            ["nonexistent_source", "a.py:foo", "calls"],
        )
        db.conn.commit()
        report = validate_graph(db)
        codes = [i.code for i in report.issues]
        assert "ORPHAN_EDGE_SOURCE" in codes
        assert report.ok is False


class TestOrphanEdgeTarget:
    def test_orphan_edge_target_detected(self, db: GraphDB):
        db.upsert_node(Node(id="a.py:foo", name="foo", kind="function", file_path="a.py", line_start=1))
        db.conn.execute(
            "INSERT INTO edges (source_id, target_id, kind) VALUES (?, ?, ?)",
            ["a.py:foo", "nonexistent_target", "calls"],
        )
        db.conn.commit()
        report = validate_graph(db)
        codes = [i.code for i in report.issues]
        assert "ORPHAN_EDGE_TARGET" in codes
        assert report.ok is False


class TestOrphanParent:
    def test_orphan_parent_detected(self, db: GraphDB):
        db.upsert_node(Node(
            id="a.py:child", name="child", kind="method", file_path="a.py",
            line_start=1, parent_id="a.py:missing_parent",
        ))
        db.conn.commit()
        report = validate_graph(db)
        codes = [i.code for i in report.issues]
        assert "ORPHAN_PARENT" in codes
        assert report.ok is False


class TestStaleFile:
    def test_stale_file_detected(self, db: GraphDB):
        db.conn.execute(
            "INSERT INTO files (path, language, content_hash) VALUES (?, ?, ?)",
            ["/nonexistent/path.py", "python", "abc123"],
        )
        db.conn.commit()
        report = validate_graph(db)
        codes = [i.code for i in report.issues]
        assert "STALE_FILE" in codes
        assert report.ok is False

    def test_stale_file_not_triggered_for_existing_path(self, db: GraphDB, tmp_path: Path):
        existing = tmp_path / "real.py"
        existing.write_text("x = 1\n")
        db.conn.execute(
            "INSERT INTO files (path, language, content_hash) VALUES (?, ?, ?)",
            [str(existing), "python", "abc123"],
        )
        db.conn.commit()
        report = validate_graph(db)
        codes = [i.code for i in report.issues]
        assert "STALE_FILE" not in codes


class TestInvalidLineRange:
    def test_negative_line_start(self, db: GraphDB):
        db.upsert_node(Node(id="a.py:bad", name="bad", kind="function", file_path="a.py", line_start=-1))
        db.conn.commit()
        report = validate_graph(db)
        codes = [i.code for i in report.issues]
        assert "INVALID_LINE_RANGE" in codes

    def test_negative_line_end(self, db: GraphDB):
        db.upsert_node(Node(id="a.py:bad", name="bad", kind="function", file_path="a.py", line_start=1, line_end=-5))
        db.conn.commit()
        report = validate_graph(db)
        codes = [i.code for i in report.issues]
        assert "INVALID_LINE_RANGE" in codes

    def test_end_lt_start(self, db: GraphDB):
        db.upsert_node(Node(id="a.py:bad", name="bad", kind="function", file_path="a.py", line_start=10, line_end=5))
        db.conn.commit()
        report = validate_graph(db)
        codes = [i.code for i in report.issues]
        assert "INVALID_LINE_RANGE" in codes

    def test_zero_default_is_valid(self, db: GraphDB):
        db.upsert_node(Node(id="a.py:ok", name="ok", kind="function", file_path="a.py", line_start=0, line_end=0))
        db.conn.commit()
        report = validate_graph(db)
        codes = [i.code for i in report.issues]
        assert "INVALID_LINE_RANGE" not in codes


class TestDuplicateLogicalSymbol:
    def test_duplicate_detected(self, db: GraphDB):
        db.conn.execute(
            "INSERT INTO nodes (id, file_path, name, kind, parent_id) VALUES (?, ?, ?, ?, ?)",
            ["a.py:dup1", "a.py", "dup", "function", None],
        )
        db.conn.execute(
            "INSERT INTO nodes (id, file_path, name, kind, parent_id) VALUES (?, ?, ?, ?, ?)",
            ["a.py:dup2", "a.py", "dup", "function", None],
        )
        db.conn.commit()
        report = validate_graph(db)
        codes = [i.code for i in report.issues]
        assert "DUPLICATE_LOGICAL_SYMBOL" in codes

    def test_synthetic_kinds_excluded(self, db: GraphDB):
        db.conn.execute(
            "INSERT INTO nodes (id, file_path, name, kind) VALUES (?, ?, ?, ?)",
            ["a.py:file1", "a.py", "a.py", "file"],
        )
        db.conn.execute(
            "INSERT INTO nodes (id, file_path, name, kind) VALUES (?, ?, ?, ?)",
            ["a.py:file2", "a.py", "a.py", "file"],
        )
        db.conn.commit()
        report = validate_graph(db)
        codes = [i.code for i in report.issues]
        assert "DUPLICATE_LOGICAL_SYMBOL" not in codes


class TestSchemaVersionMismatch:
    def test_mismatch_detected(self, db: GraphDB):
        db.conn.execute("INSERT INTO schema_meta (version) VALUES (?)", [CURRENT_SCHEMA_VERSION + 1])
        db.conn.commit()
        report = validate_graph(db)
        codes = [i.code for i in report.issues]
        assert "SCHEMA_VERSION_MISMATCH" in codes

    def test_match_no_issue(self, db: GraphDB):
        report = validate_graph(db)
        codes = [i.code for i in report.issues]
        assert "SCHEMA_VERSION_MISMATCH" not in codes


class TestParserError:
    def test_parser_error_detected(self, db: GraphDB):
        db.conn.execute(
            "INSERT INTO files (path, language, content_hash, error) VALUES (?, ?, ?, ?)",
            ["broken.py", "python", "", "SyntaxError: invalid syntax"],
        )
        db.conn.commit()
        report = validate_graph(db)
        codes = [i.code for i in report.issues]
        assert "PARSER_ERROR" in codes

    def test_parser_error_not_triggered_for_empty_error(self, db: GraphDB):
        db.conn.execute(
            "INSERT INTO files (path, language, content_hash) VALUES (?, ?, ?)",
            ["clean.py", "python", "abc"],
        )
        db.conn.commit()
        report = validate_graph(db)
        codes = [i.code for i in report.issues]
        assert "PARSER_ERROR" not in codes


class TestExistingFieldsPreserved:
    def test_existing_fields_present(self, db: GraphDB):
        db.upsert_node(Node(id="a.py:foo", name="foo", kind="function", file_path="a.py", line_start=1))
        db.conn.execute(
            "INSERT INTO edges (source_id, target_id, kind) VALUES (?, ?, ?)",
            ["a.py:foo", "a.py:foo", "calls"],
        )
        db.conn.commit()
        report = validate_graph(db)
        assert hasattr(report, "total_nodes")
        assert hasattr(report, "total_edges")
        assert hasattr(report, "total_files")
        assert hasattr(report, "by_kind")
        assert hasattr(report, "by_edge_kind")
        assert hasattr(report, "by_language")
        assert hasattr(report, "nodes_with_parent")
        assert hasattr(report, "orphan_parent_refs")
        assert hasattr(report, "orphan_edges")
        assert hasattr(report, "issues")
        assert report.total_nodes >= 1
        assert report.total_edges >= 1

    def test_summary_contains_expected_substrings(self, db: GraphDB):
        db.upsert_node(Node(id="a.py:foo", name="foo", kind="function", file_path="a.py", line_start=1))
        db.conn.commit()
        report = validate_graph(db)
        summary = report.summary()
        assert "Files:" in summary
        assert "Symbols:" in summary
        assert "Edges:" in summary
        assert "By kind:" in summary
        assert "function:" in summary

    def test_summary_includes_issues(self, db: GraphDB):
        db.conn.execute(
            "INSERT INTO files (path, language, content_hash, error) VALUES (?, ?, ?, ?)",
            ["bad.py", "python", "", "boom"],
        )
        db.conn.commit()
        report = validate_graph(db)
        summary = report.summary()
        assert "Issues:" in summary
        assert "PARSER_ERROR" in summary

    def test_importable_from_graph(self):
        from codepulse.graph import ValidationReport as GraphReport
        from codepulse.validation import ValidationReport as ValReport
        assert GraphReport is ValReport
