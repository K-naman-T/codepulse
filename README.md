# CodePulse

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org)
[![TypeScript](https://img.shields.io/badge/TypeScript-CLI-blue)](https://www.typescriptlang.org)

**Code intelligence graph** — parse, query, and explore codebases through a local CLI and MCP server.

```
pip install codepulse[all]
codepulse init --path myproject
codepulse index myproject/src
codepulse search "UserService"
codepulse serve          # AI agent integration (alias: mcp)
```

---

## What it does

CodePulse parses your codebase into a **semantic knowledge graph** stored in SQLite. Instead of grep + read + repeat, you query the graph directly:

- **Search** symbols via FTS5 full-text search
- **Trace** paths between symbols and **impact** radius
- **Map** the codebase with `repo-map` and `context` commands
- **Serve** an MCP server for AI coding agents (also: `codepulse serve`)

---

## Architecture

```
                    ┌──────────────────────┐
                    │    CLI (codepulse)    │
                    │  init · index · search │
                    │  callers · callees    │
                    │  trace · impact       │
                    │  node · file          │
                    │  repo-map · context   │
                    │  serve · validate     │
                    └──────┬───────┬───────┘
                           │       │
              ┌────────────┘       └────────────┐
              ▼                                  ▼
    ┌──────────────────┐              ┌──────────────────┐
    │   Tree-sitter    │              │  MCP Server      │
    │   Parser         │              │  (stdio)         │
    │   (12 languages) │              │ 10 AI agent tools│
    └────────┬─────────┘              └────────┬─────────┘
             │                                 │
             ▼                                 ▼
    ┌──────────────────────────────────────────────┐
    │   SQLite Graph (nodes · edges · FTS5)        │
    │   Optional: SCIP cross-file resolution       │
    │   Optional: Embeddings similarity search     │
    └──────────────────────────────────────────────┘
```

---

## Quick Start

```bash
pip install "codepulse[all]"

# Analyze any public repo from URL
codepulse analyze https://github.com/owner/repo

# Or index your local project
cd myproject
codepulse init
codepulse index .
codepulse search "UserModel"
```

### Search

```bash
codepulse search "UserService"             # FTS5 full-text search
codepulse search --kind class "User"       # Filter by symbol kind
codepulse callers "src/app.ts:handleLogin"
codepulse callees "src/app.ts:handleLogin"
codepulse trace "src/a.ts:foo" "src/b.ts:bar"  # Path between two symbols
codepulse impact "src/db.ts:connect" --depth 3  # Impact radius
codepulse node "src/app.ts:handleLogin"         # Symbol details
codepulse file "src/app.ts"                     # Symbols in a file
codepulse repo-map                              # Codebase overview
codepulse context "user auth"                   # Context for a task
codepulse validate                              # Graph stats
codepulse validate --strict                     # Exit nonzero on issues
```

### AI Agent Integration (MCP)

```bash
codepulse mcp       # or: codepulse serve
```

Then configure your AI agent (OpenCode, Claude Code, Cursor):

```json
{
  "mcp": {
    "codepulse": {
      "type": "local",
      "command": ["codepulse", "mcp"]
    }
  }
}
```

The MCP server provides 10 tools: `repo_map`, `context`, `search`, `callers`, `callees`, `impact`, `trace`, `node`, `file`, `status`.


---

## Supported Languages

| Language | Status |
|---|---|
| Python | ✅ Full |
| TypeScript / JavaScript | ✅ Full |
| Go | ✅ Full |
| Java | ✅ Full |
| Rust | ✅ Full |
| Ruby | ✅ Full |
| PHP | ✅ Full |
| C | ✅ Full |
| C++ | ✅ Full |
| Swift | ✅ Full |
| Kotlin | ✅ Full |
| Scala | ✅ Full |

---

## SCIP Integration (Optional)

For **type-accurate** cross-file symbol resolution:

```bash
pip install protobuf  # required
npm install -g @sourcegraph/scip-typescript @sourcegraph/scip-python

codepulse index . --use-scip
```

SCIP resolves `h.process()` → `Helper.process` instead of bare `process`. Without SCIP, CodePulse uses tree-sitter for fast syntax-level parsing; with SCIP, it adds type-level accuracy.

---

## Embeddings (Optional)

Semantic similarity search across your codebase:

```bash
pip install sentence-transformers
codepulse embed
codepulse similar "user authentication"
```

---

## File Structure

```
codepulse/
├── src/codepulse/        # Python core (parser, graph, MCP, CLI)
│   ├── parser.py         # Tree-sitter AST walker (12 languages)
│   ├── db.py             # SQLite graph storage + FTS5
│   ├── graph.py          # Index, search, callers/callees
│   ├── cli.py            # Click CLI commands
│   ├── mcp_server.py     # MCP protocol (10 tools)
│   ├── compat/scip.py    # SCIP → SQLite converter
│   ├── embeddings.py     # Semantic similarity search
│   └── config.py         # Config + env vars
├── packages/cli/         # TypeScript CLI (npm)
├── parsers/              # Per-language YAML query configs
├── tests/                # Python test suite
│   ├── test_accuracy.py  # Golden file tests
│   ├── test_languages.py # 17 multi-language tests
│   ├── test_scip.py      # SCIP resolution accuracy
│   └── test_smoke.py     # Real-repo regression tests
└── scripts/benchmark/    # A/B benchmark system
```

---

## Development

```bash
git clone https://github.com/codepulse/codepulse.git
cd codepulse
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[all]"
pip install pytest pytest-asyncio pytest-click
python3 -m pytest tests/
```

---

## License

MIT

---

*Built with tree-sitter, SQLite, and a lot of curiosity.*
