"""Framework-aware route detection.

Detects web framework routing patterns and links URL patterns
to their handler functions/classes.
"""

import itertools
import json
import logging
import re
from pathlib import Path
from typing import Any

from codepulse.parser import SourceParser
from codepulse.db import GraphDB, Node, Edge

logger = logging.getLogger(__name__)


FRAMEWORK_PATTERNS: dict[str, list[dict[str, Any]]] = {
    "django": [
        {
            "pattern": r"path\(['\"]([^'\"]+)['\"].*?\.as_view\(\)",
            "kind": "route",
            "handler_group": 1,
        },
        {
            "pattern": r"re_path\(['\"]([^'\"]+)['\"].*?\.as_view\(\)",
            "kind": "route",
        },
    ],
    "flask": [
        {
            "pattern": r"@\w+\.route\(['\"]([^'\"]+)['\"]",
            "kind": "route",
        },
    ],
    "fastapi": [
        {
            "pattern": r"@\w+\.(?:get|post|put|delete|patch)\(['\"]([^'\"]+)['\"]",
            "kind": "route",
        },
    ],
    "express": [
        {
            "pattern": r"\.(?:get|post|put|delete|patch|use)\(['\"](/[^'\"]+)['\"],\s*(\w+)",
            "kind": "route",
            "handler_group": 2,
        },
    ],
}


def detect_frameworks(project_root: str) -> list[str]:
    """Detect which frameworks are used in a project."""
    root = Path(project_root)
    frameworks = []

    if list(root.rglob("urls.py")):
        frameworks.append("django")
    if list(root.rglob("app.py")) or list(root.rglob("routes.py")):
        frameworks.append("flask")
        frameworks.append("fastapi")
    if list(root.rglob("package.json")):
        pkg = root / "package.json"
        try:
            data = json.loads(pkg.read_text())
            deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
            if "express" in deps:
                frameworks.append("express")
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            logger.warning("Could not read package.json for Express detection: %s", pkg)
    if list(root.rglob("requirements.txt")) or list(root.rglob("pyproject.toml")):
        for f in root.rglob("requirements.txt"):
            try:
                content = f.read_text()
            except (OSError, UnicodeDecodeError):
                logger.warning("Could not read requirements file for framework detection: %s", f)
                continue
            if "django" in content:
                frameworks.append("django")
            if "flask" in content:
                frameworks.append("flask")
            if "fastapi" in content:
                frameworks.append("fastapi")

    return list(set(frameworks))


def index_routes(project_root: str, db: GraphDB, parser: SourceParser) -> int:
    """Find route definitions in a project and add them to the graph.

    Returns number of route nodes added.
    """
    frameworks = detect_frameworks(project_root)
    if not frameworks:
        return 0

    count = 0
    root = Path(project_root)

    targets: dict[str, tuple[Any, str]] = {
        "django": (lambda root: root.rglob("urls.py"), "python"),
        "express": (
            lambda root: itertools.chain(root.rglob("*.js"), root.rglob("*.ts")),
            "typescript",
        ),
        "flask": (lambda root: root.rglob("*.py"), "python"),
        "fastapi": (lambda root: root.rglob("*.py"), "python"),
    }

    for framework in frameworks:
        patterns = FRAMEWORK_PATTERNS.get(framework, [])
        glob_fn, language = targets[framework]
        for route_file in glob_fn(root):
            try:
                content = route_file.read_text()
                for pat_def in patterns:
                    for match in re.finditer(pat_def["pattern"], content):
                        url_pattern = match.group(1)
                        handler = (
                            match.group(pat_def.get("handler_group", 1))
                            if pat_def.get("handler_group")
                            else None
                        )
                        node_id = f"{route_file}:route:{url_pattern}"
                        if framework == "django":
                            sig = f"{framework}: {url_pattern} → {handler or 'unknown'}"
                        elif framework == "express":
                            sig = f"{framework}: {url_pattern} → {handler}"
                        else:
                            sig = f"{framework}: {url_pattern}"
                            if handler:
                                sig += f" → {handler}"
                        node = Node(
                            id=node_id,
                            file_path=str(route_file.resolve()),
                            name=url_pattern,
                            kind="route",
                            signature=sig,
                            language=language,
                        )
                        db.upsert_node(node)
                        count += 1
            except (OSError, UnicodeDecodeError):
                logger.warning("Could not read %s for %s route detection", route_file, framework)

    return count
