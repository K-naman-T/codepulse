import hashlib
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from codepulse.config import CodePulseConfig
from codepulse.db import GraphDB, Node, Edge
from codepulse.parser import SourceParser
from codepulse.validation import ValidationReport, validate_graph


def _escape_like(s: str) -> str:
    return s.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


@dataclass
class IndexResult:
    files_indexed: int = 0
    symbols_found: int = 0
    edges_found: int = 0
    errors: list[str] = field(default_factory=list)


@dataclass
class NodeDetail:
    node: Node
    source: str | None = None


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
    ) -> IndexResult:
        result = IndexResult()
        batch_nodes: list[Node] = []
        batch_edges: list[Edge] = []
        search_path = Path(path or ".")

        from codepulse.parser import _EXTENSION_MAP
        extensions = tuple(
            self.config.watch_extensions
            if hasattr(self.config, "watch_extensions") and self.config.watch_extensions
            else list(_EXTENSION_MAP.keys())
        )

        skip_dirs = {"node_modules", ".git", "__pycache__", "dist", "build", ".next", "venv", ".venv", "target", ".tox"}
        files = [
            f for f in search_path.rglob("*")
            if f.suffix in extensions and f.is_file() and not any(
                part in skip_dirs for part in f.relative_to(search_path).parts
            )
        ]

        resolved = str(search_path.resolve())
        conn = self.db.conn

        # Wrap deletion and import in a single transaction so a mid-way failure
        # never leaves the graph in a half-deleted state.
        conn.execute("BEGIN TRANSACTION")
        try:
            # Delete stale data for the indexed path using exact path matching.
            # The trailing /% ensures /repo/src does not match /repo/src-old.
            conn.execute(
                "DELETE FROM edges WHERE file_path = ? OR file_path LIKE ? ESCAPE '\\'",
                [resolved, f"{_escape_like(resolved)}/%"],
            )

            old_paths = conn.execute(
                "SELECT DISTINCT file_path FROM nodes WHERE file_path = ? OR file_path LIKE ? ESCAPE '\\'",
                [resolved, f"{_escape_like(resolved)}/%"],
            ).fetchall()
            for (old_path,) in old_paths:
                conn.execute(
                    "DELETE FROM edges WHERE source_id IN (SELECT id FROM nodes WHERE file_path = ?)",
                    (old_path,),
                )
                conn.execute(
                    "DELETE FROM edges WHERE target_id IN (SELECT id FROM nodes WHERE file_path = ?)",
                    (old_path,),
                )
                conn.execute("DELETE FROM nodes WHERE file_path = ?", (old_path,))

            conn.execute(
                "DELETE FROM files WHERE path = ? OR path LIKE ? ESCAPE '\\'",
                [resolved, f"{_escape_like(resolved)}/%"],
            )

            for file_path in files:
                try:
                    if on_progress:
                        on_progress(f"Indexing {file_path}")
                    symbols, refs = self.parser.parse_file(str(file_path))
                    batch_nodes.extend(symbols)
                    batch_edges.extend(refs)
                    result.files_indexed += 1
                    result.symbols_found += len(symbols)
                    result.edges_found += len(refs)

                    fpath = str(file_path.resolve())
                    lang = self.parser.detect_language(fpath) or ""
                    try:
                        content_hash = hashlib.md5(
                            open(fpath, "rb").read()
                        ).hexdigest()
                    except OSError:
                        content_hash = ""
                    conn.execute(
                        "INSERT OR REPLACE INTO files (path, language, content_hash) VALUES (?, ?, ?)",
                        (fpath, lang, content_hash),
                    )

                    if len(batch_nodes) > 500:
                        self.db.bulk_import(batch_nodes, batch_edges)
                        batch_nodes.clear()
                        batch_edges.clear()

                except Exception as e:
                    result.errors.append(f"{file_path}: {e}")
                    fpath = str(file_path.resolve())
                    try:
                        conn.execute(
                            "INSERT OR REPLACE INTO files (path, language, content_hash, error) VALUES (?, ?, ?, ?)",
                            (fpath, "", "", str(e)),
                        )
                    except Exception:
                        pass

            # Import remaining batch even if it only contains edges (no real symbols)
            if batch_nodes or batch_edges:
                self.db.bulk_import(batch_nodes, batch_edges)

            conn.commit()
        except Exception:
            conn.rollback()
            raise

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

        return result

    def index_file(self, path: str) -> None:
        """Incrementally index a single file, replacing stale data for it."""
        resolved = str(Path(path).resolve())
        conn = self.db.conn

        conn.execute("BEGIN TRANSACTION")
        try:
            conn.execute("DELETE FROM edges WHERE file_path = ?", (resolved,))
            conn.execute(
                "DELETE FROM edges WHERE source_id IN (SELECT id FROM nodes WHERE file_path = ?)",
                (resolved,),
            )
            conn.execute(
                "DELETE FROM edges WHERE target_id IN (SELECT id FROM nodes WHERE file_path = ?)",
                (resolved,),
            )
            conn.execute("DELETE FROM nodes WHERE file_path = ?", (resolved,))
            conn.execute("DELETE FROM files WHERE path = ?", (resolved,))

            symbols, refs = self.parser.parse_file(resolved)
            for sym in symbols:
                self.db._upsert_node_raw(sym)
            for ref in refs:
                self.db._upsert_edge_raw(ref)

            lang = self.parser.detect_language(resolved) or ""
            try:
                content_hash = hashlib.md5(open(resolved, "rb").read()).hexdigest()
            except OSError:
                content_hash = ""
            conn.execute(
                "INSERT OR REPLACE INTO files (path, language, content_hash) VALUES (?, ?, ?)",
                (resolved, lang, content_hash),
            )

            conn.commit()
        except Exception:
            conn.rollback()
            raise

        self.db.resolve_cross_file_edges()

    def delete_file(self, path: str) -> None:
        """Remove all graph data for a file."""
        resolved = str(Path(path).resolve())
        conn = self.db.conn
        conn.execute("BEGIN TRANSACTION")
        try:
            conn.execute("DELETE FROM edges WHERE file_path = ?", (resolved,))
            conn.execute(
                "DELETE FROM edges WHERE source_id IN (SELECT id FROM nodes WHERE file_path = ?)",
                (resolved,),
            )
            conn.execute(
                "DELETE FROM edges WHERE target_id IN (SELECT id FROM nodes WHERE file_path = ?)",
                (resolved,),
            )
            conn.execute("DELETE FROM nodes WHERE file_path = ?", (resolved,))
            conn.execute("DELETE FROM files WHERE path = ?", (resolved,))
            conn.commit()
        except Exception:
            conn.rollback()
            raise

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

    def validate(self) -> ValidationReport:
        """Run validation checks on the indexed graph and return a report."""
        return validate_graph(self.db)

    def close(self) -> None:
        if self._db:
            self._db.close()



