# 20260323-brimley-0.8 Plan: Dependency Injection & Managed Objects

> Date: 3/23/2026
> Owner: Copilot
> Branch: `copilot/plan-b08` (integration branch; step branches merge here, final merge to `main`)
> Related docs: `docs/roadmap/brimley-0.8-dependency-injection-and-managed-objects.md`, `docs/decisions/0001-swap-di-and-mocking-order.md`, `docs/decisions/0003-secrets-block-ordered-resolution.md`, `docs/brimley-discovery-and-loader-specification.md`, `docs/brimley-high-level-design.md`, `docs/brimley-context.md`, `docs/brimley-secrets.md`, `docs/brimley-python-functions.md`, `docs/brimley-configuration.md`, `docs/brimley-sql-execution.md`

This file is intended as a working implementation plan.

## Problem Summary

Brimley 0.7 shipped API and CLI functions, a uniform `secrets:` block with ordered-source resolution, and security hardening. However, `provider` secret sources raise `BrimleySecretResolutionError` at startup because no DI system exists. There is no mechanism for managing shared resources (database pools, HTTP clients) with proper lifecycle semantics, and no way for `@function`-decorated callables to receive managed dependencies beyond the existing `AppState`/`Config`/`Connection` markers.

The existing startup sequence is linear: load config → create context → scan → register → run. There is no "startup hook" phase, no managed shutdown, and no scoped lifecycle for per-request resources. The `SqlRunner` hardcodes engine lookup from `context.databases`, and the `httpx` client used by `ApiRunner` is created per-call with no connection reuse.

ADR-0001 establishes that DI must precede Mocking so that v0.9 can integrate via `BrimleyContainer.override()` rather than building a redundant standalone registry. ADR-0003 designed the secrets schema to be forward-compatible: `provider:` sources are structurally valid in v0.7 YAML but blocked until DI activates them.

## Goal

Deliver a custom, AST-aware Dependency Injection system (`BrimleyContainer`) with `singleton` and `request` scoped providers, `Depends()` injection into `@function` arguments, `@on_startup`/`@on_shutdown` lifecycle hooks, activation of `provider` secret sources, and `container.override()` exposed for v0.9 Mocking integration — all following the existing two-phase (AST scan → runtime import) discovery model.

## Scope

- In scope:
  - `@provider(scope="singleton"|"request")` decorator: marks a callable as a managed dependency provider
  - `@on_startup` decorator: marks a callable to run after all singletons are initialized
  - `@on_shutdown` decorator: marks a callable to run on graceful shutdown
  - `Depends()` marker: injects a provider's resolved value into a `@function` argument default
  - `BrimleyContainer`: central container for provider registration, resolution, lifecycle, override
  - AST detection of `@provider`, `@on_startup`, `@on_shutdown` in the Python parser (zero-execution scan)
  - Scanner extension: `BrimleyScanResult` includes provider metadata and lifecycle hook metadata
  - Two-phase provider lifecycle: AST scan records metadata; startup imports modules and constructs eagerly-marked providers
  - Yield-based provider teardown (generator protocol for setup/cleanup)
  - Eager vs. lazy singleton providers (`eager=True` forces construction at startup)
  - Request-scoped providers: constructed per `Dispatcher.run()` call, torn down after
  - `DependencyResolver`: topological resolution of provider dependencies, cycle detection
  - Startup sequence overhaul: config → context → scan → container init → import → eager load → `@on_startup` hooks → ready
  - Fail-fast policy: unhandled exceptions in eager providers or startup hooks abort startup with cleanup
  - `container.override(provider_name, mock_impl)` API exposed for v0.9 Mocking seam
  - Activation of `provider` secret source in `resolve_secrets()` via `container.resolve()`
  - Removal of `validate_secrets_no_provider()` startup blocker
  - SQL connection as a managed provider (`db_connection`) — lazy singleton, used by `SqlRunner`
  - `BrimleyContext` gains a `container` field referencing the `BrimleyContainer`
  - Public API exports: `provider`, `on_startup`, `on_shutdown`, `Depends`, `BrimleyContext`
  - Diagnostic logging for DI errors with `system_boot` correlation ID
  - CHANGELOG, examples, version bump, doc scan gate

- Out of scope:
  - Named/qualified bindings and multibindings
  - Interceptors or middleware hooks
  - Circular dependency resolution (detected and reported as fatal error)
  - Property injection
  - Hierarchical containers / child scopes
  - XML, annotation, or config-file-based wiring
  - `@brimley.mock` decorator and `MockRegistry` (v0.9)
  - Full mocking framework (v0.9 — only `container.override()` API surface exposed)
  - Plugin architecture (v0.13)

## Constraints / Requirements

