# ADR 0001: SQLite + Tree-sitter + MCP for local code intelligence

## Status

Accepted for v0.

## Context

AI coding agents usually discover code through repeated text search and file reads. That works on small repos but degrades quickly: callers, callees, symbol ownership, and impact radius are inferred repeatedly instead of stored as queryable structure.

CodePulse needs a local-first representation that can run on laptops, work without external services, and expose compact tools to agents.

## Decision

Use:

- Tree-sitter for language-aware symbol extraction
- SQLite for local graph storage
- FTS5 for fast symbol and note search
- MCP over stdio as the agent-facing interface
- D3 dashboard for visual exploration

## Why SQLite instead of a graph database

SQLite is dependency-light, portable, inspectable, and good enough for v0 graph queries over repository-scale data. It avoids forcing users to run Neo4j, Postgres, Docker, or a hosted service before they get value.

The graph model remains explicit: `nodes`, `edges`, and `symbol_notes`. If CodePulse outgrows SQLite for very large monorepos, the schema can be lifted into a dedicated graph engine later.

## Why Tree-sitter instead of regex

Regex can find names but cannot reliably distinguish classes, methods, functions, imports, and nested declarations across languages. Tree-sitter gives CodePulse resilient syntax trees while still being lightweight enough for local indexing.

## Why MCP

MCP is the cleanest interface for AI coding agents. It lets CodePulse expose semantic operations directly: `repo_map`, `context`, `search`, `callers`, `callees`, `impact`, symbol notes, and status. Agents get structured repo knowledge without scraping the filesystem every turn.

## Why symbol notes

Agents need working memory tied to code, not only chat history. `symbol_notes` lets a human or agent attach observations to a symbol id: architecture notes, edit hypotheses, bug context, and review findings. This turns CodePulse from a static code graph into a repo-local memory layer.

## Consequences

Positive:

- zero server required for core CLI/MCP workflows
- easy backup and inspection (`sqlite3 graph.db`)
- works with local/private repos by default
- simple mental model for contributors

Tradeoffs:

- recursive graph queries are less expressive than a native graph DB
- language coverage depends on available Tree-sitter grammars
- cross-file semantic resolution remains approximate without SCIP/LSP enrichments

## Future work

- optional SCIP/LSP enrichment for stronger cross-file edges
- persistent agent sessions over the note layer
- repo dossier generation from graph + notes
- benchmark suite against real public repos
