from pathlib import Path

import pytest
from click.testing import CliRunner, Result

from codepulse.cli import cli


class TestCLI:
    @pytest.fixture
    def runner(self) -> CliRunner:
        return CliRunner()

    def test_init_creates_config(self, runner: CliRunner, tmp_path: Path):
        project = tmp_path / "testproj"
        project.mkdir()
        result = runner.invoke(cli, ["init", "--path", str(project)])
        assert result.exit_code == 0
        config_dir = project / ".codepulse"
        assert config_dir.exists()

    def test_index_cli(self, runner: CliRunner, sample_project: Path):
        result = runner.invoke(cli, ["--data-dir", str(sample_project / ".codepulse"), "index", str(sample_project / "src")])
        assert result.exit_code == 0
        assert "files indexed" in result.output.lower() or "Indexing complete" in result.output or "indexed" in result.output.lower()

    def test_search_cli(self, runner: CliRunner, sample_project: Path):
        data_dir = sample_project / ".codepulse"
        runner.invoke(cli, ["--data-dir", str(data_dir), "index", str(sample_project / "src")])
        result = runner.invoke(cli, ["--data-dir", str(data_dir), "search", "UserModel"])
        assert result.exit_code == 0
        assert "UserModel" in result.output

    def test_search_empty_results(self, runner: CliRunner, sample_project: Path):
        data_dir = sample_project / ".codepulse"
        runner.invoke(cli, ["--data-dir", str(data_dir), "index", str(sample_project / "src")])
        result = runner.invoke(cli, ["--data-dir", str(data_dir), "search", "nonexistent_symbol_xyz"])
        assert result.exit_code == 0

    def test_search_kind_filter(self, runner: CliRunner, sample_project: Path):
        data_dir = sample_project / ".codepulse"
        runner.invoke(cli, ["--data-dir", str(data_dir), "index", str(sample_project / "src")])
        result = runner.invoke(cli, ["--data-dir", str(data_dir), "search", "UserModel", "--kind", "class"])
        assert result.exit_code == 0
        assert "UserModel" in result.output

    def test_help_shows_product_name(self, runner: CliRunner):
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "Usage: codepulse" in result.output
        assert ".codepulse" in result.output

    def test_error_on_no_index(self, runner: CliRunner, tmp_path: Path):
        result = runner.invoke(cli, ["--data-dir", str(tmp_path / ".codepulse"), "search", "foo"])
        assert result.exit_code == 0

    def test_callers_cli(self, runner: CliRunner, sample_project: Path):
        data_dir = sample_project / ".codepulse"
        runner.invoke(cli, ["--data-dir", str(data_dir), "index", str(sample_project / "src")])
        sample_py = str((sample_project / "src" / "sample.py").resolve())
        result = runner.invoke(cli, ["--data-dir", str(data_dir), "callers", f"{sample_py}:calculate_total"])
        assert result.exit_code == 0

    def test_callees_cli(self, runner: CliRunner, sample_project: Path):
        data_dir = sample_project / ".codepulse"
        runner.invoke(cli, ["--data-dir", str(data_dir), "index", str(sample_project / "src")])
        sample_py = str((sample_project / "src" / "sample.py").resolve())
        result = runner.invoke(cli, ["--data-dir", str(data_dir), "callees", f"{sample_py}:UserModel"])
        assert result.exit_code == 0

    def test_trace_cli(self, runner: CliRunner, sample_project: Path):
        data_dir = sample_project / ".codepulse"
        runner.invoke(cli, ["--data-dir", str(data_dir), "index", str(sample_project / "src")])
        sample_py = str((sample_project / "src" / "sample.py").resolve())
        result = runner.invoke(cli, ["--data-dir", str(data_dir), "trace", f"{sample_py}:UserModel", "--depth", "2"])
        assert result.exit_code == 0

    def test_init_no_path(self, runner: CliRunner, tmp_path: Path):
        project = tmp_path / "noproj"
        project.mkdir()
        result = runner.invoke(cli, ["init"], standalone_mode=False)
        assert result.exit_code == 0

    def test_version_shows_version(self, runner: CliRunner):
        result = runner.invoke(cli, ["--version"])
        assert result.exit_code == 0
        assert "0.1.0" in result.output

    def test_serve_command_exists(self, runner: CliRunner):
        result = runner.invoke(cli, ["serve", "--help"])
        assert result.exit_code == 0
        assert "MCP" in result.output or "serve" in result.output
