# Complete CodePulse E2E Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make CodePulse work end to end from clean install to `init -> index -> validate --strict -> search/context/trace -> MCP`, with exact graph validation, reproducible package tests, and real-repo corpus validation.

**Architecture:** Keep CodePulse local-first: Python owns indexing, graph storage, traversal, validation, and MCP semantics; the TypeScript CLI delegates to Python instead of duplicating graph logic. The graph model becomes explicit about files, symbols, external modules, unresolved references, provenance, and validation issues so internal graph integrity can be enforced without hiding ambiguity.

**Tech Stack:** Python 3.10+, tree-sitter grammar wheels, SQLite + FTS5, Click, FastMCP, watchdog, SCIP CLI/indexers, pytest, Vitest, npm package for CLI shell.

---

## Current Baseline

Current verified baseline on 2026-05-28:

```bash
export PATH="$HOME/.local/bin:$HOME/.npm-global/bin:$PATH"
python3 -m pytest tests/ --tb=short -q
```

Expected current output:

```text
304 passed, 3 xfailed, 1 xpassed
```

TypeScript package baseline:

```bash
npm test -- --run
```

Expected current output from `packages/cli`:

```text
Test Files  4 passed
Tests  29 passed
```

The existing tests prove basic parser breadth, SQLite CRUD, some traversal, MCP direct-output formatting, SCIP happy path, and CLI smoke behavior. They do not yet prove an end-to-end product.

---

## What Is Missing, By Subsystem

### Parser And Symbol Extraction

Files:
- `src/codepulse/parser.py`
- `parsers/*.yml`
- `tests/test_golden.py`
- `tests/fixtures/accuracy.*`

Missing details:
- `parse_file()` decodes every file as UTF-8 without recovery.
- `_PARSERS_DIR` points to the repository root and may not work after wheel install.
- Node IDs use absolute paths and are not stable across checkouts.
- Import edges use `source_id=file_path` and raw target text, which creates orphan edges.
- Top-level calls fall back to `source_id=file_path`, which can create orphan call edges.
- Go receiver methods need parent extraction from receiver clauses.
- Rust functions inside `impl` need method classification and parent extraction.
- Scala object xfail is now XPASS and should be removed.
- Fixtures are small and mostly single-file.
- Golden tests check missing expected symbols but do not fail on extra symbols.

### Graph Storage And Edge Model

Files:
- `src/codepulse/db.py`
- `src/codepulse/graph.py`
- new `src/codepulse/ids.py`
- new `src/codepulse/validation.py`

Missing details:
- No first-class file/module/external nodes.
- `edges` has no metadata, range, confidence, provenance, or resolution status.
- No schema migration/version table.
- Edge uniqueness collapses multiple callsites between the same symbols.
- `delete_file_nodes()` misses file-level source edges.
- `index_all()` deletes by `LIKE resolved%`, which can delete unrelated paths with the same prefix.
- `index_all()` drops edge-only batches if `batch_nodes` is empty.
- `resolve_cross_file_edges()` is bare-name heuristic only and can choose wrong targets.
- `get_impact_radius()` mutates the current frontier while iterating.
- There is no core `trace_path()` method.

### SCIP Integration

Files:
- `src/codepulse/compat/scip.py`
- `src/codepulse/graph.py`
- `tests/test_scip.py`

Missing details:
- `is_scip_available()` depends on PATH only.
- `_find_scip_indexer()` returns one indexer and misses nested/mixed-language repos.
- `_ensure_deps()` silently runs `npm install` inside user projects.
- `index.scip` is written to the project root.
- SCIP reference edges use `source_id=file_path`, not the enclosing symbol or file node.
- SCIP edges are merged after heuristic cross-file resolution without reconciliation.
- SCIP tests cover one trivial TypeScript project only.

### CLI And User Flows

Files:
- `src/codepulse/cli.py`
- `README.md`
- `install.sh`
- `PLAN.md`

Missing details:
- `search` does not print node IDs even though callers/callees require IDs.
- CLI `trace` is actually impact radius; MCP `trace` is source-to-target path.
- Missing CLI commands: `repo-map`, `context`, `node`, `file`, `impact`, `scan` alias, `serve` alias.
- `mcp` ignores `--data-dir` because the MCP server reloads config.
- `validate` always exits 0, even with graph integrity problems.
- `export --format` accepts a format but only writes GEXF.
- `analyze --branch` is accepted but unused.
- `analyze` still suggests `cd web && npm run dev`, but the web dashboard was removed.
- `install.sh` says Python 3.9+ although `pyproject.toml` requires 3.10+.
- `install.sh` installs plain `codepulse` first, which can omit grammar extras.

### MCP Contract

Files:
- `src/codepulse/mcp_server.py`
- `src/codepulse/mcp.py`
- `tests/test_mcp_server.py`
- `tests/test_mcp_contract.py`

Missing details:
- Runtime has 10 tools, docs say 9.
- `context()` claims relationship context but only returns search hits.
- `node()` asks for source but does not include source or relationships.
- `file()` is present but underdocumented and under-tested.
- Legacy `src/codepulse/mcp.py` has divergent tool semantics.
- Tests bypass real MCP stdio transport.

### TypeScript CLI Package

Files:
- `packages/cli/src/python-bridge.ts`
- `packages/cli/src/cli.ts`
- `packages/cli/src/installer.ts`
- `packages/cli/src/mcp.ts`
- `packages/cli/package.json`
- `packages/cli/tests/*.ts`

Missing details:
- `PythonBridge.spawn(name, args)` ignores `name` and runs `python3 <args>`.
- `callPython()` tries to run Python as if `init` were a Python script.
- Installer writes `python3 -m codepulse serve`, but there is no `__main__.py` and Python command is `mcp`.
- TS CLI queries `~/.codepulse/graph.db` directly, ignoring project-local DBs.
- TS MCP duplicates Python graph traversal and has a different tool set.
- TS tests check command registration but not real execution.

### Validation And CI

Files:
- `tests/test_golden.py`
- `tests/test_integrity.py`
- `tests/test_e2e.py`
- `tests/test_scip.py`
- `tests/test_smoke.py`
- `.github/workflows/test.yml`

Missing details:
- No precision/recall/F1 reporting for symbols or edges.
- Golden tests do not enforce exact emitted sets.
- Current xfails: Go parent IDs, Rust impl methods, fixture orphan edges.
- Current XPASS: Scala object function test.
- E2E allows `orphan_edges <= 2` instead of requiring zero internal orphans.
- CI ignores SCIP and smoke tests.
- CI TypeScript job still points at removed `web` directory.
- No clean wheel install test.
- No npm pack/install test.
- No real repo corpus validator with pinned commits.

