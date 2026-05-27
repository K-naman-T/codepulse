from pathlib import Path
from typing import Any

import yaml
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class CodePulseConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="CODEPULSE_",
        env_nested_delimiter="__",
        extra="ignore",
    )

    data_dir: str = "~/.codepulse"
    log_level: str = "INFO"

    languages: list[str] = Field(
        default_factory=lambda: ["python", "typescript", "go"]
    )
    use_codegraph: bool = True
    use_scip: bool = False

    watch_debounce_ms: int = 500
    watch_extensions: list[str] = Field(default_factory=list)

    mcp_max_context_nodes: int = 30

    @property
    def db_path(self) -> str:
        return str(Path(self.data_dir).expanduser() / "graph.db")

    @property
    def config_dir(self) -> Path:
        return Path(self.data_dir).expanduser()

    def ensure_data_dir(self) -> Path:
        path = self.config_dir
        path.mkdir(parents=True, exist_ok=True)
        return path

    @classmethod
    def load(cls, path: str | None = None) -> "CodePulseConfig":
        import os as _os
        prefix = cls.model_config.get("env_prefix", "")
        env_overrides = {
            key: _os.environ.get(f"{prefix}{key.upper()}")
            for key in cls.model_fields
            if f"{prefix}{key.upper()}" in _os.environ
        }
        file_data: dict[str, Any] = {}
        if path and Path(path).exists():
            with open(path) as f:
                file_data = yaml.safe_load(f) or {}
        merged = {**file_data, **env_overrides}
        if merged:
            return cls(**merged)
        return cls()
