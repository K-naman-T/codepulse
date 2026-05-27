"""Adapter for xnuinside/codegraph Python dependency analysis.

Provides Python-specific dependency graph using codegraph's tokenizer
and entity resolution, converted to our Node/Edge schema.

Requires: pip install codegraph
"""

from pathlib import Path

from codepulse.db import Node, Edge

try:
    from codegraph.core import CodeGraph as CGCodeGraph
    from argparse import Namespace

    _HAS_CODEGRAPH = True
except ImportError:
    _HAS_CODEGRAPH = False


def is_available() -> bool:
    return _HAS_CODEGRAPH


def parse_with_codegraph(file_paths: list[str]) -> tuple[list[Node], list[Edge]]:
    """Parse Python files using codegraph and convert to our schema.

    Returns (symbols, edges) compatible with our parser output.
    """
    if not _HAS_CODEGRAPH:
        raise ImportError("codegraph is not installed. Run: pip install codegraph")

    args = Namespace(paths=file_paths)
    cg = CGCodeGraph(args)
    usage_graph = cg.usage_graph()
    entity_metadata = cg.get_entity_metadata()

    symbols: list[Node] = []
    edges: list[Edge] = []
    seen: set[str] = set()

    for file_path, entities in entity_metadata.items():
        for entity_name, meta in entities.items():
            node_id = f"{file_path}:{entity_name}"
            if node_id in seen:
                continue
            seen.add(node_id)

            sym = Node(
                id=node_id,
                file_path=str(Path(file_path).resolve()),
                name=entity_name,
                kind=meta.get("entity_type", "symbol"),
                line_start=meta.get("lineno", 0),
                line_end=meta.get("endno", 0),
                language="python",
            )
            symbols.append(sym)

    for file_path, deps in usage_graph.items():
        source_prefix = str(Path(file_path).resolve())
        for entity_name, targets in deps.items():
            source_id = f"{source_prefix}:{entity_name}" if entity_name != "_" else source_prefix
            for target in targets:
                target_str = str(target) if not isinstance(target, str) else target
                edges.append(Edge(
                    source_id=source_id,
                    target_id=target_str,
                    kind="imports" if "." in target_str else "calls",
                    file_path=source_prefix,
                ))

    return symbols, edges
