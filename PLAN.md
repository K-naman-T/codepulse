# CodePulse — Build Plan

## Core Principle
We **assemble** from battle-tested OSS, we don't rebuild. Our code is the glue (~2000-3000 lines Python).

## Stack
| Layer | What we use | How |
|---|---|---|
| Parser | `py-tree-sitter` + grammar wheels | `pip install tree-sitter tree-sitter-python tree-sitter-typescript` |
| Python deps | `jedi` + `xnuinside/codegraph` | Direct Python import |
| Cross-file | **SCIP** indexers | Subprocess → protobuf → SQLite |
| Search | **Sivru** (BM25+embeddings) | Fork or sub-MCP-server |
| Context rank | **Aider's grep-ast** (PageRank) | Direct Python import |
| Storage | `sqlite-utils` + `sqlite3` | Schema + FTS5 |
| CLI | `click` | Same as codegraph |
| MCP | `mcp` (official Python SDK) | stdio transport |
| Config | `pydantic-settings` + YAML | Env var override, file fallback |
| Testing | `pytest` + `pytest-asyncio` | ~78 tests |

## File Structure
```
codepulse/
├── src/codepulse/
│   ├── __init__.py
│   ├── config.py              # Whitelabel config
│   ├── db.py                  # SQLite schema + CRUD
│   ├── parser.py              # Tree-sitter AST walker
│   ├── graph.py               # Graph queries
│   ├── cli.py                 # 5 click commands
│   ├── mcp.py                 # 4 MCP tools
│   ├── watcher.py             # File watcher
│   └── compat/
│       ├── codegraph.py       # xnuinside/codegraph adapter
│       └── scip.py            # SCIP → SQLite converter
├── tests/
│   ├── conftest.py            # Fixtures
│   ├── test_config.py         # 8 tests
│   ├── test_db.py             # 12 tests
│   ├── test_parser.py         # 16 tests
│   ├── test_graph.py          # 12 tests
│   ├── test_cli.py            # 14 tests
│   ├── test_mcp.py            # 10 tests
│   ├── test_watcher.py        # 6 tests
│   └── fixtures/
│       ├── sample.py
│       └── sample.ts
├── parsers/
│   ├── python.yml
│   ├── typescript.yml
│   └── go.yml
├── pyproject.toml
└── config.yml.example
```

## Build Phases

### Phase 0: Foundation
- pyproject.toml with all deps
- `config.py` — pydantic model, YAML/env loading, whitelabel
- `__init__.py` — version

### Phase 1: SQLite Storage
- `db.py` — schema (nodes, edges, nodes_fts), CRUD, graph traversal

### Phase 2: Parser
- `parser.py` — generic tree-sitter walker
- `compat/codegraph.py` — xnuinside/codegraph adapter
- `compat/scip.py` — SCIP → SQLite converter
- `parsers/{python,typescript,go}.yml` — per-language query configs

### Phase 3: Graph Engine
- `graph.py` — CodePulse class (index, search, callers, callees, impact, context)

### Phase 4: CLI
- `cli.py` — init, index, search, callers, callees, trace

### Phase 5: MCP Server
- `mcp.py` — search_symbols, find_code, get_callers, get_impact_radius

### Phase 6: Watcher
- `watcher.py` — watchdog + debounce + incremental reindex

## Test Summary
| Suite | Tests | Type |
|---|---|---|
| test_config.py | 8 | Unit |
| test_db.py | 12 | Unit (in-memory SQLite) |
| test_parser.py | 16 | Unit + Integration |
| test_graph.py | 12 | Integration |
| test_cli.py | 14 | Integration |
| test_mcp.py | 10 | Integration |
| test_watcher.py | 6 | Integration |
| **Total** | **~78** | |

Whitelabel: all branding in `config.py`, nothing hardcoded. Loads from `~/.<binary_name>/config.yml` or env vars.
