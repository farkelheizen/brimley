"""Tests for B06-S6: third-party stdlib logging interception via InterceptHandler."""
from __future__ import annotations

import logging
import sys

from brimley.infrastructure import logging as logging_infra


class CapturingLogger:
    """Stub for _logger that records opt/log calls."""

    def __init__(self) -> None:
        self.remove_calls: int = 0
        self.add_calls: list[dict] = []
        self.logged: list[dict] = []
        self._opt_depth: int | None = None
        self._opt_exception: object = None

    def remove(self) -> None:
        self.remove_calls += 1

    def add(self, sink, **kwargs) -> int:
        self.add_calls.append({"sink": sink, **kwargs})
        return len(self.add_calls)

    def level(self, name: str):
        # Mimic Loguru level() return type.
        class _Level:
            pass

        obj = _Level()
        obj.name = name.upper()  # type: ignore[attr-defined]
        return obj

    def opt(self, *, depth: int = 0, exception: object = None):
        self._opt_depth = depth
        self._opt_exception = exception
        return self

    def log(self, level: str, message: str) -> None:
        self.logged.append({"level": level, "message": message})


def test_intercept_handler_emit_routes_to_loguru(monkeypatch) -> None:
    cap = CapturingLogger()
    monkeypatch.setattr(logging_infra, "_logger", cap)

    handler = logging_infra.InterceptHandler()
    record = logging.LogRecord(
        name="fastmcp",
        level=logging.INFO,
        pathname="fastmcp/server.py",
        lineno=42,
        msg="Server started",
        args=(),
        exc_info=None,
    )
    handler.emit(record)

    assert len(cap.logged) == 1
    assert cap.logged[0]["level"] == "INFO"
    assert "Server started" in cap.logged[0]["message"]


def test_intercept_handler_maps_warning_level(monkeypatch) -> None:
    cap = CapturingLogger()
    monkeypatch.setattr(logging_infra, "_logger", cap)

    handler = logging_infra.InterceptHandler()
    record = logging.LogRecord(
        name="sqlalchemy.engine",
        level=logging.WARNING,
        pathname="",
        lineno=0,
        msg="slow query",
        args=(),
        exc_info=None,
    )
    handler.emit(record)

    assert cap.logged[0]["level"] == "WARNING"


def test_install_intercept_handler_on_root(monkeypatch) -> None:
    # Remove any existing InterceptHandlers from root to start clean.
    root = logging.getLogger()
    root.handlers = [h for h in root.handlers if not isinstance(h, logging_infra.InterceptHandler)]

    logging_infra.install_intercept_handler()

    assert any(isinstance(h, logging_infra.InterceptHandler) for h in root.handlers)

    # Cleanup
    root.handlers = [h for h in root.handlers if not isinstance(h, logging_infra.InterceptHandler)]


def test_install_intercept_handler_idempotent(monkeypatch) -> None:
    root = logging.getLogger()
    root.handlers = [h for h in root.handlers if not isinstance(h, logging_infra.InterceptHandler)]

    logging_infra.install_intercept_handler()
    logging_infra.install_intercept_handler()  # second call should not add duplicate

    intercept_count = sum(1 for h in root.handlers if isinstance(h, logging_infra.InterceptHandler))
    assert intercept_count == 1

    # Cleanup
    root.handlers = [h for h in root.handlers if not isinstance(h, logging_infra.InterceptHandler)]


def test_install_intercept_handler_on_named_logger() -> None:
    test_log = logging.getLogger("fastmcp_test_isolated")
    test_log.handlers = []

    logging_infra.install_intercept_handler(logger_names=["fastmcp_test_isolated"])

    assert any(isinstance(h, logging_infra.InterceptHandler) for h in test_log.handlers)
    assert test_log.propagate is False

    # Cleanup
    test_log.handlers = []
    test_log.propagate = True


def test_install_intercept_handler_named_idempotent() -> None:
    test_log = logging.getLogger("fastmcp_named_idem")
    test_log.handlers = []

    logging_infra.install_intercept_handler(logger_names=["fastmcp_named_idem"])
    logging_infra.install_intercept_handler(logger_names=["fastmcp_named_idem"])

    count = sum(1 for h in test_log.handlers if isinstance(h, logging_infra.InterceptHandler))
    assert count == 1

    # Cleanup
    test_log.handlers = []
    test_log.propagate = True


def test_initialize_logging_installs_intercept_handler(monkeypatch, tmp_path) -> None:
    import sys as _sys

    fake_logger = type("FL", (), {
        "remove_calls": 0,
        "add_calls": [],
        "remove": lambda self: setattr(self, "remove_calls", self.remove_calls + 1),
        "add": lambda self, sink, **kw: self.add_calls.append({"sink": sink, **kw}) or len(self.add_calls),
    })()
    monkeypatch.setattr(logging_infra, "_logger", fake_logger)

    # Patch out install_intercept_handler to track it being called.
    called: list[bool] = []
    monkeypatch.setattr(logging_infra, "install_intercept_handler", lambda *a, **kw: called.append(True))

    from brimley.core.context import BrimleyContext

    ctx = BrimleyContext(config_dict={"brimley": {"logging": {"level": "info"}}})
    logging_infra.initialize_logging_for_context(ctx)

    assert called, "install_intercept_handler should have been called during initialization"
