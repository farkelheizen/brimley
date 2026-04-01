"""Tests for TaskConfig model and PythonFunction task field (B09-S4)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from brimley.core.models import PythonFunction, TaskConfig


# ---------------------------------------------------------------------------
# TaskConfig model validation
# ---------------------------------------------------------------------------


class TestTaskConfig:
    def test_interval_only_valid(self) -> None:
        tc = TaskConfig(interval="5m")
        assert tc.interval == "5m"
        assert tc.immediate is False
        assert tc.retries is None
        assert tc.retry_interval == "1s exponential"

    def test_all_fields(self) -> None:
        tc = TaskConfig(
            interval="1h",
            immediate=True,
            retries=3,
            retry_interval="10s x1.5",
        )
        assert tc.immediate is True
        assert tc.retries == 3
        assert tc.retry_interval == "10s x1.5"

    def test_retries_zero_is_valid(self) -> None:
        tc = TaskConfig(interval="1m", retries=0)
        assert tc.retries == 0

    def test_retries_none_means_unlimited(self) -> None:
        tc = TaskConfig(interval="1m", retries=None)
        assert tc.retries is None

    def test_interval_empty_rejected(self) -> None:
        with pytest.raises(ValidationError, match="too_short|min_length"):
            TaskConfig(interval="")

    def test_retries_negative_rejected(self) -> None:
        with pytest.raises(ValidationError):
            TaskConfig(interval="1m", retries=-1)

    def test_extra_fields_rejected(self) -> None:
        with pytest.raises(ValidationError):
            TaskConfig(interval="1m", unknown_field="x")

    def test_interval_missing_rejected(self) -> None:
        with pytest.raises(ValidationError):
            TaskConfig()

    def test_equality(self) -> None:
        a = TaskConfig(interval="5m", immediate=True)
        b = TaskConfig(interval="5m", immediate=True)
        assert a == b

    def test_inequality_different_interval(self) -> None:
        a = TaskConfig(interval="5m")
        b = TaskConfig(interval="10m")
        assert a != b


# ---------------------------------------------------------------------------
# PythonFunction with task field
# ---------------------------------------------------------------------------


class TestPythonFunctionTaskField:
    def _make_func(self, **extra) -> PythonFunction:
        return PythonFunction(
            name="my_func",
            type="python_function",
            return_shape="void",
            **extra,
        )

    def test_task_field_defaults_to_none(self) -> None:
        fn = self._make_func()
        assert fn.task is None

    def test_task_field_populated(self) -> None:
        tc = TaskConfig(interval="5m")
        fn = self._make_func(task=tc)
        assert fn.task is not None
        assert fn.task.interval == "5m"

    def test_task_field_distinguishes_task_from_non_task(self) -> None:
        plain = self._make_func()
        task_fn = self._make_func(task=TaskConfig(interval="1m"))
        assert plain.task is None
        assert task_fn.task is not None

    def test_task_field_round_trips_via_dict(self) -> None:
        tc = TaskConfig(interval="30s", immediate=True, retries=2)
        fn = self._make_func(task=tc)
        data = fn.model_dump()
        assert data["task"]["interval"] == "30s"
        assert data["task"]["immediate"] is True
        assert data["task"]["retries"] == 2
