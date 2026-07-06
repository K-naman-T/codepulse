"""MCP server for CodePulse over stdio.

Small tool surface optimized for code navigation:
1. `repo_map` first — codebase overview so the model doesn't thrash
2. `context` / `search` next — primary tools for exploration
3. `node` / `callers` / `callees` / `impact` / `trace` — targeted follow-ups

All output is concise markdown for human and agent readability.

Usage: codepulse mcp
"""

from pathlib import Path

from codepulse.config import CodePulseConfig
from codepulse.graph import CodePulse

try:
    from mcp.server.fastmcp import FastMCP
    HAS_MCP = True
except ImportError:
    HAS_MCP = False


def create_server(config: CodePulseConfig | None = None) -> "FastMCP":
    if config is None:
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
        with signatures, locations, callers, callees, and node IDs."""
        nodes = cp.search(task, limit=max_nodes)
        if not nodes:
            return f"No symbols matching '{task}'. Try a broader query."

        by_file: dict[str, list[str]] = {}
        for n in nodes:
            fname = Path(n.file_path).name
            by_file.setdefault(fname, [])
            line = f"`{n.name}` ({n.kind}) `{n.id}`"
            if n.signature:
                sig_short = n.signature[:80].replace("\n", " ").strip()
                line += f" — `{sig_short}`"
            by_file[fname].append(f"  {line}")
            callers = cp.get_callers(n.id, depth=1)
            if callers:
                by_file[fname].append(
                    f"    *Callers:* {', '.join(f'{c[0].name} ({c[1]})' for c in callers[:5])}"
                )
            callees = cp.get_callees(n.id, depth=1)
            if callees:
                by_file[fname].append(
                    f"    *Callees:* {', '.join(f'{c[0].name} ({c[1]})' for c in callees[:5])}"
                )

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
        lines = ["| ID | Symbol | Kind | File | Line |", "|---|---|---|---|---|"]
        for n in results:
            fname = Path(n.file_path).name
            lines.append(f"| {n.id} | {n.name} | {n.kind} | {fname} | {n.line_start} |")
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
        result = cp.trace_path(source, target, max_depth=15)
        if result is None:
            return "No path found between these symbols."
        path_str = " → ".join(n.id for n in result)
        return f"**Path ({len(result) - 1} hops):** {path_str}"

    @mcp.tool()
    def node(node_id: str) -> str:
        """Get a single symbol's source, signature, and relationships.
        Use symbol IDs from search/context results, NOT file paths."""
        detail = cp.get_node(node_id, include_source=True)
        if detail is None:
            return f"Node '{node_id}' not found. Use `search` or `context` to find symbol IDs, or `file` to view symbols in a file path."
        n = detail.node
        lines = [f"## {n.name} ({n.kind})"]
        lines.append(f"**ID:** `{n.id}`")
        lines.append(f"**File:** `{n.file_path}:{n.line_start}`")
        if n.signature:
            lines.append(f"```\n{n.signature}\n```")
        if detail.source:
            src_lines = detail.source.splitlines()
            start = max(0, n.line_start - 3)
            end = min(len(src_lines), n.line_end + 1)
            excerpt = src_lines[start:end]
            if excerpt:
                lines.append("")
                lines.append("### Source excerpt")
                lines.append("```")
                lines.extend(excerpt)
                lines.append("```")
        callers = cp.get_callers(node_id, depth=1)
        if callers:
            lines.append("")
            lines.append("### Callers")
            for c, ek in callers[:5]:
                fname = Path(c.file_path).name
                lines.append(f"- `{c.name}` ({c.kind}) — {fname}:{c.line_start} via {ek}")
        callees = cp.get_callees(node_id, depth=1)
        if callees:
            lines.append("")
            lines.append("### Callees")
            for c, ek in callees[:5]:
                fname = Path(c.file_path).name
                lines.append(f"- `{c.name}` ({c.kind}) — {fname}:{c.line_start} via {ek}")
        return "\n".join(lines)

    @mcp.tool()
    def file(file_path: str) -> str:
        """View all symbols in a specific file. Returns symbol names, kinds, and line numbers."""
        nodes = db.get_nodes_by_file(file_path)
        if not nodes:
            return f"No symbols found in '{file_path}'. Check the path matches an indexed file."
        lines = [f"## Symbols in `{Path(file_path).name}`", ""]
        lines.append("| Symbol | Kind | Line |")
        lines.append("|---|---|---|")
        for n in nodes:
            lines.append(f"| `{n.name}` | {n.kind} | {n.line_start} |")
        lines.append(f"\n_{len(nodes)} symbols_")
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


def main(config: CodePulseConfig | None = None) -> None:
    if not HAS_MCP:
        raise ImportError("mcp package not installed. Run: pip install 'mcp>=1.0'")
    server = create_server(config=config)
    server.run(transport="stdio")


if __name__ == "__main__":
    main()
