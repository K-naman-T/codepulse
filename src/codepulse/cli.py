import sys
from pathlib import Path

import click

from codepulse import __version__
from codepulse.config import CodePulseConfig
from codepulse.graph import CodePulse
from codepulse.watcher import FileWatcher
from codepulse.embeddings import index_embeddings, get_embedder, serialize_vector


@click.group(
    name="codepulse",
    invoke_without_command=False,
    context_settings=dict(help_option_names=["-h", "--help"]),
)
@click.option(
    "--data-dir",
    default=None,
    help="Data directory (default: ~/.codepulse)",
)
@click.version_option(version=__version__, prog_name="CodePulse")
@click.pass_context
def cli(ctx: click.Context, data_dir: str | None) -> None:
    ctx.ensure_object(dict)
    ctx.obj["project_root"] = Path.cwd()
    ctx.obj["explicit_data_dir"] = data_dir is not None
    config = CodePulseConfig.load_for_project(path=str(Path.cwd()))
    if data_dir:
        config.data_dir = data_dir
    ctx.obj["config"] = config


@cli.command()
@click.option("--path", default=".", help="Project path")
@click.pass_context
def init(ctx: click.Context, path: str) -> None:
    """Initialize a project for code graph indexing."""
    config = ctx.obj["config"]
    project_root = ctx.obj["project_root"]
    target = Path(path)
    if not target.is_absolute():
        target = project_root / path
    target = target.resolve()
    if not ctx.obj.get("explicit_data_dir"):
        config.data_dir = str(target / ".codepulse")
    cp = CodePulse(config)
    cp.init_project()
    click.echo(f"Initialized in {config.config_dir}")


@cli.command()
@click.argument("path", default=".")
@click.option("--watch", "-w", is_flag=True, help="Watch for changes and re-index")
@click.option("--use-scip", is_flag=True, help="Use SCIP indexer for accurate call graph")
@click.option("--no-cache", is_flag=True, help="Force full reindex, skipping file cache")
@click.option("--workers", default=1, type=int, help="Parallel parser workers (default 1 = sequential)")
@click.pass_context
def index(ctx: click.Context, path: str, watch: bool, use_scip: bool, no_cache: bool, workers: int) -> None:
    """Index all code files to build the graph."""
    config = ctx.obj["config"]
    project_root = ctx.obj["project_root"]
    path_obj = Path(path)
    if not path_obj.is_absolute():
        path_obj = project_root / path
    resolved_path = str(path_obj.resolve())
    if use_scip:
        config.use_scip = True
    cp = CodePulse(config)
    result = cp.index_all(resolved_path, no_cache=no_cache, workers=workers)

    click.echo(f"Files indexed: {result.files_indexed}")
    click.echo(f"Symbols found: {result.symbols_found}")
    click.echo(f"Edges found: {result.edges_found}")
    if result.elapsed_seconds:
        click.echo(f"Elapsed: {result.elapsed_seconds:.2f}s")
    if result.files_skipped:
        click.echo(f"Files skipped (cached): {result.files_skipped}")
        click.echo(f"Cache hits: {result.cache_hits}  misses: {result.cache_misses}")
    if result.errors:
        for err in result.errors[:5]:
            click.echo(f"Error: {err}", err=True)

    if watch:
        click.echo(f"Watching {resolved_path} for changes...")
        w = FileWatcher(resolved_path, cp, debounce_ms=config.watch_debounce_ms)

        def on_index(msg: str) -> None:
            click.echo(msg)

        w.on_index = on_index
        try:
            w.start()
            import time as _time
            while True:
                _time.sleep(1)
        except KeyboardInterrupt:
            w.stop()
            click.echo("\nWatcher stopped.")


@cli.command()
@click.argument("query")
@click.option("--kind", "-k", default=None, help="Filter by kind: function, class, method")
@click.option("--limit", "-l", default=20, help="Max results")
@click.pass_context
def search(ctx: click.Context, query: str, kind: str | None, limit: int) -> None:
    """Search indexed symbols."""
    config = ctx.obj["config"]
    cp = CodePulse(config)
    results = cp.search(query, kind=kind, limit=limit)

    if not results:
        click.echo("No results found.")
        return

    for node in results:
        suffix = f" ({node.kind})" if node.kind else ""
        loc = f"  {node.file_path}:{node.line_start}"
        click.echo(f"  {node.name}{suffix}")
        click.echo(f"  ID: {node.id}")
        click.echo(loc)
        if node.signature:
            click.echo(f"  {node.signature[:120]}")
        click.echo()


