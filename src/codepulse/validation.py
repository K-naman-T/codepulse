from dataclasses import dataclass, field
from pathlib import Path

from codepulse.db import GraphDB, _SYNTHETIC_KINDS
from codepulse.schema import CURRENT_SCHEMA_VERSION


@dataclass
class ValidationIssue:
    code: str
    severity: str
    message: str


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
    orphan_edges: int = 0
    issues: list[ValidationIssue] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not any(issue.severity == "error" for issue in self.issues)

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
            lines.append(f"  \u26a0  Orphan parent refs: {self.orphan_parent_refs}")
        else:
            lines.append("  No orphan refs")
        if self.orphan_edges:
            lines.append(f"  \u26a0  Orphan edges: {self.orphan_edges}")
        else:
            lines.append("  No orphan edges")
        if self.issues:
            lines.append("")
            lines.append("Issues:")
            for issue in self.issues:
                mark = "\u2717" if issue.severity == "error" else "!"
                lines.append(f"  {mark} [{issue.code}] {issue.message}")
        return "\n".join(lines)


def validate_graph(db: GraphDB) -> ValidationReport:
    conn = db.conn
    issues: list[ValidationIssue] = []

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

    orphans = conn.execute(
        "SELECT COUNT(*) FROM nodes WHERE parent_id IS NOT NULL AND parent_id NOT IN (SELECT id FROM nodes)"
    ).fetchone()[0]
    nodes_with_parent = conn.execute(
        "SELECT COUNT(*) FROM nodes WHERE parent_id IS NOT NULL"
    ).fetchone()[0]
    orphan_edge_count = conn.execute("""
        SELECT COUNT(*) FROM edges e
        WHERE NOT EXISTS (SELECT 1 FROM nodes WHERE id = e.source_id)
           OR NOT EXISTS (SELECT 1 FROM nodes WHERE id = e.target_id)
    """).fetchone()[0]

    orphan_source_count = conn.execute(
        "SELECT COUNT(*) FROM edges e WHERE NOT EXISTS (SELECT 1 FROM nodes WHERE id = e.source_id)"
    ).fetchone()[0]
    if orphan_source_count:
        issues.append(ValidationIssue(
            code="ORPHAN_EDGE_SOURCE",
            severity="error",
            message=f"{orphan_source_count} edges have source_id missing from nodes",
        ))

    orphan_target_count = conn.execute(
        "SELECT COUNT(*) FROM edges e WHERE NOT EXISTS (SELECT 1 FROM nodes WHERE id = e.target_id)"
    ).fetchone()[0]
    if orphan_target_count:
        issues.append(ValidationIssue(
            code="ORPHAN_EDGE_TARGET",
            severity="error",
            message=f"{orphan_target_count} edges have target_id missing from nodes",
        ))

    if orphans:
        issues.append(ValidationIssue(
            code="ORPHAN_PARENT",
            severity="error",
            message=f"{orphans} nodes have parent_id missing from nodes",
        ))

    file_rows = conn.execute("SELECT path FROM files").fetchall()
    stale_count = 0
    for (path,) in file_rows:
        if not Path(path).exists():
            stale_count += 1
    if stale_count:
        issues.append(ValidationIssue(
            code="STALE_FILE",
            severity="error",
            message=f"{stale_count} file(s) in database no longer exist on disk",
        ))

    invalid_range_rows = conn.execute(
        "SELECT id FROM nodes WHERE line_start < 0 OR line_end < 0 OR (line_start > 0 AND line_end > 0 AND line_end < line_start)"
    ).fetchall()
    if invalid_range_rows:
        issues.append(ValidationIssue(
            code="INVALID_LINE_RANGE",
            severity="error",
            message=f"{len(invalid_range_rows)} nodes have invalid line ranges",
        ))

    placeholders = ",".join("?" for _ in _SYNTHETIC_KINDS)
    dup_rows = conn.execute(
        f"""SELECT file_path, name, kind, parent_id, COUNT(*) as cnt
            FROM nodes
            WHERE kind NOT IN ({placeholders})
            GROUP BY file_path, name, kind, parent_id
            HAVING cnt > 1""",
        list(_SYNTHETIC_KINDS),
    ).fetchall()
    if dup_rows:
        total_dups = sum(r["cnt"] - 1 for r in dup_rows)
        issues.append(ValidationIssue(
            code="DUPLICATE_LOGICAL_SYMBOL",
            severity="error",
            message=f"{total_dups} duplicate logical symbol(s) found (same file_path/name/kind/parent_id)",
        ))

    version_row = conn.execute("SELECT MAX(version) as mv FROM schema_meta").fetchone()
    db_version = version_row["mv"] if version_row and version_row["mv"] is not None else 0
    if db_version != CURRENT_SCHEMA_VERSION:
        issues.append(ValidationIssue(
            code="SCHEMA_VERSION_MISMATCH",
            severity="error",
            message=f"Schema version {db_version} does not match expected {CURRENT_SCHEMA_VERSION}",
        ))

    error_rows = conn.execute(
        "SELECT path FROM files WHERE error IS NOT NULL AND error != ''"
    ).fetchall()
    if error_rows:
        issues.append(ValidationIssue(
            code="PARSER_ERROR",
            severity="error",
            message=f"{len(error_rows)} file(s) have parser errors",
        ))

    return ValidationReport(
        total_files=total_files,
        total_nodes=total_nodes,
        total_edges=total_edges,
        by_kind=kind_counts,
        by_edge_kind=edge_kind_counts,
        by_language=lang_counts,
        nodes_with_parent=nodes_with_parent,
        orphan_parent_refs=orphans,
        orphan_edges=orphan_edge_count,
        issues=issues,
    )
