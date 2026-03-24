"""
BrimleyContainer: core dependency injection container for Brimley 0.8.

Manages singleton and request-scoped provider lifecycle, including yield-based
teardown, overrides for testing, and thread-safe lazy/eager initialisation.

Introduced in Brimley 0.8 (B08-S4).
"""

from __future__ import annotations

import asyncio
import importlib
import inspect
import threading
from contextlib import contextmanager
from typing import Any, Dict, Generator, Iterator, List, Optional

from loguru import logger

from brimley.core.models import ProviderMetadata


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class ProviderResolutionError(Exception):
    """Raised when a provider cannot be imported, called, or resolved."""


class DuplicateProviderError(Exception):
    """Raised when a provider name is registered more than once."""


# ---------------------------------------------------------------------------
# Request scope
# ---------------------------------------------------------------------------


class _RequestScope:
    """
    Holds request-scoped provider instances for a single ``Dispatcher.run()`` call.

    Created and torn down via :meth:`BrimleyContainer.request_scope`.
    Singletons are still resolved from the parent container; request-scoped
    providers get fresh instances per scope.
    """

    def __init__(
        self,
        container: BrimleyContainer,
        context: Optional[Any] = None,
    ) -> None:
        self._container = container
        self._context = context
        # Resolved request-scoped instances: name -> value
        self._instances: Dict[str, Any] = {}
        # Generators awaiting teardown: name -> generator (insertion order = init order)
        self._generators: Dict[str, Iterator[Any]] = {}

    def resolve(self, name: str) -> Any:
        """
        Resolve a provider within this request scope.

        Singletons are delegated to the parent container; request-scoped
        providers are cached within this scope.
        """
        # Overrides always win
        with self._container._overrides_lock:
            if name in self._container._overrides:
                return self._container._overrides[name]

        with self._container._registry_lock:
            metadata = self._container._registry.get(name)

        if metadata is None:
            raise ProviderResolutionError(f"No provider registered with name '{name}'.")

        if metadata.scope == "singleton":
            return self._container.resolve(name, self._context)

        # Request-scoped: return cached or create fresh
        if name in self._instances:
            return self._instances[name]

        value = self._container._call_provider(
            name=name,
            metadata=metadata,
            context=self._context,
            generator_store=self._generators,
            scope=self,
        )
        self._instances[name] = value
        return value

    def _teardown(self) -> None:
        """Tear down request-scoped generators in reverse initialisation order."""
        for _name, gen in reversed(list(self._generators.items())):
            try:
                next(gen)
            except StopIteration:
                pass
            except Exception as exc:
                logger.warning(
                    "Exception during request-scope teardown for provider '{}': {}",
                    _name,
                    exc,
                )
        self._generators.clear()
        self._instances.clear()


# ---------------------------------------------------------------------------
# Container
# ---------------------------------------------------------------------------