---

## Definition Of Done

The project is considered end-to-end working only when all of these are true:

- A clean Python install includes parser configs and can index a fixture project outside the repository checkout.
- `codepulse init` creates a project-local `.codepulse/` with a valid DB and config.
- `codepulse index . --use-scip` works when SCIP is installed and degrades clearly when it is not.
- `codepulse validate --strict` returns exit 0 for healthy graphs and nonzero for orphan internal edges, stale files, invalid parents, schema mismatches, and parser errors.
- Internal graph edges have node-backed `source_id` and `target_id`; external/unresolved dependencies are represented explicitly, not as accidental orphans.
- Golden fixture tests enforce exact expected symbol and edge sets for all supported languages.
- Precision/recall/F1 is reported for symbols, calls, imports, and parent links.
- CLI and MCP expose the same core semantics for repo map, context, search, callers, callees, impact, trace, node, file, and status.
- TypeScript CLI either delegates to Python or uses shared generated contracts; it does not duplicate graph semantics.
- Watch mode receives real filesystem events, debounces, reindexes changed files, deletes removed files, and reruns resolution/validation hooks.
- CI has fast unit jobs, SCIP integration jobs, package install jobs, TS package jobs, and scheduled corpus validation.
- README, install script, and plan docs describe only features that exist.

---

## Target File Map

Create:

- `src/codepulse/ids.py` - canonical helpers for file, symbol, external, and unresolved node IDs.
- `src/codepulse/schema.py` - schema version constants and migration functions.
- `src/codepulse/validation.py` - structural validation plus accuracy metrics.
- `src/codepulse/batch.py` - real-repo/corpus validation runner.
- `src/codepulse/exporters.py` - GEXF and JSON export without graph repair hacks.
- `tests/fixtures/projects/` - multi-file and multi-language fixture projects.
- `tests/golden/` - exact expected manifests for symbols and edges.
- `tests/test_validation_metrics.py` - precision/recall tests.
- `tests/test_package_install.py` - wheel/sdist smoke tests.
- `tests/test_batch_validation.py` - corpus manifest and aggregation tests.

Modify:

- `src/codepulse/parser.py` - parser config loading, file nodes, import edges, language-specific normalizers.
- `src/codepulse/db.py` - schema migrations, edge metadata/ranges, traversal fixes.
- `src/codepulse/graph.py` - safe indexing pipeline, validation delegation, trace API, SCIP merge order.
- `src/codepulse/compat/scip.py` - multi-indexer, safe output path, source-symbol mapping, no implicit install.
- `src/codepulse/watcher.py` - real watchdog observer and incremental reindex.
- `src/codepulse/cli.py` - user-facing command contract and strict validation exits.
- `src/codepulse/mcp_server.py` - exact 10-tool MCP contract.
- `packages/cli/src/*.ts` - delegate to Python or remove duplicate graph logic.
- `pyproject.toml` - package data, strict xfail, markers, optional deps cleanup.
- `.github/workflows/test.yml` - correct Python/TS/SCIP/package jobs.
- `README.md`, `PLAN.md`, `install.sh` - accurate docs and install commands.

---

## Execution Rules

- Work in order. Do not start a later phase until the phase acceptance command passes.
- Use TDD for behavior changes: failing test first, minimal implementation, targeted pass, full relevant suite.
- Keep one logical change per commit.
- Do not remove existing tests; strengthen them or replace them with stricter equivalents.
- When changing public CLI or MCP behavior, update tests and docs in the same task.
- Use `export PATH="$HOME/.local/bin:$HOME/.npm-global/bin:$PATH"` before SCIP test commands locally.

---

## Phase 0: Lock The Current Truth

### Task 1: Make test status honest

**Files:**
- Modify: `pyproject.toml`
- Modify: `tests/test_golden.py`
- Modify: `tests/test_integrity.py`

- [ ] Step 1: Run the Python baseline.

```bash
export PATH="$HOME/.local/bin:$HOME/.npm-global/bin:$PATH"
python3 -m pytest tests/ --tb=short -q
```

Expected now: `304 passed, 3 xfailed, 1 xpassed`.

- [ ] Step 2: Remove the stale Scala xfail in `tests/test_golden.py` from `TestGoldenScala::test_all_functions_found` because it XPASSes.

- [ ] Step 3: Add strict xfail behavior to `pyproject.toml`.

```toml
[tool.pytest.ini_options]
xfail_strict = true
```

- [ ] Step 4: Keep only the real known xfails: Go receiver parent, Rust impl method classification, fixture orphan edges.

- [ ] Step 5: Run the golden and integrity subsets.

```bash
python3 -m pytest tests/test_golden.py tests/test_integrity.py --tb=short -q
```

Expected after implementation: pass with only strict expected xfails.

- [ ] Step 6: Commit.

```bash
git add pyproject.toml tests/test_golden.py tests/test_integrity.py
git commit -m "test: make validation xfails strict"
```

### Task 2: Make SCIP discovery independent of shell PATH

**Files:**
- Modify: `src/codepulse/compat/scip.py`
- Modify: `tests/test_scip.py`

- [ ] Step 1: Add a test that clears PATH but keeps SCIP in known local locations.

Test name: `tests/test_scip.py::TestSCIPIntegration::test_scip_available_from_default_local_bins`.

Expected behavior: `is_scip_available()` returns true when `~/.local/bin/scip` exists even if PATH omits it.

- [ ] Step 2: Update `is_scip_available()` to use `_which("scip")` first, then run the resolved executable.

Implementation target:

```python
def is_scip_available() -> bool:
    scip = _which("scip")
    if not scip:
        return False
    try:
        result = subprocess.run([scip, "--help"], capture_output=True, timeout=5)
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False
```

- [ ] Step 3: Run SCIP tests.

```bash
python3 -m pytest tests/test_scip.py -v
```

Expected: all SCIP tests pass locally when binaries exist.

- [ ] Step 4: Commit.

```bash
git add src/codepulse/compat/scip.py tests/test_scip.py
git commit -m "test: make SCIP discovery deterministic"
```

---

## Phase 1: Clean Install And Project Model

### Task 3: Package parser YAML with the Python wheel

**Files:**
- Move: `parsers/*.yml` -> `src/codepulse/parsers/*.yml`
- Modify: `src/codepulse/parser.py`
- Modify: `pyproject.toml`
- Create: `tests/test_package_data.py`

- [ ] Step 1: Write a package-data test.

Test name: `tests/test_package_data.py::test_parser_configs_are_loaded_from_package_resources`.

Test behavior: instantiate `SourceParser()` and parse `tests/fixtures/accuracy.py` without relying on repository-root `parsers/`.

