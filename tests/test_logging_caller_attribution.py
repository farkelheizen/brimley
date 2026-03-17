"""Tests for B06-S8: caller attribution and dispatcher depth correctness."""
from __future__ import annotations

from brimley.infrastructure import logging as logging_infra


def test_get_logger_returns_loguru_opt_proxy() -> None:
    log = logging_infra.get_logger(depth=0)
    # The returned object must have a .info/.debug/.warning method (it's a Loguru proxy).
    assert callable(getattr(log, "info", None))
    assert callable(getattr(log, "debug", None))
    assert callable(getattr(log, "warning", None))


def test_get_logger_depth_zero_is_default() -> None:
    log_d0 = logging_infra.get_logger(depth=0)
    log_default = logging_infra.get_logger()
    # Both should be opt-proxies; we can't compare identity, but both should have the same attrs.
    assert type(log_d0).__name__ == type(log_default).__name__


def test_get_logger_with_positive_depth() -> None:
    log = logging_infra.get_logger(depth=2)
    # Should not raise; depth is passed through to Loguru.
    assert callable(getattr(log, "info", None))


def test_intercept_handler_traverses_logging_frames() -> None:
    """InterceptHandler should walk past stdlib logging frames to find user-land frame."""
    import logging

    class CapLogger:
        def __init__(self) -> None:
            self.opt_calls: list[dict] = []
            self.log_calls: list[dict] = []

        def level(self, name: str):
            obj = type("L", (), {"name": name.upper()})()
            return obj

        def opt(self, *, depth: int = 0, exception: object = None):
            self.opt_calls.append({"depth": depth, "exception": exception})
            return self

        def log(self, level: str, message: str) -> None:
            self.log_calls.append({"level": level, "message": message})

    import sys
    cap = CapLogger()

    # Temporarily patch _logger
    original = logging_infra._logger
    try:
        import brimley.infrastructure.logging as _mod
        _mod._logger = cap  # type: ignore[assignment]

        handler = logging_infra.InterceptHandler()
        record = logging.LogRecord(
            name="mylib",
            level=logging.INFO,
            pathname="mylib/module.py",
            lineno=10,
            msg="attribution test",
            args=(),
            exc_info=None,
        )
        handler.emit(record)

        assert len(cap.log_calls) == 1
        # depth should be >= 2 (at least past logging.currentframe and one extra step)
        assert cap.opt_calls[0]["depth"] >= 2
    finally:
        _mod._logger = original  # type: ignore[assignment]