@cli.command()
@click.argument("node_id")
@click.option("--depth", "-d", default=1, help="Traversal depth")
@click.pass_context
def callers(ctx: click.Context, node_id: str, depth: int) -> None:
    """Show nodes that call a given symbol."""
    config = ctx.obj["config"]
    cp = CodePulse(config)
    results = cp.get_callers(node_id, depth=depth)

    if not results:
        click.echo("No callers found.")
        return

    for node, edge_kind in results:
        click.echo(f"  {node.name} ({edge_kind})")
        click.echo(f"  {node.file_path}:{node.line_start}")
        click.echo()


@cli.command()
@click.argument("node_id")
@click.option("--depth", "-d", default=1, help="Traversal depth")
@click.pass_context
def callees(ctx: click.Context, node_id: str, depth: int) -> None:
    """Show symbols called by a given node."""
    config = ctx.obj["config"]
    cp = CodePulse(config)
    results = cp.get_callees(node_id, depth=depth)

    if not results:
        click.echo("No callees found.")
        return

    for node, edge_kind in results:
        click.echo(f"  {node.name} ({edge_kind})")
        click.echo(f"  {node.file_path}:{node.line_start}")
        click.echo()


@cli.command()
@click.argument("source")
@click.argument("target")
@click.option("--depth", "-d", default=10, help="Max traversal depth")
@click.pass_context
def trace(ctx: click.Context, source: str, target: str, depth: int) -> None:
    """Trace the call path between two symbols."""
    config = ctx.obj["config"]
    cp = CodePulse(config)
    path = cp.trace_path(source, target, max_depth=depth)

    if not path:
        click.echo("No path found between these symbols.")
        return

    click.echo(f"Path ({len(path) - 1} hops):")
    for node in path:
        click.echo(f"  {node.name} ({node.kind})")
        click.echo(f"  {node.file_path}:{node.line_start}")
        click.echo()


@cli.command()
@click.argument("node_id")
@click.option("--depth", "-d", default=3, help="Impact depth")
@click.pass_context
def impact(ctx: click.Context, node_id: str, depth: int) -> None:
    """Show impact radius of a symbol (what would be affected by changing it)."""
    config = ctx.obj["config"]
    cp = CodePulse(config)
    result = cp.get_impact_radius(node_id, depth=depth)

    if not result:
        click.echo("No impact found.")
        return

    for level, nodes in sorted(result.items()):
        click.echo(f"Depth {level}:")
        for node in nodes:
            click.echo(f"  {node.name} ({node.kind})")
            click.echo(f"  {node.file_path}:{node.line_start}")
            click.echo()


@cli.command()
@click.option("--backend", default="local", help="Embedding backend: local or openai")
@click.option("--model", default=None, help="Model name")
@click.pass_context
def embed(ctx: click.Context, backend: str, model: str | None) -> None:
    """Generate embeddings for all indexed symbols."""
    config = ctx.obj["config"]
    cp = CodePulse(config)

    def on_progress(msg: str) -> None:
        click.echo(msg)

    count = index_embeddings(cp.db, backend=backend, model=model, on_progress=on_progress)
    click.echo(f"Embedded {count} symbols.")


@cli.group()
def note() -> None:
    """Attach and search human/agent notes on indexed symbols."""


@note.command("add")
@click.argument("symbol_id")
@click.argument("note_text")
@click.option("--source", default="human", help="Note source label, e.g. human or agent")
@click.pass_context
def note_add(ctx: click.Context, symbol_id: str, note_text: str, source: str) -> None:
    """Attach a note to a symbol id."""
    config = ctx.obj["config"]
    cp = CodePulse(config)
    created = cp.add_symbol_note(symbol_id, note_text, source=source)
    click.echo(f"Added note {created.id} to {created.symbol_id}")


@note.command("list")
@click.argument("symbol_id")
@click.option("--limit", "-l", default=20, help="Max notes")
@click.pass_context
def note_list(ctx: click.Context, symbol_id: str, limit: int) -> None:
    """List notes attached to a symbol id."""
    config = ctx.obj["config"]
    cp = CodePulse(config)
    notes = cp.list_symbol_notes(symbol_id, limit=limit)
    if not notes:
        click.echo("No notes found.")
        return
    for item in notes:
        click.echo(f"[{item.id}] {item.symbol_id} · {item.source} · {item.created_at}")
        click.echo(f"  {item.note}")


