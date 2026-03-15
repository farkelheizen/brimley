"""Tests for B06-S3: correlation_id and external_trace_id context propagation."""
from __future__ import annotations

from brimley.core.context import BrimleyContext
from brimley.infrastructure import logging as logging_infra


def _reset_context_vars() -> None:
    logging_infra._correlation_id.set("")
    logging_infra._external_trace_id.set("")


def test_get_or_create_correlation_id_generates_id() -> None:
    _reset_context_vars()
    cid = logging_infra.get_or_create_correlation_id()
    assert isinstance(cid, str)
    assert len(cid) == 8


def test_get_or_create_correlation_id_is_stable() -> None:
    _reset_context_vars()
    first = logging_infra.get_or_create_correlation_id()
    second = logging_infra.get_or_create_correlation_id()
    assert first == second


def test_set_correlation_id_overrides_generated() -> None:
    _reset_context_vars()
    logging_infra.set_correlation_id("deadbeef")
    assert logging_infra.get_correlation_id() == "deadbeef"
    assert logging_infra.get_or_create_correlation_id() == "deadbeef"


def test_get_external_trace_id_falls_back_to_correlation() -> None:
    _reset_context_vars()
    logging_infra.set_correlation_id("aabbccdd")
    ext = logging_infra.get_external_trace_id()
    assert ext == "aabbccdd"


def test_get_external_trace_id_returns_upstream_when_set() -> None:
    _reset_context_vars()
    logging_infra.set_correlation_id("localcid")
    logging_infra.set_external_trace_id("trace-from-upstream")
    assert logging_infra.get_external_trace_id() == "trace-from-upstream"


def test_brimley_context_correlation_id_property() -> None:
    _reset_context_vars()
    logging_infra.set_correlation_id("ctx-prop-1")
    ctx = BrimleyContext()
    assert ctx.correlation_id == "ctx-prop-1"


def test_brimley_context_external_trace_id_property() -> None:
    _reset_context_vars()
    logging_infra.set_correlation_id("ctx-cid")
    logging_infra.set_external_trace_id("ctx-ext-trace")
    ctx = BrimleyContext()
    assert ctx.external_trace_id == "ctx-ext-trace"


def test_brimley_context_external_trace_id_fallback() -> None:
    _reset_context_vars()
    logging_infra.set_correlation_id("fallback-cid")
    ctx = BrimleyContext()
    assert ctx.external_trace_id == "fallback-cid"


def test_sink_filter_injects_correlation_id_into_record() -> None:
    _reset_context_vars()
    logging_infra.set_correlation_id("filter-cid")

    sink_filter = logging_infra._make_sink_filter("DEBUG", {})

    # Simulate a Loguru-style record dict.
    record: dict = {
        "extra": {},
        "name": "brimley.test",
        "level": type("L", (), {"name": "INFO"})(),
    }
    result = sink_filter(record)
    assert result is True
    assert record["extra"]["correlation_id"] == "filter-cid"


def test_sink_filter_does_not_overwrite_existing_correlation_id() -> None:
    _reset_context_vars()
    logging_infra.set_correlation_id("outer-cid")

    sink_filter = logging_infra._make_sink_filter("DEBUG", {})
    record: dict = {
        "extra": {"correlation_id": "inner-cid"},
        "name": "brimley.test",
        "level": type("L", (), {"name": "INFO"})(),
    }
    sink_filter(record)
    # setdefault should not overwrite an already-set value.
    assert record["extra"]["correlation_id"] == "inner-cid"
