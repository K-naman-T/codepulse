"""Tests for batch validation of repos against a corpus manifest."""

import json
from pathlib import Path

import pytest
import yaml

from codepulse.batch import BatchValidator


HERE = Path(__file__).parent
FIXTURES = HERE / "fixtures"


class TestBatchValidator:
    def test_empty_manifest(self, tmp_path):
        manifest = {"repos": []}
        mpath = tmp_path / "empty.yml"
        mpath.write_text(yaml.dump(manifest))
        opath = tmp_path / "report.json"
        BatchValidator().run(str(mpath), str(opath))
        report = json.loads(opath.read_text())
        assert report["repos"] == []
        assert report["summary"]["total_repos"] == 0

    def test_manifest_not_found(self):
        with pytest.raises(FileNotFoundError):
            BatchValidator().run("/nonexistent/manifest.yml", "/tmp/out.json")

    def test_missing_required_fields(self, tmp_path):
        manifest = {"repos": [{"name": "test"}]}
        mpath = tmp_path / "bad.yml"
        mpath.write_text(yaml.dump(manifest))
        with pytest.raises(ValueError, match="required"):
            BatchValidator().run(str(mpath), str(tmp_path / "report.json"))

    def test_report_structure(self, tmp_path):
        manifest = {"repos": []}
        mpath = tmp_path / "struct.yml"
        mpath.write_text(yaml.dump(manifest))
        opath = tmp_path / "report.json"
        BatchValidator().run(str(mpath), str(opath))
        report = json.loads(opath.read_text())
        assert list(report.keys()) == ["summary", "repos"]
        assert "total_repos" in report["summary"]
        assert "total_passed" in report["summary"]
        assert "total_failed" in report["summary"]

    def test_local_project_validates_successfully(self, tmp_path):
        proj = FIXTURES / "projects" / "python_app"
        manifest = {
            "repos": [
                {
                    "name": "python_app",
                    "url": str(proj),
                    "commit": "local",
                    "language": "python",
                    "path": ".",
                    "use_scip": False,
                    "max_seconds": 30,
                    "min_symbols": 5,
                    "max_internal_orphans": 0,
                }
            ]
        }
        mpath = tmp_path / "python_app.yml"
        mpath.write_text(yaml.dump(manifest))
        opath = tmp_path / "report.json"
        BatchValidator().run(str(mpath), str(opath))
        report = json.loads(opath.read_text())
        assert len(report["repos"]) == 1
        entry = report["repos"][0]
        assert entry["name"] == "python_app"
        assert entry["passed"] is True
        assert entry["files_indexed"] >= 1
        assert entry["symbols_found"] >= 5
        assert entry["duration_seconds"] > 0
        assert entry["error"] is None

    def test_min_symbols_threshold_causes_failure(self, tmp_path):
        proj = FIXTURES / "projects" / "python_app"
        manifest = {
            "repos": [
                {
                    "name": "python_app",
                    "url": str(proj),
                    "commit": "local",
                    "language": "python",
                    "path": ".",
                    "use_scip": False,
                    "max_seconds": 30,
                    "min_symbols": 999999,
                    "max_internal_orphans": 0,
                }
            ]
        }
        mpath = tmp_path / "min_fail.yml"
        mpath.write_text(yaml.dump(manifest))
        opath = tmp_path / "min_fail_report.json"
        BatchValidator().run(str(mpath), str(opath))
        report = json.loads(opath.read_text())
        entry = report["repos"][0]
        assert entry["passed"] is False

    def test_max_internal_orphans_threshold_causes_failure(self, tmp_path):
        proj = FIXTURES / "projects" / "python_app"
        manifest = {
            "repos": [
                {
                    "name": "python_app",
                    "url": str(proj),
                    "commit": "local",
                    "language": "python",
                    "path": ".",
                    "use_scip": False,
                    "max_seconds": 30,
                    "min_symbols": 5,
                    "max_internal_orphans": -1,
                }
            ]
        }
        mpath = tmp_path / "orphan_fail.yml"
        mpath.write_text(yaml.dump(manifest))
        opath = tmp_path / "orphan_fail_report.json"
        BatchValidator().run(str(mpath), str(opath))
        report = json.loads(opath.read_text())
        entry = report["repos"][0]
        assert entry["passed"] is False

    def test_max_seconds_threshold_causes_failure(self, tmp_path):
        proj = FIXTURES / "projects" / "python_app"
        manifest = {
            "repos": [
                {
                    "name": "python_app",
                    "url": str(proj),
                    "commit": "local",
                    "language": "python",
                    "path": ".",
                    "use_scip": False,
                    "max_seconds": -1,
                    "min_symbols": 5,
                    "max_internal_orphans": 0,
                }
            ]
        }
        mpath = tmp_path / "time_fail.yml"
        mpath.write_text(yaml.dump(manifest))
        opath = tmp_path / "time_fail_report.json"
        BatchValidator().run(str(mpath), str(opath))
        report = json.loads(opath.read_text())
        entry = report["repos"][0]
        assert entry["passed"] is False

    def test_manifest_path_populates_precision(self, tmp_path):
        proj = FIXTURES / "projects" / "python_app"
        golden = {
            "symbols": [
                {
                    "id_suffix": "User",
                    "name": "User",
                    "kind": "class",
                    "file": "models.py",
                    "line_start": 1,
                    "line_end": 10,
                }
            ],
            "edges": [],
            "allowed_external": [],
        }
        golden_path = tmp_path / "golden.yml"
        golden_path.write_text(yaml.dump(golden))
        manifest = {
            "repos": [
                {
                    "name": "python_app",
                    "url": str(proj),
                    "commit": "local",
                    "language": "python",
                    "path": ".",
                    "use_scip": False,
                    "max_seconds": 30,
                    "min_symbols": 5,
                    "max_internal_orphans": 0,
                    "manifest_path": str(golden_path),
                }
            ]
        }
        mpath = tmp_path / "with_precision.yml"
        mpath.write_text(yaml.dump(manifest))
        opath = tmp_path / "with_precision_report.json"
        BatchValidator().run(str(mpath), str(opath))
        report = json.loads(opath.read_text())
        entry = report["repos"][0]
        assert entry["precision"] is not None

    def test_cli_validate_corpus(self, tmp_path, cli_runner):
        proj = FIXTURES / "projects" / "python_app"
        manifest = {
            "repos": [
                {
                    "name": "python_app",
                    "url": str(proj),
                    "commit": "local",
                    "language": "python",
                    "path": ".",
                    "use_scip": False,
                    "max_seconds": 30,
                    "min_symbols": 5,
                    "max_internal_orphans": 0,
                }
            ]
        }
        mpath = tmp_path / "cli_test.yml"
        mpath.write_text(yaml.dump(manifest))
        opath = tmp_path / "cli_report.json"
        from codepulse.cli import cli
        result = cli_runner.invoke(cli, ["validate-corpus", str(mpath), "--output", str(opath)])
        assert result.exit_code == 0
        report = json.loads(opath.read_text())
        assert report["summary"]["total_repos"] == 1
        entry = report["repos"][0]
        assert entry["passed"] is True
