"""Edge data model tests: verify call source/target IDs resolve to real node IDs."""

from pathlib import Path

from codepulse.parser import SourceParser


class TestEdgeModel:
    """Every call edge's source_id must point to the enclosing function's node ID."""

    def _assert_sources_resolve(self, fixture: str):
        p = SourceParser()
        fpath = str(Path(__file__).parent / "fixtures" / fixture)
        syms, refs = p.parse_file(fpath)
        node_ids = {s.id for s in syms}
        fails = []
        for r in refs:
            if r.kind != "calls":
                continue
            if r.source_id not in node_ids:
                fails.append(f"source_id={r.source_id!r} (line {r.line_number}) not in node IDs")
            if ":" not in r.target_id:
                fails.append(f"target_id={r.target_id!r} has no colon (bare name, not path:name)")
        assert not fails, "\n".join(fails)

    def test_go_source_resolves(self):
        self._assert_sources_resolve("accuracy.go")

    def test_rust_source_resolves(self):
        self._assert_sources_resolve("accuracy.rs")

    def test_python_source_resolves(self):
        self._assert_sources_resolve("accuracy.py")

    def test_typescript_source_resolves(self):
        self._assert_sources_resolve("accuracy.ts")

    def test_java_source_resolves(self):
        self._assert_sources_resolve("accuracy.java")

    def test_ruby_source_resolves(self):
        self._assert_sources_resolve("accuracy.rb")

    def test_php_source_resolves(self):
        self._assert_sources_resolve("accuracy.php")

    def test_c_source_resolves(self):
        self._assert_sources_resolve("accuracy.c")

    def test_cpp_source_resolves(self):
        self._assert_sources_resolve("accuracy.cpp")

    def test_swift_source_resolves(self):
        self._assert_sources_resolve("accuracy.swift")

    def test_kotlin_source_resolves(self):
        self._assert_sources_resolve("accuracy.kt")

    def test_scala_source_resolves(self):
        self._assert_sources_resolve("accuracy.scala")

    def test_source_id_is_not_file_path(self):
        """Ensure source_id is never a bare file path for call edges."""
        p = SourceParser()
        fpath = str(Path(__file__).parent / "fixtures" / "accuracy.py")
        _, refs = p.parse_file(fpath)
        for r in refs:
            if r.kind == "calls":
                assert ":" in r.source_id, f"source_id {r.source_id!r} looks like a file path"

    def test_same_file_calls_have_correct_targets(self):
        """For direct calls to known same-file functions, target should resolve to node ID."""
        p = SourceParser()
        fpath = str(Path(__file__).parent / "fixtures" / "accuracy.go")
        syms, refs = p.parse_file(fpath)
        node_ids = {s.id for s in syms}
        for r in refs:
            if r.kind == "calls" and r.target_id.endswith(":ParseInt"):
                assert r.target_id in node_ids, (
                    f"ParseInt should resolve to a node ID, got {r.target_id!r}"
                )
                assert r.source_id.endswith(":HandleRequest"), (
                    f"ParseInt call should be from HandleRequest, got {r.source_id!r}"
                )
                return
        assert False, "No call to ParseInt found"

    def test_target_id_has_path_prefix_for_same_file_calls(self):
        """Target IDs for same-file calls should be in path:name format."""
        p = SourceParser()
        fpath = str(Path(__file__).parent / "fixtures" / "accuracy.go")
        _, refs = p.parse_file(fpath)
        for r in refs:
            if r.kind == "calls":
                assert r.target_id.startswith("/"), (
                    f"target_id {r.target_id!r} should start with file path"
                )
                assert ":" in r.target_id, (
                    f"target_id {r.target_id!r} should have path:name format"
                )
