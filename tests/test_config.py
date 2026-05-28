import os
from pathlib import Path

import pytest
import yaml

from codepulse.config import CodePulseConfig


class TestConfigDefaults:
    def test_default_values(self):
        config = CodePulseConfig()
        assert config.data_dir == "~/.codepulse"

    def test_db_path_interpolation(self):
        config = CodePulseConfig(data_dir="/tmp/test")
        assert "{data_dir}" not in config.db_path
        assert config.db_path == "/tmp/test/graph.db"

    def test_parser_languages_default(self):
        config = CodePulseConfig()
        assert "python" in config.languages


class TestConfigLoading:
    def test_load_from_file(self, tmp_path: Path):
        cfg_path = tmp_path / "config.yml"
        cfg_path.write_text(yaml.dump({"data_dir": "/tmp/custom"}))
        config = CodePulseConfig.load(str(cfg_path))
        assert config.data_dir == "/tmp/custom"

    def test_missing_file_returns_defaults(self):
        config = CodePulseConfig.load("/nonexistent/path/config.yml")
        assert config.data_dir == "~/.codepulse"

    def test_invalid_yaml_raises(self, tmp_path: Path):
        cfg_path = tmp_path / "bad.yml"
        cfg_path.write_text("{invalid: yaml: broken}")
        with pytest.raises(Exception):
            CodePulseConfig.load(str(cfg_path))


class TestConfigHelpers:
    def test_ensure_data_dir_creates(self, tmp_path: Path):
        config = CodePulseConfig(data_dir=str(tmp_path / "newdir"))
        path = config.ensure_data_dir()
        assert path.exists()
        assert path.is_dir()

    def test_ensure_data_dir_exists(self, tmp_path: Path):
        (tmp_path / "exists").mkdir()
        config = CodePulseConfig(data_dir=str(tmp_path / "exists"))
        path = config.ensure_data_dir()
        assert path.exists()


class TestConfigProjectDiscovery:
    def test_load_for_project_uses_dot_codepulse(self, tmp_path: Path):
        project = tmp_path / "myproject"
        project.mkdir()
        (project / ".codepulse").mkdir()
        config = CodePulseConfig.load_for_project(path=str(project))
        expected = (project / ".codepulse").resolve()
        assert Path(config.data_dir).resolve() == expected

    def test_load_for_project_fallback(self, tmp_path: Path):
        config = CodePulseConfig.load_for_project(
            path=str(tmp_path / "nonexistent")
        )
        assert config.data_dir == "~/.codepulse"

    def test_load_for_project_no_path_returns_default(self):
        config = CodePulseConfig.load_for_project()
        assert config.data_dir == "~/.codepulse"

    def test_load_for_project_preserves_env_overrides(self, tmp_path: Path, monkeypatch):
        project = tmp_path / "myproject"
        project.mkdir()
        (project / ".codepulse").mkdir()
        monkeypatch.setenv("CODEPULSE_LOG_LEVEL", "DEBUG")
        config = CodePulseConfig.load_for_project(path=str(project))
        assert config.log_level == "DEBUG"
        expected = (project / ".codepulse").resolve()
        assert Path(config.data_dir).resolve() == expected

    def test_codepulse_data_dir_overrides_project(self, tmp_path: Path, monkeypatch):
        project = tmp_path / "myproject"
        project.mkdir()
        (project / ".codepulse").mkdir()
        custom_data_dir = tmp_path / "custom_data"
        custom_data_dir.mkdir()
        monkeypatch.setenv("CODEPULSE_DATA_DIR", str(custom_data_dir))
        config = CodePulseConfig.load_for_project(path=str(project))
        assert Path(config.data_dir).resolve() == custom_data_dir.resolve()