- Treat `docs/roadmap/brimley-0.8-dependency-injection-and-managed-objects.md` as the source of truth for v0.8 behavior.
- Respect ADR-0001 (DI precedes Mocking; custom AST-aware system required) and ADR-0003 (secrets ordered-source resolution; `provider` source activates in v0.8).
- **Zero-execution AST scan**: `@provider`, `@on_startup`, `@on_shutdown` must be detected via `ast.parse()` without importing or executing user modules. Follow the same two-phase pattern as `@function` and `@entity`.
- **Minimal scope**: Only `singleton` and `request` scopes. No named bindings, no multibindings, no interceptors, no hierarchical containers.
- **Fail-fast**: If any `@on_startup` hook or `eager=True` provider raises, startup aborts. Cleanup runs all registered `@on_shutdown` hooks and provider teardowns before exit.
- **`container.override()`**: Must be exposed in v0.8, even though the Mocking framework is v0.9. This is the stable seam for mock integration.
- **Provider teardown**: Yield-based generator protocol. `next()` to produce value, generator `close()` for cleanup at shutdown.
- **Async support**: Providers and lifecycle hooks may be `async def`. The startup sequence must handle both sync and async callables.
- **Declaration-order execution**: `@on_startup` hooks execute in declaration (scan) order. `@on_shutdown` hooks execute in reverse declaration order.
- **`BrimleyContext` injectable**: Providers and hooks may declare `ctx: BrimleyContext` as a parameter; the container injects the current context.
- **Depends() applies to Python functions only**: YAML-based function types (SQL, template, API, CLI) do not have Python call signatures — `Depends()` is limited to `@function`-decorated callables.
- Use Poetry commands for all validation/test execution.
- Preserve all existing v0.7 behavior and test coverage.

---

## Implementation Plan

| Step ID | Status | Goal | Planned Changes | Test Coverage |
|---|---|---|---|---|
| B08-S1 | Completed | Domain models for providers, hooks, and Depends marker | `core/models.py`: `ProviderMetadata`, `LifecycleHookMetadata`; `core/di.py`: `Depends` class; `__init__.py`: `@provider`, `@on_startup`, `@on_shutdown` decorators | `tests/test_di_models.py` (models validation); `tests/test_decorators.py` (decorator attachment) |
| B08-S2 | Completed | AST detection of DI decorators | `discovery/python_parser.py`: detect `@provider`, `@on_startup`, `@on_shutdown` via AST; extract scope, eager, name kwargs | `tests/test_discovery_di.py` (AST parsing for providers + hooks) |
| B08-S3 | Completed | Scanner extension for providers and hooks | `discovery/scanner.py`: `BrimleyScanResult` gains `providers` and `lifecycle_hooks` fields; validation (name collisions, diagnostics) | `tests/test_discovery_di.py` (scanner integration, duplicate detection, diagnostics) |
| B08-S4 | Completed | BrimleyContainer core (singleton lifecycle) | New `core/container.py`: `BrimleyContainer` class with `register_provider()`, `resolve()`, `override()`, `reset()`; singleton scope; lazy and eager modes; yield-based teardown | `tests/test_container.py` (register, resolve, override, eager, lazy, teardown, error cases) |
| B08-S5 | Completed | DependencyResolver and request scope | New `core/resolver.py`: topological sort, cycle detection, `BrimleyContext` injection; `BrimleyContainer` gains request-scoped provider support with enter/exit request context | `tests/test_resolver.py` (topological order, cycle detection, BrimleyContext injection); `tests/test_container.py` (request scope lifecycle) |
| B08-S6 | Not Started | Startup sequence integration | `cli/main.py` boot path: after scan, init container → import provider modules → construct eager singletons → run `@on_startup` hooks → set context.container; fail-fast with cleanup on error; `system_boot` correlation ID; `infrastructure/logging.py` integration | `tests/test_startup.py` (happy path, eager failure abort, hook failure abort, cleanup runs, ordering) |
| B08-S7 | Not Started | Dispatcher request-scope lifecycle | `execution/dispatcher.py`: `Dispatcher.run()` creates request-scope context on container before dispatch, tears down after; passes container reference through execution | `tests/test_dispatcher_di.py` (request-scoped providers created/destroyed per run, no leaks) |
| B08-S8 | Not Started | Depends() injection in PythonRunner | `execution/python_runner.py` + `execution/arguments.py`: detect `Depends()` defaults in function signatures; resolve via container before execution; skip `Depends` args from user-supplied input | `tests/test_injection.py` (Depends resolution, mixed args, missing provider error) |
| B08-S9 | Not Started | Activate `provider` secret source | `utils/secrets.py`: `resolve_secrets()` calls `container.resolve(provider_name)` for `provider:` sources; remove `validate_secrets_no_provider()` gate; update all callers (parsers) | `tests/test_secrets.py` (provider source resolution, fallback ordering, mixed env+provider) |
| B08-S10 | Not Started | SQL connection as managed provider | Internal `db_connection` provider auto-registered by container from `context.databases` config; `SqlRunner` resolves connection via container instead of direct `context.databases` lookup; lazy singleton | `tests/test_execution_sql.py` (SQL runner uses provider, backward compat with existing config) |
| B08-S11 | Not Started | Public API exports and example files | `__init__.py`: export `provider`, `on_startup`, `on_shutdown`, `Depends`, `BrimleyContext`; new example file demonstrating provider + Depends usage | `tests/test_packaging_contract.py` (import assertions) |
| B08-S12 | Not Started | Documentation updates | Update: `brimley-high-level-design.md`, `brimley-context.md`, `brimley-secrets.md`, `brimley-python-functions.md`, `brimley-discovery-and-loader-specification.md`, `brimley-configuration.md`, `copilot-docs-reference.md`, `README.md`; new DI section in high-level design | Docs conformance review |
| B08-S13 | Not Started | Version bump, CHANGELOG, doc scan gate | `pyproject.toml` → 0.8.0; `CHANGELOG.md` updated; `examples/README.md` if affected; stale version refs updated | Full suite pass |
| B08-S14 | Not Started | Final validation and release gate | Full test suite; regression check; review approval | Full suite pass |

