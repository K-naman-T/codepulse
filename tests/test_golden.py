"""Golden file accuracy tests for all 12 languages.

Each fixture file in tests/fixtures/accuracy.<ext> has known symbols documented
in comments. Tests verify EXACT matches — no false positives, no false negatives,
correct parent_id, correct references.

Also includes precision/recall/F1 threshold tests against the golden manifest.
"""

from pathlib import Path

import pytest
import yaml

from codepulse.parser import SourceParser
from codepulse.validation import compare_to_golden


FIXTURES = Path(__file__).parent / "fixtures"

LANG_EXT = {
    "go": ".go", "rust": ".rs", "python": ".py", "typescript": ".ts",
    "java": ".java", "ruby": ".rb", "php": ".php", "c": ".c", "cpp": ".cpp",
    "swift": ".swift", "kotlin": ".kt", "scala": ".scala",
}

ALLOWED_SYNTHETIC_KINDS = {"file", "external_module"}

GOLDEN = {
    "go": {
        "functions": ["NewConfig", "ParseInt", "HandleRequest", "init", "NewReader"],
        "methods": ["Config.Load", "Config.Validate", "Config.String", "Repository.Save", "Repository.Value"],
        "classes": ["Config", "Repository", "Reader"],
        "interfaces": [],
        "call_targets": ["ParseInt", "append", "len"],
        "method_parents": {"Config.Load": "Config", "Config.Validate": "Config", "Config.String": "Config", "Repository.Save": "Repository", "Repository.Value": "Repository"},
    },
    "rust": {
        "functions": ["create_user", "factorial", "run", "helper", "identity"],
        "methods": ["User.get_name", "User.is_active", "User.greet", "User.new"],
        "classes": ["User"],
        "interfaces": [],
        "call_targets": ["factorial", "create_user", "User.is_active", "User.greet", "identity"],
        "method_parents": {"User.get_name": "User", "User.is_active": "User", "User.greet": "User", "User.new": "User"},
    },
    "python": {
        "functions": ["create_user", "send_welcome_email", "format_date", "get_logger", "fetch_data", "outer_function", "inner_function"],
        "methods": ["User.__init__", "User.get_display_name", "User.save", "User.from_dict", "User.validate_email", "User.domain", "Logger.log", "AdminUser.get_display_name"],
        "classes": ["User", "AdminUser", "Logger"],
        "interfaces": [],
        "call_targets": ["Logger", "Logger.log", "User", "User.get_display_name", "User.save", "get_logger", "isoformat", "print", "send_email", "super", "upper", "cls", "split", "get", "json", "inner_function"],
        "method_parents": {"User.__init__": "User", "User.get_display_name": "User", "User.save": "User", "User.from_dict": "User", "User.validate_email": "User", "User.domain": "User", "Logger.log": "Logger", "AdminUser.get_display_name": "AdminUser"},
    },
    "typescript": {
        "functions": ["start", "connect", "initialize", "log", "demo"],
        "methods": ["Database.constructor", "Database.query", "UserService.constructor", "UserService.getFullName", "UserService.sendEmail", "ExportedClass.constructor", "ExportedClass.getValue", "DefaultClass.run"],
        "classes": ["Database", "UserService", "ExportedClass", "DefaultClass"],
        "interfaces": ["User", "Config"],
        "call_targets": ["connect", "log", "parseInt", "express", "start", "fetch", "Database.query", "listen", "ExportedClass", "ExportedClass.getValue"],
        "method_parents": {"Database.constructor": "Database", "Database.query": "Database", "UserService.constructor": "UserService", "UserService.getFullName": "UserService", "UserService.sendEmail": "UserService", "ExportedClass.constructor": "ExportedClass", "ExportedClass.getValue": "ExportedClass", "DefaultClass.run": "DefaultClass"},
    },
    "java": {
        "functions": ["draw"],
        "methods": ["Calculator.add", "Calculator.compute", "Circle.draw", "Circle.unit"],
        "classes": ["Calculator", "Circle"],
        "interfaces": ["Drawable"],
        "call_targets": ["Calculator.add", "println"],
        "method_parents": {"Calculator.add": "Calculator", "Calculator.compute": "Calculator", "Circle.draw": "Circle", "Circle.unit": "Circle"},
    },
    "ruby": {
        "functions": ["initialize", "greet", "hello", "demo", "helper"],
        "methods": [],
        "classes": ["Inner", "Greeter"],
        "interfaces": [],
        "call_targets": ["puts", "new", "greet", "helper", "hello"],
        "method_parents": {},
    },
    "php": {
        "functions": ["helper"],
        "methods": [],
        "classes": ["Logger", "Calculator"],
        "interfaces": [],
        "call_targets": ["\\strlen"],
        "method_parents": {},
    },
    "c": {
        "functions": ["make_point", "print_point", "double_x"],
        "methods": [],
        "classes": ["Point"],
        "interfaces": [],
        "call_targets": ["printf"],
        "method_parents": {},
    },
    "cpp": {
        "functions": ["create_counter", "run"],
        "methods": ["Counter.Counter"],
        "classes": ["Counter"],
        "interfaces": [],
        "call_targets": ["getValue", "create_counter"],
        "method_parents": {"Counter.Counter": "Counter"},
    },
    "swift": {
        "functions": ["create_car", "create_circle"],
        "methods": ["Car.drive", "Circle.draw", "Circle.unit"],
        "classes": ["Car", "Circle"],
        "interfaces": [],
        "call_targets": ["print", "Car", "Circle"],
        "method_parents": {"Car.drive": "Car", "Circle.draw": "Circle", "Circle.unit": "Circle"},
    },
    "kotlin": {
        "functions": ["main"],
        "methods": ["Calculator.add", "Drawable.draw", "Shape.area", "Circle.draw", "Circle.area", "Circle.unit"],
        "classes": ["Calculator", "Drawable", "Shape", "Circle"],
        "interfaces": [],
        "call_targets": ["println", "Calculator", "Circle"],
        "method_parents": {"Calculator.add": "Calculator", "Drawable.draw": "Drawable", "Shape.area": "Shape", "Circle.draw": "Circle", "Circle.area": "Circle", "Circle.unit": "Circle"},
    },
    "scala": {
        "functions": ["helper", "Main.run", "CircleFactory.unit", "demo"],
        "methods": ["Hello.greet", "Circle.draw", "Circle.area"],
        "classes": ["Hello", "Main", "Shape", "Circle", "CircleFactory"],
        "interfaces": ["Greeter", "Drawable"],
        "call_targets": ["println"],
        "method_parents": {"Hello.greet": "Hello", "Circle.draw": "Circle", "Circle.area": "Circle"},
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


def _name_from_id(node_id: str) -> str:
    """Extract symbol name from node ID (strip file path prefix before ':')."""
    return node_id.split(":")[-1]


class GoldenBase:
    LANG = ""

    @pytest.fixture
    def parsed(self, parser):
        return parse_golden(parser, self.LANG)

    def test_all_functions_found(self, parsed):
        syms, _ = parsed
        actual = {s.name for s in syms if s.kind == "function"}
        expected = set(self.GOLDEN["functions"])
        missing = expected - actual
        extras = actual - expected
        assert not missing, f"Missing functions: {missing}"
        assert not extras, f"Extra functions: {extras}"

    def test_all_methods_found(self, parsed):
        syms, _ = parsed
        actual = {s.name for s in syms if s.kind == "method"}
        expected = set(self.GOLDEN["methods"])
        missing = expected - actual
        extras = actual - expected
        assert not missing, f"Missing methods: {missing}"
        assert not extras, f"Extra methods: {extras}"

    def test_all_classes_found(self, parsed):
        syms, _ = parsed
        actual = {s.name for s in syms if s.kind == "class"}
        expected = set(self.GOLDEN.get("classes", []))
        missing = expected - actual
        extras = actual - expected
        assert not missing, f"Missing classes: {missing}"
        assert not extras, f"Extra classes: {extras}"

    def test_all_interfaces_found(self, parsed):
        syms, _ = parsed
        actual = {s.name for s in syms if s.kind == "interface"}
        expected = set(self.GOLDEN.get("interfaces", []))
        missing = expected - actual
        extras = actual - expected
        assert not missing, f"Missing interfaces: {missing}"
        assert not extras, f"Extra interfaces: {extras}"

    def test_methods_have_parent_class(self, parsed):
        syms, _ = parsed
        expected_parents = self.GOLDEN.get("method_parents", {})
        if not expected_parents:
            return
        all_ids = {s.id for s in syms}
        for s in syms:
            if s.kind == "method" and s.name in expected_parents:
                assert s.parent_id is not None, (
                    f"Method {s.name} has no parent_id"
                )
                assert s.parent_id in all_ids, (
                    f"Method {s.name} parent_id {s.parent_id} not found in parsed node IDs"
                )
                parent_name = _name_from_id(s.parent_id)
                expected = expected_parents[s.name]
                assert parent_name == expected, (
                    f"Method {s.name} parent should be {expected}, got {parent_name}"
                )

    def test_calls_detected(self, parsed):
        _, refs = parsed
        actual = {_name_from_id(r.target_id) for r in refs if r.kind == "calls"}
        expected = set(self.GOLDEN.get("call_targets", []))
        missing = expected - actual
        extras = actual - expected
        assert not missing, f"Missing call targets: {missing}"
        assert not extras, f"Extra call targets: {extras}"

    def test_no_empty_symbols(self, parsed):
        syms, _ = parsed
        empty = [s for s in syms if not s.name.strip()]
        assert not empty, "Found symbols with empty names"

    def test_all_symbols_have_line_numbers(self, parsed):
        syms, _ = parsed
        no_lines = [s for s in syms if s.kind not in ALLOWED_SYNTHETIC_KINDS and (s.line_start < 1 or s.line_end < 1)]
        assert not no_lines, f"Symbols without line numbers: {[s.name for s in no_lines]}"

    def test_no_false_positives(self, parsed):
        syms, _ = parsed
        known_kinds = {"function", "method", "class", "interface"} | ALLOWED_SYNTHETIC_KINDS
        for s in syms:
            assert s.kind in known_kinds, f"Unexpected kind '{s.kind}' for {s.name}"


class TestGoldenGo(GoldenBase):
    LANG = "go"
    GOLDEN = GOLDEN["go"]

class TestGoldenRust(GoldenBase):
    LANG = "rust"
    GOLDEN = GOLDEN["rust"]


class TestGoldenPython(GoldenBase):
    LANG = "python"
    GOLDEN = GOLDEN["python"]


class TestGoldenTypescript(GoldenBase):
    LANG = "typescript"
    GOLDEN = GOLDEN["typescript"]


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


# ---------------------------------------------------------------------------
# Precision / Recall / F1 threshold tests against the accuracy.yml manifest
# ---------------------------------------------------------------------------

HERE = Path(__file__).parent
GOLDEN_MANIFEST_PATH = HERE / "golden" / "accuracy.yml"


@pytest.fixture(scope="module")
def accuracy_manifest():
    with open(GOLDEN_MANIFEST_PATH) as f:
        return yaml.safe_load(f)


@pytest.fixture
def indexed_golden_db(db, accuracy_manifest):
    """Index the accuracy.py fixture into a fresh DB for comparison."""
    from codepulse.parser import SourceParser
    parser = SourceParser()
    fpath = FIXTURES / "accuracy.py"
    symbols, edges = parser.parse_file(str(fpath))
    db.bulk_import(symbols, edges)
    return db


class TestAccuracyGoldenThresholds:
    """Threshold assertions against the golden manifest for accuracy.py."""

    def test_symbols_precision(self, indexed_golden_db, accuracy_manifest):
        result = compare_to_golden(indexed_golden_db, accuracy_manifest)
        assert result.symbols.precision >= 0.98, (
            f"symbols precision {result.symbols.precision} < 0.98"
        )

    def test_symbols_recall(self, indexed_golden_db, accuracy_manifest):
        result = compare_to_golden(indexed_golden_db, accuracy_manifest)
        assert result.symbols.recall >= 0.98, (
            f"symbols recall {result.symbols.recall} < 0.98"
        )

    def test_calls_precision(self, indexed_golden_db, accuracy_manifest):
        result = compare_to_golden(indexed_golden_db, accuracy_manifest)
        assert result.calls.precision >= 0.90, (
            f"calls precision {result.calls.precision} < 0.90"
        )

    def test_calls_recall(self, indexed_golden_db, accuracy_manifest):
        result = compare_to_golden(indexed_golden_db, accuracy_manifest)
        assert result.calls.recall >= 0.85, (
            f"calls recall {result.calls.recall} < 0.85"
        )

    def test_imports_precision(self, indexed_golden_db, accuracy_manifest):
        result = compare_to_golden(indexed_golden_db, accuracy_manifest)
        assert result.imports.precision >= 0.95, (
            f"imports precision {result.imports.precision} < 0.95"
        )

    def test_imports_recall(self, indexed_golden_db, accuracy_manifest):
        result = compare_to_golden(indexed_golden_db, accuracy_manifest)
        assert result.imports.recall >= 0.95, (
            f"imports recall {result.imports.recall} < 0.95"
        )

    def test_parent_links_precision(self, indexed_golden_db, accuracy_manifest):
        result = compare_to_golden(indexed_golden_db, accuracy_manifest)
        assert result.parent_links.precision >= 0.98, (
            f"parent_links precision {result.parent_links.precision} < 0.98"
        )

    def test_parent_links_recall(self, indexed_golden_db, accuracy_manifest):
        result = compare_to_golden(indexed_golden_db, accuracy_manifest)
        assert result.parent_links.recall >= 0.98, (
            f"parent_links recall {result.parent_links.recall} < 0.98"
        )
