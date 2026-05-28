"""Schema migration tests.

Verifies that:
- A new DB creates schema_meta with current version.
- Existing DBs missing new edge columns are migrated in place.
- Edges stores metadata, line_start, line_end, column_start, column_end, confidence, provenance.
- Multiple callsites between the same source and target can be preserved.
"""

import os
import tempfile

import pytest

from codepulse.db import GraphDB, Node, Edge
from codepulse.schema import CURRENT_SCHEMA_VERSION, _get_columns


@pytest.fixture
def fresh_db():
    db_path = os.path.join(tempfile.mkdtemp(), "fresh.db")
    db = GraphDB(db_path)
    db.initialize()
    yield db
    db.close()


def test_new_db_creates_schema_meta(fresh_db: GraphDB):
    version = fresh_db.conn.execute(
        "SELECT MAX(version) FROM schema_meta"
    ).fetchone()[0]
    assert version == CURRENT_SCHEMA_VERSION


def test_new_db_has_edge_columns(fresh_db: GraphDB):
    cols = _get_columns(fresh_db.conn, "edges")
    for col in ("metadata", "line_start", "line_end", "column_start",
                "column_end", "confidence", "provenance", "resolution_status"):
        assert col in cols, f"Missing column: {col}"


def test_existing_db_migrates_columns():
    db_path = os.path.join(tempfile.mkdtemp(), "old_schema.db")
    conn = GraphDB(db_path)

    conn.conn.executescript("""
        CREATE TABLE IF NOT EXISTS schema_meta (
            version INTEGER PRIMARY KEY,
            applied_at TEXT DEFAULT (datetime('now'))
        );
        INSERT INTO schema_meta (version) VALUES (0);

        CREATE TABLE IF NOT EXISTS edges (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_id TEXT NOT NULL,
            target_id TEXT NOT NULL,
            kind TEXT NOT NULL,
            file_path TEXT DEFAULT '',
            line_number INTEGER DEFAULT 0,
            UNIQUE(source_id, target_id, kind)
        );

        CREATE INDEX IF NOT EXISTS idx_edges_source ON edges(source_id);
        CREATE INDEX IF NOT EXISTS idx_edges_target ON edges(target_id);
    """)
    conn.conn.commit()
    conn.close()

    db = GraphDB(db_path)
    db.initialize()

    cols = _get_columns(db.conn, "edges")
    for col in ("metadata", "line_start", "confidence", "provenance", "resolution_status"):
        assert col in cols, f"Missing migrated column: {col}"

    version = db.conn.execute(
        "SELECT MAX(version) FROM schema_meta"
    ).fetchone()[0]
    assert version == CURRENT_SCHEMA_VERSION
    db.close()


def test_edge_stores_metadata_and_range(fresh_db: GraphDB):
    a = Node(id="a.py:A", file_path="a.py", name="A", kind="function")
    b = Node(id="a.py:B", file_path="a.py", name="B", kind="function")
    fresh_db.upsert_node(a)
    fresh_db.upsert_node(b)

    fresh_db.upsert_edge(Edge(
        source_id="a.py:A", target_id="a.py:B", kind="calls",
        file_path="a.py", line_number=10,
        metadata={"call_site": "test"},
        line_start=10, line_end=10, column_start=5, column_end=20,
        confidence=0.95, provenance="test", resolution_status="resolved",
    ))

    row = fresh_db.conn.execute(
        "SELECT * FROM edges WHERE source_id=? AND target_id=? AND kind=?",
        ("a.py:A", "a.py:B", "calls"),
    ).fetchone()
    assert row is not None
    assert '"call_site": "test"' in row["metadata"]
    assert row["line_start"] == 10
    assert row["line_end"] == 10
    assert row["column_start"] == 5
    assert row["column_end"] == 20
    assert row["confidence"] == 0.95
    assert row["provenance"] == "test"
    assert row["resolution_status"] == "resolved"


