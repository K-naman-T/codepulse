"""MCP server — 9 tools optimized for benchmark performance.

Key design principles (copied from colbymchenry/codegraph):
1. `context` is the PRIMARY tool — composes search + callers + callees in one call
2. `repo_map` gives the codebase overview so the model doesn't thrash
3. All output is concise markdown — minimal tokens for the model to parse
4. Tools replace file-reading; AGENTS.md steers the agent to use them

Usage: codepulse mcp
"""

import json
from pathlib import Path

from codepulse.config import CodePulseConfig
from codepulse.graph import CodePulse

try:
    from mcp.server.fastmcp import FastMCP
    HAS_MCP = True
except ImportError:
    HAS_MCP = False


def create_server() -> "FastMCP":
    config = CodePulseConfig.load()
    cp = CodePulse(config)
    db = cp.db

    if not HAS_MCP:
        raise ImportError("mcp package not installed. Run: pip install mcp")

    mcp = FastMCP("CodePulse")

    @mcp.tool()
    def repo_map(limit: int = 25) -> str:
        """Overview of the codebase — top files and symbols by reference count.
        Use this FIRST to understand the codebase shape before asking specific questions."""
        files = db.get_file_summary(limit=limit)
        symbols = db.get_top_symbols_with_context(limit=limit)

        lines = ["## Codebase Overview", ""]

        lines.append("### Top files")
        lines.append("| File | Symbols | References | Kinds |")
        lines.append("|---|---|---|---|")
        for f in files:
            name = Path(str(f["file"])).name
            lines.append(f"| {name} | {f['symbols']} | {f['edges']} | {f['kinds']} |")

        lines.append("")
        lines.append("### Top symbols")
        lines.append("| Symbol | Kind | File | Refs |")
        lines.append("|---|---|---|---|")
        for s in symbols:
            fname = Path(str(s["file"])).name
            lines.append(f"| {s['name']} | {s['kind']} | {fname}:{s['line']} | {s['refs']} |")

        return "\n".join(lines)

    @mcp.tool()
    def context(task: str, max_nodes: int = 15) -> str:
        """Primary tool — maps an area. Returns symbols matching the task grouped by file,
        with signatures, locations, and file-level overview."""
        nodes = cp.search(task, limit=max_nodes)
        if not nodes:
            return f"No symbols matching '{task}'. Try a broader query."

        by_file: dict[str, list[str]] = {}
        for n in nodes:
            fname = Path(n.file_path).name
            by_file.setdefault(fname, [])
            line = f"`{n.name}` ({n.kind})"
            if n.signature:
                sig_short = n.signature[:80].replace("\n", " ").strip()
                line += f" — `{sig_short}`"
            by_file[fname].append(f"  {line}")

        lines = [f"## Context: {task}", ""]
        for fname, syms in sorted(by_file.items()):
            lines.append(f"### {fname}")
            lines.extend(syms)
            lines.append("")
        lines.append(f"_{len(nodes)} symbols in {len(by_file)} files_")
        return "\n".join(lines)

    @mcp.tool()
    def search(query: str, kind: str | None = None, limit: int = 20) -> str:
        """Find symbols by name (FTS5 full-text search)."""
        results = cp.search(query, kind=kind, limit=limit)
        if not results:
            return "No symbols found."
        lines = ["| Symbol | Kind | File | Line |", "|---|---|---|---|"]
        for n in results:
            fname = Path(n.file_path).name
            lines.append(f"| {n.name} | {n.kind} | {fname} | {n.line_start} |")
        return "\n".join(lines)

    @mcp.tool()
    def callers(node_id: str, depth: int = 1) -> str:
        """Find what calls a symbol."""
        results = cp.get_callers(node_id, depth=depth)
        if not results:
            return "No callers found."
        lines = ["| Caller | Kind | Via | File |", "|---|---|---|---|"]
        for node, ek in results:
            fname = Path(node.file_path).name
            lines.append(f"| {node.name} | {node.kind} | {ek} | {fname}:{node.line_start} |")
        return "\n".join(lines)

    @mcp.tool()
    def callees(node_id: str, depth: int = 1) -> str:
        """Find what a symbol calls."""
        results = cp.get_callees(node_id, depth=depth)
        if not results:
            return "No callees found."
        lines = ["| Callee | Kind | Via | File |", "|---|---|---|---|"]
        for node, ek in results:
            fname = Path(node.file_path).name
            lines.append(f"| {node.name} | {node.kind} | {ek} | {fname}:{node.line_start} |")
        return "\n".join(lines)

    @mcp.tool()
    def impact(node_id: str, depth: int = 3) -> str:
        """What code would be affected by changing this symbol? (transitive impact)."""
        result = cp.get_impact_radius(node_id, depth=depth)
        if not result:
            return "No impact found."
        lines: list[str] = []
        for level, nodes in sorted(result.items()):
            lines.append(f"**Depth {level}:** {', '.join(f'{n.name}({n.kind})' for n in nodes)}")
        return "\n".join(lines)

    @mcp.tool()
    def trace(source: str, target: str) -> str:
        """Trace the call path between two symbols ('how does X reach Y')."""
        conn = db.conn
        rows = conn.execute(
            """WITH RECURSIVE path AS (
                SELECT source_id, target_id, kind, file_path, line_number, 0 AS depth,
                       source_id || ' → ' || target_id AS path_str
                FROM edges WHERE source_id = ?
                UNION ALL
                SELECT e.source_id, e.target_id, e.kind, e.file_path, e.line_number, p.depth + 1,
                       p.path_str || ' → ' || e.target_id
                FROM edges e JOIN path p ON e.source_id = p.target_id
                WHERE p.depth < 15 AND e.target_id != p.source_id
            )
            SELECT * FROM path WHERE target_id = ? ORDER BY depth LIMIT 1""",
            (source, target)
        ).fetchall()
        if not rows:
            return "No path found between these symbols."
        r = rows[0]
        return f"**Path ({r['depth']} hops):** {r['path_str']}"

    @mcp.tool()
    def node(node_id: str) -> str:
        """Get a single symbol's source, signature, and relationships."""
        detail = cp.get_node(node_id, include_source=True)
        if detail is None:
            return "Node not found."
        n = detail.node
        lines = [f"## {n.name} ({n.kind})"]
        lines.append(f"**File:** `{n.file_path}:{n.line_start}`")
        if n.signature:
            lines.append(f"```\n{n.signature}\n```")
        return "\n".join(lines)

    @mcp.tool()
    def status() -> str:
        """Check index health and stats."""
        report = cp.validate()
        lines = [f"**{report.total_files}** files · **{report.total_nodes}** symbols · **{report.total_edges}** edges"]
        lines.append("")
        k = [f"{kind}:{count}" for kind, count in sorted(report.by_kind.items(), key=lambda x: -x[1])]
        lines.append("By kind: " + ", ".join(k))
        return "\n".join(lines)

    return mcp


def main() -> None:
    if not HAS_MCP:
        print("Error: mcp package not installed. Run: pip install 'mcp>=1.0'", file=__import__('sys').stderr)
        __import__('sys').exit(1)
    server = create_server()
    server.run(transport="stdio")


if __name__ == "__main__":
    main()
