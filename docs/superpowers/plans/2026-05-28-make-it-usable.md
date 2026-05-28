# Make CodePulse Usable — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Go from "265 tests pass but unverified on real data" to "someone can `pip install codepulse` and get correct results from scan → query → MCP."

**Architecture:** Re-verify the edge model fix on real data, then layer traversal tests, MCP tool tests, and real-world validation on top. Each layer builds confidence that the full pipeline works.

**Tech Stack:** Python 3.14, tree-sitter, SQLite + FTS5, Click CLI, FastMCP, pytest

---

## File Structure

| Action | File | Purpose |
|--------|------|---------|
| Modify | `tests/test_integrity.py` | Remove xfail for orphan edges (edge model fixed) |
| Create | `tests/test_traversal.py` | Layer 4: Traversal correctness tests |
| Create | `tests/test_mcp_contract.py` | Layer 5: MCP tool contract tests |
| Create | `tests/test_e2e.py` | Layer 7: End-to-end pipeline test |
| Modify | `src/codepulse/graph.py` | May need fixes found by traversal tests |
| Modify | `src/codepulse/db.py` | May need fixes found by traversal tests |
| Modify | `src/codepulse/mcp_server.py` | May need fixes found by MCP tests |
| Modify | `src/codepulse/cli.py` | Layer 8: CLI polish |

---

## Layer 3: Re-verification

Verify the edge model fix works on real data. The old production DB has 29k stale edges that don't match any node.

### Task 1: Remove xfail and verify orphan edges are gone

**Files:**
- Modify: `tests/test_integrity.py:1` (remove xfail marker)
- Modify: `tests/test_integrity.py:85-100` (update `test_integrity_full_pipeline`)

- [ ] **Step 1: Remove the xfail marker**

In `tests/test_integrity.py`, find the test `test_orphan_edges_detected` and remove the `@pytest.mark.xfail(...)` decorator. The edge model is now fixed.

- [ ] **Step 2: Run the integrity tests**

```bash
.venv/bin/python -m pytest tests/test_integrity.py -v
```

Expected: All 10 tests pass (no xfail).

- [ ] **Step 3: Run full suite to confirm no regressions**

```bash
.venv/bin/python -m pytest tests/ --tb=short -q
```

Expected: 265+ passed, 0 failed.

- [ ] **Step 4: Commit**

```bash
git add tests/test_integrity.py
git commit -m "fix: remove orphan edges xfail — edge model resolved"
```

---

## Layer 4: Traversal Correctness

The core question: do `callers`, `callees`, `trace`, and `impact` actually return correct results on a known graph?

### Task 2: Write traversal tests (TDD red)

**Files:**
- Create: `tests/test_traversal.py`

These tests build a small in-memory graph with known structure, then verify traversal returns correct results. This isolates traversal logic from parser accuracy.

- [ ] **Step 1: Create test file with a known graph fixture**

```python
"""Traversal correctness tests.

Builds a small known graph, then verifies callers/callees/trace/impact
return correct results. Isolates traversal logic from parser accuracy.
"""

import pytest
from codepulse.db import GraphDB, Node, Edge


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
    import tempfile, os
    db_path = os.path.join(tempfile.mkdtemp(), "traversal.db")
    db = GraphDB(db_path)
    db.initialize()

    nodes = [
        Node(id="/src/main.py:main", file_path="/src/main.py", name="main", kind="function", signature="main()", line_start=1, line_end=5),
        Node(id="/src/main.py:parse", file_path="/src/main.py", name="parse", kind="function", signature="parse()", line_start=7, line_end=10),
        Node(id="/src/main.py:validate", file_path="/src/main.py", name="validate", kind="function", signature="validate()", line_start=12, line_end=15),
        Node(id="/src/main.py:format", file_path="/src/main.py", name="format", kind="function", signature="format()", line_start=17, line_end=20),
        Node(id="/src/helper.py:helper", file_path="/src/helper.py", name="helper", kind="function", signature="helper()", line_start=1, line_end=3),
    ]
    edges = [
        Edge(source_id="/src/main.py:main", target_id="/src/main.py:parse", kind="calls", file_path="/src/main.py", line_number=2),
        Edge(source_id="/src/main.py:main", target_id="/src/main.py:format", kind="calls", file_path="/src/main.py", line_number=3),
        Edge(source_id="/src/main.py:parse", target_id="/src/main.py:validate", kind="calls", file_path="/src/main.py", line_number=8),
        Edge(source_id="/src/helper.py:helper", target_id="/src/main.py:validate", kind="calls", file_path="/src/helper.py", line_number=2),
    ]
    db.bulk_import(nodes, edges)
    yield db
    db.close()
```

