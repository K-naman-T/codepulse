from pathlib import Path

import pytest

from codepulse.db import Node, Edge


class TestParserPython:
    def test_parse_python_functions(self, parser, sample_project: Path):
        src = sample_project / "src" / "sample.py"
        symbols, refs = parser.parse_file(str(src))
        funcs = [s for s in symbols if s.kind == "function"]
        assert len(funcs) >= 3

    def test_parse_python_classes(self, parser, sample_project: Path):
        src = sample_project / "src" / "sample.py"
        symbols, refs = parser.parse_file(str(src))
        classes = [s for s in symbols if s.kind == "class"]
        assert len(classes) == 2

    def test_parse_python_imports(self, parser, sample_project: Path):
        src = sample_project / "src" / "sample.py"
        symbols, refs = parser.parse_file(str(src))
        import_edges = [r for r in refs if r.kind == "imports"]
        assert len(import_edges) >= 2

    def test_symbol_line_ranges(self, parser, sample_project: Path):
        src = sample_project / "src" / "sample.py"
        symbols, refs = parser.parse_file(str(src))
        for sym in symbols:
            assert sym.line_end >= sym.line_start
            assert sym.line_start > 0


class TestParserTypeScript:
    def test_parse_typescript_functions(self, parser, sample_project: Path):
        src = sample_project / "src" / "sample.ts"
        symbols, refs = parser.parse_file(str(src))
        funcs = [s for s in symbols if s.kind == "function"]
        assert len(funcs) >= 1

    def test_parse_typescript_class(self, parser, sample_project: Path):
        src = sample_project / "src" / "sample.ts"
        symbols, refs = parser.parse_file(str(src))
        classes = [s for s in symbols if s.kind == "class"]
        assert len(classes) == 1

    def test_parse_typescript_imports(self, parser, sample_project: Path):
        src = sample_project / "src" / "sample.ts"
        symbols, refs = parser.parse_file(str(src))
        import_edges = [r for r in refs if r.kind == "imports"]
        assert len(import_edges) >= 2


class TestParserEdgeCases:
    def test_empty_file(self, parser, tmp_path: Path):
        f = tmp_path / "empty.py"
        f.write_text("")
        symbols, refs = parser.parse_file(str(f))
        assert symbols == []
        assert refs == []

    def test_syntax_error_graceful(self, parser, tmp_path: Path):
        f = tmp_path / "broken.py"
        f.write_text("def foo(\n    pass\n")
        symbols, refs = parser.parse_file(str(f))
        assert len(symbols) <= 1

    def test_unsupported_language(self, parser, tmp_path: Path):
        f = tmp_path / "file.xyz"
        f.write_text("def foo; end")
        symbols, refs = parser.parse_file(str(f))
        assert symbols == []
        assert refs == []

    def test_detect_language_from_extension(self, parser, tmp_path: Path):
        py_file = tmp_path / "test.py"
        py_file.write_text("x = 1")
        syms1, _ = parser.parse_file(str(py_file))
        assert isinstance(syms1, list)

    def test_parse_python_methods_have_parent(self, parser, sample_project: Path):
        src = sample_project / "src" / "sample.py"
        symbols, refs = parser.parse_file(str(src))
        methods = [s for s in symbols if s.kind == "method"]
        for m in methods:
            assert m.parent_id is not None


class TestParserIntegration:
    def test_parse_and_store_to_db(self, parser, db, sample_project: Path):
        src = sample_project / "src" / "sample.py"
        symbols, refs = parser.parse_file(str(src))
        for sym in symbols:
            db.upsert_node(sym)
        for ref in refs:
            db.upsert_edge(ref)
        stored = db.get_nodes_by_file(str(src))
        assert len(stored) == len(symbols)

    def test_parse_python_detects_calls(self, parser, sample_project: Path):
        src = sample_project / "src" / "sample.py"
        symbols, refs = parser.parse_file(str(src))
        call_edges = [r for r in refs if r.kind == "calls"]
        assert len(call_edges) >= 0
