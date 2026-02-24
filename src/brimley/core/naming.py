from pathlib import Path

RESERVED_FUNCTION_NAMES: set[str] = {
    "help",
    "quit",
    "exit",
    "reset",
    "reload",
    "settings",
    "config",
    "state",
    "functions",
    "entities",
    "databases",
    "errors",
}


def is_reserved_function_name(name: str) -> bool:
    """Return whether a function name conflicts with reserved REPL/admin commands."""
    return name.lower() in RESERVED_FUNCTION_NAMES


def normalize_name_for_proximity(name: str) -> str:
    """Normalize names for near-collision checks (case + separator folding)."""
    return name.lower().replace("-", "").replace("_", "")


def build_canonical_id(kind: str, root_dir: Path, source_file: Path, symbol: str) -> str:
    """Build deterministic canonical object ID: <kind>:<normalized_path>:<symbol>."""
    root_resolved = root_dir.resolve()
    source_resolved = source_file.resolve()

    try:
        relative_path = source_resolved.relative_to(root_resolved)
        normalized_path = relative_path.as_posix()
    except ValueError:
        normalized_path = source_resolved.as_posix()

    normalized_path = normalized_path.replace("\\", "/").lstrip("./")
    return f"{kind}:{normalized_path.lower()}:{symbol}"