- [ ] **Step 2: Write the failing test for `callees`**

```python
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
```

- [ ] **Step 3: Write the failing test for `callers`**

```python
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
```

- [ ] **Step 4: Write the failing test for `impact`**

```python
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
```

- [ ] **Step 5: Write the failing test for `trace` (path between two symbols)**

```python
class TestTrace:
    def test_trace_main_to_validate(self, graph):
        path = graph.trace_path("/src/main.py:main", "/src/main.py:validate", max_depth=10)
        assert path is not None
        assert len(path) >= 3  # main -> parse -> validate
        ids = [n.id for n in path]
        assert ids[0] == "/src/main.py:main"
        assert ids[-1] == "/src/main.py:validate"

    def test_trace_no_path(self, graph):
        # main doesn't call helper, and helper doesn't call main
        # But validate is reachable from main, so let's test an unreachable node
        # Actually, validate is reachable. Let's test a node not in the graph.
        path = graph.trace_path("/src/main.py:main", "/nonexistent.py:foo", max_depth=10)
        assert path is None

    def test_trace_same_node(self, graph):
        path = graph.trace_path("/src/main.py:main", "/src/main.py:main", max_depth=10)
        assert path is not None
        assert len(path) == 1
```

- [ ] **Step 6: Run tests to verify they fail**

```bash
.venv/bin/python -m pytest tests/test_traversal.py -v
```

Expected: Most tests FAIL (some may pass if traversal works by accident).

- [ ] **Step 7: Commit (TDD red)**

```bash
git add tests/test_traversal.py
git commit -m "test: add traversal correctness tests (red phase)"
```

### Task 3: Fix traversal issues and go green

**Files:**
- Modify: `src/codepulse/db.py` (if traversal bugs found)
- Modify: `src/codepulse/graph.py` (if wrapper bugs found)

- [ ] **Step 1: Run traversal tests and diagnose failures**

```bash
.venv/bin/python -m pytest tests/test_traversal.py -v --tb=short
```

Analyze each failure. Common issues:
- `_traverse_edges` uses wrong column for direction
- `trace_path` recursive CTE has bugs
- `get_impact_radius` doesn't follow bidirectional edges correctly

- [ ] **Step 2: Fix each issue in db.py or graph.py**

Based on the failures, apply minimal fixes. The traversal logic is in `db.py`:
- `_traverse_edges()` — BFS for callers/callees
- `get_impact_radius()` — bidirectional BFS
- `trace_path()` — recursive CTE

- [ ] **Step 3: Run traversal tests until green**

```bash
.venv/bin/python -m pytest tests/test_traversal.py -v
```

Expected: All traversal tests pass.

- [ ] **Step 4: Run full suite to verify no regressions**

```bash
.venv/bin/python -m pytest tests/ --tb=short -q
```

Expected: 265+ passed, 0 failed.

- [ ] **Step 5: Commit**

```bash
git add src/codepulse/db.py src/codepulse/graph.py
git commit -m "fix: traversal correctness for callers/callees/impact/trace"
```

---

## Layer 5: MCP Tool Contract Tests

Test that every MCP tool returns correct results on a known graph.

### Task 4: Write MCP tool tests (TDD red)

**Files:**
- Create: `tests/test_mcp_contract.py`

These tests use the same known-graph fixture as Layer 4, plus the MCP server's tool functions directly (no async needed for unit tests).

- [ ] **Step 1: Create the test file**