@note.command("search")
@click.argument("query")
@click.option("--limit", "-l", default=20, help="Max notes")
@click.pass_context
def note_search(ctx: click.Context, query: str, limit: int) -> None:
    """Search symbol notes via FTS5."""
    config = ctx.obj["config"]
    cp = CodePulse(config)
    notes = cp.search_symbol_notes(query, limit=limit)
    if not notes:
        click.echo("No notes found.")
        return
    for item in notes:
        click.echo(f"[{item.id}] {item.symbol_id} · {item.source} · {item.created_at}")
        click.echo(f"  {item.note}")


@cli.command()
@click.argument("query")
@click.option("--limit", "-l", default=10, help="Max results")
@click.option("--backend", default="local", help="Embedding backend")
@click.option("--model", default=None, help="Model name")
@click.pass_context
def similar(ctx: click.Context, query: str, limit: int, backend: str, model: str | None) -> None:
    """Find semantically similar symbols."""
    config = ctx.obj["config"]
    cp = CodePulse(config)
    embed_fn = get_embedder(backend, model)
    vec = embed_fn([query])[0]
    results = cp.db.search_similar(vec, limit=limit)

    if not results:
        click.echo("No similar symbols found. Run `codepulse embed` first.")
        return

    for node, score in results:
        click.echo(f"  {node.name} ({node.kind})  similarity: {score:.3f}")
        click.echo(f"  {node.file_path}:{node.line_start}")
        if node.signature:
            click.echo(f"  {node.signature[:120]}")
        click.echo()


@cli.command()
@click.argument("url")
@click.option("--token", envvar="GITHUB_TOKEN", help="GitHub token for private repos")
@click.option("--branch", default=None, help="Branch to analyze (default: main)")
@click.option("--no-cache", is_flag=True, help="Force full reindex, skipping file cache")
@click.option("--workers", default=1, type=int, help="Parallel parser workers (default 1 = sequential)")
@click.pass_context
def analyze(ctx: click.Context, url: str, token: str | None, branch: str | None, no_cache: bool, workers: int) -> None:
    """Clone a repo from URL, index it, and open the graph.

    Supports GitHub, GitLab, Bitbucket URLs.
    """
    from codepulse.cloner import clone_repo, RepoCache
    from codepulse.graph import CodePulse

    config = ctx.obj["config"]

    def progress(msg: str) -> None:
        click.echo(f"  {msg}")

    click.echo(f"Analyzing {url}...")

    repo_path = clone_repo(url, token=token, on_progress=progress)
    click.echo(f"Repo at {repo_path}")

    cp = CodePulse(config)
    result = cp.index_all(repo_path, no_cache=no_cache, workers=workers)
    click.echo(f"Files indexed: {result.files_indexed}")
    click.echo(f"Symbols found: {result.symbols_found}")
    click.echo(f"Edges found: {result.edges_found}")
    if result.elapsed_seconds:
        click.echo(f"Elapsed: {result.elapsed_seconds:.2f}s")
    if result.files_skipped:
        click.echo(f"Files skipped (cached): {result.files_skipped}")

    click.echo("")
    click.echo("You can now:")
    click.echo("  codepulse search <query>  — search symbols")
    click.echo("  codepulse repo-map        — inspect top files and symbols")
    click.echo("  codepulse serve           — start MCP server for AI agents")
    click.echo("  codepulse validate --strict  — graph integrity check")


