# ADR 0002: Turbo Indexer — parser cache, file cache, and parallel parsing

## Status

Accepted.

## Context

The original `CodePulse.index_all` rebuilt everything from scratch on every invocation:

- A new `Parser` object was created for every file, even though Tree-sitter `Parser` is stateless and fully reusable across parses of the same language.
- No cache existed for previously indexed files. Changing one file meant re-parsing every file, even when 99% were unchanged.
- Parsing was strictly sequential. On multi-core machines, files queued up behind the single-threaded parse loop.

For CI workflows, iterative development, and large-repo indexing, these three shortcomings made re-indexing scale linearly with total file count instead of delta.

## Decision

### 1. Parser reuse (parser.py:SourceParser)

`Parser` objects are cached per language inside `SourceParser._parsers`. The first call to `_ensure_language` creates one `Parser(grammar)` and reuses it for all subsequent `parse_file` calls for that language.

**Before:**
```python
parser = Parser(self._grammars[language])  # new Parser per file
```

**After:**
```python
parser = self._parsers[language]           # cached once per language
```

### 2. File index cache (db.py:GraphDB + graph.py)

A new `indexed_files` table stores per-file metadata:

| Column        | Type    | Purpose                          |
|---------------|---------|----------------------------------|
| `file_path`   | TEXT PK | Absolute path to file            |
| `size`        | INTEGER | `os.stat().st_size`              |
| `mtime_ns`    | INTEGER | `os.stat().st_mtime_ns`          |
| `content_hash`| TEXT    | blake2b hex digest of file bytes |
| `indexed_at`  | TEXT    | SQLite datetime                  |

On index, before parsing a file, `_is_file_unchanged` checks:

1. Does a row exist in `indexed_files` for this path?
2. Does `os.stat` match stored `size` and `mtime_ns`?
3. Does blake2b match stored `content_hash`?

If all three match, the file is **skipped** — no parse, no DB write.

If the file is new or changed, old nodes/edges are deleted via `delete_file_epoch` (which does NOT touch `symbol_notes`), then the file is re-parsed and re-imported.

The cache survives across CLI invocations since it lives in the same SQLite database.

### 3. Parallel parsing (graph.py:CodePulse._index_parallel)

When `workers > 1`, `index_all` delegates file parsing to `ProcessPoolExecutor`. A module-level function `_parse_files_worker` creates a fresh `SourceParser` per subprocess (grammar DLLs load independently per process).

**Design constraints:**

- Only file *parsing* runs in subprocesses. SQLite writes always happen in the main process via `bulk_import`. This avoids SQLite serialization issues and connection sharing.
- Errors are collected per-file and reported, never crash the indexer.
- `_is_file_unchanged` is checked in the main process before submitting to workers, so only changed files consume pool slots.
- Default worker count: `min(os.cpu_count() or 1, 8)`.
- `ProcessPoolExecutor` uses the default `fork` start method (Linux) — acceptable since the fork happens before any threading.

### 4. IndexResult extension

New fields: `elapsed_seconds`, `files_skipped`, `cache_hits`, `cache_misses`, `workers`.

### 5. CLI

- `codepulse index --workers N --no-cache`
- `codepulse bench <path_or_url>` — runs warm (sequential), cached, and parallel benchmarks, reports throughput.

## Consequences

**Positive:**

- Second index of unchanged repo is near-instant (~0s).
- Modified files are handled correctly (old nodes deleted, only delta re-parsed).
- Symbol notes survive re-index (separate table, never deleted by indexer).
- Parallel parsing gives near-linear speedup on multi-core machines for CPU-bound parsing.
- `bench` command provides a repeatable way to measure and compare throughput.

**Tradeoffs:**

- Subprocess overhead for small repos: ProcessPoolExecutor adds ~0.1-0.3s per worker for grammar loading. For repos with <20 files, sequential may be faster.
- blake2b hash is computed on every file during the *first* index (and when files change). This is negligible (~0.01s per 100KB) but adds some time to the initial full index.
- `mtime_ns` is platform-dependent. Filesystems with sub-second precision (ext4, APFS, NTFS) work correctly; others may cause false cache misses on rapid edits.

## Future work

- Optional inotify/watch-based invalidation (existing `FileWatcher` could be taught to update cache entries on file change events).
- `indexed_files.clean()` — remove stale entries for files that no longer exist on disk.
- `--cache-only` mode that updates metadata without re-parsing (for watch mode).
- Configurable hash algorithm (e.g., fast xxhash when available).


## Cache-hit verification policy

Warm indexing uses a metadata-only hit test: path + size + `mtime_ns`. This is deliberate. Re-hashing every unchanged file would perform a full byte read of the repository on every "cached" run, which is the exact cost the cache is meant to avoid. CodePulse still records a BLAKE2 content hash when a file is indexed so future strict verification modes can compare hashes when needed.

If a filesystem preserves both size and nanosecond mtime across content changes, CodePulse may skip a changed file. That tradeoff matches common build-tool behavior and keeps the default path fast. A user can force correctness over cache speed with `codepulse index --no-cache`.
