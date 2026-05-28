"""Graph integrity tests: orphan detection, duplicate resilience, reindex consistency."""

import tempfile
from pathlib import Path

import pytest

from codepulse.config import CodePulseConfig
from codepulse.graph import CodePulse
from codepulse.db import GraphDB, Node, Edge


@pytest.fixture
def fresh_db():
    """A fresh DB with no orphan edges."""
    with tempfile.TemporaryDirectory() as tmp:
        config = CodePulseConfig(data_dir=tmp)
        cp = CodePulse(config)
        db = cp.db
        db.upsert_node(Node(id="a.py:foo", name="foo", kind="function", file_path="a.py", line_start=1, language="python"))
        db.upsert_node(Node(id="a.py:bar", name="bar", kind="function", file_path="a.py", line_start=5, language="python"))
        db.conn.execute("INSERT INTO edges (source_id, target_id, kind) VALUES (?, ?, ?)",
                        ["a.py:foo", "a.py:bar", "calls"])
        db.conn.commit()
        yield cp, db


class TestOrphanEdges:
    """validate() must detect edges whose source or target doesn't match any node."""

    def test_zero_orphans_on_clean_graph(self, fresh_db):
        cp, _ = fresh_db
        report = cp.validate()
        assert report.orphan_edges == 0

    def test_orphan_source_detected(self, fresh_db):
        cp, db = fresh_db
        db.conn.execute("INSERT INTO edges (source_id, target_id, kind) VALUES (?, ?, ?)",
                        ["nonexistent", "a.py:bar", "calls"])
        db.conn.commit()
        report = cp.validate()
        assert report.orphan_edges >= 1

    def test_orphan_target_detected(self, fresh_db):
        cp, db = fresh_db
        db.conn.execute("INSERT INTO edges (source_id, target_id, kind) VALUES (?, ?, ?)",
                        ["a.py:foo", "nonexistent", "calls"])
        db.conn.commit()
        report = cp.validate()
        assert report.orphan_edges >= 1

    def test_both_ends_orphan_detected(self, fresh_db):
        cp, db = fresh_db
        db.conn.execute("INSERT INTO edges (source_id, target_id, kind) VALUES (?, ?, ?)",
                        ["ghost", "phantom", "calls"])
        db.conn.commit()
        report = cp.validate()
        assert report.orphan_edges >= 1

    def test_orphan_count_is_accurate(self, fresh_db):
        cp, db = fresh_db
        db.conn.execute("INSERT INTO edges (source_id, target_id, kind) VALUES (?, ?, ?)",
                        ["a.py:foo", "missing1", "calls"])
        db.conn.execute("INSERT INTO edges (source_id, target_id, kind) VALUES (?, ?, ?)",
                        ["missing2", "a.py:bar", "calls"])
        db.conn.commit()
        report = cp.validate()
        assert report.orphan_edges == 2

    @pytest.mark.xfail(reason="Edges store file_path as source_id, not node IDs — no edges match nodes")
    def test_validate_on_fixtures_yields_zero_orphans(self):
        """Indexing real fixture files should produce zero orphan edges.
        XFAIL: known limitation — edge source_id is file_path, not node ID."""
        with tempfile.TemporaryDirectory() as tmp:
            config = CodePulseConfig(data_dir=tmp)
            cp = CodePulse(config)
            fixtures = Path(__file__).parent / "fixtures"
            cp.index_all(str(fixtures))
            report = cp.validate()
            assert report.orphan_edges == 0, (
                f"Fixture indexing produced {report.orphan_edges} orphan edges"
            )


class TestBulkImportIntegrity:
    """bulk_import must handle duplicates and maintain graph integrity."""

    def test_bulk_import_no_duplicate_nodes(self, fresh_db):
        cp, db = fresh_db
        count_before = db.conn.execute("SELECT COUNT(*) FROM nodes").fetchone()[0]
        db.bulk_import(
            [Node(id="a.py:foo", name="foo", kind="function", file_path="a.py", line_start=1, language="python")],
            [],
        )
        count_after = db.conn.execute("SELECT COUNT(*) FROM nodes").fetchone()[0]
        assert count_after == count_before, "bulk_import created duplicate node"

    def test_bulk_import_adds_new_nodes(self, fresh_db):
        cp, db = fresh_db
        count_before = db.conn.execute("SELECT COUNT(*) FROM nodes").fetchone()[0]
        db.bulk_import(
            [Node(id="a.py:baz", name="baz", kind="function", file_path="a.py", line_start=10, language="python")],
            [],
        )
        count_after = db.conn.execute("SELECT COUNT(*) FROM nodes").fetchone()[0]
        assert count_after == count_before + 1


class TestReindexConsistency:
    """Re-indexing must clean up stale nodes and edges for files that disappear."""

    def test_reindex_removes_deleted_file_nodes(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = CodePulseConfig(data_dir=tmp)
            cp = CodePulse(config)
            src = Path(tmp) / "src"
            src.mkdir()
            keep_file = src / "keep.py"
            keep_file.write_text("def keep(): pass\n")
            gone_file = src / "gone.py"
            gone_file.write_text("def gone(): pass\n")
            cp.index_all(str(src))
            # Verify both indexed
            assert cp.search("keep")
            assert cp.search("gone")
            # Delete gone.py and re-index
            gone_file.unlink()
            cp.index_all(str(src))
            # gone should be removed; keep should still exist
            assert cp.search("keep"), "Existing symbol removed during reindex"
            gone_nodes = cp.db.conn.execute(
                "SELECT COUNT(*) FROM nodes WHERE file_path LIKE ?", [f"%gone%"]
            ).fetchone()[0]
            assert gone_nodes == 0, f"Stale node from deleted file survived reindex ({gone_nodes})"

    def test_reindex_counts_are_consistent(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = CodePulseConfig(data_dir=tmp)
            cp = CodePulse(config)
            src = Path(tmp) / "src"
            src.mkdir()
            f = src / "test.py"
            f.write_text("def foo(): pass\ndef bar(): pass\n")
            r1 = cp.index_all(str(src))
            r2 = cp.index_all(str(src))
            assert r1.symbols_found == r2.symbols_found
            assert r1.files_indexed == r2.files_indexed
