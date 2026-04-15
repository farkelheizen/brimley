from pathlib import Path
from typing import Dict, Any, Optional
from sqlalchemy import create_engine, Engine
from sqlalchemy.engine import make_url


_NON_ENGINE_CONFIG_KEYS = {"url", "connector"}


def _resolve_database_url(url: str, base_dir: Optional[Path]) -> str:
    """Resolve relative SQLite database URLs against a configured base directory."""
    if base_dir is None:
        return url

    try:
        parsed = make_url(url)
    except Exception:
        return url

    if not parsed.drivername.startswith("sqlite"):
        return url

    database = parsed.database
    if not database or database == ":memory:" or database.startswith("file:"):
        return url

    db_path = Path(database)
    if db_path.is_absolute():
        return url

    resolved_db = (base_dir / db_path).resolve()
    return parsed.set(database=str(resolved_db)).render_as_string(hide_password=False)


def _build_engine_options(config: Dict[str, Any]) -> Dict[str, Any]:
    """Extract SQLAlchemy create_engine options from a database config block."""
    return {
        key: value
        for key, value in config.items()
        if key not in _NON_ENGINE_CONFIG_KEYS
    }


def initialize_databases(db_configs: Dict[str, Any], base_dir: Optional[Path] = None) -> Dict[str, Engine]:
    """
    Initializes database engines from a configuration dictionary.

    Args:
        db_configs: A dictionary mapping connection names to their configurations.
                   Expected structure per connection: {'url': '...', 'connect_args': {...}}
        base_dir: Optional root directory used to resolve relative SQLite file URLs.

    Returns:
        A dictionary mapping connection names to SQLAlchemy Engine objects.
    """
    engines: Dict[str, Engine] = {}

    for name, config in db_configs.items():
        url = config.get("url")
        if not url:
            # We might want to use Diagnostics here later, but for now a simple check
            continue

        resolved_url = _resolve_database_url(url, base_dir=base_dir)
        engine_options = _build_engine_options(config)
        engine = create_engine(resolved_url, **engine_options)
        engines[name] = engine

    return engines
