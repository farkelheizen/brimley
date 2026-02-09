from typing import Dict, Iterator, Optional
from brimley.core.models import BrimleyFunction

class Registry:
    """
    A centralized repository for all loaded BrimleyFunctions.
    """
    def __init__(self):
        self._functions: Dict[str, BrimleyFunction] = {}

    def register(self, func: BrimleyFunction) -> None:
        """
        Register a function. Raises ValueError if name already exists.
        """
        if func.name in self._functions:
            raise ValueError(f"Function '{func.name}' is already registered.")
        
        self._functions[func.name] = func

    def get(self, name: str) -> BrimleyFunction:
        """
        Retrieve a function by name. Raises KeyError if not found.
        """
        if name not in self._functions:
            raise KeyError(f"Function '{name}' not found in registry.")
        return self._functions[name]

    def __contains__(self, name: str) -> bool:
        return name in self._functions

    def __len__(self) -> int:
        return len(self._functions)

    def __iter__(self) -> Iterator[BrimleyFunction]:
        return iter(self._functions.values())
