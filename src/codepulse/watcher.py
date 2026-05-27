import time
from pathlib import Path
from threading import Event, Thread
from typing import Callable

from codepulse.graph import CodePulse


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
        self._debounce_timer: float = 0
        self._pending: set[str] = set()
        self._lock = type(
            "Lock", (), {"__enter__": lambda s: None, "__exit__": lambda *a: None}
        )()
        self.on_index: Callable[[str], None] | None = None

    def _should_handle(self, path: str) -> bool:
        return Path(path).suffix in self.extensions

    def _on_created(self, path: str) -> None:
        if not self._should_handle(path):
            return
        try:
            symbols, refs = self.cp.parser.parse_file(path)
            for sym in symbols:
                self.cp.db.upsert_node(sym)
            for ref in refs:
                self.cp.db.upsert_edge(ref)
            if self.on_index:
                self.on_index(f"Indexed new file: {path}")
        except Exception:
            pass

    def _on_modified(self, path: str) -> None:
        if not self._should_handle(path):
            return
        try:
            self.cp.db.delete_file_nodes(path)
            self._on_created(path)
            if self.on_index:
                self.on_index(f"Re-indexed: {path}")
        except Exception:
            pass

    def _on_deleted(self, path: str) -> None:
        if not self._should_handle(path):
            return
        try:
            self.cp.db.delete_file_nodes(path)
            if self.on_index:
                self.on_index(f"Removed: {path}")
        except Exception:
            pass

    def start(self) -> None:
        self._running = True
        self._thread = Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)

    def is_running(self) -> bool:
        return self._running

    def _run(self) -> None:
        import time as _time
        while self._running:
            _time.sleep(0.1)
