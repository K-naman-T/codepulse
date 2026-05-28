"""Import edge tests: file nodes, external nodes, zero orphan edges."""

import tempfile
from pathlib import Path

from codepulse.config import CodePulseConfig
from codepulse.db import GraphDB, Node, Edge
from codepulse.graph import CodePulse
from codepulse.ids import file_node_id, external_node_id
from codepulse.parser import SourceParser


def test_parse_file_emits_file_node():
    parser = SourceParser()
    src_dir = Path(tempfile.mkdtemp())
    f = src_dir / "test.py"
    f.write_text("x = 1\n")
    symbols, refs = parser.parse_file(str(f))
    file_nodes = [n for n in symbols if n.kind == "file"]
    assert len(file_nodes) == 1
    assert file_nodes[0].id == file_node_id(str(f))


def test_import_edge_source_is_file_node():
    parser = SourceParser()
    src_dir = Path(tempfile.mkdtemp())
    f = src_dir / "test.py"
    f.write_text("import os\n")
    symbols, refs = parser.parse_file(str(f))
    import_edges = [e for e in refs if e.kind == "imports"]
    assert len(import_edges) >= 1
    expected_source = file_node_id(str(f))
    for edge in import_edges:
        assert edge.source_id == expected_source, (
            f"Expected source {expected_source}, got {edge.source_id}"
        )


def test_external_import_target_is_external_node():
    parser = SourceParser()
    src_dir = Path(tempfile.mkdtemp())
    f = src_dir / "test.py"
    f.write_text("import os\n")
    symbols, refs = parser.parse_file(str(f))
    import_edges = [e for e in refs if e.kind == "imports"]
    assert len(import_edges) >= 1
    for edge in import_edges:
        assert edge.target_id.startswith("external:"), (
            f"Expected external target, got {edge.target_id}"
        )


def test_external_node_emitted_for_import_target():
    parser = SourceParser()
    src_dir = Path(tempfile.mkdtemp())
    f = src_dir / "test.py"
    f.write_text("import os\n")
    symbols, refs = parser.parse_file(str(f))
    ext_nodes = [n for n in symbols if n.kind == "external_module"]
    assert len(ext_nodes) >= 1
    ext_ids = {n.id for n in ext_nodes}
    assert external_node_id("module", "os") in ext_ids


def test_orphan_edges_zero_for_import_fixture():
    with tempfile.TemporaryDirectory() as tmp:
        config = CodePulseConfig(data_dir=tmp)
        cp = CodePulse(config)
        fixtures = Path(__file__).parent / "fixtures"
        cp.index_all(str(fixtures))
        report = cp.validate()
        assert report.orphan_edges == 0, (
            f"Fixture indexing produced {report.orphan_edges} orphan edges"
        )


def test_file_node_exists_for_indexed_file():
    with tempfile.TemporaryDirectory() as tmp:
        config = CodePulseConfig(data_dir=tmp)
        cp = CodePulse(config)
        fixtures = Path(__file__).parent / "fixtures"
        cp.index_all(str(fixtures))
        report = cp.validate()
        assert report.by_kind.get("file", 0) >= 1


def _db_with_synthetic_and_real() -> GraphDB:
    """Helper: create a GraphDB with both synthetic and real nodes."""
    import tempfile as _tf
    tmp = _tf.mkdtemp()
    db = GraphDB(str(Path(tmp) / "test.db"))
    db.initialize()
    real = Node(id="mod.py:func", file_path="mod.py", name="func", kind="function")
    file_node = Node(id="mod.py", file_path="mod.py", name="mod.py", kind="file")
    ext = Node(id="external:module:os", file_path="mod.py", name="os", kind="external_module")
    unresolved = Node(id="unresolved:calls:foo", file_path="mod.py", name="foo", kind="unresolved_symbol")
    for n in [real, file_node, ext, unresolved]:
        db.upsert_node(n)
    db.upsert_edge(Edge(source_id="mod.py:func", target_id="mod.py:func", kind="calls"))
    return db


def test_search_nodes_excludes_synthetic_by_default():
    db = _db_with_synthetic_and_real()
    try:
        results = db.search_nodes("")
        names = {r.name for r in results}
        assert "func" in names
        assert "mod.py" not in names
        assert "os" not in names
        assert "foo" not in names

        file_results = db.search_nodes("", kind="file")
        assert len(file_results) == 1
        assert file_results[0].kind == "file"
    finally:
        db.close()


def test_get_node_rankings_excludes_synthetic():
    db = _db_with_synthetic_and_real()
    try:
        rankings = db.get_node_rankings()
        ranking_ids = {n.id for n, _ in rankings}
        assert "mod.py:func" in ranking_ids
        assert "mod.py" not in ranking_ids
        assert "external:module:os" not in ranking_ids
        assert "unresolved:calls:foo" not in ranking_ids
    finally:
        db.close()


def test_get_file_summary_excludes_synthetic_from_symbol_count():
    with tempfile.TemporaryDirectory() as tmp:
        db_path = str(Path(tmp) / "test.db")
        db = GraphDB(db_path)
        db.initialize()
        try:
            file_node = Node(id="mod.py", file_path="mod.py", name="mod.py", kind="file")
            real = Node(id="mod.py:func", file_path="mod.py", name="func", kind="function")
            db.upsert_node(file_node)
            db.upsert_node(real)

            empty_file = Node(id="empty.py", file_path="empty.py", name="empty.py", kind="file")
            db.upsert_node(empty_file)

            summary = db.get_file_summary(limit=10)
            summaries = {s["file"]: s for s in summary}

            assert "mod.py" in summaries
            assert summaries["mod.py"]["symbols"] == 1

            assert "empty.py" in summaries
            assert summaries["empty.py"]["symbols"] == 0
        finally:
            db.close()


def test_get_top_symbols_with_context_excludes_synthetic():
    db = _db_with_synthetic_and_real()
    try:
        results = db.get_top_symbols_with_context()
        names = {r["name"] for r in results}
        assert "func" in names
        assert "mod.py" not in names
        assert "os" not in names
        assert "foo" not in names
    finally:
        db.close()


def test_get_nodes_by_file_excludes_synthetic_by_default():
    db = _db_with_synthetic_and_real()
    try:
        results = db.get_nodes_by_file("mod.py")
        names = {r.name for r in results}
        assert "func" in names
        assert "mod.py" not in names

        all_nodes = db.get_nodes_by_file("mod.py", include_synthetic=True)
        all_names = {r.name for r in all_nodes}
        assert "func" in all_names
        assert "mod.py" in all_names
    finally:
        db.close()