@cli.command()
@click.argument("path_or_url", default=".")
@click.option("--workers", default=0, type=int, help="Parser workers (0 = auto, min(os.cpu_count(), 8))")
@click.option("--token", envvar="GITHUB_TOKEN", help="GitHub token for private URL repos")
@click.pass_context
def bench(ctx: click.Context, path_or_url: str, workers: int, token: str | None) -> None:
    """Benchmark indexing performance on a path or git URL."""
    from codepulse.graph import CodePulse, _default_workers

    config = ctx.obj["config"]
    num_workers = workers if workers > 0 else _default_workers()

    is_url = "://" in path_or_url or path_or_url.startswith("git@")
    if is_url:
        from codepulse.cloner import clone_repo
        click.echo(f"Benchmark: cloning {path_or_url} ...")
        repo_path = clone_repo(path_or_url, token=token)
        click.echo(f"Cloned to {repo_path}")
        search_path = repo_path
    else:
        search_path = path_or_url

    cp = CodePulse(config)

    click.echo(f"Workers: {num_workers}")
    click.echo(f"Indexing {search_path} ...")

    # Warm cache with sequential first
    click.echo("--- Warm-up (sequential) ---")
    warm = cp.index_all(search_path)
    click.echo(f"  Files: {warm.files_indexed}, Symbols: {warm.symbols_found}, Edges: {warm.edges_found}")
    if warm.elapsed_seconds:
        rate_f = warm.files_indexed / warm.elapsed_seconds if warm.elapsed_seconds > 0 else 0
        rate_s = warm.symbols_found / warm.elapsed_seconds if warm.elapsed_seconds > 0 else 0
        rate_e = warm.edges_found / warm.elapsed_seconds if warm.elapsed_seconds > 0 else 0
        click.echo(f"  Elapsed: {warm.elapsed_seconds:.2f}s ({rate_f:.1f} files/s, {rate_s:.1f} sym/s, {rate_e:.1f} edges/s)")

    # Second run with cache
    click.echo("--- Cached (sequential) ---")
    cached = cp.index_all(search_path, no_cache=False)
    click.echo(f"  Files indexed: {cached.files_indexed}, Skipped: {cached.files_skipped}")
    if cached.elapsed_seconds:
        click.echo(f"  Elapsed: {cached.elapsed_seconds:.3f}s")

    # Force reindex with parallel workers
    if num_workers > 1:
        click.echo(f"--- Parallel ({num_workers} workers) ---")
        parallel = cp.index_all(search_path, no_cache=True, workers=num_workers)
        click.echo(f"  Files: {parallel.files_indexed}, Symbols: {parallel.symbols_found}, Edges: {parallel.edges_found}")
        if parallel.elapsed_seconds:
            rate_f = parallel.files_indexed / parallel.elapsed_seconds if parallel.elapsed_seconds > 0 else 0
            rate_s = parallel.symbols_found / parallel.elapsed_seconds if parallel.elapsed_seconds > 0 else 0
            rate_e = parallel.edges_found / parallel.elapsed_seconds if parallel.elapsed_seconds > 0 else 0
            click.echo(f"  Elapsed: {parallel.elapsed_seconds:.2f}s ({rate_f:.1f} files/s, {rate_s:.1f} sym/s, {rate_e:.1f} edges/s)")

    click.echo("--- Summary ---")
    click.echo(f"  Files: {warm.files_indexed + warm.files_skipped}, Symbols: {warm.symbols_found}, Edges: {warm.edges_found}")
    if warm.elapsed_seconds:
        click.echo(f"  Warm (seq):  {warm.elapsed_seconds:.2f}s")
    if cached.elapsed_seconds:
        click.echo(f"  Cached:      {cached.elapsed_seconds:.3f}s")
    if num_workers > 1 and parallel.elapsed_seconds:
        click.echo(f"  Parallel:    {parallel.elapsed_seconds:.2f}s ({num_workers} workers)")


@cli.command()
@click.pass_context
def mcp(ctx: click.Context) -> None:
    """Start MCP server over stdio for AI agent integration."""
    from codepulse.mcp_server import main as mcp_main
    try:
        mcp_main(config=ctx.obj["config"])
    except ImportError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.pass_context
def serve(ctx: click.Context) -> None:
    """Start MCP server over stdio for AI agent integration (alias for mcp)."""
    from codepulse.mcp_server import main as mcp_main
    try:
        mcp_main(config=ctx.obj["config"])
    except ImportError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.pass_context
@click.option("--strict", is_flag=True, help="Exit with nonzero status if validation fails")
def validate(ctx: click.Context, strict: bool) -> None:
    """Validate the indexed graph and report accuracy stats."""
    config = ctx.obj["config"]
    cp = CodePulse(config)
    report = cp.validate()
    click.echo(report.summary())
    if strict and not report.ok:
        sys.exit(1)


@cli.command()
@click.argument("manifest", type=click.Path(exists=True))
@click.option("--output", "-o", default="report.json", help="Output report path")
def validate_corpus(manifest: str, output: str) -> None:
    """Validate multiple repos against a corpus manifest."""
    from codepulse.batch import BatchValidator

    click.echo(f"Validating corpus from {manifest}...")
    validator = BatchValidator()
    report = validator.run(manifest, output)

    summary = report["summary"]
    click.echo(
        f"Total: {summary['total_repos']}, "
        f"Passed: {summary['total_passed']}, "
        f"Failed: {summary['total_failed']}"
    )
    click.echo(f"Report written to {output}")