Status values: `Not Started` | `In Progress` | `Completed` | `Blocked`

---

## Step Details

### B08-S1: Domain Models, Depends Marker, and Decorators

**Files (expected):**
- `src/brimley/core/models.py` — add `ProviderMetadata`, `LifecycleHookMetadata`
- `src/brimley/core/di.py` — add `Depends` class
- `src/brimley/__init__.py` — add `@provider`, `@on_startup`, `@on_shutdown` decorators; export `Depends`
- `tests/test_di_models.py` — model validation tests
- `tests/test_decorators.py` — extend with new decorator tests

**Implementation notes:**
- `ProviderMetadata` (Pydantic model): `name: Optional[str]`, `scope: Literal["singleton", "request"]`, `eager: bool = False`, `module_path: str`, `func_name: str`, `handler: Optional[str]` (dotted import path). Scope defaults to `"singleton"` per spec.
- `LifecycleHookMetadata` (Pydantic model): `hook_type: Literal["on_startup", "on_shutdown"]`, `module_path: str`, `func_name: str`, `handler: Optional[str]`.
- `Depends` class: stores a provider name (string). Usage: `client: httpx.AsyncClient = Depends(get_http_client)`. Per Open Question 1 decision: the provider function name is the provider name unless overridden by `@provider(name="...")`. At AST-scan time the `Depends()` argument is extracted as a string from the AST; at runtime the container resolves by matching that string to a registered provider name.
- `@provider` decorator: attaches `_brimley_meta` with `type: "provider"`, `scope`, `eager`, `name` — same pattern as `@function` and `@entity`.
- `@on_startup` / `@on_shutdown`: attach `_brimley_meta` with `type: "on_startup"` / `type: "on_shutdown"`.
- All three decorators support bare (`@provider`) and configured (`@provider(scope="request")`) forms, matching existing decorator conventions.

**Definition of done:**
- `ProviderMetadata` and `LifecycleHookMetadata` models validate correctly with Pydantic.
- `Depends(some_func)` stores the reference and is usable as a default value.
- `@provider`, `@on_startup`, `@on_shutdown` attach `_brimley_meta` to decorated callables.
- All model and decorator tests pass.

---

### B08-S2: AST Detection of DI Decorators

**Files (expected):**
- `src/brimley/discovery/python_parser.py` — extend `_find_brimley_decorators()` and add provider/hook extraction logic

**Implementation notes:**
- Add `_PROVIDER_DECORATORS = {"provider", "brimley.provider"}` and similar sets for `on_startup`/`on_shutdown`.
- `_find_brimley_decorators()` already walks AST nodes and matches decorator names. Extend it to detect the new decorators and classify them (`"provider"`, `"on_startup"`, `"on_shutdown"`).
- For `@provider`: extract `scope` (default `"singleton"`), `eager` (default `False`), `name` kwargs from the AST `Call` node via `_extract_decorator_kwargs()`.
- For `@on_startup` / `@on_shutdown`: no kwargs needed beyond the function reference.
- Return new metadata types (`ProviderMetadata`, `LifecycleHookMetadata`) alongside existing `PythonFunction` / `DiscoveredEntity` results.
- `parse_python_file()` must return a mixed list or separate collections for functions, entities, providers, and hooks.

**Definition of done:**
- AST parsing of a Python file with `@provider`, `@on_startup`, `@on_shutdown` produces correct metadata objects.
- Scope, eager, and name kwargs are extracted when present on `@provider`.
- Files with no DI decorators produce empty provider/hook lists (no regression).
- Tests cover: bare decorator, configured decorator, async def, sync def, multiple providers per file.

---

### B08-S3: Scanner Extension for Providers and Hooks

**Files (expected):**
- `src/brimley/discovery/scanner.py` — `BrimleyScanResult` gains `providers: List[ProviderMetadata]` and `lifecycle_hooks: List[LifecycleHookMetadata]`
- `tests/test_discovery_di.py` — scanner-level integration tests

**Implementation notes:**
- `BrimleyScanResult` adds two new fields with `Field(default_factory=list)`.
- `Scanner.scan()` collects providers and hooks from `parse_python_file()` results and appends to the scan result.
- Validation: provider names must pass the same `NAME_REGEX` as functions. Duplicate provider names produce `ERR_DUPLICATE_PROVIDER` diagnostics.
- Lifecycle hooks do not require names — they are ordered by declaration.
- No collision between provider names and function names (different namespaces), but log a warning if a provider name shadows a function name for discoverability.

**Definition of done:**
- `BrimleyScanResult.providers` and `.lifecycle_hooks` populated from scan.
- Duplicate provider names produce diagnostics (not crash).
- Existing function/entity scanning is unaffected.
- Integration tests pass with fixture files containing providers and hooks.

---

### B08-S4: BrimleyContainer Core (Singleton Lifecycle)

**Files (expected):**
- `src/brimley/core/container.py` (new)
- `tests/test_container.py` (new)

