"""Version compatibility tests.

Ensures our Python version requirements are correct and enforced.
"""

from pathlib import Path

import yaml


def test_min_python_version():
    """pyproject.toml must require Python >=3.10 (not 3.9)."""
    path = Path(__file__).parent.parent / "pyproject.toml"
    content = path.read_text()
    assert ">=3.10" in content, "Expected >=3.10 in requires-python"


def test_build_backend_correct():
    """Build backend must be setuptools.build_meta (not _legacy)."""
    path = Path(__file__).parent.parent / "pyproject.toml"
    content = path.read_text()
    for line in content.split("\n"):
        line = line.strip()
        if line.startswith("build-backend"):
            backend = line.split("=")[1].strip().strip('"').strip("'")
            assert backend == "setuptools.build_meta", f"Expected setuptools.build_meta, got {backend}"
            return
    assert False, "build-backend not found"


def test_ci_includes_py310():
    """GitHub Actions CI must test Python 3.10."""
    path = Path(__file__).parent.parent / ".github" / "workflows" / "test.yml"
    content = path.read_text()
    assert "3.10" in content, "CI must include Python 3.10 in matrix"


def test_ci_includes_py313():
    """GitHub Actions CI must test Python 3.13."""
    path = Path(__file__).parent.parent / ".github" / "workflows" / "test.yml"
    content = path.read_text()
    assert "3.13" in content, "CI must include Python 3.13 in matrix"


def test_all_language_extras_listed():
    """pyproject.toml must have extras for all supported languages."""
    path = Path(__file__).parent.parent / "pyproject.toml"
    content = path.read_text()
    required_extras = [
        "python", "typescript", "go", "java", "rust", "ruby",
        "php", "c", "cpp", "swift", "kotlin", "scala",
    ]
    for extra in required_extras:
        assert f"{extra} = [" in content, f"Missing extra: [{extra}]"


def test_full_extra_includes_all():
    """The 'all' extra must include all language extras."""
    path = Path(__file__).parent.parent / "pyproject.toml"
    content = path.read_text()
    required = [
        "python", "typescript", "go", "java", "rust", "ruby",
        "php", "c", "cpp", "swift", "kotlin", "scala",
    ]
    for lang in required:
        assert lang in content, f"Missing '{lang}' in pyproject.toml"