@cli.command()
@click.argument("output", default=None, required=False)
@click.option("--format", "-f", "fmt", default="gexf", help="Export format: gexf")
@click.pass_context
def export(ctx: click.Context, output: str | None, fmt: str) -> None:
    """Export the graph to GEXF for visualization in Gephi Lite."""
    supported = {"gexf"}
    if fmt not in supported:
        supported_formats = ", ".join(sorted(supported))
        click.echo(f"Unsupported format '{fmt}'. Supported: {supported_formats}", err=True)
        sys.exit(1)

    config = ctx.obj["config"]
    cp = CodePulse(config)
    db = cp.db

    nodes = db.conn.execute("SELECT * FROM nodes ORDER BY name").fetchall()
    edges = db.conn.execute("SELECT * FROM edges").fetchall()

    _export_gexf(cp, output, nodes, edges)

@cli.command()
@click.argument("task")
@click.option("--max-nodes", "-m", default=30, help="Max nodes in context")
@click.pass_context
def context(ctx: click.Context, task: str, max_nodes: int) -> None:
    """Build a code context summary for a task."""
    config = ctx.obj["config"]
    cp = CodePulse(config)
    output = cp.build_context(task, max_nodes=max_nodes)
    click.echo(output)


@cli.command()
@click.option("--limit", "-l", default=25, help="Max files/symbols")
@click.pass_context
def repo_map(ctx: click.Context, limit: int) -> None:
    """Show a map of the codebase — top files and symbols."""
    config = ctx.obj["config"]
    cp = CodePulse(config)
    db = cp.db

    files = db.get_file_summary(limit=limit)
    symbols = db.get_top_symbols_with_context(limit=limit)

    lines = ["## Codebase Overview", ""]

    lines.append("### Top files")
    lines.append("| File | Symbols | References | Kinds |")
    lines.append("|---|---|---|---|")
    for f in files:
        name = Path(str(f["file"])).name
        lines.append(f"| {name} | {f['symbols']} | {f['edges']} | {f['kinds']} |")

    lines.append("")
    lines.append("### Top symbols")
    lines.append("| Symbol | Kind | File | Refs |")
    lines.append("|---|---|---|---|")
    for s in symbols:
        fname = Path(str(s["file"])).name
        lines.append(f"| {s['name']} | {s['kind']} | {fname}:{s['line']} | {s['refs']} |")

    click.echo("\n".join(lines))


@cli.command()
@click.argument("node_id")
@click.option("--source/--no-source", default=True, help="Include source code")
@click.pass_context
def node(ctx: click.Context, node_id: str, source: bool) -> None:
    """Get a single symbol's details."""
    config = ctx.obj["config"]
    cp = CodePulse(config)
    detail = cp.get_node(node_id, include_source=source)

    if detail is None:
        click.echo(f"Node '{node_id}' not found.")
        return

    n = detail.node
    click.echo(f"  {n.name} ({n.kind})")
    click.echo(f"  ID: {n.id}")
    click.echo(f"  {n.file_path}:{n.line_start}")
    if n.signature:
        click.echo(f"  {n.signature[:120]}")
    if detail.source:
        click.echo("---")
        click.echo(detail.source)


@cli.command()
@click.argument("file_path")
@click.pass_context
def file(ctx: click.Context, file_path: str) -> None:
    """View all symbols in a specific file."""
    config = ctx.obj["config"]
    cp = CodePulse(config)
    nodes = cp.db.get_nodes_by_file(file_path)

    if not nodes:
        click.echo(f"No symbols found in '{file_path}'.")
        return

    fname = Path(file_path).name
    click.echo(f"## Symbols in `{fname}`")
    click.echo("")
    click.echo("| Symbol | Kind | Line |")
    click.echo("|---|---|---|")
    for n in nodes:
        click.echo(f"| `{n.name}` | {n.kind} | {n.line_start} |")
    click.echo("")
    click.echo(f"_{len(nodes)} symbols_")


