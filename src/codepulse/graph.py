import hashlib
import multiprocessing as _mp
import os
import time
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from codepulse.config import CodePulseConfig
from codepulse.db import GraphDB, Node, Edge, SymbolNote
from codepulse.parser import SourceParser, _parse_files_worker


@dataclass
class IndexResult:
    files_indexed: int = 0
    symbols_found: int = 0
    edges_found: int = 0
    errors: list[str] = field(default_factory=list)
    elapsed_seconds: float = 0.0
    files_skipped: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    workers: int = 1


@dataclass
class NodeDetail:
    node: Node
    source: str | None = None


def _file_content_hash(file_path: str) -> str:
    h = hashlib.blake2b()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _is_file_unchanged(db: GraphDB, file_path: str) -> dict | None:
    """Return cached metadata when a file can be skipped.

    The warm path must be metadata-only. Re-hashing every unchanged file would
    turn cache hits into a second full repo read, which defeats the point of a
    turbo indexer on large trees. The content hash is still recorded on writes
    for audit/debugging and for future optional verification modes.
    """
    meta = db.get_file_meta(file_path)
    if meta is None:
        return None
    try:
        st = os.stat(file_path)
    except OSError:
        return None
    if st.st_size != meta["size"] or st.st_mtime_ns != meta["mtime_ns"]:
        return None
    return meta


def _default_workers() -> int:
    return min(os.cpu_count() or 1, 8)