class BrimleyContainer:
    """
    Central dependency injection container for Brimley.

    Manages singleton and request-scoped providers with full lifecycle support:
    lazy/eager initialisation, yield-based teardown, thread-safe singleton
    resolution, and override seams for testing.

    Introduced in Brimley 0.8.
    """

    def __init__(self) -> None:
        # Provider registry: canonical_name -> ProviderMetadata
        self._registry: Dict[str, ProviderMetadata] = {}
        # Per-provider lock: prevents double-initialisation of singletons
        self._provider_locks: Dict[str, threading.Lock] = {}
        # Singleton instances: name -> resolved value
        self._singletons: Dict[str, Any] = {}
        # Singleton generators awaiting teardown: name -> generator
        self._singleton_generators: Dict[str, Iterator[Any]] = {}
        # Global lock: guards _registry, _singletons, _singleton_generators
        self._registry_lock = threading.Lock()
        # Overrides: name -> mock value (testing seam)
        self._overrides: Dict[str, Any] = {}
        self._overrides_lock = threading.Lock()

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register(self, metadata: ProviderMetadata) -> None:
        """
        Register a provider from its AST-scanned metadata.

        Args:
            metadata: :class:`ProviderMetadata` produced by the scanner.

        Raises:
            DuplicateProviderError: If a provider with the same name is already
                registered.
        """
        name = metadata.name or metadata.func_name
        with self._registry_lock:
            if name in self._registry:
                raise DuplicateProviderError(
                    f"Provider '{name}' is already registered. "
                    "Use container.override() to replace it for testing."
                )
            self._registry[name] = metadata
            self._provider_locks[name] = threading.Lock()

    # ------------------------------------------------------------------
    # Resolution
    # ------------------------------------------------------------------

    def resolve(self, name: str, context: Optional[Any] = None) -> Any:
        """
        Resolve a provider by name.

        * **Singleton** providers are lazily instantiated and cached.
        * **Request-scoped** providers produce a fresh instance per call when
          invoked outside a :meth:`request_scope` context (suitable for simple
          testing; production code should use ``request_scope``).

        Args:
            name: The registered provider name.
            context: Optional ``BrimleyContext`` forwarded to providers that
                declare a ``BrimleyContext``-typed parameter.

        Returns:
            The resolved provider value.

        Raises:
            ProviderResolutionError: If no provider named *name* is registered.
        """
        # Overrides take precedence over everything
        with self._overrides_lock:
            if name in self._overrides:
                return self._overrides[name]

        with self._registry_lock:
            if name not in self._registry:
                raise ProviderResolutionError(
                    f"No provider registered with name '{name}'."
                )
            metadata = self._registry[name]

        if metadata.scope == "singleton":
            return self._resolve_singleton(name, metadata, context)

        # Request-scoped without an active scope: fresh instance, no caching
        return self._call_provider(
            name=name,
            metadata=metadata,
            context=context,
            generator_store={},
            scope=None,
        )

    def _resolve_singleton(
        self,
        name: str,
        metadata: ProviderMetadata,
        context: Optional[Any],
    ) -> Any:
        """Thread-safe lazy singleton resolution with per-provider locking."""
        with self._provider_locks[name]:
            # Double-checked locking: another thread may have initialised while
            # we waited for the provider lock.
            with self._registry_lock:
                if name in self._singletons:
                    return self._singletons[name]

            value = self._call_provider(
                name=name,
                metadata=metadata,
                context=context,
                generator_store=self._singleton_generators,
                scope=None,
            )

            with self._registry_lock:
                self._singletons[name] = value

            return value

    def _call_provider(
        self,
        name: str,
        metadata: ProviderMetadata,
        context: Optional[Any],
        generator_store: Dict[str, Any],
        scope: Optional[_RequestScope],
    ) -> Any:
        """
        Import, call, and unwrap a provider function.

        Handles plain callables, sync generators (yield-based teardown),
        coroutines (``async def``), and async generators.
        """
        handler_path = metadata.handler or f"{metadata.module_path}.{metadata.func_name}"
        fn = self._import_handler(handler_path)
        kwargs = self._build_kwargs(fn, context, scope)
        result = fn(**kwargs)

        # Sync generator: yield provides the value; remainder is teardown
        if inspect.isgenerator(result):
            value = next(result)
            generator_store[name] = result
            return value

        # Coroutine: async def provider() -> T (no teardown)
        if asyncio.iscoroutine(result):
            loop = self._get_or_create_loop()
            return loop.run_until_complete(result)

        # Async generator: async def provider(): yield value  (teardown after yield)
        if inspect.isasyncgen(result):
            loop = self._get_or_create_loop()

            async def _advance(agen: Any) -> Any:
                return await agen.__anext__()

            value = loop.run_until_complete(_advance(result))

            # Wrap async teardown in a sync generator so shutdown() is uniform.
            # Use asend(None) to advance past the yield and run cleanup code;
            # aclose() would inject GeneratorExit and skip cleanup.
            agen_ref = result

            def _async_gen_teardown_wrapper() -> Iterator[Any]:
                yield value
                async def _run_teardown() -> None:
                    try:
                        await agen_ref.asend(None)
                    except StopAsyncIteration:
                        pass
                    except Exception as exc:
                        logger.warning(
                            "Exception during async provider teardown for '{}': {}",
                            name,
                            exc,
                        )
                loop.run_until_complete(_run_teardown())

            wrapper = _async_gen_teardown_wrapper()
            next(wrapper)  # advance past the yield, teardown is now pending
            generator_store[name] = wrapper
            return value

        return result

    def _import_handler(self, handler: str) -> Any:
        """Import and return the callable identified by *handler* (``module.func``)."""
        try:
            module_path, func_name = handler.rsplit(".", 1)
        except ValueError:
            raise ProviderResolutionError(
                f"Invalid handler path '{handler}': expected 'module.function'."
            )
        try:
            module = importlib.import_module(module_path)
        except ImportError as exc:
            raise ProviderResolutionError(
                f"Cannot import module '{module_path}' for handler '{handler}': {exc}"
            ) from exc
        if not hasattr(module, func_name):
            raise ProviderResolutionError(
                f"Module '{module_path}' has no attribute '{func_name}'."
            )
        return getattr(module, func_name)

    def _build_kwargs(
        self,
        fn: Any,
        context: Optional[Any],
        scope: Optional[_RequestScope],
    ) -> Dict[str, Any]:
        """
        Build keyword arguments for *fn* by inspecting its signature.

        Handles:
        * ``BrimleyContext``-annotated parameters → inject *context*.
        * Parameters with ``Depends(...)`` defaults → recursively resolve.

        Resolves PEP 563 (``from __future__ import annotations``) string
        annotations via ``typing.get_type_hints`` where possible.
        """
        import typing
        from brimley.core.di import Depends  # local import avoids circular dependency

        try:
            sig = inspect.signature(fn)
        except (ValueError, TypeError):
            return {}

        # Attempt to resolve stringified annotations (PEP 563)
        try:
            resolved_hints: Dict[str, Any] = typing.get_type_hints(fn)
        except Exception:
            resolved_hints = {}

        kwargs: Dict[str, Any] = {}
        for param_name, param in sig.parameters.items():
            # Prefer the resolved hint; fall back to raw annotation
            annotation = resolved_hints.get(param_name, param.annotation)

            # BrimleyContext injection
            if self._is_context_annotation(annotation) and context is not None:
                kwargs[param_name] = context
                continue

            # Depends() injection
            if isinstance(param.default, Depends):
                dep_name = param.default.provider_name
                if scope is not None:
                    kwargs[param_name] = scope.resolve(dep_name)
                else:
                    kwargs[param_name] = self.resolve(dep_name, context)

        return kwargs

    @staticmethod
    def _is_context_annotation(annotation: Any) -> bool:
        """
        Return True if *annotation* is or subclasses ``BrimleyContext``.

        Handles both resolved type objects and PEP 563 string annotations.
        """
        if annotation is inspect.Parameter.empty:
            return False
        # String annotation (PEP 563: from __future__ import annotations)
        if isinstance(annotation, str):
            return annotation.rsplit(".", 1)[-1] == "BrimleyContext"
        try:
            from brimley.core.context import BrimleyContext  # local import
            return annotation is BrimleyContext or (
                isinstance(annotation, type) and issubclass(annotation, BrimleyContext)
            )
        except (ImportError, TypeError):
            return False

    @staticmethod
    def _get_or_create_loop() -> asyncio.AbstractEventLoop:
        """Return a usable event loop, creating one if necessary."""
        try:
            loop = asyncio.get_running_loop()
            raise ProviderResolutionError(
                "Cannot synchronously resolve an async provider: an event loop is "
                "already running. Use an async-aware startup sequence."
            )
        except RuntimeError:
            # No running loop; create a fresh one
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            return loop

    # ------------------------------------------------------------------
    # Overrides (testing seam)
    # ------------------------------------------------------------------

    def override(self, name: str, value: Any) -> None:
        """
        Pin a provider to a fixed value, bypassing its factory.

        Overrides take precedence over all registered providers and are
        visible from both direct :meth:`resolve` calls and request scopes.
        Intended for use in tests.

        Args:
            name: The provider name to override.
            value: The value to return whenever *name* is resolved.
        """
        with self._overrides_lock:
            self._overrides[name] = value

    def reset_overrides(self) -> None:
        """Clear all overrides, restoring normal provider resolution."""
        with self._overrides_lock:
            self._overrides.clear()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def init_eager(self, context: Optional[Any] = None) -> None:
        """
        Eagerly initialise all singleton providers marked ``eager=True``.

        Call this during application startup after all providers have been
        registered and before processing any requests.

        Args:
            context: Optional ``BrimleyContext`` forwarded to each eager provider.
        """
        with self._registry_lock:
            eager_names: List[str] = [
                name
                for name, meta in self._registry.items()
                if meta.scope == "singleton" and meta.eager
            ]

        for name in eager_names:
            self.resolve(name, context)

    def shutdown(self) -> None:
        """
        Tear down all singleton providers in reverse initialisation order.

        For each provider that returned a generator (yield-based teardown),
        ``next()`` is called to run the cleanup code after the ``yield``.
        """
        with self._registry_lock:
            generators = list(self._singleton_generators.items())

        # Reverse initialisation order for correct teardown dependency ordering
        for name, gen in reversed(generators):
            try:
                next(gen)
            except StopIteration:
                pass
            except Exception as exc:
                logger.warning(
                    "Exception during singleton teardown for provider '{}': {}",
                    name,
                    exc,
                )

        with self._registry_lock:
            self._singleton_generators.clear()
            self._singletons.clear()

    @contextmanager
    def request_scope(
        self,
        context: Optional[Any] = None,
    ) -> Generator[_RequestScope, None, None]:
        """
        Context manager that creates and tears down a request-scoped resolution context.

        Request-scoped providers get fresh instances per scope; singleton
        providers are still served from the shared cache.  On exit, all
        request-scoped generators are driven to completion in reverse order.

        Usage::

            with container.request_scope(context) as scope:
                value = scope.resolve("my_provider")

        Args:
            context: Optional ``BrimleyContext`` forwarded to providers.

        Yields:
            A :class:`_RequestScope` instance for the duration of the block.
        """
        scope = _RequestScope(self, context)
        try:
            yield scope
        finally:
            scope._teardown()

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    def has_provider(self, name: str) -> bool:
        """Return True if a provider named *name* is registered."""
        with self._registry_lock:
            return name in self._registry

    def provider_names(self) -> List[str]:
        """Return the list of all registered provider names (in registration order)."""
        with self._registry_lock:
            return list(self._registry.keys())