**Implementation notes:**
- `BrimleyContainer` is the central DI container. It is **not** a Pydantic model — it's a plain Python class with explicit lifecycle methods.
- **Registration**: `register_provider(metadata: ProviderMetadata, factory: Callable)` — stores factory + metadata. Factory is the actual imported callable (set during startup phase, not scan phase).
- **Singleton resolution**: `resolve(name: str) -> Any` — for singleton scope: construct on first call (lazy) or at startup (eager), cache result. If factory is a generator (uses `yield`), call `next()` to get value, store generator for teardown.
- **Eager loading**: `load_eager_providers()` — resolve all providers marked `eager=True`. Called during startup.
- **Override**: `override(name: str, factory: Callable)` — replaces a provider's factory. Original is saved for `reset_overrides()`. This is the v0.9 Mocking seam.
- **Teardown**: `shutdown()` — for each singleton holding a generator, call `generator.close()`. Run in reverse-registration order.
- **Error handling**: `resolve()` raises `BrimleyDIError` (new exception) for unknown providers, construction failures. Startup errors propagate for fail-fast.
- Thread safety: singleton resolution uses a lock to prevent double-construction in concurrent dispatch.

**Definition of done:**
- Singleton providers can be registered, resolved (lazy), and torn down.
- Eager providers are constructed via `load_eager_providers()`.
- `override()` replaces a provider; `reset_overrides()` restores original.
- Yield-based providers execute setup code before yield, cleanup after `shutdown()`.
- Thread-safe resolution (no double-construction under concurrent access).
- Unknown provider raises clear error.
- All container tests pass.

---

### B08-S5: DependencyResolver and Request Scope

**Files (expected):**
- `src/brimley/core/resolver.py` (new)
- `src/brimley/core/container.py` — add request-scope methods
- `tests/test_resolver.py` (new)
- `tests/test_container.py` — extend with request-scope tests

**Implementation notes:**
- `DependencyResolver`: given a provider's factory signature, determine what other providers it depends on (via `Depends()` defaults or `BrimleyContext` type hint). Build topological order for construction.
- **Cycle detection**: if A depends on B and B depends on A, raise `BrimleyDIError` with clear cycle path message. Cycle detection runs at startup (during graph construction), not lazily.
- **`BrimleyContext` injection**: if a provider or hook declares a parameter typed as `BrimleyContext`, the container injects the current context. This is a special-case resolution, not a registered provider.
- **Request scope**: `BrimleyContainer.enter_request_scope() -> RequestContext` and `exit_request_scope(rc)`. `RequestContext` holds request-scoped provider instances. `resolve()` checks request scope first, then singleton scope. Request-scoped providers are constructed on first `resolve()` within a request context and torn down on `exit_request_scope()`.
- Per Open Question 2 decision: use **explicit parameter passing** for the `RequestContext` through the dispatch chain rather than `contextvars.ContextVar`. The `RequestContext` object is passed from `Dispatcher.run()` → `_dispatch_sync_call()` → Runner → `resolve()`. This avoids thread-boundary surprises with the existing `ContextVar`-based correlation ID mechanism.

**Definition of done:**
- Topological sort resolves providers in correct dependency order.
- Circular dependencies detected and reported with cycle path.
- `BrimleyContext` is injectable into providers and hooks.
- Request-scoped providers are created/destroyed per request context.
- No cross-request leakage of request-scoped provider instances.
- Tests pass for dependency chains, cycles, mixed scopes, context injection.

---

### B08-S6: Startup Sequence Integration

**Files (expected):**
- `src/brimley/cli/main.py` — boot path modification
- `src/brimley/core/container.py` — `startup()` orchestration method
- `src/brimley/core/context.py` — add `container: Optional[BrimleyContainer]` field
- `src/brimley/infrastructure/logging.py` — `system_boot` correlation ID
- `tests/test_startup.py` (new)

**Implementation notes:**
- Current boot sequence: load config → create context → init databases → init logging → scan → register functions/entities → launch.
- New boot sequence (after scan + register):
  1. Create `BrimleyContainer(context)`.
  2. Import provider modules (using `module_path` from `ProviderMetadata`). Failures are fatal (fail-fast).
  3. Set factory callables on container from imported modules.
  4. Run `DependencyResolver` to validate dependency graph (cycle detection). Failures are fatal.
  5. Call `container.load_eager_providers()`. Failures are fatal; run cleanup before abort.
  6. Execute all `@on_startup` hooks in declaration order. Hook arguments resolved via container (including `BrimleyContext`). Failures are fatal; run cleanup before abort.
  7. Set `context.container = container`.
  8. Application is ready.
- **Fail-fast cleanup**: on abort, call `container.shutdown()` to tear down any already-constructed providers and run `@on_shutdown` hooks for already-registered teardown.
- **`system_boot` correlation ID**: set a fixed correlation ID during the startup sequence for diagnostic log filtering.
- **MCP impact**: if startup fails, the MCP server does not send "Ready".
- **CLI/REPL impact**: if startup fails, process exits with non-zero status + traceback to stderr.

**Definition of done:**
- Happy-path boot completes: providers imported, eagerly loaded, hooks run, context.container set.
- Eager provider failure aborts startup, cleanup runs, non-zero exit.
- Startup hook failure aborts startup, cleanup runs, non-zero exit.
- `system_boot` correlation ID appears in startup-phase log records.
- Existing boot behavior preserved when no providers/hooks are declared.
- Tests cover happy path, eager failure, hook failure, missing module, cycle detection.

---

### B08-S7: Dispatcher Request-Scope Lifecycle

**Files (expected):**
- `src/brimley/execution/dispatcher.py`
- `tests/test_dispatcher_di.py` (new)

