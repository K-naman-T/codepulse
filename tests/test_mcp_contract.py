"""MCP tool contract tests.

Verifies each MCP tool returns correct results on a known graph.
Tests the tool logic directly without async/stdio transport.
"""

import os
import tempfile

import pytest

from codepulse.db import Edge, GraphDB, Node
from codepulse.graph import CodePulse, CodePulseConfig


@pytest.fixture
def cp():
    """CodePulse instance with a known graph."""
    tmp = tempfile.mkdtemp()
    config = CodePulseConfig(data_dir=tmp)
    cp = CodePulse(config)
    cp.db.initialize()

    nodes = [
        Node(id="/src/app.py:main", file_path="/src/app.py", name="main",
             kind="function", signature="def main(): ...", line_start=1, line_end=5),
        Node(id="/src/app.py:parse", file_path="/src/app.py", name="parse",
             kind="function", signature="def parse(data): ...", line_start=7, line_end=10),
        Node(id="/src/app.py:validate", file_path="/src/app.py", name="validate",
             kind="function", signature="def validate(data): ...", line_start=12, line_end=15),
        Node(id="/src/app.py:User", file_path="/src/app.py", name="User",
             kind="class", signature="class User: ...", line_start=20, line_end=30),
        Node(id="/src/app.py:User.save", file_path="/src/app.py", name="User.save",
             kind="method", signature="def save(self): ...", line_start=22, line_end=24,
             parent_id="/src/app.py:User"),
    ]
    edges = [
        Edge(source_id="/src/app.py:main", target_id="/src/app.py:parse",
             kind="calls", file_path="/src/app.py", line_number=2),
        Edge(source_id="/src/app.py:main", target_id="/src/app.py:validate",
             kind="calls", file_path="/src/app.py", line_number=3),
        Edge(source_id="/src/app.py:parse", target_id="/src/app.py:validate",
             kind="calls", file_path="/src/app.py", line_number=8),
    ]
    cp.db.bulk_import(nodes, edges)
    yield cp
    cp.db.close()


class TestSearchTool:
    def test_search_finds_function(self, cp):
        results = cp.search("parse")
        assert len(results) >= 1
        assert any("parse" in r.name for r in results)

    def test_search_finds_class(self, cp):
        results = cp.search("User")
        assert len(results) >= 1
        assert any(r.kind == "class" for r in results)

    def test_search_finds_method(self, cp):
        results = cp.search("save")
        assert len(results) >= 1

    def test_search_with_kind_filter(self, cp):
        results = cp.search("save", kind="method")
        assert len(results) >= 1
        assert all(r.kind == "method" for r in results)

    def test_search_no_results(self, cp):
        results = cp.search("nonexistent_function_xyz")
        assert len(results) == 0

    def test_search_empty_query(self, cp):
        results = cp.search("")
        assert len(results) >= 5  # all nodes


class TestCallersTool:
    def test_validate_called_by_parse_and_main(self, cp):
        callers = cp.get_callers("/src/app.py:validate", depth=1)
        names = {c[0].name for c in callers}
        assert "main" in names
        assert "parse" in names

    def test_main_has_no_callers(self, cp):
        callers = cp.get_callers("/src/app.py:main", depth=1)
        assert len(callers) == 0

    def test_callers_returns_node_objects(self, cp):
        callers = cp.get_callers("/src/app.py:validate", depth=1)
        for node, edge_kind in callers:
            assert hasattr(node, "name")
            assert hasattr(node, "kind")
            assert edge_kind == "calls"


class TestCalleesTool:
    def test_main_calls_parse_and_validate(self, cp):
        callees = cp.get_callees("/src/app.py:main", depth=1)
        names = {c[0].name for c in callees}
        assert "parse" in names
        assert "validate" in names

    def test_callees_returns_node_objects(self, cp):
        callees = cp.get_callees("/src/app.py:main", depth=1)
        for node, edge_kind in callees:
            assert hasattr(node, "name")
            assert hasattr(node, "kind")


class TestImpactTool:
    def test_impact_returns_depth_keyed(self, cp):
        impact = cp.get_impact_radius("/src/app.py:main", depth=2)
        assert 1 in impact
        names = {n.name for n in impact[1]}
        assert "parse" in names

    def test_impact_depth_2(self, cp):
        impact = cp.get_impact_radius("/src/app.py:main", depth=2)
        all_names = {n.name for depth in impact.values() for n in depth}
        assert "validate" in all_names


class TestNodeTool:
    def test_get_node_returns_detail(self, cp):
        detail = cp.get_node("/src/app.py:main", include_source=False)
        assert detail is not None
        assert detail.node.name == "main"

    def test_get_node_not_found(self, cp):
        detail = cp.get_node("/nonexistent.py:foo", include_source=False)
        assert detail is None

    def test_get_node_method(self, cp):
        detail = cp.get_node("/src/app.py:User.save", include_source=False)
        assert detail is not None
        assert detail.node.kind == "method"
        assert detail.node.parent_id == "/src/app.py:User"


class TestFileTool:
    def test_get_nodes_by_file(self, cp):
        nodes = cp.db.get_nodes_by_file("/src/app.py")
        assert len(nodes) >= 4
        names = {n.name for n in nodes}
        assert "main" in names
        assert "User" in names


class TestValidateTool:
    def test_validate_returns_report(self, cp):
        report = cp.validate()
        assert report.total_nodes >= 5
        assert report.total_edges >= 3
        assert report.orphan_edges == 0
