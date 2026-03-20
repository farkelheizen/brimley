"""Abstract base runner interface (Brimley 0.7, ADR-0002)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict

from brimley.core.models import BrimleyFunction
from brimley.core.context import BrimleyContext


class BaseRunner(ABC):
    """
    Abstract base class for all Brimley function runners.

    Ships as an internal-only interface in v0.7.  External plugin loading is
    deferred to v0.13 (ADR-0004).

    Implementors must provide:
    - ``can_handle`` – returns True if this runner handles the given function.
    - ``run`` – executes the function and returns its result.
    """

    @abstractmethod
    def can_handle(self, func: BrimleyFunction) -> bool:
        """Return True if this runner can execute the given function."""

    @abstractmethod
    def run(
        self,
        func: BrimleyFunction,
        args: Dict[str, Any],
        context: BrimleyContext,
    ) -> Any:
        """Execute the function and return its result."""
