from pathlib import Path

from codepulse.ids import (
    normalize_path,
    file_node_id,
    symbol_node_id,
    external_node_id,
    unresolved_node_id,
)


def test_file_node_id():
    result = file_node_id("/repo/src/a.py")
    assert result == "/repo/src/a.py:__file__"


def test_symbol_node_id():
    result = symbol_node_id("/repo/src/a.py", "User.save")
    assert result == "/repo/src/a.py:User.save"


def test_external_node_id():
    assert external_node_id("module", "os") == "external:module:os"


def test_unresolved_node_id():
    assert unresolved_node_id("calls", "missing") == "unresolved:calls:missing"


def test_normalize_path_preserves_absolute():
    result = normalize_path("/repo/src/a.py")
    assert result.startswith("/")
    assert result.endswith("/repo/src/a.py")
    assert result == str(Path("/repo/src/a.py").resolve())


def test_normalize_path_handles_tilde():
    home = str(Path.home())
    result = normalize_path("~/src/a.py")
    assert result.startswith(home)
    assert result.endswith("/src/a.py")


def test_normalize_path_returns_absolute():
    result = normalize_path("a.py")
    assert result.startswith("/")


def test_file_node_id_uses_normalize_path():
    result = file_node_id("/repo/src/a.py")
    expected = f"{normalize_path('/repo/src/a.py')}:__file__"
    assert result == expected


def test_symbol_node_id_uses_normalize_path():
    result = symbol_node_id("/repo/src/a.py", "User.save")
    expected = f"{normalize_path('/repo/src/a.py')}:User.save"
    assert result == expected
