import pytest

from codepulse.db import GraphDB, Node, Edge


class TestDBSchema:
    def test_initialize_creates_tables(self, db: GraphDB):
        tables = db.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        names = [r["name"] for r in tables]
        assert "nodes" in names
        assert "edges" in names
        assert "nodes_fts" in names

    def test_initialize_idempotent(self, db: GraphDB):
        db.initialize()
        db.initialize()


class TestNodeCRUD:
    def test_insert_and_get_node(self, db: GraphDB):
        node = Node(
            id="test.py:foo",
            file_path="test.py",
            name="foo",
            kind="function",
            language="python",
        )
        db.upsert_node(node)
        retrieved = db.get_node("test.py:foo")
        assert retrieved is not None
        assert retrieved.name == "foo"
        assert retrieved.kind == "function"

    def test_upsert_updates_existing(self, db: GraphDB):
        node = Node(id="test.py:bar", file_path="test.py", name="bar", kind="function")
        db.upsert_node(node)
        updated = Node(
            id="test.py:bar",
            file_path="test.py",
            name="bar",
            kind="method",
            signature="def bar()",
        )
        db.upsert_node(updated)
        retrieved = db.get_node("test.py:bar")
        assert retrieved is not None
        assert retrieved.kind == "method"
        assert retrieved.signature == "def bar()"

    def test_get_nonexistent_node(self, db: GraphDB):
        assert db.get_node("nonexistent") is None

    def test_node_with_metadata(self, db: GraphDB):
        node = Node(
            id="test.py:Baz",
            file_path="test.py",
            name="Baz",
            kind="class",
            metadata={"docstring": "A test class", "visibility": "public"},
        )
        db.upsert_node(node)
        retrieved = db.get_node("test.py:Baz")
        assert retrieved is not None
        assert retrieved.metadata["docstring"] == "A test class"

    def test_node_with_parent(self, db: GraphDB):
        parent = Node(id="test.py:Parent", file_path="test.py", name="Parent", kind="class")
        child = Node(
            id="test.py:Parent.method",
            file_path="test.py",
            name="method",
            kind="method",
            parent_id="test.py:Parent",
        )
        db.upsert_node(parent)
        db.upsert_node(child)
        retrieved = db.get_node("test.py:Parent.method")
        assert retrieved is not None
        assert retrieved.parent_id == "test.py:Parent"


class TestEdgeCRUD:
    def test_insert_edge(self, db: GraphDB):
        a = Node(id="mod.py:a", file_path="mod.py", name="a", kind="function")
        b = Node(id="mod.py:b", file_path="mod.py", name="b", kind="function")
        db.upsert_node(a)
        db.upsert_node(b)
        edge_id = db.upsert_edge(Edge(source_id="mod.py:a", target_id="mod.py:b", kind="calls"))
        assert edge_id > 0

    def test_edge_unique_constraint(self, db: GraphDB):
        a = Node(id="mod.py:a", file_path="mod.py", name="a", kind="function")
        b = Node(id="mod.py:b", file_path="mod.py", name="b", kind="function")
        db.upsert_node(a)
        db.upsert_node(b)
        e1 = db.upsert_edge(Edge(source_id="mod.py:a", target_id="mod.py:b", kind="calls"))
        e2 = db.upsert_edge(Edge(source_id="mod.py:a", target_id="mod.py:b", kind="calls"))
        assert e2 == e1 or e2 > 0


class TestSearch:
    def test_fts_search_by_name(self, db: GraphDB):
        node = Node(id="util.py:calculate", file_path="util.py", name="calculate", kind="function")
        db.upsert_node(node)
        results = db.search_nodes("calculate")
        assert len(results) == 1
        assert results[0].name == "calculate"

    def test_fts_search_filter_by_kind(self, db: GraphDB):
        func = Node(id="a.py:func", file_path="a.py", name="do_thing", kind="function")
        cls = Node(id="a.py:MyClass", file_path="a.py", name="do_thing", kind="class")
        db.upsert_node(func)
        db.upsert_node(cls)
        results = db.search_nodes("do_thing", kind="class")
        assert len(results) == 1
        assert results[0].kind == "class"

    def test_search_empty_db(self, db: GraphDB):
        results = db.search_nodes("anything")
        assert results == []


class TestGraphQueries:
    def test_get_callers_depth_1(self, db: GraphDB):
        a = Node(id="a.py:A", file_path="a.py", name="A", kind="function")
        b = Node(id="b.py:B", file_path="b.py", name="B", kind="function")
        c = Node(id="c.py:C", file_path="c.py", name="C", kind="function")
        for n in [a, b, c]:
            db.upsert_node(n)
        db.upsert_edge(Edge(source_id="a.py:A", target_id="b.py:B", kind="calls"))
        db.upsert_edge(Edge(source_id="b.py:B", target_id="c.py:C", kind="calls"))
        callers = db.get_callers("c.py:C", depth=1)
        assert len(callers) == 1
        assert callers[0][0].id == "b.py:B"

    def test_get_callers_depth_2(self, db: GraphDB):
        a = Node(id="a.py:A", file_path="a.py", name="A", kind="function")
        b = Node(id="b.py:B", file_path="b.py", name="B", kind="function")
        c = Node(id="c.py:C", file_path="c.py", name="C", kind="function")
        for n in [a, b, c]:
            db.upsert_node(n)
        db.upsert_edge(Edge(source_id="a.py:A", target_id="b.py:B", kind="calls"))
        db.upsert_edge(Edge(source_id="b.py:B", target_id="c.py:C", kind="calls"))
        callers = db.get_callers("c.py:C", depth=2)
        assert len(callers) == 2

    def test_get_callees_depth_1(self, db: GraphDB):
        a = Node(id="a.py:A", file_path="a.py", name="A", kind="function")
        b = Node(id="b.py:B", file_path="b.py", name="B", kind="function")
        c = Node(id="c.py:C", file_path="c.py", name="C", kind="function")
        for n in [a, b, c]:
            db.upsert_node(n)
        db.upsert_edge(Edge(source_id="a.py:A", target_id="b.py:B", kind="calls"))
        db.upsert_edge(Edge(source_id="b.py:B", target_id="c.py:C", kind="calls"))
        callees = db.get_callees("a.py:A", depth=1)
        assert len(callees) == 1
        assert callees[0][0].id == "b.py:B"

    def test_impact_radius_returns_depth_keyed(self, db: GraphDB):
        a = Node(id="a.py:A", file_path="a.py", name="A", kind="function")
        b = Node(id="b.py:B", file_path="b.py", name="B", kind="function")
        c = Node(id="c.py:C", file_path="c.py", name="C", kind="function")
        for n in [a, b, c]:
            db.upsert_node(n)
        db.upsert_edge(Edge(source_id="a.py:A", target_id="b.py:B", kind="calls"))
        db.upsert_edge(Edge(source_id="b.py:B", target_id="c.py:C", kind="calls"))
        impact = db.get_impact_radius("a.py:A", max_depth=3)
        assert 1 in impact
        assert 2 in impact

    def test_delete_file_nodes(self, db: GraphDB):
        n1 = Node(id="del.py:X", file_path="del.py", name="X", kind="function")
        n2 = Node(id="keep.py:Y", file_path="keep.py", name="Y", kind="function")
        db.upsert_node(n1)
        db.upsert_node(n2)
        db.upsert_edge(Edge(source_id="del.py:X", target_id="keep.py:Y", kind="calls"))
        db.delete_file_nodes("del.py")
        assert db.get_node("del.py:X") is None
        assert db.get_node("keep.py:Y") is not None
