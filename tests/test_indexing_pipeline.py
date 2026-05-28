"""Indexing pipeline safety and determinism tests.

Tests safe path deletion, edge-only files, and parser error resilience.
"""

import tempfile
from pathlib import Path

import pytest

from codepulse.config import CodePulseConfig
from codepulse.graph import CodePulse


class TestSafePathDeletion:
    """index_all must not delete data from sibling paths with common prefix."""

    def test_index_does_not_delete_sibling_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = CodePulseConfig(data_dir=tmp)
            cp = CodePulse(config)

            src = Path(tmp) / "src"
            src.mkdir()
            (src / "a.py").write_text("def foo(): pass\n")

            src_old = Path(tmp) / "src-old"
            src_old.mkdir()
            (src_old / "b.py").write_text("def bar(): pass\n")

            cp.index_all(str(src_old))
            bar_nodes = cp.db.conn.execute(
                "SELECT COUNT(*) FROM nodes WHERE name = 'bar'"
            ).fetchone()[0]
            assert bar_nodes > 0, "bar should be indexed from src-old"

            cp.index_all(str(src))

            foo_nodes = cp.db.conn.execute(
                "SELECT COUNT(*) FROM nodes WHERE name = 'foo'"
            ).fetchone()[0]
            assert foo_nodes > 0, "foo should be indexed from src"

            bar_nodes = cp.db.conn.execute(
                "SELECT COUNT(*) FROM nodes WHERE name = 'bar'"
            ).fetchone()[0]
            assert bar_nodes > 0, "bar from src-old must survive src reindex"


class TestEdgesWithoutSymbols:
    """Files with only import edges (no real symbols) must persist."""

    def test_imports_only_file_persists_file_node_and_edges(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = CodePulseConfig(data_dir=tmp)
            cp = CodePulse(config)

            src = Path(tmp) / "src"
            src.mkdir()
            (src / "main.py").write_text("import os\nimport sys\n")

            result = cp.index_all(str(src))
            assert result.files_indexed >= 1

            node_count = cp.db.conn.execute("SELECT COUNT(*) FROM nodes").fetchone()[0]
            assert node_count >= 3, "expected file node + 2 external module nodes"

            edge_count = cp.db.conn.execute("SELECT COUNT(*) FROM edges").fetchone()[0]
            assert edge_count >= 2, "expected 2 import edges"


class TestParserErrors:
    """A single bad file must not erase graph data for other files."""

    def test_bad_file_does_not_erase_existing_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = CodePulseConfig(data_dir=tmp)
            cp = CodePulse(config)

            src = Path(tmp) / "src"
            src.mkdir()
            good = src / "good.py"
            good.write_text("def hello(): pass\n")

            result = cp.index_all(str(src))
            assert result.files_indexed == 1
            assert len(result.errors) == 0

            hello_found = cp.db.conn.execute(
                "SELECT COUNT(*) FROM nodes WHERE name LIKE '%hello%'"
            ).fetchone()[0]
            assert hello_found > 0, "hello symbol must exist"

            bad = src / "bad.py"
            bad.write_bytes(b"\xff\xfe\x00\xff")

            result = cp.index_all(str(src))
            assert result.files_indexed >= 1
            assert len(result.errors) >= 1

            hello_found = cp.db.conn.execute(
                "SELECT COUNT(*) FROM nodes WHERE name LIKE '%hello%'"
            ).fetchone()[0]
            assert hello_found > 0, "hello symbol must survive bad file"

    def test_bad_file_recorded_in_files_table(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = CodePulseConfig(data_dir=tmp)
            cp = CodePulse(config)

            src = Path(tmp) / "src"
            src.mkdir()
            good = src / "good.py"
            good.write_text("def hello(): pass\n")
            bad = src / "bad.py"
            bad.write_bytes(b"\xff\xfe\x00\xff")

            result = cp.index_all(str(src))
            assert len(result.errors) >= 1, "bad file should produce error"

            error_rows = cp.db.conn.execute(
                "SELECT path, error FROM files WHERE error IS NOT NULL"
            ).fetchall()
            assert len(error_rows) >= 1
            found_bad = any(str(bad.resolve()) in row["path"] for row in error_rows)
            assert found_bad, "bad file should have error recorded in files table"

    def test_multiple_bad_files_all_record_errors(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = CodePulseConfig(data_dir=tmp)
            cp = CodePulse(config)

            src = Path(tmp) / "src"
            src.mkdir()
            (src / "good.py").write_text("def ok(): pass\n")
            (src / "bad1.py").write_bytes(b"\xff\xfe\x00\xff")
            (src / "bad2.py").write_bytes(b"\xff\xfe\x00\x00\x00")

            result = cp.index_all(str(src))
            assert result.files_indexed >= 1
            assert len(result.errors) >= 2

            ok_found = cp.db.conn.execute(
                "SELECT COUNT(*) FROM nodes WHERE name = 'ok'"
            ).fetchone()[0]
            assert ok_found > 0, "ok symbol must survive multiple bad files"
