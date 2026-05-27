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
    config = CodePulseConfig.load()
    if data_dir:
        config.data_dir = data_dir
    ctx.obj["config"] = config


@cli.command()
@click.option("--path", default=".", help="Project path")
@click.pass_context
def init(ctx: click.Context, path: str) -> None:
    """Initialize a project for code graph indexing."""
    config = ctx.obj["config"]
    target = Path(path).resolve()
    config.data_dir = str(target / ".codepulse")
    cp = CodePulse(config)
    cp.init_project()
    click.echo(f"Initialized in {config.config_dir}")


@cli.command()
@click.argument("path", default=".")
@click.option("--watch", "-w", is_flag=True, help="Watch for changes and re-index")
@click.option("--use-scip", is_flag=True, help="Use SCIP indexer for accurate call graph")
@click.pass_context
def index(ctx: click.Context, path: str, watch: bool, use_scip: bool) -> None:
    """Index all code files to build the graph."""
    config = ctx.obj["config"]
    if use_scip:
        config.use_scip = True
    cp = CodePulse(config)
    result = cp.index_all(path)

    click.echo(f"Files indexed: {result.files_indexed}")
    click.echo(f"Symbols found: {result.symbols_found}")
    click.echo(f"Edges found: {result.edges_found}")
    if result.errors:
        for err in result.errors[:5]:
            click.echo(f"Error: {err}", err=True)

    if watch:
        click.echo(f"Watching {path} for changes...")
        w = FileWatcher(path, cp, debounce_ms=config.watch_debounce_ms)

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
@click.argument("node_id")
@click.option("--depth", "-d", default=3, help="Impact depth")
@click.pass_context
def trace(ctx: click.Context, node_id: str, depth: int) -> None:
    """Show impact radius of a symbol."""
    config = ctx.obj["config"]
    cp = CodePulse(config)
    impact = cp.get_impact_radius(node_id, depth=depth)

    if not impact:
        click.echo("No impact found.")
        return

    for level, nodes in sorted(impact.items()):
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
@click.pass_context
def analyze(ctx: click.Context, url: str, token: str | None, branch: str | None) -> None:
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
    result = cp.index_all(repo_path)
    click.echo(f"Files indexed: {result.files_indexed}")
    click.echo(f"Symbols found: {result.symbols_found}")
    click.echo(f"Edges found: {result.edges_found}")

    click.echo("")
    click.echo("You can now:")
    click.echo(f"  codepulse search    — search symbols")
    click.echo(f"  codepulse mcp       — start MCP server for AI agents")
    click.echo(f"  codepulse validate  — graph statistics")
    click.echo(f"  cd web && npm run dev  — web dashboard")


@cli.command()
@click.pass_context
def mcp(ctx: click.Context) -> None:
    """Start MCP server over stdio for AI agent integration."""
    from codepulse.mcp_server import main as mcp_main
    mcp_main()


@cli.command()
@click.pass_context
def validate(ctx: click.Context) -> None:
    """Validate the indexed graph and report accuracy stats."""
    config = ctx.obj["config"]
    cp = CodePulse(config)
    report = cp.validate()
    click.echo(report.summary())


@cli.command()
@click.pass_context
def serve(ctx: click.Context) -> None:
    """Start MCP server over stdio for AI agent integration."""
    from codepulse.mcp import CodePulseMCPServer

    config = ctx.obj["config"]
    cp = CodePulse(config)
    server = CodePulseMCPServer(cp)

    import sys as _sys

    for line in _sys.stdin:
        if not line.strip():
            continue
        parts = line.strip().split(maxsplit=1)
        cmd = parts[0] if parts else ""
        args = parts[1] if len(parts) > 1 else ""

        if cmd == "search":
            result = server.search_symbols(args)
        elif cmd == "callers":
            result = server.get_callers(args)
        elif cmd == "impact":
            result = server.get_impact_radius(args)
        elif cmd == "context":
            result = server.find_code(args)
        elif cmd == "similar":
            result = server.search_similar(args)
        elif cmd == "ping":
            result = "pong"
        else:
            result = f"unknown: {cmd}"

        _sys.stdout.write(result + "\n---\n")
        _sys.stdout.flush()
