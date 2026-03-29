"""
Human-readable duration and retry interval parser for Brimley task scheduling.

Introduced in Brimley v0.9 (B09-S3).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional


# ---------------------------------------------------------------------------
# Duration parsing
# ---------------------------------------------------------------------------

_DURATION_PATTERN = re.compile(
    r"""
    (?:(\d+(?:\.\d+)?)\s*h)?   # hours
    \s*
    (?:(\d+(?:\.\d+)?)\s*m(?!s))?  # minutes (not ms)
    \s*
    (?:(\d+(?:\.\d+)?)\s*s)?   # seconds
    \s*
    (?:(\d+(?:\.\d+)?)\s*ms)?  # milliseconds
    """,
    re.VERBOSE | re.IGNORECASE,
)


def parse_duration(value: str) -> float:
    """Parse a human-readable duration string into total seconds (float).

    Supported units:
    - ``ms`` — milliseconds
    - ``s``  — seconds
    - ``m``  — minutes
    - ``h``  — hours

    Multiple units may be combined: ``"1h 30m 15s"``.

    Examples::

        parse_duration("30s")       # → 30.0
        parse_duration("5m")        # → 300.0
        parse_duration("1h 30m")    # → 5400.0
        parse_duration("500ms")     # → 0.5
        parse_duration("1h 30m 15s 500ms")  # → 5415.5

    Raises:
        ValueError: if the string is empty, unparseable, or all components are zero.
    """
    text = value.strip()
    if not text:
        raise ValueError("Duration string must not be empty.")

    # Validate that the string contains only known tokens
    # Strip all valid tokens and check what remains.
    stripped = re.sub(
        r"\d+(?:\.\d+)?\s*(?:ms|[hms])\b",
        "",
        text,
        flags=re.IGNORECASE,
    ).strip()
    if stripped:
        raise ValueError(
            f"Unrecognised tokens in duration string {value!r}: {stripped!r}. "
            "Expected units: h, m, s, ms."
        )

    hours = _extract_unit(text, r"(\d+(?:\.\d+)?)\s*h(?!r)(?!\w)", "hours")
    minutes = _extract_unit(text, r"(\d+(?:\.\d+)?)\s*m(?!s)(?!\w)", "minutes")
    seconds = _extract_unit(text, r"(\d+(?:\.\d+)?)\s*s(?!\w)", "seconds")
    millis = _extract_unit(text, r"(\d+(?:\.\d+)?)\s*ms(?!\w)", "milliseconds")

    total = hours * 3600.0 + minutes * 60.0 + seconds + millis / 1000.0

    if total < 0:
        raise ValueError(f"Duration must not be negative, got: {total}s from {value!r}.")

    return total


def _extract_unit(text: str, pattern: str, label: str) -> float:
    """Extract a single time unit from the text using a regex pattern."""
    matches = re.findall(pattern, text, re.IGNORECASE)
    if not matches:
        return 0.0
    if len(matches) > 1:
        raise ValueError(
            f"Duplicate {label} component in duration string {text!r}."
        )
    return float(matches[0])


# ---------------------------------------------------------------------------
# Retry interval parsing
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class RetryIntervalConfig:
    """Parsed retry interval configuration.

    Attributes:
        base: Base retry delay in seconds.
        strategy: One of ``"fixed"``, ``"exponential"``, or ``"multiplier"``.
        factor: Multiplier for the ``"multiplier"`` strategy (e.g. 1.5).
    """

    base: float
    strategy: str  # "fixed" | "exponential" | "multiplier"
    factor: Optional[float] = None  # only for "multiplier"


_MULTIPLIER_SUFFIX = re.compile(r"^x(\d+(?:\.\d+)?)$", re.IGNORECASE)


def parse_retry_interval(value: str) -> RetryIntervalConfig:
    """Parse a retry_interval string into a :class:`RetryIntervalConfig`.

    Supported formats:

    - ``"10s"``              → fixed, base=10.0
    - ``"10s exponential"`` or ``"10s ex"``  → exponential, base=10.0
    - ``"10s x1.5"``         → multiplier, base=10.0, factor=1.5

    The base duration is parsed by :func:`parse_duration` and supports all
    unit combinations (``h``, ``m``, ``s``, ``ms``), including multi-unit
    expressions like ``"1h 30m"``.

    Raises:
        ValueError: if the string is malformed or the base is negative.
    """
    text = value.strip()
    if not text:
        raise ValueError("retry_interval string must not be empty.")

    # Detect strategy suffix by inspecting the last whitespace-delimited token.
    tokens = text.split()
    last = tokens[-1]

    if last.lower() in ("exponential", "ex"):
        base_str = " ".join(tokens[:-1]) if len(tokens) > 1 else ""
        if not base_str:
            raise ValueError(
                f"retry_interval {value!r} has no base duration before the strategy suffix."
            )
        base = parse_duration(base_str)
        return RetryIntervalConfig(base=base, strategy="exponential")

    m = _MULTIPLIER_SUFFIX.match(last)
    if m:
        base_str = " ".join(tokens[:-1]) if len(tokens) > 1 else ""
        if not base_str:
            raise ValueError(
                f"retry_interval {value!r} has no base duration before the strategy suffix."
            )
        base = parse_duration(base_str)
        factor = float(m.group(1))
        if factor <= 0:
            raise ValueError(
                f"Multiplier factor must be positive, got {factor!r} in {value!r}."
            )
        return RetryIntervalConfig(base=base, strategy="multiplier", factor=factor)

    # No recognised strategy suffix — the entire string is the base duration.
    base = parse_duration(text)
    return RetryIntervalConfig(base=base, strategy="fixed")
