from __future__ import annotations

import importlib
from typing import Any

import pytest

from brimley.core.context import BrimleyContext
from brimley.core.models import PythonFunction


def _load_execute_helper_module():
    try:
        return importlib.import_module("brimley.execution.execute_helper")
    except ModuleNotFoundError as error:
        pytest.fail(
            "Missing module 'brimley.execution.execute_helper' required by execute-function-helper contract tests. "
            "Implement EFH-P2-S1 to satisfy this test-first contract.",
            pytrace=False,
        )


def _register_child(context: BrimleyContext, name: str = "child_task") -> PythonFunction:
    child = PythonFunction(
        name=name,
        type="python_function",
        return_shape="dict",
        handler="pkg.mod.child",
    )
    context.functions.register(child)
    return child


def test_execute_function_helper_success_path(monkeypatch: pytest.MonkeyPatch) -> None:
    execute_helper_module = _load_execute_helper_module()
    execute_function_by_name = execute_helper_module.execute_function_by_name

    context = BrimleyContext()
    child = _register_child(context)

    calls: dict[str, Any] = {}

    def fake_resolve(func, user_input, ctx):
        calls["resolved_func"] = func
        calls["resolved_input"] = user_input
        calls["resolved_ctx"] = ctx
        return {"resolved": True}

    class FakeDispatcher:
        def run(self, func, args, ctx, runtime_injections=None):
            calls["ran_func"] = func
            calls["ran_args"] = args
            calls["ran_ctx"] = ctx
            calls["ran_runtime_injections"] = runtime_injections
            return {"ok": True}

    monkeypatch.setattr(execute_helper_module.ArgumentResolver, "resolve", fake_resolve)
    monkeypatch.setattr(execute_helper_module, "Dispatcher", FakeDispatcher)

    runtime_injections = {"mcp_context": object()}

    result = execute_function_by_name(
        context=context,
        function_name="child_task",
        input_data={"name": "Ada"},
        runtime_injections=runtime_injections,
    )

    assert result == {"ok": True}
    assert calls["resolved_func"] is child
    assert calls["resolved_input"] == {"name": "Ada"}
    assert calls["resolved_ctx"] is context
    assert calls["ran_func"] is child
    assert calls["ran_args"] == {"resolved": True}
    assert calls["ran_ctx"] is context
    assert calls["ran_runtime_injections"] is runtime_injections


def test_execute_function_helper_function_not_found() -> None:
    execute_helper_module = _load_execute_helper_module()
    execute_function_by_name = execute_helper_module.execute_function_by_name

    context = BrimleyContext()

    with pytest.raises(KeyError) as error:
        execute_function_by_name(
            context=context,
            function_name="missing_task",
            input_data={},
        )

    assert "missing_task" in str(error.value)


def test_execute_function_helper_argument_resolution_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    execute_helper_module = _load_execute_helper_module()
    execute_function_by_name = execute_helper_module.execute_function_by_name

    context = BrimleyContext()
    _register_child(context)

    def fake_resolve(func, user_input, ctx):
        raise ValueError("Missing required argument: 'user_id'")

    monkeypatch.setattr(execute_helper_module.ArgumentResolver, "resolve", fake_resolve)

    with pytest.raises(ValueError) as error:
        execute_function_by_name(
            context=context,
            function_name="child_task",
            input_data={},
        )

    assert "Missing required argument" in str(error.value)


def test_execute_function_helper_dispatch_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    execute_helper_module = _load_execute_helper_module()
    execute_function_by_name = execute_helper_module.execute_function_by_name

    context = BrimleyContext()
    _register_child(context)

    def fake_resolve(func, user_input, ctx):
        return {"resolved": True}

    class FakeDispatcher:
        def run(self, func, args, ctx, runtime_injections=None):
            raise RuntimeError("child runtime failed")

    monkeypatch.setattr(execute_helper_module.ArgumentResolver, "resolve", fake_resolve)
    monkeypatch.setattr(execute_helper_module, "Dispatcher", FakeDispatcher)

    with pytest.raises(RuntimeError) as error:
        execute_function_by_name(
            context=context,
            function_name="child_task",
            input_data={"x": 1},
        )

    assert "child runtime failed" in str(error.value)
