"""ApiRunner: executes api_function definitions via httpx (Brimley 0.7)."""

from __future__ import annotations

import asyncio
import re
from typing import Any, Dict, Optional

import httpx
from jinja2 import Environment, StrictUndefined, UndefinedError

from brimley.core.context import BrimleyContext
from brimley.core.models import ApiFunction, BrimleyFunction
from brimley.execution.base_runner import BaseRunner
from brimley.execution.result_mapper import ResultMapper
from brimley.infrastructure.logging import get_or_create_correlation_id
from brimley.utils.diagnostics import BrimleyExecutionError
from brimley.utils.secrets import BrimleySecretResolutionError, resolve_secrets

_JINJA_ENV = Environment(undefined=StrictUndefined, keep_trailing_newline=True)

# JSONPath-lite: supports "$.key" and "$.key.sub" patterns.
_JSONPATH_SIMPLE = re.compile(r"^\$\.(.+)$")


class ApiRunner(BaseRunner):
    """
    Executes ``api_function`` definitions.

    Execution flow (per spec §6):
    1. Resolve secrets (env-only in v0.7).
    2. Build Jinja2 template context (args + secrets + correlation_id).
    3. Render URL, headers, and optional body.
    4. Execute HTTP call asynchronously via httpx.
    5. Map response through the ``response:`` block to ``return_shape``.

    Security notes:
    - Secrets are resolved from environment variables only; values are never
      logged (callers must mask via the logging sink filter).
    - Correlation ID is propagated into headers when the YAML declares
      ``X-Correlation-ID: "{{ correlation_id }}"``.

    Introduced in Brimley 0.7.
    """

    def can_handle(self, func: BrimleyFunction) -> bool:
        return func.type == "api_function"

    def run(
        self,
        func: BrimleyFunction,
        args: Dict[str, Any],
        context: BrimleyContext,
    ) -> Any:
        if not isinstance(func, ApiFunction):
            raise TypeError(f"ApiRunner.run expects ApiFunction, got {type(func).__name__}")

        # 1. Resolve secrets.
        try:
            secrets = resolve_secrets(func.secrets, func.name)
        except BrimleySecretResolutionError as exc:
            raise BrimleyExecutionError(message=str(exc), func_name=func.name) from exc

        # 2. Template context — secrets are injected as a nested namespace.
        correlation_id = get_or_create_correlation_id()
        template_ctx: Dict[str, Any] = {
            **args,
            "secrets": secrets,
            "correlation_id": correlation_id,
        }

        # 3. Render request fields.
        try:
            url = _render(func.request.url, template_ctx)
            headers: Dict[str, str] = {}
            if func.request.headers:
                for k, v in func.request.headers.items():
                    headers[k] = _render(v, template_ctx)
            body: Optional[Any] = None
            if func.request.body is not None:
                raw_body = func.request.body
                if isinstance(raw_body, str):
                    body = _render(raw_body, template_ctx)
                else:
                    body = raw_body
        except UndefinedError as exc:
            raise BrimleyExecutionError(
                message=f"Template rendering failed: {exc}",
                func_name=func.name,
            ) from exc

        # 4. Execute.
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(
                    asyncio.run,
                    self._async_request(func, url, headers, body),
                )
                raw_response = future.result()
        else:
            raw_response = asyncio.run(self._async_request(func, url, headers, body))

        # 5. Map to return_shape.
        return ResultMapper.map_result(raw_response, func, context)

    async def _async_request(
        self,
        func: ApiFunction,
        url: str,
        headers: Dict[str, str],
        body: Optional[Any],
    ) -> Any:
        """Perform the HTTP call and apply response-block handling."""
        timeout = func.request.timeout

        async with httpx.AsyncClient() as client:
            response = await client.request(
                method=func.request.method.upper(),
                url=url,
                headers=headers if headers else None,
                json=body if isinstance(body, dict) else None,
                content=body.encode() if isinstance(body, str) else None,
                timeout=timeout,
            )

        return self._handle_response(response, func)

    def _handle_response(self, response: httpx.Response, func: ApiFunction) -> Any:
        """Map the HTTP response through the ``response:`` configuration block."""
        status = response.status_code
        response_cfg: Dict[Any, Any] = func.response or {}

        # Look up status code handler; try int first, then str.
        handler = response_cfg.get(status) or response_cfg.get(str(status))

        if handler is not None:
            if not isinstance(handler, dict):
                raise BrimleyExecutionError(
                    message=f"Response handler for status {status} must be a mapping.",
                    func_name=func.name,
                )
            if "error" in handler:
                raise BrimleyExecutionError(
                    message=str(handler["error"]),
                    func_name=func.name,
                )
            return self._extract_from_handler(response, handler, func)

        # No explicit handler — treat 2xx as success.
        if response.is_success:
            content_type = response.headers.get("content-type", "")
            if "json" in content_type:
                return response.json()
            return response.text

        raise BrimleyExecutionError(
            message=f"HTTP {status} {response.reason_phrase}: {response.text[:200]}",
            func_name=func.name,
        )

    def _extract_from_handler(
        self,
        response: httpx.Response,
        handler: Dict[str, Any],
        func: ApiFunction,
    ) -> Any:
        """Apply the ``parse:`` block inside a response handler."""
        content_type_hint = handler.get("type", "auto")

        if content_type_hint in ("json", "auto"):
            try:
                data: Any = response.json()
            except Exception:
                data = response.text
        elif content_type_hint == "text":
            data = response.text
        else:
            data = response.content

        parse_cfg = handler.get("parse")
        if not parse_cfg or not isinstance(parse_cfg, dict):
            return data

        path = parse_cfg.get("path")
        if path:
            data = _jsonpath_extract(data, path, func.name)

        return data


def _render(template_str: str, ctx: Dict[str, Any]) -> str:
    """Render a Jinja2 template string with the given context."""
    return _JINJA_ENV.from_string(template_str).render(**ctx)


def _jsonpath_extract(data: Any, path: str, func_name: str) -> Any:
    """
    Minimal JSONPath extractor supporting ``$.key`` and ``$.key.sub`` patterns.

    Full JSONPath evaluation is out of scope for v0.7.
    """
    match = _JSONPATH_SIMPLE.match(path)
    if not match:
        return data

    segments = match.group(1).split(".")
    current = data
    for segment in segments:
        if isinstance(current, dict):
            current = current.get(segment)
        else:
            return current
    return current
