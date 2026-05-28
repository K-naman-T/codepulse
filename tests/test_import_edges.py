"""Import edge tests: file nodes, external nodes, zero orphan edges."""

import tempfile
from pathlib import Path

from codepulse.config import CodePulseConfig
from codepulse.db import Node, Edge
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
