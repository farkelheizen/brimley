from typing import Dict, Iterator, Optional, TypeVar, Generic, Protocol, List

class HasName(Protocol):
    name: str

T = TypeVar("T", bound=HasName)

class Registry(Generic[T]):
    """
    A generic centralized repository for objects with a name attribute.
    """
    def __init__(self):
        self._items: Dict[str, T] = {}
        self._aliases: Dict[str, str] = {}
        self._quarantined: Dict[str, str] = {}

    def register(self, item: T) -> None:
        """
        Register an item. Raises ValueError if name already exists.
        """
        if item.name in self._aliases:
            raise ValueError(f"Item name '{item.name}' conflicts with an existing alias.")

        if item.name in self._quarantined:
            del self._quarantined[item.name]

        if item.name in self._items:
            raise ValueError(f"Item with name '{item.name}' is already registered.")
        
        self._items[item.name] = item

    def register_all(self, items: List[T]) -> None:
        for item in items:
            self.register(item)

    def get(self, name: str) -> T:
        """
        Retrieve an item by name. Raises KeyError if not found.
        """
        if name in self._quarantined:
            reason = self._quarantined[name]
            raise KeyError(f"'{name}' is quarantined due to reload error: {reason}")

        if name in self._aliases:
            target = self._aliases[name]
            if target in self._quarantined:
                reason = self._quarantined[target]
                raise KeyError(f"'{target}' is quarantined due to reload error: {reason}")
            return self._items[target]

        if name not in self._items:
            raise KeyError(f"'{name}' not found in registry.")
        return self._items[name]

    def register_alias(self, alias: str, target: str) -> None:
        """
        Register a temporary alias that resolves to an existing canonical item.
        """
        if target in self._aliases:
            raise ValueError("Alias chains are not supported.")

        if target not in self._items:
            raise ValueError(f"Alias target '{target}' does not exist.")

        if alias in self._items:
            raise ValueError(f"Alias '{alias}' cannot shadow an existing canonical name.")

        if alias in self._aliases:
            raise ValueError(f"Alias '{alias}' is already registered.")

        if alias == target:
            raise ValueError("Alias and target cannot be the same.")

        self._aliases[alias] = target

    def mark_quarantined(self, name: str, reason: str) -> None:
        """Mark a canonical name as quarantined for fail-closed reload behavior."""
        self._quarantined[name] = reason

    def is_quarantined(self, name: str) -> bool:
        """Return whether a canonical or alias name is quarantined."""
        if name in self._quarantined:
            return True
        if name in self._aliases:
            return self._aliases[name] in self._quarantined
        return False

    def __contains__(self, name: str) -> bool:
        return name in self._items or name in self._aliases or name in self._quarantined

    def __len__(self) -> int:
        return len(self._items)

    def __iter__(self) -> Iterator[T]:
        return iter(self._items.values())
