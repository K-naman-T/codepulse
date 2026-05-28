"""SCIP reconciliation tests: verify SCIP edges override tree-sitter heuristic edges."""

import tempfile
import os
from pathlib import Path

import pytest

from codepulse.compat.scip import reconcile_scip_edges
from codepulse.db import GraphDB, Edge, Node


@pytest.fixture
def db():
    f = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    db_path = f.name
    f.close()
    gdb = GraphDB(db_path)
    gdb.initialize()
    yield gdb
    gdb.close()
    os.unlink(db_path)


class TestReconcileSCIPEdges:
    """Tests for reconcile_scip_edges()."""

    def test_reconcile_removes_tree_sitter_edge_at_same_location(self, db: GraphDB):
        db.upsert_edge(Edge(
            source_id="/test/main.ts:start",
            target_id="/test/main.ts:process",
            kind="calls",
            file_path="/test/main.ts",
            line_start=10,
            column_start=4,
            provenance="tree-sitter",
        ))
        db.upsert_edge(Edge(
            source_id="/test/main.ts:start",
            target_id="/test/helper.ts:Helper.process",
            kind="calls",
            file_path="/test/main.ts",
            line_start=10,
            column_start=4,
            provenance="scip",
            metadata={"scip_symbol": "pkg/Helper#process"},
        ))

        count = reconcile_scip_edges(db)
        assert count == 1, f"Expected 1 deletion, got {count}"

        rows = db.conn.execute("SELECT provenance, target_id FROM edges").fetchall()
        assert len(rows) == 1, f"Expected 1 edge remaining, got {len(rows)}"
        assert rows[0]["provenance"] == "scip"
        assert "Helper.process" in rows[0]["target_id"]

    def test_reconcile_preserves_tree_sitter_edge_without_scip_overlap(self, db: GraphDB):
        db.upsert_edge(Edge(
            source_id="/test/main.ts:start",
            target_id="/test/main.ts:local_func",
            kind="calls",
            file_path="/test/main.ts",
            line_start=5,
            column_start=2,
            provenance="tree-sitter",
        ))

        count = reconcile_scip_edges(db)
        assert count == 0, f"Expected 0 deletions, got {count}"

        rows = db.conn.execute("SELECT provenance, target_id FROM edges").fetchall()
        assert len(rows) == 1
        assert rows[0]["provenance"] == "tree-sitter"

    def test_reconcile_leaves_scip_edge_when_no_tree_sitter_overlap(self, db: GraphDB):
        db.upsert_edge(Edge(
            source_id="/test/main.ts:start",
            target_id="/test/helper.ts:Helper.process",
            kind="calls",
            file_path="/test/main.ts",
            line_start=10,
            column_start=4,
            provenance="scip",
            metadata={"scip_symbol": "pkg/Helper#process"},
        ))

        count = reconcile_scip_edges(db)
        assert count == 0, f"Expected 0 deletions, got {count}"

        rows = db.conn.execute("SELECT provenance FROM edges").fetchall()
        assert len(rows) == 1

    def test_reconcile_multiple_overlapping_edges(self, db: GraphDB):
        for i in range(3):
            db.upsert_edge(Edge(
                source_id=f"/test/main.ts:func{i}",
                target_id="/test/main.ts:bare_target",
                kind="calls",
                file_path="/test/main.ts",
                line_start=10 + i,
                column_start=4,
                provenance="tree-sitter",
            ))
        for i in range(3):
            db.upsert_edge(Edge(
                source_id=f"/test/main.ts:func{i}",
                target_id="/test/helper.ts:Qualified.target",
                kind="calls",
                file_path="/test/main.ts",
                line_start=10 + i,
                column_start=4,
                provenance="scip",
                metadata={"scip_symbol": f"pkg/target#{i}"},
            ))

        count = reconcile_scip_edges(db)
        assert count == 3, f"Expected 3 deletions, got {count}"

        rows = db.conn.execute("SELECT provenance FROM edges").fetchall()
        assert all(r["provenance"] == "scip" for r in rows)

    def test_reconcile_preserves_different_kind_at_same_location(self, db: GraphDB):
        """Different-kind tree-sitter and SCIP edges at the same location are both preserved."""
        db.upsert_edge(Edge(
            source_id="/test/main.ts:start", target_id="/test/main.ts:bare_proc",
            kind="calls", file_path="/test/main.ts", line_start=10, column_start=4,
            provenance="tree-sitter",
        ))
        db.upsert_edge(Edge(
            source_id="/test/main.ts:start", target_id="/test/helper.ts:Helper.process",
            kind="references", file_path="/test/main.ts", line_start=10, column_start=4,
            provenance="scip", metadata={"scip_symbol": "pkg/Helper#process"},
        ))
        count = reconcile_scip_edges(db)
        assert count == 0, f"Expected 0 deletions (kinds differ), got {count}"
        rows = db.conn.execute("SELECT provenance, kind FROM edges").fetchall()
        assert len(rows) == 2, f"Expected 2 edges, got {len(rows)}"

    def test_reconcile_removes_same_kind_at_same_location(self, db: GraphDB):
        """Same-kind tree-sitter edge at same (file,line,col) should still be removed."""
        db.upsert_edge(Edge(
            source_id="/test/main.ts:start", target_id="/test/main.ts:bare_proc",
            kind="calls", file_path="/test/main.ts", line_start=10, column_start=4,
            provenance="tree-sitter",
        ))
        db.upsert_edge(Edge(
            source_id="/test/main.ts:start", target_id="/test/helper.ts:Helper.process",
            kind="calls", file_path="/test/main.ts", line_start=10, column_start=4,
            provenance="scip", metadata={"scip_symbol": "pkg/Helper#process"},
        ))
        count = reconcile_scip_edges(db)
        assert count == 1, f"Expected 1 deletion, got {count}"
        rows = db.conn.execute("SELECT provenance FROM edges").fetchall()
        assert len(rows) == 1
        assert rows[0]["provenance"] == "scip"

    def test_reconcile_does_not_affect_non_overlapping_edges(self, db: GraphDB):
        db.upsert_edge(Edge(
            source_id="/test/main.ts:start",
            target_id="/test/main.ts:process",
            kind="calls",
            file_path="/test/main.ts",
            line_start=10,
            column_start=4,
            provenance="tree-sitter",
        ))
        db.upsert_edge(Edge(
            source_id="/test/main.ts:start",
            target_id="/test/main.ts:other_call",
            kind="calls",
            file_path="/test/main.ts",
            line_start=20,
            column_start=4,
            provenance="tree-sitter",
        ))
        db.upsert_edge(Edge(
            source_id="/test/main.ts:start",
            target_id="/test/helper.ts:Helper.process",
            kind="calls",
            file_path="/test/main.ts",
            line_start=10,
            column_start=4,
            provenance="scip",
            metadata={"scip_symbol": "pkg/Helper#process"},
        ))

        count = reconcile_scip_edges(db)
        assert count == 1, f"Expected 1 deletion, got {count}"

        rows = db.conn.execute("SELECT target_id FROM edges WHERE provenance='tree-sitter'").fetchall()
        remaining = [r["target_id"] for r in rows]
        assert any("other_call" in t for t in remaining), "Non-overlapping tree-sitter edge should remain"
        assert not any("process" in t and "Helper" not in t for t in remaining), "Overlapping tree-sitter edge should be removed"
