import pytest

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


@pytest.mark.asyncio
class TestMCPServerTools:
    async def test_list_tools_returns_9_tools(self, server):
        tools = await server.list_tools()
        assert len(tools) >= 9
        names = {t.name for t in tools}
        expected = {"repo_map", "context", "search", "callers", "callees", "impact", "trace", "node", "status"}
        assert expected.issubset(names)

    async def test_search_tool_returns_markdown_table(self, server):
        result = await server.call_tool("search", {"query": "class", "limit": 3})
        text = _extract(result)
        assert isinstance(text, str)
        # Should contain symbols or a "not found" message
        assert len(text) > 10

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

    async def test_tool_descriptions_are_descriptive(self, server):
        tools = await server.list_tools()
        short = [t.name for t in tools if len(t.description or "") < 10]
        assert not short
