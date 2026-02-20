from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypeVar, overload

from brimley.core.di import AppState, Config, Connection

DecoratedCallable = TypeVar("DecoratedCallable", bound=Callable[..., Any])
DecoratedClass = TypeVar("DecoratedClass", bound=type)


@overload
def function(func: DecoratedCallable, /) -> DecoratedCallable:
	...


@overload
def function(
	func: None = None,
	/,
	*,
	name: str | None = None,
	mcpType: str | None = None,
	reload: bool = True,
	type: str = "python_function",
	**kwargs: Any,
) -> Callable[[DecoratedCallable], DecoratedCallable]:
	...


def function(
	func: DecoratedCallable | None = None,
	/,
	*,
	name: str | None = None,
	mcpType: str | None = None,
	reload: bool = True,
	type: str = "python_function",
	**kwargs: Any,
) -> DecoratedCallable | Callable[[DecoratedCallable], DecoratedCallable]:
	"""Decorator that marks a callable as a Brimley function.

	Supports both bare and configured usage:
	- ``@function``
	- ``@function(name="my_name", mcpType="tool")``
	"""

	def decorator(target: DecoratedCallable) -> DecoratedCallable:
		meta: dict[str, Any] = {
			"name": name,
			"type": type,
			"reload": reload,
			"extra": dict(kwargs),
		}

		if mcpType is not None:
			meta["mcpType"] = mcpType

		setattr(target, "_brimley_meta", meta)
		return target

	if callable(func):
		return decorator(func)

	return decorator


@overload
def entity(cls: DecoratedClass, /) -> DecoratedClass:
	...


@overload
def entity(
	cls: None = None,
	/,
	*,
	name: str | None = None,
	**kwargs: Any,
) -> Callable[[DecoratedClass], DecoratedClass]:
	...


def entity(
	cls: DecoratedClass | None = None,
	/,
	*,
	name: str | None = None,
	**kwargs: Any,
) -> DecoratedClass | Callable[[DecoratedClass], DecoratedClass]:
	"""Decorator that marks a class as a Brimley entity.

	Supports both bare and configured usage:
	- ``@entity``
	- ``@entity(name="User")``
	"""

	def decorator(target: DecoratedClass) -> DecoratedClass:
		meta = {
			"name": name,
			"type": "python_entity",
			"description": kwargs.get("description"),
			"extra": dict(kwargs),
		}
		setattr(target, "_brimley_meta", meta)
		return target

	if isinstance(cls, type):
		return decorator(cls)

	return decorator


__all__ = [
	"AppState",
	"Config",
	"Connection",
	"function",
	"entity",
]