@cli.command(name="scan")
@click.argument("path", default=".")
@click.option("--watch", "-w", is_flag=True, help="Watch for changes and re-index")
@click.option("--use-scip", is_flag=True, help="Use SCIP indexer for accurate call graph")
@click.pass_context
def scan(ctx: click.Context, path: str, watch: bool, use_scip: bool) -> None:
    """Index all code files (alias for index)."""
    config = ctx.obj["config"]
    project_root = ctx.obj["project_root"]
    path_obj = Path(path)
    if not path_obj.is_absolute():
        path_obj = project_root / path
    resolved_path = str(path_obj.resolve())
    if use_scip:
        config.use_scip = True
    cp = CodePulse(config)
    result = cp.index_all(resolved_path)

    click.echo(f"Files indexed: {result.files_indexed}")
    click.echo(f"Symbols found: {result.symbols_found}")
    click.echo(f"Edges found: {result.edges_found}")
    if result.errors:
        for err in result.errors[:5]:
            click.echo(f"Error: {err}", err=True)

    if watch:
        click.echo(f"Watching {resolved_path} for changes...")
        w = FileWatcher(resolved_path, cp, debounce_ms=config.watch_debounce_ms)

        def on_index(msg: str) -> None:
            click.echo(msg)

        w.on_index = on_index
        try:
            w.start()
            import time as _time
            while True:
                _time.sleep(1)
        except KeyboardInterrupt:
            w.stop()
            click.echo("\nWatcher stopped.")


def _xml_escape(s: str) -> str:
    return s.replace("&", "&amp;").replace('"', "&quot;").replace("<", "&lt;").replace(">", "&gt;")


def _export_gexf(
    cp: "CodePulse", output: str, nodes: list | None = None, edges: list | None = None
) -> str:
    db = cp.db
    if nodes is None:
        nodes = db.conn.execute("SELECT * FROM nodes ORDER BY name").fetchall()
    if edges is None:
        edges = db.conn.execute("SELECT * FROM edges").fetchall()

    node_map = {}
    for i, n in enumerate(nodes):
        node_map[n["id"]] = f"n{i}"

    matched_edges = 0
    edge_xml = []
    for i, e in enumerate(edges):
        src = node_map.get(e["source_id"])
        tgt = node_map.get(e["target_id"])
        if not tgt:
            target_node = db.conn.execute(
                "SELECT id FROM nodes WHERE name = ? LIMIT 1", (e["target_id"],)
            ).fetchone()
            if target_node:
                tgt = node_map.get(target_node["id"])
        if not src:
            source_node = db.conn.execute(
                "SELECT id FROM nodes WHERE file_path = ? LIMIT 1", (e["source_id"],)
            ).fetchone()
            if source_node:
                src = node_map.get(source_node["id"])
        if src and tgt:
            ek = _xml_escape(e["kind"])
            edge_xml.append(f'    <edge id="{i}" source="{src}" target="{tgt}" label="{ek}"/>')
            matched_edges += 1

    lines = ['<?xml version="1.0" encoding="UTF-8"?>']
    lines.append('<gexf xmlns="http://gexf.net/1.3" version="1.3">')
    lines.append('<graph defaultedgetype="directed">')
    lines.append('  <attributes class="node">')
    lines.append('    <attribute id="kind" title="kind" type="string"/>')
    lines.append('    <attribute id="file" title="file" type="string"/>')
    lines.append('    <attribute id="line" title="line" type="integer"/>')
    lines.append('    <attribute id="language" title="language" type="string"/>')
    lines.append('  </attributes>')

    lines.append('  <nodes>')
    for n in nodes:
        sid = node_map[n["id"]]
        label_raw = n["name"]
        label = _xml_escape(label_raw.split(":")[-1] if ":" in label_raw else label_raw)[:80]
        kind = _xml_escape(n["kind"])
        file_ = _xml_escape(n["file_path"][:60])
        lang = _xml_escape(n["language"])
        lines.append(f'    <node id="{sid}" label="{label}">')
        lines.append('      <attvalues>')
        lines.append(f'        <attvalue for="kind" value="{kind}"/>')
        lines.append(f'        <attvalue for="file" value="{file_}"/>')
        lines.append(f'        <attvalue for="line" value="{n["line_start"]}"/>')
        lines.append(f'        <attvalue for="language" value="{lang}"/>')
        lines.append('      </attvalues>')
        lines.append('    </node>')
    lines.append('  </nodes>')

    lines.append('  <edges>')
    lines.extend(edge_xml)
    lines.append('  </edges>')

    lines.append('</graph>')
    lines.append('</gexf>')
    content = "\n".join(lines)

    if output:
        Path(output).write_text(content)
        click.echo(f"Exported {len(nodes)} nodes, {matched_edges} edges to {output}")
    else:
        click.echo(content)

    return content