- [ ] Step 2: Move all parser YAML files into `src/codepulse/parsers/`.

- [ ] Step 3: Change parser config loading to package resources.

Implementation target in `src/codepulse/parser.py`:

```python
from importlib.resources import files

_PARSERS_PACKAGE = "codepulse.parsers"

def _default_parsers_dir() -> Path:
    return Path(str(files(_PARSERS_PACKAGE)))
```

- [ ] Step 4: Add package-data configuration.

```toml
[tool.setuptools.package-data]
"codepulse.parsers" = ["*.yml"]
```

- [ ] Step 5: Run parser/package tests.

```bash
python3 -m pytest tests/test_package_data.py tests/test_parser.py tests/test_languages.py -q
```

Expected: all pass.

- [ ] Step 6: Commit.

```bash
git add pyproject.toml src/codepulse/parser.py src/codepulse/parsers tests/test_package_data.py parsers
git commit -m "fix: package parser configs with CodePulse"
```

### Task 4: Make project-local `.codepulse` the default runtime model

**Files:**
- Modify: `src/codepulse/config.py`
- Modify: `src/codepulse/cli.py`
- Modify: `src/codepulse/mcp_server.py`
- Modify: `tests/test_config.py`
- Modify: `tests/test_cli.py`
- Modify: `tests/test_mcp_server.py`

- [ ] Step 1: Add tests for config discovery.

Test cases:
- `CodePulseConfig.load_for_project(path)` uses `path/.codepulse` when it exists.
- CLI global `--data-dir` overrides project discovery.
- MCP server uses the config object passed by CLI instead of reloading globals.

- [ ] Step 2: Implement `CodePulseConfig.load_for_project(path: str | None = None)`.

Expected behavior:
- If `--data-dir` is provided, use it.
- Else if current project has `.codepulse/`, use it.
- Else fall back to `~/.codepulse` only for backward-compatible global usage.

- [ ] Step 3: Change `cli()` to store both `config` and `project_root` in `ctx.obj`.

- [ ] Step 4: Change `mcp_server.create_server(config: CodePulseConfig | None = None)` so CLI can pass the already-resolved config.

- [ ] Step 5: Run config, CLI, and MCP tests.

```bash
python3 -m pytest tests/test_config.py tests/test_cli.py tests/test_mcp_server.py -q
```

Expected: all pass.

- [ ] Step 6: Commit.

```bash
git add src/codepulse/config.py src/codepulse/cli.py src/codepulse/mcp_server.py tests/test_config.py tests/test_cli.py tests/test_mcp_server.py
git commit -m "fix: use project-local CodePulse config by default"
```

---

## Phase 2: Graph Identity And Schema Integrity

### Task 5: Add canonical ID helpers

**Files:**
- Create: `src/codepulse/ids.py`
- Create: `tests/test_ids.py`
- Modify: `src/codepulse/parser.py`
- Modify: `src/codepulse/compat/scip.py`

- [ ] Step 1: Create tests for ID helpers.

Required behavior:
- `file_node_id("/repo/src/a.py") == "/repo/src/a.py:__file__"`
- `symbol_node_id("/repo/src/a.py", "User.save") == "/repo/src/a.py:User.save"`
- `external_node_id("module", "os") == "external:module:os"`
- `unresolved_node_id("calls", "missing") == "unresolved:calls:missing"`

- [ ] Step 2: Implement `src/codepulse/ids.py`.

Implementation target:

```python
from pathlib import Path

def normalize_path(path: str) -> str:
    return str(Path(path).expanduser().resolve())

def file_node_id(file_path: str) -> str:
    return f"{normalize_path(file_path)}:__file__"

def symbol_node_id(file_path: str, qualified_name: str) -> str:
    return f"{normalize_path(file_path)}:{qualified_name}"

def external_node_id(kind: str, name: str) -> str:
    return f"external:{kind}:{name}"

def unresolved_node_id(kind: str, name: str) -> str:
    return f"unresolved:{kind}:{name}"
```

- [ ] Step 3: Replace direct string assembly in `parser.py` and `scip.py` with helper calls.

- [ ] Step 4: Run ID and parser tests.

```bash
python3 -m pytest tests/test_ids.py tests/test_edge_model.py tests/test_scip.py -q
```

Expected: all pass.

- [ ] Step 5: Commit.

```bash
git add src/codepulse/ids.py src/codepulse/parser.py src/codepulse/compat/scip.py tests/test_ids.py
git commit -m "refactor: centralize graph node identifiers"
```

### Task 6: Add file and external nodes so imports are never accidental orphans

**Files:**
- Modify: `src/codepulse/parser.py`
- Modify: `src/codepulse/db.py`
- Modify: `src/codepulse/graph.py`
- Modify: `tests/test_integrity.py`
- Modify: `tests/test_e2e.py`
- Create: `tests/test_import_edges.py`

- [ ] Step 1: Write import-edge tests.

Required assertions:
- Every parsed file emits one `kind="file"` node with ID `file_node_id(file_path)`.
- Import edge `source_id` is the file node ID.
- External imports target an `external:module:<name>` node.
- Internal imports target an indexed file or symbol node when resolvable.
- `CodePulse.validate().orphan_edges == 0` for fixture indexing.

- [ ] Step 2: Update parser output contract to include file nodes.

Expected output from `parse_file()`:
- First node is the file node.
- Symbol nodes keep existing IDs.
- Import edges use file node as source.
- Top-level call edges use file node as source if no enclosing symbol exists.

- [ ] Step 3: Update `GraphDB.bulk_import()` to upsert external/unresolved nodes before edges when parser emits them.

- [ ] Step 4: Remove `@pytest.mark.xfail` from `TestOrphanEdges::test_validate_on_fixtures_yields_zero_orphans`.

- [ ] Step 5: Strengthen E2E assertion from `orphan_edges <= 2` to `orphan_edges == 0`.

- [ ] Step 6: Run integrity and E2E tests.

```bash
python3 -m pytest tests/test_import_edges.py tests/test_integrity.py tests/test_e2e.py -q
```

Expected: all pass with no orphan-edge xfail.

- [ ] Step 7: Commit.

```bash
git add src/codepulse/parser.py src/codepulse/db.py src/codepulse/graph.py tests/test_import_edges.py tests/test_integrity.py tests/test_e2e.py
git commit -m "fix: model imports with file and external nodes"
```

### Task 7: Add schema versioning and edge metadata

**Files:**
- Create: `src/codepulse/schema.py`
- Modify: `src/codepulse/db.py`
- Modify: `tests/test_db.py`
- Create: `tests/test_schema_migrations.py`

- [ ] Step 1: Add migration tests.