def test_multiple_callsites_preserved(fresh_db: GraphDB):
    a = Node(id="a.py:A", file_path="a.py", name="A", kind="function")
    b = Node(id="a.py:B", file_path="a.py", name="B", kind="function")
    fresh_db.upsert_node(a)
    fresh_db.upsert_node(b)

    fresh_db.upsert_edge(Edge(
        source_id="a.py:A", target_id="a.py:B", kind="calls",
        file_path="a.py", line_number=5,
        line_start=5, column_start=1,
    ))
    fresh_db.upsert_edge(Edge(
        source_id="a.py:A", target_id="a.py:B", kind="calls",
        file_path="a.py", line_number=15,
        line_start=15, column_start=1,
    ))

    rows = fresh_db.conn.execute(
        "SELECT * FROM edges WHERE source_id=? AND target_id=? AND kind=?",
        ("a.py:A", "a.py:B", "calls"),
    ).fetchall()
    assert len(rows) == 2, f"Expected 2 rows for different callsites, got {len(rows)}"


def test_old_schema_preserves_edge_data():
    db_path = os.path.join(tempfile.mkdtemp(), "old_edge.db")
    conn = GraphDB(db_path)

    conn.conn.executescript("""
        CREATE TABLE IF NOT EXISTS schema_meta (
            version INTEGER PRIMARY KEY,
            applied_at TEXT DEFAULT (datetime('now'))
        );
        INSERT INTO schema_meta (version) VALUES (0);

        CREATE TABLE IF NOT EXISTS edges (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_id TEXT NOT NULL,
            target_id TEXT NOT NULL,
            kind TEXT NOT NULL,
            file_path TEXT DEFAULT '',
            line_number INTEGER DEFAULT 0,
            UNIQUE(source_id, target_id, kind)
        );

        CREATE INDEX IF NOT EXISTS idx_edges_source ON edges(source_id);
        CREATE INDEX IF NOT EXISTS idx_edges_target ON edges(target_id);

        INSERT INTO edges (source_id, target_id, kind, file_path, line_number)
        VALUES ('mod.py:A', 'mod.py:B', 'calls', 'mod.py', 10);
    """)
    conn.conn.commit()
    conn.close()

    db = GraphDB(db_path)
    db.initialize()

    row = db.conn.execute(
        "SELECT source_id, target_id, kind, file_path, line_number FROM edges"
    ).fetchone()
    assert row is not None, "Edge row should exist after migration"
    assert row["source_id"] == "mod.py:A"
    assert row["target_id"] == "mod.py:B"
    assert row["kind"] == "calls"
    assert row["line_number"] == 10

    version = db.conn.execute(
        "SELECT MAX(version) FROM schema_meta"
    ).fetchone()[0]
    assert version == CURRENT_SCHEMA_VERSION
    db.close()


def test_initialize_idempotent_after_migration():
    db_path = os.path.join(tempfile.mkdtemp(), "old_idem.db")
    conn = GraphDB(db_path)

    conn.conn.executescript("""
        CREATE TABLE IF NOT EXISTS schema_meta (
            version INTEGER PRIMARY KEY,
            applied_at TEXT DEFAULT (datetime('now'))
        );
        INSERT INTO schema_meta (version) VALUES (0);

        CREATE TABLE IF NOT EXISTS edges (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_id TEXT NOT NULL,
            target_id TEXT NOT NULL,
            kind TEXT NOT NULL,
            file_path TEXT DEFAULT '',
            line_number INTEGER DEFAULT 0,
            UNIQUE(source_id, target_id, kind)
        );

        INSERT INTO edges (source_id, target_id, kind, file_path, line_number)
        VALUES ('mod.py:A', 'mod.py:B', 'calls', 'mod.py', 10);
    """)
    conn.conn.commit()
    conn.close()

    db = GraphDB(db_path)
    db.initialize()
    db.initialize()

    rows = db.conn.execute("SELECT * FROM edges").fetchall()
    assert len(rows) == 1, "Edge data should survive double initialize"

    version = db.conn.execute(
        "SELECT MAX(version) FROM schema_meta"
    ).fetchone()[0]
    assert version == CURRENT_SCHEMA_VERSION
    db.close()


