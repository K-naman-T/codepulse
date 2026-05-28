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
    def test_trace_main_to_validate(self, graph):
        """Test the recursive CTE trace query directly."""
        conn = graph.conn
        rows = conn.execute(
            """WITH RECURSIVE path AS (
                SELECT source_id, target_id, kind, file_path, line_number, 0 AS depth,
                       source_id || ' -> ' || target_id AS path_str
                FROM edges WHERE source_id = ?
                UNION ALL
                SELECT e.source_id, e.target_id, e.kind, e.file_path, e.line_number, p.depth + 1,
                       p.path_str || ' -> ' || e.target_id
                FROM edges e JOIN path p ON e.source_id = p.target_id
                WHERE p.depth < 15 AND e.target_id != p.source_id
            )
            SELECT * FROM path WHERE target_id = ? ORDER BY depth LIMIT 1""",
            ("/src/main.py:main", "/src/main.py:validate"),
        ).fetchall()
        assert len(rows) >= 1
        assert rows[0]["depth"] >= 1  # main -> parse -> validate (depth 1 = 2 hops)

    def test_trace_no_path(self, graph):
        conn = graph.conn
        rows = conn.execute(
            """WITH RECURSIVE path AS (
                SELECT source_id, target_id, kind, file_path, line_number, 0 AS depth,
                       source_id || ' -> ' || target_id AS path_str
                FROM edges WHERE source_id = ?
                UNION ALL
                SELECT e.source_id, e.target_id, e.kind, e.file_path, e.line_number, p.depth + 1,
                       p.path_str || ' -> ' || e.target_id
                FROM edges e JOIN path p ON e.source_id = p.target_id
                WHERE p.depth < 15 AND e.target_id != p.source_id
            )
            SELECT * FROM path WHERE target_id = ? ORDER BY depth LIMIT 1""",
            ("/src/main.py:main", "/nonexistent.py:foo"),
        ).fetchall()
        assert len(rows) == 0

    def test_trace_same_node(self, graph):
        """CTE trace doesn't support same-node (source_id = target_id).
        It returns no rows because the base case looks for edges FROM the
        source, not self-loops. This is expected behavior."""
        conn = graph.conn
        rows = conn.execute(
            """WITH RECURSIVE path AS (
                SELECT source_id, target_id, kind, file_path, line_number, 0 AS depth,
                       source_id || ' -> ' || target_id AS path_str
                FROM edges WHERE source_id = ?
                UNION ALL
                SELECT e.source_id, e.target_id, e.kind, e.file_path, e.line_number, p.depth + 1,
                       p.path_str || ' -> ' || e.target_id
                FROM edges e JOIN path p ON e.source_id = p.target_id
                WHERE p.depth < 15 AND e.target_id != p.source_id
            )
            SELECT * FROM path WHERE target_id = ? ORDER BY depth LIMIT 1""",
            ("/src/main.py:main", "/src/main.py:main"),
        ).fetchall()
        assert len(rows) == 0  # CTE doesn't handle same-node