Required assertions:
- A new DB creates `schema_meta` with current version.
- Existing DBs missing new columns are migrated in place.
- `edges` stores `metadata`, `line_start`, `line_end`, `column_start`, `column_end`, `confidence`, and `provenance`.
- Multiple callsites between the same source and target can be preserved.

- [ ] Step 2: Add `Edge.metadata` and range/provenance fields to the dataclass.

Target fields:

```python
metadata: dict[str, Any] = field(default_factory=dict)
line_start: int = 0
line_end: int = 0
column_start: int = 0
column_end: int = 0
confidence: float = 1.0
provenance: str = "tree-sitter"
resolution_status: str = "resolved"
```

- [ ] Step 3: Implement schema migrations in `GraphDB.initialize()` via `schema.py`.

- [ ] Step 4: Update `_upsert_edge_raw()` and all edge construction sites.

- [ ] Step 5: Run DB and graph tests.

```bash
python3 -m pytest tests/test_db.py tests/test_schema_migrations.py tests/test_edge_model.py tests/test_traversal.py -q
```

Expected: all pass.

- [ ] Step 6: Commit.

```bash
git add src/codepulse/schema.py src/codepulse/db.py tests/test_db.py tests/test_schema_migrations.py
git commit -m "feat: add graph schema migrations and edge metadata"
```

---

## Phase 3: Parser Correctness For Known Xfails

### Task 8: Fix Go receiver method parent IDs

**Files:**
- Modify: `src/codepulse/parser.py`
- Modify: `tests/test_golden.py`
- Modify: `tests/fixtures/accuracy.go`

- [ ] Step 1: Remove the Go xfail and run the single test to confirm failure.

```bash
python3 -m pytest tests/test_golden.py::TestGoldenGo::test_methods_have_parent_class -q
```

Expected before implementation: fail because parent IDs are missing or wrong.

- [ ] Step 2: Add parser logic for Go `function_declaration` with a receiver child.

Required behavior:
- `func (c *Config) Load()` emits `kind="method"`.
- Parent ID resolves to the receiver type node, e.g. `<file>:Config`.
- Method name becomes `Config.Load`.

- [ ] Step 3: Add fixture coverage for pointer and value receivers.

- [ ] Step 4: Run Go golden tests.

```bash
python3 -m pytest tests/test_golden.py::TestGoldenGo -q
```

Expected: all Go golden tests pass without xfail.

- [ ] Step 5: Commit.

```bash
git add src/codepulse/parser.py tests/test_golden.py tests/fixtures/accuracy.go
git commit -m "fix: classify Go receiver functions as methods"
```

### Task 9: Fix Rust impl method classification

**Files:**
- Modify: `src/codepulse/parser.py`
- Modify: `tests/test_golden.py`
- Modify: `tests/fixtures/accuracy.rs`

- [ ] Step 1: Remove the Rust xfail and run the single test to confirm failure.

```bash
python3 -m pytest tests/test_golden.py::TestGoldenRust::test_all_methods_found -q
```

Expected before implementation: fail because impl methods are classified as functions.

- [ ] Step 2: Add Rust-specific handling for `function_item` inside `impl_item`.

Required behavior:
- `impl User { fn name(&self) {} }` emits `kind="method"`.
- Parent ID resolves to `<file>:User`.
- Method name becomes `User.name`.

- [ ] Step 3: Add fixture coverage for inherent impl and trait impl.

- [ ] Step 4: Run Rust golden tests.

```bash
python3 -m pytest tests/test_golden.py::TestGoldenRust -q
```

Expected: all Rust golden tests pass without xfail.

- [ ] Step 5: Commit.

```bash
git add src/codepulse/parser.py tests/test_golden.py tests/fixtures/accuracy.rs
git commit -m "fix: classify Rust impl functions as methods"
```

### Task 10: Normalize exact symbol names without short-name hiding

**Files:**
- Modify: `tests/test_golden.py`
- Modify: `tests/fixtures/accuracy.py`, `tests/fixtures/accuracy.ts`, `tests/fixtures/accuracy.go`, `tests/fixtures/accuracy.rs`, `tests/fixtures/accuracy.java`, `tests/fixtures/accuracy.rb`, `tests/fixtures/accuracy.php`, `tests/fixtures/accuracy.c`, `tests/fixtures/accuracy.cpp`, `tests/fixtures/accuracy.swift`, `tests/fixtures/accuracy.kt`, `tests/fixtures/accuracy.scala`
- Modify: `src/codepulse/parser.py`

- [ ] Step 1: Replace `_short()` correctness checks with exact expected names in golden tests.

Required behavior:
- Expected `User.save` must not pass as plain `save`.
- Wrong parent-qualified names fail.
- Extra unexpected symbols fail unless explicitly marked as allowed external/file nodes.

- [ ] Step 2: Add per-language `allowed_extra_kinds = {"file", "external_module", "external_symbol"}` where needed.

- [ ] Step 3: Run all golden tests.

```bash
python3 -m pytest tests/test_golden.py -q
```

Expected after parser fixes: all pass, no xfail, no xpass.

- [ ] Step 4: Commit.

```bash
git add src/codepulse/parser.py tests/test_golden.py tests/fixtures
git commit -m "test: make golden parser checks exact"
```

---

## Phase 4: Safe Indexing And Incremental Updates

### Task 11: Make full indexing safe and deterministic

**Files:**
- Modify: `src/codepulse/graph.py`
- Modify: `src/codepulse/config.py`
- Modify: `src/codepulse/db.py`
- Create: `tests/test_indexing_pipeline.py`

- [ ] Step 1: Add tests for safe path deletion.

Required case: indexing `/repo/src` must not delete `/repo/src-old`.

- [ ] Step 2: Add tests for files with edges but no symbols.

Required case: a file containing only imports still persists its file node and import edges.

- [ ] Step 3: Add tests for parser errors.

Required case: one unreadable file records an error but does not erase existing graph data for other files.

- [ ] Step 4: Replace `LIKE f"{resolved}%"` deletion with exact file manifest deletion.

Expected behavior:
- Find files under the indexed root.
- Delete stale rows only for files in that root using exact normalized file paths.
- Wrap deletion and import in a transaction.

- [ ] Step 5: Add `files` table or manifest fields with path, language, content hash, indexed_at, parser_version, error.

- [ ] Step 6: Run indexing tests.

```bash
python3 -m pytest tests/test_indexing_pipeline.py tests/test_integrity.py tests/test_e2e.py -q
```

Expected: all pass.

- [ ] Step 7: Commit.

```bash
git add src/codepulse/graph.py src/codepulse/config.py src/codepulse/db.py tests/test_indexing_pipeline.py
git commit -m "fix: make indexing transactionally safe"
```

