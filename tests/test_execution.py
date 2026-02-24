import pytest
from brimley.core.context import BrimleyContext
from brimley.core.models import PythonFunction, SqlFunction, TemplateFunction
from brimley.execution.dispatcher import Dispatcher
from brimley.utils.diagnostics import BrimleyExecutionError
import time
from threading import Event, Thread


def test_dispatcher_passes_runtime_injections_to_python_runner() -> None:
	dispatcher = Dispatcher()
	context = BrimleyContext()
	func = PythonFunction(
		name="py_fn",
		type="python_function",
		return_shape="string",
		handler="pkg.mod.fn",
	)

	captured: dict[str, object] = {}

	def fake_python_run(f, args, ctx, runtime_injections=None):
		captured["func"] = f
		captured["args"] = args
		captured["ctx"] = ctx
		captured["runtime_injections"] = runtime_injections
		return "ok"

	dispatcher.python_runner.run = fake_python_run  # type: ignore[method-assign]

	runtime_injections = {"mcp_context": object()}
	result = dispatcher.run(func, {"name": "test"}, context, runtime_injections=runtime_injections)

	assert result == "ok"
	assert captured["func"] is func
	assert captured["args"] == {"name": "test"}
	assert captured["ctx"] is context
	assert captured["runtime_injections"] is runtime_injections


def test_dispatcher_keeps_sql_and_template_runners_pure() -> None:
	dispatcher = Dispatcher()
	context = BrimleyContext()

	sql_func = SqlFunction(
		name="sql_fn",
		type="sql_function",
		return_shape="void",
		sql_body="SELECT 1",
	)
	template_func = TemplateFunction(
		name="tpl_fn",
		type="template_function",
		return_shape="string",
		template_body="Hello",
	)

	sql_calls: dict[str, object] = {}
	tpl_calls: dict[str, object] = {}

	def fake_sql_run(f, args, ctx):
		sql_calls["func"] = f
		sql_calls["args"] = args
		sql_calls["ctx"] = ctx
		return "sql-ok"

	def fake_tpl_run(f, args, ctx):
		tpl_calls["func"] = f
		tpl_calls["args"] = args
		tpl_calls["ctx"] = ctx
		return "tpl-ok"

	dispatcher.sql_runner.run = fake_sql_run  # type: ignore[method-assign]
	dispatcher.jinja_runner.run = fake_tpl_run  # type: ignore[method-assign]

	result_sql = dispatcher.run(sql_func, {"id": 1}, context, runtime_injections={"mcp_context": object()})
	result_tpl = dispatcher.run(template_func, {"name": "x"}, context, runtime_injections={"mcp_context": object()})

	assert result_sql == "sql-ok"
	assert sql_calls == {"func": sql_func, "args": {"id": 1}, "ctx": context}

	assert result_tpl == "tpl-ok"
	assert tpl_calls == {"func": template_func, "args": {"name": "x"}, "ctx": context}


def test_dispatcher_defaults_runtime_injections_to_none() -> None:
	dispatcher = Dispatcher()
	context = BrimleyContext()
	func = PythonFunction(
		name="py_fn",
		type="python_function",
		return_shape="string",
		handler="pkg.mod.fn",
	)

	captured: dict[str, object] = {}

	def fake_python_run(f, args, ctx, runtime_injections=None):
		captured["runtime_injections"] = runtime_injections
		return "ok"

	dispatcher.python_runner.run = fake_python_run  # type: ignore[method-assign]

	result = dispatcher.run(func, {}, context)

	assert result == "ok"
	assert captured["runtime_injections"] is None


def test_dispatcher_function_timeout_precedence_over_global() -> None:
	dispatcher = Dispatcher()
	context = BrimleyContext(
		config_dict={
			"execution": {
				"thread_pool_size": 2,
				"timeout_seconds": 0.01,
				"queue": {"max_size": 2, "on_full": "reject"},
			}
		}
	)

	func = PythonFunction(
		name="slow_ok",
		type="python_function",
		return_shape="string",
		handler="pkg.mod.fn",
		timeout_seconds=0.2,
	)

	def fake_python_run(_func, _args, _context, runtime_injections=None):
		time.sleep(0.05)
		return "ok"

	dispatcher.python_runner.run = fake_python_run  # type: ignore[method-assign]

	result = dispatcher.run(func, {}, context)
	assert result == "ok"


def test_dispatcher_times_out_without_function_override() -> None:
	dispatcher = Dispatcher()
	context = BrimleyContext(
		config_dict={
			"execution": {
				"thread_pool_size": 2,
				"timeout_seconds": 0.01,
				"queue": {"max_size": 2, "on_full": "reject"},
			}
		}
	)

	func = PythonFunction(
		name="slow_timeout",
		type="python_function",
		return_shape="string",
		handler="pkg.mod.fn",
	)

	def fake_python_run(_func, _args, _context, runtime_injections=None):
		time.sleep(0.05)
		return "too-late"

	dispatcher.python_runner.run = fake_python_run  # type: ignore[method-assign]

	with pytest.raises(BrimleyExecutionError, match="timed out"):
		dispatcher.run(func, {}, context)


def test_dispatcher_rejects_when_bounded_queue_is_full() -> None:
	dispatcher = Dispatcher()
	context = BrimleyContext(
		config_dict={
			"execution": {
				"thread_pool_size": 1,
				"timeout_seconds": 0.5,
				"queue": {"max_size": 0, "on_full": "reject"},
			}
		}
	)

	func = PythonFunction(
		name="queue_test",
		type="python_function",
		return_shape="string",
		handler="pkg.mod.fn",
	)

	started = Event()
	release = Event()

	def blocking_python_run(_func, _args, _context, runtime_injections=None):
		started.set()
		release.wait(timeout=1)
		return "done"

	dispatcher.python_runner.run = blocking_python_run  # type: ignore[method-assign]

	results: list[object] = []

	def occupy_worker() -> None:
		results.append(dispatcher.run(func, {}, context))

	worker = Thread(target=occupy_worker)
	worker.start()
	started.wait(timeout=1)

	with pytest.raises(BrimleyExecutionError, match="queue is full"):
		dispatcher.run(func, {}, context)

	release.set()
	worker.join(timeout=1)
	assert results == ["done"]
