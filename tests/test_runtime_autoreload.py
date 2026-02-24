from pathlib import Path
import pytest

from brimley.runtime.controller import BrimleyRuntimeController
from brimley.execution.execute_helper import execute_function_by_name
from brimley.runtime.reload_contracts import ReloadCommandStatus


def _write_config(root: Path) -> None:
    (root / "brimley.yaml").write_text(
        """
auto_reload:
  enabled: true
  interval_ms: 100
  debounce_ms: 100
  include_patterns: ["*.md", "*.py", "*.sql", "*.yaml"]
  exclude_patterns: []
"""
    )


def _write_tool(path: Path, body: str = "Hello", valid: bool = True) -> None:
    if valid:
        path.write_text(
            f"""
---
name: hello
type: template_function
return_shape: string
mcp:
  type: tool
---
{body}
"""
        )
    else:
        path.write_text(
            f"""
---
name: hello
type: template_function
mcp:
  type: tool
---
{body}
"""
        )


def test_runtime_autoreload_adds_new_function_after_change(tmp_path: Path):
    _write_config(tmp_path)

    first = tmp_path / "first.md"
    first.write_text(
        """
---
name: first
type: template_function
return_shape: string
---
First
"""
    )

    runtime = BrimleyRuntimeController(tmp_path)
    runtime.load_initial()
    runtime.start_auto_reload(background=False)

    assert "first" in runtime.context.functions
    assert "second" not in runtime.context.functions

    second = tmp_path / "second.md"
    second.write_text(
        """
---
name: second
type: template_function
return_shape: string
---
Second
"""
    )

    runtime.poll_once(now=0.00)
    result = runtime.poll_once(now=0.20)

    assert result is not None
    assert result.status == ReloadCommandStatus.SUCCESS
    assert "second" in runtime.context.functions

    runtime.stop_auto_reload()


def test_runtime_autoreload_removes_deleted_function_after_change(tmp_path: Path):
    _write_config(tmp_path)

    stale = tmp_path / "stale.md"
    stale.write_text(
        """
---
name: stale
type: template_function
return_shape: string
---
Stale
"""
    )

    runtime = BrimleyRuntimeController(tmp_path)
    runtime.load_initial()
    runtime.start_auto_reload(background=False)

    assert "stale" in runtime.context.functions

    stale.unlink()

    runtime.poll_once(now=0.00)
    result = runtime.poll_once(now=0.20)

    assert result is not None
    assert result.status == ReloadCommandStatus.SUCCESS
    assert "stale" not in runtime.context.functions

    runtime.stop_auto_reload()


def test_runtime_autoreload_failed_reload_keeps_active_tool_set(tmp_path: Path):
    _write_config(tmp_path)

    hello_file = tmp_path / "hello.md"
    _write_tool(hello_file, body="Hello V1", valid=True)

    runtime = BrimleyRuntimeController(tmp_path)
    first_result = runtime.load_initial()

    assert first_result.status == ReloadCommandStatus.SUCCESS
    assert "hello" in runtime.context.functions

    runtime.start_auto_reload(background=False)

    _write_tool(hello_file, body="Broken", valid=False)

    runtime.poll_once(now=0.00)
    failure_result = runtime.poll_once(now=0.20)

    assert failure_result is not None
    assert failure_result.status == ReloadCommandStatus.FAILURE
    assert "hello" in runtime.context.functions
    assert any("[functions]" in diag.message for diag in failure_result.diagnostics)
    with pytest.raises(KeyError, match="quarantined"):
        execute_function_by_name(runtime.context, "hello", {})

    runtime.stop_auto_reload()


def test_runtime_autoreload_success_invokes_external_mcp_refresh_callback(tmp_path: Path):
    _write_config(tmp_path)

    first = tmp_path / "first.md"
    first.write_text(
        """
---
name: first
type: template_function
return_shape: string
mcp:
  type: tool
---
First
"""
    )

    refresh_calls = {"count": 0}

    runtime = BrimleyRuntimeController(
        tmp_path,
        mcp_refresh=lambda: refresh_calls.__setitem__("count", refresh_calls["count"] + 1),
    )
    runtime.load_initial()

    assert refresh_calls["count"] == 1


def test_runtime_autoreload_successful_watched_update_invokes_mcp_refresh(tmp_path: Path):
    _write_config(tmp_path)

    hello_file = tmp_path / "hello.md"
    _write_tool(hello_file, body="Hello V1", valid=True)

    refresh_calls = {"count": 0}
    runtime = BrimleyRuntimeController(
        tmp_path,
        mcp_refresh=lambda: refresh_calls.__setitem__("count", refresh_calls["count"] + 1),
    )

    first_result = runtime.load_initial()
    assert first_result.status == ReloadCommandStatus.SUCCESS
    assert refresh_calls["count"] == 1

    runtime.start_auto_reload(background=False)

    _write_tool(hello_file, body="Hello V2", valid=True)

    runtime.poll_once(now=0.00)
    second_result = runtime.poll_once(now=0.20)

    assert second_result is not None
    assert second_result.status == ReloadCommandStatus.SUCCESS
    assert "V2" in (runtime.context.functions.get("hello").template_body or "")
    assert refresh_calls["count"] == 2

    runtime.stop_auto_reload()


def test_runtime_autoreload_failed_watched_update_does_not_invoke_mcp_refresh(tmp_path: Path):
    _write_config(tmp_path)

    hello_file = tmp_path / "hello.md"
    _write_tool(hello_file, body="Hello V1", valid=True)

    refresh_calls = {"count": 0}
    runtime = BrimleyRuntimeController(
        tmp_path,
        mcp_refresh=lambda: refresh_calls.__setitem__("count", refresh_calls["count"] + 1),
    )

    first_result = runtime.load_initial()
    assert first_result.status == ReloadCommandStatus.SUCCESS
    assert refresh_calls["count"] == 1

    runtime.start_auto_reload(background=False)

    _write_tool(hello_file, body="Broken", valid=False)

    runtime.poll_once(now=0.00)
    failure_result = runtime.poll_once(now=0.20)

    assert failure_result is not None
    assert failure_result.status == ReloadCommandStatus.FAILURE
    assert refresh_calls["count"] == 1
    assert "hello" in runtime.context.functions
    with pytest.raises(KeyError, match="quarantined"):
        execute_function_by_name(runtime.context, "hello", {})

    runtime.stop_auto_reload()


def test_runtime_autoreload_refreshes_python_function_body_only_changes(tmp_path: Path):
    _write_config(tmp_path)

    python_func = tmp_path / "calc.py"
    python_func.write_text(
        '''from brimley import function

@function(name="calc")
def calc() -> int:
    return 1
'''
    )

    runtime = BrimleyRuntimeController(tmp_path)
    first_result = runtime.load_initial()

    assert first_result.status == ReloadCommandStatus.SUCCESS
    assert execute_function_by_name(runtime.context, "calc", {}) == 1

    runtime.start_auto_reload(background=False)

    python_func.write_text(
        '''from brimley import function

@function(name="calc")
def calc() -> int:
    return 2
'''
    )

    runtime.poll_once(now=0.00)
    second_result = runtime.poll_once(now=0.20)

    assert second_result is not None
    assert second_result.status == ReloadCommandStatus.SUCCESS
    assert execute_function_by_name(runtime.context, "calc", {}) == 2

    runtime.stop_auto_reload()