```python
"""MCP tool contract tests.

Verifies each MCP tool returns correct results on a known graph.
Tests the tool logic directly without async/stdio transport.
"""

import pytest
from unittest.mock import MagicMock, patch
from codepulse.graph import CodePulse, CodePulseConfig
from codepulse.db import GraphDB, Node, Edge
import tempfile, os


@pytest.fixture
def cp():
    """CodePulse instance with a known graph."""
    db_path = os.path.join(tempfile.mkdtemp(), "mcp_test.db")
    config = CodePulseConfig(db_path=db_path)
    cp = CodePulse(config)
    cp.db.initialize()

    nodes = [
        Node(id="/src/app.py:main", file_path="/src/app.py", name="main", kind="function", signature="def main(): ...", line_start=1, line_end=5),
        Node(id="/src/app.py:parse", file_path="/src/app.py", name="parse", kind="function", signature="def parse(data): ...", line_start=7, line_end=10),
        Node(id="/src/app.py:validate", file_path="/src/app.py", name="validate", kind="function", signature="def validate(data): ...", line_start=12, line_end=15),
        Node(id="/src/app.py:User", file_path="/src/app.py", name="User", kind="class", signature="class User: ...", line_start=20, line_end=30),
        Node(id="/src/app.py:User.save", file_path="/src/app.py", name="User.save", kind="method", signature="def save(self): ...", line_start=22, line_end=24, parent_id="/src/app.py:User"),
    ]
    edges = [
        Edge(source_id="/src/app.py:main", target_id="/src/app.py:parse", kind="calls", file_path="/src/app.py", line_number=2),
        Edge(source_id="/src/app.py:main", target_id="/src/app.py:validate", kind="calls", file_path="/src/app.py", line_number=3),
        Edge(source_id="/src/app.py:parse", target_id="/src/app.py:validate", kind="calls", file_path="/src/app.py", line_number=8),
    ]
    cp.db.bulk_import(nodes, edges)
    yield cp
    cp.db.close()
```

- [ ] **Step 2: Write tests for `search` tool**

```python
class TestSearchTool:
    def test_search_finds_function(self, cp):
        results = cp.search("parse")
        assert len(results) >= 1
        assert any("parse" in r.name for r in results)

    def test_search_finds_class(self, cp):
        results = cp.search("User")
        assert len(results) >= 1
        assert any(r.kind == "class" for r in results)

    def test_search_with_kind_filter(self, cp):
        results = cp.search("save", kind="method")
        assert len(results) >= 1
        assert all(r.kind == "method" for r in results)

    def test_search_no_results(self, cp):
        results = cp.search("nonexistent_function_xyz")
        assert len(results) == 0
```

- [ ] **Step 3: Write tests for `callers` and `callees` tools**

```python
class TestCallersTool:
    def test_validate_called_by_parse_and_main(self, cp):
        callers = cp.get_callers("/src/app.py:validate", depth=1)
        names = {c[0].name for c in callers}
        assert "main" in names
        assert "parse" in names

    def test_main_has_no_callers(self, cp):
        callers = cp.get_callers("/src/app.py:main", depth=1)
        assert len(callers) == 0


class TestCalleesTool:
    def test_main_calls_parse_and_validate(self, cp):
        callees = cp.get_callees("/src/app.py:main", depth=1)
        names = {c[0].name for c in callees}
        assert "parse" in names
        assert "validate" in names
```

- [ ] **Step 4: Write tests for `impact` tool**

```python
class TestImpactTool:
    def test_impact_returns_depth_keyed(self, cp):
        impact = cp.get_impact_radius("/src/app.py:main", max_depth=2)
        assert 1 in impact
        names = {n.name for n in impact[1]}
        assert "parse" in names
```

- [ ] **Step 5: Write tests for `node` and `file` tools**

```python
class TestNodeTool:
    def test_get_node_returns_detail(self, cp):
        detail = cp.get_node("/src/app.py:main", include_source=False)
        assert detail is not None
        assert detail.node.name == "main"

    def test_get_node_not_found(self, cp):
        detail = cp.get_node("/nonexistent.py:foo", include_source=False)
        assert detail is None


class TestFileTool:
    def test_get_nodes_by_file(self, cp):
        from codepulse.db import GraphDB
        nodes = cp.db.get_nodes_by_file("/src/app.py")
        assert len(nodes) >= 4
```

- [ ] **Step 6: Write tests for `validate` and `search` edge cases**

```python
class TestValidateTool:
    def test_validate_returns_report(self, cp):
        report = cp.validate()
        assert report.total_nodes >= 5
        assert report.total_edges >= 3
        assert report.orphan_edges == 0
```

