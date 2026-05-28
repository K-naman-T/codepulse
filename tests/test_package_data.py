from pathlib import Path

from codepulse.parser import SourceParser


def test_parser_configs_are_loaded_from_package_resources():
    parser = SourceParser()

    old_repo_root_parsers = str(Path(__file__).resolve().parent.parent / "parsers")
    assert parser._parsers_dir != old_repo_root_parsers, (
        "SourceParser still uses repo-root parsers/ — should use package resources"
    )

    assert "codepulse" in parser._parsers_dir

    fixture = Path(__file__).parent / "fixtures" / "accuracy.py"
    symbols, refs = parser.parse_file(str(fixture))
    assert len(symbols) > 0
