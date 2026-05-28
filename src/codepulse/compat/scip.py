"""SCIP indexer integration with JSON output parsing.

SCIP provides type-aware cross-file symbol resolution, fixing the
key accuracy gap: `obj.method()` resolves to `Helper.process` instead
of bare `process`.

Requires:
  - scip CLI (https://github.com/scip-code/scip)
  - Language-specific indexers:
    - @sourcegraph/scip-typescript (npm)
    - @sourcegraph/scip-python (npm)
"""

import json
import os
import subprocess
from pathlib import Path

from codepulse.db import GraphDB, Node, Edge
from codepulse.ids import symbol_node_id


def is_scip_available() -> bool:
    scip = _which("scip")
    if not scip:
        return False
    try:
        result = subprocess.run([scip, "--help"], capture_output=True, timeout=5)
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def _find_scip_indexer(project_root: str) -> list[str]:
    root = Path(project_root)
    has_ts_files = bool(list(root.rglob("*.ts")) + list(root.rglob("*.tsx")))
    has_py_files = bool(list(root.rglob("*.py")))
    has_ts_config = (root / "tsconfig.json").exists() or (root / "package.json").exists() or has_ts_files
    has_py_config = has_py_files

    indexers: list[str] = []
    if has_ts_config:
        ts_idx = _which("scip-typescript")
        if ts_idx:
            indexers.append(ts_idx)
    if has_py_config:
        py_idx = _which("scip-python")
        if py_idx:
            indexers.append(py_idx)
    return indexers


def _which(name: str) -> str | None:
    search_dirs = [
        Path(os.environ.get("HOME", "")) / ".local/bin",
        Path(os.environ.get("HOME", "")) / ".npm-global/bin",
        Path("/usr/local/bin"), Path("/usr/bin"),
    ]
    for d in search_dirs:
        c = d / name
        if c.exists():
            return str(c)
    try:
        r = subprocess.run(["which", name], capture_output=True, text=True, timeout=5)
        return r.stdout.strip() if r.returncode == 0 else None
    except Exception:
        return None


def index_with_scip(project_root: str, db: GraphDB) -> int:
    if not is_scip_available():
        raise RuntimeError("scip CLI not found")
    indexers = _find_scip_indexer(project_root)
    if not indexers:
        raise RuntimeError("No SCIP indexer found for this project")

    scip_output_dir = Path(project_root) / ".codepulse" / "scip"
    scip_output_dir.mkdir(parents=True, exist_ok=True)

    total_count = 0
    for indexer in indexers:
        lang = "python" if "scip-python" in indexer else "typescript"
        output_file = scip_output_dir / f"{lang}.scip"
        try:
            result = subprocess.run(
                [indexer, "index", "--output", str(output_file)],
                cwd=project_root, capture_output=True, text=True, timeout=300,
            )
            if result.returncode != 0:
                raise RuntimeError(f"Indexer {indexer} failed: {result.stderr[:500]}")
        except FileNotFoundError:
            raise RuntimeError(f"Indexer not found: {indexer}")

        if output_file.exists():
            total_count += _convert_scip_to_graph(str(output_file), db, project_root)

    return total_count


def _parse_scip_symbol(symbol: str) -> tuple[str, str | None]:
    if ".(" in symbol:
        return "", None
    if symbol.startswith("local") or not symbol:
        return "", None

    if "#" in symbol:
        parts = symbol.split("#", 1)
        base = parts[0].rsplit("/", 1)[-1].strip("`")
        rest = parts[1].replace("().", ".").rstrip(")")
        if rest and rest != ".":
            return f"{base}.{rest.rstrip('.')}", "method"
        return base, "class"

    if symbol.endswith("()."):
        return symbol[:-3].rsplit("/", 1)[-1].strip("`"), "function"
    if "()." in symbol:
        parts = symbol.rsplit("().", 1)
        return parts[0].rsplit("/", 1)[-1].strip("`"), "method"
    if "(" in symbol:
        return symbol.split("(")[0].rsplit("/", 1)[-1].strip("`"), "function"

    name = symbol.strip("`").rsplit("/", 1)[-1]
    return (name, "symbol") if name else ("", None)


def _detect_lang(file_path: str) -> str:
    ext = Path(file_path).suffix.lower()
    return {".py": "python", ".ts": "typescript", ".tsx": "typescript",
            ".js": "typescript", ".go": "go"}.get(ext, "")


def _convert_scip_to_graph(scip_path: str, db: GraphDB, project_root: str) -> int:
    try:
        r = subprocess.run(
            ["scip", "print", "--json", scip_path],
            capture_output=True, text=True, timeout=30,
        )
        if r.returncode != 0:
            raise RuntimeError(f"scip print failed: {r.stderr[:200]}")
    except FileNotFoundError:
        raise RuntimeError("scip CLI not found")

    data = json.loads(r.stdout)
    root = Path(project_root).resolve()
    count = 0

    symbol_to_node_id: dict[str, str] = {}
    reference_occurrences: list[tuple[str, str, str, int]] = []

    for doc in data.get("documents", []):
        rel_path = doc.get("relative_path", "")
        full_path = str(root / rel_path)
        language = _detect_lang(rel_path)

        for occ in doc.get("occurrences", []):
            symbol = occ.get("symbol", "")
            roles = occ.get("symbol_roles", 0)
            if not symbol or symbol.startswith("local "):
                continue

            if roles & 1:
                name, kind = _parse_scip_symbol(symbol)
                if not name or not kind:
                    continue
                node_id = symbol_node_id(full_path, name)
                symbol_to_node_id[symbol] = node_id
                existing = db.get_node(node_id)
                if not existing:
                    db.upsert_node(Node(
                        id=node_id, file_path=full_path,
                        name=name, kind=kind, language=language,
                    ))
                    count += 1
            elif roles == 0:
                reference_occurrences.append((symbol, rel_path, full_path, language))

        for sym_info in doc.get("symbols", []):
            symbol = sym_info.get("symbol", "")
            if not symbol or symbol.startswith("local "):
                continue
            name, kind = _parse_scip_symbol(symbol)
            if not name or not kind:
                continue
            if kind not in ("class", "interface", "function", "method"):
                continue
            node_id = symbol_node_id(full_path, name)
            symbol_to_node_id[symbol] = node_id
            if not db.get_node(node_id):
                db.upsert_node(Node(
                    id=node_id, file_path=full_path,
                    name=name, kind=kind, language=language,
                ))
                count += 1

    for symbol, rel_path, full_path, language in reference_occurrences:
        target_id = symbol_to_node_id.get(symbol)
        if not target_id:
            continue
        target_kind = ""
        target_node = db.get_node(target_id)
        if target_node:
            target_kind = target_node.kind

        edge_kind = "calls" if target_kind in ("function", "method") else "imports" if target_kind == "symbol" else "references"
        edge = Edge(
            source_id=full_path,
            target_id=target_id,
            kind=edge_kind,
            file_path=full_path,
        )
        db.upsert_edge(edge)
        count += 1

    return count