- [ ] **Step 7: Run tests to verify they fail**

```bash
.venv/bin/python -m pytest tests/test_mcp_contract.py -v
```

Expected: Some tests fail (tool logic bugs or missing methods).

- [ ] **Step 8: Commit (TDD red)**

```bash
git add tests/test_mcp_contract.py
git commit -m "test: add MCP tool contract tests (red phase)"
```

### Task 5: Fix MCP tool issues and go green

**Files:**
- Modify: `src/codepulse/graph.py` (if wrapper bugs found)
- Modify: `src/codepulse/db.py` (if query bugs found)

- [ ] **Step 1: Run MCP tests and diagnose failures**

```bash
.venv/bin/python -m pytest tests/test_mcp_contract.py -v --tb=short
```

- [ ] **Step 2: Fix each issue**

Common issues:
- `search()` doesn't return results for method names
- `get_node()` doesn't handle parent_id correctly
- `validate()` counts are wrong

- [ ] **Step 3: Run MCP tests until green**

```bash
.venv/bin/python -m pytest tests/test_mcp_contract.py -v
```

Expected: All MCP contract tests pass.

- [ ] **Step 4: Run full suite**

```bash
.venv/bin/python -m pytest tests/ --tb=short -q
```

Expected: All tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/codepulse/graph.py src/codepulse/db.py
git commit -m "fix: MCP tool correctness for search/callers/callees/impact/node"
```

---

## Layer 6: Real-World Validation

Scan a known small repo and verify the output is correct.

### Task 6: Scan the codepulse codebase itself and validate

**Files:**
- Modify: `tests/test_smoke.py` (update self-index test to check edge counts)

- [ ] **Step 1: Scan codepulse's own src/ directory**

```bash
.venv/bin/python -m codepulse scan src/ --data-dir /tmp/cp_validate
```

Check the output for:
- Files indexed: should be ~6-8 Python files
- Symbols found: should be ~50+ (functions, classes, methods)
- Edges found: should be ~20+ (call edges, import edges)

- [ ] **Step 2: Validate the graph**

```bash
.venv/bin/python -m codepulse validate --data-dir /tmp/cp_validate
```

Expected:
- 0 orphan edges (source_id and target_id both resolve to nodes)
- 0 orphan parent refs
- Node counts match expected (functions, classes, methods)

- [ ] **Step 3: Test search**

```bash
.venv/bin/python -m codepulse search "parse" --data-dir /tmp/cp_validate
```

Expected: Returns `parse_file`, `SourceParser`, or similar symbols.

- [ ] **Step 4: Test callers/callees**

```bash
.venv/bin/python -m codepulse callers "/tmp/cp_validate:src/codepulse/graph.py:CodePulse.index_all" --data-dir /tmp/cp_validate
```

Expected: Returns `__init__`, or whoever calls `index_all`.

- [ ] **Step 5: Update the self-index smoke test**

In `tests/test_smoke.py`, update `test_self_index` to check:
- `orphan_edges == 0` (was never checked before)
- `report.total_edges >= 10` (call + import edges)

- [ ] **Step 6: Commit**

```bash
git add tests/test_smoke.py
git commit -m "test: update self-index smoke test with orphan edge check"
```

---

## Layer 7: End-to-End Integration

Full pipeline: scan → index → query → MCP. One test that exercises everything.

### Task 7: Write E2E integration test

**Files:**
- Create: `tests/test_e2e.py`

- [ ] **Step 1: Create the E2E test**

```python
"""End-to-end integration tests.

Scans a known fixture project, then verifies the full pipeline:
scan → index → search → callers → callees → validate → export.
"""

import pytest
import tempfile
import os
from pathlib import Path
from codepulse.graph import CodePulse, CodePulseConfig
from codepulse.parser import SourceParser


@pytest.fixture
def fixture_project(tmp_path):
    """Create a small known project in tmp_path."""
    # main.py calls greet and format_name
    main_py = tmp_path / "main.py"
    main_py.write_text("""
from utils import greet, format_name

def main():
    name = format_name("Alice")
    msg = greet(name)
    print(msg)

def run():
    main()
""")

    utils_py = tmp_path / "utils.py"
    utils_py.write_text("""
def greet(name):
    return "Hello, " + name

def format_name(first, last=""):
    if last:
        return first + " " + last
    return first

def helper():
    return format_name("test")
""")

    models_py = tmp_path / "models.py"
    models_py.write_text("""
class User:
    def __init__(self, name):
        self.name = name

    def save(self):
        return True

    def get_name(self):
        return self.name
""")

    return tmp_path