def test_row_to_edge_helper(fresh_db: GraphDB):
    a = Node(id="a.py:A", file_path="a.py", name="A", kind="function")
    b = Node(id="a.py:B", file_path="a.py", name="B", kind="function")
    fresh_db.upsert_node(a)
    fresh_db.upsert_node(b)

    fresh_db.upsert_edge(Edge(
        source_id="a.py:A", target_id="a.py:B", kind="calls",
        file_path="a.py", line_number=5, line_start=5,
        metadata={"key": "val"}, confidence=0.9,
    ))

    row = fresh_db.conn.execute(
        "SELECT * FROM edges WHERE source_id=? AND target_id=? AND kind=?",
        ("a.py:A", "a.py:B", "calls"),
    ).fetchone()
    edge = GraphDB._row_to_edge(row)
    assert edge.source_id == "a.py:A"
    assert edge.target_id == "a.py:B"
    assert edge.kind == "calls"
    assert edge.metadata == {"key": "val"}
    assert edge.confidence == 0.9


def test_version_current_but_edges_table_old():
    """DB with current schema_meta but old edges table must be repaired."""
    db_path = os.path.join(tempfile.mkdtemp(), "missing_cols_current_version.db")
    conn = GraphDB(db_path)

    conn.conn.executescript("""
        CREATE TABLE IF NOT EXISTS schema_meta (
            version INTEGER PRIMARY KEY,
            applied_at TEXT DEFAULT (datetime('now'))
        );
        INSERT INTO schema_meta (version) VALUES (1);

        CREATE TABLE IF NOT EXISTS edges (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_id TEXT NOT NULL,
            target_id TEXT NOT NULL,
            kind TEXT NOT NULL,
            file_path TEXT DEFAULT '',
            line_number INTEGER DEFAULT 0,
            UNIQUE(source_id, target_id, kind)
        );

        CREATE INDEX IF NOT EXISTS idx_edges_source ON edges(source_id);
        CREATE INDEX IF NOT EXISTS idx_edges_target ON edges(target_id);

        INSERT INTO edges (source_id, target_id, kind, file_path, line_number)
        VALUES ('mod.py:A', 'mod.py:B', 'calls', 'mod.py', 10);
    """)
    conn.conn.commit()
    conn.close()

    db = GraphDB(db_path)
    db.initialize()

    cols = _get_columns(db.conn, "edges")
    for col in ("provenance", "resolution_status", "confidence", "metadata",
                "line_start", "line_end", "column_start", "column_end"):
        assert col in cols, f"Missing column: {col}"

    indexes = db.conn.execute(
        "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='edges'"
    ).fetchall()
    assert "idx_edges_reconciliation" in [r["name"] for r in indexes]

    row = db.conn.execute("SELECT * FROM edges").fetchone()
    assert row["source_id"] == "mod.py:A"
    assert row["provenance"] == "tree-sitter"

    db.close()


def test_edge_defaults_used_when_not_provided(fresh_db: GraphDB):
    a = Node(id="a.py:A", file_path="a.py", name="A", kind="function")
    b = Node(id="a.py:B", file_path="a.py", name="B", kind="function")
    fresh_db.upsert_node(a)
    fresh_db.upsert_node(b)

    fresh_db.upsert_edge(Edge(source_id="a.py:A", target_id="a.py:B", kind="calls"))

    row = fresh_db.conn.execute(
        "SELECT * FROM edges WHERE source_id=? AND target_id=? AND kind=?",
        ("a.py:A", "a.py:B", "calls"),
    ).fetchone()
    assert row is not None
    assert row["metadata"] == "{}"
    assert row["line_start"] == 0
    assert row["line_end"] == 0
    assert row["column_start"] == 0
    assert row["column_end"] == 0
    assert row["confidence"] == 1.0
    assert row["provenance"] == "tree-sitter"
    assert row["resolution_status"] == "resolved"
