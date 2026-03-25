# Changelog

All notable changes to Brimley are documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

---

## [0.8.0] - 2026-03-25

### Added

- **`@provider` decorator** — marks a callable as a DI-managed dependency provider. Supports `scope="singleton"` (default) and `scope="request"`. Yield-based providers run setup code before `yield` and teardown on `shutdown()`. Eager providers (`eager=True`) are constructed during the startup phase. Provider name may be overridden with `name="..."`.
- **`@on_startup` decorator** — marks a callable as a lifecycle hook executed after all singleton providers are initialised. Hooks run in declaration order. Supports both sync and async callables.
- **`@on_shutdown` decorator** — marks a callable as a teardown lifecycle hook executed on graceful shutdown, in reverse declaration order.
- **`Depends()` marker** — used as a parameter default in `@function` signatures to inject a named provider at execution time. `Depends`-annotated parameters are excluded from CLI/REPL/MCP argument schemas.
- **`BrimleyContainer`** — central DI container with `register_provider()`, `resolve()`, `override()`, `reset_overrides()`, `shutdown()`, `load_eager_providers()`, and `request_scope()` context manager. Stored on `BrimleyContext.container` after startup.
- **`DependencyResolver`** — topological sort and cycle detection for the provider dependency graph. Validates the full graph at startup; aborts with a clear cycle-path message on circular dependencies.
- **`container.override()` seam** — replaces a provider factory for testing or mock integration. `reset_overrides()` restores the original. This is the stable seam for v0.9 Mocking integration.
- **Request-scoped providers** — `Dispatcher.run()` wraps every invocation in `container.request_scope(context)`. Request-scoped providers are constructed fresh per call and torn down after (even on error).
- **Activated `provider` secret source** — `secrets:` blocks on API/CLI functions may now declare `- provider: name` sources. Resolved via `container.resolve(name)` at call time. The provider must return a `str`. Previously blocked with `BrimleySecretResolutionError` at scan time (v0.7).
- **Database connection providers** — connections declared in `databases:` are auto-registered as lazy singleton providers (`db_<name>`). `SqlRunner` resolves connections through the container with a fallback to `context.databases` for backward compatibility.
- **AST detection of DI decorators** — `@provider`, `@on_startup`, `@on_shutdown` are detected by `parse_python_file()` via `ast.parse()` (zero-execution). Scope, eager, and name kwargs are extracted from AST literal arguments.
- **`BrimleyScanResult` DI fields** — `providers: List[ProviderMetadata]` and `lifecycle_hooks: List[LifecycleHookMetadata]` fields added. Duplicate provider names produce `ERR_DUPLICATE_PROVIDER` diagnostics.
- **DI startup sequence** — boot path extended: after scan, `BrimleyContainer` is created, provider modules are imported, the dependency graph is validated, eager providers are loaded, `@on_startup` hooks run, and `context.container` is set. Fail-fast with `@on_shutdown` cleanup on any error. `system_boot` correlation ID is active during startup.
- **`BrimleyContext.container` field** — `Optional[BrimleyContainer]` field (defaults to `None`). Populated at the end of the DI startup phase.
- **Top-level exports** — `provider`, `on_startup`, `on_shutdown`, `Depends`, and `BrimleyContext` are now importable directly from `brimley` (`from brimley import provider, Depends, BrimleyContext`).
- **`examples/di_provider.py`** — new example demonstrating `@provider` with yield teardown, `@on_startup` hook, and `@function` with `Depends()` injection.

### Changed

- `pyproject.toml` version bumped to `0.8.0`.
- `resolve_secrets()` gains an optional `container` parameter; `ApiRunner` and `CliRunner` pass `context.container` through.
- `SqlRunner` resolves database connections via `container.resolve(f"db_{connection_name}")` when a container is set; falls back to `context.databases` for backward compatibility.
- `Dispatcher._dispatch_sync_call()` and `PythonRunner.run()` accept a `request_ctx` parameter for request-scoped provider resolution.
- `validate_secrets_no_provider()` removed from `api_parser.py` and `cli_parser.py` — `provider:` sources are now accepted at scan time.

