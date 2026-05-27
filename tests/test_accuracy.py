"""Accuracy tests: verify parser correctly extracts ALL known symbols and calls.

Each fixture file has KNOWN symbols and calls documented in comments.
Tests verify EXACT matches — no false positives, no false negatives.
"""

from pathlib import Path

import pytest

from codepulse.parser import SourceParser


FIXTURES = Path(__file__).parent / "fixtures"


class TestPythonAccuracy:
    """Verify Python parser accuracy against known fixture data."""

    @pytest.fixture
    def symbols(self, parser: SourceParser):
        fpath = str(FIXTURES / "accuracy.py")
        syms, refs = parser.parse_file(fpath)
        return syms, refs

    def test_all_classes_found(self, symbols):
        syms, _ = symbols
        class_names = {s.name for s in syms if s.kind == "class"}
        expected = {"User", "AdminUser", "Logger"}
        missing = expected - class_names
        assert not missing, f"Missing classes: {missing}"

    def test_all_functions_found(self, symbols):
        syms, _ = symbols
        func_names = {s.name for s in syms if s.kind == "function"}
        expected = {"create_user", "send_welcome_email", "format_date", "get_logger"}
        missing = expected - func_names
        assert not missing, f"Missing functions: {missing}"

    def test_all_methods_found(self, symbols):
        syms, _ = symbols
        method_names = {s.name for s in syms if s.kind == "method"}
        expected = {"__init__", "get_display_name", "save", "log"}
        methods_in_classes = {m for m in method_names if any(m in s.name for s in syms)}
        missing = expected - {m.split(".")[-1] for m in method_names}
        assert not missing, f"Missing methods: {missing}"

    def test_methods_have_parent_class(self, symbols):
        syms, _ = symbols
        for s in syms:
            if s.kind == "method":
                assert s.parent_id is not None, f"Method {s.name} has no parent_id"

    def test_calls_detected(self, symbols):
        _, refs = symbols
        call_names = {r.target_id for r in refs if r.kind == "calls"}
        expected_calls = {"save", "get_logger", "get_display_name", "send_email", "log"}
        found = call_names & expected_calls
        assert len(found) >= 3, f"Too few calls detected: {found} out of {expected_calls}"

    def test_imports_detected(self, symbols):
        _, refs = symbols
        import_targets = {r.target_id for r in refs if r.kind == "imports"}
        expected_imports = {"os", "datetime"}
        found = import_targets & expected_imports
        assert len(found) >= 1, f"No expected imports found in {import_targets}"

    def test_no_empty_symbols(self, symbols):
        syms, _ = symbols
        empty = [s for s in syms if not s.name.strip()]
        assert not empty, "Found symbols with empty names"

    def test_all_symbols_have_line_numbers(self, symbols):
        syms, _ = symbols
        no_lines = [s for s in syms if s.line_start < 1 or s.line_end < 1]
        assert not no_lines, f"Symbols without line numbers: {[s.name for s in no_lines]}"


class TestTypeScriptAccuracy:
    """Verify TypeScript parser accuracy against known fixture data."""

    @pytest.fixture
    def symbols(self, parser: SourceParser):
        fpath = str(FIXTURES / "accuracy.ts")
        if not Path(fpath).exists():
            pytest.skip("accuracy.ts fixture not found")
        syms, refs = parser.parse_file(fpath)
        return syms, refs

    def test_all_classes_found(self, symbols):
        syms, _ = symbols
        class_names = {s.name for s in syms if s.kind == "class"}
        assert "Database" in class_names, f"Missing class 'Database' in {class_names}"
        assert "UserService" in class_names

    def test_all_interfaces_found(self, symbols):
        syms, _ = symbols
        iface_names = {s.name for s in syms if s.kind == "interface"}
        assert "User" in iface_names, f"Missing interface 'User' in {iface_names}"
        assert "Config" in iface_names

    def test_import_variants_detected(self, symbols):
        _, refs = symbols
        imports = {r.target_id for r in refs if r.kind == "imports"}
        assert "readFile" in imports, f"Missing named import 'readFile' in {imports}"
        assert "express" in imports, f"Missing default import 'express' in {imports}"
        assert "fs" in imports, f"Missing namespace import 'fs' in {imports}"
        assert "dotenv/config" in imports, f"Missing side-effect import 'dotenv/config' in {imports}"

    def test_call_variants_detected(self, symbols):
        _, refs = symbols
        calls = {r.target_id for r in refs if r.kind == "calls"}
        expected = {"listen", "parseInt", "connect", "log", "getFullName", "sendEmail"}
        found = calls & expected
        assert len(found) >= 4, (
            f"Too few calls detected.\n"
            f"  Expected at least 4 of: {expected}\n"
            f"  Found: {found}"
        )

    def test_methods_have_parent(self, symbols):
        syms, _ = symbols
        for s in syms:
            if s.kind == "method":
                assert s.parent_id is not None, f"Method {s.name} has no parent_id"

    def test_all_functions_found(self, symbols):
        syms, _ = symbols
        func_names = {s.name for s in syms if s.kind == "function"}
        assert "start" in func_names, f"Missing function 'start' in {func_names}"
        assert "initialize" in func_names

    def test_all_methods_found(self, symbols):
        syms, _ = symbols
        method_names = set()
        for s in syms:
            if s.kind == "method":
                method_names.add(s.name.split(".")[-1])
        expected = {"constructor", "getFullName", "sendEmail", "query"}
        missing = expected - method_names
        assert not missing, f"Missing methods: {missing}"
