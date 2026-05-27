import time
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from codepulse.config import CodePulseConfig
from codepulse.db import GraphDB, Node, Edge
from codepulse.parser import SourceParser


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

                if len(batch_nodes) > 500:
                    self.db.bulk_import(batch_nodes, batch_edges)
                    batch_nodes.clear()
                    batch_edges.clear()

            except Exception as e:
                result.errors.append(f"{file_path}: {e}")

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

        return result

    def search(self, query: str, kind: str | None = None, limit: int = 20) -> list[Node]:
        return self.db.search_nodes(query, kind=kind, limit=limit)

    def get_callers(self, node_id: str, depth: int = 1) -> list[tuple[Node, str]]:
        return self.db.get_callers(node_id, depth=depth)

    def get_callees(self, node_id: str, depth: int = 1) -> list[tuple[Node, str]]:
        return self.db.get_callees(node_id, depth=depth)

    def get_impact_radius(self, node_id: str, depth: int = 3) -> dict[int, list[Node]]:
        return self.db.get_impact_radius(node_id, max_depth=depth)

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
