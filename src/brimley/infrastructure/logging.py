from __future__ import annotations

import logging
import sys
import threading
import uuid
from contextvars import ContextVar
from pathlib import Path
from typing import TYPE_CHECKING, Callable

from loguru import logger as _logger

if TYPE_CHECKING:
    from brimley.core.context import BrimleyContext
    from brimley.core.models import LoggingSettings


# ---------------------------------------------------------------------------
# Correlation / trace ContextVars
# ---------------------------------------------------------------------------

_correlation_id: ContextVar[str] = ContextVar("_correlation_id", default="")
_external_trace_id: ContextVar[str] = ContextVar("_external_trace_id", default="")

# Fixed correlation ID used during the startup sequence so startup-phase log
# records can be filtered separately from per-request records.
SYSTEM_BOOT_CORRELATION_ID: str = "system_boot"


def get_correlation_id() -> str:
    """Return the current correlation ID, or empty string if none is set."""
    return _correlation_id.get()


def get_or_create_correlation_id() -> str:
    """Return the current correlation ID, generating one if absent."""
    value = _correlation_id.get()
    if not value:
        value = uuid.uuid4().hex[:8]
        _correlation_id.set(value)
    return value


def set_correlation_id(value: str) -> None:
    """Explicitly set the correlation ID for the current context."""
    _correlation_id.set(value)


def get_external_trace_id() -> str:
    """Return the upstream trace ID (e.g. FastMCP request_id), or fall back to the local correlation ID."""
    ext = _external_trace_id.get()
    return ext if ext else get_or_create_correlation_id()


def set_external_trace_id(value: str) -> None:
    """Set the external trace ID sourced from the upstream provider (e.g. FastMCP request_id)."""
    _external_trace_id.set(value)


# ---------------------------------------------------------------------------
# Per-correlation level overrides (global dict, protected by a lock)
# ---------------------------------------------------------------------------

_correlation_overrides: dict[str, str] = {}
_overrides_lock = threading.Lock()


def set_correlation_level_override(correlation_id: str, level: str) -> None:
    """Set a temporary log-level override for a specific in-flight correlation ID."""
    with _overrides_lock:
        _correlation_overrides[correlation_id] = level.upper()


def clear_correlation_level_override(correlation_id: str) -> None:
    """Remove the log-level override for a specific correlation ID."""
    with _overrides_lock:
        _correlation_overrides.pop(correlation_id, None)


def get_correlation_overrides() -> dict[str, str]:
    """Return a snapshot of current per-correlation level overrides."""
    with _overrides_lock:
        return dict(_correlation_overrides)


# ---------------------------------------------------------------------------
# Module-level threshold filtering
# ---------------------------------------------------------------------------

_LEVEL_ORDER = ("TRACE", "DEBUG", "INFO", "SUCCESS", "WARNING", "ERROR", "CRITICAL")


def _module_threshold(logger_name: str, global_level: str, module_levels: dict[str, str]) -> str:
    """Return the effective level for *logger_name* using longest-prefix module matching."""
    threshold = global_level
    for module_name, module_level in sorted(module_levels.items(), key=lambda kv: len(kv[0]), reverse=True):
        if logger_name == module_name or logger_name.startswith(module_name + "."):
            threshold = module_level
            break
    return threshold


from brimley.utils.secrets import get_registered_secrets, redact_secrets


def _make_sink_filter(global_level: str, module_levels: dict[str, str]) -> Callable[[dict], bool]:
    """Create a Loguru sink filter that injects correlation IDs, applies level gating, and redacts secrets."""

    def _filter(record: dict) -> bool:
        # Inject context IDs into every log record.
        record["extra"].setdefault("correlation_id", get_or_create_correlation_id())
        record["extra"].setdefault("external_trace_id", get_external_trace_id())

        logger_name: str = record.get("name") or ""
        threshold = _module_threshold(logger_name, global_level, module_levels)

        # Check per-correlation override.
        cid: str = record["extra"].get("correlation_id", "")
        with _overrides_lock:
            if cid and cid in _correlation_overrides:
                threshold = _correlation_overrides[cid]

        current = record["level"].name
        try:
            passes = _LEVEL_ORDER.index(current) >= _LEVEL_ORDER.index(threshold)
        except ValueError:
            passes = True

        # Scrub registered secret values from the log message before it
        # reaches any sink (two-layer redaction — layer 1).
        if passes and cid:
            secret_values = get_registered_secrets(cid)
            if secret_values:
                record["message"] = redact_secrets(record["message"], secret_values)

        return passes

    return _filter


# ---------------------------------------------------------------------------
# Log format
# ---------------------------------------------------------------------------