class TestE2E:
    def test_full_pipeline(self, fixture_project):
        # 1. Initialize
        config = CodePulseConfig(db_path=os.path.join(tempfile.mkdtemp(), "e2e.db"))
        cp = CodePulse(config)
        cp.db.initialize()

        # 2. Index
        result = cp.index_all(str(fixture_project))
        assert result.files_indexed >= 3
        assert result.symbols_found >= 8
        assert len(result.errors) == 0

        # 3. Validate
        report = cp.validate()
        assert report.total_nodes >= 8
        assert report.total_edges >= 4
        assert report.orphan_edges == 0

        # 4. Search
        results = cp.search("greet")
        assert len(results) >= 1
        assert any("greet" in r.name for r in results)

        # 5. Callers — who calls greet?
        greet_id = results[0].id
        callers = cp.get_callers(greet_id, depth=1)
        caller_names = {c[0].name for c in callers}
        assert "main" in caller_names

        # 6. Callees — what does main call?
        main_results = cp.search("main")
        main_id = None
        for r in main_results:
            if r.name == "main" and r.kind == "function":
                main_id = r.id
                break
        assert main_id is not None
        callees = cp.get_callees(main_id, depth=1)
        callee_names = {c[0].name for c in callees}
        assert "greet" in callee_names
        assert "format_name" in callee_names

        # 7. Impact — changing greet affects what?
        impact = cp.get_impact_radius(greet_id, max_depth=2)
        all_impacted = {n.name for depth in impact.values() for n in depth}
        assert "main" in all_impacted

        cp.db.close()
```

- [ ] **Step 2: Run the E2E test**

```bash
.venv/bin/python -m pytest tests/test_e2e.py -v
```

Expected: PASS.

- [ ] **Step 3: Run full suite**

```bash
.venv/bin/python -m pytest tests/ --tb=short -q
```

Expected: All tests pass.

- [ ] **Step 4: Commit**

```bash
git add tests/test_e2e.py
git commit -m "test: add end-to-end integration test (scan → query → MCP)"
```

---

## Layer 8: CLI Polish

Make the CLI output clean and informative.

### Task 8: Improve CLI help text and error messages

**Files:**
- Modify: `src/codepulse/cli.py`

- [ ] **Step 1: Update scan command output**

In `cli.py`, the `index` command should show a cleaner summary:

```
Indexing /path/to/project...
  12 files scanned
  87 symbols found
  34 call edges, 12 import edges
  0 errors
```

- [ ] **Step 2: Add progress indicator for large projects**

For projects with >50 files, show a progress counter:

```
Indexing... 12/45 files
```

- [ ] **Step 3: Improve error messages**

When a node_id is not found in `callers`/`callees`/`trace`, show a helpful message:

```
Node 'foo' not found. Run 'codepulse search foo' to find the correct ID.
```

- [ ] **Step 4: Test CLI improvements**

```bash
.venv/bin/python -m codepulse scan src/
.venv/bin/python -m codepulse search "parse"
.venv/bin/python -m codepulse callers "nonexistent"
```

- [ ] **Step 5: Commit**

```bash
git add src/codepulse/cli.py
git commit -m "feat: improve CLI help text, progress, and error messages"
```

---

## Verification

After all tasks complete:

- [ ] **Final full suite:**
```bash
.venv/bin/python -m pytest tests/ -v --tb=short
```
Expected: 280+ passed, 0 failed.

- [ ] **Manual smoke test:**
```bash
.venv/bin/codepulse scan src/
.venv/bin/codepulse validate
.venv/bin/codepulse search "parse"
.venv/bin/codepulse callers "src/codepulse/parser.py:SourceParser.parse_file"
.venv/bin/codepulse callees "src/codepulse/graph.py:CodePulse.index_all"
```
Expected: All commands return meaningful results with no errors.

- [ ] **MCP smoke test:**
Start the MCP server and use it from Claude to verify context/search/callers/callees work end-to-end.