### Task 12: Implement real watch mode

**Files:**
- Modify: `src/codepulse/watcher.py`
- Modify: `src/codepulse/graph.py`
- Modify: `tests/test_watcher.py`

- [ ] Step 1: Replace current sleep loop tests with watchdog behavior tests.

Required cases:
- Created file indexes after debounce.
- Modified file deletes old nodes and inserts new nodes.
- Deleted file removes file node, symbol nodes, and connected edges.
- Multiple rapid events collapse into one reindex.
- Incremental update reruns cross-file resolution.

- [ ] Step 2: Implement watchdog `Observer` and event handler.

- [ ] Step 3: Replace dummy lock with `threading.Lock`.

- [ ] Step 4: Expose `CodePulse.index_file(path)` and `CodePulse.delete_file(path)` for watcher use.

- [ ] Step 5: Run watcher tests.

```bash
python3 -m pytest tests/test_watcher.py tests/test_indexing_pipeline.py -q
```

Expected: all pass.

- [ ] Step 6: Commit.

```bash
git add src/codepulse/watcher.py src/codepulse/graph.py tests/test_watcher.py
git commit -m "feat: implement real incremental watch mode"
```

---

## Phase 5: SCIP As The Accurate Resolver

### Task 13: Make SCIP multi-language and safe

**Files:**
- Modify: `src/codepulse/compat/scip.py`
- Modify: `src/codepulse/config.py`
- Modify: `tests/test_scip.py`

- [ ] Step 1: Add tests for nested Python and TypeScript projects.

Required cases:
- Python files under `src/pkg/*.py` trigger `scip-python`.
- TypeScript files under `packages/app/src/*.ts` trigger `scip-typescript`.
- Mixed Python+TypeScript project runs both available indexers.

- [ ] Step 2: Change `_find_scip_indexer()` to return a list of indexer commands.

- [ ] Step 3: Write SCIP outputs to `.codepulse/scip/<language>.scip`, never project root.

- [ ] Step 4: Remove implicit `_ensure_deps()` installs.

Required behavior: if dependencies are missing, report a clear error in `IndexResult.errors`; never run `npm install` automatically.

- [ ] Step 5: Run SCIP tests.

```bash
python3 -m pytest tests/test_scip.py -q
```

Expected: all pass.

- [ ] Step 6: Commit.

```bash
git add src/codepulse/compat/scip.py src/codepulse/config.py tests/test_scip.py
git commit -m "fix: make SCIP indexing safe and multi-language"
```

### Task 14: Map SCIP references to enclosing symbols and reconcile edges

**Files:**
- Modify: `src/codepulse/compat/scip.py`
- Modify: `src/codepulse/db.py`
- Modify: `src/codepulse/graph.py`
- Modify: `tests/test_scip.py`
- Create: `tests/test_scip_reconciliation.py`

- [ ] Step 1: Add a test where two classes both define `process()`.

Required behavior: SCIP resolves `Helper.process`, not the first bare-name `process`.

- [ ] Step 2: Add a test where a SCIP reference occurs inside a function.

Required behavior: edge `source_id` is the enclosing function/method node, not the file path.

- [ ] Step 3: Add metadata to SCIP edges.

Required fields:
- `provenance="scip"`
- `resolution_status="resolved"`
- `confidence=1.0`
- original SCIP symbol in metadata.

- [ ] Step 4: Change indexing order.

Required behavior:
- Import tree-sitter nodes and edges.
- Import SCIP nodes and edges.
- Reconcile SCIP edges over heuristic edges.
- Run bare-name heuristic only for unresolved tree-sitter call edges not covered by SCIP.

- [ ] Step 5: Run SCIP reconciliation tests.

```bash
python3 -m pytest tests/test_scip.py tests/test_scip_reconciliation.py tests/test_edge_model.py -q
```

Expected: all pass.

- [ ] Step 6: Commit.

```bash
git add src/codepulse/compat/scip.py src/codepulse/db.py src/codepulse/graph.py tests/test_scip.py tests/test_scip_reconciliation.py
git commit -m "fix: reconcile SCIP references with graph edges"
```

---

## Phase 6: Traversal And Context Semantics

### Task 15: Add core trace API and fix impact frontier

**Files:**
- Modify: `src/codepulse/db.py`
- Modify: `src/codepulse/graph.py`
- Modify: `tests/test_traversal.py`
- Modify: `tests/test_mcp_contract.py`

- [ ] Step 1: Add tests for `GraphDB.trace_path(source, target, max_depth)`.

Required cases:
- Direct path returns `[source, target]`.
- Multi-hop path returns ordered nodes.
- No path returns `None`.
- Cycle does not loop forever.
- Max depth is respected.

- [ ] Step 2: Fix `get_impact_radius()` to use a separate `next_nodes` set for each depth.

- [ ] Step 3: Add optional `edge_kinds: set[str] | None` filters to callers, callees, impact, and trace.

- [ ] Step 4: Add `CodePulse.trace_path()` wrapper.

- [ ] Step 5: Run traversal tests.

```bash
python3 -m pytest tests/test_traversal.py tests/test_mcp_contract.py -q
```

Expected: all pass.

- [ ] Step 6: Commit.

```bash
git add src/codepulse/db.py src/codepulse/graph.py tests/test_traversal.py tests/test_mcp_contract.py
git commit -m "fix: add canonical trace and impact traversal"
```

---

## Phase 7: Real Validation, Not Just Counts

### Task 16: Extract structural validation into `validation.py`

**Files:**
- Create: `src/codepulse/validation.py`
- Modify: `src/codepulse/graph.py`
- Modify: `tests/test_integrity.py`
- Create: `tests/test_validation_report.py`

- [ ] Step 1: Add tests for structured validation issues.

Required issue codes:
- `ORPHAN_EDGE_SOURCE`
- `ORPHAN_EDGE_TARGET`
- `ORPHAN_PARENT`
- `STALE_FILE`
- `INVALID_LINE_RANGE`
- `DUPLICATE_LOGICAL_SYMBOL`
- `SCHEMA_VERSION_MISMATCH`
- `PARSER_ERROR`

- [ ] Step 2: Move `ValidationReport` from `graph.py` to `validation.py`.

- [ ] Step 3: Add `issues: list[ValidationIssue]` to report.

- [ ] Step 4: Add `ok` property.

Required behavior: `ok` is true only when no severity `error` issues exist.

- [ ] Step 5: Update `CodePulse.validate()` to delegate to `validate_graph(db)`.

- [ ] Step 6: Run validation tests.

```bash
python3 -m pytest tests/test_integrity.py tests/test_validation_report.py -q
```

