"""Traversal correctness tests.

Builds a small known graph, then verifies callers/callees/impact
return correct results. Isolates traversal logic from parser accuracy.
"""

import os
import tempfile

import pytest

from codepulse.db import Edge, GraphDB, Node


@pytest.fixture
def graph():
    """A small directed graph:

    main() -> parse() -> validate()
    main() -> format()
    parse() -> validate()
    helper() -> validate()

    Nodes: main, parse, validate, format, helper
    Edges: main->parse, main->format, parse->validate, helper->validate
    """
    db_path = os.path.join(tempfile.mkdtemp(), "traversal.db")
    db = GraphDB(db_path)
    db.initialize()

    nodes = [
        Node(id="/src/main.py:main", file_path="/src/main.py", name="main",
             kind="function", signature="main()", line_start=1, line_end=5),
        Node(id="/src/main.py:parse", file_path="/src/main.py", name="parse",
             kind="function", signature="parse()", line_start=7, line_end=10),
        Node(id="/src/main.py:validate", file_path="/src/main.py", name="validate",
             kind="function", signature="validate()", line_start=12, line_end=15),
        Node(id="/src/main.py:format", file_path="/src/main.py", name="format",
             kind="function", signature="format()", line_start=17, line_end=20),
        Node(id="/src/helper.py:helper", file_path="/src/helper.py", name="helper",
             kind="function", signature="helper()", line_start=1, line_end=3),
    ]
    edges = [
        Edge(source_id="/src/main.py:main", target_id="/src/main.py:parse",
             kind="calls", file_path="/src/main.py", line_number=2),
        Edge(source_id="/src/main.py:main", target_id="/src/main.py:format",
             kind="calls", file_path="/src/main.py", line_number=3),
        Edge(source_id="/src/main.py:parse", target_id="/src/main.py:validate",
             kind="calls", file_path="/src/main.py", line_number=8),
        Edge(source_id="/src/helper.py:helper", target_id="/src/main.py:validate",
             kind="calls", file_path="/src/helper.py", line_number=2),
        Edge(source_id="/src/main.py:main", target_id="/src/helper.py:helper",
             kind="references", file_path="/src/main.py", line_number=1),
    ]
    db.bulk_import(nodes, edges)
    yield db
    db.close()


@pytest.fixture
def cycle_graph():
    """A graph with a cycle: node_a -> node_b -> node_c -> node_a"""
    db_path = os.path.join(tempfile.mkdtemp(), "cycle.db")
    db = GraphDB(db_path)
    db.initialize()

    nodes = [
        Node(id="node_a", file_path="/cycle.py", name="a", kind="function",
             signature="a()", line_start=1, line_end=3),
        Node(id="node_b", file_path="/cycle.py", name="b", kind="function",
             signature="b()", line_start=5, line_end=7),
        Node(id="node_c", file_path="/cycle.py", name="c", kind="function",
             signature="c()", line_start=9, line_end=11),
    ]
    edges = [
        Edge(source_id="node_a", target_id="node_b", kind="calls",
             file_path="/cycle.py", line_number=2),
        Edge(source_id="node_b", target_id="node_c", kind="calls",
             file_path="/cycle.py", line_number=6),
        Edge(source_id="node_c", target_id="node_a", kind="calls",
             file_path="/cycle.py", line_number=10),
    ]
    db.bulk_import(nodes, edges)
    yield db
    db.close()


class TestCallees:
    def test_main_calls_parse_and_format(self, graph):
        callees = graph.get_callees("/src/main.py:main", depth=1)
        names = {c[0].name for c in callees}
        assert "parse" in names
        assert "format" in names
        assert "validate" not in names  # transitive, not direct

    def test_parse_calls_validate(self, graph):
        callees = graph.get_callees("/src/main.py:parse", depth=1)
        names = {c[0].name for c in callees}
        assert "validate" in names
        assert len(callees) == 1

    def test_callees_depth_2(self, graph):
        callees = graph.get_callees("/src/main.py:main", depth=2)
        names = {c[0].name for c in callees}
        assert "parse" in names
        assert "format" in names
        assert "validate" in names  # transitive via parse

    def test_leaf_has_no_callees(self, graph):
        callees = graph.get_callees("/src/main.py:validate", depth=1)
        assert len(callees) == 0


class TestCallers:
    def test_validate_has_two_callers(self, graph):
        callers = graph.get_callers("/src/main.py:validate", depth=1)
        names = {c[0].name for c in callers}
        assert "parse" in names
        assert "helper" in names

    def test_parse_called_by_main(self, graph):
        callers = graph.get_callers("/src/main.py:parse", depth=1)
        names = {c[0].name for c in callers}
        assert "main" in names
        assert len(callers) == 1

    def test_callers_depth_2(self, graph):
        callers = graph.get_callers("/src/main.py:validate", depth=2)
        names = {c[0].name for c in callers}
        assert "parse" in names
        assert "helper" in names
        assert "main" in names  # transitive via parse

    def test_root_has_no_callers(self, graph):
        callers = graph.get_callers("/src/main.py:main", depth=1)
        assert len(callers) == 0


