from pathlib import Path

import pytest

from codepulse.db import GraphDB, Node, Edge
from codepulse.graph import CodePulse, _file_content_hash, _is_file_unchanged, _default_workers
from codepulse.config import CodePulseConfig


class TestFileMetaCache:
    def test_upsert_and_get_file_meta(self, db: GraphDB, tmp_path: Path):
        f = tmp_path / "test.py"
        f.write_text("def foo(): pass\n")
        st = f.stat()
        db.upsert_file_meta(str(f), st.st_size, st.st_mtime_ns, "abc123")
        meta = db.get_file_meta(str(f))
        assert meta is not None
        assert meta["size"] == st.st_size
        assert meta["mtime_ns"] == st.st_mtime_ns
        assert meta["content_hash"] == "abc123"

    def test_get_file_meta_missing(self, db: GraphDB):
        assert db.get_file_meta("/nonexistent.py") is None

    def test_upsert_updates_existing(self, db: GraphDB, tmp_path: Path):
        f = tmp_path / "test.py"
        f.write_text("v1")
        st1 = f.stat()
        db.upsert_file_meta(str(f), st1.st_size, st1.st_mtime_ns, "hash1")
        f.write_text("v2")
        st2 = f.stat()
        db.upsert_file_meta(str(f), st2.st_size, st2.st_mtime_ns, "hash2")
        meta = db.get_file_meta(str(f))
        assert meta["content_hash"] == "hash2"

    def test_delete_file_meta(self, db: GraphDB, tmp_path: Path):
        f = tmp_path / "test.py"
        f.write_text("x = 1")
        st = f.stat()
        db.upsert_file_meta(str(f), st.st_size, st.st_mtime_ns, "h")
        db.delete_file_meta(str(f))
        assert db.get_file_meta(str(f)) is None

    def test_content_hash_changes_on_modification(self, db: GraphDB, tmp_path: Path):
        f = tmp_path / "test.py"
        f.write_text("def foo(): pass\n")
        h1 = _file_content_hash(str(f))
        f.write_text("def bar(): pass\n")
        h2 = _file_content_hash(str(f))
        assert h1 != h2

    def test_content_hash_deterministic(self, tmp_path: Path):
        f = tmp_path / "test.py"
        f.write_text("x = 42\n")
        assert _file_content_hash(str(f)) == _file_content_hash(str(f))

    def test_is_file_unchanged_returns_meta(self, db: GraphDB, tmp_path: Path):
        f = tmp_path / "test.py"
        f.write_text("def foo(): pass\n")
        st = f.stat()
        h = _file_content_hash(str(f))
        db.upsert_file_meta(str(f), st.st_size, st.st_mtime_ns, h)
        assert _is_file_unchanged(db, str(f)) is not None

    def test_is_file_unchanged_returns_none_when_missing(self, db: GraphDB, tmp_path: Path):
        f = tmp_path / "test.py"
        assert _is_file_unchanged(db, str(f)) is None

    def test_is_file_unchanged_returns_none_when_modified(self, db: GraphDB, tmp_path: Path):
        f = tmp_path / "test.py"
        f.write_text("v1")
        st = f.stat()
        h = _file_content_hash(str(f))
        db.upsert_file_meta(str(f), st.st_size, st.st_mtime_ns, h)
        f.write_text("v2")
        assert _is_file_unchanged(db, str(f)) is None

    def test_indexed_files_table_exists(self, db: GraphDB):
        tables = db.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        names = [r["name"] for r in tables]
        assert "indexed_files" in names



    def test_cache_hit_does_not_rehash_unchanged_file(self, db: GraphDB, tmp_path: Path, monkeypatch):
        f = tmp_path / "test.py"
        f.write_text("def foo(): pass\n")
        st = f.stat()
        db.upsert_file_meta(str(f), st.st_size, st.st_mtime_ns, "stored-hash")

        import codepulse.graph as graph_mod
        def fail_hash(_: str) -> str:
            raise AssertionError("cache hit should not read and hash the file")
        monkeypatch.setattr(graph_mod, "_file_content_hash", fail_hash)

        assert graph_mod._is_file_unchanged(db, str(f)) is not None


