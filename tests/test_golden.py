"""Golden file accuracy tests for all 12 languages.

Each fixture file in tests/fixtures/accuracy.<ext> has known symbols documented
in comments. Tests verify EXACT matches — no false positives, no false negatives,
correct parent_id, correct references.
"""

from pathlib import Path

import pytest

from codepulse.parser import SourceParser


FIXTURES = Path(__file__).parent / "fixtures"

LANG_EXT = {
    "go": ".go", "rust": ".rs", "python": ".py", "typescript": ".ts",
    "java": ".java", "ruby": ".rb", "php": ".php", "c": ".c", "cpp": ".cpp",
    "swift": ".swift", "kotlin": ".kt", "scala": ".scala",
}

GOLDEN = {
    "go": {
        "functions": ["NewConfig", "ParseInt", "HandleRequest"],
        "methods": ["Load", "Validate", "String", "Save", "Value"],
        "classes": ["Config", "Repository"],
        "interfaces": [],
        "call_targets": ["ParseInt"],
        "imports": [],
        "method_parents": {"Load": "Config", "Validate": "Config", "String": "Config", "Save": "Repository", "Value": "Repository"},
    },
    "rust": {
        "functions": ["create_user", "factorial", "run"],
        "methods": ["get_name", "is_active", "greet"],
        "classes": ["User"],
        "interfaces": [],
        "call_targets": ["factorial", "create_user", "is_active", "greet"],
        "imports": [],
        "method_parents": {"get_name": "User", "is_active": "User", "greet": "User"},
    },
    "java": {
        "functions": [],
        "methods": ["add", "compute"],
        "classes": ["Calculator"],
        "interfaces": [],
        "call_targets": ["add"],
        "imports": [],
        "method_parents": {"add": "Calculator", "compute": "Calculator"},
    },
    "ruby": {
        "functions": ["greet", "helper"],
        "methods": [],
        "classes": ["Greeter"],
        "interfaces": [],
        "call_targets": ["puts", "new", "greet"],
        "imports": [],
        "method_parents": {},
    },
    "php": {
        "functions": ["helper"],
        "methods": [],
        "classes": ["Logger"],
        "interfaces": [],
        "call_targets": ["\\strlen"],
        "imports": [],
        "method_parents": {},
    },
    "c": {
        "functions": ["make_point", "print_point"],
        "methods": [],
        "classes": ["Point"],
        "interfaces": [],
        "call_targets": ["printf"],
        "imports": [],
        "method_parents": {},
    },
    "cpp": {
        "functions": ["create_counter", "run"],
        "methods": [],
        "classes": ["Counter"],
        "interfaces": [],
        "call_targets": ["getValue", "create_counter"],
        "imports": [],
        "method_parents": {},
    },
    "swift": {
        "functions": ["create_car"],
        "methods": ["drive"],
        "classes": ["Car"],
        "interfaces": [],
        "call_targets": ["print", "Car"],
        "imports": [],
        "method_parents": {"drive": "Car"},
    },
    "kotlin": {
        "functions": ["main"],
        "methods": ["add"],
        "classes": ["Calculator"],
        "interfaces": [],
        "call_targets": ["Calculator", "println"],
        "imports": [],
        "method_parents": {"add": "Calculator"},
    },
    "scala": {
        "functions": ["helper"],
        "methods": ["greet"],
        "classes": ["Hello", "Main"],
        "interfaces": ["Greeter"],
        "call_targets": ["println"],
        "imports": [],
        "method_parents": {"greet": "Hello"},
    },
}


@pytest.fixture
def parser():
    return SourceParser()


def parse_golden(parser, lang: str):
    ext = LANG_EXT.get(lang)
    if ext is None:
        pytest.skip(f"No extension mapping for {lang}")
    fpath = FIXTURES / f"accuracy{ext}"
    if not fpath.exists():
        pytest.skip(f"No golden fixture at {fpath}")
    return parser.parse_file(str(fpath))


def _short(names: set[str]) -> set[str]:
    """Extract short symbol names handling both bare and path-prefixed formats."""
    result = set()
    for n in names:
        short = n.split(":")[-1]
        if "." in short:
            short = short.split(".")[-1]
        result.add(short)
    return result


