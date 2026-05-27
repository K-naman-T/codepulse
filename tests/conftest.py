from pathlib import Path
from typing import AsyncGenerator, Generator

import pytest
import yaml

from codepulse.config import CodePulseConfig
from codepulse.db import GraphDB


@pytest.fixture
def temp_dir(tmp_path: Path) -> Path:
    return tmp_path


@pytest.fixture
def sample_project(tmp_path: Path) -> Path:
    project = tmp_path / "sample_project"
    project.mkdir()
    src = project / "src"
    src.mkdir()
    (src / "__init__.py").write_text("")
    fixture_dir = Path(__file__).parent / "fixtures"
    for fname in ["sample.py", "sample.ts"]:
        content = (fixture_dir / fname).read_text()
        (src / fname).write_text(content)
    return project


@pytest.fixture
def config(sample_project: Path) -> CodePulseConfig:
    return CodePulseConfig(
        product_name="CodePulse",
        binary_name="codepulse",
        data_dir=str(sample_project / ".codepulse"),
    )


@pytest.fixture
def db_path(tmp_path: Path) -> str:
    return str(tmp_path / "test.db")


@pytest.fixture
def db(db_path: str) -> Generator[GraphDB, None, None]:
    gdb = GraphDB(db_path)
    gdb.initialize()
    yield gdb
    gdb.close()


@pytest.fixture
def indexed_db(db: GraphDB, sample_project: Path) -> GraphDB:
    from codepulse.parser import SourceParser

    parser = SourceParser()
    src_dir = sample_project / "src"
    for fpath in src_dir.iterdir():
        if fpath.suffix in (".py", ".ts"):
            symbols, refs = parser.parse_file(str(fpath))
            for sym in symbols:
                db.upsert_node(sym)
            for ref in refs:
                db.upsert_edge(ref)
    return db


@pytest.fixture
def parser() -> Generator:
    from codepulse.parser import SourceParser

    yield SourceParser()


@pytest.fixture
def cli_runner():
    from click.testing import CliRunner
    return CliRunner()
