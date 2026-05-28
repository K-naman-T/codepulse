import os
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


# ---------------------------------------------------------------------------
# Golden manifest comparison - precision, recall, F1
# ---------------------------------------------------------------------------

_SYMBOL_KINDS = frozenset({
    "function", "method", "class", "interface",
    "struct", "trait", "enum", "type", "object",
})


def _file_key(path: str) -> str:
    """Reduce a file path to its basename for matching."""
    return os.path.basename(path)


def _node_name_for_edge(nid: str, node_map: dict) -> str:
    """Resolve a readable name from a node ID for edge comparison."""
    info = node_map.get(nid)
    if info is None:
        return nid.split(":")[-1]
    if info["kind"] == "file":
        return os.path.basename(info["file_path"])
    return info["name"]


@dataclass
class MetricSet:
    name: str = ""
    true_positives: int = 0
    false_positives: int = 0
    false_negatives: int = 0
    wrong_kind: list[str] = field(default_factory=list)
    wrong_parent: list[str] = field(default_factory=list)
    wrong_line_range: list[str] = field(default_factory=list)

    @property
    def precision(self) -> float:
        emitted = self.true_positives + self.false_positives
        expected = self.true_positives + self.false_negatives
        if emitted == 0 and expected == 0:
            return 1.0
        if emitted == 0:
            return 0.0
        return self.true_positives / emitted

    @property
    def recall(self) -> float:
        emitted = self.true_positives + self.false_positives
        expected = self.true_positives + self.false_negatives
        if emitted == 0 and expected == 0:
            return 1.0
        if expected == 0:
            return 0.0
        return self.true_positives / expected

    @property
    def f1(self) -> float:
        p = self.precision
        r = self.recall
        if p + r == 0:
            return 0.0
        return 2.0 * p * r / (p + r)


@dataclass
class GoldenComparison:
    symbols: MetricSet = field(default_factory=lambda: MetricSet(name="symbols"))
    calls: MetricSet = field(default_factory=lambda: MetricSet(name="calls"))
    imports: MetricSet = field(default_factory=lambda: MetricSet(name="imports"))
    parent_links: MetricSet = field(default_factory=lambda: MetricSet(name="parent_links"))