Expected: all pass.

- [ ] Step 7: Commit.

```bash
git add src/codepulse/validation.py src/codepulse/graph.py tests/test_integrity.py tests/test_validation_report.py
git commit -m "feat: add structured graph validation reports"
```

### Task 17: Add precision, recall, and F1 metrics against golden manifests

**Files:**
- Create: `tests/golden/accuracy.yml`
- Create: `src/codepulse/validation.py` additions
- Create: `tests/test_validation_metrics.py`
- Modify: `tests/test_golden.py`

- [ ] Step 1: Define golden manifest schema.

Manifest keys:
- `symbols`: list of `{id_suffix, name, kind, file, parent_name, line_start, line_end}`.
- `edges`: list of `{source_name, target_name, kind, file, line_number, resolution_status}`.
- `allowed_external`: list of external module/symbol names.

- [ ] Step 2: Add metric tests.

Required formulas:
- `precision = true_positives / emitted`
- `recall = true_positives / expected`
- `f1 = 2 * precision * recall / (precision + recall)`
- empty denominators produce `1.0` only when both expected and emitted are empty.

- [ ] Step 3: Implement `compare_to_golden(db, manifest)`.

Required output:
- symbol precision/recall/F1
- edge precision/recall/F1
- false positives
- false negatives
- wrong kind
- wrong parent
- wrong line range

- [ ] Step 4: Update golden tests to assert thresholds.

Initial required thresholds:
- symbols precision >= 0.98
- symbols recall >= 0.98
- calls precision >= 0.90
- calls recall >= 0.85
- imports precision >= 0.95
- imports recall >= 0.95
- parent links precision >= 0.98
- parent links recall >= 0.98

- [ ] Step 5: Run validation metric tests.

```bash
python3 -m pytest tests/test_validation_metrics.py tests/test_golden.py -q
```

Expected: all pass.

- [ ] Step 6: Commit.

```bash
git add src/codepulse/validation.py tests/golden tests/test_validation_metrics.py tests/test_golden.py
git commit -m "feat: measure graph precision and recall"
```

### Task 18: Expand single-language fixtures to cover real constructs

**Files:**
- Modify: `tests/fixtures/accuracy.py`
- Modify: `tests/fixtures/accuracy.ts`
- Modify: `tests/fixtures/accuracy.go`
- Modify: `tests/fixtures/accuracy.rs`
- Modify: `tests/fixtures/accuracy.java`
- Modify: `tests/fixtures/accuracy.rb`
- Modify: `tests/fixtures/accuracy.php`
- Modify: `tests/fixtures/accuracy.c`
- Modify: `tests/fixtures/accuracy.cpp`
- Modify: `tests/fixtures/accuracy.swift`
- Modify: `tests/fixtures/accuracy.kt`
- Modify: `tests/fixtures/accuracy.scala`
- Modify: `tests/golden/accuracy.yml`

- [ ] Step 1: Add Python constructs: async def, decorators, classmethod, staticmethod, property, nested function, relative import, alias import.

- [ ] Step 2: Add TypeScript constructs: arrow function, exported class, default export, interface, type alias, enum, generic method, optional chaining.

- [ ] Step 3: Add Go constructs: interface, pointer receiver, value receiver, package-qualified call, init function, generic function.

- [ ] Step 4: Add Rust constructs: trait, trait impl, inherent impl, module, associated function, enum, generic function.

- [ ] Step 5: Add Java, Kotlin, Scala, Swift constructs: package/import, interface/trait/protocol, inheritance, annotation, constructor, static/companion members.

- [ ] Step 6: Add Ruby/PHP/C/C++ constructs: class methods, module/namespace, constructor/destructor where relevant, header/source include case for C++.

- [ ] Step 7: Update exact golden manifest for every new symbol and edge.

- [ ] Step 8: Run golden tests.

```bash
python3 -m pytest tests/test_golden.py tests/test_validation_metrics.py -q
```

Expected: all pass with thresholds.

- [ ] Step 9: Commit.

```bash
git add tests/fixtures tests/golden tests/test_golden.py
git commit -m "test: expand golden fixtures across supported languages"
```

### Task 19: Add multi-file and multi-language fixture projects

**Files:**
- Create: `tests/fixtures/projects/python_app/`
- Create: `tests/fixtures/projects/typescript_app/`
- Create: `tests/fixtures/projects/mixed_stack/`
- Create: `tests/test_project_fixtures.py`

- [ ] Step 1: Create `python_app` with `models.py`, `services.py`, `main.py`, relative imports, aliases, same function name in two files.

- [ ] Step 2: Create `typescript_app` with `src/models.ts`, `src/service.ts`, `src/index.ts`, default export, named export, re-export barrel, duplicate method names.

- [ ] Step 3: Create `mixed_stack` with Python backend and TypeScript frontend in one root.

- [ ] Step 4: Add exact expected manifests for each project.

- [ ] Step 5: Add tests that index each project with tree-sitter only and assert zero internal orphans.

- [ ] Step 6: Add tests that index Python and TypeScript projects with SCIP and assert qualified cross-file targets.

- [ ] Step 7: Run project fixture tests.

```bash
python3 -m pytest tests/test_project_fixtures.py tests/test_scip.py -q
```

Expected: all pass.

- [ ] Step 8: Commit.

```bash
git add tests/fixtures/projects tests/test_project_fixtures.py
git commit -m "test: add multi-file project validation fixtures"
```

### Task 20: Add reproducible batch validation over real repos

**Files:**
- Create: `src/codepulse/batch.py`
- Modify: `src/codepulse/cli.py`
- Create: `tests/fixtures/corpus/manifest.yml`
- Create: `tests/test_batch_validation.py`

- [ ] Step 1: Define corpus manifest schema.

Required fields per repo:
- `name`
- `url`
- `commit`
- `language`
- `path`
- `use_scip`
- `max_seconds`
- `min_symbols`
- `max_internal_orphans`

- [ ] Step 2: Implement `BatchValidator`.

Required behavior:
- Clones or uses local cache.
- Checks out pinned commit.
- Runs `CodePulse.index_all()`.
- Runs `validate()`.
- Captures duration, files, nodes, edges, issues, precision if manifest exists.
- Writes JSON report.

- [ ] Step 3: Add CLI command `validate-corpus manifest.yml --output report.json`.

- [ ] Step 4: Add small fixture manifest using local fixture projects so tests do not require network.

- [ ] Step 5: Run batch tests.

```bash
python3 -m pytest tests/test_batch_validation.py -q
```

Expected: all pass.

- [ ] Step 6: Commit.

