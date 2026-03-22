"""CliRunner: executes cli_function definitions via asyncio subprocess (Brimley 0.7)."""

from __future__ import annotations

import asyncio
import json
import os
import re
from pathlib import Path
from typing import Any, Dict, Optional

from jinja2.sandbox import SandboxedEnvironment
from jinja2 import StrictUndefined, UndefinedError

from brimley.core.context import BrimleyContext
from brimley.core.models import BrimleyFunction, CliFunction, CliParsingConfig, ResultMapping
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

# Shell metacharacters that must not appear in rendered command_arguments entries.
_SHELL_METACHAR_PATTERN = re.compile(r"[;&|`$><\r\n]|\$\(|\`")


class CliRunner(BaseRunner):
    """
    Executes ``cli_function`` definitions via ``asyncio.create_subprocess_exec``.

    Security constraints (non-negotiable per ADR-0002 / 0.7 spec):
    - ``shell=False`` always enforced; command + args are passed as a list.
    - Only explicit ``command_arguments:`` list entries are passed to the subprocess.
    - ``timeout_seconds`` is required and validated at scanner load time.
    - ``cwd`` defaults to ``context.app["root_dir"]`` or CWD; never inherited.
    - Shell metacharacters in rendered ``command_arguments`` entries are rejected.
    - Environment follows two-mode behaviour: if ``env:`` is declared, only
      declared keys are passed; if ``env:`` is omitted, parent environment is
      inherited.

    Introduced in Brimley 0.7.
    """

    def can_handle(self, func: BrimleyFunction) -> bool:
        return func.type == "cli_function"

    def run(
        self,
        func: BrimleyFunction,
        args: Dict[str, Any],
        context: BrimleyContext,
    ) -> Any:
        if not isinstance(func, CliFunction):
            raise TypeError(f"CliRunner.run expects CliFunction, got {type(func).__name__}")

        # 1. Resolve secrets.
        try:
            secrets = resolve_secrets(func.secrets, func.name)
        except BrimleySecretResolutionError as exc:
            raise BrimleyExecutionError(message=str(exc), func_name=func.name) from exc

        # 1a. Register resolved secrets for log redaction.
        correlation_id = get_or_create_correlation_id()
        secret_values = list(secrets.values())
        register_secrets(correlation_id, secret_values)

        try:
            # 2. Template context.
            template_ctx: Dict[str, Any] = {
                **args,
                "secrets": secrets,
                "correlation_id": correlation_id,
            }

            # 3. Render command_arguments list (Jinja2 sandboxed).
            try:
                rendered_args = [_render(a, template_ctx) for a in func.command_arguments]
            except UndefinedError as exc:
                raise BrimleyExecutionError(
                    message=redact_secrets(f"Arg template rendering failed: {exc}", secret_values),
                    func_name=func.name,
                ) from exc

            # 3a. Validate rendered args for shell metacharacters (injection prevention).
            for rendered in rendered_args:
                _validate_arg_no_metachar(rendered, func.name)

            # 4. Build subprocess env (two-mode behaviour per spec / OQ-8 resolution).
            subprocess_env: Optional[Dict[str, str]] = None
            if func.env is not None:
                # env: declared — strict whitelist mode: only declared keys forwarded.
                try:
                    subprocess_env = {
                        k: _render(v, template_ctx) for k, v in func.env.items()
                    }
                except UndefinedError as exc:
                    raise BrimleyExecutionError(
                        message=redact_secrets(f"Env template rendering failed: {exc}", secret_values),
                        func_name=func.name,
                    ) from exc
            else:
                # env: omitted — inherit parent process environment (convenience mode).
                subprocess_env = dict(os.environ)

            # 5. Determine cwd — defaults to project root, never inherited.
            cwd = func.cwd
            if not cwd:
                root_dir = context.app.get("root_dir") or context.app.get("project_root")
                cwd = str(root_dir) if root_dir else str(Path.cwd())

            # 6. Execute.
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None

            if loop and loop.is_running():
                import concurrent.futures

                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                    future = pool.submit(
                        asyncio.run,
                        self._async_exec(func, rendered_args, subprocess_env, cwd),
                    )
                    exit_code, stdout_bytes, stderr_bytes = future.result()
            else:
                exit_code, stdout_bytes, stderr_bytes = asyncio.run(
                    self._async_exec(func, rendered_args, subprocess_env, cwd)
                )

            # 7. Apply results: block (per-exit-code) or fall back to legacy behaviour.
            if func.results:
                return self._handle_results_block(
                    exit_code, stdout_bytes, stderr_bytes, func, context
                )
            return self._handle_legacy_parsing(
                exit_code, stdout_bytes, stderr_bytes, func, context
            )
        except BrimleyExecutionError as exc:
            # Layer 2: scrub secret values from error messages.
            exc.message = redact_secrets(exc.message, secret_values)
            raise
        finally:
            clear_secrets(correlation_id)

    async def _async_exec(
        self,
        func: CliFunction,
        rendered_args: list[str],
        subprocess_env: Optional[Dict[str, str]],
        cwd: str,
    ) -> tuple[int, bytes, bytes]:
        """Spawn the subprocess and capture stdout + stderr."""
        cmd = [func.command] + rendered_args

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=subprocess_env,
            cwd=cwd,
        )

        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                process.communicate(),
                timeout=func.timeout_seconds,
            )
        except asyncio.TimeoutError:
            try:
                process.kill()
            except ProcessLookupError:
                pass
            raise BrimleyExecutionError(
                message=(
                    f"CLI command '{func.command}' timed out after "
                    f"{func.timeout_seconds}s."
                ),
                func_name=func.name,
            )

        return process.returncode or 0, stdout_bytes, stderr_bytes

    # ------------------------------------------------------------------
    # New results: block (per-exit-code, SD-3)
    # ------------------------------------------------------------------

    def _handle_results_block(
        self,
        exit_code: int,
        stdout_bytes: bytes,
        stderr_bytes: bytes,
        func: CliFunction,
        context: BrimleyContext,
    ) -> Any:
        """Apply per-exit-code first-match against ``results:`` block."""
        mapping = _match_exit_code(exit_code, func.results or {})

        if mapping is None:
            # No mapping — default: exit 0 → text, non-zero → error with stderr.
            if exit_code == 0:
                raw: Any = stdout_bytes.decode(errors="replace")
            else:
                stderr_text = stderr_bytes.decode(errors="replace").strip()
                raise BrimleyExecutionError(
                    message=(
                        f"CLI command '{func.command}' exited with code "
                        f"{exit_code}: {stderr_text}"
                    ),
                    func_name=func.name,
                )
            return ResultMapper.map_result(raw, func, context)

        if mapping.error is not None:
            stderr_text = stderr_bytes.decode(errors="replace").strip()
            raise BrimleyExecutionError(
                message=str(mapping.error),
                func_name=func.name,
            )

        if mapping.empty:
            return ResultMapper.map_result(None, func, context)

        parser = get_parser(mapping.type or "text", func.name)
        raw = parser.parse(stdout_bytes, mapping.parse, func.name)
        return ResultMapper.map_result(raw, func, context)

    # ------------------------------------------------------------------
    # Legacy parsing: block (backward compat)
    # ------------------------------------------------------------------

    def _handle_legacy_parsing(
        self,
        exit_code: int,
        stdout_bytes: bytes,
        stderr_bytes: bytes,
        func: CliFunction,
        context: BrimleyContext,
    ) -> Any:
        """Apply legacy single-strategy parsing and non-zero-as-error behaviour."""
        if exit_code != 0:
            stderr_text = stderr_bytes.decode(errors="replace").strip()
            raise BrimleyExecutionError(
                message=(
                    f"CLI command '{func.command}' exited with code "
                    f"{exit_code}: {stderr_text}"
                ),
                func_name=func.name,
            )

        stdout_text = stdout_bytes.decode(errors="replace")

        raw_result: Any
        if func.parsing:
            raw_result = _parse_output(stdout_text, func.parsing, func.name)
        else:
            raw_result = stdout_text

        return ResultMapper.map_result(raw_result, func, context)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _render(template_str: str, ctx: Dict[str, Any]) -> str:
    """Render a Jinja2 template string using the sandboxed environment."""
    return _JINJA_ENV.from_string(template_str).render(**ctx)