---

## [0.7.0] - 2026-03-20

### Added

- **`api_function` type** — YAML-declared HTTP integrations backed by `httpx` async execution. Fields: `request` (method, url, headers, body, timeout), `response` (status-code → handler map with `type`, `parse.path`, and `error` keys), `secrets`, `mcp`, `return_shape`. Introduced in Brimley 0.7 (ADR-0002).
- **`cli_function` type** — YAML-declared shell command wrappers backed by `asyncio.create_subprocess_exec` (`shell=False` enforced). Fields: `command`, `args` (Jinja2 template list), `timeout_seconds` (required, no default), `cwd` (defaults to project root), `env` (explicit whitelist), `parsing` (text/json/regex strategies), `secrets`, `mcp`, `return_shape`. Introduced in Brimley 0.7 (ADR-0002).
- **`secrets:` block** — Uniform ordered-source resolution for `api_function` and `cli_function` YAML definitions (ADR-0003). Each named secret declares an ordered list of sources; the first non-empty value wins. `env:` sources are fully resolved in v0.7. `provider:` sources were structurally recognised but raised `BrimleySecretResolutionError` at scanner load time until DI (v0.8, now resolved).
- **`BaseRunner` abstract interface** — `execution/base_runner.py` defines `can_handle(func)` and `run(func, args, context)` as the internal runner contract (ADR-0004; external plugin loading deferred to v0.13).
- **`ApiRunner`** — Implements `BaseRunner`. Jinja2 `StrictUndefined` templating for URL, headers, and body. Correlation ID available as `{{ correlation_id }}` in templates. Secrets available as `{{ secrets.<name> }}`. Minimal JSONPath extraction (`$.key`, `$.key.sub`) from JSON responses. Async httpx execution.
- **`CliRunner`** — Implements `BaseRunner`. `asyncio.create_subprocess_exec` only (no `shell=True` ever). Args rendered via Jinja2 from the declared `args:` list. Only explicitly declared `env:` keys forwarded to subprocess. `asyncio.wait_for` timeout with process kill on expiry. Stdout parsing: `text` (passthrough), `json` (stdlib), `regex` (named capture group support).
- **`BrimleySecretResolutionError`** — New exception in `utils/secrets.py`; inherits `ValueError` so parsers can raise it and the Scanner converts it to a `BrimleyDiagnostic`.
- **`resolve_secrets()`** — Module-level helper in `utils/secrets.py`; resolves `env:` sources in declared order at call time.
- **`validate_secrets_no_provider()`** — Module-level helper in `utils/secrets.py`; called at scan time to reject `provider:` sources with a clear startup error.
- **Secret log redaction** — Two-layer automatic redaction for resolved secret values. Layer 1: Loguru sink filter scrubs secrets from all log records before they reach stderr or file sinks. Layer 2: `BrimleyExecutionError` messages are scrubbed before being embedded in exception text. Secret values ≤ 2 characters are excluded to avoid false positives. Implemented via `redact_secrets()`, `register_secrets()`, `clear_secrets()`, and `get_registered_secrets()` in `utils/secrets.py`.
- **YAML scanner extension** — `Scanner` now detects `.yaml` and `.yml` files. Files with `type: api_function` or `type: cli_function` are parsed and registered. Unknown YAML files are silently ignored.
- **`api_parser.py` / `cli_parser.py`** — New parsers in `discovery/` for YAML function files.
- **Dispatcher routing** — `Dispatcher._dispatch_sync_call()` routes `api_function` → `ApiRunner` and `cli_function` → `CliRunner`. Documented v0.9 stub intercept points left for future `MockRegistry` integration.
- **`httpx`** added as a core dependency (`>=0.27.0`).

### Changed

- `pyproject.toml` version bumped to `0.7.0`.

### Known Gaps (v0.7 Release)

