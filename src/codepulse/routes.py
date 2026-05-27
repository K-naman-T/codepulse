"""Framework-aware route detection.

Detects web framework routing patterns and links URL patterns
to their handler functions/classes.
"""

import re
from pathlib import Path
from typing import Any

from codepulse.parser import SourceParser
from codepulse.db import GraphDB, Node, Edge


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
            import json
            data = json.loads(pkg.read_text())
            deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
            if "express" in deps:
                frameworks.append("express")
        except Exception:
            pass
    if list(root.rglob("requirements.txt")) or list(root.rglob("pyproject.toml")):
        for f in root.rglob("requirements.txt"):
            content = f.read_text()
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

    for framework in frameworks:
        patterns = FRAMEWORK_PATTERNS.get(framework, [])

        if framework == "django":
            for urls_file in root.rglob("urls.py"):
                try:
                    content = urls_file.read_text()
                    for pat_def in patterns:
                        for match in re.finditer(pat_def["pattern"], content):
                            url_pattern = match.group(1)
                            handler = match.group(pat_def.get("handler_group", 1)) if pat_def.get("handler_group") else None
                            name = handler or url_pattern
                            node_id = f"{urls_file}:route:{url_pattern}"
                            node = Node(
                                id=node_id,
                                file_path=str(urls_file.resolve()),
                                name=url_pattern,
                                kind="route",
                                signature=f"{framework}: {url_pattern} → {handler or 'unknown'}",
                                language="python",
                            )
                            db.upsert_node(node)
                            count += 1
                except Exception:
                    pass

        elif framework == "express":
            for js_file in root.rglob("*.js") + root.rglob("*.ts"):
                try:
                    content = js_file.read_text()
                    for pat_def in patterns:
                        for match in re.finditer(pat_def["pattern"], content):
                            url_pattern = match.group(1)
                            handler = match.group(pat_def.get("handler_group", 1))
                            node_id = f"{js_file}:route:{url_pattern}"
                            node = Node(
                                id=node_id,
                                file_path=str(js_file.resolve()),
                                name=url_pattern,
                                kind="route",
                                signature=f"{framework}: {url_pattern} → {handler}",
                                language="typescript",
                            )
                            db.upsert_node(node)
                            count += 1
                except Exception:
                    pass

        else:
            for py_file in root.rglob("*.py"):
                try:
                    content = py_file.read_text()
                    for pat_def in patterns:
                        for match in re.finditer(pat_def["pattern"], content):
                            url_pattern = match.group(1)
                            name = handler if (handler := match.group(pat_def.get("handler_group", 1)) if pat_def.get("handler_group") else None) else url_pattern
                            handler_name = handler if pat_def.get("handler_group") else None
                            sig = f"{framework}: {url_pattern}"
                            if handler_name:
                                sig += f" → {handler_name}"
                            node_id = f"{py_file}:route:{url_pattern}"
                            node = Node(
                                id=node_id,
                                file_path=str(py_file.resolve()),
                                name=url_pattern,
                                kind="route",
                                signature=sig,
                                language="python",
                            )
                            db.upsert_node(node)
                            count += 1
                except Exception:
                    pass

    return count
