import importlib
from importlib.resources import files
from pathlib import Path
from typing import Any

import yaml
from tree_sitter import Language, Parser, Query, QueryCursor

from codepulse.db import Node, Edge
from codepulse.ids import file_node_id, symbol_node_id, external_node_id

_DEFINITION_NODE_TYPES = frozenset({
    "function_definition", "async_function_definition", "method_definition",
    "class_definition", "class_declaration", "class_specifier",
    "interface_declaration", "struct_definition", "struct_specifier",
    "trait_definition", "object_definition", "function_declaration",
    "method_declaration", "function_item", "struct_item",
    "protocol_declaration", "type_spec", "method", "class", "module",
})


def _find_definition_parent(node) -> Any:
    p = node.parent
    while p.parent and p.type not in _DEFINITION_NODE_TYPES:
        p = p.parent
    return p

_EXTENSION_MAP: dict[str, str] = {
    ".py": "python",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".js": "typescript",
    ".jsx": "typescript",
    ".go": "go",
    ".java": "java",
    ".rs": "rust",
    ".rb": "ruby",
    ".php": "php",
    ".c": "c",
    ".h": "c",
    ".cpp": "cpp",
    ".hpp": "cpp",
    ".cc": "cpp",
    ".cxx": "cpp",
    ".swift": "swift",
    ".kt": "kotlin",
    ".kts": "kotlin",
    ".scala": "scala",
    ".sc": "scala",
}

_PARSERS_DIR = Path(str(files("codepulse.parsers")))


def _load_grammar(grammar_module: str, grammar_function: str | None = None) -> Language:
    mod = importlib.import_module(grammar_module)
    if grammar_function:
        return Language(getattr(mod, grammar_function)())
    return Language(mod.language())


def _load_config(language: str, parsers_dir: str | None = None) -> dict[str, Any]:
    dir_path = Path(parsers_dir) if parsers_dir else _PARSERS_DIR
    cfg_path = dir_path / f"{language}.yml"
    if not cfg_path.exists():
        raise FileNotFoundError(f"No parser config for {language}: {cfg_path}")
    with open(cfg_path) as f:
        return yaml.safe_load(f)