- **`provider` secret sources** raised `BrimleySecretResolutionError` at startup until DI was available. *(Resolved in 0.8.)*
- **MockRegistry intercept** for `ApiRunner`/`CliRunner` is deferred to v0.9 Mocking. Stub intercept points are in place in `Dispatcher._dispatch_sync_call()`.
- **Full JSONPath** support (wildcards, filters) in `ApiRunner` requires an external library; deferred. Only `$.key` and `$.key.subkey` patterns are currently supported.

---

## [0.6.1] - 2026-03-17

### Fixed

- SQL functions now commit correctly when DML statements return rows (for example `INSERT ... RETURNING` in SQLite). `SqlRunner` now commits after consuming row-returning results, preventing writes from being dropped on successful execution.
- Added regression coverage for row-returning DML commit behavior via `test_sql_execution_insert_returning_commits` in `tests/test_execution_sql.py`.

### Changed

- Documentation versioning policy is now standardized around baseline markers (for example `Docs baseline: 0.6.x`) to reduce per-doc point-version churn.
- Removed stale per-doc `Version 0.6` headers in active specs and normalized outdated historical body wording where exact point versions were no longer semantically necessary.

## [0.6.0] - 2026-03-16

### Added

- **Structured logging via Loguru** — Brimley now owns and configures the Loguru logging pipeline at startup. All internal logs use a consistent `[timestamp] | level | [ID: correlation_id] | module:fn:line - message` format.
- **Correlation IDs** — Every top-level `Dispatcher.run()` call gets a unique 8-character correlation ID stored in a `ContextVar`. Nested calls inherit the parent ID. Async and thread-pool contexts preserve the ID correctly.
- **External trace ID alignment** — When FastMCP provides a `request_id`, Brimley captures it as `external_trace_id` and falls back to `correlation_id` for local-only runs. Both fields are injected into every log record.
- **Dual-sink logging** — Stderr sink is always active (required for MCP transport compatibility). An optional file sink can be enabled via `logging.file` in `brimley.yaml`.
- **File sink features** — JSONL format (`format: jsonl`), rotation (`rotation: 10 MB`, `daily`, etc.), and retention (`retention: 7 days`, `4 weeks`, etc.). File sink level is independently configurable from the stderr sink.
- **Per-module level overrides** — Log4J-style prefix matching: `logging.modules` maps module name prefixes to log levels. Longest-prefix match wins.
- **CLI log overrides** — `--log-level` (global stderr level) and `--log-module MODULE:LEVEL` (per-module, repeatable) are now accepted by `brimley invoke`, `brimley repl`, and `brimley repl-daemon`.
- **REPL runtime log commands** — `/log-level`, `/log-level MODULE LEVEL`, `/log-modules`, `/log-reset` allow changing log verbosity without restarting the daemon.
- **Per-correlation runtime overrides** — In-flight log level overrides scoped to a specific correlation ID, used by the REPL `/log-level` commands.
- **FastMCP log interception** — An `InterceptHandler` redirects stdlib `logging` calls (used by FastMCP and SQLAlchemy) into the Loguru stream, decorating them with the same correlation ID as the surrounding Brimley execution.
- **`managed: false` escape hatch** — Setting `logging.managed: false` in `brimley.yaml` disables Brimley's Loguru setup entirely for environments that manage their own logging pipeline.
- **Top-level `logging:` key in `brimley.yaml`** — The `logging` configuration block is now accepted at the root level of `brimley.yaml` (previously it was only recognized when nested under `brimley:`).

### Fixed

- `load_config` was silently discarding the top-level `logging:` key because it was not in the allowed-keys allowlist. Log file sinks configured in `brimley.yaml` were never initialised.
- `BrimleyContext` was not forwarding the top-level `logging` dict to `FrameworkSettings`, so file sink settings (path, rotation, retention) were always `None` even when present in the config.

### Changed

- `logging.level` and `logging.file.level` now normalize all level strings to uppercase. Invalid levels raise a `ValueError` at config parse time.
- `load_config` allowed-keys list extended with `"logging"`.
- `examples/brimley.yaml` updated to use the top-level `logging:` key and demonstrate the full file-sink configuration.

---
