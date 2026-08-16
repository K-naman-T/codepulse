import hashlib
import multiprocessing as _mp
import os
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from codepulse.config import CodePulseConfig
from codepulse.db import Edge, GraphDB, Node, SymbolNote
from codepulse.parser import SourceParser, _parse_files_worker
from codepulse.validation import ValidationReport, validate_graph


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
    digest = hashlib.blake2b()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _escape_like(s: str) -> str:
    return s.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _is_file_unchanged(db: GraphDB, file_path: str) -> dict | None:
    """Return cached metadata when a file can be skipped."""
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
        skip_dirs = {
            "node_modules", ".git", "__pycache__", "dist", "build",
            ".next", "venv", ".venv", "target", ".tox",
        }
        files = [
            f for f in search_path.rglob("*")
            if f.suffix in extensions and f.is_file() and not any(
                part in skip_dirs for part in f.relative_to(search_path).parts
            )
        ]
        self._prune_missing_files(search_path, files)

        if workers > 1:
            self._index_parallel(files, result, batch_nodes, batch_edges, on_progress, no_cache, workers)
        else:
            self._index_sequential(files, result, batch_nodes, batch_edges, on_progress, no_cache)

        if batch_nodes or batch_edges:
            self.db.bulk_import(batch_nodes, batch_edges)

        if self.config.use_scip:
            try:
                from codepulse.compat.scip import index_with_scip, reconcile_scip_edges
                if on_progress:
                    on_progress("Running SCIP indexer for accurate symbol resolution...")
                scip_count = index_with_scip(str(search_path), self.db)
                result.symbols_found += scip_count
                if on_progress:
                    on_progress(f"SCIP added {scip_count} symbols")
                reconciled = reconcile_scip_edges(self.db)
                if reconciled and on_progress:
                    on_progress(f"Reconciled {reconciled} edges with SCIP")
            except Exception as e:
                result.errors.append(f"SCIP: {e}")

        resolved_count = self.db.resolve_cross_file_edges()
        if resolved_count and on_progress:
            on_progress(f"Resolved {resolved_count} cross-file calls")

        result.elapsed_seconds = time.time() - start
        return result

    def _resolve_extensions(self) -> tuple[str, ...]:
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
            fp = str(file_path.resolve())
            cached = None if no_cache else _is_file_unchanged(self.db, fp)
            if cached:
                result.files_skipped += 1
                result.cache_hits += 1
                self._add_cached_counts(result, fp)
                if on_progress:
                    on_progress(f"Skipping (unchanged) {fp}")
                continue
            result.cache_misses += 1
            try:
                if on_progress:
                    on_progress(f"Indexing {fp}")
                symbols, refs = self.parser.parse_file(fp)
                self._ingest_indexed_file(fp, symbols, refs, result, batch_nodes, batch_edges)
            except Exception as e:
                result.errors.append(f"{fp}: {e}")
                result.files_indexed += 1
                self._record_file_error(fp, e)

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
            fp = str(file_path.resolve())
            cached = None if no_cache else _is_file_unchanged(self.db, fp)
            if cached:
                result.files_skipped += 1
                result.cache_hits += 1
                self._add_cached_counts(result, fp)
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
                            result.errors.append(f"{fp}: {error}")
                            result.files_indexed += 1
                            self._record_file_error(fp, error)
                            continue
                        self._ingest_indexed_file(fp, symbols, edges, result, batch_nodes, batch_edges)
                except Exception as e:
                    result.errors.append(f"Worker error: {e}")

    def _ingest_indexed_file(
        self,
        file_path: str,
        symbols: list[Node],
        refs: list[Edge],
        result: IndexResult,
        batch_nodes: list[Node],
        batch_edges: list[Edge],
    ) -> None:
        self.db.delete_file_nodes(file_path)
        batch_nodes.extend(symbols)
        batch_edges.extend(refs)
        result.files_indexed += 1
        result.symbols_found += len(symbols)
        result.edges_found += len(refs)
        self._update_file_cache(file_path)

        if len(batch_nodes) > 500:
            self.db.bulk_import(batch_nodes, batch_edges)
            batch_nodes.clear()
            batch_edges.clear()

    def _update_file_cache(self, file_path: str) -> None:
        try:
            st = os.stat(file_path)
            ch = _file_content_hash(file_path)
            self.db.upsert_file_meta(file_path, st.st_size, st.st_mtime_ns, ch)
        except OSError:
            pass

    def _record_file_error(self, file_path: str, error: Exception | str) -> None:
        lang = self.parser.detect_language(file_path) or ""
        self.db.conn.execute(
            "INSERT OR REPLACE INTO files (path, language, content_hash, error) VALUES (?, ?, ?, ?)",
            (file_path, lang, "", str(error)),
        )

    def _add_cached_counts(self, result: IndexResult, file_path: str) -> None:
        row = self.db.conn.execute(
            "SELECT COUNT(*) AS cnt FROM nodes WHERE file_path = ?",
            (file_path,),
        ).fetchone()
        edge_row = self.db.conn.execute(
            "SELECT COUNT(*) AS cnt FROM edges WHERE file_path = ?",
            (file_path,),
        ).fetchone()
        result.symbols_found += row["cnt"] if row else 0
        result.edges_found += edge_row["cnt"] if edge_row else 0

    def _prune_missing_files(self, search_path: Path, files: list[Path]) -> None:
        resolved = str(search_path.resolve())
        prefix = f"{_escape_like(resolved)}/%"
        current = {str(f.resolve()) for f in files}
        rows = self.db.conn.execute(
            """SELECT file_path AS path FROM indexed_files
               WHERE file_path = ? OR file_path LIKE ? ESCAPE '\\'
               UNION
               SELECT path FROM files
               WHERE path = ? OR path LIKE ? ESCAPE '\\'""",
            (resolved, prefix, resolved, prefix),
        ).fetchall()
        for row in rows:
            old_path = row["path"]
            if old_path not in current and not Path(old_path).exists():
                self.db.delete_file_nodes(old_path)
                self.db.delete_file_meta(old_path)

    def index_file(self, path: str) -> None:
        """Incrementally index a single file, replacing stale graph data for it."""
        resolved = str(Path(path).resolve())
        self.db.delete_file_nodes(resolved)
        symbols, refs = self.parser.parse_file(resolved)
        self.db.bulk_import(symbols, refs)
        self._update_file_cache(resolved)
        self.db.resolve_cross_file_edges()

    def delete_file(self, path: str) -> None:
        """Remove graph and cache data for a file."""
        resolved = str(Path(path).resolve())
        self.db.delete_file_nodes(resolved)
        self.db.delete_file_meta(resolved)

    def search(self, query: str, kind: str | None = None, limit: int = 20) -> list[Node]:
        return self.db.search_nodes(query, kind=kind, limit=limit)

    def get_callers(self, node_id: str, depth: int = 1,
                    edge_kinds: set[str] | None = None) -> list[tuple[Node, str]]:
        return self.db.get_callers(node_id, depth=depth, edge_kinds=edge_kinds)

    def get_callees(self, node_id: str, depth: int = 1,
                    edge_kinds: set[str] | None = None) -> list[tuple[Node, str]]:
        return self.db.get_callees(node_id, depth=depth, edge_kinds=edge_kinds)

    def get_impact_radius(self, node_id: str, depth: int = 3,
                          edge_kinds: set[str] | None = None) -> dict[int, list[Node]]:
        return self.db.get_impact_radius(node_id, max_depth=depth, edge_kinds=edge_kinds)

    def trace_path(self, source: str, target: str, max_depth: int = 10,
                   edge_kinds: set[str] | None = None) -> list[Node] | None:
        return self.db.trace_path(source, target, max_depth=max_depth, edge_kinds=edge_kinds)

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

    def validate(self) -> ValidationReport:
        """Run validation checks on the indexed graph and return a report."""
        return validate_graph(self.db)

    def close(self) -> None:
        if self._db:
            self._db.close()
