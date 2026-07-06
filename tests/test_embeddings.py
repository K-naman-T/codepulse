"""Tests for incremental and validated embeddings."""

import hashlib
import struct
from typing import Generator

import pytest

from codepulse.db import GraphDB, Node
from codepulse.embeddings import index_embeddings, serialize_vector
from codepulse.validation import validate_graph


# ---------------------------------------------------------------------------
# A fake embedder that returns deterministic vectors
# ---------------------------------------------------------------------------

def _fake_embedder(texts: list[str]) -> list[list[float]]:
    """Deterministic fake: each text → a 4-d vector derived from its hash."""
    out = []
    for t in texts:
        h = hashlib.md5(t.encode()).digest()
        vec = [b / 255.0 for b in h[:4]]
        out.append(vec)
    return out


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def db_with_nodes(db: GraphDB) -> GraphDB:
    """Populate a few non-synthetic nodes."""
    for i, (nid, kind) in enumerate([
        ("mod.py:fn_a", "function"),
        ("mod.py:fn_b", "function"),
        ("mod.py:Klass", "class"),
    ]):
        db.upsert_node(Node(
            id=nid,
            file_path="mod.py",
            name=nid.split(":")[1],
            kind=kind,
            signature=f"def {nid.split(':')[1]}(): ..." if kind == "function"
                        else f"class {nid.split(':')[1]}: ...",
            line_start=(i + 1) * 10,
            line_end=(i + 1) * 10 + 5,
        ))
    return db


# ---------------------------------------------------------------------------
# Tests: model name and dimension storage
# ---------------------------------------------------------------------------

class TestModelAndDimensionStorage:
    def test_stores_actual_model_name(self, db_with_nodes, monkeypatch):
        monkeypatch.setattr("codepulse.embeddings.get_embedder", lambda backend="local", model=None: _fake_embedder)
        count = index_embeddings(db_with_nodes, backend="local", model="all-MiniLM-L6-v2")
        assert count == 3
        rows = db_with_nodes.conn.execute(
            "SELECT DISTINCT model FROM embeddings"
        ).fetchall()
        models = [r["model"] for r in rows]
        assert "all-MiniLM-L6-v2" in models
        assert "local" not in models

    def test_stores_correct_dimensions(self, db_with_nodes, monkeypatch):
        monkeypatch.setattr("codepulse.embeddings.get_embedder", lambda backend="local", model=None: _fake_embedder)
        index_embeddings(db_with_nodes, backend="local", model="test-model")
        rows = db_with_nodes.conn.execute(
            "SELECT dimensions FROM embeddings"
        ).fetchall()
        for r in rows:
            assert r["dimensions"] == 4, f"Expected 4-d vector, got {r['dimensions']}"


# ---------------------------------------------------------------------------
# Tests: skip unchanged nodes
# ---------------------------------------------------------------------------

