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
