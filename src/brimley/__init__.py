from __future__ import annotations

from importlib.metadata import version

__version__ = version("brimley")

from collections.abc import Callable
from typing import Any, TypeVar, overload

from brimley.core.di import AppState, Config, Connection, Depends

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


@overload
def provider(func: DecoratedCallable, /) -> DecoratedCallable:
	...


@overload
def provider(
	func: None = None,
	/,
	*,
	name: str | None = None,
	scope: str = "singleton",
	eager: bool = False,
) -> Callable[[DecoratedCallable], DecoratedCallable]:
	...


def provider(
	func: DecoratedCallable | None = None,
	/,
	*,
	name: str | None = None,
	scope: str = "singleton",
	eager: bool = False,
) -> DecoratedCallable | Callable[[DecoratedCallable], DecoratedCallable]:
	"""Decorator that marks a callable as a Brimley managed dependency provider.

	Supports both bare and configured usage:

	- ``@provider``
	- ``@provider(scope="request", eager=False)``

	The decorated callable may be a regular function or a generator function
	(using ``yield`` for setup/teardown semantics).

	Introduced in Brimley 0.8.
	"""

	def decorator(target: DecoratedCallable) -> DecoratedCallable:
		meta: dict[str, Any] = {
			"type": "provider",
			"name": name,
			"scope": scope,
			"eager": eager,
		}
		setattr(target, "_brimley_meta", meta)
		return target

	if callable(func):
		return decorator(func)

	return decorator


@overload
def on_startup(func: DecoratedCallable, /) -> DecoratedCallable:
	...


@overload
def on_startup(
	func: None = None,
	/,
) -> Callable[[DecoratedCallable], DecoratedCallable]:
	...


def on_startup(
	func: DecoratedCallable | None = None,
	/,
) -> DecoratedCallable | Callable[[DecoratedCallable], DecoratedCallable]:
	"""Decorator that marks a callable to run after all singletons are initialized.

	Supports both bare and configured usage:

	- ``@on_startup``
	- ``@on_startup()``

	Hooks execute in declaration (scan) order.

	Introduced in Brimley 0.8.
	"""

	def decorator(target: DecoratedCallable) -> DecoratedCallable:
		meta: dict[str, Any] = {"type": "on_startup"}
		setattr(target, "_brimley_meta", meta)
		return target

	if callable(func):
		return decorator(func)

	return decorator


@overload
def on_shutdown(func: DecoratedCallable, /) -> DecoratedCallable:
	...


@overload
def on_shutdown(
	func: None = None,
	/,
) -> Callable[[DecoratedCallable], DecoratedCallable]:
	...


def on_shutdown(
	func: DecoratedCallable | None = None,
	/,
) -> DecoratedCallable | Callable[[DecoratedCallable], DecoratedCallable]:
	"""Decorator that marks a callable to run on graceful shutdown.

	Supports both bare and configured usage:

	- ``@on_shutdown``
	- ``@on_shutdown()``

	Hooks execute in reverse declaration (scan) order.

	Introduced in Brimley 0.8.
	"""

	def decorator(target: DecoratedCallable) -> DecoratedCallable:
		meta: dict[str, Any] = {"type": "on_shutdown"}
		setattr(target, "_brimley_meta", meta)
		return target

	if callable(func):
		return decorator(func)

	return decorator


__all__ = [
	"AppState",
	"Config",
	"Connection",
	"Depends",
	"function",
	"entity",
	"provider",
	"on_startup",
	"on_shutdown",
]
