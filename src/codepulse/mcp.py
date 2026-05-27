from codepulse.graph import CodePulse


class CodePulseMCPServer:
    def __init__(self, cp: CodePulse):
        self.cp = cp

    def search_symbols(self, query: str, kind: str | None = None, limit: int = 20) -> str:
        results = self.cp.search(query, kind=kind, limit=limit)
        if not results:
            return "No symbols found."
        lines: list[str] = []
        for node in results:
            sig = f"  {node.signature}" if node.signature else ""
            lines.append(f"- {node.name} ({node.kind})")
            lines.append(f"  File: {node.file_path}:{node.line_start}")
            if sig:
                lines.append(sig)
            lines.append("")
        return "\n".join(lines)

    def find_code(self, task: str, max_nodes: int = 30) -> str:
        return self.cp.build_context(task, max_nodes=max_nodes)

    def get_callers(self, node_id: str, depth: int = 1) -> str:
        results = self.cp.get_callers(node_id, depth=depth)
        if not results:
            return "No callers found."
        lines: list[str] = []
        for node, edge_kind in results:
            lines.append(f"- {node.name} ({node.kind}) via {edge_kind}")
            lines.append(f"  File: {node.file_path}:{node.line_start}")
            lines.append("")
        return "\n".join(lines)

    def search_similar(self, query: str, limit: int = 10) -> str:
        try:
            from codepulse.embeddings import get_embedder
            embed_fn = get_embedder()
            vec = embed_fn([query])[0]
            results = self.cp.db.search_similar(vec, limit=limit)
        except Exception as e:
            return f"Similarity search error: {e}"

        if not results:
            return "No similar symbols found. Run `embed` first."
        lines: list[str] = []
        for node, score in results:
            sig = f"  {node.signature}" if node.signature else ""
            lines.append(f"- {node.name} ({node.kind}) [{score:.3f}]")
            lines.append(f"  File: {node.file_path}:{node.line_start}")
            if sig:
                lines.append(sig)
            lines.append("")
        return "\n".join(lines)

    def get_impact_radius(self, node_id: str, depth: int = 3) -> str:
        impact = self.cp.get_impact_radius(node_id, depth=depth)
        if not impact:
            return "No impact found."
        lines: list[str] = []
        for level, nodes in sorted(impact.items()):
            lines.append(f"Depth {level}:")
            for node in nodes:
                lines.append(f"  - {node.name} ({node.kind})")
                lines.append(f"    File: {node.file_path}:{node.line_start}")
            lines.append("")
        return "\n".join(lines)


def create_mcp_server(cp: CodePulse) -> CodePulseMCPServer:
    return CodePulseMCPServer(cp)