class TestSkipUnchangedNodes:
    def test_synthetic_nodes_are_not_embedded(self, db: GraphDB, monkeypatch):
        db.upsert_node(Node(
            id="file:///mod.py",
            file_path="mod.py",
            name="mod.py",
            kind="file",
            line_start=1,
            line_end=1,
        ))
        monkeypatch.setattr("codepulse.embeddings.get_embedder",
                            lambda backend="local", model=None: _fake_embedder)

        assert index_embeddings(db, backend="local", model="m1") == 0
        row = db.conn.execute("SELECT COUNT(*) as cnt FROM embeddings").fetchone()
        assert row["cnt"] == 0

    def test_skip_when_content_and_model_match(self, db_with_nodes, monkeypatch):
        call_count = 0

        def counting_embedder(texts):
            nonlocal call_count
            call_count += 1
            return _fake_embedder(texts)

        monkeypatch.setattr("codepulse.embeddings.get_embedder",
                            lambda backend="local", model=None: counting_embedder)

        # First pass: embed all 3 nodes
        count1 = index_embeddings(db_with_nodes, backend="local", model="m1")
        assert count1 == 3
        assert call_count == 1  # one batch call

        # Second pass: nothing changed, should skip all
        call_count = 0
        monkeypatch.setattr("codepulse.embeddings.get_embedder",
                            lambda backend="local", model=None: counting_embedder)
        count2 = index_embeddings(db_with_nodes, backend="local", model="m1")
        assert count2 == 0  # nothing new embedded
        assert call_count == 0  # embedder never called

    def test_skip_when_content_and_model_match_does_not_load_embedder(self, db_with_nodes, monkeypatch):
        monkeypatch.setattr("codepulse.embeddings.get_embedder",
                            lambda backend="local", model=None: _fake_embedder)
        index_embeddings(db_with_nodes, backend="local", model="m1")

        def fail_get_embedder(backend="local", model=None):
            raise AssertionError("embedder should not be loaded when all nodes are unchanged")

        monkeypatch.setattr("codepulse.embeddings.get_embedder", fail_get_embedder)
        assert index_embeddings(db_with_nodes, backend="local", model="m1") == 0

    def test_reembed_when_model_changes(self, db_with_nodes, monkeypatch):
        monkeypatch.setattr("codepulse.embeddings.get_embedder",
                            lambda backend="local", model=None: _fake_embedder)
        index_embeddings(db_with_nodes, backend="local", model="m1")

        monkeypatch.setattr("codepulse.embeddings.get_embedder",
                            lambda backend="local", model=None: _fake_embedder)
        count2 = index_embeddings(db_with_nodes, backend="local", model="m2")
        assert count2 == 3

    def test_reembed_when_node_content_changes(self, db_with_nodes, monkeypatch):
        monkeypatch.setattr("codepulse.embeddings.get_embedder",
                            lambda backend="local", model=None: _fake_embedder)
        index_embeddings(db_with_nodes, backend="local", model="m1")

        # Change a node's signature
        db_with_nodes.upsert_node(Node(
            id="mod.py:fn_a",
            file_path="mod.py",
            name="fn_a",
            kind="function",
            signature="def fn_a(new_sig): ...",
            line_start=10,
            line_end=15,
        ))

        monkeypatch.setattr("codepulse.embeddings.get_embedder",
                            lambda backend="local", model=None: _fake_embedder)
        count2 = index_embeddings(db_with_nodes, backend="local", model="m1")
        assert count2 == 1  # only the changed node

    def test_only_unchanged_skipped(self, db_with_nodes, monkeypatch):
        monkeypatch.setattr("codepulse.embeddings.get_embedder",
                            lambda backend="local", model=None: _fake_embedder)
        index_embeddings(db_with_nodes, backend="local", model="m1")

        # Add a new node
        db_with_nodes.upsert_node(Node(
            id="mod.py:fn_c",
            file_path="mod.py",
            name="fn_c",
            kind="function",
            signature="def fn_c(): ...",
            line_start=30,
            line_end=35,
        ))

        monkeypatch.setattr("codepulse.embeddings.get_embedder",
                            lambda backend="local", model=None: _fake_embedder)
        count2 = index_embeddings(db_with_nodes, backend="local", model="m1")
        assert count2 == 1  # only the new node


# ---------------------------------------------------------------------------
# Tests: validation issues for embeddings
# ---------------------------------------------------------------------------

class TestEmbeddingValidation:

    def test_nodes_without_embeddings_are_ok_because_embeddings_are_optional(self, db_with_nodes):
        report = validate_graph(db_with_nodes)
        codes = [i.code for i in report.issues]
        assert "MISSING_EMBEDDING" not in codes

    def test_embedding_for_missing_node_detected(self, db: GraphDB):
        db.conn.execute("PRAGMA foreign_keys=OFF")
        db.conn.execute(
            "INSERT INTO embeddings (node_id, vector, model, dimensions) VALUES (?, ?, ?, ?)",
            ("missing.py:ghost", serialize_vector([0.1, 0.2, 0.3, 0.4]), "m1", 4),
        )
        db.conn.commit()
        db.conn.execute("PRAGMA foreign_keys=ON")

        report = validate_graph(db)
        codes = [i.code for i in report.issues]
        assert "ORPHAN_EMBEDDING_NODE" in codes

    def test_inconsistent_dimensions_detected(self, db: GraphDB):
        db.upsert_node(Node(id="a.py:foo", name="foo", kind="function", file_path="a.py", line_start=1))
        db.upsert_node(Node(id="a.py:bar", name="bar", kind="function", file_path="a.py", line_start=10))
        # Insert embeddings with mismatched dimensions
        db.upsert_embedding("a.py:foo", serialize_vector([0.1, 0.2, 0.3, 0.4]), model="m1", dimensions=4)
        db.upsert_embedding("a.py:bar", serialize_vector([0.5, 0.6, 0.7]), model="m2", dimensions=3)
        report = validate_graph(db)
        codes = [i.code for i in report.issues]
        assert "EMBEDDING_DIMENSION_MISMATCH" in codes

    def test_vector_dimension_metadata_mismatch_detected(self, db: GraphDB):
        db.upsert_node(Node(id="a.py:foo", name="foo", kind="function", file_path="a.py", line_start=1))
        db.upsert_embedding("a.py:foo", serialize_vector([0.1, 0.2, 0.3]), model="m1", dimensions=4)

        report = validate_graph(db)
        codes = [i.code for i in report.issues]
        assert "EMBEDDING_DIMENSION_MISMATCH" in codes

    def test_consistent_dimensions_ok(self, db_with_nodes, monkeypatch):
        monkeypatch.setattr("codepulse.embeddings.get_embedder",
                            lambda backend="local", model=None: _fake_embedder)
        index_embeddings(db_with_nodes, backend="local", model="m1")
        report = validate_graph(db_with_nodes)
        codes = [i.code for i in report.issues]
        assert "EMBEDDING_DIMENSION_MISMATCH" not in codes
