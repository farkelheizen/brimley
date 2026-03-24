"""
DependencyResolver: topological sort, cycle detection, and BrimleyContext
injection for Brimley 0.8's dependency injection system.

Introduced in Brimley 0.8 (B08-S5).
"""

from __future__ import annotations

import inspect
from typing import Any, Dict, List, Optional, Set

from brimley.core.container import BrimleyContainer, ProviderResolutionError


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class CircularDependencyError(Exception):
    """Raised when a circular dependency is detected in the provider graph."""


# ---------------------------------------------------------------------------
# Resolver
# ---------------------------------------------------------------------------


class DependencyResolver:
    """
    Resolves provider dependency order using DFS-based topological sort.

    Works in conjunction with :class:`BrimleyContainer` to:

    * Build the directed acyclic graph (DAG) of provider ``Depends()``
      relationships.
    * Return providers in the order they must be initialised (dependencies
      first).
    * Detect circular dependencies early—at startup, before any provider is
      called—so failures are deterministic and easy to diagnose.
    * Recognise ``BrimleyContext``-typed parameters as injected (not
      treated as provider dependencies in the graph).

    Introduced in Brimley 0.8.
    """

    def __init__(self, container: BrimleyContainer) -> None:
        self._container = container

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def topological_sort(self, names: Optional[List[str]] = None) -> List[str]:
        """
        Return *names* in dependency-first order (safe initialisation sequence).

        If *names* is ``None``, all registered providers are sorted.

        Args:
            names: Provider names to sort.  Transitive dependencies that are
                   not in *names* but are registered in the container are
                   included automatically.

        Returns:
            A list of provider names, dependencies preceding dependants.

        Raises:
            CircularDependencyError: If a cycle is detected.
            ProviderResolutionError: If a dependency references an unregistered
                provider name.
        """
        if names is None:
            with self._container._registry_lock:
                names = list(self._container._registry.keys())

        result: List[str] = []
        visited: Set[str] = set()
        # Tracks visitation path in order (list for ordered iteration)
        path: List[str] = []
        path_set: Set[str] = set()

        def visit(name: str) -> None:
            if name in path_set:
                # Reconstruct the cycle segment from the current path
                cycle_start = path.index(name)
                cycle_path = " -> ".join(path[cycle_start:]) + f" -> {name}"
                raise CircularDependencyError(
                    f"Circular dependency detected involving '{name}'. "
                    f"Cycle: {cycle_path}"
                )
            if name in visited:
                return

            # Validate the provider is registered (not just a missing Depends target)
            if not self._container.has_provider(name):
                raise ProviderResolutionError(
                    f"Provider '{name}' is referenced as a dependency but is not "
                    "registered in the container."
                )

            path.append(name)
            path_set.add(name)
            for dep in self._get_dependencies(name):
                visit(dep)
            path.pop()
            path_set.discard(name)
            visited.add(name)
            result.append(name)

        for name in names:
            visit(name)

        return result

    def detect_cycles(self, names: Optional[List[str]] = None) -> None:
        """
        Validate that the provider dependency graph is acyclic.

        Args:
            names: Subset of provider names to check.  Defaults to all
                   registered providers.

        Raises:
            CircularDependencyError: If any cycle is found.
        """
        self.topological_sort(names)  # raises on first cycle

    def get_dependencies(self, name: str) -> List[str]:
        """
        Return the direct provider dependencies of *name*.

        ``BrimleyContext``-annotated parameters and parameters without
        ``Depends()`` defaults are excluded—they are not provider dependencies.

        Args:
            name: A registered provider name.

        Returns:
            A (possibly empty) list of provider name strings.

        Raises:
            ProviderResolutionError: If *name* is not registered or its handler
                cannot be imported.
        """
        return self._get_dependencies(name)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _get_dependencies(self, name: str) -> List[str]:
        """
        Inspect the provider function's signature and return names of all
        ``Depends()`` dependencies, excluding ``BrimleyContext`` parameters.

        Handles PEP 563 (``from __future__ import annotations``) string
        annotations via ``typing.get_type_hints`` where possible.
        """
        import typing
        from brimley.core.di import Depends  # local import avoids circularity

        with self._container._registry_lock:
            metadata = self._container._registry.get(name)

        if metadata is None:
            return []

        handler_path = metadata.handler or f"{metadata.module_path}.{metadata.func_name}"
        try:
            fn = self._container._import_handler(handler_path)
        except ProviderResolutionError:
            return []

        try:
            sig = inspect.signature(fn)
        except (ValueError, TypeError):
            return []

        # Attempt to resolve stringified annotations (PEP 563)
        try:
            resolved_hints: Dict[str, Any] = typing.get_type_hints(fn)
        except Exception:
            resolved_hints = {}

        deps: List[str] = []
        for param in sig.parameters.values():
            annotation = resolved_hints.get(param.name, param.annotation)
            # Skip BrimleyContext parameters—they are injected, not provider deps
            if BrimleyContainer._is_context_annotation(annotation):
                continue
            if isinstance(param.default, Depends):
                deps.append(param.default.provider_name)

        return deps
