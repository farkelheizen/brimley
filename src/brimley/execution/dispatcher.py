from typing import Any, Dict, Optional
from concurrent.futures import Future, ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from threading import BoundedSemaphore
from loguru import logger as _logger
from brimley.core.models import BrimleyFunction, PythonFunction, SqlFunction, TemplateFunction, ApiFunction, CliFunction
from brimley.core.context import BrimleyContext
from brimley.execution.python_runner import PythonRunner
from brimley.execution.sql_runner import SqlRunner
from brimley.execution.jinja_runner import JinjaRunner
from brimley.execution.api_runner import ApiRunner
from brimley.execution.cli_runner import CliRunner
from brimley.utils.diagnostics import BrimleyExecutionError
from brimley.infrastructure.logging import (
    get_or_create_correlation_id,
    set_external_trace_id,
)

class Dispatcher:
    """
    Routes execution to the appropriate runner based on function type.
    """
    def __init__(self):
        self.python_runner = PythonRunner()
        self.sql_runner = SqlRunner()
        self.jinja_runner = JinjaRunner()
        self.api_runner = ApiRunner()
        self.cli_runner = CliRunner()
        self._executor: Optional[ThreadPoolExecutor] = None
        self._inflight_slots: Optional[BoundedSemaphore] = None
        self._runtime_signature: Optional[tuple[int, int, str]] = None

    def _ensure_runtime_controls(self, context: BrimleyContext) -> None:
        execution = context.execution
        runtime_signature = (
            execution.thread_pool_size,
            execution.queue.max_size,
            execution.queue.on_full,
        )
        if self._executor is not None and self._inflight_slots is not None and self._runtime_signature == runtime_signature:
            return

        if self._executor is not None:
            self._executor.shutdown(wait=False, cancel_futures=True)

        total_slots = execution.thread_pool_size + execution.queue.max_size
        self._executor = ThreadPoolExecutor(max_workers=execution.thread_pool_size)
        self._inflight_slots = BoundedSemaphore(value=total_slots)
        self._runtime_signature = runtime_signature

    def _resolve_timeout_seconds(self, func: BrimleyFunction, context: BrimleyContext) -> float:
        if func.timeout_seconds is not None:
            return float(func.timeout_seconds)
        return float(context.execution.timeout_seconds)

    def _dispatch_sync_call(
        self,
        func: BrimleyFunction,
        args: Dict[str, Any],
        context: BrimleyContext,
        runtime_injections: Optional[Dict[str, Any]],
    ) -> Any:
        if func.type == "python_function":
            if isinstance(func, PythonFunction):
                return self.python_runner.run(func, args, context, runtime_injections=runtime_injections)
        elif func.type == "sql_function":
            if isinstance(func, SqlFunction):
                return self.sql_runner.run(func, args, context)
        elif func.type == "template_function":
            if isinstance(func, TemplateFunction):
                return self.jinja_runner.run(func, args, context)
        elif func.type == "api_function":
            # NOTE(v0.9): stub intercept point for MockRegistry — do not remove.
            if isinstance(func, ApiFunction):
                return self.api_runner.run(func, args, context)
        elif func.type == "cli_function":
            # NOTE(v0.9): stub intercept point for MockRegistry — do not remove.
            if isinstance(func, CliFunction):
                return self.cli_runner.run(func, args, context)

        raise NotImplementedError(f"No runner for function type: {func.type} ({type(func)})")

    def _has_fastmcp_runtime_injection(
        self,
        runtime_injections: Optional[Dict[str, Any]],
    ) -> bool:
        if not runtime_injections:
            return False

        for key in (
            "mcp_context",
            "mcp",
            "ctx",
            "context",
            "fastmcp_context",
            "mcp.server.fastmcp.Context",
        ):
            if key in runtime_injections and runtime_injections[key] is not None:
                return True

        return False

    def run(
        self,
        func: BrimleyFunction,
        args: Dict[str, Any],
        context: BrimleyContext,
        runtime_injections: Optional[Dict[str, Any]] = None,
    ) -> Any:
        # Establish / inherit correlation ID for this dispatch.
        get_or_create_correlation_id()

        # Propagate external trace ID from FastMCP request context when present.
        if runtime_injections:
            mcp_ctx = runtime_injections.get("mcp_context") or runtime_injections.get("mcp")
            if mcp_ctx is not None:
                request_id = getattr(mcp_ctx, "request_id", None)
                if request_id:
                    set_external_trace_id(str(request_id))

        _logger.trace("Dispatching function '{}' (type={})", func.name, func.type)

        if func.type == "python_function" and self._has_fastmcp_runtime_injection(runtime_injections):
            try:
                result = self._dispatch_sync_call(func, args, context, runtime_injections)
                _logger.trace("Function '{}' completed (type={})", func.name, func.type)
                return result
            except Exception as exc:
                _logger.trace("Function '{}' failed (type={}): {}", func.name, func.type, exc)
                raise

        self._ensure_runtime_controls(context)
        timeout_seconds = self._resolve_timeout_seconds(func, context)
        queue_strategy = context.execution.queue.on_full

        assert self._inflight_slots is not None
        assert self._executor is not None

        if queue_strategy == "block":
            acquired = self._inflight_slots.acquire(timeout=timeout_seconds)
        else:
            acquired = self._inflight_slots.acquire(blocking=False)

        if not acquired:
            raise BrimleyExecutionError(
                message=(
                    f"Execution queue is full for function '{func.name}' (on_full={queue_strategy})."
                ),
                func_name=func.name,
            )

        try:
            future: Future = self._executor.submit(
                self._dispatch_sync_call,
                func,
                args,
                context,
                runtime_injections,
            )
            try:
                result = future.result(timeout=timeout_seconds)
                _logger.trace("Function '{}' completed (type={})", func.name, func.type)
                return result
            except FuturesTimeoutError as exc:
                future.cancel()
                _logger.trace("Function '{}' timed out after {}s (type={})", func.name, timeout_seconds, func.type)
                raise BrimleyExecutionError(
                    message=f"Execution timed out after {timeout_seconds:.3f}s.",
                    func_name=func.name,
                ) from exc
            except Exception as exc:
                _logger.trace("Function '{}' failed (type={}): {}", func.name, func.type, exc)
                raise
        finally:
            self._inflight_slots.release()
