"""MCP stdio transport tests.

Launches the MCP server as a subprocess and communicates via JSON-RPC
over stdin/stdout using the MCP protocol.
"""

import json
import os
from pathlib import Path
import select
import subprocess
import sys

import pytest

pytestmark = [
    pytest.mark.skipif(sys.version_info < (3, 10), reason="MCP requires Python 3.10+"),
    pytest.mark.skipif(sys.platform == "win32", reason="stdio timeout uses select on pipes"),
]


@pytest.fixture
def mcp_stdio(tmp_path):
    env = os.environ.copy()
    src_path = Path.cwd() / "src"
    env["PYTHONPATH"] = f"{src_path}:{env.get('PYTHONPATH', '')}"
    proc = subprocess.Popen(
        [
            sys.executable,
            "-c",
            "from codepulse.cli import cli; cli()",
            "--data-dir",
            str(tmp_path / ".codepulse"),
            "mcp",
        ],
        env=env,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    yield proc, tmp_path / ".codepulse"
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()


def _send(proc, method, params=None, req_id=1):
    """Send a JSON-RPC request and return the response."""
    req = {"jsonrpc": "2.0", "id": req_id, "method": method}
    if params is not None:
        req["params"] = params
    if proc.stdin is None or proc.stdout is None:
        raise RuntimeError("MCP server stdio pipes were not created")
    proc.stdin.write(json.dumps(req).encode() + b"\n")
    proc.stdin.flush()
    ready, _, _ = select.select([proc.stdout], [], [], 5)
    if not ready:
        proc.terminate()
        try:
            proc.wait(timeout=1)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=1)
        stderr = proc.stderr.read() if proc.stderr is not None else b""
        raise TimeoutError(
            f"Timed out waiting for MCP response. stderr: {stderr.decode(errors='replace')}"
        )
    line = proc.stdout.readline()
    if not line:
        stderr = proc.stderr.read() if proc.stderr is not None else b""
        raise RuntimeError(
            f"No response from MCP server. stderr: {stderr.decode(errors='replace')}"
        )
    return json.loads(line)


class TestMCPStdioTransport:
    """Verify the MCP server launches and communicates via stdio."""

    def test_list_tools_returns_expected_tools(self, mcp_stdio):
        proc, _ = mcp_stdio

        resp = _send(proc, "initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "test", "version": "1.0"},
        })
        assert "result" in resp, f"Initialize failed: {resp}"

        resp = _send(proc, "tools/list", req_id=2)
        assert "result" in resp, f"tools/list failed: {resp}"
        tools = resp["result"]["tools"]
        names = {t["name"] for t in tools}
        expected = {
            "repo_map", "context", "search", "callers", "callees",
            "impact", "trace", "node", "file", "add_symbol_note",
            "list_symbol_notes", "search_symbol_notes", "status",
        }
        assert names == expected, f"Expected {expected}, got {names}"

    def test_tool_call_returns_result(self, mcp_stdio):
        proc, _ = mcp_stdio

        _send(proc, "initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "test", "version": "1.0"},
        })

        resp = _send(proc, "tools/call", {
            "name": "status",
            "arguments": {},
        }, req_id=2)
        assert "result" in resp, f"tools/call status failed: {resp}"
        content = resp["result"]["content"]
        assert len(content) > 0
        text = content[0].get("text", "")
        assert "files" in text.lower() or "0" in text or "symbols" in text.lower()

    def test_tool_call_search_without_index(self, mcp_stdio):
        """Search on empty index returns not-found message (not crash)."""
        proc, _ = mcp_stdio

        _send(proc, "initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "test", "version": "1.0"},
        })

        resp = _send(proc, "tools/call", {
            "name": "search",
            "arguments": {"query": "test", "limit": 5},
        }, req_id=2)
        assert "result" in resp, f"tools/call search failed: {resp}"
        content = resp["result"]["content"]
        assert len(content) > 0
        text = content[0].get("text", "")
        assert isinstance(text, str)
