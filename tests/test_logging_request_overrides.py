"""Tests for B06-S5: per-correlation_id log-level overrides."""
from __future__ import annotations

from brimley.infrastructure import logging as logging_infra


def _reset() -> None:
    with logging_infra._overrides_lock:
        logging_infra._correlation_overrides.clear()
    logging_infra._correlation_id.set("")


def _make_record(name: str, level_name: str, extra: dict | None = None) -> dict:
    return {
        "extra": dict(extra or {}),
        "name": name,
        "level": type("L", (), {"name": level_name})(),
    }


def test_set_correlation_level_override_stores_value() -> None:
    _reset()
    logging_infra.set_correlation_level_override("abc123", "DEBUG")
    overrides = logging_infra.get_correlation_overrides()
    assert overrides["abc123"] == "DEBUG"


def test_set_correlation_level_override_normalises_to_upper() -> None:
    _reset()
    logging_infra.set_correlation_level_override("abc123", "debug")
    assert logging_infra.get_correlation_overrides()["abc123"] == "DEBUG"


def test_clear_correlation_level_override_removes_entry() -> None:
    _reset()
    logging_infra.set_correlation_level_override("abc123", "DEBUG")
    logging_infra.clear_correlation_level_override("abc123")
    assert "abc123" not in logging_infra.get_correlation_overrides()


def test_clear_missing_override_is_noop() -> None:
    _reset()
    logging_infra.clear_correlation_level_override("nonexistent")  # should not raise


def test_get_correlation_overrides_returns_snapshot() -> None:
    _reset()
    logging_infra.set_correlation_level_override("cid1", "WARNING")
    snap = logging_infra.get_correlation_overrides()
    # Mutating the snapshot should not affect the internal store.
    snap["cid1"] = "TRACE"
    assert logging_infra.get_correlation_overrides()["cid1"] == "WARNING"


def test_filter_applies_per_correlation_override() -> None:
    _reset()
    logging_infra.set_correlation_id("req-debug")
    logging_infra.set_correlation_level_override("req-debug", "DEBUG")

    sink_filter = logging_infra._make_sink_filter("INFO", {})
    record = _make_record("brimley", "DEBUG", extra={"correlation_id": "req-debug"})
    assert sink_filter(record) is True


def test_filter_blocks_below_per_correlation_override() -> None:
    _reset()
    logging_infra.set_correlation_level_override("req-warn", "WARNING")

    sink_filter = logging_infra._make_sink_filter("INFO", {})
    record = _make_record("brimley", "INFO", extra={"correlation_id": "req-warn"})
    assert sink_filter(record) is False


def test_filter_unaffected_for_other_correlation_ids() -> None:
    _reset()
    logging_infra.set_correlation_level_override("special-cid", "DEBUG")

    sink_filter = logging_infra._make_sink_filter("INFO", {})
    record = _make_record("brimley", "DEBUG", extra={"correlation_id": "normal-cid"})
    assert sink_filter(record) is False
