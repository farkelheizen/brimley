"""Tests for MCP registration of API and CLI functions (Brimley 0.7, B07-S8)."""

from __future__ import annotations

import inspect
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from brimley.core.context import BrimleyContext
from brimley.core.models import ApiFunction, CliFunction
from brimley.mcp.fastmcp_provider import BrimleyProvider


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_api_func(**kwargs: Any) -> ApiFunction:
    defaults = {
        "name": "github_profile",
        "type": "api_function",
        "description": "Fetch GitHub user profile",
        "return_shape": "primitive",
        "request": {"url": "https://api.github.com/users/{{ username }}", "method": "GET"},
        "mcp": {"type": "tool"},
        "arguments": {"inline": {"username": {"type": "string", "description": "GitHub username"}}},
    }
    defaults.update(kwargs)
    return ApiFunction(**defaults)


def _make_cli_func(**kwargs: Any) -> CliFunction:
    defaults = {
        "name": "system_load",
        "type": "cli_function",
        "description": "Get system load average",
        "return_shape": "string",
        "command": "uptime",
        "timeout_seconds": 10.0,
        "mcp": {"type": "tool"},
    }
    defaults.update(kwargs)
    return CliFunction(**defaults)


# ---------------------------------------------------------------------------
# B07-S8: discover_tools includes API and CLI functions
# ---------------------------------------------------------------------------


def test_discover_tools_includes_api_function_with_mcp_tool() -> None:
    context = BrimleyContext()
    func = _make_api_func()
    context.functions.register(func)

    provider = BrimleyProvider(registry=context.functions, context=context)
    tools = provider.discover_tools()

    assert len(tools) == 1
    assert tools[0].name == "github_profile"
    assert tools[0].type == "api_function"


def test_discover_tools_includes_cli_function_with_mcp_tool() -> None:
    context = BrimleyContext()
    func = _make_cli_func()
    context.functions.register(func)

    provider = BrimleyProvider(registry=context.functions, context=context)
    tools = provider.discover_tools()

    assert len(tools) == 1
    assert tools[0].name == "system_load"
    assert tools[0].type == "cli_function"


def test_discover_tools_excludes_api_function_without_mcp() -> None:
    context = BrimleyContext()
    func = ApiFunction(
        name="no_mcp_api",
        type="api_function",
        return_shape="string",
        request={"url": "https://example.com"},
    )
    context.functions.register(func)

    provider = BrimleyProvider(registry=context.functions, context=context)
    tools = provider.discover_tools()

    assert len(tools) == 0


def test_discover_tools_mixed_types_all_included() -> None:
    from brimley.core.models import TemplateFunction

    context = BrimleyContext()
    context.functions.register(_make_api_func())
    context.functions.register(_make_cli_func())
    context.functions.register(
        TemplateFunction(
            name="hello",
            type="template_function",
            return_shape="string",
            template_body="Hello",
            mcp={"type": "tool"},
        )
    )

    provider = BrimleyProvider(registry=context.functions, context=context)
    tools = provider.discover_tools()

    names = {t.name for t in tools}
    assert names == {"github_profile", "system_load", "hello"}


# ---------------------------------------------------------------------------
# B07-S8: build_tool_input_model generates correct schema for API/CLI
# ---------------------------------------------------------------------------


def test_build_tool_input_model_api_function_with_arguments() -> None:
    context = BrimleyContext()
    func = _make_api_func()
    provider = BrimleyProvider(registry=context.functions, context=context)

    model = provider.build_tool_input_model(func)
    schema = model.model_json_schema()

    assert "username" in schema.get("properties", {})
    # secrets and from_context fields must NOT be exposed in tool schema
    assert "secrets" not in schema.get("properties", {})


def test_build_tool_input_model_api_function_no_arguments() -> None:
    context = BrimleyContext()
    func = ApiFunction(
        name="ping",
        type="api_function",
        return_shape="string",
        request={"url": "https://example.com/ping"},
        mcp={"type": "tool"},
    )
    provider = BrimleyProvider(registry=context.functions, context=context)

    model = provider.build_tool_input_model(func)
    schema = model.model_json_schema()

    # No required user arguments — schema should have empty properties
    assert schema.get("properties", {}) == {}


def test_build_tool_input_model_cli_function_excludes_from_context() -> None:
    context = BrimleyContext()
    func = _make_cli_func(
        arguments={
            "inline": {
                "debug": {"type": "bool", "description": "Enable debug"},
                "root_dir": {"type": "string", "from_context": "app.root_dir"},
            }
        }
    )
    provider = BrimleyProvider(registry=context.functions, context=context)

    model = provider.build_tool_input_model(func)
    schema = model.model_json_schema()

    # "debug" should appear; "root_dir" (from_context) must NOT appear
    assert "debug" in schema.get("properties", {})
    assert "root_dir" not in schema.get("properties", {})


# ---------------------------------------------------------------------------
# B07-S8: create_tool_wrapper dispatches correctly for API/CLI functions
# ---------------------------------------------------------------------------


def test_create_tool_wrapper_api_function_is_sync_callable() -> None:
    """API functions are dispatched synchronously via ThreadPoolExecutor."""
    context = BrimleyContext()
    func = _make_api_func()
    context.functions.register(func)

    provider = BrimleyProvider(registry=context.functions, context=context)
    wrapper = provider.create_tool_wrapper(func)

    # API functions use sync wrapper (runners manage async internally)
    assert callable(wrapper)


def test_create_tool_wrapper_cli_function_dispatches_to_runner() -> None:
    context = BrimleyContext()
    func = _make_cli_func()
    context.functions.register(func)

    provider = BrimleyProvider(registry=context.functions, context=context)
    provider.execute_tool_by_name = lambda fn, args, runtime_injections=None: f"cli-result-{fn}"  # type: ignore[method-assign]

    wrapper = provider.create_tool_wrapper(func)
    result = wrapper()

    assert result == "cli-result-system_load"


def test_execute_tool_by_name_api_function_dispatches_correctly() -> None:
    context = BrimleyContext()
    func = _make_api_func()
    context.functions.register(func)

    provider = BrimleyProvider(registry=context.functions, context=context)

    captured: dict = {}

    def fake_run(f, resolved_args, ctx):
        captured["func"] = f
        captured["args"] = resolved_args
        return "api-response"

    provider.dispatcher.api_runner.run = fake_run  # type: ignore[method-assign]

    result = provider.execute_tool_by_name("github_profile", {"username": "alice"})
    assert result == "api-response"
    assert captured["func"] is func


def test_execute_tool_by_name_cli_function_dispatches_correctly() -> None:
    context = BrimleyContext()
    func = _make_cli_func()
    context.functions.register(func)

    provider = BrimleyProvider(registry=context.functions, context=context)

    captured: dict = {}

    def fake_run(f, resolved_args, ctx):
        captured["func"] = f
        return "cli-response"

    provider.dispatcher.cli_runner.run = fake_run  # type: ignore[method-assign]

    result = provider.execute_tool_by_name("system_load", {})
    assert result == "cli-response"
    assert captured["func"] is func
