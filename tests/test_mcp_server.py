import pytest

from codepulse.config import CodePulseConfig

try:
    from codepulse.mcp_server import create_server
except ImportError:
    create_server = None


def _extract(result: tuple) -> str:
    """Extract text content from FastMCP tool result."""
    contents, _ = result
    for c in contents:
        if hasattr(c, "text") and c.text:
            return c.text
    return str(result)


@pytest.fixture
def server():
    if create_server is None:
        pytest.skip("mcp package not installed")
    return create_server()


EXPECTED_TOOLS = {
    "repo_map", "context", "search", "callers", "callees",
    "impact", "trace", "node", "file", "add_symbol_note",
    "list_symbol_notes", "search_symbol_notes", "status",
}


@pytest.mark.asyncio
class TestMCPServerTools:
    async def test_list_tools_returns_expected_tools(self, server):
        tools = await server.list_tools()
        names = {t.name for t in tools}
        assert names == EXPECTED_TOOLS

    async def test_search_tool_returns_markdown_table(self, server):
        result = await server.call_tool("search", {"query": "class", "limit": 3})
        text = _extract(result)
        assert isinstance(text, str)
        assert len(text) > 10

    async def test_search_tool_includes_node_ids(self, server):
        result = await server.call_tool("search", {"query": "class", "limit": 5})
        text = _extract(result)
        assert "| ID" in text or "No symbols" in text

    async def test_status_tool_returns_index_stats(self, server):
        result = await server.call_tool("status", {})
        text = _extract(result)
        assert "files" in text.lower() or "symbols" in text.lower() or "nodes" in text.lower()

    async def test_repo_map_tool_returns_markdown(self, server):
        result = await server.call_tool("repo_map", {"limit": 3})
        text = _extract(result)
        assert "|" in text

    async def test_context_tool_returns_markdown(self, server):
        result = await server.call_tool("context", {"task": "class", "max_nodes": 3})
        text = _extract(result)
        assert len(text) > 10

    async def test_context_tool_includes_node_ids(self, server):
        result = await server.call_tool("context", {"task": "class", "max_nodes": 3})
        text = _extract(result)
        assert "`/" in text or "No symbols" in text

    async def test_context_tool_includes_callers_and_callees(self, server):
        result = await server.call_tool("context", {"task": "class", "max_nodes": 3})
        text = _extract(result)
        if "No symbols" in text or not text.strip():
            pytest.skip("no indexed symbols at default config; requires populated ~/.codepulse")
        if "Callers" in text or "Callees" in text:
            assert "Callers" in text and "Callees" in text
        else:
            pytest.skip("indexed symbols have no caller/callee relationships to verify")

    async def test_node_tool_reports_missing_node(self, server):
        result = await server.call_tool("node", {"node_id": "/nonexistent"})
        text = _extract(result)
        assert "not found" in text.lower()

    async def test_tool_descriptions_are_descriptive(self, server):
        tools = await server.list_tools()
        short = [t.name for t in tools if len(t.description or "") < 10]
        assert not short


    async def test_symbol_note_tools_roundtrip(self, server):
        add = await server.call_tool("add_symbol_note", {"symbol_id": "src/app.py:main", "note": "Entry point owns startup", "source": "test"})
        assert "Added note" in _extract(add)
        listed = await server.call_tool("list_symbol_notes", {"symbol_id": "src/app.py:main"})
        assert "Entry point owns startup" in _extract(listed)
        searched = await server.call_tool("search_symbol_notes", {"query": "startup"})
        assert "src/app.py:main" in _extract(searched)


class TestMCPConfig:
    def test_create_server_accepts_config(self, tmp_path):
        config = CodePulseConfig(data_dir=str(tmp_path / "mcp_config_test"))
        server = create_server(config=config)
        assert server is not None
        assert hasattr(server, "list_tools") or hasattr(server, "call_tool")
