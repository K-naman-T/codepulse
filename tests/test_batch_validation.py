"""Tests for batch validation of repos against a corpus manifest."""

import json
import shutil
import subprocess
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
            BatchValidator().run("/nonexistent/manifest.yml", "unused.json")

    def test_missing_required_fields(self, tmp_path):
        manifest = {"repos": [{"name": "test"}]}
        mpath = tmp_path / "bad.yml"
        mpath.write_text(yaml.dump(manifest))
        with pytest.raises(ValueError, match="required"):
            BatchValidator().run(str(mpath), str(tmp_path / "report.json"))

    def test_invalid_field_type_rejected(self, tmp_path):
        proj = FIXTURES / "projects" / "python_app"
        manifest = {
            "repos": [
                {
                    "name": "python_app",
                    "url": str(proj),
                    "commit": "local",
                    "language": "python",
                    "path": ".",
                    "use_scip": "false",
                    "max_seconds": 30,
                    "min_symbols": 5,
                    "max_internal_orphans": 0,
                }
            ]
        }
        mpath = tmp_path / "bad_type.yml"
        mpath.write_text(yaml.dump(manifest))
        with pytest.raises(ValueError, match="use_scip"):
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

    def test_missing_manifest_path_fails_entry(self, tmp_path):
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
                    "manifest_path": str(tmp_path / "missing.yml"),
                }
            ]
        }
        mpath = tmp_path / "missing_precision.yml"
        mpath.write_text(yaml.dump(manifest))
        opath = tmp_path / "missing_precision_report.json"
        BatchValidator().run(str(mpath), str(opath))
        report = json.loads(opath.read_text())
        entry = report["repos"][0]
        assert entry["passed"] is False
        assert "Golden manifest not found" in entry["error"]

    def test_pinned_local_git_repo_does_not_mutate_original_checkout(self, tmp_path):
        if shutil.which("git") is None:
            pytest.skip("git not installed")
        repo = tmp_path / "repo"
        repo.mkdir()
        subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
        (repo / "app.py").write_text("def first():\n    return 1\n")
        subprocess.run(["git", "add", "app.py"], cwd=repo, check=True, capture_output=True)
        subprocess.run(
            [
                "git",
                "-c",
                "user.name=Test",
                "-c",
                "user.email=test@example.com",
                "commit",
                "-m",
                "first",
            ],
            cwd=repo, check=True, capture_output=True,
        )
        first_commit = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=repo, check=True, capture_output=True, text=True,
        ).stdout.strip()
        (repo / "app.py").write_text("def second():\n    return 2\n")
        subprocess.run(["git", "add", "app.py"], cwd=repo, check=True, capture_output=True)
        subprocess.run(
            [
                "git",
                "-c",
                "user.name=Test",
                "-c",
                "user.email=test@example.com",
                "commit",
                "-m",
                "second",
            ],
            cwd=repo, check=True, capture_output=True,
        )
        original_head = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=repo, check=True, capture_output=True, text=True,
        ).stdout.strip()

        manifest = {
            "repos": [
                {
                    "name": "local_git_repo",
                    "url": str(repo),
                    "commit": first_commit,
                    "language": "python",
                    "path": ".",
                    "use_scip": False,
                    "max_seconds": 30,
                    "min_symbols": 1,
                    "max_internal_orphans": 0,
                }
            ]
        }
        mpath = tmp_path / "git_manifest.yml"
        mpath.write_text(yaml.dump(manifest))
        BatchValidator().run(str(mpath), str(tmp_path / "git_report.json"))
        current_head = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=repo, check=True, capture_output=True, text=True,
        ).stdout.strip()
        assert current_head == original_head

    def test_invalid_local_git_commit_fails_entry(self, tmp_path):
        if shutil.which("git") is None:
            pytest.skip("git not installed")
        repo = tmp_path / "repo"
        repo.mkdir()
        subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
        (repo / "app.py").write_text("def only():\n    return 1\n")
        subprocess.run(["git", "add", "app.py"], cwd=repo, check=True, capture_output=True)
        subprocess.run(
            [
                "git",
                "-c",
                "user.name=Test",
                "-c",
                "user.email=test@example.com",
                "commit",
                "-m",
                "only",
            ],
            cwd=repo, check=True, capture_output=True,
        )
        original_head = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=repo, check=True, capture_output=True, text=True,
        ).stdout.strip()

        manifest = {
            "repos": [
                {
                    "name": "bad_commit_repo",
                    "url": str(repo),
                    "commit": "deadbeef",
                    "language": "python",
                    "path": ".",
                    "use_scip": False,
                    "max_seconds": 30,
                    "min_symbols": 1,
                    "max_internal_orphans": 0,
                }
            ]
        }
        mpath = tmp_path / "bad_commit.yml"
        mpath.write_text(yaml.dump(manifest))
        opath = tmp_path / "bad_commit_report.json"
        BatchValidator().run(str(mpath), str(opath))
        report = json.loads(opath.read_text())
        entry = report["repos"][0]
        assert entry["passed"] is False
        assert "checkout commit deadbeef" in entry["error"]
        current_head = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=repo, check=True, capture_output=True, text=True,
        ).stdout.strip()
        assert current_head == original_head

    def test_temp_directories_are_cleaned_up(self, tmp_path, monkeypatch):
        import tempfile

        original_mkdtemp = tempfile.mkdtemp
        created: list[Path] = []

        def tracked_mkdtemp(*args, **kwargs):
            kwargs["dir"] = str(tmp_path)
            path = Path(original_mkdtemp(*args, **kwargs))
            created.append(path)
            return str(path)

        monkeypatch.setattr(tempfile, "mkdtemp", tracked_mkdtemp)
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
        mpath = tmp_path / "cleanup.yml"
        mpath.write_text(yaml.dump(manifest))
        BatchValidator().run(str(mpath), str(tmp_path / "cleanup_report.json"))
        assert created
        assert all(not path.exists() for path in created)

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
