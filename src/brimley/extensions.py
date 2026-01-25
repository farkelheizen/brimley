from typing import Callable, NamedTuple, Dict, Any
import sqlite3

class UDFDefinition(NamedTuple):
    name: str
    num_args: int
    func: Callable

# Global registry for extensions
_UDF_REGISTRY: Dict[str, UDFDefinition] = {}

def register_sqlite_function(name: str, num_args: int):
    """
    Decorator to register a Python function as a SQLite UDF.
    
    Args:
        name: The name to use inside SQL (e.g., 'CALC_TAX').
        num_args: Number of arguments the function accepts.
    """
    def decorator(func: Callable):
        _UDF_REGISTRY[name] = UDFDefinition(name, num_args, func)
        return func
    return decorator

def get_registry() -> Dict[str, UDFDefinition]:
    return _UDF_REGISTRY

def clear_registry():
    """Clear registry, primarily for testing purposes."""
    _UDF_REGISTRY.clear()