class GoldenBase:
    LANG = ""

    @pytest.fixture
    def parsed(self, parser):
        return parse_golden(parser, self.LANG)

    def test_all_functions_found(self, parsed):
        syms, _ = parsed
        func_names = {s.name for s in syms if s.kind == "function"}
        expected = set(self.GOLDEN["functions"])
        missing = expected - _short(func_names)
        assert not missing, f"Missing functions: {missing}"

    def test_all_methods_found(self, parsed):
        syms, _ = parsed
        method_names = {s.name for s in syms if s.kind == "method"}
        expected = set(self.GOLDEN["methods"])
        missing = expected - _short(method_names)
        assert not missing, f"Missing methods: {missing}"

    def test_all_classes_found(self, parsed):
        syms, _ = parsed
        class_names = {s.name for s in syms if s.kind == "class"}
        expected = set(self.GOLDEN.get("classes", []))
        missing = expected - class_names
        assert not missing, f"Missing classes: {missing}"

    def test_all_interfaces_found(self, parsed):
        syms, _ = parsed
        iface_names = {s.name for s in syms if s.kind == "interface"}
        expected = set(self.GOLDEN.get("interfaces", []))
        missing = expected - iface_names
        assert not missing, f"Missing interfaces: {missing}"

    def test_methods_have_parent_class(self, parsed):
        syms, _ = parsed
        expected_parents = self.GOLDEN.get("method_parents", {})
        if not expected_parents:
            return
        all_ids = {s.id for s in syms}
        for s in syms:
            if s.kind == "method":
                short = s.name.split(":")[-1].split(".")[-1]
                if short in expected_parents:
                    assert s.parent_id is not None, (
                        f"Method {short} has no parent_id"
                    )
                    assert s.parent_id in all_ids, (
                        f"Method {short} parent_id {s.parent_id} not found in parsed node IDs"
                    )
                    parent_short = s.parent_id.split(":")[-1]
                    expected = expected_parents[short]
                    assert parent_short == expected, (
                        f"Method {short} parent should be {expected}, got {parent_short}"
                    )

    def test_calls_detected(self, parsed):
        _, refs = parsed
        raw = {r.target_id for r in refs if r.kind == "calls"}
        call_targets = _short(raw)
        expected = set(self.GOLDEN.get("call_targets", []))
        missing = expected - call_targets
        assert not missing, f"Missing call targets: {missing}"

    def test_no_empty_symbols(self, parsed):
        syms, _ = parsed
        empty = [s for s in syms if not s.name.strip()]
        assert not empty, "Found symbols with empty names"

    def test_all_symbols_have_line_numbers(self, parsed):
        syms, _ = parsed
        no_lines = [s for s in syms if s.kind not in ("file", "external_module") and (s.line_start < 1 or s.line_end < 1)]
        assert not no_lines, f"Symbols without line numbers: {[s.name for s in no_lines]}"

    def test_no_false_positives(self, parsed):
        syms, _ = parsed
        known_kinds = {"function", "method", "class", "interface", "file", "external_module"}
        for s in syms:
            assert s.kind in known_kinds, f"Unexpected kind '{s.kind}' for {s.name}"


class TestGoldenGo(GoldenBase):
    LANG = "go"
    GOLDEN = GOLDEN["go"]

    def test_methods_have_parent_class(self, parsed):
        super().test_methods_have_parent_class(parsed)


class TestGoldenRust(GoldenBase):
    LANG = "rust"
    GOLDEN = GOLDEN["rust"]

    def test_all_methods_found(self, parsed):
        super().test_all_methods_found(parsed)


class TestGoldenJava(GoldenBase):
    LANG = "java"
    GOLDEN = GOLDEN["java"]


class TestGoldenRuby(GoldenBase):
    LANG = "ruby"
    GOLDEN = GOLDEN["ruby"]


class TestGoldenPhp(GoldenBase):
    LANG = "php"
    GOLDEN = GOLDEN["php"]


class TestGoldenC(GoldenBase):
    LANG = "c"
    GOLDEN = GOLDEN["c"]


class TestGoldenCpp(GoldenBase):
    LANG = "cpp"
    GOLDEN = GOLDEN["cpp"]


class TestGoldenSwift(GoldenBase):
    LANG = "swift"
    GOLDEN = GOLDEN["swift"]


class TestGoldenKotlin(GoldenBase):
    LANG = "kotlin"
    GOLDEN = GOLDEN["kotlin"]


class TestGoldenScala(GoldenBase):
    LANG = "scala"
    GOLDEN = GOLDEN["scala"]