class TestTurboIndex:
    @pytest.fixture
    def cp(self, tmp_path: Path) -> CodePulse:
        config = CodePulseConfig(data_dir=str(tmp_path / ".codepulse"))
        return CodePulse(config)

    def test_second_index_skips_unchanged_files(self, cp: CodePulse, sample_project: Path):
        cp.index_all(str(sample_project / "src"))
        meta_count = cp.db.conn.execute(
            "SELECT COUNT(*) FROM indexed_files"
        ).fetchone()[0]
        assert meta_count > 0, "Should have cached file metadata"
        result = cp.index_all(str(sample_project / "src"))
        assert result.files_skipped > 0, "Should skip unchanged files"
        assert result.cache_hits > 0
        assert result.files_indexed == 0, "No files should be re-indexed"

    def test_no_cache_forces_reindex(self, cp: CodePulse, sample_project: Path):
        cp.index_all(str(sample_project / "src"))
        result = cp.index_all(str(sample_project / "src"), no_cache=True)
        assert result.files_indexed > 0, "Should re-index when no_cache=True"
        assert result.files_skipped == 0, "No files should be skipped"

    def test_modified_file_refreshes_nodes(self, cp: CodePulse, sample_project: Path):
        cp.index_all(str(sample_project / "src"))
        sample_py = sample_project / "src" / "sample.py"
        original = sample_py.read_text()
        first_nodes = cp.db.get_nodes_by_file(str(sample_py.resolve()))
        first_count = len(first_nodes)

        modified = original + "\ndef brand_new_func():\n    return 99\n"
        sample_py.write_text(modified)

        result = cp.index_all(str(sample_project / "src"))
        assert result.files_indexed > 0

        new_nodes = cp.db.get_nodes_by_file(str(sample_py.resolve()))
        new_names = {n.name for n in new_nodes}
        assert "brand_new_func" in new_names, "New function should be indexed"

        assert len(new_nodes) > first_count, "Should have more nodes with new function"

        old_names = {n.name.split(".")[-1] for n in first_nodes}
        for name in old_names:
            found = any(name in n.name for n in new_nodes)
            assert found, f"Original symbol '{name}' should still exist"


    def test_changed_file_to_zero_symbols_clears_old_nodes(self, cp: CodePulse, sample_project: Path):
        sample_py = sample_project / "src" / "sample.py"
        resolved = str(sample_py.resolve())
        cp.index_all(str(sample_project / "src"))
        assert len(cp.db.get_nodes_by_file(resolved)) > 0

        sample_py.write_text("# emptied module; no symbols now\n")
        result = cp.index_all(str(sample_project / "src"))
        assert result.files_indexed > 0
        assert cp.db.get_nodes_by_file(resolved) == []

    def test_notes_survive_file_refresh(self, cp: CodePulse, sample_project: Path):
        sample_py = sample_project / "src" / "sample.py"
        resolved = str(sample_py.resolve())
        cp.index_all(str(sample_project / "src"))
        nodes = cp.db.get_nodes_by_file(resolved)
        assert len(nodes) > 0
        target_id = nodes[0].id

        cp.add_symbol_note(target_id, "Important architectural note", source="test")
        notes_before = cp.list_symbol_notes(target_id)
        assert len(notes_before) == 1

        original = sample_py.read_text()
        sample_py.write_text(original + "\ndef another_func():\n    pass\n")
        cp.index_all(str(sample_project / "src"))

        notes_after = cp.list_symbol_notes(target_id)
        assert len(notes_after) == 1, "Notes should survive file refresh"
        assert notes_after[0].note == "Important architectural note"

    def test_parallel_index_no_errors(self, cp: CodePulse, sample_project: Path):
        result = cp.index_all(str(sample_project / "src"), no_cache=True, workers=2)
        assert result.files_indexed > 0
        assert result.symbols_found > 0
        assert len(result.errors) == 0, f"Unexpected errors: {result.errors}"

    def test_default_workers_is_reasonable(self):
        w = _default_workers()
        assert 1 <= w <= 64

    def test_index_result_has_new_fields(self, cp: CodePulse, sample_project: Path):
        result = cp.index_all(str(sample_project / "src"))
        assert hasattr(result, "elapsed_seconds")
        assert hasattr(result, "files_skipped")
        assert hasattr(result, "cache_hits")
        assert hasattr(result, "cache_misses")
        assert hasattr(result, "workers")
        assert result.elapsed_seconds > 0


class TestTurboCLI:
    def test_index_no_cache_flag(self, cli_runner, sample_project: Path):
        from codepulse.cli import cli
        runner = cli_runner
        data_dir = sample_project / ".codepulse"
        runner.invoke(cli, ["--data-dir", str(data_dir), "index", str(sample_project / "src")])
        result = runner.invoke(cli, ["--data-dir", str(data_dir), "index", str(sample_project / "src"), "--no-cache"])
        assert result.exit_code == 0

    def test_index_workers_flag(self, cli_runner, sample_project: Path):
        from codepulse.cli import cli
        runner = cli_runner
        data_dir = sample_project / ".codepulse"
        result = runner.invoke(cli, ["--data-dir", str(data_dir), "index", str(sample_project / "src"), "--workers", "2"])
        assert result.exit_code == 0

    def test_bench_command_smoke(self, cli_runner, tmp_path: Path):
        from codepulse.cli import cli
        runner = cli_runner
        (tmp_path / "bench_test.py").write_text("def f(): pass\n")
        data_dir = tmp_path / ".codepulse"
        result = runner.invoke(cli, ["--data-dir", str(data_dir), "bench", str(tmp_path)])
        assert result.exit_code == 0
        assert "files/s" in result.output or "Elapsed" in result.output or "Symbols" in result.output
