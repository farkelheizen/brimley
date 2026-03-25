"""ApiRunner: executes api_function definitions via httpx (Brimley 0.7)."""

from __future__ import annotations

import asyncio
import re
from typing import Any, Dict, Optional
from urllib.parse import urlparse

import httpx
from jinja2.sandbox import SandboxedEnvironment
from jinja2 import StrictUndefined, UndefinedError

from brimley.core.context import BrimleyContext
from brimley.core.models import ApiFunction, BrimleyFunction, ResultMapping
from brimley.execution.base_runner import BaseRunner
from brimley.execution.result_mapper import ResultMapper
from brimley.execution.result_parser import get_parser
from brimley.infrastructure.logging import get_or_create_correlation_id
from brimley.utils.diagnostics import BrimleyExecutionError
from brimley.utils.secrets import (
    BrimleySecretResolutionError,
    clear_secrets,
    redact_secrets,
    register_secrets,
    resolve_secrets,
)

# Sandboxed Jinja2 environment — defence-in-depth for user-controlled template values.
_JINJA_ENV = SandboxedEnvironment(undefined=StrictUndefined, keep_trailing_newline=True)

# Wildcard status-code pattern: e.g. "2xx", "4xx", "5xx"
_WILDCARD_CODE_PATTERN = re.compile(r"^([1-5])xx$")

# Allowed URL schemes (SSRF mitigation)
_ALLOWED_SCHEMES = frozenset({"http", "https"})


class ApiRunner(BaseRunner):
    """
    Executes ``api_function`` definitions.

    Execution flow (per spec §6):
    1. Resolve secrets (env-only in v0.7).
    2. Build Jinja2 template context (args + secrets + correlation_id).
    3. Render URL, headers, and optional body via SandboxedEnvironment.
    4. Validate URL scheme (http/https only) and headers (no CRLF).
    5. Execute HTTP call asynchronously via httpx.
    6. Match response status code against ``results:`` block (ordered first-match),
       or fall back to legacy ``response:`` block.
    7. Map result through ``return_shape``.

    Security notes:
    - ``SandboxedEnvironment`` prevents Jinja2 template injection via user inputs.
    - URL scheme validation rejects non-HTTP(S) schemes (SSRF mitigation).
    - Header value validation rejects CRLF sequences (header injection prevention).
    - Secrets are resolved from environment variables only; values are never logged.

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
            secrets = resolve_secrets(func.secrets, func.name, container=context.container)
        except BrimleySecretResolutionError as exc:
            raise BrimleyExecutionError(message=str(exc), func_name=func.name) from exc

        # 1a. Register resolved secrets for log redaction.
        correlation_id = get_or_create_correlation_id()
        secret_values = list(secrets.values())
        register_secrets(correlation_id, secret_values)

        try:
            # 2. Template context — secrets are injected as a nested namespace.
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
                    message=redact_secrets(f"Template rendering failed: {exc}", secret_values),
                    func_name=func.name,
                ) from exc

            # 4a. Validate URL scheme (SSRF mitigation).
            _validate_url_scheme(url, func.name)

            # 4b. Validate header values (header injection prevention).
            _validate_headers(headers, func.name)

            # 5. Execute.
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

            # 6. Map to return_shape.
            return ResultMapper.map_result(raw_response, func, context)
        except BrimleyExecutionError as exc:
            # Layer 2: scrub secret values from error messages.
            exc.message = redact_secrets(exc.message, secret_values)
            raise
        finally:
            clear_secrets(correlation_id)

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

        # Prefer new ``results:`` block; fall back to legacy ``response:`` block.
        if func.results:
            return self._handle_results_block(response, func)
        return self._handle_legacy_response(response, func)

    # ------------------------------------------------------------------
    # New results: block (ordered first-match, SD-3)
    # ------------------------------------------------------------------

    def _handle_results_block(self, response: httpx.Response, func: ApiFunction) -> Any:
        """Apply ordered first-match against ``results:`` status-code mappings."""
        status = response.status_code
        mapping = _match_status_code(status, func.results or {})

        if mapping is None:
            # No match — fall back to raw text body, no error.
            return response.text

        if mapping.error is not None:
            raise BrimleyExecutionError(
                message=str(mapping.error),
                func_name=func.name,
            )

        parser = get_parser(mapping.type or "text", func.name)
        return parser.parse(response.content, mapping.parse, func.name)

    # ------------------------------------------------------------------
    # Legacy response: block (backward compat)
    # ------------------------------------------------------------------

    def _handle_response(self, response: httpx.Response, func: ApiFunction) -> Any:
        """Backward-compatible alias for ``_handle_legacy_response``."""
        return self._handle_legacy_response(response, func)

    def _handle_legacy_response(self, response: httpx.Response, func: ApiFunction) -> Any:
        """Map the HTTP response through the legacy ``response:`` configuration block."""
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
        """Apply the ``parse:`` block inside a legacy response handler."""
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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _render(template_str: str, ctx: Dict[str, Any]) -> str:
    """Render a Jinja2 template string using the sandboxed environment."""
    return _JINJA_ENV.from_string(template_str).render(**ctx)


def _validate_url_scheme(url: str, func_name: str) -> None:
    """
    Reject URLs with non-HTTP(S) schemes (SSRF mitigation).

    Raises :class:`BrimleyExecutionError` if the scheme is not ``http`` or
    ``https``, or if the URL contains embedded credentials.
    """
    try:
        parsed = urlparse(url)
    except Exception as exc:
        raise BrimleyExecutionError(
            message=f"Invalid URL '{url}': {exc}",
            func_name=func_name,
        ) from exc

    if parsed.scheme not in _ALLOWED_SCHEMES:
        raise BrimleyExecutionError(
            message=(
                f"Disallowed URL scheme '{parsed.scheme}' in '{url}'. "
                "Only 'http' and 'https' are permitted (SSRF mitigation)."
            ),
            func_name=func_name,
        )

    if parsed.username or parsed.password:
        raise BrimleyExecutionError(
            message=(
                f"Embedded credentials are not allowed in URL '{url}'."
            ),
            func_name=func_name,
        )


def _validate_headers(headers: Dict[str, str], func_name: str) -> None:
    """
    Reject header values containing CRLF sequences (header injection prevention).

    Raises :class:`BrimleyExecutionError` if any header value contains ``\\r`` or
    ``\\n``.
    """
    for name, value in headers.items():
        if "\r" in value or "\n" in value:
            raise BrimleyExecutionError(
                message=(
                    f"Header '{name}' contains illegal CR/LF characters "
                    "(header injection prevention)."
                ),
                func_name=func_name,
            )


def _match_status_code(
    status: int,
    results: Dict[str, "ResultMapping"],
) -> Optional["ResultMapping"]:
    """
    Ordered first-match against a ``results:`` block.

    Match precedence (in YAML declaration order):
    1. Exact numeric match (e.g. ``"200"``)
    2. Wildcard match (e.g. ``"2xx"``)
    3. ``"default"`` catch-all
    """
    for key, mapping in results.items():
        if key == "default":
            return mapping
        if re.fullmatch(r"\d+", key) and int(key) == status:
            return mapping
        wm = _WILDCARD_CODE_PATTERN.fullmatch(key)
        if wm and str(status)[0] == wm.group(1):
            return mapping
    return None


def _jsonpath_extract(data: Any, path: str, func_name: str) -> Any:
    """
    Minimal legacy JSONPath extractor supporting ``$.key`` and ``$.key.sub``.

    Full JSONPath evaluation is out of scope for v0.7.
    """
    _JSONPATH_SIMPLE = re.compile(r"^\$\.(.+)$")
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
