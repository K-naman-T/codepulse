"""Tests for multi-file and multi-language fixture projects.

Each fixture project exercises cross-file resolution, duplicate names,
relative imports, aliases, and mixed-language indexing.
"""

import shutil
from pathlib import Path

import pytest

from codepulse.compat.scip import is_scip_available
from codepulse.config import CodePulseConfig
from codepulse.graph import CodePulse

FIXTURES = Path(__file__).parent / "fixtures" / "projects"


def _index_project(src_dir, use_scip=False, tmp_path=None):
    """Copy fixture to tmp_path (to avoid side effects) and index."""
    if use_scip:
        dst = tmp_path / src_dir.name
        shutil.copytree(str(src_dir), str(dst))
        project_dir = dst
    else:
        project_dir = src_dir
    config = CodePulseConfig(
        data_dir=str(tmp_path / ".codepulse"),
        use_scip=use_scip,
    )
    cp = CodePulse(config)
    cp.index_all(str(project_dir))
    report = cp.validate()
    return cp, report


class TestPythonAppFixtures:
    """python_app fixture: models.py, services.py, main.py with relative imports."""

    PROJECT = FIXTURES / "python_app"

    def test_treesitter_zero_orphans(self, tmp_path):
        cp, report = _index_project(self.PROJECT, tmp_path=tmp_path)
        assert report.orphan_edges == 0, (
            f"python_app tree-sitter: {report.orphan_edges} orphan edges"
        )
        names = {r["name"] for r in cp.db.conn.execute("SELECT name FROM nodes").fetchall()}
        assert "User" in names, f"Missing User in {names}"
        assert "AdminUser" in names
        assert "Logger" in names
        assert "run" in names
        assert "create_user" in names
        cnt = cp.db.conn.execute(
            "SELECT COUNT(*) as c FROM nodes WHERE name LIKE '%.validate' OR name = 'validate'"
        ).fetchone()["c"]
        assert cnt >= 2, f"Expected >=2 validate symbols (models+services), got {cnt}"
        top_level_validates = cp.db.conn.execute(
            "SELECT COUNT(*) as c FROM nodes WHERE kind = 'function' AND name = 'validate'"
        ).fetchone()["c"]
        assert top_level_validates >= 2, (
            f"Expected same top-level validate() in two files, got {top_level_validates}"
        )

    @pytest.mark.skipif(not is_scip_available(), reason="scip CLI not installed")
    def test_scip_qualified_cross_file_targets(self, tmp_path):
        cp, report = _index_project(self.PROJECT, use_scip=True, tmp_path=tmp_path)
        assert report.orphan_edges == 0


class TestTypeScriptAppFixtures:
    """typescript_app fixture: src/models.ts, src/service.ts, src/index.ts."""

    PROJECT = FIXTURES / "typescript_app"

    def test_treesitter_zero_orphans(self, tmp_path):
        cp, report = _index_project(self.PROJECT, tmp_path=tmp_path)
        assert report.orphan_edges == 0, (
            f"typescript_app tree-sitter: {report.orphan_edges} orphan edges"
        )
        names = {r["name"] for r in cp.db.conn.execute("SELECT name FROM nodes").fetchall()}
        assert "UserService" in names, f"Missing UserService in {names}"
        assert "AdminService" in names
        assert "run" in names
        assert "export default" in (self.PROJECT / "src" / "service.ts").read_text()

    @pytest.mark.skipif(not is_scip_available(), reason="scip CLI not installed")
    def test_scip_qualified_cross_file_targets(self, tmp_path):
        cp, report = _index_project(self.PROJECT, use_scip=True, tmp_path=tmp_path)
        assert report.orphan_edges == 0
        scip_edges = cp.db.conn.execute(
            "SELECT target_id FROM edges WHERE provenance = 'scip' AND kind = 'calls'"
        ).fetchall()
        assert len(scip_edges) > 0, "Expected at least one SCIP call edge"
        targets = [r["target_id"] for r in scip_edges]
        dotted = [t for t in targets if "." in t or "#" in t]
        assert len(dotted) > 0, f"No qualified SCIP targets in {targets}"


class TestMixedStackFixtures:
    """mixed_stack fixture: Python backend + TypeScript frontend in one root."""

    PROJECT = FIXTURES / "mixed_stack"

    def test_treesitter_zero_orphans(self, tmp_path):
        cp, report = _index_project(self.PROJECT, tmp_path=tmp_path)
        assert report.orphan_edges == 0, (
            f"mixed_stack tree-sitter: {report.orphan_edges} orphan edges"
        )
        langs = {
            r["language"]
            for r in cp.db.conn.execute(
                "SELECT DISTINCT language FROM nodes WHERE language != ''"
            ).fetchall()
        }
        assert "python" in langs, f"Missing python language; got {langs}"
        assert "typescript" in langs, f"Missing typescript language; got {langs}"
