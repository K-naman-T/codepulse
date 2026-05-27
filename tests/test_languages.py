"""Comprehensive language tests: verify ALL supported languages parse correctly.

Each language must parse a minimal fixture and return at least one symbol.
This ensures grammars load, queries match, and the pipeline works end-to-end.
"""

import tempfile
from pathlib import Path

import pytest

from codepulse.parser import SourceParser


# Each entry: (extension, code, min_symbols, expected_kinds)
LANGUAGE_FIXTURES = [
    (".py", "def foo(): pass\nclass Bar: pass\n", 2, {"function", "class"}),
    (".ts", "function foo(): void {}\nclass Bar {}\n", 2, {"function", "class"}),
    (".tsx", "function foo(): void {}\nclass Bar {}\n", 2, {"function", "class"}),
    (".js", "function foo() {}\nclass Bar {}\n", 2, {"function", "class"}),
    (".go", "func foo() {}\ntype Bar struct {}\n", 2, {"function", "class"}),
    (".java", "class Foo { void bar() { } }\n", 2, {"class", "method"}),
    (".rs", "fn foo() {}\nstruct Bar { x: i32 }\n", 2, {"function", "class"}),
    (".rb", "class Foo; def bar; end; end\n", 2, {"class", "function"}),
    (".php", "<?php function foo() {} class Bar {}\n", 2, {"function", "class"}),
    (".c", "int foo() { return 1; }\nstruct Bar { int x; };\n", 2, {"function", "class"}),
    (".cpp", "void foo() {}\nclass Bar { int x; };\n", 2, {"function", "class"}),
    (".swift", "func foo() {}\nclass Bar {}\n", 2, {"function", "class"}),
    (".kt", "fun foo(): Unit {}\nclass Bar {}\n", 2, {"function", "class"}),
    (".scala", "def foo(): Unit = {}\nclass Bar\n", 2, {"function", "class"}),
]


class TestAllLanguages:
    @pytest.fixture(scope="class")
    def parser(self):
        return SourceParser()

    @pytest.mark.parametrize("ext,code,min_symbols,expected_kinds", LANGUAGE_FIXTURES)
    def test_language_parses(self, parser: SourceParser, ext: str, code: str, min_symbols: int, expected_kinds: set):
        with tempfile.NamedTemporaryFile(suffix=ext, delete=False, mode="w") as f:
            f.write(code)
            fpath = f.name
        try:
            symbols, refs = parser.parse_file(fpath)
            kinds = {s.kind for s in symbols}
            assert len(symbols) >= min_symbols, (
                f"{ext}: expected >= {min_symbols} symbols, got {len(symbols)}: {[s.name for s in symbols]}"
            )
            for k in expected_kinds:
                assert k in kinds, (
                    f"{ext}: expected kind '{k}' in {kinds}"
                )
        finally:
            import os
            os.unlink(fpath)

    def test_all_extensions_mapped(self):
        """Every test fixture extension must map to a language."""
        from codepulse.parser import _EXTENSION_MAP
        for ext, _, _, _ in LANGUAGE_FIXTURES:
            assert ext in _EXTENSION_MAP, f"Missing extension mapping: {ext}"

    def test_unsupported_extension_returns_empty(self, parser: SourceParser):
        with tempfile.NamedTemporaryFile(suffix=".xyz", delete=False, mode="w") as f:
            f.write("whatever")
            fpath = f.name
        try:
            symbols, refs = parser.parse_file(fpath)
            assert symbols == []
            assert refs == []
        finally:
            import os
            os.unlink(fpath)

    def test_empty_file_returns_empty(self, parser: SourceParser):
        with tempfile.NamedTemporaryFile(suffix=".py", delete=False, mode="w") as f:
            f.write("")
            fpath = f.name
        try:
            symbols, refs = parser.parse_file(fpath)
            assert symbols == []
            assert refs == []
        finally:
            import os
            os.unlink(fpath)
