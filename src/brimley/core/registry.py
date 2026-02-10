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

    def register(self, item: T) -> None:
        """
        Register an item. Raises ValueError if name already exists.
        """
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
        if name not in self._items:
            raise KeyError(f"'{name}' not found in registry.")
        return self._items[name]

    def __contains__(self, name: str) -> bool:
        return name in self._items

    def __len__(self) -> int:
        return len(self._items)

    def __iter__(self) -> Iterator[T]:
        return iter(self._items.values())
