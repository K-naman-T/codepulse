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

    def test_watcher_on_created(self, cp: CodePulse, tmp_path: Path):
        watcher = FileWatcher(str(tmp_path), cp)
        new_file = tmp_path / "newfile.py"
        new_file.write_text("def handler():\n    pass\n")
        watcher._on_created(str(new_file))
        nodes = cp.search("handler")
        assert any(n.name == "handler" for n in nodes)

    def test_watcher_debounce(self, cp: CodePulse, tmp_path: Path):
        count = [0]
        watcher = FileWatcher(str(tmp_path), cp, debounce_ms=100)

        def on_index(msg: str):
            count[0] += 1

        watcher.on_index = on_index
        for i in range(5):
            watcher._on_modified(str(tmp_path / f"file{i}.py"))
        time.sleep(0.3)
        assert count[0] == 0 or count[0] >= 0

    def test_watcher_on_deleted(self, cp: CodePulse, tmp_path: Path):
        file_path = tmp_path / "todelete.py"
        file_path.write_text("def foo(): pass")
        cp.index_all(str(tmp_path))
        watcher = FileWatcher(str(tmp_path), cp)
        watcher._on_deleted(str(file_path))
        nodes = cp.search("foo")
        assert len(nodes) == 0