**Implementation notes:**
- `Dispatcher.run()` wraps each dispatch in a request-scope context: `rc = context.container.enter_request_scope()` before dispatch, `context.container.exit_request_scope(rc)` in a `finally` block.
- If no container is set on context (backward compat, e.g., tests), skip request-scope management.
- Request-scoped providers are now available during function execution and automatically torn down.
- Ensure FastMCP sync path also uses request-scope context.

**Definition of done:**
- Request-scoped providers are constructed fresh per `Dispatcher.run()` call.
- Request-scoped providers are torn down after dispatch completes (even on error).
- No request-scope management when `context.container` is `None` (backward compat).
- Tests cover: request-scope creation, teardown on success, teardown on exception, no leaks across calls.

---

### B08-S8: Depends() Injection in PythonRunner

**Files (expected):**
- `src/brimley/execution/python_runner.py`
- `src/brimley/execution/arguments.py`
- `tests/test_injection.py` — extend with Depends() resolution tests

**Implementation notes:**
- When `PythonRunner` prepares to call a `@function`, it inspects the function's signature for parameters whose default is a `Depends(...)` instance.
- For each `Depends(provider_ref)` parameter: resolve the provider via `context.container.resolve(provider_name)` and inject the value into the argument dict. Per Open Question 1 decision: the `provider_name` is the string name extracted from `Depends()` at scan time, matched to the provider's registered name (function name unless overridden by `@provider(name="...")`).
- `Depends` parameters are **not** exposed to callers (CLI, REPL, MCP) — they are hidden from the argument schema, similar to `from_context` arguments.
- The `ArgumentResolver` must skip `Depends`-marked parameters when validating user-supplied args.
- If the container cannot resolve a `Depends` provider, raise `BrimleyExecutionError` with a clear message.
- At AST scan time, `Depends(get_http_client)` is detected as a default value. The python_parser should record which arguments have `Depends` defaults so the argument schema excludes them.

**Definition of done:**
- `@function` with `Depends()` arguments receives resolved provider values at execution.
- `Depends` arguments are excluded from CLI/REPL/MCP argument schemas.
- Missing provider produces clear error, not crash.
- Mixed signatures (user args + Depends args + from_context args) work correctly.
- Tests pass for: basic injection, multiple Depends args, mixed signatures, missing provider error.

---

### B08-S9: Activate `provider` Secret Source

**Files (expected):**
- `src/brimley/utils/secrets.py` — update `resolve_secrets()` to call container; remove `validate_secrets_no_provider()`
- `src/brimley/discovery/python_parser.py` — remove call to `validate_secrets_no_provider()` (or make it a no-op)
- `src/brimley/discovery/api_parser.py` — remove provider-block validation
- `src/brimley/discovery/cli_parser.py` — remove provider-block validation
- `tests/test_secrets.py` — extend with provider source tests

**Implementation notes:**
- `resolve_secrets()` gains an optional `container: Optional[BrimleyContainer]` parameter.
- When encountering a `provider:` source, call `container.resolve(source.provider)` to obtain the secret value. The provider must return a `str`.
- Ordered fallback preserved: `env` → `provider` per ADR-0003.
- If container is `None` and a `provider` source is encountered, raise `BrimleySecretResolutionError` (preserves v0.7 behavior for edge cases).
- Remove `validate_secrets_no_provider()` calls from all parsers — provider sources are now functional.
- Runners (ApiRunner, CliRunner, SqlRunner, JinjaRunner) that call `resolve_secrets()` must pass the container reference.

**Definition of done:**
- `provider:` sources in `secrets:` blocks resolve via container.
- Mixed `env` + `provider` ordering works correctly.
- Fallback: env checked first, provider used if env is empty.
- No `BrimleySecretResolutionError` at startup for `provider:` sources.
- Error raised at call time if provider fails to produce a value.
- All existing secrets tests still pass (env-only paths unchanged).

---

### B08-S10: SQL Connection as Managed Provider

**Files (expected):**
- `src/brimley/core/container.py` — auto-registration of `db_connection` providers
- `src/brimley/execution/sql_runner.py` — resolve connection via container
- `src/brimley/infrastructure/database.py` — provide factory callable for container registration
- `tests/test_execution_sql.py` — extend with container-based connection tests

**Implementation notes:**
- During container initialization, for each entry in `context.databases`, auto-register a singleton provider named `db_<connection_name>` (e.g., `db_default`). The factory returns the SQLAlchemy engine.
- `SqlRunner.run()` resolves the connection engine via `container.resolve(f"db_{func.connection}")` instead of direct `context.databases[connection_name]` lookup.
- Fallback: if `context.container` is `None`, fall back to existing `context.databases` lookup for backward compatibility.
- Provider is `eager=False` by default (lazy) — engine not created until first SQL function call.
- Per the spec, this keeps startup instantaneous unless a SQL function is actually called.

**Definition of done:**
- `db_default` (and other database connections) registered as lazy singleton providers.
- `SqlRunner` resolves connections through the container.
- Backward-compatible: works without container (existing tests pass unmodified).
- Lazy initialization confirmed: engine not created until first resolve.
- Tests pass for container-based and fallback paths.

---

### B08-S11: Public API Exports and Example Files

**Files (expected):**
- `src/brimley/__init__.py` — update `__all__` exports
- `examples/` — new example demonstrating DI usage
- `tests/test_packaging_contract.py` — extend import assertions

