from pathlib import Path


def normalize_path(path: str) -> str:
    return str(Path(path).expanduser().resolve())


def file_node_id(file_path: str) -> str:
    return f"{normalize_path(file_path)}:__file__"


def symbol_node_id(file_path: str, qualified_name: str) -> str:
    return f"{normalize_path(file_path)}:{qualified_name}"


def external_node_id(kind: str, name: str) -> str:
    return f"external:{kind}:{name}"


def unresolved_node_id(kind: str, name: str) -> str:
    return f"unresolved:{kind}:{name}"