DEFAULT_LOG_FORMAT = (
    "[{time:YYYY-MM-DD HH:mm:ss}] | {level: <8} | "
    "[ID: {extra[correlation_id]}] | "
    "{name}:{function}:{line} - {message}"
)


# ---------------------------------------------------------------------------
# Third-party logging interception
# ---------------------------------------------------------------------------

class InterceptHandler(logging.Handler):
    """Redirect stdlib *logging* records into the Loguru stream."""

    def emit(self, record: logging.LogRecord) -> None:
        """Forward a stdlib log record to Loguru preserving level and callsite."""
        try:
            level: str = _logger.level(record.levelname).name
        except ValueError:
            level = str(record.levelno)

        frame, depth = logging.currentframe(), 2
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back  # type: ignore[assignment]
            depth += 1

        _logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())


def install_intercept_handler(logger_names: list[str] | None = None) -> None:
    """Install :class:`InterceptHandler` on stdlib logging to route into Loguru.

    If *logger_names* is provided, only those named loggers are intercepted.
    Otherwise the root stdlib logger is configured.
    """
    handler = InterceptHandler()
    if logger_names:
        for name in logger_names:
            std_log = logging.getLogger(name)
            if not any(isinstance(h, InterceptHandler) for h in std_log.handlers):
                std_log.handlers = [handler]
                std_log.propagate = False
    else:
        root = logging.getLogger()
        if not any(isinstance(h, InterceptHandler) for h in root.handlers):
            root.handlers = [handler]
            root.setLevel(logging.DEBUG)


# ---------------------------------------------------------------------------
# Path helper
# ---------------------------------------------------------------------------

def _resolve_log_path(path_value: str, root_dir: Path) -> Path:
    path = Path(path_value)
    if not path.is_absolute():
        path = root_dir / path
    return path


# ---------------------------------------------------------------------------
# Public bootstrap API
# ---------------------------------------------------------------------------

def initialize_logging(
    logging_settings: "LoggingSettings",
    *,
    root_dir: Path | None = None,
    global_level_override: str | None = None,
    module_overrides: dict[str, str] | None = None,
) -> None:
    """Configure Brimley-managed logging sinks using Loguru.

    Args:
        logging_settings: The validated :class:`~brimley.core.models.LoggingSettings` instance.
        root_dir: Base directory for resolving relative file-sink paths.
        global_level_override: Optional CLI/runtime override for the global stderr level.
        module_overrides: Optional CLI/runtime per-module level overrides merged on top of config.
    """
    if not logging_settings.managed:
        return

    effective_level = (global_level_override or logging_settings.level).upper()
    merged_modules: dict[str, str] = {**logging_settings.modules, **(module_overrides or {})}

    _logger.remove()
    _logger.add(
        sys.stderr,
        level=effective_level,
        format=DEFAULT_LOG_FORMAT,
        filter=_make_sink_filter(effective_level, merged_modules),
    )

    if logging_settings.file.path:
        resolved_root = root_dir or Path.cwd()
        file_path = _resolve_log_path(logging_settings.file.path, resolved_root)
        file_path.parent.mkdir(parents=True, exist_ok=True)

        file_level = logging_settings.file.level
        _logger.add(
            str(file_path),
            level=file_level,
            rotation=logging_settings.file.rotation,
            retention=logging_settings.file.retention,
            serialize=logging_settings.file.format == "jsonl",
            filter=_make_sink_filter(file_level, merged_modules),
        )

    install_intercept_handler()


def initialize_logging_for_context(
    context: "BrimleyContext",
    *,
    global_level_override: str | None = None,
    module_overrides: dict[str, str] | None = None,
) -> None:
    """Configure logging for an initialized runtime context.

    Args:
        context: The active :class:`~brimley.core.context.BrimleyContext`.
        global_level_override: Optional runtime override for the global stderr level.
        module_overrides: Optional per-module level overrides merged on top of config.
    """
    root_dir = Path(context.app.get("root_dir", Path.cwd()))
    initialize_logging(
        context.settings.logging,
        root_dir=root_dir,
        global_level_override=global_level_override,
        module_overrides=module_overrides,
    )


def get_logger(depth: int = 0):
    """Return a Loguru logger instance pre-configured with ``opt(depth=depth)``.

    Use *depth* to skip wrapper call frames so that log records attribute to
    the caller's callsite rather than to the dispatcher or runner frame::

        # Inside a runner that wraps user-land code one level deep
        log = get_logger(depth=1)
        log.info("Executing user function")

    Args:
        depth: Number of additional call-stack frames to skip.

    Returns:
        A :mod:`loguru` logger with the given depth applied via
        :meth:`~loguru.Logger.opt`.
    """
    return _logger.opt(depth=depth)
