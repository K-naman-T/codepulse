import json
import math
import sqlite3
from dataclasses import dataclass, field, asdict
from typing import Any, Optional

_SYNTHETIC_KINDS = ("file", "external_module", "unresolved_symbol")


@dataclass
class Node:
    id: str
    file_path: str
    name: str
    kind: str
    signature: str = ""
    line_start: int = 0
    line_end: int = 0
    parent_id: str | None = None
    language: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Edge:
    source_id: str
    target_id: str
    kind: str
    file_path: str = ""
    line_number: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)
    line_start: int = 0
    line_end: int = 0
    column_start: int = 0
    column_end: int = 0
    confidence: float = 1.0
    provenance: str = "tree-sitter"
    resolution_status: str = "resolved"

    def __post_init__(self) -> None:
        if self.line_start == 0 and self.line_number != 0:
            object.__setattr__(self, "line_start", self.line_number)
        if self.line_number == 0 and self.line_start != 0:
            object.__setattr__(self, "line_number", self.line_start)


class GraphDB:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._conn: sqlite3.Connection | None = None

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
        return self._conn

    def initialize(self) -> None:
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS nodes (
                id TEXT PRIMARY KEY,
                file_path TEXT NOT NULL,
                name TEXT NOT NULL,
                kind TEXT NOT NULL,
                signature TEXT DEFAULT '',
                line_start INTEGER DEFAULT 0,
                line_end INTEGER DEFAULT 0,
                parent_id TEXT,
                language TEXT DEFAULT '',
                metadata TEXT DEFAULT '{}',
                indexed_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS edges (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_id TEXT NOT NULL,
                target_id TEXT NOT NULL,
                kind TEXT NOT NULL,
                file_path TEXT DEFAULT '',
                line_number INTEGER DEFAULT 0,
                metadata TEXT DEFAULT '{}',
                line_start INTEGER DEFAULT 0,
                line_end INTEGER DEFAULT 0,
                column_start INTEGER DEFAULT 0,
                column_end INTEGER DEFAULT 0,
                confidence REAL DEFAULT 1.0,
                provenance TEXT DEFAULT 'tree-sitter',
                resolution_status TEXT DEFAULT 'resolved',
                UNIQUE(source_id, target_id, kind, file_path, line_start, column_start)
            );

            CREATE TABLE IF NOT EXISTS embeddings (
                node_id TEXT PRIMARY KEY REFERENCES nodes(id),
                vector BLOB NOT NULL,
                model TEXT NOT NULL DEFAULT '',
                dimensions INTEGER NOT NULL DEFAULT 384,
                indexed_at TEXT DEFAULT (datetime('now'))
            );

            CREATE INDEX IF NOT EXISTS idx_nodes_file ON nodes(file_path);
            CREATE INDEX IF NOT EXISTS idx_nodes_kind ON nodes(kind);
            CREATE INDEX IF NOT EXISTS idx_nodes_parent ON nodes(parent_id);
            CREATE INDEX IF NOT EXISTS idx_edges_source ON edges(source_id);
            CREATE INDEX IF NOT EXISTS idx_edges_target ON edges(target_id);

            CREATE VIRTUAL TABLE IF NOT EXISTS nodes_fts USING fts5(
                name, signature, metadata,
                content='nodes',
                content_rowid='rowid'
            );

            CREATE TRIGGER IF NOT EXISTS nodes_ai AFTER INSERT ON nodes BEGIN
                INSERT INTO nodes_fts(rowid, name, signature, metadata)
                VALUES (new.rowid, new.name, new.signature, new.metadata);
            END;

            CREATE TRIGGER IF NOT EXISTS nodes_ad AFTER DELETE ON nodes BEGIN
                INSERT INTO nodes_fts(nodes_fts, rowid, name, signature, metadata)
                VALUES ('delete', old.rowid, old.name, old.signature, old.metadata);
            END;

            CREATE TRIGGER IF NOT EXISTS nodes_au AFTER UPDATE ON nodes BEGIN
                INSERT INTO nodes_fts(nodes_fts, rowid, name, signature, metadata)
                VALUES ('delete', old.rowid, old.name, old.signature, old.metadata);
                INSERT INTO nodes_fts(rowid, name, signature, metadata)
                VALUES (new.rowid, new.name, new.signature, new.metadata);
            END;
        """)

        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS files (
                path TEXT PRIMARY KEY,
                language TEXT NOT NULL DEFAULT '',
                content_hash TEXT NOT NULL DEFAULT '',
                indexed_at TEXT DEFAULT (datetime('now')),
                error TEXT DEFAULT NULL
            )
        """)

        from codepulse.schema import ensure_schema
        ensure_schema(self.conn)

        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_edges_reconciliation
            ON edges(provenance, file_path, line_start, column_start, kind)
        """)

    def upsert_node(self, node: Node) -> str:
        self._upsert_node_raw(node)
        self.conn.commit()
        return node.id

    def _upsert_node_raw(self, node: Node) -> None:
        self.conn.execute(
            """INSERT INTO nodes (id, file_path, name, kind, signature, line_start, line_end, parent_id, language, metadata)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(id) DO UPDATE SET
                 file_path=excluded.file_path,
                 name=excluded.name,
                 kind=excluded.kind,
                 signature=excluded.signature,
                 line_start=excluded.line_start,
                 line_end=excluded.line_end,
                 parent_id=excluded.parent_id,
                 language=excluded.language,
                 metadata=excluded.metadata,
                 indexed_at=datetime('now')""",
            (
                node.id,
                node.file_path,
                node.name,
                node.kind,
                node.signature,
                node.line_start,
                node.line_end,
                node.parent_id,
                node.language,
                json.dumps(node.metadata),
            ),
        )

    def upsert_edge(self, edge: Edge) -> int:
        cursor = self._upsert_edge_raw(edge)
        self.conn.commit()
        return cursor.lastrowid or 0

    def _upsert_edge_raw(self, edge: Edge) -> sqlite3.Cursor:
        return self.conn.execute(
            """INSERT INTO edges (source_id, target_id, kind, file_path, line_number, metadata, line_start, line_end, column_start, column_end, confidence, provenance, resolution_status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(source_id, target_id, kind, file_path, line_start, column_start) DO UPDATE SET
                 line_end=excluded.line_end,
                 column_end=excluded.column_end,
                 confidence=excluded.confidence,
                 provenance=excluded.provenance,
                 resolution_status=excluded.resolution_status,
                 metadata=excluded.metadata""",
            (edge.source_id, edge.target_id, edge.kind, edge.file_path, edge.line_number,
             json.dumps(edge.metadata), edge.line_start, edge.line_end, edge.column_start,
             edge.column_end, edge.confidence, edge.provenance, edge.resolution_status),
        )

    def bulk_import(self, nodes: list[Node], edges: list[Edge]) -> tuple[int, int]:
        """Import many nodes and edges in a single transaction. Returns (node_count, edge_count).
        Uses savepoint if already inside a transaction so callers can nest safely.
        """
        manage_txn = not self.conn.in_transaction
        if manage_txn:
            self.conn.execute("BEGIN TRANSACTION")
        try:
            for node in nodes:
                self._upsert_node_raw(node)
            for edge in edges:
                self._upsert_edge_raw(edge)
            if manage_txn:
                self.conn.commit()
        except Exception:
            if manage_txn:
                self.conn.rollback()
            raise
        return len(nodes), len(edges)

    def get_node(self, node_id: str) -> Node | None:
        row = self.conn.execute(
            "SELECT * FROM nodes WHERE id = ?", (node_id,)
        ).fetchone()
        if row is None:
            return None
        return self._row_to_node(row)

    def _row_to_node(self, row: sqlite3.Row) -> Node:
        return Node(
            id=row["id"],
            file_path=row["file_path"],
            name=row["name"],
            kind=row["kind"],
            signature=row["signature"],
            line_start=row["line_start"],
            line_end=row["line_end"],
            parent_id=row["parent_id"],
            language=row["language"],
            metadata=json.loads(row["metadata"] or "{}"),
        )

    @staticmethod
    def _row_to_edge(row: sqlite3.Row) -> Edge:
        return Edge(
            source_id=row["source_id"],
            target_id=row["target_id"],
            kind=row["kind"],
            file_path=row["file_path"],
            line_number=row["line_number"],
            metadata=json.loads(row["metadata"] or "{}"),
            line_start=row["line_start"],
            line_end=row["line_end"],
            column_start=row["column_start"],
            column_end=row["column_end"],
            confidence=row["confidence"],
            provenance=row["provenance"],
            resolution_status=row["resolution_status"],
        )

    def search_nodes(self, query: str, kind: str | None = None, limit: int = 20) -> list[Node]:
        if not query.strip():
            sql = "SELECT * FROM nodes"
            params: list[Any] = []
            conditions: list[str] = []
            if kind:
                conditions.append("kind = ?")
                params.append(kind)
            else:
                conditions.append(f"kind NOT IN ({','.join('?' for _ in _SYNTHETIC_KINDS)})")
                params.extend(_SYNTHETIC_KINDS)
            if conditions:
                sql += " WHERE " + " AND ".join(conditions)
            sql += " ORDER BY name LIMIT ?"
            params.append(limit)
        else:
            sql = """SELECT n.* FROM nodes n
                     JOIN nodes_fts fts ON n.rowid = fts.rowid
                     WHERE nodes_fts MATCH ?"""
            params = [query]
            if kind:
                sql += " AND n.kind = ?"
                params.append(kind)
            else:
                sql += f" AND n.kind NOT IN ({','.join('?' for _ in _SYNTHETIC_KINDS)})"
                params.extend(_SYNTHETIC_KINDS)
            sql += " ORDER BY rank LIMIT ?"
            params.append(limit)
        rows = self.conn.execute(sql, params).fetchall()
        return [self._row_to_node(r) for r in rows]

    def get_callers(self, node_id: str, depth: int = 1) -> list[tuple[Node, str]]:
        return self._traverse_edges(node_id, depth, direction="incoming")

    def get_callees(self, node_id: str, depth: int = 1) -> list[tuple[Node, str]]:
        return self._traverse_edges(node_id, depth, direction="outgoing")

    def _traverse_edges(self, node_id: str, depth: int, direction: str) -> list[tuple[Node, str]]:
        results: list[tuple[Node, str]] = []
        visited: set[str] = set()
        current: set[str] = {node_id}

        if direction == "incoming":
            join_col, where_col = "source_id", "target_id"
        else:
            join_col, where_col = "target_id", "source_id"

        for _ in range(depth):
            if not current:
                break
            placeholders = ",".join("?" for _ in current)
            rows = self.conn.execute(
                f"""SELECT DISTINCT n.*, e.kind as edge_kind
                    FROM edges e
                    JOIN nodes n ON n.id = e.{join_col}
                    WHERE e.{where_col} IN ({placeholders})
                      AND e.{join_col} NOT IN ({placeholders})""",
                list(current) + list(current),
            ).fetchall()
            next_nodes: set[str] = set()
            for row in rows:
                node = self._row_to_node(row)
                if node.id not in visited:
                    visited.add(node.id)
                    results.append((node, row["edge_kind"]))
                    next_nodes.add(node.id)
            current = next_nodes
        return results

    def get_impact_radius(self, node_id: str, max_depth: int = 3) -> dict[int, list[Node]]:
        result: dict[int, list[Node]] = {}
        visited: set[str] = {node_id}
        current: set[str] = {node_id}
        for depth in range(1, max_depth + 1):
            if not current:
                break
            placeholders = ",".join("?" for _ in current)
            rows = self.conn.execute(
                f"""SELECT DISTINCT n.*
                    FROM edges e
                    JOIN nodes n ON n.id IN (e.source_id, e.target_id)
                    WHERE (e.source_id IN ({placeholders}) OR e.target_id IN ({placeholders}))
                      AND n.id NOT IN ({placeholders})""",
                list(current) + list(current) + list(visited),
            ).fetchall()
            nodes_at_depth: list[Node] = []
            for row in rows:
                node = self._row_to_node(row)
                if node.id not in visited:
                    visited.add(node.id)
                    nodes_at_depth.append(node)
                    current.add(node.id)
            if nodes_at_depth:
                result[depth] = nodes_at_depth
        return result

    def get_nodes_by_file(self, file_path: str, include_synthetic: bool = False) -> list[Node]:
        if include_synthetic:
            rows = self.conn.execute(
                "SELECT * FROM nodes WHERE file_path = ? ORDER BY line_start", (file_path,)
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT * FROM nodes WHERE file_path = ? AND kind NOT IN (?, ?, ?) ORDER BY line_start",
                (file_path, *_SYNTHETIC_KINDS)
            ).fetchall()
        return [self._row_to_node(r) for r in rows]

    def delete_file_nodes(self, file_path: str) -> None:
        self.conn.execute("DELETE FROM edges WHERE source_id IN (SELECT id FROM nodes WHERE file_path = ?)", (file_path,))
        self.conn.execute("DELETE FROM edges WHERE target_id IN (SELECT id FROM nodes WHERE file_path = ?)", (file_path,))
        self.conn.execute("DELETE FROM nodes WHERE file_path = ?", (file_path,))
        self.conn.execute("DELETE FROM files WHERE path = ?", (file_path,))
        self.conn.commit()

    def resolve_cross_file_edges(self) -> int:
        """Resolve orphan call edges by matching target names to known nodes.

        For call edges where target_id doesn't match any node, tries to find
        a node with the matching bare name. Updates edge target_id if a unique
        match is found. For truly unresolvable targets, creates an unresolved
        node so the edge is not orphaned. Returns the number of edges resolved.
        """
        from codepulse.ids import unresolved_node_id

        # Find all call edges with orphan targets
        orphan_rows = self.conn.execute(
            """SELECT e.rowid, e.source_id, e.target_id, e.kind
               FROM edges e
               WHERE e.kind = 'calls'
                 AND e.target_id NOT IN (SELECT id FROM nodes)"""
        ).fetchall()

        if not orphan_rows:
            return 0

        # Build name → node_id map from all nodes
        name_to_ids: dict[str, list[str]] = {}
        for row in self.conn.execute("SELECT id, name FROM nodes").fetchall():
            bare = row["name"].split(".")[-1]
            name_to_ids.setdefault(bare, []).append(row["id"])

        resolved = 0
        for rowid, source_id, target_id, kind in orphan_rows:
            # Extract bare name from target_id (last component after ':')
            bare_name = target_id.split(":")[-1]
            if "." in bare_name:
                bare_name = bare_name.split(".")[-1]

            candidates = name_to_ids.get(bare_name, [])
            if len(candidates) == 1:
                # Unique match — update the edge
                self.conn.execute(
                    "UPDATE edges SET target_id = ? WHERE rowid = ?",
                    (candidates[0], rowid),
                )
                resolved += 1
            elif len(candidates) > 1:
                # Multiple matches — prefer same file as source
                source_file = source_id.rsplit(":", 1)[0] if ":" in source_id else ""
                same_file = [c for c in candidates if c.startswith(source_file)]
                if len(same_file) >= 1:
                    self.conn.execute(
                        "UPDATE edges SET target_id = ? WHERE rowid = ?",
                        (same_file[0], rowid),
                    )
                    resolved += 1
                else:
                    # No same-file match — prefer real symbols over external nodes
                    real = [c for c in candidates if not c.startswith("external:")]
                    if real:
                        self.conn.execute(
                            "UPDATE edges SET target_id = ? WHERE rowid = ?",
                            (real[0], rowid),
                        )
                        resolved += 1
            else:
                # No match — create unresolved node so edge is not orphaned
                unresolved_id = unresolved_node_id("calls", bare_name)
                source_file = source_id.rsplit(":", 1)[0] if ":" in source_id else ""
                self.conn.execute(
                    "INSERT OR IGNORE INTO nodes (id, file_path, name, kind, line_start, line_end) VALUES (?, ?, ?, ?, ?, ?)",
                    (unresolved_id, source_file, bare_name, "unresolved_symbol", 1, 1),
                )
                self.conn.execute(
                    "UPDATE edges SET target_id = ? WHERE rowid = ?",
                    (unresolved_id, rowid),
                )
                resolved += 1

        self.conn.commit()
        return resolved

    def get_node_rankings(self, limit: int = 50) -> list[tuple[Node, int]]:
        rows = self.conn.execute(
            """SELECT n.*, COALESCE(ec.edge_count, 0) as edge_count
               FROM nodes n
               LEFT JOIN (
                 SELECT target_id as node_id, COUNT(*) as edge_count
                 FROM edges
                 GROUP BY target_id
               ) ec ON n.id = ec.node_id
               WHERE n.kind NOT IN (?, ?, ?)
               ORDER BY edge_count DESC, n.name
               LIMIT ?""", (*_SYNTHETIC_KINDS, limit)
        ).fetchall()
        return [(self._row_to_node(r), r["edge_count"]) for r in rows]

    def upsert_embedding(self, node_id: str, vector: bytes, model: str = "", dimensions: int = 384) -> None:
        self.conn.execute(
            "INSERT INTO embeddings (node_id, vector, model, dimensions) VALUES (?, ?, ?, ?) "
            "ON CONFLICT(node_id) DO UPDATE SET vector=excluded.vector, model=excluded.model, "
            "dimensions=excluded.dimensions, indexed_at=datetime('now')",
            (node_id, vector, model, dimensions),
        )
        self.conn.commit()

    def get_embedding(self, node_id: str) -> bytes | None:
        row = self.conn.execute(
            "SELECT vector FROM embeddings WHERE node_id = ?", (node_id,)
        ).fetchone()
        return row["vector"] if row else None

    def search_similar(
        self, query_vector: list[float], limit: int = 10
    ) -> list[tuple[Node, float]]:
        all_rows = self.conn.execute(
            "SELECT n.*, e.vector FROM nodes n JOIN embeddings e ON n.id = e.node_id"
        ).fetchall()
        scored: list[tuple[Node, float]] = []
        for row in all_rows:
            vec = _deserialize_vector(row["vector"])
            sim = _cosine_similarity(query_vector, vec)
            node = self._row_to_node(row)
            scored.append((node, sim))
        scored.sort(key=lambda x: -x[1])
        return scored[:limit]

    def get_file_summary(self, limit: int = 20) -> list[dict[str, object]]:
        """Return top files ranked by symbol count + edge references."""
        rows = self.conn.execute(
            """SELECT n.file_path,
               SUM(CASE WHEN n.kind NOT IN (?, ?, ?) THEN 1 ELSE 0 END) as symbol_count,
               (SELECT COUNT(*) FROM edges WHERE file_path = n.file_path) as edge_refs,
               GROUP_CONCAT(DISTINCT n.kind) as kinds
             FROM nodes n
             GROUP BY n.file_path
             ORDER BY (symbol_count + edge_refs) DESC
             LIMIT ?""", (*_SYNTHETIC_KINDS, limit)
        ).fetchall()
        return [{"file": r["file_path"], "symbols": r["symbol_count"], "edges": r["edge_refs"],
                 "kinds": r["kinds"] or ""} for r in rows]

    def get_top_symbols_with_context(self, limit: int = 20) -> list[dict[str, object]]:
        """Return top symbols by reference count with file + kind + signature."""
        rows = self.conn.execute(
            """SELECT n.name, n.kind, n.file_path, n.line_start, n.signature,
               (SELECT COUNT(*) FROM edges WHERE source_id = n.id OR target_id = n.id) as refs
              FROM nodes n
              WHERE n.kind NOT IN (?, ?, ?)
              ORDER BY refs DESC, n.name
              LIMIT ?""", (*_SYNTHETIC_KINDS, limit)
        ).fetchall()
        return [{"name": r["name"], "kind": r["kind"], "file": r["file_path"],
                 "line": r["line_start"], "sig": (r["signature"] or "")[:120], "refs": r["refs"]}
                for r in rows]

    def get_symbols_with_callers(self, query: str, limit: int = 10) -> list[dict[str, object]]:
        """Find symbols matching query, return each with its immediate callers."""
        matches = self.search_nodes(query, limit=limit)
        results: list[dict[str, object]] = []
        for node in matches:
            entry: dict[str, object] = {
                "name": node.name, "kind": node.kind,
                "file": node.file_path, "line": node.line_start,
                "sig": node.signature[:120] if node.signature else ""
            }
            callers = self.get_callers(node.id, depth=1)
            callees = self.get_callees(node.id, depth=1)
            entry["called_by"] = [f"{n.name} ({ek})" for n, ek in callers[:5]]
            entry["calls"] = [f"{n.name} ({ek})" for n, ek in callees[:5]]
            results.append(entry)
        return results

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None


def _deserialize_vector(data: bytes) -> list[float]:
    import struct
    n = len(data) // 4
    return list(struct.unpack(f"{n}f", data))


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)