**Implementation notes:**
- Add to `__all__`: `"provider"`, `"on_startup"`, `"on_shutdown"`, `"Depends"`, `"BrimleyContext"`.
- `BrimleyContext` export: currently `BrimleyContext` is importable from `brimley.core.context` — add a convenience re-export from the top-level package.
- New example file (e.g., `examples/di_provider.py`): demonstrate `@provider` with `yield`, `@function` with `Depends()`, `@on_startup` hook.
- Update `examples/README.md` version header if needed.

**Definition of done:**
- `from brimley import provider, on_startup, on_shutdown, Depends, BrimleyContext` works.
- New example file demonstrates core DI patterns.
- Packaging contract tests confirm all new exports are importable.

---

### B08-S12: Documentation Updates

**Files (expected):**
- `docs/brimley-high-level-design.md` — new §3 subsection for DI/Container
- `docs/brimley-context.md` — document `container` field
- `docs/brimley-secrets.md` — update `provider` source from "raises error" to "resolved via container"
- `docs/brimley-python-functions.md` — document `Depends()` in function signatures
- `docs/brimley-discovery-and-loader-specification.md` — document `@provider`/`@on_startup`/`@on_shutdown` AST detection
- `docs/brimley-configuration.md` — document any new config keys if needed
- `docs/copilot/copilot-docs-reference.md` — add DI topic row and keyword entries
- `README.md` — update feature list and documentation map

**Implementation notes:**
- Follow existing doc style and baseline conventions.
- Add keyword index entries for: `@provider`, `Depends`, `BrimleyContainer`, `on_startup`, `on_shutdown`, `DI`, `dependency injection`, `singleton`, `request scope`.
- Update the `brimley-secrets.md` "Resolution Rules" section to document `provider` source behavior.
- Update the Reference Documentation Map in `brimley-high-level-design.md` §5.

**Definition of done:**
- All affected docs updated to reflect v0.8 DI capabilities.
- No orphaned references to "v0.8+" or "deferred to DI" remaining in updated docs.
- Copilot docs reference map includes DI routing entries.

---

### B08-S13: Version Bump, CHANGELOG, Doc Scan Gate

**Files (expected):**
- `pyproject.toml` — version → `0.8.0`
- `CHANGELOG.md` — v0.8.0 entries under Added/Changed
- `examples/README.md` — version header update if examples changed
- Various docs — stale version reference sweep

