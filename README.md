# CodePulse

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org)
[![Tests](https://img.shields.io/badge/tests-171%20passing-brightgreen.svg)](#)
[![TypeScript](https://img.shields.io/badge/TypeScript-CLI-blue)](https://www.typescriptlang.org)

**Code intelligence graph** — parse, query, and explore codebases. CLI, MCP server, interactive D3 force-directed graph.

```
pip install codepulse[all]
codepulse init --path myproject
codepulse index myproject/src
codepulse search "UserService"
codepulse mcp           # AI agent integration
```

---

## What it does

CodePulse parses your codebase into a **semantic knowledge graph** stored in SQLite. Instead of grep + read + repeat, you query the graph directly:

- **Search** symbols via FTS5 full-text search
- **Trace** callers, callees, and impact radius of any symbol
- **Visualize** your entire codebase as an interactive force-directed graph
- **Serve** an MCP server for AI coding agents

---

## Architecture

```
                    ┌──────────────────────┐
                    │    CLI (codepulse)    │
                    │  init · index · search│
                    │  callers · trace · mcp│
                    └──────┬───────┬───────┘
                           │       │
              ┌────────────┘       └────────────┐
              ▼                                  ▼
    ┌──────────────────┐              ┌──────────────────┐
    │   Tree-sitter    │              │  MCP Server      │
    │   Parser         │              │  (stdio)         │
    │   (12 languages) │              │  9 AI agent tools│
    └────────┬─────────┘              └────────┬─────────┘
             │                                 │
             ▼                                 ▼
    ┌──────────────────────────────────────────────┐
    │   SQLite Graph (nodes · edges · FTS5)        │
    │   Optional: SCIP cross-file resolution       │
    │   Optional: Embeddings similarity search     │
    └──────────────────────────────────────────────┘
             │
             ▼
    ┌──────────────────┐
    │  Web Dashboard   │
    │  D3.js force     │
    │  graph · search  │
    │  · detail panel  │
    └──────────────────┘
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
codepulse search "UserService"           # FTS5 full-text search
codepulse search --kind class "User"     # Filter by symbol kind
codepulse callers "src/app.ts:handleLogin"
codepulse trace "src/db.ts:connect" --depth 3
codepulse validate                       # Graph stats
```

### AI Agent Integration (MCP)

```bash
codepulse mcp
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

The MCP server provides 9 tools: `repo_map`, `context`, `search`, `callers`, `callees`, `impact`, `trace`, `node`, `status`.

### Web Dashboard

```bash
# Terminal 1: index your codebase
codepulse index myproject

# Terminal 2: start the dashboard
cd web
CODEPULSE_DB_PATH=~/.codepulse/graph.db npm run dev
```

Open `http://localhost:3000` to see an interactive force-directed graph of your codebase:

- **Pan/zoom** the D3 force simulation
- **Click** any node to see symbol details (file, signature, kind)
- **Search** via FTS5
- **Node colors**: function=amber, class=blue, method=purple, interface=cyan
- **Keyboard shortcuts**: `Ctrl+K` search, `Esc` close panel, `R` refresh

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
│   ├── cli.py            # Commander CLI (8 commands)
│   ├── mcp_server.py     # MCP protocol (9 tools)
│   ├── compat/scip.py    # SCIP → SQLite converter
│   ├── embeddings.py     # Semantic similarity search
│   └── config.py         # Config + env vars
├── web/                  # Next.js dashboard
│   ├── app/page.tsx      # Force graph + search + detail panel
│   ├── components/       # ForceGraph, NodeDetail, StatsBar
│   └── DESIGN.md         # Design system spec
├── packages/cli/         # TypeScript CLI (npm)
├── parsers/              # Per-language YAML query configs
├── tests/                # 124 Python tests
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

*Built with tree-sitter, SQLite, D3.js, and a lot of curiosity.*
