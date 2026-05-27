"""SCIP accuracy tests: verify cross-file symbol resolution.

SCIP should resolve `obj.method()` to `Helper.process` instead of bare `process`.
"""

import os
import tempfile
from pathlib import Path

import pytest

from codepulse.compat.scip import is_scip_available, index_with_scip, _find_scip_indexer
from codepulse.db import GraphDB


pytestmark = pytest.mark.skipif(
    not is_scip_available(),
    reason="scip CLI not installed"
)


@pytest.fixture
def ts_project(tmp_path: Path):
    """Create a small TypeScript project for SCIP testing."""
    (tmp_path / "tsconfig.json").write_text('{"compilerOptions":{"module":"commonjs","target":"es2020"},"include":["*.ts"]}')
    (tmp_path / "helper.ts").write_text("""
export class Helper {
  process(data: string): string {
    return data.trim();
  }
}
""")
    (tmp_path / "main.ts").write_text("""
import { Helper } from './helper';

function start(): void {
  const h = new Helper();
  const result = h.process("hello");  // Should resolve to Helper.process
}
""")
    return tmp_path


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


class TestSCIPIntegration:
    def test_scip_available(self):
        assert is_scip_available()

    def test_scip_indexer_detected(self, ts_project: Path):
        indexer = _find_scip_indexer(str(ts_project))
        assert indexer is not None
        assert "scip-typescript" in indexer

    def test_scip_indexes_and_creates_nodes(self, ts_project: Path, db: GraphDB):
        count = index_with_scip(str(ts_project), db)
        assert count >= 3, f"Expected >=3 nodes, got {count}"
        rows = db.conn.execute("SELECT name, kind FROM nodes").fetchall()
        names = {r["name"] for r in rows}
        kinds = {r["kind"] for r in rows}
        assert "Helper" in names, f"Missing Helper in {names}"
        assert "Helper.process" in names, f"Missing Helper.process in {names} — this is the key SCIP resolution!"
        assert "start" in names, f"Missing start in {names}"
        assert "class" in kinds
        assert "method" in kinds
        assert "function" in kinds

    def test_scip_resolves_cross_file(self, ts_project: Path, db: GraphDB):
        """SCIP should resolve method calls to their qualified names."""
        count = index_with_scip(str(ts_project), db)
        rows = db.conn.execute("SELECT name, kind FROM nodes WHERE kind = 'method'").fetchall()
        method_names = [r["name"] for r in rows]
        assert any("process" in n for n in method_names), (
            f"No method containing 'process' found in {method_names}"
        )
        assert any("Helper" in n for n in method_names), (
            f"No method qualified with 'Helper' found in {method_names}"
        )

    def test_scip_creates_call_edges_to_qualified_targets(self, ts_project: Path, db: GraphDB):
        """h.process() should create edge → Helper.process, not bare process."""
        index_with_scip(str(ts_project), db)
        edges = db.conn.execute(
            "SELECT source_id, target_id, kind FROM edges"
        ).fetchall()
        call_edges = [(r["source_id"], r["target_id"], r["kind"]) for r in edges]

        matching = [
            e for e in call_edges
            if "process" in e[1] and ("Helper" in e[1] or "helper" in e[1].lower())
        ]
        assert matching, (
            f"No call edge to qualified Helper.process in {call_edges}"
        )

        bare = [e for e in call_edges if e[1] == "process" or e[1].endswith(":process")]
        assert len(bare) == 0, (
            f"Found bare 'process' edges instead of qualified: {bare}"
        )
