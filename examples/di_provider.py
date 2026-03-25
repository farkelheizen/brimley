"""Example demonstrating Brimley 0.8 dependency injection with @provider and Depends().

This file shows:
- A singleton provider using yield-based setup/teardown
- An @on_startup lifecycle hook
- A @function that receives an injected dependency via Depends()
"""
from __future__ import annotations

from typing import Generator

from loguru import logger

from brimley import BrimleyContext, Depends, function, on_startup, provider


# ---------------------------------------------------------------------------
# Provider: a simple in-memory counter object used as a managed dependency
# ---------------------------------------------------------------------------

class RequestCounter:
    """Tracks the number of function invocations during a session."""

    def __init__(self) -> None:
        self._count = 0

    def increment(self) -> int:
        self._count += 1
        return self._count

    @property
    def total(self) -> int:
        return self._count


@provider(name="request_counter", scope="singleton", eager=True)
def provide_request_counter() -> Generator[RequestCounter, None, None]:
    """Creates a RequestCounter singleton and logs teardown on shutdown."""
    counter = RequestCounter()
    logger.info("RequestCounter provider initialized")
    yield counter
    logger.info("RequestCounter provider torn down (total calls: {})", counter.total)


# ---------------------------------------------------------------------------
# Lifecycle hook: runs after all singletons are ready
# ---------------------------------------------------------------------------

@on_startup
def log_ready(ctx: BrimleyContext) -> None:
    """Logs a startup message once DI initialisation is complete."""
    logger.info("DI startup complete — application is ready")


# ---------------------------------------------------------------------------
# Function: receives the counter via Depends() rather than user-supplied args
# ---------------------------------------------------------------------------

@function(name="greet_with_counter", mcpType="tool")
def greet_with_counter(
    name: str,
    counter: RequestCounter = Depends("request_counter"),
) -> str:
    """Greets a user and returns a message including the current invocation count.

    Args:
        name: The name to greet.
        counter: Injected by the DI container — do not supply this argument.

    Returns:
        A greeting string that includes the invocation number.
    """
    n = counter.increment()
    greeting = f"Hello, {name}! (invocation #{n})"
    logger.info("greet_with_counter called by '{}', invocation #{}", name, n)
    return greeting