class TestImpact:
    def test_impact_returns_depth_keyed_results(self, graph):
        impact = graph.get_impact_radius("/src/main.py:main", max_depth=2)
        assert 1 in impact
        assert 2 in impact

    def test_impact_depth_1_is_direct_neighbors(self, graph):
        impact = graph.get_impact_radius("/src/main.py:main", max_depth=1)
        names = {n.name for n in impact[1]}
        assert "parse" in names
        assert "format" in names

    def test_impact_depth_2_includes_transitive(self, graph):
        impact = graph.get_impact_radius("/src/main.py:main", max_depth=2)
        all_names = {n.name for depth in impact.values() for n in depth}
        assert "validate" in all_names

    def test_impact_from_leaf(self, graph):
        impact = graph.get_impact_radius("/src/main.py:validate", max_depth=2)
        all_names = {n.name for depth in impact.values() for n in depth}
        assert "parse" in all_names
        assert "helper" in all_names
        assert "main" in all_names  # via parse


class TestTrace:
    def test_direct_path(self, graph):
        result = graph.trace_path("/src/main.py:main", "/src/main.py:parse", max_depth=1)
        assert result is not None
        assert len(result) == 2
        assert result[0].id == "/src/main.py:main"
        assert result[-1].id == "/src/main.py:parse"

    def test_multi_hop_path(self, graph):
        result = graph.trace_path("/src/main.py:main", "/src/main.py:validate", max_depth=2)
        assert result is not None
        ids = [n.id for n in result]
        assert ids[0] == "/src/main.py:main"
        assert ids[-1] == "/src/main.py:validate"
        assert len(ids) == 3  # main -> parse -> validate

    def test_no_path_returns_none(self, graph):
        result = graph.trace_path("/src/main.py:main", "/nonexistent.py:foo", max_depth=10)
        assert result is None

    def test_same_node_returns_none(self, graph):
        result = graph.trace_path("/src/main.py:main", "/src/main.py:main", max_depth=10)
        assert result is None

    def test_max_depth_respected(self, graph):
        result = graph.trace_path("/src/main.py:main", "/src/main.py:validate", max_depth=1)
        assert result is None

    def test_cycle_does_not_loop_forever(self, cycle_graph):
        result = cycle_graph.trace_path("node_a", "node_c", max_depth=10)
        assert result is not None
        ids = [n.id for n in result]
        assert ids[0] == "node_a"
        assert ids[-1] == "node_c"
        assert len(ids) == 3  # a -> b -> c

    def test_trace_edge_kinds_filter(self, graph):
        result = graph.trace_path("/src/main.py:main", "/src/helper.py:helper",
                                  max_depth=1, edge_kinds={"calls"})
        assert result is None
        result = graph.trace_path("/src/main.py:main", "/src/helper.py:helper",
                                  max_depth=1, edge_kinds={"references"})
        assert result is not None
        assert result[0].id == "/src/main.py:main"
        assert result[-1].id == "/src/helper.py:helper"

    def test_trace_empty_edge_kinds_returns_none(self, graph):
        result = graph.trace_path("/src/main.py:main", "/src/main.py:parse",
                                  max_depth=1, edge_kinds=set())
        assert result is None

    def test_trace_missing_node_returns_none(self, graph):
        graph.upsert_edge(Edge(
            source_id="/src/main.py:main", target_id="/missing.py:ghost",
            kind="calls", file_path="/src/main.py", line_number=99,
        ))
        result = graph.trace_path("/src/main.py:main", "/missing.py:ghost", max_depth=1)
        assert result is None


class TestCalleesEdgeKinds:
    def test_callees_filter_by_edge_kind(self, graph):
        callees = graph.get_callees("/src/main.py:main", depth=1, edge_kinds={"calls"})
        names = {c[0].name for c in callees}
        assert "parse" in names
        assert "format" in names
        assert "helper" not in names

    def test_callees_no_filter_returns_all(self, graph):
        callees = graph.get_callees("/src/main.py:main", depth=1)
        names = {c[0].name for c in callees}
        assert "parse" in names
        assert "format" in names
        assert "helper" in names

    def test_callees_filter_empty_kind_set(self, graph):
        callees = graph.get_callees("/src/main.py:main", depth=1, edge_kinds=set())
        assert len(callees) == 0


class TestCallersEdgeKinds:
    def test_callers_filter_by_edge_kind(self, graph):
        callers = graph.get_callers("/src/helper.py:helper", depth=1, edge_kinds={"calls"})
        assert len(callers) == 0

        callers = graph.get_callers("/src/helper.py:helper", depth=1, edge_kinds={"references"})
        names = {c[0].name for c in callers}
        assert names == {"main"}

    def test_callers_no_filter_returns_all(self, graph):
        callers = graph.get_callers("/src/helper.py:helper", depth=1)
        names = {c[0].name for c in callers}
        assert names == {"main"}

    def test_callers_filter_empty_kind_set(self, graph):
        callers = graph.get_callers("/src/helper.py:helper", depth=1, edge_kinds=set())
        assert len(callers) == 0


class TestImpactEdgeKinds:
    def test_impact_filter_by_edge_kind(self, graph):
        impact = graph.get_impact_radius("/src/main.py:main", max_depth=1, edge_kinds={"calls"})
        names = {n.name for n in impact[1]}
        assert "parse" in names
        assert "format" in names
        assert "helper" not in names

    def test_impact_empty_edge_kinds_returns_empty(self, graph):
        impact = graph.get_impact_radius("/src/main.py:main", max_depth=1, edge_kinds=set())
        assert len(impact) == 0
