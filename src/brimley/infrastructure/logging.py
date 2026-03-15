from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING

from loguru import logger as _logger

if TYPE_CHECKING:
    from brimley.core.context import BrimleyContext
    from brimley.core.models import LoggingSettings


DEFAULT_LOG_FORMAT = (
    "[{time:YYYY-MM-DD HH:mm:ss}] | {level: <8} | "
    "{name}:{function}:{line} - {message}"
)


def _resolve_log_path(path_value: str, root_dir: Path) -> Path:
    path = Path(path_value)
    if not path.is_absolute():
        path = root_dir / path
    return path


def initialize_logging(logging_settings: "LoggingSettings", *, root_dir: Path | None = None) -> None:
    """Configure Brimley-managed logging sinks using Loguru."""
    if not logging_settings.managed:
        return

    _logger.remove()
    _logger.add(sys.stderr, level=logging_settings.level, format=DEFAULT_LOG_FORMAT)

    if not logging_settings.file.path:
        return

    resolved_root = root_dir or Path.cwd()
    file_path = _resolve_log_path(logging_settings.file.path, resolved_root)
    file_path.parent.mkdir(parents=True, exist_ok=True)

    _logger.add(
        str(file_path),
        level=logging_settings.file.level,
        rotation=logging_settings.file.rotation,
        retention=logging_settings.file.retention,
        serialize=logging_settings.file.format == "jsonl",
    )


def initialize_logging_for_context(context: "BrimleyContext") -> None:
    """Configure logging for an initialized runtime context."""
    root_dir = Path(context.app.get("root_dir", Path.cwd()))
    initialize_logging(context.settings.logging, root_dir=root_dir)
