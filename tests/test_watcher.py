import os
import time
from pathlib import Path
from threading import Event

import pytest

from codepulse.config import CodePulseConfig
from codepulse.graph import CodePulse
from codepulse.watcher import FileWatcher


class TestFileWatcher:
    @pytest.fixture
    def cp(self, tmp_path: Path):
        config = CodePulseConfig(data_dir=str(tmp_path / ".codepulse"))
        instance = CodePulse(config)
        instance.init_project()
        return instance

    def test_watcher_created(self, cp: CodePulse, tmp_path: Path):
        watcher = FileWatcher(str(tmp_path), cp)
        assert watcher is not None
        assert watcher.root == str(tmp_path)

    def test_watcher_start_stop(self, cp: CodePulse, tmp_path: Path):
        watcher = FileWatcher(str(tmp_path), cp)
        watcher.start()
        time.sleep(0.1)
        watcher.stop()
        assert not watcher.is_running()

    def test_watcher_ignores_non_code(self, cp: CodePulse, tmp_path: Path):
        watcher = FileWatcher(str(tmp_path), cp)
        assert not watcher._should_handle("readme.md")
        assert not watcher._should_handle(".hidden")
        assert watcher._should_handle("test.py")
        assert watcher._should_handle("app.ts")

    def test_watcher_process_pending_created(self, cp: CodePulse, tmp_path: Path):
        watcher = FileWatcher(str(tmp_path), cp)
        new_file = tmp_path / "newfile.py"
        new_file.write_text("def handler():\n    pass\n")
        watcher._on_event(str(new_file))
        watcher.process_pending()
        nodes = cp.search("handler")
        assert any(n.name == "handler" for n in nodes)

    def test_watcher_process_pending_modified(self, cp: CodePulse, tmp_path: Path):
        watcher = FileWatcher(str(tmp_path), cp)
        pyfile = tmp_path / "mod.py"
        pyfile.write_text("def foo():\n    pass\n")
        cp.index_file(str(pyfile))
        old_nodes = cp.search("foo")
        assert len(old_nodes) == 1

        pyfile.write_text("def bar():\n    pass\n")
        watcher._on_event(str(pyfile))
        watcher.process_pending()
        new_nodes = cp.search("bar")
        assert any(n.name == "bar" for n in new_nodes)
        old_foo = cp.search("foo")
        assert len(old_foo) == 0

    def test_watcher_process_pending_deleted(self, cp: CodePulse, tmp_path: Path):
        pyfile = tmp_path / "todelete.py"
        pyfile.write_text("def foo():\n    pass\n")
        cp.index_file(str(pyfile))
        old_nodes = cp.search("foo")
        assert len(old_nodes) == 1

        watcher = FileWatcher(str(tmp_path), cp)
        os.remove(str(pyfile))
        watcher._on_event(str(pyfile))
        watcher.process_pending()
        nodes = cp.search("foo")
        assert len(nodes) == 0

    def test_watcher_debounce(self, cp: CodePulse, tmp_path: Path):
        count = [0]
        watcher = FileWatcher(str(tmp_path), cp)

        def on_index(msg: str):
            count[0] += 1

        watcher.on_index = on_index
        for i in range(5):
            (tmp_path / f"file{i}.py").write_text(f"def f{i}(): pass\n")
            watcher._on_event(str(tmp_path / f"file{i}.py"))
        watcher.process_pending()
        assert count[0] == 5
        for i in range(5):
            nodes = cp.search(f"f{i}")
            assert any(n.name == f"f{i}" for n in nodes)

    def test_index_file_cross_file_resolution(self, cp: CodePulse, tmp_path: Path):
        a = tmp_path / "a.py"
        a.write_text("def helper():\n    return 42\n")
        b = tmp_path / "b.py"
        b.write_text("def caller():\n    return helper()\n")

        cp.index_file(str(a))
        cp.index_file(str(b))

        helper_nodes = [n for n in cp.search("helper") if n.name == "helper"]
        assert len(helper_nodes) == 1
        callers = cp.get_callers(helper_nodes[0].id, depth=1)
        assert any(n.name == "caller" for n, _ in callers)

    def test_delete_file_removes_nodes_edges_and_files_entry(self, cp: CodePulse, tmp_path: Path):
        pyfile = tmp_path / "cleanup.py"
        pyfile.write_text("def doit():\n    pass\n")
        cp.index_file(str(pyfile))

        file_nodes = cp.db.conn.execute(
            "SELECT COUNT(*) FROM nodes WHERE file_path = ?", (str(pyfile.resolve()),)
        ).fetchone()[0]
        assert file_nodes > 0

        cp.delete_file(str(pyfile))

        file_nodes = cp.db.conn.execute(
            "SELECT COUNT(*) FROM nodes WHERE file_path = ?", (str(pyfile.resolve()),)
        ).fetchone()[0]
        assert file_nodes == 0

        file_entry = cp.db.conn.execute(
            "SELECT COUNT(*) FROM files WHERE path = ?", (str(pyfile.resolve()),)
        ).fetchone()[0]
        assert file_entry == 0

    def test_watcher_does_not_crash_on_nonexistent_file(self, cp: CodePulse, tmp_path: Path):
        watcher = FileWatcher(str(tmp_path), cp)
        watcher._on_event(str(tmp_path / "nonexistent.py"))
        watcher.process_pending()
        assert watcher.last_error is None

    def test_watcher_real_observer_start_stop(self, cp: CodePulse, tmp_path: Path):
        watcher = FileWatcher(str(tmp_path), cp)
        watcher.start()
        assert watcher.is_running()
        watcher.stop()
        assert not watcher.is_running()

    def test_watcher_thread_safety(self, cp: CodePulse, tmp_path: Path):
        _ = cp.db.conn
        new_file = tmp_path / "thread_test.py"
        new_file.write_text("def thread_safe():\n    return 42\n")
        watcher = FileWatcher(str(tmp_path), cp)
        watcher._on_event(str(new_file))

        errors = []
        def run():
            try:
                watcher.process_pending()
            except Exception as e:
                errors.append(e)

        from threading import Thread
        t = Thread(target=run, daemon=True)
        t.start()
        t.join(timeout=10)

        assert not errors, f"Thread raised: {errors}"
        assert watcher.last_error is None
        nodes = cp.search("thread_safe")
        assert any(n.name == "thread_safe" for n in nodes)

    def test_watcher_error_sets_last_error(self, cp: CodePulse, tmp_path: Path):
        from unittest.mock import patch
        watcher = FileWatcher(str(tmp_path), cp)
        new_file = tmp_path / "fail.py"
        new_file.write_text("def ok(): pass\n")
        watcher._on_event(str(new_file))
        with patch.object(cp, "index_file", side_effect=RuntimeError("index failed")):
            watcher.process_pending()
        assert watcher.last_error is not None
        assert "index failed" in str(watcher.last_error)
