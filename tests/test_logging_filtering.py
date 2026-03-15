"""Tests for B06-S4: module-level threshold filtering with longest-prefix matching."""
from __future__ import annotations

import pytest

from brimley.infrastructure import logging as logging_infra


def _make_record(name: str, level_name: str, extra: dict | None = None) -> dict:
    """Build a minimal Loguru-style record dict for filter testing."""
    return {
        "extra": dict(extra or {}),
        "name": name,
        "level": type("L", (), {"name": level_name})(),
    }


class TestModuleThreshold:
    def test_returns_global_level_when_no_module_match(self) -> None:
        result = logging_infra._module_threshold("brimley.execution", "INFO", {})
        assert result == "INFO"

    def test_exact_module_match(self) -> None:
        modules = {"brimley.execution": "DEBUG"}
        result = logging_infra._module_threshold("brimley.execution", "INFO", modules)
        assert result == "DEBUG"

    def test_prefix_module_match(self) -> None:
        modules = {"brimley.execution": "DEBUG"}
        result = logging_infra._module_threshold("brimley.execution.dispatcher", "INFO", modules)
        assert result == "DEBUG"

    def test_longest_prefix_wins(self) -> None:
        modules = {
            "brimley": "WARNING",
            "brimley.execution": "DEBUG",
            "brimley.execution.dispatcher": "TRACE",
        }
        result = logging_infra._module_threshold("brimley.execution.dispatcher", "INFO", modules)
        assert result == "TRACE"

    def test_shorter_prefix_does_not_match_sibling(self) -> None:
        modules = {"brimley.execution": "DEBUG"}
        result = logging_infra._module_threshold("brimley.mcp", "INFO", modules)
        assert result == "INFO"

    def test_no_partial_word_match(self) -> None:
        modules = {"brimley.exec": "DEBUG"}
        result = logging_infra._module_threshold("brimley.execution", "INFO", modules)
        assert result == "INFO"

    def test_empty_module_name_uses_global(self) -> None:
        modules = {"brimley": "DEBUG"}
        result = logging_infra._module_threshold("", "WARNING", modules)
        assert result == "WARNING"


class TestSinkFilter:
    def _filter(self, global_level: str, modules: dict, record: dict) -> bool:
        f = logging_infra._make_sink_filter(global_level, modules)
        return f(record)

    def test_passes_record_at_global_level(self) -> None:
        record = _make_record("brimley", "INFO")
        assert self._filter("INFO", {}, record) is True

    def test_blocks_record_below_global_level(self) -> None:
        record = _make_record("brimley", "DEBUG")
        assert self._filter("INFO", {}, record) is False

    def test_module_override_allows_lower_level(self) -> None:
        record = _make_record("brimley.execution", "DEBUG")
        assert self._filter("INFO", {"brimley.execution": "DEBUG"}, record) is True

    def test_module_override_blocks_below_module_level(self) -> None:
        record = _make_record("brimley.execution", "TRACE")
        assert self._filter("INFO", {"brimley.execution": "DEBUG"}, record) is False

    def test_sibling_module_not_affected_by_override(self) -> None:
        record = _make_record("brimley.mcp", "DEBUG")
        assert self._filter("INFO", {"brimley.execution": "DEBUG"}, record) is False

    def test_unknown_level_passes_through(self) -> None:
        record = _make_record("brimley", "UNKNOWN_LEVEL")
        assert self._filter("INFO", {}, record) is True

    def test_success_level_passes_at_info_threshold(self) -> None:
        record = _make_record("brimley", "SUCCESS")
        assert self._filter("INFO", {}, record) is True
