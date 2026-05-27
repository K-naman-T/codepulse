import importlib
from pathlib import Path
from typing import Any

import yaml
from tree_sitter import Language, Parser, Query, QueryCursor

from codepulse.db import Node, Edge

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

_PARSERS_DIR = Path(__file__).resolve().parent.parent.parent / "parsers"


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
        self._configs: dict[str, dict[str, Any]] = {}
        self._queries: dict[str, dict[str, Query]] = {}

    def _ensure_language(self, language: str) -> None:
        if language in self._grammars:
            return
        config = _load_config(language, self._parsers_dir)
        self._configs[language] = config
        grammar = _load_grammar(config["grammar"], config.get("grammar_function"))
        self._grammars[language] = grammar
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

        parser = Parser(self._grammars[language])
        tree = parser.parse(source)
        root = tree.root_node
        lines = source.decode("utf-8").split("\n")
        rel_path = str(Path(file_path).resolve())

        symbols: list[Node] = []
        refs: list[Edge] = []
        seen_symbols: set[str] = set()

        node_types = config.get("node_types", {})
        import_res = config.get("import_resolution", {})

        for query_name, query in queries.items():
            cursor = QueryCursor(query)
            captures = cursor.captures(root)

            for capture_name, nodes in captures.items():
                for node in nodes:
                    if query_name in (
                        "function_definition", "async_function_definition",
                        "class_definition", "method_definition",
                        "interface_declaration", "struct_definition",
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
                                if check.type in ("class_definition", "class_declaration", "class_body"):
                                    in_class = True
                                    break
                                check = check.parent
                            if in_class:
                                kind = "method"
                        name = lines[node.start_point[0]][node.start_point[1]:node.end_point[1]]
                        parent_node = node.parent

                        parent_id = None
                        p = parent_node.parent
                        while p:
                            if p.type in ("class_definition", "class_declaration"):
                                pname_field = p.child_by_field_name("name")
                                if pname_field:
                                    pname = lines[pname_field.start_point[0]][pname_field.start_point[1]:pname_field.end_point[1]]
                                    parent_id = f"{rel_path}:{pname}"
                                break
                            p = p.parent

                        full_name = f"{parent_id}.{name}" if parent_id else name
                        node_id = f"{rel_path}:{full_name}"
                        if node_id in seen_symbols:
                            continue
                        seen_symbols.add(node_id)

                        sig_start = parent_node.start_point[0]
                        sig_end = parent_node.end_point[0]
                        sig_lines = lines[sig_start:sig_end + 1]
                        sig_text = " ".join(s.strip() for s in sig_lines if s.strip())

                        sym = Node(
                            id=node_id,
                            file_path=rel_path,
                            name=full_name,
                            kind=kind,
                            signature=sig_text[:500],
                            line_start=parent_node.start_point[0] + 1,
                            line_end=parent_node.end_point[0] + 1,
                            parent_id=parent_id,
                            language=language,
                        )
                        symbols.append(sym)

                    elif query_name.startswith("import_"):
                        if capture_name == "name":
                            text = lines[node.start_point[0]][node.start_point[1]:node.end_point[1]]
                            refs.append(Edge(
                                source_id=rel_path,
                                target_id=text,
                                kind="imports",
                                file_path=rel_path,
                                line_number=node.start_point[0] + 1,
                            ))
                        elif capture_name == "source":
                            text = lines[node.start_point[0]][node.start_point[1]:node.end_point[1]]
                            refs.append(Edge(
                                source_id=rel_path,
                                target_id=text.strip("'\"") if text else text,
                                kind="imports",
                                file_path=rel_path,
                                line_number=node.start_point[0] + 1,
                            ))

                    elif query_name.startswith("call_") or query_name in ("call", "call_expression"):
                        if capture_name == "name":
                            text = lines[node.start_point[0]][node.start_point[1]:node.end_point[1]]
                            refs.append(Edge(
                                source_id=rel_path,
                                target_id=text,
                                kind="calls",
                                file_path=rel_path,
                                line_number=node.start_point[0] + 1,
                            ))

        return symbols, refs
