"""SCIP accuracy tests: verify cross-file symbol resolution.

SCIP should resolve `obj.method()` to `Helper.process` instead of bare `process`.
"""

import json
import os
import subprocess
import tempfile
from pathlib import Path

import warnings

import pytest

from codepulse.compat.scip import is_scip_available, index_with_scip, _find_scip_indexer
from codepulse.db import GraphDB


def _make_which_fake(
    scip_typescript: str | None = "/usr/local/bin/scip-typescript",
    scip_python: str | None = "/usr/local/bin/scip-python",
):
    def fake_which(name: str) -> str | None:
        if name == "scip-typescript":
            return scip_typescript
        if name == "scip-python":
            return scip_python
        return None
    return fake_which


def _make_scip_document(relative_path: str) -> dict:
    """Produce a minimal SCIP document with known symbols for unit-testing graph conversion."""
    return {
        "relative_path": relative_path,
        "occurrences": [
            {
                "symbol": "scip-python python . `module`.",
                "symbol_roles": 1,
                "range": [0, 0, 0, 0],
            },
        ],
        "symbols": [],
    }


def _mock_indexing_subprocess(monkeypatch, scip_output_dir: Path, documents: list[dict] | None = None):
    """Replace subprocess.run with a fake that writes an index.scip and returns it on scip print."""
    if documents is None:
        documents = []
    fake_data = json.dumps({"documents": documents})

    def fake_run(args, **kwargs):
        args_str = " ".join(args)
        if "--output" in args_str:
            idx = args.index("--output")
            out = Path(args[idx + 1])
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(fake_data)
        if "print" in args_str and "--json" in args_str:
            return type("Result", (), {"returncode": 0, "stdout": fake_data, "stderr": ""})()
        return type("Result", (), {"returncode": 0, "stdout": "", "stderr": ""})()

    monkeypatch.setattr(subprocess, "run", fake_run)


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


