from typing import Dict, Any
from sqlalchemy import create_engine, Engine


def initialize_databases(db_configs: Dict[str, Any]) -> Dict[str, Engine]:
    """
    Initializes database engines from a configuration dictionary.

    Args:
        db_configs: A dictionary mapping connection names to their configurations.
                   Expected structure per connection: {'url': '...', 'connect_args': {...}}

    Returns:
        A dictionary mapping connection names to SQLAlchemy Engine objects.
    """
    engines: Dict[str, Engine] = {}

    for name, config in db_configs.items():
        url = config.get("url")
        if not url:
            # We might want to use Diagnostics here later, but for now a simple check
            continue

        connect_args = config.get("connect_args", {})
        engine = create_engine(url, **connect_args)
        engines[name] = engine

    return engines
