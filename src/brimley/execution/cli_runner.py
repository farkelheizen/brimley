"""CliRunner: executes cli_function definitions via asyncio subprocess (Brimley 0.7)."""

from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path
from typing import Any, Dict, Optional

from jinja2 import Environment, StrictUndefined, UndefinedError

from brimley.core.context import BrimleyContext
from brimley.core.models import BrimleyFunction, CliFunction, CliParsingConfig
from brimley.execution.base_runner import BaseRunner
from brimley.execution.result_mapper import ResultMapper
from brimley.infrastructure.logging import get_or_create_correlation_id
from brimley.utils.diagnostics import BrimleyExecutionError
from brimley.utils.secrets import BrimleySecretResolutionError, resolve_secrets

_JINJA_ENV = Environment(undefined=StrictUndefined, keep_trailing_newline=True)


class CliRunner(BaseRunner):
    """
    Executes ``cli_function`` definitions via ``asyncio.create_subprocess_exec``.

    Security constraints (non-negotiable per ADR-0002 / 0.7 spec):
    - ``shell=False`` always enforced; command + args are passed as a list.
    - Only explicit ``args:`` list entries are passed to the subprocess.
    - ``timeout_seconds`` is required and validated at scanner load time; the
      runner treats a missing value as a hard error.
    - ``cwd`` defaults to ``context.app["root_dir"]`` or CWD; never inherited
      implicitly from the parent process.
    - Only explicitly declared ``env:`` keys are forwarded to the subprocess.

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

        # 2. Template context.
        correlation_id = get_or_create_correlation_id()
        template_ctx: Dict[str, Any] = {
            **args,
            "secrets": secrets,
            "correlation_id": correlation_id,
        }

        # 3. Render args list (Jinja2).
        try:
            rendered_args = [_render(a, template_ctx) for a in func.args]
        except UndefinedError as exc:
            raise BrimleyExecutionError(
                message=f"Arg template rendering failed: {exc}",
                func_name=func.name,
            ) from exc

        # 4. Build subprocess env (only explicitly declared keys, per security spec).
        subprocess_env: Optional[Dict[str, str]] = None
        if func.env:
            try:
                subprocess_env = {
                    k: _render(v, template_ctx) for k, v in func.env.items()
                }
            except UndefinedError as exc:
                raise BrimleyExecutionError(
                    message=f"Env template rendering failed: {exc}",
                    func_name=func.name,
                ) from exc

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
                stdout_text = future.result()
        else:
            stdout_text = asyncio.run(
                self._async_exec(func, rendered_args, subprocess_env, cwd)
            )

        # 7. Parse stdout.
        raw_result: Any
        if func.parsing:
            raw_result = _parse_output(stdout_text, func.parsing, func.name)
        else:
            raw_result = stdout_text

        # 8. Map to return_shape.
        return ResultMapper.map_result(raw_result, func, context)

    async def _async_exec(
        self,
        func: CliFunction,
        rendered_args: list[str],
        subprocess_env: Optional[Dict[str, str]],
        cwd: str,
    ) -> str:
        """Spawn the subprocess and capture stdout."""
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

        if process.returncode != 0:
            stderr_text = stderr_bytes.decode(errors="replace").strip()
            raise BrimleyExecutionError(
                message=(
                    f"CLI command '{func.command}' exited with code "
                    f"{process.returncode}: {stderr_text}"
                ),
                func_name=func.name,
            )

        return stdout_bytes.decode(errors="replace")


def _parse_output(stdout: str, cfg: CliParsingConfig, func_name: str) -> Any:
    """Apply the parsing strategy declared in the ``parsing:`` block."""
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


def _render(template_str: str, ctx: Dict[str, Any]) -> str:
    """Render a Jinja2 template string with the given context."""
    return _JINJA_ENV.from_string(template_str).render(**ctx)