def compare_to_golden(db: GraphDB, manifest: dict) -> GoldenComparison:
    """Compare the indexed graph against a golden manifest.

    Parameters
    ----------
    db : GraphDB
        Populated database instance.
    manifest : dict
        Python dict (from YAML) with ``symbols``, ``edges``, and
        ``allowed_external`` keys.

    Returns
    -------
    GoldenComparison
        Per-kind metrics including precision, recall, F1, and
        diagnostic lists (wrong_kind, wrong_parent, wrong_line_range).
    """
    node_rows = db.conn.execute("SELECT * FROM nodes").fetchall()
    edge_rows = db.conn.execute("SELECT * FROM edges").fetchall()

    # Build node metadata map keyed by node ID
    node_info: dict[str, dict] = {}
    for r in node_rows:
        node_info[r["id"]] = {
            "name": r["name"],
            "kind": r["kind"],
            "file_path": r["file_path"],
            "line_start": r["line_start"],
            "line_end": r["line_end"],
            "parent_id": r["parent_id"],
        }

    # Build node_id to parent_name lookup
    parent_name_of: dict[str, str | None] = {}
    for nid, info in node_info.items():
        pid = info["parent_id"]
        if pid and pid in node_info:
            parent_name_of[nid] = node_info[pid]["name"]
        else:
            parent_name_of[nid] = None

    allowed: set[str] = set(manifest.get("allowed_external", []))

    # ------------------------------------------------------------------
    # Parse manifest data
    # ------------------------------------------------------------------
    m_symbols: list[dict] = manifest.get("symbols", [])
    m_edges: list[dict] = manifest.get("edges", [])

    # Manifest symbol index by (file, name, kind)
    m_sym_key: dict[tuple[str, str, str], dict] = {}
    for s in m_symbols:
        m_sym_key[(_file_key(s["file"]), s["name"], s["kind"])] = s

    # Manifest symbol index by (file, name) for wrong-kind / parent / line checks
    m_sym_by_name: dict[tuple[str, str], list[dict]] = {}
    for s in m_symbols:
        m_sym_by_name.setdefault((_file_key(s["file"]), s["name"]), []).append(s)

    # Manifest edge index by (file, source_name, target_name, kind)
    m_edge_key: dict[tuple[str, str, str, str], dict] = {}
    for e in m_edges:
        m_edge_key[(_file_key(e["file"]), e["source_name"], e["target_name"], e["kind"])] = e

    # ------------------------------------------------------------------
    # DB non-synthetic symbol index
    # ------------------------------------------------------------------
    db_sym_key: dict[tuple[str, str, str], str] = {}
    db_sym_by_name: dict[tuple[str, str], list[tuple[str, dict]]] = {}
    for nid, info in node_info.items():
        if info["kind"] in ("file", "external_module", "unresolved_symbol"):
            continue
        key = (_file_key(info["file_path"]), info["name"], info["kind"])
        db_sym_key[key] = nid
        db_sym_by_name.setdefault((_file_key(info["file_path"]), info["name"]), []).append((nid, info))

    # ------------------------------------------------------------------
    # SYMBOL METRICS
    # ------------------------------------------------------------------
    sym = MetricSet(name="symbols")

    # True positives: manifest and DB agree on (file, name, kind)
    for key in m_sym_key:
        if key in db_sym_key:
            sym.true_positives += 1

    # False positives: DB has extra symbols not in manifest
    for key in db_sym_key:
        if key not in m_sym_key:
            _, name, _ = key
            if name not in allowed:
                sym.false_positives += 1

    # False negatives: manifest has symbols missing from DB
    for key in m_sym_key:
        if key not in db_sym_key:
            sym.false_negatives += 1

    # Wrong kind: match by (file, name) but kinds differ
    for nkey, db_entries in db_sym_by_name.items():
        if nkey in m_sym_by_name:
            m_kinds = {s["kind"] for s in m_sym_by_name[nkey]}
            db_kinds = {info["kind"] for _, info in db_entries}
            if m_kinds != db_kinds:
                sym.wrong_kind.append(nkey[1])

    # Wrong parent & wrong line range: match by (file, name)
    for s in m_symbols:
        nkey = (_file_key(s["file"]), s["name"])
        if nkey in db_sym_by_name:
            child_id, info = db_sym_by_name[nkey][0]
            exp_parent = s.get("parent_name")
            actual_parent = parent_name_of.get(child_id)
            if exp_parent != actual_parent:
                sym.wrong_parent.append(s["name"])
            if info["line_start"] != s.get("line_start") or info["line_end"] != s.get("line_end"):
                sym.wrong_line_range.append(s["name"])

    # ------------------------------------------------------------------
    # EDGE METRICS
    # ------------------------------------------------------------------
    # Index DB edges by (file, source_name, target_name, kind), deduplicating
    db_edge_set: set[tuple[str, str, str, str]] = set()
    for r in edge_rows:
        src_name = _node_name_for_edge(r["source_id"], node_info)
        tgt_name = _node_name_for_edge(r["target_id"], node_info)
        key = (_file_key(r["file_path"]), src_name, tgt_name, r["kind"])
        db_edge_set.add(key)

    calls = MetricSet(name="calls")
    imports_m = MetricSet(name="imports")

    for kind, ms in [("calls", calls), ("imports", imports_m)]:
        m_set = {k for k, e in m_edge_key.items() if k[3] == kind}
        db_set = {k for k in db_edge_set if k[3] == kind}

        tp = len(m_set & db_set)
        fp = len(db_set - m_set)
        fn = len(m_set - db_set)

        ms.true_positives = tp
        ms.false_positives = fp
        ms.false_negatives = fn

    # ------------------------------------------------------------------
    # PARENT LINK METRICS
    # ------------------------------------------------------------------
    pl = MetricSet(name="parent_links")
    correct_parent = 0
    db_parent_count = 0
    manifest_parent_count = 0

    for s in m_symbols:
        nkey = (_file_key(s["file"]), s["name"])
        if nkey not in db_sym_by_name:
            continue
        child_id, _ = db_sym_by_name[nkey][0]
        exp_parent = s.get("parent_name")
        actual_parent = parent_name_of.get(child_id)

        has_db_parent = actual_parent is not None
        has_m_parent = exp_parent is not None

        if has_db_parent:
            db_parent_count += 1
        if has_m_parent:
            manifest_parent_count += 1

        if has_db_parent and has_m_parent:
            if actual_parent == exp_parent:
                correct_parent += 1

    pl.true_positives = correct_parent
    pl.false_positives = db_parent_count - correct_parent
    pl.false_negatives = manifest_parent_count - correct_parent

    return GoldenComparison(symbols=sym, calls=calls, imports=imports_m, parent_links=pl)