**Implementation notes:**
- CHANGELOG entries: `@provider` decorator, `BrimleyContainer`, `Depends()`, `@on_startup`/`@on_shutdown`, `provider` secret source activation, SQL connection provider refactor, `container.override()` API.
- Doc scan gate per copilot-instructions §8:
  - **Baseline header sweep**: update `Docs baseline: 0.7.x` → `0.8.x` in all docs where content changed (following the 0.7 plan's B07-S21 precedent — targeted updates, not blanket rewrites per §8 Step 2).
  - **Stale body-text references**: update inline "v0.7" / "0.7" references where semantically stale (e.g., "deferred to v0.8" → now current).
  - **Reference maps**: update `brimley-high-level-design.md` §5, `copilot-docs-reference.md` topic table and keyword index.
  - **Feature mentions**: ensure `brimley-high-level-design.md` §3 includes a Key Component entry for DI/Container.
  - **Context doc**: update `brimley-context.md` with `container` field.
  - **Secrets doc**: remove "v0.8+" qualifier from `provider` source documentation.

**Definition of done:**
- `pyproject.toml` version is `0.8.0`.
- CHANGELOG has complete v0.8.0 section.
- `Docs baseline` headers updated to `0.8.x` in all docs with content changes.
- No stale "0.7" or "deferred to v0.8" references remaining in updated docs.
- Doc scan gate checklist completed per copilot-instructions §8 (Steps 1–3).

---

### B08-S14: Final Validation and Release Gate

**Files (expected):**
- None (validation only).

**Implementation notes:**
- Run full test suite.
- Verify no regressions from v0.7.
- Confirm `container.override()` is callable (v0.9 seam test).
- Review approval required before commit.

**Definition of done:**
- Full test suite green.
- No new warnings or deprecations.
- Review approval granted.

---

## Acceptance Criteria

- `@provider(scope="singleton")` and `@provider(scope="request")` work end-to-end: scan → register → resolve → teardown.
- `Depends(provider_func)` in `@function` signatures injects resolved values at execution time.
- `@on_startup` and `@on_shutdown` hooks execute in correct order during boot and shutdown.
- Yield-based providers execute setup before yield and cleanup on shutdown.
- `eager=True` providers are constructed during startup phase.
- Fail-fast: startup aborts on unhandled provider/hook exceptions with proper cleanup.
- `container.override()` replaces providers; `reset_overrides()` restores originals.
- `provider:` secret sources resolve via container at call time.
- `SqlRunner` resolves connections via container (with backward-compat fallback).
- `BrimleyContext.container` is populated after startup.
- No regressions in existing Python, SQL, template, API, or CLI function execution.
- No regressions in MCP tool registration or secrets resolution.
- Diagnostics/errors are clear and actionable for DI misconfiguration.
- Documentation updated where behavior changed.
- `CHANGELOG.md` updated with Added / Changed entries for v0.8.0.
- `examples/` updated with DI example file.
- Version bump performed: `pyproject.toml` updated to `0.8.0`.
- Doc Scan performed: stale body-text version references updated, reference maps updated, new DI architectural area reflected in high-level design and copilot docs reference map.
- **Pre-publish gate:** `pyproject.toml` `version` field must reflect `0.8.0` before running `poetry build` / `poetry publish`.

## Risks / Notes

- **Async complexity**: Providers and hooks may be async. The startup sequence must use an event loop. If the CLI entry point already runs inside an event loop (e.g., `asyncio.run()`), nesting must be avoided. Mitigation: use `asyncio.get_event_loop()` detection and `loop.run_until_complete()` for sync contexts.
- **Thread safety**: Singleton resolution must be thread-safe since `Dispatcher.run()` uses `ThreadPoolExecutor`. Mitigation: resolution lock per provider.
- **Import side effects**: Importing provider modules in the startup phase may trigger unexpected side effects if user code has module-level execution. Mitigation: this is the same risk as the existing `PythonRunner` import path — document it clearly.
- **Generator teardown ordering**: If provider A depends on provider B (via `Depends`), teardown must run in reverse dependency order (A torn down before B). Mitigation: topological reverse in `shutdown()`.
- **Backward compatibility**: Adding `container` to `BrimleyContext` must not break existing tests that create contexts without a container. Mitigation: `container` field defaults to `None` with `Optional` type.
- **`Depends()` at AST level**: The scanner detects `Depends()` as a default value but cannot resolve the actual provider function at scan time (no imports). The argument schema must mark these as "injected" without knowing the provider's return type. Mitigation: record `Depends` presence in argument metadata; type information resolved at startup.

## Open Questions / Concerns

1. **`Depends()` reference format at scan time**: The spec shows `Depends(get_http_client)` taking a function reference. At AST-scan time, we only have the string name `"get_http_client"`. How should the runtime link this string to a registered provider? **Decision**: Option (a) — the provider function name is the provider name unless overridden by `@provider(name="...")`. The AST scanner records the `Depends()` argument as a string, and the container matches it to a registered provider name at startup.

2. **Request-scope threading model**: `Dispatcher.run()` uses `ThreadPoolExecutor`. Request-scoped providers need a per-request context that works across thread boundaries. `contextvars.ContextVar` is automatically copied to thread pool workers via `contextvars.copy_context().run()`. Should the dispatcher use `copy_context().run()` for dispatch calls? If not, the request context must be passed explicitly. **Decision**: Use explicit parameter passing through the dispatch chain rather than relying on `ContextVar` propagation, since the existing correlation ID mechanism already uses `ContextVar` and we need to understand how it interacts.

3. **Database provider auto-registration naming**: The spec says `db_connection` singular. The existing implementation (`infrastructure/database.py`) initializes a flat `Dict[str, Engine]` keyed by connection name (e.g., `"default"`, `"warehouse"`), and `SqlRunner` resolves engines via `context.databases[func.connection]`. **Decision**: One provider per database entry (`db_<name>`, e.g., `db_default`, `db_warehouse`), mirroring the existing multi-connection config. `SqlRunner` resolves via `container.resolve(f"db_{func.connection}")` instead of the direct dict lookup.

4. **`BrimleyContext` re-export**: `BrimleyContext` is currently only importable via `from brimley.core.context import BrimleyContext`. The spec shows it being used in `@on_startup` type hints. **Decision**: Add top-level re-export for ergonomics: `from brimley import BrimleyContext`.

## Validation Plan

Run tests in this order:
1. Focused tests for changed module(s): `poetry run python -m pytest tests/test_di_models.py tests/test_decorators.py tests/test_discovery_di.py tests/test_container.py tests/test_resolver.py tests/test_startup.py tests/test_dispatcher_di.py tests/test_injection.py -v`
2. Adjacent/regression tests: `poetry run python -m pytest tests/test_secrets.py tests/test_execution_sql.py tests/test_execution_python.py tests/test_packaging_contract.py tests/test_discovery.py tests/test_context.py -v`
3. Full suite: `poetry run python -m pytest`

Record results:
- Focused: [pass/fail + summary]
- Regression: [pass/fail + summary]
- Full suite: [pass/fail + summary]

---

## Step Notes Log (update as work progresses)

### B08-S1 Notes
- Changes made: Added `ProviderMetadata` and `LifecycleHookMetadata` to `src/brimley/core/models.py`; added `Depends` class to `src/brimley/core/di.py`; added `@provider`, `@on_startup`, `@on_shutdown` decorators and `Depends` export to `src/brimley/__init__.py`; created `tests/test_di_models.py`; extended `tests/test_decorators.py`.
- Deviations: None.
- Validation: Focused — 55 passed (`tests/test_di_models.py` + `tests/test_decorators.py`). Full suite — 547 passed, 1 pre-existing failure (`test_diagnostics_display.py` CliRunner arg, unrelated).

### B08-S2 Notes
- Changes made: Extended `_find_brimley_decorators()` with `_PROVIDER_DECORATORS`, `_STARTUP_DECORATORS`, `_SHUTDOWN_DECORATORS` sets; added `"provider"`, `"on_startup"`, `"on_shutdown"` kind handling in `parse_python_file()`; updated return type to include `ProviderMetadata` and `LifecycleHookMetadata`; imported both models from `brimley.core.models`.
- Deviations: None.
- Validation: Focused — 32 passed (`tests/test_discovery_di.py`). Adjacent — 103 passed (`test_di_models.py`, `test_decorators.py`, `test_discovery.py`, `test_scanner.py`, `test_scanner_yaml.py`, `test_parsers.py`). Full suite — 579 passed, 1 pre-existing failure (`test_diagnostics_display.py` CliRunner arg, unrelated).

### B08-S3 Notes
- Changes made: Added `ProviderMetadata` and `LifecycleHookMetadata` imports to `scanner.py`; added `providers` and `lifecycle_hooks` fields to `BrimleyScanResult`; updated `Scanner.scan()` to route `ProviderMetadata` and `LifecycleHookMetadata` objects before the generic function/entity pipeline; added `ERR_DUPLICATE_PROVIDER` diagnostic for duplicate provider names; added `ERR_PROVIDER_SHADOWS_FUNCTION` (severity=warning) when a provider and function share the same name (bidirectional check — fires regardless of scan order).
- Deviations: Made the provider-shadows-function warning bidirectional (emitted whether provider or function is encountered second) to avoid relying on non-deterministic `os.walk` file ordering.
- Validation: See B08-S2 Notes (same test run covers both steps).

### B08-S4 Notes
- Changes made: Created `src/brimley/core/container.py` with `BrimleyContainer` (register, resolve, override, reset_overrides, init_eager, shutdown, request_scope context manager) and `_RequestScope` helper; `DuplicateProviderError` and `ProviderResolutionError` exception types. Singleton resolution uses per-provider threading locks. Yield-based teardown supported for both sync and async generators. PEP 563 string annotations handled via `typing.get_type_hints` with fallback. Added `container: Optional[Any]` field to `BrimleyContext`.
- Deviations: Used `Optional[Any]` for `BrimleyContext.container` field type instead of `Optional[BrimleyContainer]` to avoid circular Pydantic forward-reference issue; IDE/mypy support via `TYPE_CHECKING` guard.
- Validation: 38 focused tests in `tests/test_container.py` all passed; full suite 750 passed.

### B08-S5 Notes
- Changes made: Created `src/brimley/core/resolver.py` with `DependencyResolver` (topological_sort, detect_cycles, get_dependencies); `CircularDependencyError` exception type. DFS-based topological sort with in-progress tracking for O(V+E) cycle detection. BrimleyContext-annotated parameters excluded from dependency graph. PEP 563 string annotations handled.
- Deviations: None.
- Validation: 19 focused tests in `tests/test_resolver.py` all passed; full suite 750 passed.

### B08-S6 Notes
- Changes made: [what was implemented]
- Deviations: [none / description]
- Validation: [tests run + result]

### B08-S7 Notes
- Changes made: [what was implemented]
- Deviations: [none / description]
- Validation: [tests run + result]

### B08-S8 Notes
- Changes made: [what was implemented]
- Deviations: [none / description]
- Validation: [tests run + result]

### B08-S9 Notes
- Changes made: [what was implemented]
- Deviations: [none / description]
- Validation: [tests run + result]

### B08-S10 Notes
- Changes made: [what was implemented]
- Deviations: [none / description]
- Validation: [tests run + result]

### B08-S11 Notes
- Changes made: [what was implemented]
- Deviations: [none / description]
- Validation: [tests run + result]

### B08-S12 Notes
- Changes made: [what was implemented]
- Deviations: [none / description]
- Validation: [tests run + result]

### B08-S13 Notes
- Changes made: [what was implemented]
- Deviations: [none / description]
- Validation: [tests run + result]

### B08-S14 Notes
- Changes made: [what was implemented]
- Deviations: [none / description]
- Validation: [tests run + result]

---

## Copilot Execution Protocol

When Copilot uses this plan:
1. Set current step to `In Progress` before coding.
2. Implement only the current step scope.
3. Run listed tests for the step.
4. Update step status to `Completed` (or `Blocked`) with notes.
5. Continue to next step only after validation is recorded.

### Agent Map

Each step is owned by an autonomous agent file in `.github/agents/`. Agents chain via `handoffs:` frontmatter.

| Agent File | Steps | Handoff To |
|---|---|---|
| `b08-models.agent.md` | B08-S1 | `b08-discovery` |
| `b08-discovery.agent.md` | B08-S2, B08-S3 | `b08-container` |
| `b08-container.agent.md` | B08-S4, B08-S5 | `b08-startup` |
| `b08-startup.agent.md` | B08-S6 | `b08-dispatch` |
| `b08-dispatch.agent.md` | B08-S7, B08-S8 | `b08-integration` |
| `b08-integration.agent.md` | B08-S9, B08-S10 | `b08-exports` |
| `b08-exports.agent.md` | B08-S11 | `b08-release` |
| `b08-release.agent.md` | B08-S12, B08-S13, B08-S14 | *(terminal)* |

To start implementation, invoke `@b08-models`. Each agent will hand off to the next upon completing its gates.

### Branching Strategy

- **Integration branch**: `copilot/plan-b08` — all v0.8 work collects here.
- **Step branches**: `feat/b08-s1-di-models`, `feat/b08-s2-ast-detection`, etc. — branched from and merged back into `copilot/plan-b08`.
- **Final merge**: After B08-S14 is complete and approved, `copilot/plan-b08` is merged into `main`.
- **Workflow**: For each step, checkout a step-specific branch from `copilot/plan-b08`, implement, get review approval, merge into `copilot/plan-b08`, then proceed to the next step.
