import sqlite3

CURRENT_SCHEMA_VERSION = 1
SCHEMA_TABLE = "schema_meta"


def _get_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return {r["name"] for r in rows}


def _add_edge_columns(conn: sqlite3.Connection) -> None:
    existing = _get_columns(conn, "edges")
    new_columns = [
        ("metadata", "TEXT DEFAULT '{}'"),
        ("line_start", "INTEGER DEFAULT 0"),
        ("line_end", "INTEGER DEFAULT 0"),
        ("column_start", "INTEGER DEFAULT 0"),
        ("column_end", "INTEGER DEFAULT 0"),
        ("confidence", "REAL DEFAULT 1.0"),
        ("provenance", "TEXT DEFAULT 'tree-sitter'"),
        ("resolution_status", "TEXT DEFAULT 'resolved'"),
    ]
    for col_name, col_type in new_columns:
        if col_name not in existing:
            conn.execute(f"ALTER TABLE edges ADD COLUMN {col_name} {col_type}")


def _relax_edge_unique_constraint(conn: sqlite3.Connection) -> None:
    schema_row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='edges'"
    ).fetchone()
    if not schema_row:
        return
    create_sql = schema_row[0]
    normalized = create_sql.replace(" ", "").lower()
    if "unique(source_id,target_id,kind)" not in normalized:
        return

    conn.execute("SAVEPOINT edge_migration")
    try:
        conn.execute("""CREATE TABLE IF NOT EXISTS edges_v2 (
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
        )""")
        conn.execute("""INSERT INTO edges_v2 (id, source_id, target_id, kind, file_path, line_number, metadata, line_start, line_end, column_start, column_end, confidence, provenance, resolution_status)
            SELECT id, source_id, target_id, kind, file_path, line_number, metadata, line_start, line_end, column_start, column_end, confidence, provenance, resolution_status FROM edges""")
        conn.execute("DROP TABLE edges")
        conn.execute("ALTER TABLE edges_v2 RENAME TO edges")
        conn.execute("RELEASE SAVEPOINT edge_migration")
    except Exception:
        conn.execute("ROLLBACK TO SAVEPOINT edge_migration")
        raise


def _recreate_indexes(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE INDEX IF NOT EXISTS idx_edges_source ON edges(source_id);
        CREATE INDEX IF NOT EXISTS idx_edges_target ON edges(target_id);
    """)


def ensure_schema(conn: sqlite3.Connection) -> None:
    meta_exists = bool(
        conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (SCHEMA_TABLE,),
        ).fetchone()
    )

    if not meta_exists:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_meta (version INTEGER PRIMARY KEY, applied_at TEXT DEFAULT (datetime('now')))"
        )
        conn.execute("INSERT INTO schema_meta (version) VALUES (?)", (CURRENT_SCHEMA_VERSION,))
        conn.commit()
        return

    version_row = conn.execute("SELECT MAX(version) FROM schema_meta").fetchone()
    current_version = version_row[0] if version_row and version_row[0] else 0

    if current_version >= CURRENT_SCHEMA_VERSION:
        return

    if current_version < 1:
        _add_edge_columns(conn)
        _relax_edge_unique_constraint(conn)
        _recreate_indexes(conn)
        conn.execute("INSERT INTO schema_meta (version) VALUES (?)", (CURRENT_SCHEMA_VERSION,))
        conn.commit()