```bash
git add src/codepulse/batch.py src/codepulse/cli.py tests/fixtures/corpus tests/test_batch_validation.py
git commit -m "feat: add reproducible batch validation runner"
```

---

## Phase 8: CLI, MCP, And TypeScript Contract

### Task 21: Fix Python CLI semantics and outputs

**Files:**
- Modify: `src/codepulse/cli.py`
- Modify: `tests/test_cli.py`
- Modify: `README.md`

- [ ] Step 1: Add CLI tests that assert exact useful output for `search` includes `ID:`.

- [ ] Step 2: Add commands: `repo-map`, `context`, `node`, `file`, `impact`.

- [ ] Step 3: Change `trace` to accept `source` and `target` node IDs.

- [ ] Step 4: Keep old one-argument impact behavior under `impact`, not `trace`.

- [ ] Step 5: Add `serve` alias for `mcp` and `scan` alias for `index`.

- [ ] Step 6: Add `validate --strict` with nonzero exit when `report.ok` is false.

- [ ] Step 7: Validate `export --format`; unsupported formats exit nonzero.

- [ ] Step 8: Pass `branch` into `clone_repo()` or remove the option.

- [ ] Step 9: Run CLI tests.

```bash
python3 -m pytest tests/test_cli.py tests/test_export.py -q
```

Expected: all pass.

- [ ] Step 10: Commit.

```bash
git add src/codepulse/cli.py tests/test_cli.py tests/test_export.py README.md
git commit -m "fix: align CLI commands with graph semantics"
```

### Task 22: Make MCP tools exact and transport-tested

**Files:**
- Modify: `src/codepulse/mcp_server.py`
- Delete or deprecate: `src/codepulse/mcp.py`
- Modify: `tests/test_mcp_server.py`
- Modify: `tests/test_mcp_contract.py`
- Create: `tests/test_mcp_transport.py`

- [ ] Step 1: Assert exact tool list.

Required tools:
- `repo_map`
- `context`
- `search`
- `callers`
- `callees`
- `impact`
- `trace`
- `node`
- `file`
- `status`

- [ ] Step 2: Update `search()` and `context()` outputs to include node IDs.

- [ ] Step 3: Update `context()` to include immediate callers and callees for each matched symbol.

- [ ] Step 4: Update `node()` to include source excerpt, callers, and callees.

- [ ] Step 5: Add MCP stdio launch test using a temporary data dir.

- [ ] Step 6: Remove divergent legacy MCP behavior or mark `src/codepulse/mcp.py` as compatibility wrapper around `mcp_server.py`.

- [ ] Step 7: Run MCP tests.

```bash
python3 -m pytest tests/test_mcp_server.py tests/test_mcp_contract.py tests/test_mcp_transport.py -q
```

Expected: all pass.

- [ ] Step 8: Commit.

```bash
git add src/codepulse/mcp_server.py src/codepulse/mcp.py tests/test_mcp_server.py tests/test_mcp_contract.py tests/test_mcp_transport.py
git commit -m "fix: enforce exact MCP tool contract"
```

### Task 23: Make the TypeScript CLI delegate to Python

**Files:**
- Modify: `packages/cli/src/python-bridge.ts`
- Modify: `packages/cli/src/cli.ts`
- Modify: `packages/cli/src/installer.ts`
- Modify or delete: `packages/cli/src/mcp.ts`
- Modify: `packages/cli/tests/*.ts`
- Modify: `packages/cli/package.json`

- [ ] Step 1: Add a PythonBridge test that expects command execution as `python3 -m codepulse.cli` or `codepulse`, not `python3 init`.

- [ ] Step 2: Implement `PythonBridge.spawn(command, args)` so `command` is used.

Recommended behavior:
- Prefer `codepulse` executable.
- Fallback to `python3 -m codepulse.cli` only if executable is unavailable and `__main__` or module execution is implemented.

- [ ] Step 3: Add `src/codepulse/__main__.py` if `python -m codepulse` remains a supported invocation.

Required content:

```python
from codepulse.cli import cli

if __name__ == "__main__":
    cli()
```

- [ ] Step 4: Change installer MCP command to the real command.

Required command:

```json
{
  "command": "codepulse",
  "args": ["mcp"],
  "env": {}
}
```

- [ ] Step 5: Remove direct SQLite query logic from TS commands or mark it internal and unregistered.

- [ ] Step 6: Make `serve` delegate to `codepulse mcp` instead of starting a separate TS MCP implementation.

- [ ] Step 7: Add Vitest cases that execute `init`, `index --help`, and `serve --help` through a mocked bridge.

- [ ] Step 8: Run TS tests.

```bash
npm test -- --run
```

Expected from `packages/cli`: all pass.

- [ ] Step 9: Commit.

```bash
git add src/codepulse/__main__.py packages/cli/src packages/cli/tests packages/cli/package.json
git commit -m "fix: make npm CLI delegate to Python CodePulse"
```

---

## Phase 9: Optional Capabilities That Must Not Break Core

### Task 24: Make embeddings incremental and validated

**Files:**
- Modify: `src/codepulse/embeddings.py`
- Modify: `src/codepulse/db.py`
- Modify: `src/codepulse/validation.py`
- Create: `tests/test_embeddings.py`

- [ ] Step 1: Add tests for model name and dimension storage.

- [ ] Step 2: Store actual model name, not backend name.

- [ ] Step 3: Skip unchanged nodes using node content hash plus model name.

- [ ] Step 4: Add validation issue for embeddings with wrong dimensions or missing nodes.

- [ ] Step 5: Run embedding tests.

```bash
python3 -m pytest tests/test_embeddings.py -q
```

Expected: all pass.

- [ ] Step 6: Commit.

```bash
git add src/codepulse/embeddings.py src/codepulse/db.py src/codepulse/validation.py tests/test_embeddings.py
git commit -m "fix: make embeddings incremental and validated"
```

### Task 25: Move exports into core and stop repairing broken edges at export time

**Files:**
- Create: `src/codepulse/exporters.py`
- Modify: `src/codepulse/cli.py`
- Modify: `tests/test_export.py`

- [ ] Step 1: Add exporter tests for GEXF and JSON.

- [ ] Step 2: Move `_export_gexf()` from `cli.py` to `exporters.py`.

- [ ] Step 3: Remove source/target fallback matching inside GEXF export.

Required behavior: invalid edges are excluded only when validation has already identified them; exporter does not guess repairs.

- [ ] Step 4: Add `--format json` support.

- [ ] Step 5: Run export tests.

```bash
python3 -m pytest tests/test_export.py -q
```

Expected: all pass.

- [ ] Step 6: Commit.

```bash
git add src/codepulse/exporters.py src/codepulse/cli.py tests/test_export.py
git commit -m "refactor: move graph export into core"
```