class TestFindIndexer:
    """Tests for _find_scip_indexer with mocked _which."""

    def test_returns_list(self, ts_project: Path, monkeypatch):
        monkeypatch.setattr("codepulse.compat.scip._which", _make_which_fake())
        indexers = _find_scip_indexer(str(ts_project))
        assert isinstance(indexers, list)

    def test_returns_empty_list_for_empty_project(self, tmp_path: Path, monkeypatch):
        monkeypatch.setattr("codepulse.compat.scip._which", _make_which_fake())
        indexers = _find_scip_indexer(str(tmp_path))
        assert isinstance(indexers, list)
        assert len(indexers) == 0

    def test_detects_typescript_indexer(self, ts_project: Path, monkeypatch):
        monkeypatch.setattr("codepulse.compat.scip._which", _make_which_fake())
        indexers = _find_scip_indexer(str(ts_project))
        assert len(indexers) > 0
        assert any("scip-typescript" in cmd for _, cmd in indexers)

    def test_detects_python_indexer_nested(self, tmp_path: Path, monkeypatch):
        monkeypatch.setattr("codepulse.compat.scip._which", _make_which_fake())
        pkg = tmp_path / "src" / "pkg"
        pkg.mkdir(parents=True)
        (pkg / "__init__.py").write_text("")
        (pkg / "module.py").write_text("x = 1")
        indexers = _find_scip_indexer(str(tmp_path))
        assert any("scip-python" in cmd for _, cmd in indexers)

    def test_detects_typescript_indexer_nested(self, tmp_path: Path, monkeypatch):
        monkeypatch.setattr("codepulse.compat.scip._which", _make_which_fake())
        app = tmp_path / "packages" / "app" / "src"
        app.mkdir(parents=True)
        (app / "index.ts").write_text("export const x = 1;")
        (tmp_path / "tsconfig.json").write_text("{}")
        indexers = _find_scip_indexer(str(tmp_path))
        assert any("scip-typescript" in cmd for _, cmd in indexers)

    def test_detects_mixed_project(self, tmp_path: Path, monkeypatch):
        monkeypatch.setattr("codepulse.compat.scip._which", _make_which_fake())
        pkg = tmp_path / "src" / "pkg"
        pkg.mkdir(parents=True)
        (pkg / "__init__.py").write_text("")
        (pkg / "module.py").write_text("x = 1")
        app = tmp_path / "packages" / "app" / "src"
        app.mkdir(parents=True)
        (app / "index.ts").write_text("export const x = 1;")
        (tmp_path / "tsconfig.json").write_text("{}")
        indexers = _find_scip_indexer(str(tmp_path))
        assert any("scip-python" in cmd for _, cmd in indexers)
        assert any("scip-typescript" in cmd for _, cmd in indexers)

    def test_skipped_dirs_ignored(self, tmp_path: Path, monkeypatch):
        monkeypatch.setattr("codepulse.compat.scip._which", _make_which_fake())
        (tmp_path / "node_modules" / "pkg" / "index.ts").parent.mkdir(parents=True)
        (tmp_path / "node_modules" / "pkg" / "index.ts").write_text("")
        (tmp_path / ".venv" / "lib" / "python3.12" / "site-packages" / "mod.py").parent.mkdir(parents=True)
        (tmp_path / ".venv" / "lib" / "python3.12" / "site-packages" / "mod.py").write_text("")
        indexers = _find_scip_indexer(str(tmp_path))
        assert len(indexers) == 0

    def test_package_json_alone_does_not_trigger_ts(self, tmp_path: Path, monkeypatch):
        monkeypatch.setattr("codepulse.compat.scip._which", _make_which_fake())
        (tmp_path / "package.json").write_text("{}")
        indexers = _find_scip_indexer(str(tmp_path))
        assert not any(lang == "typescript" for lang, _ in indexers)

    def test_pyproject_toml_alone_does_not_trigger_python(self, tmp_path: Path, monkeypatch):
        monkeypatch.setattr("codepulse.compat.scip._which", _make_which_fake())
        (tmp_path / "pyproject.toml").write_text("")
        indexers = _find_scip_indexer(str(tmp_path))
        assert not any(lang == "python" for lang, _ in indexers)

    def test_indexer_not_installed_returns_empty(self, tmp_path: Path, monkeypatch):
        monkeypatch.setattr("codepulse.compat.scip._which", _make_which_fake(scip_typescript=None, scip_python=None))
        src = tmp_path / "src"
        src.mkdir(parents=True)
        (src / "index.ts").write_text("")
        (src / "mod.py").write_text("")
        indexers = _find_scip_indexer(str(tmp_path))
        assert len(indexers) == 0

    def test_output_path_is_dot_codepulse_scip(self, ts_project: Path, db: GraphDB, monkeypatch):
        monkeypatch.setattr("codepulse.compat.scip.is_scip_available", lambda: True)
        monkeypatch.setattr("codepulse.compat.scip._which", _make_which_fake())
        _mock_indexing_subprocess(
            monkeypatch,
            ts_project / ".codepulse" / "scip",
            [_make_scip_document("helper.ts")],
        )
        index_with_scip(str(ts_project), db)
        scip_dir = ts_project / ".codepulse" / "scip"
        assert scip_dir.is_dir(), f"Expected {scip_dir} to exist"
        scip_files = list(scip_dir.glob("*.scip"))
        assert len(scip_files) >= 1, f"Expected .scip files in {scip_dir}"
        assert not (ts_project / "index.scip").exists(), "Must not write to project root"

    def test_mixed_indexers_continue_on_failure(self, tmp_path: Path, db: GraphDB, monkeypatch):
        monkeypatch.setattr("codepulse.compat.scip.is_scip_available", lambda: True)
        monkeypatch.setattr("codepulse.compat.scip._which", _make_which_fake())
        pkg = tmp_path / "src" / "pkg"
        pkg.mkdir(parents=True)
        (pkg / "__init__.py").write_text("")
        (pkg / "module.py").write_text("x = 1")
        app = tmp_path / "packages" / "app" / "src"
        app.mkdir(parents=True)
        (app / "index.ts").write_text("export const x = 1;")
        (tmp_path / "tsconfig.json").write_text("{}")
        calls = []

        def tracking_run(args, **kwargs):
            calls.append(" ".join(args))
            args_str = " ".join(args)
            if "scip-python" in args_str:
                raise FileNotFoundError(f"No such file: {args[0]}")
            if "--output" in args_str:
                idx = args.index("--output")
                out = Path(args[idx + 1])
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_text(json.dumps({"documents": []}))
            if "print" in args_str and "--json" in args_str:
                return type("Result", (), {"returncode": 0, "stdout": json.dumps({"documents": []}), "stderr": ""})()
            return type("Result", (), {"returncode": 0, "stdout": "", "stderr": ""})()

        monkeypatch.setattr(subprocess, "run", tracking_run)
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            count = index_with_scip(str(tmp_path), db)
            assert count == 0
            assert any("scip-typescript" in c for c in calls), "TS indexer should have been attempted"
            assert any("scip-python" in c for c in calls), "Python indexer should have been attempted"
            assert any("scip-python" in str(warning.message) for warning in w), "Python failure should be warned"

    def test_timeout_failure_does_not_block_other_indexers(self, tmp_path: Path, db: GraphDB, monkeypatch):
        monkeypatch.setattr("codepulse.compat.scip.is_scip_available", lambda: True)
        monkeypatch.setattr("codepulse.compat.scip._which", _make_which_fake())
        pkg = tmp_path / "src" / "pkg"
        pkg.mkdir(parents=True)
        (pkg / "__init__.py").write_text("")
        (pkg / "module.py").write_text("x = 1")
        app = tmp_path / "packages" / "app" / "src"
        app.mkdir(parents=True)
        (app / "index.ts").write_text("export const x = 1;")
        (tmp_path / "tsconfig.json").write_text("{}")
        calls = []

        def timeout_run(args, **kwargs):
            calls.append(" ".join(args))
            args_str = " ".join(args)
            if "scip-typescript" in args_str:
                raise subprocess.TimeoutExpired(args[0], 300)
            if "--output" in args_str:
                idx = args.index("--output")
                out = Path(args[idx + 1])
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_text(json.dumps({"documents": [_make_scip_document("module.py")]}))
            if "print" in args_str and "--json" in args_str:
                return type("Result", (), {"returncode": 0, "stdout": json.dumps({"documents": [_make_scip_document("module.py")]}), "stderr": ""})()
            return type("Result", (), {"returncode": 0, "stdout": "", "stderr": ""})()

        monkeypatch.setattr(subprocess, "run", timeout_run)
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            count = index_with_scip(str(tmp_path), db)
            assert count >= 0
            assert any("scip-typescript" in c for c in calls), "TS indexer should have been attempted"
            assert any("scip-python" in c for c in calls), "Python indexer should have been attempted"
            assert any("timed out" in str(warning.message) for warning in w), "Timeout should be warned"

    def test_all_indexers_fail_raises_runtime_error(self, tmp_path: Path, db: GraphDB, monkeypatch):
        monkeypatch.setattr("codepulse.compat.scip.is_scip_available", lambda: True)
        monkeypatch.setattr("codepulse.compat.scip._which", _make_which_fake())
        pkg = tmp_path / "src" / "pkg"
        pkg.mkdir(parents=True)
        (pkg / "__init__.py").write_text("")
        (pkg / "module.py").write_text("x = 1")
        app = tmp_path / "packages" / "app" / "src"
        app.mkdir(parents=True)
        (app / "index.ts").write_text("export const x = 1;")
        (tmp_path / "tsconfig.json").write_text("{}")

        def fail_run(args, **kwargs):
            args_str = " ".join(args)
            if "scip-python" in args_str:
                raise subprocess.TimeoutExpired(args[0], 300)
            raise RuntimeError("indexer crashed")

        monkeypatch.setattr(subprocess, "run", fail_run)
        with pytest.raises(RuntimeError) as excinfo:
            index_with_scip(str(tmp_path), db)
        assert "scip-python" in str(excinfo.value)
        assert "scip-typescript" in str(excinfo.value)

    def _setup_scip_mocks(self, monkeypatch, tmp_path: Path, documents: list[dict]):
        """Set up all mocks needed for SCIP indexing: availability, indexer discovery, subprocess."""
        monkeypatch.setattr("codepulse.compat.scip.is_scip_available", lambda: True)
        monkeypatch.setattr("codepulse.compat.scip._find_scip_indexer",
                            lambda _: [("typescript", "/usr/local/bin/scip-typescript")])
        monkeypatch.setattr("codepulse.compat.scip._which", _make_which_fake())
        _mock_indexing_subprocess(monkeypatch, tmp_path / ".codepulse" / "scip", documents)
        (tmp_path / "tsconfig.json").write_text("{}")
        (tmp_path / "index.ts").write_text("// placeholder")

    def test_scip_edges_have_scip_provenance(self, tmp_path: Path, db: GraphDB, monkeypatch):
        """SCIP edges must have provenance='scip', resolution_status='resolved', confidence=1.0, and original symbol in metadata."""
        self._setup_scip_mocks(monkeypatch, tmp_path, [_make_scip_document("helper.ts")])
        index_with_scip(str(tmp_path), db)

        rows = db.conn.execute(
            "SELECT provenance, resolution_status, confidence, metadata FROM edges"
        ).fetchall()

        for row in rows:
            assert row["provenance"] == "scip", f"Expected provenance='scip', got {row['provenance']}"
            assert row["resolution_status"] == "resolved", f"Expected resolution_status='resolved', got {row['resolution_status']}"
            assert row["confidence"] == 1.0, f"Expected confidence=1.0, got {row['confidence']}"
            assert '"scip_symbol"' in row["metadata"], f"Expected scip_symbol in metadata, got {row['metadata']}"

    def test_reference_inside_function_uses_enclosing_source_id(self, tmp_path: Path, db: GraphDB, monkeypatch):
        """SCIP reference inside a function should have source_id = enclosing function node, not file path."""
        doc = {
            "relative_path": "main.ts",
            "occurrences": [
                {"symbol": "pkg/main/start().", "symbol_roles": 1, "range": [5, 0, 15, 0]},
                {"symbol": "pkg/Helper#process", "symbol_roles": 0, "range": [10, 4, 10, 15]},
            ],
            "symbols": [
                {"symbol": "pkg/Helper#", "information": {"kind": 4}},
                {"symbol": "pkg/Helper#process", "information": {"kind": 6}},
            ],
        }
        self._setup_scip_mocks(monkeypatch, tmp_path, [doc])
        index_with_scip(str(tmp_path), db)

        rows = db.conn.execute("SELECT source_id, target_id, kind FROM edges").fetchall()
        assert len(rows) > 0, "Expected at least one edge"

        for source_id, target_id, kind in rows:
            assert ":start" in source_id, (
                f"Edge source_id should be the enclosing function 'start', got {source_id!r}"
            )
            assert source_id != str(tmp_path / "main.ts"), "source_id must not be bare file path"
            assert ":Helper.process" in target_id, (
                f"Edge target_id should be Helper.process, got {target_id!r}"
            )

    def test_two_classes_with_process_resolves_correctly(self, tmp_path: Path, db: GraphDB, monkeypatch):
        """When two classes define process(), SCIP must resolve the correct qualified name."""
        doc = {
            "relative_path": "main.ts",
            "occurrences": [
                {"symbol": "pkg/Helper#process", "symbol_roles": 0, "range": [10, 4, 10, 15]},
            ],
            "symbols": [
                {"symbol": "pkg/Helper#", "information": {"kind": 4}},
                {"symbol": "pkg/Helper#process", "information": {"kind": 6}},
                {"symbol": "pkg/Processor#", "information": {"kind": 4}},
                {"symbol": "pkg/Processor#process", "information": {"kind": 6}},
            ],
        }
        self._setup_scip_mocks(monkeypatch, tmp_path, [doc])
        index_with_scip(str(tmp_path), db)

        rows = db.conn.execute("SELECT source_id, target_id, kind FROM edges").fetchall()
        assert len(rows) > 0, "Expected at least one edge"

        for source_id, target_id, kind in rows:
            assert ":Helper.process" in target_id, (
                f"Edge should target Helper.process, got {target_id!r}"
            )

    def test_bad_scip_conversion_does_not_block_other_indexers(self, tmp_path: Path, db: GraphDB, monkeypatch):
        monkeypatch.setattr("codepulse.compat.scip.is_scip_available", lambda: True)
        monkeypatch.setattr("codepulse.compat.scip._which", _make_which_fake())
        pkg = tmp_path / "src" / "pkg"
        pkg.mkdir(parents=True)
        (pkg / "__init__.py").write_text("")
        (pkg / "module.py").write_text("x = 1")
        app = tmp_path / "packages" / "app" / "src"
        app.mkdir(parents=True)
        (app / "index.ts").write_text("export const x = 1;")
        (tmp_path / "tsconfig.json").write_text("{}")
        calls = []

        def bad_convert_run(args, **kwargs):
            calls.append(" ".join(args))
            args_str = " ".join(args)
            if "--output" in args_str:
                idx = args.index("--output")
                out = Path(args[idx + 1])
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_text(json.dumps({"documents": [_make_scip_document("module.py")]}))
                return type("Result", (), {"returncode": 0, "stdout": "", "stderr": ""})()
            if "print" in args_str and "--json" in args_str:
                if "typescript" in args_str:
                    return type("Result", (), {"returncode": 0, "stdout": "not valid json", "stderr": ""})()
                return type("Result", (), {"returncode": 0, "stdout": json.dumps({"documents": []}), "stderr": ""})()
            return type("Result", (), {"returncode": 0, "stdout": "", "stderr": ""})()

        monkeypatch.setattr(subprocess, "run", bad_convert_run)
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            count = index_with_scip(str(tmp_path), db)
            assert count == 0
            assert any("scip-typescript" in c for c in calls), "TS indexer should have been attempted"
            assert any("scip-python" in c for c in calls), "Python indexer should have been attempted"
            assert any("Expecting value" in str(warning.message) for warning in w), "JSON decode error should be warned"


class TestSCIPIntegration:
    pytestmark = pytest.mark.skipif(
        not is_scip_available(),
        reason="scip CLI not installed"
    )

    def test_scip_available(self):
        assert is_scip_available()

    def test_scip_available_from_default_local_bins(self):
        original_path = os.environ.get("PATH", "")
        try:
            os.environ["PATH"] = ""
            assert is_scip_available()
        finally:
            os.environ["PATH"] = original_path

    def test_scip_indexer_detected(self, ts_project: Path):
        indexers = _find_scip_indexer(str(ts_project))
        assert len(indexers) > 0
        assert any("scip-typescript" in cmd for _, cmd in indexers)

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
        index_with_scip(str(ts_project), db)
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