class SourceParser:
    def __init__(self, parsers_dir: str | None = None):
        self._parsers_dir = str(parsers_dir) if parsers_dir else str(_PARSERS_DIR)
        self._grammars: dict[str, Language] = {}
        self._parsers: dict[str, Parser] = {}
        self._configs: dict[str, dict[str, Any]] = {}
        self._queries: dict[str, dict[str, Query]] = {}

    def _ensure_language(self, language: str) -> None:
        if language in self._grammars:
            return
        config = _load_config(language, self._parsers_dir)
        self._configs[language] = config
        grammar = _load_grammar(config["grammar"], config.get("grammar_function"))
        self._grammars[language] = grammar
        self._parsers[language] = Parser(grammar)
        self._queries[language] = {}
        for name, pattern in config.get("queries", {}).items():
            self._queries[language][name] = Query(grammar, pattern)

    def detect_language(self, file_path: str) -> str | None:
        ext = Path(file_path).suffix.lower()
        return _EXTENSION_MAP.get(ext)

    def parse_file(self, file_path: str) -> tuple[list[Node], list[Edge]]:
        language = self.detect_language(file_path)
        if language is None:
            return [], []
        self._ensure_language(language)
        config = self._configs[language]
        queries = self._queries[language]

        with open(file_path, "rb") as f:
            source = f.read()

        parser = self._parsers[language]
        tree = parser.parse(source)
        root = tree.root_node
        lines = source.decode("utf-8").split("\n")
        rel_path = str(Path(file_path).resolve())

        symbols: list[Node] = []
        refs: list[Edge] = []
        seen_symbols: set[str] = set()
        external_ids: set[str] = set()

        file_node_id_val = file_node_id(rel_path)
        symbols.append(Node(
            id=file_node_id_val,
            file_path=rel_path,
            name=rel_path,
            kind="file",
            line_start=1,
            line_end=1,
            language=language,
        ))

        node_types = config.get("node_types", {})

        symbol_ranges: list[tuple[str, int, int]] = []
        call_sites: list[tuple[str, int]] = []

        for query_name, query in queries.items():
            cursor = QueryCursor(query)
            captures = cursor.captures(root)

            for capture_name, nodes in captures.items():
                for node in nodes:
                    if query_name in (
                        "function_definition", "async_function_definition",
                        "class_definition", "method_definition",
                        "interface_declaration", "struct_definition",
                        "trait_definition", "object_definition",
                    ):
                        if capture_name != "name":
                            continue
                        parent_type = node.parent.type
                        kind = node_types.get(parent_type, "function" if "function" in query_name else "symbol")
                        if kind == "function" and parent_type in ("method_definition",):
                            kind = "method"
                        elif kind == "function":
                            in_class = False
                            check = node.parent.parent
                            while check:
                                if check.type in ("class_definition", "class_declaration", "class_body", "class_specifier", "struct_specifier", "impl_item"):
                                    in_class = True
                                    break
                                check = check.parent
                            if in_class:
                                kind = "method"
                        name = lines[node.start_point[0]][node.start_point[1]:node.end_point[1]]
                        def_node = _find_definition_parent(node)

                        parent_id = None
                        p = def_node.parent
                        while p:
                            if p.type in ("class_definition", "class_declaration", "object_definition", "class_specifier", "struct_specifier"):
                                pname_field = p.child_by_field_name("name")
                                if pname_field:
                                    pname = lines[pname_field.start_point[0]][pname_field.start_point[1]:pname_field.end_point[1]]
                                    parent_id = symbol_node_id(rel_path, pname)
                                break
                            if p.type == "impl_item":
                                type_field = p.child_by_field_name("type")
                                if type_field:
                                    pname = lines[type_field.start_point[0]][type_field.start_point[1]:type_field.end_point[1]]
                                    parent_id = symbol_node_id(rel_path, pname)
                                break
                            p = p.parent

                        if parent_id is None and def_node.type == "method_declaration":
                            receiver = def_node.child_by_field_name("receiver")
                            if receiver:
                                for child in receiver.children:
                                    if child.type == "parameter_declaration":
                                        type_node = child.child_by_field_name("type")
                                        if type_node:
                                            if type_node.type == "pointer_type":
                                                for child in type_node.children:
                                                    if child.type != "*":
                                                        type_node = child
                                                        break
                                            pname = lines[type_node.start_point[0]][type_node.start_point[1]:type_node.end_point[1]]
                                            bracket_pos = pname.find('[')
                                            if bracket_pos >= 0:
                                                pname = pname[:bracket_pos]
                                            parent_id = symbol_node_id(rel_path, pname)
                                        break

                        full_name = f"{pname}.{name}" if parent_id else name
                        node_id = symbol_node_id(rel_path, full_name)
                        dedup_key = f"{node_id}:{kind}"
                        if dedup_key in seen_symbols:
                            continue
                        seen_symbols.add(dedup_key)

                        sig_start = def_node.start_point[0]
                        sig_end = def_node.end_point[0]
                        sig_lines = lines[sig_start:sig_end + 1]
                        sig_text = " ".join(s.strip() for s in sig_lines if s.strip())

                        sym = Node(
                            id=node_id,
                            file_path=rel_path,
                            name=full_name,
                            kind=kind,
                            signature=sig_text[:500],
                            line_start=def_node.start_point[0] + 1,
                            line_end=def_node.end_point[0] + 1,
                            parent_id=parent_id,
                            language=language,
                        )
                        symbols.append(sym)
                        symbol_ranges.append((node_id, sym.line_start, sym.line_end))

                    elif query_name.startswith("import_"):
                        if capture_name in ("name", "module", "source"):
                            text = lines[node.start_point[0]][node.start_point[1]:node.end_point[1]]
                            if capture_name == "source":
                                text = text.strip("'\"") if text else text
                            if not text:
                                continue
                            ext_id = external_node_id("module", text)
                            if ext_id not in external_ids:
                                external_ids.add(ext_id)
                                symbols.append(Node(
                                    id=ext_id,
                                    file_path=rel_path,
                                    name=text,
                                    kind="external_module",
                                    line_start=1,
                                    line_end=1,
                                    language=language,
                                ))
                            refs.append(Edge(
                                source_id=file_node_id_val,
                                target_id=ext_id,
                                kind="imports",
                                file_path=rel_path,
                                line_number=node.start_point[0] + 1,
                            ))

                    elif query_name.startswith("call_") or query_name in ("call", "call_expression"):
                        if capture_name == "name":
                            text = lines[node.start_point[0]][node.start_point[1]:node.end_point[1]]
                            call_sites.append((text, node.start_point[0] + 1))

        # Build bare-name → node_id map (first occurrence wins for same-name symbols).
        # Sort by source position so resolution is deterministic regardless of
        # tree-sitter capture iteration order.
        sorted_syms = sorted(
            (s for s in symbols if s.kind not in ("file", "external_module")),
            key=lambda s: (s.line_start, s.line_end),
        )
        name_to_id: dict[str, str] = {}
        for sym in sorted_syms:
            bare = sym.name.split(".")[-1]
            if bare not in name_to_id:
                name_to_id[bare] = sym.id

        # Resolve call edges: find enclosing function and target node.
        # Sort by source position so resolution is deterministic regardless of
        # tree-sitter capture iteration order.
        symbol_ranges.sort(key=lambda x: (x[1], x[2], x[0]))
        for target_text, line in call_sites:
            source_id = file_node_id_val
            for sym_id, s_start, s_end in reversed(symbol_ranges):
                if s_start <= line <= s_end:
                    source_id = sym_id
                    break
            target_id = name_to_id.get(target_text, symbol_node_id(rel_path, target_text))
            refs.append(Edge(
                source_id=source_id,
                target_id=target_id,
                kind="calls",
                file_path=rel_path,
                line_number=line,
            ))

        return symbols, refs


def _parse_files_worker(file_paths: list[str]) -> list[tuple[str, list[Node], list[Edge], str | None]]:
    sp = SourceParser()
    results = []
    for fp in file_paths:
        try:
            symbols, edges = sp.parse_file(fp)
            results.append((fp, symbols, edges, None))
        except Exception as e:
            results.append((fp, [], [], str(e)))
    return results