---

## Phase 10: Install, CI, Docs, Release Gates

### Task 26: Add clean package install tests

**Files:**
- Create: `tests/test_package_install.py`
- Modify: `pyproject.toml`
- Modify: `packages/cli/package.json`

- [ ] Step 1: Add a Python test that builds a wheel in a temp directory.

- [ ] Step 2: Install the wheel into a clean venv.

- [ ] Step 3: Run `codepulse init`, `codepulse index <fixture>`, `codepulse validate --strict`, and `codepulse search User` from outside the repository root.

- [ ] Step 4: Add npm pack test that verifies `dist/index.js` is shipped.

- [ ] Step 5: Add `prepack` or `prepare` script in `packages/cli/package.json`.

- [ ] Step 6: Run package tests.

```bash
python3 -m pytest tests/test_package_install.py -q
```

Expected: all pass.

- [ ] Step 7: Commit.

```bash
git add pyproject.toml packages/cli/package.json tests/test_package_install.py
git commit -m "test: verify clean package installation"
```

### Task 27: Fix CI to match the actual project

**Files:**
- Modify: `.github/workflows/test.yml`

- [ ] Step 1: Replace the removed `web` working directory with `packages/cli`.

- [ ] Step 2: Add Python fast job for unit/golden tests.

- [ ] Step 3: Add SCIP integration job that installs `scip`, `@sourcegraph/scip-python`, and `@sourcegraph/scip-typescript`.

- [ ] Step 4: Add package install job.

- [ ] Step 5: Add scheduled corpus validation job that uploads JSON reports as artifacts.

- [ ] Step 6: Remove blanket `--ignore=tests/test_scip.py`; use markers or separate jobs instead.

- [ ] Step 7: Run workflow-equivalent commands locally.

```bash
python3 -m pytest tests/ --tb=short -q
npm test -- --run
```

Expected: all pass locally.

- [ ] Step 8: Commit.

```bash
git add .github/workflows/test.yml
git commit -m "ci: validate Python, SCIP, package, and npm flows"
```

### Task 28: Update install script and docs to match reality

**Files:**
- Modify: `install.sh`
- Modify: `README.md`
- Modify: `PLAN.md`
- Modify: `CONTRIBUTING.md`
- Modify: `AGENTS.md`

- [ ] Step 1: Update `install.sh` to require Python 3.10+.

- [ ] Step 2: Make `install.sh` install `codepulse[all]` by default.

- [ ] Step 3: Remove all web dashboard claims unless a dashboard is actually restored.

- [ ] Step 4: Document the exact CLI commands: `init`, `index`, `validate --strict`, `search`, `repo-map`, `context`, `node`, `file`, `mcp`.

- [ ] Step 5: Document SCIP setup with both the CLI binary and npm indexers.

- [ ] Step 6: Update MCP tool count to 10.

- [ ] Step 7: Update supported language table with tiers: parser-only, SCIP-backed, known limitations.

- [ ] Step 8: Run markdown/link sanity checks if available, otherwise run the full test suite.

```bash
python3 -m pytest tests/ --tb=short -q
```

Expected: all pass.

- [ ] Step 9: Commit.

```bash
git add install.sh README.md PLAN.md CONTRIBUTING.md AGENTS.md
git commit -m "docs: document the working CodePulse flow"
```

### Task 29: Final release gate

**Files:**
- No planned edits. If any gate fails, stop and return to the task that owns the failing subsystem.

- [ ] Step 1: Run full Python suite with SCIP available.

```bash
export PATH="$HOME/.local/bin:$HOME/.npm-global/bin:$PATH"
python3 -m pytest tests/ --tb=short -q
```

Expected final target: no xfails, no xpasses, no skips except explicitly marked unavailable optional backends.

- [ ] Step 2: Run TypeScript suite.

```bash
cd packages/cli && npm test -- --run
```

Expected: all pass.

- [ ] Step 3: Run clean CLI E2E from a temp directory.

```bash
tmpdir=$(mktemp -d)
cp -R tests/fixtures/projects/python_app "$tmpdir/python_app"
codepulse --data-dir "$tmpdir/python_app/.codepulse" init --path "$tmpdir/python_app"
codepulse --data-dir "$tmpdir/python_app/.codepulse" index "$tmpdir/python_app" --use-scip
codepulse --data-dir "$tmpdir/python_app/.codepulse" validate --strict
codepulse --data-dir "$tmpdir/python_app/.codepulse" search User
```

Expected: validate exits 0 and search prints node IDs.

- [ ] Step 4: Run MCP smoke test from CLI.

Required behavior: `codepulse --data-dir <tmp/.codepulse> mcp` starts and lists the 10 tools under the MCP transport test.

- [ ] Step 5: Run package install test.

```bash
python3 -m pytest tests/test_package_install.py -q
```

Expected: pass.

- [ ] Step 6: Run batch validation on local fixture corpus.

```bash
codepulse validate-corpus tests/fixtures/corpus/manifest.yml --output /tmp/codepulse-corpus-report.json
```

Expected: report contains zero internal orphans and all fixture projects pass thresholds.

- [ ] Step 7: Inspect git diff and confirm there is no uncommitted cleanup left from the gate.

```bash
git status --short
git diff --stat
```

Expected: no unexpected unstaged changes from the release gate itself. If files changed during the gate, assign them to the owning task and commit there.

---

## Recommended Execution Slices

Use these slices for subagent-driven development:

1. Phase 0 and Phase 1: honest tests, SCIP discovery, package data, project config.
2. Phase 2: graph IDs, file/external nodes, schema metadata.
3. Phase 3: Go/Rust/Scala parser correctness and exact golden checks.
4. Phase 4: safe indexing and watcher.
5. Phase 5: SCIP multi-language and reconciliation.
6. Phase 6 and Phase 7: traversal and validation metrics.
7. Phase 8: CLI, MCP, TypeScript delegation.
8. Phase 9: embeddings/export hardening.
9. Phase 10: CI, install, docs, release gates.

Each slice should end with targeted tests, relevant full-suite tests, and an atomic commit.

---

## Self-Review Checklist

- Every known xfail and xpass has a task.
- Import orphan edges have a graph-model fix, not a test workaround.
- SCIP is made deterministic, safe, multi-language, and source-symbol aware.
- CLI, MCP, and TypeScript package are aligned to one contract.
- Package installation is tested outside the source checkout.
- Real validation includes exact golden manifests and precision/recall metrics.
- Batch corpus validation exists and can run in CI/nightly.
- Removed web dashboard claims are cleaned from docs and install script.
- The final gate proves clean install, index, strict validation, query, MCP, and corpus reporting.