class CodePulse:
    def __init__(self, config: CodePulseConfig):
        self.config = config
        self._db: GraphDB | None = None
        self._parser: SourceParser | None = None

    @property
    def db(self) -> GraphDB:
        if self._db is None:
            self.config.ensure_data_dir()
            self._db = GraphDB(self.config.db_path)
            self._db.initialize()
        return self._db

    @property
    def parser(self) -> SourceParser:
        if self._parser is None:
            self._parser = SourceParser()
        return self._parser

    def init_project(self) -> None:
        self.config.ensure_data_dir()
        self.db.initialize()

    def index_all(
        self,
        path: str | None = None,
        on_progress: Callable[[str], None] | None = None,
        no_cache: bool = False,
        workers: int = 1,
    ) -> IndexResult:
        start = time.time()
        result = IndexResult(workers=workers)
        batch_nodes: list[Node] = []
        batch_edges: list[Edge] = []
        search_path = Path(path or ".")

        extensions = self._resolve_extensions()

        skip_dirs = {"node_modules", ".git", "__pycache__", "dist", "build", ".next", "venv", ".venv", "target", ".tox"}
        files = [
            f for f in search_path.rglob("*")
            if f.suffix in extensions and f.is_file() and not any(
                part in skip_dirs for part in f.relative_to(search_path).parts
            )
        ]

        if workers > 1:
            self._index_parallel(files, result, batch_nodes, batch_edges, on_progress, no_cache, workers)
        else:
            self._index_sequential(files, result, batch_nodes, batch_edges, on_progress, no_cache)

        if batch_nodes:
            self.db.bulk_import(batch_nodes, batch_edges)

        if self.config.use_scip:
            try:
                from codepulse.compat.scip import index_with_scip
                if on_progress:
                    on_progress("Running SCIP indexer for accurate symbol resolution...")
                scip_count = index_with_scip(str(search_path), self.db)
                result.symbols_found += scip_count
                if on_progress:
                    on_progress(f"SCIP added {scip_count} symbols")
            except Exception as e:
                result.errors.append(f"SCIP: {e}")

        result.elapsed_seconds = time.time() - start
        return result

    def _resolve_extensions(self) -> tuple:
        from codepulse.parser import _EXTENSION_MAP
        return tuple(
            self.config.watch_extensions
            if self.config.watch_extensions
            else list(_EXTENSION_MAP.keys())
        )

    def _index_sequential(
        self,
        files: list[Path],
        result: IndexResult,
        batch_nodes: list[Node],
        batch_edges: list[Edge],
        on_progress: Callable[[str], None] | None,
        no_cache: bool,
    ) -> None:
        for file_path in files:
            fp = str(file_path)
            cached = None if no_cache else _is_file_unchanged(self.db, fp)
            if cached:
                result.files_skipped += 1
                result.cache_hits += 1
                if on_progress:
                    on_progress(f"Skipping (unchanged) {fp}")
                continue
            result.cache_misses += 1
            try:
                if on_progress:
                    on_progress(f"Indexing {fp}")
                symbols, refs = self.parser.parse_file(fp)
                # Always clear old graph rows for a refreshed file, even when the
                # new file parses to zero symbols (e.g. file emptied or changed to
                # comments only). Symbol notes intentionally live in a separate
                # table and survive this graph refresh.
                self.db.delete_file_nodes(fp)
                batch_nodes.extend(symbols)
                batch_edges.extend(refs)
                result.files_indexed += 1
                result.symbols_found += len(symbols)
                result.edges_found += len(refs)
                self._update_file_cache(fp)

                if len(batch_nodes) > 500:
                    self.db.bulk_import(batch_nodes, batch_edges)
                    batch_nodes.clear()
                    batch_edges.clear()

            except Exception as e:
                result.errors.append(f"{fp}: {e}")

    def _index_parallel(
        self,
        files: list[Path],
        result: IndexResult,
        batch_nodes: list[Node],
        batch_edges: list[Edge],
        on_progress: Callable[[str], None] | None,
        no_cache: bool,
        workers: int,
    ) -> None:
        files_to_index: list[str] = []
        for file_path in files:
            fp = str(file_path)
            cached = None if no_cache else _is_file_unchanged(self.db, fp)
            if cached:
                result.files_skipped += 1
                result.cache_hits += 1
                continue
            result.cache_misses += 1
            files_to_index.append(fp)

        if not files_to_index:
            return

        chunk_size = max(1, len(files_to_index) // workers)
        chunks = [files_to_index[i:i + chunk_size] for i in range(0, len(files_to_index), chunk_size)]

        ctx = _mp.get_context("fork")
        with ProcessPoolExecutor(max_workers=workers, mp_context=ctx) as executor:
            futures = {executor.submit(_parse_files_worker, chunk): chunk for chunk in chunks}
            for future in as_completed(futures):
                try:
                    for fp, symbols, edges, error in future.result():
                        if error:
                            result.errors.append(error)
                            result.files_indexed += 1
                            continue
                        # Always clear old graph rows for a refreshed file, even
                        # when the new parse returns zero symbols.
                        self.db.delete_file_nodes(fp)
                        batch_nodes.extend(symbols)
                        batch_edges.extend(edges)
                        result.files_indexed += 1
                        result.symbols_found += len(symbols)
                        result.edges_found += len(edges)
                        self._update_file_cache(fp)

                        if len(batch_nodes) > 500:
                            self.db.bulk_import(batch_nodes, batch_edges)
                            batch_nodes.clear()
                            batch_edges.clear()
                except Exception as e:
                    result.errors.append(f"Worker error: {e}")

    def _update_file_cache(self, file_path: str) -> None:
        try:
            st = os.stat(file_path)
            ch = _file_content_hash(file_path)
            self.db.upsert_file_meta(file_path, st.st_size, st.st_mtime_ns, ch)
        except OSError:
            pass

    def search(self, query: str, kind: str | None = None, limit: int = 20) -> list[Node]:
        return self.db.search_nodes(query, kind=kind, limit=limit)

    def get_callers(self, node_id: str, depth: int = 1) -> list[tuple[Node, str]]:
        return self.db.get_callers(node_id, depth=depth)

    def get_callees(self, node_id: str, depth: int = 1) -> list[tuple[Node, str]]:
        return self.db.get_callees(node_id, depth=depth)

    def get_impact_radius(self, node_id: str, depth: int = 3) -> dict[int, list[Node]]:
        return self.db.get_impact_radius(node_id, max_depth=depth)

    def add_symbol_note(self, symbol_id: str, note: str, source: str = "human") -> SymbolNote:
        return self.db.add_symbol_note(symbol_id, note, source=source)

    def list_symbol_notes(self, symbol_id: str, limit: int = 20) -> list[SymbolNote]:
        return self.db.list_symbol_notes(symbol_id, limit=limit)

    def search_symbol_notes(self, query: str, limit: int = 20) -> list[SymbolNote]:
        return self.db.search_symbol_notes(query, limit=limit)

    def get_node(self, node_id: str, include_source: bool = False) -> NodeDetail | None:
        node = self.db.get_node(node_id)
        if node is None:
            return None
        source = None
        if include_source:
            try:
                fpath = Path(node.file_path)
                if fpath.exists():
                    source = fpath.read_text()
            except (OSError, IOError):
                pass
        return NodeDetail(node=node, source=source)

    def build_context(self, task: str, max_nodes: int = 30) -> str:
        lines: list[str] = []
        lines.append(f"# Code Context: {task}")
        lines.append("")

        ranked = self.db.get_node_rankings(limit=max_nodes)
        if not ranked:
            ranked_with_kind = []
            for lang in self.config.languages:
                nodes = self.db.search_nodes("", kind="class", limit=max_nodes // 2)
                for n in nodes:
                    ranked_with_kind.append((n, 0))
            ranked = ranked_with_kind

        for node, score in ranked:
            lines.append(f"## {node.kind.title()}: {node.name}")
            if node.signature:
                lines.append(f"   {node.signature}")
            lines.append(f"   File: {node.file_path}:{node.line_start}")
            lines.append(f"   References: {score}")
            lines.append("")

        if not lines:
            lines.append("(No symbols indexed yet. Run `index` first.)")

        return "\n".join(lines)

    def validate(self) -> "ValidationReport":
        """Run validation checks on the indexed graph and return a report."""
        conn = self.db.conn
        total_nodes = conn.execute("SELECT COUNT(*) FROM nodes").fetchone()[0]
        total_edges = conn.execute("SELECT COUNT(*) FROM edges").fetchone()[0]
        total_files = conn.execute("SELECT COUNT(DISTINCT file_path) FROM nodes").fetchone()[0]

        kind_counts = dict(
            conn.execute("SELECT kind, COUNT(*) as cnt FROM nodes GROUP BY kind ORDER BY cnt DESC").fetchall()
        )
        edge_kind_counts = dict(
            conn.execute("SELECT kind, COUNT(*) as cnt FROM edges GROUP BY kind ORDER BY cnt DESC").fetchall()
        )
        lang_counts = dict(
            conn.execute("SELECT language, COUNT(*) as cnt FROM nodes GROUP BY language ORDER BY cnt DESC").fetchall()
        )
        error_count = conn.execute("SELECT COUNT(*) FROM edges WHERE kind = 'error'").fetchone()[0]

        orphans = conn.execute(
            "SELECT COUNT(*) FROM nodes WHERE parent_id IS NOT NULL AND parent_id NOT IN (SELECT id FROM nodes)"
        ).fetchone()[0]
        nodes_with_parent = conn.execute(
            "SELECT COUNT(*) FROM nodes WHERE parent_id IS NOT NULL"
        ).fetchone()[0]

        return ValidationReport(
            total_files=total_files,
            total_nodes=total_nodes,
            total_edges=total_edges,
            by_kind=kind_counts,
            by_edge_kind=edge_kind_counts,
            by_language=lang_counts,
            nodes_with_parent=nodes_with_parent,
            orphan_parent_refs=orphans,
        )

    def close(self) -> None:
        if self._db:
            self._db.close()


@dataclass
class ValidationReport:
    total_files: int = 0
    total_nodes: int = 0
    total_edges: int = 0
    by_kind: dict[str, int] = field(default_factory=dict)
    by_edge_kind: dict[str, int] = field(default_factory=dict)
    by_language: dict[str, int] = field(default_factory=dict)
    nodes_with_parent: int = 0
    orphan_parent_refs: int = 0

    def summary(self) -> str:
        lines = []
        lines.append(f"Files:      {self.total_files}")
        lines.append(f"Symbols:    {self.total_nodes}")
        lines.append(f"Edges:      {self.total_edges}")
        lines.append("")
        lines.append("By kind:")
        for kind, count in sorted(self.by_kind.items(), key=lambda x: -x[1]):
            lines.append(f"  {kind}: {count}")
        lines.append("")
        lines.append("By edge kind:")
        for kind, count in sorted(self.by_edge_kind.items(), key=lambda x: -x[1]):
            lines.append(f"  {kind}: {count}")
        lines.append("")
        lines.append("By language:")
        for lang, count in sorted(self.by_language.items(), key=lambda x: -x[1]):
            lines.append(f"  {lang}: {count}")
        lines.append("")
        lines.append(f"Parent-child relationships: {self.nodes_with_parent}")
        if self.orphan_parent_refs:
            lines.append(f"  ⚠  Orphan parent refs: {self.orphan_parent_refs}")
        else:
            lines.append("  No orphan refs")
        return "\n".join(lines)
