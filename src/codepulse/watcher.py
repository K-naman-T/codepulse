import os
import time
from pathlib import Path
from threading import Lock, Thread
from typing import Callable

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from codepulse.graph import CodePulse


class _CodePulseHandler(FileSystemEventHandler):
    def __init__(self, watcher: "FileWatcher"):
        super().__init__()
        self._watcher = watcher

    def on_created(self, event):
        if not event.is_directory:
            self._watcher._on_event(event.src_path)

    def on_modified(self, event):
        if not event.is_directory:
            self._watcher._on_event(event.src_path)

    def on_deleted(self, event):
        if not event.is_directory:
            self._watcher._on_event(event.src_path)


class FileWatcher:
    def __init__(
        self,
        root: str,
        cp: CodePulse,
        debounce_ms: int = 500,
        extensions: list[str] | None = None,
    ):
        self.root = root
        self.cp = cp
        self.debounce_ms = debounce_ms
        self.extensions = extensions or [".py", ".ts", ".js", ".go"]
        self._running = False
        self._thread: Thread | None = None
        self._observer: Observer | None = None
        self._lock = Lock()
        self._pending: set[str] = set()
        self._debounce_timer: float = 0
        self.on_index: Callable[[str], None] | None = None
        self.last_error: Exception | None = None

    def _should_handle(self, path: str) -> bool:
        return Path(path).suffix in self.extensions

    def _on_event(self, path: str) -> None:
        if not self._should_handle(path):
            return
        with self._lock:
            self._pending.add(path)
            self._debounce_timer = time.monotonic() + self.debounce_ms / 1000

    def process_pending(self) -> None:
        with self._lock:
            paths = set(self._pending)
            self._pending.clear()
            self._debounce_timer = 0
        for path in paths:
            try:
                if os.path.exists(path):
                    self.cp.index_file(path)
                else:
                    self.cp.delete_file(path)
                if self.on_index:
                    self.on_index(f"{'Indexed' if os.path.exists(path) else 'Removed'}: {path}")
            except Exception as e:
                self.last_error = e
                if self.on_index:
                    self.on_index(f"Error: {path}: {e}")

    def start(self) -> None:
        self._running = True
        handler = _CodePulseHandler(self)
        self._observer = Observer()
        self._observer.schedule(handler, self.root, recursive=True)
        self._observer.start()
        self._thread = Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        if self._observer:
            self._observer.stop()
            self._observer.join(timeout=2)
            self._observer = None
        if self._thread:
            self._thread.join(timeout=2)
            self._thread = None

    def is_running(self) -> bool:
        return self._running

    def _run(self) -> None:
        while self._running:
            now = time.monotonic()
            with self._lock:
                expired = self._debounce_timer > 0 and now >= self._debounce_timer
            if expired:
                self.process_pending()
            time.sleep(0.05)
