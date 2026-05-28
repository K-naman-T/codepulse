"""Compatibility wrapper — delegates to mcp_server.

This module is deprecated and will be removed in a future version.
Use codepulse.mcp_server.create_server() or `codepulse mcp` directly.
"""

import asyncio
import warnings

from codepulse.graph import CodePulse
from codepulse.mcp_server import create_server as _create_server


def _run(coro):
    """Run an async coroutine synchronously."""
    return asyncio.run(coro)


class CodePulseMCPServer:
    """Deprecated compatibility wrapper. Use codepulse.mcp_server directly."""

    def __init__(self, cp: CodePulse):
        warnings.warn(
            "CodePulseMCPServer is deprecated. Use codepulse.mcp_server.create_server() instead.",
            DeprecationWarning, stacklevel=2,
        )
        self.cp = cp
        self._fastmcp = _create_server(cp.config)

    def search_symbols(self, query: str, kind: str | None = None, limit: int = 20) -> str:
        result = _run(self._fastmcp.call_tool("search", {"query": query, "kind": kind, "limit": limit}))
        contents, _ = result
        for c in contents:
            if hasattr(c, "text") and c.text:
                return c.text
        return str(result)

    def find_code(self, task: str, max_nodes: int = 30) -> str:
        result = _run(self._fastmcp.call_tool("context", {"task": task, "max_nodes": max_nodes}))
        contents, _ = result
        for c in contents:
            if hasattr(c, "text") and c.text:
                return c.text
        return str(result)

    def get_callers(self, node_id: str, depth: int = 1) -> str:
        result = _run(self._fastmcp.call_tool("callers", {"node_id": node_id, "depth": depth}))
        contents, _ = result
        for c in contents:
            if hasattr(c, "text") and c.text:
                return c.text
        return str(result)

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
        result = _run(self._fastmcp.call_tool("impact", {"node_id": node_id, "depth": depth}))
        contents, _ = result
        for c in contents:
            if hasattr(c, "text") and c.text:
                return c.text
        return str(result)


def create_mcp_server(cp: CodePulse) -> CodePulseMCPServer:
    """Deprecated. Use codepulse.mcp_server.create_server() instead."""
    return CodePulseMCPServer(cp)
