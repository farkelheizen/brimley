"""Tests for ApiRunner (Brimley 0.7)."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from brimley.core.context import BrimleyContext
from brimley.core.models import ApiFunction
from brimley.execution.api_runner import ApiRunner
from brimley.utils.diagnostics import BrimleyExecutionError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_func(**kwargs: Any) -> ApiFunction:
    defaults = {
        "name": "test_api",
        "type": "api_function",
        "return_shape": "primitive",
        "request": {"url": "https://example.com/api", "method": "GET"},
    }
    defaults.update(kwargs)
    return ApiFunction(**defaults)


def _mock_response(
    status_code: int = 200,
    json_data: Any = None,
    text: str = "",
    content_type: str = "application/json",
) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    resp.is_success = 200 <= status_code < 300
    resp.reason_phrase = "OK" if status_code == 200 else "Error"
    resp.headers = {"content-type": content_type}
    resp.text = text or (json.dumps(json_data) if json_data else "")
    resp.json.return_value = json_data or {}
    resp.content = resp.text.encode()
    return resp


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_api_runner_can_handle() -> None:
    runner = ApiRunner()
    func = _make_func()
    assert runner.can_handle(func) is True


def test_api_runner_cannot_handle_python_function() -> None:
    from brimley.core.models import PythonFunction
    runner = ApiRunner()
    func = PythonFunction(name="fn", type="python_function", return_shape="string", handler="mod.fn")
    assert runner.can_handle(func) is False


def test_api_runner_success_json(monkeypatch: pytest.MonkeyPatch) -> None:
    func = _make_func(return_shape="string")
    context = BrimleyContext()
    runner = ApiRunner()

    with patch.object(runner, "_async_request", new=AsyncMock(return_value="some result")):
        result = runner.run(func, {}, context)
    assert result is not None


def test_api_runner_error_status_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    func = _make_func(
        response={404: {"error": "Not found"}},
    )
    context = BrimleyContext()
    runner = ApiRunner()

    mock_resp = _mock_response(404)

    with patch.object(runner, "_async_request", new=AsyncMock(side_effect=BrimleyExecutionError("Not found", func_name="test_api"))):
        with pytest.raises(BrimleyExecutionError, match="Not found"):
            runner.run(func, {}, context)


def test_api_runner_handles_response_mapping() -> None:
    runner = ApiRunner()
    func = _make_func(response={200: {"type": "json", "parse": {"path": "$.user"}}})

    mock_resp = _mock_response(200, json_data={"user": {"id": 42}})
    result = runner._handle_response(mock_resp, func)
    assert result == {"id": 42}


def test_api_runner_handle_response_error_key_raises() -> None:
    runner = ApiRunner()
    func = _make_func(response={401: {"error": "Authentication failed"}})
    mock_resp = _mock_response(401)

    with pytest.raises(BrimleyExecutionError, match="Authentication failed"):
        runner._handle_response(mock_resp, func)


def test_api_runner_handle_response_success_no_explicit_handler() -> None:
    runner = ApiRunner()
    func = _make_func()
    mock_resp = _mock_response(200, json_data={"ok": True})

    result = runner._handle_response(mock_resp, func)
    assert result == {"ok": True}


def test_api_runner_handle_unrecognised_error_status_raises() -> None:
    runner = ApiRunner()
    func = _make_func()
    mock_resp = _mock_response(500, text="Internal Server Error")

    with pytest.raises(BrimleyExecutionError, match="500"):
        runner._handle_response(mock_resp, func)


def test_api_runner_url_template_rendered(monkeypatch: pytest.MonkeyPatch) -> None:
    func = _make_func(
        return_shape="string",
        request={"url": "https://api.example.com/users/{{ username }}", "method": "GET"},
    )
    context = BrimleyContext()
    runner = ApiRunner()

    captured = {}

    async def fake_async_request(f, url, headers, body):
        captured["url"] = url
        return "Alice"

    with patch.object(runner, "_async_request", side_effect=fake_async_request):
        runner.run(func, {"username": "alice"}, context)

    assert captured["url"] == "https://api.example.com/users/alice"


def test_api_runner_undefined_template_var_raises() -> None:
    func = _make_func(
        request={"url": "https://api.example.com/users/{{ missing_var }}", "method": "GET"},
    )
    context = BrimleyContext()
    runner = ApiRunner()

    with patch.object(runner, "_async_request", new=AsyncMock(return_value={})):
        with pytest.raises(BrimleyExecutionError, match="Template rendering failed"):
            runner.run(func, {}, context)


def test_api_runner_secret_resolved_into_header(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MY_TOKEN", "secretval")
    func = _make_func(
        return_shape="string",
        request={
            "url": "https://api.example.com",
            "headers": {"Authorization": "Bearer {{ secrets.token }}"},
        },
        secrets={"token": [{"env": "MY_TOKEN"}]},
    )
    context = BrimleyContext()
    runner = ApiRunner()

    captured = {}

    async def fake_async_request(f, url, headers, body):
        captured["headers"] = headers
        return "ok"

    with patch.object(runner, "_async_request", side_effect=fake_async_request):
        runner.run(func, {}, context)

    assert captured["headers"].get("Authorization") == "Bearer secretval"


def test_api_runner_missing_secret_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MISSING_SECRET", raising=False)
    func = _make_func(
        secrets={"token": [{"env": "MISSING_SECRET"}]},
    )
    context = BrimleyContext()
    runner = ApiRunner()

    with pytest.raises(BrimleyExecutionError):
        runner.run(func, {}, context)


def test_api_runner_jsonpath_extract_simple() -> None:
    from brimley.execution.api_runner import _jsonpath_extract
    data = {"user": {"id": 42, "name": "Alice"}}
    assert _jsonpath_extract(data, "$.user", "fn") == {"id": 42, "name": "Alice"}
    assert _jsonpath_extract(data, "$.user.id", "fn") == 42


def test_api_runner_jsonpath_extract_missing_key_returns_none() -> None:
    from brimley.execution.api_runner import _jsonpath_extract
    data = {"user": {"id": 1}}
    assert _jsonpath_extract(data, "$.user.missing", "fn") is None


def test_api_runner_jsonpath_invalid_path_returns_data() -> None:
    from brimley.execution.api_runner import _jsonpath_extract
    data = {"key": "val"}
    assert _jsonpath_extract(data, "not_a_path", "fn") == {"key": "val"}