def _validate_arg_no_metachar(value: str, func_name: str) -> None:
    """
    Reject rendered command_arguments entries containing shell metacharacters.

    Protects against command injection when user-supplied values are injected
    into the subprocess argument vector.  Even though we use ``shell=False``,
    rejecting metacharacters provides defence-in-depth.

    Raises :class:`BrimleyExecutionError` on violation.
    """
    if _SHELL_METACHAR_PATTERN.search(value):
        raise BrimleyExecutionError(
            message=(
                f"Rendered argument contains shell metacharacters which are "
                f"not permitted: {value!r}"
            ),
            func_name=func_name,
        )


def _match_exit_code(
    exit_code: int,
    results: Dict[str, ResultMapping],
) -> Optional[ResultMapping]:
    """
    Ordered first-match against a ``results:`` CLI exit-code block.

    Supports exact numeric keys (``"0"``–``"255"``) and ``"default"`` catch-all.
    No wildcard patterns for CLI (exit codes enumerated explicitly per SD-3).
    """
    for key, mapping in results.items():
        if key == "default":
            return mapping
        if re.fullmatch(r"\d+", key) and int(key) == exit_code:
            return mapping
    return None


def _parse_output(stdout: str, cfg: CliParsingConfig, func_name: str) -> Any:
    """Apply the legacy single-strategy parsing from the ``parsing:`` block."""
    if cfg.strategy == "json":
        try:
            return json.loads(stdout)
        except json.JSONDecodeError as exc:
            raise BrimleyExecutionError(
                message=f"Failed to parse stdout as JSON: {exc}",
                func_name=func_name,
            ) from exc

    if cfg.strategy == "regex":
        if not cfg.pattern:
            raise BrimleyExecutionError(
                message="'regex' parsing strategy requires a 'pattern' field.",
                func_name=func_name,
            )
        match = re.search(cfg.pattern, stdout)
        if not match:
            raise BrimleyExecutionError(
                message=(
                    f"Regex pattern '{cfg.pattern}' did not match stdout output."
                ),
                func_name=func_name,
            )
        if cfg.capture_group:
            try:
                return match.group(cfg.capture_group)
            except IndexError:
                return match.group(0)
        return match.group(0)

    # strategy == "text" (default) — return stdout as-is.
    return stdout
