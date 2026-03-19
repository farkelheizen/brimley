# 20260318-brimley-0.7 Plan: Brimley 0.7 API & CLI Functions

> Date: 3/18/2026
> Owner: Copilot
> Branch: [optional-branch-name]
> Related docs: `docs/roadmap/brimley-0.7-api-functions.md`, `docs/roadmap/brimley-0.7-cli-functions.md`, `docs/decisions/0002-accelerate-api-cli-to-v0.7.md`, `docs/decisions/0003-secrets-block-ordered-resolution.md`, `docs/decisions/0004-defer-plugin-architecture-to-v0.13.md`, `docs/brimley-discovery-and-loader-specification.md`, `docs/brimley-configuration.md`, `docs/brimley-context.md`, `docs/brimley-model-context-protocol-integration.md`, `README.md`

This file is intended as a working implementation plan.

## Problem Summary

Brimley 0.6 shipped structured logging, correlation IDs, and PyPI publishing. The immediate production need now is to let developers declaratively wrap external HTTP APIs and OS-level CLI commands as first-class Brimley functions, fully surfaced via MCP.

Today, all Brimley functions are one of three types: `python_function`, `sql_function`, or `template_function`. There is no mechanism for YAML-declared HTTP calls or subprocess execution, no secrets resolution layer, and no security hardening infrastructure for LLM-invoked shell commands. ADR-0002 accelerated these capabilities from the original v0.9 slot to v0.7, after analysis confirmed that the core runner loop (YAML parsing → argument injection → execution → return-shape validation → MCP registration) has no structural dependency on DI (v0.8) or Mocking (v0.9).

This plan delivers two new function types (`api_function`, `cli_function`), a `BaseRunner` abstract interface, a uniform `secrets:` block with ordered-source resolution, YAML scanner extensions, security hardening, and complete documentation alignment.

## Goal

Deliver Brimley 0.7 with two new declarative function types (API and CLI), a uniform secrets resolution layer, and a security-hardened runner architecture — all test-validated and documented as a coherent extension of the 0.6 runtime.

## Scope

- In scope:
  - `BaseRunner` abstract interface (internal contract for all runners)
  - `ApiRunner`: `httpx` async execution, Jinja2 URL/header/body templating, result parsing (pluggable `ResultParser`: `text` and `json` built-in), status-code error mapping, `return_shape` validation
  - `CliRunner`: `asyncio.create_subprocess_exec` (list-form args, `shell=False` enforced), stdout/stderr capture, per-exit-code result parsing (pluggable `ResultParser`: `text`, `json`, and `regex` built-in), `return_shape` validation
  - `ApiFunction` and `CliFunction` Pydantic models
  - YAML scanner extension for `.yaml` files with `type: api_function` and `type: cli_function`
  - Uniform `secrets:` block on `BrimleyFunction` base with ordered-source resolution (`env` in v0.7; `provider` recognized but raises at startup)
  - `SecretsResolver` service with automatic log redaction
  - Dispatcher routing extension for new function types
  - MCP auto-registration for API and CLI functions via `mcp:` block
  - Correlation ID propagation into HTTP headers (API) and subprocess env (CLI)
  - CLI/REPL support for invoking new function types
  - Security hardening: arg validation, env whitelisting, cwd scoping, `timeout_seconds` as required field for CLI functions, no `shell=True`
  - Security acceptance gate: threat model document, injection test suite, static analysis (Bandit/Semgrep), runtime prompt injection screening (llm-guard), pre-commit secret scanning (detect-secrets)
  - Documentation updates across all affected specs
  - `httpx` added as a core dependency
  - CHANGELOG, examples, version bump, doc scan gate

- Out of scope:
  - `provider` secret source resolution (deferred to v0.8 DI)
  - `MockRegistry` intercept for ApiRunner/CliRunner (deferred to v0.9 Mocking; stub intercept point left in Dispatcher)
  - External plugin loading / community runners (deferred to v0.13 per ADR-0004)
  - `brimley manifest` command (deferred to v0.14 per ADR-0005)
  - `httpx.AsyncClient` singleton provider (v0.8 DI)
  - OpenTelemetry exporter SDK integration

## Constraints / Requirements

- Treat `docs/roadmap/brimley-0.7-api-functions.md` and `docs/roadmap/brimley-0.7-cli-functions.md` as sources of truth for 0.7 behavior.
- Respect ADR-0002 (acceleration rationale + security acceptance gate), ADR-0003 (secrets schema), and ADR-0004 (plugin deferral).
- CLI runner: **No `shell=True`** — arguments MUST be passed as a list to `asyncio.create_subprocess_exec`.
- CLI runner: `timeout_seconds` is required — missing value fails at scanner load time.
- CLI runner: `cwd` defaults to project root, never inherited from parent process.
- CLI runner: Only explicitly declared `env:` keys are passed; no environment inheritance.
- API runner: `httpx` async execution; must not block the event loop.
- Secrets: All keys declared under `secrets:` are automatically redacted in log output.
- Secrets: `provider` source recognized syntactically but raises `BrimleySecretResolutionError` at startup in v0.7.
- MCP safety: logs must never contaminate stdout JSON-RPC streams (preserved from 0.6).
- Preserve deterministic argument resolution precedence from 0.6.
- Use Poetry commands (`poetry run ...`) for all validation/test execution.
- Prefer `poetry run python -m pytest ...` for test execution.
- Keep documentation and implementation in lockstep before step completion.
- Security acceptance gate must be completed before release.

---

## Implementation Plan

| Step ID | Status | Goal | Planned Changes | Test Coverage |
|---|---|---|---|---|
| B07-S1 | Not Started | Define API and CLI function domain models | Add `ApiFunction`, `CliFunction` to `core/models.py`; add `secrets` field to `BrimleyFunction` base; add request/results/command sub-models; unified `ResultMapping` for both types | `tests/test_models.py` (new model validation cases) |
| B07-S2 | Not Started | Implement SecretsResolver with log redaction | New `SecretsResolver` class; `env` source resolution; `provider` source startup error; Loguru redaction filter integration | new `tests/test_secrets.py` |
| B07-S3 | Not Started | Extend scanner for YAML function discovery | Update `Scanner` to detect `.yaml` files; add `yaml_parser.py` for `api_function`/`cli_function` parsing; validate required fields and `secrets:` block | new `tests/test_yaml_parser.py`, `tests/test_discovery.py` (new cases) |
| B07-S4 | Not Started | Implement BaseRunner abstract interface | New `BaseRunner` ABC in `execution/base_runner.py` with `can_handle()` and `run()` contract; retrofit existing runners to match (non-breaking) | `tests/test_execution.py` (verify existing behavior unchanged) |
| B07-S5 | Not Started | Implement ApiRunner | New `execution/api_runner.py`: httpx async execution, Jinja2 templating for URL/headers/body, per-status-code result parsing (`text`/`json` via pluggable `ResultParser`), status-code error mapping, correlation ID header injection, secrets injection, `return_shape` validation via ResultMapper | new `tests/test_execution_api.py` |
| B07-S6 | Not Started | Implement CliRunner | New `execution/cli_runner.py`: `asyncio.create_subprocess_exec` (no shell), arg validation against declared schema, stdout/stderr capture, per-exit-code result parsing (`text`/`json`/`regex` via pluggable `ResultParser`), env whitelisting, cwd scoping, correlation ID env injection, secrets injection, `return_shape` validation via ResultMapper | new `tests/test_execution_cli.py` |
| B07-S7 | Not Started | Extend Dispatcher for new function types | Add `api_function` and `cli_function` routing in `Dispatcher._dispatch_sync_call()`; add stub mock-intercept point; integrate SecretsResolver in dispatch path | `tests/test_execution.py` (new routing cases), existing regression |
| B07-S8 | Not Started | MCP registration for API and CLI functions | Extend `BrimleyProvider` to generate tool schemas for `api_function`/`cli_function`; ensure `secrets` args are excluded from MCP schema; verify tool wrapper generation | `tests/test_mcp_provider.py` (new cases), `tests/test_mcp_adapter.py` |
| B07-S9 | Not Started | Add httpx dependency and wire integration | Add `httpx` to `pyproject.toml` core dependencies; ensure ApiRunner uses `httpx.AsyncClient` for async HTTP calls; verify timeout propagation | `tests/test_execution_api.py` (integration subset) |
| B07-S10 | Not Started | Security hardening: CLI argument sanitization | Enforce list-form args (no shell interpolation); validate args against `arg_schema`/`allowed_args`; fuzz-style injection test suite using PayloadAllTheThings payloads | new `tests/test_security_cli_injection.py` |
| B07-S11 | Not Started | Security hardening: API request sanitization | Validate URL construction; header injection prevention; body injection tests; prompt injection screening integration point | new `tests/test_security_api_injection.py` |
| B07-S12 | Not Started | Security tooling and CI integration | Bandit configuration (B602/B603 rules); Semgrep ruleset; detect-secrets pre-commit hook; llm-guard PromptInjection scanner integration point in Dispatcher | new `tests/test_security_tooling.py`, CI config |
| B07-S13 | Not Started | Threat model document | Author `docs/security/brimley-0.7-threat-model.md` covering LLM-driven injection vectors for API and CLI calls | docs review |
| B07-S14 | Not Started | End-to-end examples | Add example YAML files for `api_function` and `cli_function`; update `examples/brimley.yaml`; add integration test coverage | `tests/test_e2e_examples.py` (new cases), `examples/` updates |
| B07-S15 | Not Started | Update docs and operator guidance | Update discovery spec, functions spec, MCP spec, configuration docs, context docs, CLI/REPL docs, high-level design, copilot docs reference map | docs conformance review |
| B07-S16 | Not Started | Version bump, CHANGELOG, doc scan gate | Bump `pyproject.toml` to 0.7.0; update CHANGELOG.md; run full doc scan gate per copilot-instructions §8 | full suite run, doc scan verification |
| B07-S17 | Not Started | Validate, harden, and hand off | Full test suite pass; security acceptance gate checklist sign-off; validation evidence recorded | full `poetry run pytest` + validation summary |

Status values: `Not Started` | `In Progress` | `Completed` | `Blocked`

---

## Step Details

### B07-S1 API and CLI Function Domain Models
**Files (expected):**
- `src/brimley/core/models.py`

**Implementation notes:**
- Add `secrets: Optional[Dict[str, List[Dict[str, str]]]] = None` field to `BrimleyFunction` base class. This makes `secrets:` available to all four function types per ADR-0003.
- Define `ApiRequestConfig` model:
  - `method: Literal["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"]`
  - `url: str` (Jinja2 template string)
  - `headers: Optional[Dict[str, str]] = None` (Jinja2 template values)
  - `body: Optional[Union[str, Dict[str, Any]]] = None` (Jinja2 template)
  - `timeout: Optional[float] = None` (request-level timeout override)
- Define `ResultMapping` model (shared by API and CLI functions):
  - `type: Literal["text", "json", "regex"] = "text"` (parser name — a registry key selecting the `ResultParser` implementation; defaults to `text` if omitted. API functions support `text` and `json`; CLI functions additionally support `regex`.)
  - `parse: Optional[Dict[str, Any]] = None` (parser-specific config; for `json`: `{ path: "..." }`; for `regex`: `{ pattern: "...", capture_group: "..." }`; for `text`: unused)
  - `error: Optional[str] = None` (error message for this result code)
  - `empty: Optional[bool] = None` (CLI-only; if `true`, signals a valid-but-empty result — the exit code is not an error, but stdout is not meaningful. Ignored for API functions.)
- Define `ApiFunction(BrimleyFunction)`:
  - `type: Literal["api_function"]`
  - `request: ApiRequestConfig`
  - `results: Optional[Dict[str, ResultMapping]] = None` (status code → mapping; keys are strings: exact codes like `"200"`, `"404"`, or wildcard patterns like `"2xx"`, `"4xx"`; YAML dict order is preserved and defines match priority — see SD-3)
- Define `CliFunction(BrimleyFunction)`:
  - `type: Literal["cli_function"]`
  - `command: str`
  - `command_arguments: List[str] = []` (ordered list of strings passed to `asyncio.create_subprocess_exec` after `command`; each entry is a Jinja2 template that can reference `{{ args.<name> }}` for validated function arguments, `{{ secrets.<name> }}` for resolved secrets, `{{ correlation_id }}`, or literal strings)
  - `timeout_seconds: float` (REQUIRED — no default; enforced by Pydantic)
  - `cwd: Optional[str] = None` (defaults to project root at runtime, not inherited)
  - `env: Optional[Dict[str, str]] = None` (explicit env whitelist, Jinja2 template values)
  - `results: Optional[Dict[str, ResultMapping]] = None` (exit code → mapping; keys are strings: `"0"`, `"1"`, or `"default"` catch-all; YAML dict order is preserved and defines match priority. No wildcard patterns — exit codes 0–255 are enumerated explicitly.)
- Note: `arguments` (inherited from `BrimleyFunction`) defines the user-facing function input schema — what MCP exposes, what `ArgumentResolver` validates. `command_arguments` defines the subprocess arg vector — how validated inputs are assembled into the exec call. These serve different purposes and must not be confused.
- Ensure `timeout_seconds` on `CliFunction` has no default value — Pydantic validation must reject missing values. This matches the spec requirement: "Missing `timeout_seconds` fails at scanner load time."

**Definition of done:**
- All new models pass Pydantic validation with valid inputs and reject invalid inputs (missing required fields, invalid enum values, negative timeouts).
- `BrimleyFunction.secrets` field is available on all function subclasses.

### B07-S2 SecretsResolver with Log Redaction
**Files (expected):**
- `src/brimley/infrastructure/secrets.py` (new)
- `src/brimley/infrastructure/logging.py` (redaction filter addition)

**Implementation notes:**
- `SecretsResolver` class with:
  - `resolve(secrets_block: Dict[str, List[Dict[str, str]]], context: BrimleyContext) -> Dict[str, str]`: iterates each named secret, tries sources in order, returns resolved name→value map.
  - `env` source: reads `os.environ[env_var_name]`; skips if missing/empty.
  - `provider` source: raises `BrimleySecretResolutionError` at call time in v0.7 with clear message: "Secret source 'provider' requires DI (v0.8). Use 'env' source for v0.7."
  - If all sources exhausted for a secret: raises `BrimleySecretResolutionError` with the secret name and tried sources.
- `validate_secrets_at_startup(secrets_block)`: called by scanner during YAML parsing. If any secret declares only `provider` sources (no `env` fallback), raises `BrimleySecretResolutionError` immediately at startup.
- Log redaction (two layers — see OQ-6 resolution):
  - **Loguru sink filter:** add a `patch` or `filter` that scrubs resolved secret values from log record messages before they reach sinks. All keys declared under `secrets:` trigger automatic redaction.
  - **`BrimleyExecutionError` message scrubbing:** when constructing error messages in runners/dispatcher, pass messages through the same redaction function before embedding in exceptions. This prevents secret leakage in error output even if the exception is caught and logged by external code.
  - **Known limitation:** exception stack traces in Python's default debug/traceback output may still contain secret values if they appear in local variable repr. This is documented as a known limitation for v0.7.
- Thread-safe: no mutable shared state beyond what `os.environ` provides.

**Definition of done:**
- `env` resolution works for present and missing env vars.
- `provider` source raises clear startup error.
- All-sources-exhausted raises clear call-time error.
- Resolved secret values do not appear in Loguru log output.
- Resolved secret values do not appear in `BrimleyExecutionError` messages.

### B07-S3 YAML Scanner Extension
**Files (expected):**
- `src/brimley/discovery/yaml_parser.py` (new)
- `src/brimley/discovery/scanner.py` (extend file type detection)
- `src/brimley/infrastructure/secrets.py` (startup validation call)

**Implementation notes:**
- New `yaml_parser.py`:
  - `parse_yaml_function(file_path: Path) -> Union[ApiFunction, CliFunction]`
  - Reads full YAML file (not frontmatter-delimited like SQL/Template — the entire file IS the definition).
  - Discriminates on `type` field: `"api_function"` → parse as `ApiFunction`, `"cli_function"` → parse as `CliFunction`.
  - Validates required fields per model (Pydantic handles most validation).
  - Calls `validate_secrets_at_startup()` if `secrets:` block is present.
  - Returns typed function model or raises diagnostic.
- Update `Scanner._identify_file_type()`:
  - Add `.yaml` extension detection.
  - Check for `type: api_function` or `type: cli_function` as the discriminator (quick regex or YAML peek).
  - Avoid treating other YAML files (like `brimley.yaml` config) as function definitions — require explicit `type` field.
- Update `Scanner._parse_file()`:
  - Route `.yaml` function files to `yaml_parser.parse_yaml_function()`.
- Validation rules:
  - Name regex and uniqueness checks (same as existing functions).
  - For `CliFunction`: `timeout_seconds` must be present (model-enforced); `command` must be non-empty.
  - For `ApiFunction`: `request.url` must be non-empty; `request.method` must be valid HTTP method.
  - `secrets:` block: each source must be either `env` or `provider` (reject unknown source types).

**Definition of done:**
- Scanner discovers `.yaml` files and correctly parses `api_function` and `cli_function` types.
- Invalid YAML function files produce actionable diagnostics without crashing the scan.
- Config-only YAML files (`brimley.yaml`) are not misidentified as function files.

### B07-S4 BaseRunner Abstract Interface
**Files (expected):**
- `src/brimley/execution/base_runner.py` (new)

**Implementation notes:**
- Define `BaseRunner` as an ABC:
  ```python
  class BaseRunner(ABC):
      @abstractmethod
      def can_handle(self, func: BrimleyFunction) -> bool: ...

      @abstractmethod
      async def run(self, func: BrimleyFunction, args: Dict[str, Any], context: BrimleyContext) -> Any: ...
  ```
- This is the stable internal contract per ADR-0002 / ADR-0004. External plugin loading is deferred to v0.13; this interface ships now for first-party runners.
- Existing runners (`PythonRunner`, `SqlRunner`, `JinjaRunner`) are NOT required to subclass `BaseRunner` in v0.7; the interface is introduced alongside new runners and existing runners can be retrofitted in a future housekeeping pass. This avoids unnecessary churn on well-tested code.
- New runners (`ApiRunner`, `CliRunner`) MUST implement `BaseRunner`.

**Definition of done:**
- `BaseRunner` ABC exists with `can_handle` and `run` methods.
- Importing `BaseRunner` does not break existing tests.

### B07-S5 ApiRunner
**Files (expected):**
- `src/brimley/execution/api_runner.py` (new)
- `src/brimley/execution/result_parser.py` (new — pluggable parser interface + built-in parsers, shared by API and CLI runners)
- `src/brimley/infrastructure/secrets.py` (used for resolution)

**Implementation notes:**
- Define `ResultParser` interface (ABC):
  ```python
  class ResultParser(ABC):
      @abstractmethod
      def parse(self, body: bytes, config: Optional[Dict[str, Any]]) -> Any: ...
  ```
  - `body`: raw output bytes (HTTP response body for API, stdout for CLI).
  - `config`: parser-specific configuration from `results.<code>.parse` block. May be `None`.
  - Returns: parsed data suitable for `ResultMapper`.
- Built-in parsers (shipped in v0.7):
  - **`TextResultParser`** (`type: "text"`): decodes bytes to UTF-8 string and returns it. Ignores `config`.
  - **`JsonResultParser`** (`type: "json"`): decodes bytes as JSON. If `config.path` is present, evaluates a **custom dot-path expression** to extract a sub-object. Path syntax: `"key.nested_key"` for object traversal, `"items[0]"` for list index access, `"items[*].name"` for list-member projection. No third-party library — implemented and tested in-house.
  - **`RegexResultParser`** (`type: "regex"`): applies `config.pattern` as a regex to the decoded UTF-8 string. Extracts named group `config.capture_group` if specified, otherwise returns the full match. If no match, returns `None`. Intended for CLI functions but available to any runner.
- Parser registry (internal, not yet pluggable):
  - `_RESULT_PARSERS: Dict[str, ResultParser] = {"text": TextResultParser(), "json": JsonResultParser(), "regex": RegexResultParser()}`
  - Looked up by `results.<code>.type`. If `type` is omitted, defaults to `"text"` (see SD-1).
  - If an unknown parser name is used, raise `BrimleyExecutionError` with a clear message listing available parsers.
  - The registry is designed for future extensibility (v0.13 plugin architecture); new parsers can be registered without changing core code.
- `ApiRunner` implements `BaseRunner`:
  - `can_handle(func)`: returns `func.type == "api_function"`
  - `run(func: ApiFunction, args, context) -> Any`:
    1. Resolve secrets via `SecretsResolver.resolve()`.
    2. Build Jinja2 context: `{"args": resolved_args, "secrets": resolved_secrets, "correlation_id": context.correlation_id}`.
    3. Render URL, headers, and body via Jinja2 `SandboxedEnvironment` (see OQ-9 resolution — defense-in-depth for all template rendering in API and CLI runners).
    4. Execute HTTP request via `httpx.AsyncClient`:
       - Method from `func.request.method`.
       - URL from rendered template.
       - Headers from rendered templates.
       - Body from rendered template (if present).
       - Timeout from `func.request.timeout` or fall back to `func.timeout_seconds` or `context.execution.timeout_seconds`.
    5. Match response status code against `func.results` mappings using **ordered first-match** (see SD-3):
       - Iterate `func.results` keys in declaration order.
       - For each key, check if the actual status code matches:
         - **Exact match:** key is a numeric string (e.g., `"201"`) — matches only that code.
         - **Wildcard match:** key uses `x` placeholders (e.g., `"2xx"`) — matches any code in that range (`200`–`299`). Only the class digit is significant; remaining positions are wildcards.
         - **`"default"`:** matches any code (catch-all, should be last).
       - Use the **first** matching entry. This means exact codes listed before a wildcard take priority by virtue of declaration order.
       - If the matched entry has an `error` key: raise `BrimleyExecutionError` with the mapped error message.
       - If the matched entry has a `parse` block: look up the parser by `type` from the registry, call `parser.parse(body, config)`.
       - If no mapping matches the status code: fall back to `text` parser (raw response body).
    6. Map result via `ResultMapper.map_result()` against `func.return_shape`.
- `httpx.AsyncClient` is created per-call in v0.7. Singleton provider deferred to v0.8 DI.
- Correlation ID is automatically available in Jinja2 context for injection into headers (e.g., `X-Correlation-ID: "{{ correlation_id }}"`).
- Error handling: network errors (`httpx.HTTPError`) map to `BrimleyExecutionError` with diagnostic details.

**Definition of done:**
- Successful HTTP GET/POST with JSON result parsing and `return_shape` validation.
- Error result mapping produces `BrimleyExecutionError` with correct status-code messages.
- Jinja2 template rendering works for URL, headers, and body.
- Secrets are injected into templates and redacted from logs.
- Correlation ID propagates to request headers.

### B07-S6 CliRunner
**Files (expected):**
- `src/brimley/execution/cli_runner.py` (new)
- `src/brimley/infrastructure/secrets.py` (used for resolution)

**Implementation notes:**
- `CliRunner` implements `BaseRunner`:
  - `can_handle(func)`: returns `func.type == "cli_function"`
  - `run(func: CliFunction, args, context) -> Any`:
    1. Resolve secrets via `SecretsResolver.resolve()`.
    2. Build Jinja2 context: `{"args": resolved_args, "secrets": resolved_secrets, "correlation_id": context.correlation_id}`.
    3. Render `command`, `command_arguments` list entries, and `env` values via Jinja2 `SandboxedEnvironment` (see OQ-9 resolution — defense-in-depth for all template rendering).
    4. Determine `cwd`: use `func.cwd` if set, otherwise default to `context.root_dir` (project root). NEVER inherit from parent process.
    5. Build environment dict (see OQ-8 resolution):
       - If `func.env` **is declared** (even if empty dict): build env from rendered `func.env` entries ONLY. No inheritance from parent process. This is the strict-security path.
       - If `func.env` **is omitted** (`None`): inherit the parent process environment (`os.environ` copy). This is the convenience path for simple commands that need standard system env.
    6. Execute via `asyncio.create_subprocess_exec`:
       - First arg: rendered `command`.
       - Remaining args: rendered `command_arguments` list (each element is a separate exec arg).
       - `shell=False` (enforced by using `create_subprocess_exec`, not `create_subprocess_shell`).
       - `cwd`: resolved working directory.
       - `env`: explicit environment dict.
       - `stdout=PIPE`, `stderr=PIPE`.
    7. Wait with `timeout_seconds` enforcement via `asyncio.wait_for()` or `process.communicate(timeout=...)`. Timeout raises `BrimleyExecutionError`.
    8. Match exit code against `func.results` mappings using **ordered first-match** (same semantics as API, minus wildcards):
       - Iterate `func.results` keys in declaration order.
       - For each key, check if the actual exit code matches:
         - **Exact match:** key is a numeric string (e.g., `"0"`, `"1"`) — matches only that code.
         - **`"default"`:** matches any code (catch-all, should be last).
       - Use the **first** matching entry.
       - If the matched entry has an `error` key: raise `BrimleyExecutionError` with the mapped error message (include stderr if available).
       - If the matched entry has `empty: true`: return `None` (valid-but-empty result, no error).
       - Otherwise: look up the parser by `type` from the registry, call `parser.parse(stdout_bytes, config)`.
       - If `func.results` is `None` (omitted): use default behavior — exit 0 parsed as `text`, non-zero raises `BrimleyExecutionError` with stderr.
    9. Map result via `ResultMapper.map_result()` against `func.return_shape`.
- Security invariants (hard requirements):
  - NEVER use `shell=True`. This is enforced by using `create_subprocess_exec`.
  - Arguments are passed as a list, never concatenated into a shell string.
  - Environment is explicitly scoped when `env:` is declared — no inheritance from parent. When `env:` is omitted, parent environment is inherited for convenience.

**Definition of done:**
- Successful subprocess execution with stdout capture and per-exit-code result parsing (text, JSON, regex).
- Non-zero exit code produces `BrimleyExecutionError` with stderr (when mapped as error or when `results:` is omitted).
- Exit codes mapped to `empty: true` return `None` without error.
- Per-exit-code parsing selects correct `ResultParser` and config.
- Timeout enforcement kills process and raises error.
- When `env:` is declared: environment is strictly scoped to declared keys only.
- When `env:` is omitted: parent process environment is inherited.
- `cwd` defaults to project root, not parent process cwd.
- No `shell=True` anywhere in the implementation.

### B07-S7 Dispatcher Extension
**Files (expected):**
- `src/brimley/execution/dispatcher.py`
- `src/brimley/infrastructure/secrets.py` (integrated into dispatch path)

**Implementation notes:**
- Add routing branches in `Dispatcher._dispatch_sync_call()`:
  ```python
  elif func.type == "api_function":
      return await self.api_runner.run(func, args, context)
  elif func.type == "cli_function":
      return await self.cli_runner.run(func, args, context)
  ```
- Initialize `ApiRunner` and `CliRunner` in `Dispatcher.__init__()`.
- Add a documented stub intercept point for future MockRegistry (v0.9):
  ```python
  # v0.9 MockRegistry intercept point — do not remove
  # if self._mock_registry and self._mock_registry.has_intercept(func.name):
  #     return self._mock_registry.intercept(func.name, args, context)
  ```
- Integrate `SecretsResolver` into the dispatch path. The resolver is called early in dispatch if `func.secrets` is non-None; resolved secrets are passed to the runner.
- For `api_function`: dispatch as async (similar to Python async path). ApiRunner.run() is an async method.
- For `cli_function`: dispatch as async (subprocess execution is async).

**Definition of done:**
- API and CLI functions route correctly to their runners.
- Existing `python_function`, `sql_function`, and `template_function` routing is unchanged.
- Mock intercept stub is present and documented.
- Full regression against existing test suite.

### B07-S8 MCP Registration for API and CLI Functions
**Files (expected):**
- `src/brimley/mcp/fastmcp_provider.py`

**Implementation notes:**
- Extend `BrimleyProvider.discover_tools()` to include `api_function` and `cli_function` (currently filters on `mcp.type == "tool"`; just needs to not filter by function type).
- Verify `build_tool_input_model()` generates correct JSON Schema for API/CLI function arguments:
  - Arguments declared in the function's `arguments:` block map to tool input fields.
  - `secrets` keys are NOT exposed in the MCP tool schema (they are internal).
  - `from_context` arguments are excluded (injected at runtime).
- Verify `create_tool_wrapper()` generates correct async wrappers for API/CLI functions.
- Test that `execute_tool_by_name()` correctly dispatches to the new runners.

**Definition of done:**
- API and CLI functions with `mcp.type: tool` appear in the MCP tool registry.
- MCP tool schemas correctly reflect user-facing arguments (no secrets, no from_context).
- Tool invocation via MCP dispatches correctly through to ApiRunner/CliRunner.

### B07-S9 httpx Dependency and Integration Wiring
**Files (expected):**
- `pyproject.toml`
- `src/brimley/execution/api_runner.py` (verify imports)

**Implementation notes:**
- Add `httpx>=0.27` to core dependencies in `pyproject.toml` (not optional — API functions are a core feature).
- Verify that `ApiRunner` uses `httpx.AsyncClient` with proper timeout handling.
- Verify that `httpx` timeout propagation respects the function-level → global execution timeout fallback chain.
- Run `poetry lock` and `poetry install` to validate dependency resolution.

**Definition of done:**
- `httpx` is declared in `pyproject.toml` and available in the poetry environment.
- `ApiRunner` imports and uses `httpx` without import errors.
- Timeout propagation is verified end-to-end.

### B07-S10 Security Hardening: CLI Argument Sanitization
**Files (expected):**
- `src/brimley/execution/cli_runner.py` (hardening additions)
- `tests/test_security_cli_injection.py` (new)

**Implementation notes:**
- Enforce that `CliRunner` NEVER constructs a shell command string. Verify via static analysis and test assertion.
- Add argument validation layer:
  - If `func.arguments` defines allowed args, validate user-provided values against the declared schema before subprocess creation.
  - Reject arguments containing shell metacharacters (`;`, `|`, `&`, `` ` ``, `$()`, `>`, `<`, `\n`, `\r`) when they appear in user-supplied values injected into `command_arguments`. Jinja2 rendering outputs are validated post-render.
- Build injection test suite using representative payloads from PayloadAllTheThings:
  - Command injection: `; ls`, `| cat /etc/passwd`, `` `whoami` ``, `$(id)`, `\nid`
  - Path traversal: `../../etc/passwd`, `%2e%2e%2f`
  - Environment injection: `LD_PRELOAD` overrides, `PATH` hijacking
- Each payload must be proven safe (command not executed, error raised).

**Definition of done:**
- All injection payloads produce `BrimleyExecutionError` or are safely neutralized.
- No subprocess is spawned with shell metacharacters in user-supplied args.
- Static analysis confirms no `shell=True` usage.

### B07-S11 Security Hardening: API Request Sanitization
**Files (expected):**
- `src/brimley/execution/api_runner.py` (hardening additions)
- `tests/test_security_api_injection.py` (new)

**Implementation notes:**
- URL construction validation:
  - After Jinja2 rendering, validate the final URL against a parsed scheme (http/https only).
  - Reject URLs with schemes like `file://`, `ftp://`, `gopher://`, etc. (SSRF mitigation).
  - Reject URLs with embedded credentials (`http://user:pass@host`).
- Header injection prevention:
  - Validate rendered header values don't contain `\r\n` (HTTP header injection / response splitting).
- Body injection tests:
  - Test that Jinja2-rendered body values don't allow template injection (e.g., `{{ config }}` in user input).
  - Jinja2 `SandboxedEnvironment` is already used for all template rendering (see OQ-9 resolution in B07-S5/S6). This step validates that user-controlled inputs cannot escape the sandbox.
- Prompt injection screening integration point:
  - Add a hook in `Dispatcher.run()` or `ApiRunner.run()` for llm-guard `PromptInjection` scanner.
  - `llm-guard` is an **optional dependency** (see OQ-7 resolution): declared as a Poetry extra (`poetry install --extras security`), not a core requirement.
  - In v0.7, implement as a configurable guard (off by default; can be enabled in `brimley.yaml`). If `llm-guard` is not installed and screening is enabled, log a clear warning and skip scanning.

**Definition of done:**
- SSRF payloads (non-http schemes, internal IPs) are rejected or flagged.
- HTTP header injection payloads are rejected.
- Jinja2 template injection via user inputs is blocked by sandboxed environment.
- Prompt injection screening hook exists (even if disabled by default).

### B07-S12 Security Tooling and CI Integration
**Files (expected):**
- `.bandit` or `pyproject.toml` [tool.bandit] (Bandit config)
- `.semgrep.yml` or CI config (Semgrep rules)
- `.pre-commit-config.yaml` (detect-secrets hook)
- `src/brimley/execution/dispatcher.py` (llm-guard integration point)

**Implementation notes:**
- **Bandit:** Configure with focus on B602 (subprocess with shell=True) and B603 (subprocess without shell=True — audit) rules. Ensure zero violations before release.
- **Semgrep:** Add rules for command injection patterns, SSRF patterns, and secrets-in-code patterns. Can use community rulesets.
- **detect-secrets:** Add pre-commit hook to prevent secrets from being committed. Configure baseline and allowlist.
- **llm-guard:** Declared as an **optional Poetry extra** (`security`), not a core dependency (see OQ-7 resolution). Add integration point in `Dispatcher.run()`. In v0.7, this is a documented, configurable hook:
  ```python
  # llm-guard PromptInjection screening (v0.7 hook)
  if context.config.get("security", {}).get("prompt_injection_screening", False):
      self._screen_for_prompt_injection(args)
  ```
  If llm-guard is not installed: log a warning and skip scanning gracefully. The hook is the structural commitment; the dependency is opt-in via `poetry install --extras security`.

**Definition of done:**
- Bandit passes with zero B602/B603 violations on the codebase.
- Semgrep rulesets are configured and passing.
- detect-secrets pre-commit hook is installed.
- llm-guard hook exists in Dispatcher (configurable, documented).

### B07-S13 Threat Model Document
**Files (expected):**
- `docs/security/brimley-0.7-threat-model.md` (new)

**Implementation notes:**
- Document the following threat categories for LLM-driven API and CLI calls:
  1. **Command Injection** (CLI): LLM provides shell metacharacters as tool arguments. Mitigations: list-form exec, arg validation, no shell=True.
  2. **Server-Side Request Forgery (SSRF)** (API): LLM provides internal URLs or non-HTTP schemes. Mitigations: URL scheme validation, optional allowlist.
  3. **HTTP Header Injection** (API): LLM provides CRLF sequences in header values. Mitigations: header value validation.
  4. **Prompt Injection** (both): LLM embeds instructions in tool arguments to manipulate behavior. Mitigations: llm-guard screening hook.
  5. **Secret Exfiltration** (both): LLM crafts requests to extract secrets. Mitigations: secrets never in tool schema, log redaction, env scoping.
  6. **Path Traversal** (CLI): LLM provides `../` sequences in args. Mitigations: arg validation, cwd scoping.
  7. **Timeout/Resource Exhaustion** (both): LLM triggers long-running operations. Mitigations: required timeout_seconds, resource limits.
- For each threat: describe the vector, likelihood, impact, and specific mitigations implemented in v0.7.

**Definition of done:**
- Threat model document is complete, reviewed, and covers all categories listed above.

### B07-S14 End-to-End Examples
**Files (expected):**
- `examples/github_profile.yaml` (new API function example)
- `examples/system_metrics.yaml` (new CLI function example)
- `examples/brimley.yaml` (update if needed)
- `examples/README.md` (update with new examples)

**Implementation notes:**
- `github_profile.yaml`: adapted from the spec example. Uses `env` secret source for `GITHUB_TOKEN`. Returns `GitHubUser` entity or similar.
- `system_metrics.yaml`: adapted from the spec example. Uses `uptime` command with per-exit-code `results:` block and `regex` parser. Returns `SystemLoad` entity or similar.
- Ensure examples are self-contained and runnable with `brimley invoke <function_name> --root examples/`.
- Add corresponding entities if needed.
- Update `examples/README.md` with new examples and v0.7 version header.
- Add integration tests in `test_e2e_examples.py` that validate discovery and (where safe) execution of example functions.

**Definition of done:**
- Example YAML function files are valid and discoverable by the scanner.
- Examples are documented in `examples/README.md`.
- Integration tests cover discovery of new examples.

### B07-S15 Documentation and Operator Guidance
**Files (expected):**
- `docs/brimley-functions.md` (add API and CLI function types)
- `docs/brimley-discovery-and-loader-specification.md` (add YAML function scanning)
- `docs/brimley-model-context-protocol-integration.md` (add API/CLI MCP registration)
- `docs/brimley-configuration.md` (add secrets schema, security config)
- `docs/brimley-context.md` (add secrets-related context fields if any)
- `docs/brimley-high-level-design.md` (add API/CLI as key components, update data flow)
- `docs/brimley-cli-and-repl-harness.md` (update invoke support for new types)
- `docs/brimley-diagnostics-and-error-reporting.md` (add new error types)
- `docs/copilot/copilot-docs-reference.md` (add API/CLI/secrets keyword entries)
- `README.md` (add API/CLI to documentation map and feature list)

**Implementation notes:**
- Create new spec docs:
  - `docs/brimley-api-functions.md` — API function specification (derived from roadmap but written as a canonical spec).
  - `docs/brimley-cli-functions.md` — CLI function specification.
  - `docs/brimley-secrets.md` — Secrets resolution specification.
- Update existing docs to reference new function types where function type lists appear.
- Add secrets resolution precedence table (env → provider, with v0.7 restrictions noted).
- Document security constraints prominently in CLI function spec.

**Definition of done:**
- No contradictions between roadmap specs, canonical docs, and runtime behavior.
- New docs are linked from high-level design and copilot reference map.

### B07-S16 Version Bump, CHANGELOG, Doc Scan Gate
**Files (expected):**
- `pyproject.toml` (version → 0.7.0)
- `CHANGELOG.md` (Added / Changed / Fixed entries)
- All docs (scan per copilot-instructions §8)

**Implementation notes:**
- Bump version in `pyproject.toml` to `0.7.0`.
- CHANGELOG entries:
  - **Added:** API Functions (`api_function` type), CLI Functions (`cli_function` type), BaseRunner interface, SecretsResolver with ordered-source resolution, YAML function scanner, httpx integration, security hardening (injection tests, Bandit/Semgrep, detect-secrets), threat model document.
  - **Changed:** Dispatcher extended with new function type routing, BrimleyFunction gains `secrets` field, MCP provider supports API/CLI tool registration.
- Run full doc scan gate per copilot-instructions §8:
  - Release metadata bump (pyproject.toml, CHANGELOG, examples/README.md).
  - Targeted content scan for stale version references. 
  - Reference documentation maps updated.
  - Copilot docs reference map updated.

**Definition of done:**
- `pyproject.toml` version is `0.7.0`.
- CHANGELOG is complete and accurate.
- Doc scan gate is satisfied — no stale references, all maps updated.

### B07-S17 Validation and Handoff
**Files (expected):**
- Plan notes + validation summary artifacts

**Implementation notes:**
- Execute tests in this order:
  1. Focused tests for new modules.
  2. Adjacent/regression tests for modified modules.
  3. Full suite.
- Security acceptance gate checklist:
  - [ ] Threat model document reviewed.
  - [ ] Injection test suite passes (CLI + API).
  - [ ] Bandit passes (zero B602/B603).
  - [ ] Semgrep passes.
  - [ ] detect-secrets pre-commit installed.
  - [ ] llm-guard hook in Dispatcher (documented, configurable).
  - [ ] Code review checklist signed off.
- Record all test outcomes and known non-blocking warnings.

**Definition of done:**
- All acceptance criteria are met and validation evidence is recorded in this plan.
- Security acceptance gate is fully passed.

---

## Acceptance Criteria

- `ApiFunction` and `CliFunction` models are fully defined, validated, and documented.
- `BaseRunner` abstract interface exists as the internal stable contract.
- `ApiRunner` executes HTTP requests via httpx with Jinja2 templating, per-status-code result parsing (`text` and `json` built-in via pluggable `ResultParser` interface), status-code error mapping, and `return_shape` validation.
- `CliRunner` executes subprocesses via `asyncio.create_subprocess_exec` (NO `shell=True`) with strict arg validation, env whitelisting, cwd scoping, per-exit-code result parsing (`text`, `json`, `regex` built-in via pluggable `ResultParser` interface), and `return_shape` validation.
- `secrets:` block is available on all function types with ordered-source resolution (`env` in v0.7; `provider` raises at startup).
- Resolved secret values are automatically redacted from all log output.
- Scanner discovers `.yaml` function files and correctly parses both new types.
- Dispatcher routes `api_function` and `cli_function` to the correct runners.
- MCP auto-registration works for API and CLI functions via `mcp:` block.
- Correlation ID propagates to HTTP request headers and subprocess environment.
- `timeout_seconds` is required for CLI functions (no default-to-unlimited fallback).
- CLI `cwd` defaults to project root, never inherited.
- CLI environment follows two-mode behavior: if `env:` is declared, only declared keys are passed (strict); if `env:` is omitted, parent environment is inherited (convenience).
- Security acceptance gate is fully completed: threat model, injection tests, Bandit, Semgrep, detect-secrets, llm-guard hook.
- No regressions in existing `python_function`, `sql_function`, or `template_function` paths.
- `CHANGELOG.md` updated with Added / Changed / Fixed entries for 0.7.0.
- `examples/` updated with API and CLI function examples.
- Version bump to 0.7.0 in `pyproject.toml`.
- Doc scan gate satisfied per copilot-instructions §8.
- **Pre-publish gate:** `pyproject.toml` `version` field must reflect 0.7.0 before `poetry build` / `poetry publish`.

## Risks / Notes

### Risks
- **httpx as core dependency:** Adding `httpx` to core deps increases install footprint. Acceptable since API functions are a core feature, not optional.
- **Security surface of CLI functions:** Wrapping shell commands as MCP-exposed tools is inherently high-risk. The multi-layered mitigation (no shell=True, list-form exec, arg validation, env whitelisting, cwd scoping, timeout enforcement) must be airtight. The Security Acceptance gate is non-negotiable.
- **Jinja2 template injection:** If user-supplied values are rendered through Jinja2 without sandboxing, an attacker could extract secrets or manipulate execution. Must use `SandboxedEnvironment` for rendering user-controlled inputs.
- **SSRF via API functions:** LLM-provided URLs could target internal services. URL scheme validation (http/https only) is a minimum; additional allowlisting may be needed for production deployments.
- **Secret leakage in error messages:** Exception messages, stack traces, and diagnostic output could contain rendered secret values. Redaction must cover all output paths, not just structured logs.
- **Subprocess resource exhaustion:** Even with `timeout_seconds`, a subprocess could consume excessive memory or file descriptors. v0.7 mitigates with timeout only; resource limits are a future enhancement.
- **httpx.AsyncClient per-call overhead:** Creating a new client per API call is suboptimal. Acceptable for v0.7; singleton provider via DI in v0.8.

### Mitigations
- Use `jinja2.sandbox.SandboxedEnvironment` for all user-input rendering paths.
- Validate URLs post-render: reject non-http(s) schemes and embedded credentials.
- Apply secret redaction to both structured logs and exception message strings.
- Enforce `timeout_seconds` as required (no default) for CLI functions.
- Document known gaps (provider secrets, MockRegistry, httpx singleton) in release notes.

### Known Gaps (Acceptable for v0.7)
- `provider` secret source: raises `BrimleySecretResolutionError` at startup until DI (v0.8). See ADR-0003.
- MockRegistry intercept: `ApiRunner` and `CliRunner` cannot be intercepted in offline tests until v0.9 Mocking. Stub intercept point left in Dispatcher.
- `httpx.AsyncClient` singleton: per-call creation in v0.7; refactored to `@provider(scope="singleton")` in v0.8 DI.
- Plugin architecture: `BaseRunner` ships as internal-only. External plugin loading deferred to v0.13. See ADR-0004.
- URL allowlisting for SSRF: v0.7 validates scheme only; production-grade allowlisting is a future enhancement.
- Secret values in stack traces: Python debug tracebacks may show secret values in local variable repr. Redaction covers Loguru output and `BrimleyExecutionError` messages but not raw stack frames. See OQ-6 resolution.

## Validation Plan

Run tests in this order:
1. Focused tests for new modules: `poetry run python -m pytest tests/test_models.py tests/test_secrets.py tests/test_yaml_parser.py tests/test_execution_api.py tests/test_execution_cli.py tests/test_security_cli_injection.py tests/test_security_api_injection.py -q`
2. Adjacent/regression tests: `poetry run python -m pytest tests/test_execution.py tests/test_execution_python.py tests/test_execution_sql.py tests/test_execution_jinja.py tests/test_discovery.py tests/test_mcp_provider.py tests/test_mcp_adapter.py tests/test_e2e_examples.py -q`
3. Full suite: `poetry run python -m pytest`
4. Security tooling: `poetry run bandit -r src/brimley -ll` and `semgrep --config .semgrep.yml src/brimley`
5. Docs conformance: `grep -RInE "api_function|cli_function|secrets:|BaseRunner|ApiRunner|CliRunner|httpx" docs README.md`

Record results:
- Focused: [pass/fail + summary]
- Regression: [pass/fail + summary]
- Full suite: [pass/fail + summary]
- Security: [pass/fail + summary]

---

## Step Notes Log (update as work progresses)

### B07-S1 Notes
- Changes made: [what was implemented]
- Deviations: [none / description]
- Validation: [tests run + result]

### B07-S2 Notes
- Changes made: [what was implemented]
- Deviations: [none / description]
- Validation: [tests run + result]

### B07-S3 Notes
- Changes made: [what was implemented]
- Deviations: [none / description]
- Validation: [tests run + result]

### B07-S4 Notes
- Changes made: [what was implemented]
- Deviations: [none / description]
- Validation: [tests run + result]

### B07-S5 Notes
- Changes made: [what was implemented]
- Deviations: [none / description]
- Validation: [tests run + result]

### B07-S6 Notes
- Changes made: [what was implemented]
- Deviations: [none / description]
- Validation: [tests run + result]

### B07-S7 Notes
- Changes made: [what was implemented]
- Deviations: [none / description]
- Validation: [tests run + result]

### B07-S8 Notes
- Changes made: [what was implemented]
- Deviations: [none / description]
- Validation: [tests run + result]

### B07-S9 Notes
- Changes made: [what was implemented]
- Deviations: [none / description]
- Validation: [tests run + result]

### B07-S10 Notes
- Changes made: [what was implemented]
- Deviations: [none / description]
- Validation: [tests run + result]

### B07-S11 Notes
- Changes made: [what was implemented]
- Deviations: [none / description]
- Validation: [tests run + result]

### B07-S12 Notes
- Changes made: [what was implemented]
- Deviations: [none / description]
- Validation: [tests run + result]

### B07-S13 Notes
- Changes made: [what was implemented]
- Deviations: [none / description]
- Validation: [tests run + result]

### B07-S14 Notes
- Changes made: [what was implemented]
- Deviations: [none / description]
- Validation: [tests run + result]

### B07-S15 Notes
- Changes made: [what was implemented]
- Deviations: [none / description]
- Validation: [tests run + result]

### B07-S16 Notes
- Changes made: [what was implemented]
- Deviations: [none / description]
- Validation: [tests run + result]

### B07-S17 Notes
- Changes made: [what was implemented]
- Deviations: [none / description]
- Validation: [tests run + result]

---

## Specification Deviations

This section documents deliberate deviations from the roadmap specs (`brimley-0.7-api-functions.md`, `brimley-0.7-cli-functions.md`). Each deviation must be reviewed and merged back into the canonical specs before B07-S15 (Documentation) is marked complete.

### SD-1: Simplified Result Parsing — Pluggable `ResultParser` Replaces Fixed Content-Type Handling
**Spec reference:** `brimley-0.7-api-functions.md` §4 (Supported Content Types)

**Spec says:** "Brimley 0.7 handles a variety of response formats including `json`, `xml`, `text`, and `binary`. The `auto` type uses the `Content-Type` header for intelligent detection."

**Plan deviates:** v0.7 ships with **three** built-in result parsers: `text`, `json`, and `regex`. The `xml`, `binary`, and `auto` types are deferred. The `results.<code>.type` field becomes a **parser name** (a registry key) rather than a content-type indicator. The `regex` parser is intended primarily for CLI functions but is available to any runner.

**Rationale:**
- Real-world API integrations are overwhelmingly JSON or raw text. `xml` and `binary` are niche use cases that add dependency complexity (`xmltodict`/`lxml`) without covering the launch use cases.
- `auto` (Content-Type sniffing) introduces ambiguity when headers are missing or incorrect. Explicit parser selection is safer and more predictable.
- A pluggable `ResultParser` interface is introduced so that `xml`, `binary`, `jsonpath`, or any other parser can be registered in the future (v0.13 plugin architecture or earlier) without changing core code.
- Default behavior when `type` is omitted is `text` (raw body/stdout) — the safest zero-surprise default.

**Impact on spec:**
- `results.<code>.type` valid values: `"text"` | `"json"` | `"regex"` (was: `"json"` | `"xml"` | `"text"` | `"binary"` | `"auto"`).
- Default changes from implicit `"json"` to `"text"`.
- `parse.path` syntax changes from JSONPath (`$.user_profile`) to custom dot-path (`user_profile` or `data.user.profile`).
- The `ResultParser` ABC and built-in parser registry are new structural additions not in the original spec.
- `results` dict keys are strings (not integers) to support wildcard patterns — see SD-3.

**Spec update required:** Yes — `brimley-0.7-api-functions.md` §4 must be rewritten to reflect the pluggable parser model, reduced type set, and new path syntax.

### SD-2: Custom Dot-Path Expression Parser Replaces JSONPath
**Spec reference:** `brimley-0.7-api-functions.md` §1 (Schema Example, `parse.path: "$.user_profile"`)

**Spec says:** `parse.path` uses JSONPath syntax (e.g., `$.user_profile`).

**Plan deviates:** `parse.path` uses a custom dot-path expression syntax implemented in-house with no third-party dependency.

**Path syntax (v0.7):**
- `"user_profile"` — top-level key extraction
- `"data.user.name"` — nested key traversal
- `"items[0]"` — list index access
- `"items[*].name"` — list-member projection (returns a list of `name` values)

**Rationale:**
- The actual use case is simple key/nested-key extraction, not full JSONPath query power.
- Eliminates a new dependency (`jsonpath-ng`, `jmespath`).
- The path parser is small, fully tested, and easy to reason about.
- A future `jsonpath` parser can be registered as a new `ResultParser` if full JSONPath is needed.

**Spec update required:** Yes — update the schema example `parse.path` from `"$.user_profile"` to `"user_profile"` and document the custom path syntax.

### SD-3: Result Code Matching — Ordered First-Match with Wildcards
**Spec reference:** `brimley-0.7-api-functions.md` §1 (Schema Example, `response:` block), `brimley-0.7-cli-functions.md` §1 (Schema Example, exit code handling)

**Spec says:** The API `response` block uses integer status codes as keys (e.g., `200:`, `401:`, `404:`). No wildcard or range matching is specified. The CLI spec has a flat `parsing:` block with no per-exit-code handling — non-zero exit codes unconditionally raise `BrimleyExecutionError`.

**Plan deviates:** Both API and CLI functions use a unified `results:` block with **ordered first-match** semantics. Keys are strings, not integers.

**Matching rules (API — status codes):**
- Keys are strings: `"200"`, `"404"`, `"2xx"`, `"5xx"`, `"default"`, etc.
- **Exact keys** (all digits): match only that specific status code.
- **Wildcard keys** (`Nxx` pattern): the first digit is literal, `xx` matches any value. `"2xx"` matches `200`–`299`, `"4xx"` matches `400`–`499`, etc.
- **`"default"`:** matches any code (catch-all, should be last).
- **Declaration order is match order.** The `results` dict is iterated in YAML declaration order. The first key that matches the actual status code wins. This means:
  ```yaml
  results:
    201:
      type: json
      parse:
        path: "id"
    202:
      type: text
    2xx:
      type: json
      parse:
        path: "data"
  ```
  A `201` response uses the first entry. A `204` response falls through to `2xx`. A `500` response matches nothing and falls back to the `text` parser default.
- If no key matches: fall back to `text` parser (raw response body), no error raised.

**Matching rules (CLI — exit codes):**
- Keys are strings: `"0"`, `"1"`, `"default"`, etc.
- **Exact keys** (numeric): match only that specific exit code.
- **`"default"`:** matches any code (catch-all, should be last).
- **No wildcard patterns** — exit codes 0–255 are cheap to enumerate explicitly and have no standardized range families.
- **Declaration order is match order**, same as API.
- If `results:` is omitted entirely: default behavior is exit 0 → parse stdout as `text`, non-zero → raise `BrimleyExecutionError` with stderr.

**Unified inner structure (shared by API and CLI):**
- `results.<code>.type` — parser selector (`text`, `json`, `regex`)
- `results.<code>.parse` — parser-specific config
- `results.<code>.error` — error message string
- `results.<code>.empty` — valid-but-empty signal (CLI-only)

**Rationale:**
- Real-world APIs commonly return different success codes (201 Created, 202 Accepted, 204 No Content) with different body shapes, while sharing a common error shape across a class (4xx, 5xx). Exact-only matching forces verbose repetition. Wildcards with exact overrides give developers precise control with minimal YAML.
- Real-world CLI commands use non-zero exit codes for meaningful non-error outcomes (`grep` returns 1 for no match, `diff` returns 1 for files differ). Per-exit-code handling prevents false-positive errors.
- Ordered first-match is intuitive and mirrors how route matching works in web frameworks. No implicit priority rules to memorize — what you write first, matches first.
- YAML dict order preservation is guaranteed by PyYAML (and the YAML 1.1+ spec for ordered mappings), so this is safe to rely on.
- Using the same `results:` keyword and inner structure for both function types gives YAML authors one mental model to learn.

**Validation rules (scanner):**
- **API:** Each key must be either: a 3-digit numeric string (`"200"`–`"599"`), a wildcard pattern matching `^[1-5]xx$`, or the literal `"default"`. A diagnostic warning is emitted if a wildcard key appears before an exact key in the same class (e.g., `"2xx"` before `"201"`) since the exact key would be unreachable.
- **CLI:** Each key must be either: a numeric string `"0"`–`"255"`, or the literal `"default"`.
- Both: Duplicate keys are rejected at scan time.

**Impact on spec:**
- API: `response` block is renamed to `results`. Dict keys change from integer to string. Wildcard patterns and `"default"` catch-all are new capabilities.
- CLI: flat `parsing:` block is replaced by per-exit-code `results:` block. Non-zero exit codes can now be mapped to parsers, errors, or `empty` outcomes instead of unconditionally raising errors.
- Declaration-order matching semantics must be documented for both function types.

**Spec update required:** Yes — `brimley-0.7-api-functions.md` §1 must rename `response` → `results`, use string keys, and document wildcard + ordered first-match behavior. `brimley-0.7-cli-functions.md` §1 must replace `parsing:` with `results:` block and document per-exit-code handling.

### SD-4: `args` Renamed to `command_arguments` on CLI Functions
**Spec reference:** `brimley-0.7-cli-functions.md` §1 (Schema Example, `args: []`), §4 (Key Features, "Arguments are injected into `command`, `args`, or `env`"), §5 (Security Requirements, "Only explicit `args:` list entries are passed")

**Spec says:** The subprocess argument vector is defined by `args: []`.

**Plan deviates:** The field is renamed from `args` to `command_arguments`.

**Rationale:**
- `BrimleyFunction` has an inherited `arguments:` block that defines the user-facing function input schema (what MCP exposes, what `ArgumentResolver` validates, what the user provides at call time). A field named `args` on `CliFunction` creates confusion between these two distinct concerns.
- `command_arguments` makes the separation of concerns explicit:
  - **`arguments:`** — the validated function input schema (inherited, shared by all function types).
  - **`command_arguments:`** — the ordered list of strings passed to `asyncio.create_subprocess_exec` after the command. Each entry is a Jinja2 template that can reference validated function arguments (`{{ args.<name> }}`), resolved secrets (`{{ secrets.<name> }}`), correlation ID (`{{ correlation_id }}`), or literal strings.
- This naming convention is clearer for developers authoring YAML and for Copilot when reasoning about which "args" are being discussed.

**Template semantics for `command_arguments` entries:**
```yaml
command_arguments:
  - "--user"                          # literal string
  - "{{ args.username }}"             # validated function argument
  - "--token"                         # literal
  - "{{ secrets.api_token }}"         # resolved secret
  - "--trace-id={{ correlation_id }}" # correlation ID
```
Each entry is rendered independently via Jinja2 `SandboxedEnvironment`. The rendered list is passed as-is to `create_subprocess_exec` — no shell expansion, no concatenation.

**Impact on spec:**
- All references to `args:` (as the subprocess argument vector) must be renamed to `command_arguments:` throughout `brimley-0.7-cli-functions.md`.
- §4 "Input Injection" must clarify the distinction between `arguments` (function inputs) and `command_arguments` (subprocess exec vector).
- §5 "Arg list enforcement" must reference `command_arguments:`, not `args:`.

**Spec update required:** Yes — `brimley-0.7-cli-functions.md` §1, §4, §5 must rename `args` → `command_arguments` and document the Jinja2 template semantics.

### SD-5: Unified `results:` Block Replaces `response:` (API) and `parsing:` (CLI)
**Spec reference:** `brimley-0.7-api-functions.md` §1 (Schema Example, `response:` block), `brimley-0.7-cli-functions.md` §1 (Schema Example, `parsing:` block), §3 (Return Shapes & Output Mapping), §4 (Key Features, "Error Handling: Non-zero exit codes trigger `BrimleyExecutionError`")

**Spec says:**
- **API:** The outcome-handling block is named `response:`, keyed by HTTP status code, with `type`/`parse`/`error` inner fields.
- **CLI:** A flat `parsing:` block with `strategy`/`pattern`/`capture_group` fields handles stdout parsing. Non-zero exit codes unconditionally raise `BrimleyExecutionError`.

**Plan deviates:** Both API and CLI functions use a unified `results:` block. The keyword `response:` is renamed to `results:` for API functions. The flat `parsing:` block is removed entirely for CLI functions and replaced by the same `results:` structure.

**Rationale:**
- `results` is semantically neutral — it describes what the function *produced*, regardless of transport mechanism (HTTP response, subprocess output, or any future function type). `response` is HTTP-flavored and `parsing` is CLI-flavored; unifying under `results` gives YAML authors one mental model.
- The inner structure is now identical across function types: `results.<code>.type`, `results.<code>.parse`, `results.<code>.error`. CLI adds `results.<code>.empty` for valid-but-empty outcomes.
- No shipped code exists for v0.7 yet, so the rename cost is purely spec-and-plan edits.
- Per-exit-code handling for CLI functions fixes a real gap: commands like `grep` (exit 1 = no match), `diff` (exit 1 = files differ), and `curl` (exit 6 = DNS failure) use non-zero exit codes for meaningful non-error outcomes that the flat `parsing:` model couldn't express.

**API example (before → after):**
```yaml
# Before (spec)
response:
  200:
    type: json
    parse:
      path: "user_profile"
  401:
    error: "Auth failed"

# After (plan)
results:
  200:
    type: json
    parse:
      path: "user_profile"
  401:
    error: "Auth failed"
```

**CLI example (before → after):**
```yaml
# Before (spec) — flat parsing, non-zero always errors
parsing:
  strategy: regex
  pattern: "load average: (?P<load_1min>\\d+\\.\\d+)"
  capture_group: "load_1min"

# After (plan) — per-exit-code results
results:
  0:
    type: regex
    parse:
      pattern: "load average: (?P<load_1min>\\d+\\.\\d+)"
      capture_group: "load_1min"
  default:
    error: "uptime failed"
```

**CLI example — non-trivial exit codes (grep):**
```yaml
results:
  0:
    type: text          # matches found — stdout has match count
  1:
    empty: true         # no matches — valid result, not an error
  default:
    error: "grep failed"
```

**Default behavior when `results:` is omitted:**
- **API:** Fall back to `text` parser for all status codes. No error mapping.
- **CLI:** Exit 0 → parse stdout as `text`. Non-zero → raise `BrimleyExecutionError` with stderr. This preserves backward-compatible behavior for simple commands that don't need per-exit-code handling.

**Impact on spec:**
- **API:** `response:` is renamed to `results:` throughout `brimley-0.7-api-functions.md`. Inner field `type`/`parse`/`error` are unchanged. §1 schema example, §3 extraction hints, §5 error mapping references must all use `results:`.
- **CLI:** `parsing:` block is removed from `brimley-0.7-cli-functions.md` §1 schema example. Replaced by `results:` block. §3 "Parsing to Shape" must reference `results:` per-exit-code mappings. §4 "Error Handling" must document per-exit-code behavior instead of blanket non-zero → error.
- **Models:** `ApiResponseMapping` is renamed to `ResultMapping` (shared). `CliParsingConfig` is removed. Both `ApiFunction` and `CliFunction` use `results: Optional[Dict[str, ResultMapping]]`.
- **Parsers:** `ApiResponseParser` is renamed to `ResultParser`. `TextResponseParser`/`JsonResponseParser` become `TextResultParser`/`JsonResultParser`. `RegexResultParser` is added for CLI (available to all runners). The parser file is `result_parser.py` (was `api_response_parser.py`).

**Spec update required:** Yes — `brimley-0.7-api-functions.md` §1, §3, §5 must rename `response` → `results`. `brimley-0.7-cli-functions.md` §1, §3, §4 must replace `parsing:` with `results:` and document per-exit-code handling including `empty` flag.



---

## Open Questions and Concerns

### ~~OQ-1: JSONPath Library for API Response Extraction~~ — RESOLVED (SD-2)
Resolved: Custom dot-path expression parser, no third-party library. See SD-2.

### ~~OQ-2: XML Response Parsing Strategy~~ — RESOLVED (SD-1)
Resolved: `xml` deferred from v0.7. Can be added as a registered `ResultParser` in a future release.

### ~~OQ-3: Binary Response Handling~~ — RESOLVED (SD-1)
Resolved: `binary` deferred from v0.7. Can be added as a registered `ResultParser` in a future release.

### ~~OQ-4: `auto` Content-Type Detection~~ — RESOLVED (SD-1)
Resolved: `auto` removed. Default parser is `text` (explicit, no sniffing). See SD-1.

### ~~OQ-5: `httpx` Version Floor~~ — RESOLVED
**Decision:** Pin `httpx>=0.27,<1.0` in `pyproject.toml`. This covers all Python 3.10+ environments and tracks the 0.x series until 1.0 stabilizes. The lower bound (`0.27`) is the oldest release supporting the async API surface used by `ApiRunner`. The upper bound (`<1.0`) avoids surprises from a major version bump.

**Spec update required:** No — the specs do not prescribe a specific httpx version. This is a `pyproject.toml` detail documented in B07-S9.

### ~~OQ-6: Secret Redaction Scope~~ — RESOLVED
**Decision:** Redact in **two layers**: (1) Loguru sink filter scrubs resolved secret values from all log messages, and (2) `BrimleyExecutionError` message construction passes messages through the same redaction function before embedding in exceptions. CLI formatter output passes through Loguru, so it's covered by layer 1. Exception stack traces in debug mode may still contain secret values in local variable repr — this is documented as a known limitation for v0.7.

**Spec update required:** Yes — `brimley-0.7-api-functions.md` and `brimley-0.7-cli-functions.md` reference automatic log redaction but do not specify the two-layer scope or the stack-trace limitation. ADR-0003 says "automatically redacted from log output" which is accurate but incomplete — the exception-message layer should be noted. The new canonical `docs/brimley-secrets.md` (created in B07-S15) will be the definitive reference for redaction scope.

### ~~OQ-7: llm-guard as Optional Dependency~~ — RESOLVED
**Decision:** `llm-guard` is an **optional Poetry extra** declared under `[tool.poetry.extras]` as `security = ["llm-guard"]`, installed via `poetry install --extras security`. It is NOT a core dependency. The Dispatcher hook checks for availability at runtime (`importlib.util.find_spec("llm_guard")`), logs a clear warning if not installed and screening is enabled in config, and skips scanning gracefully. The hook is the structural commitment; the dependency is opt-in.

**Spec update required:** Yes — `brimley-0.7-api-functions.md` §7 and `brimley-0.7-cli-functions.md` §5 list "Runtime prompt injection screening: llm-guard PromptInjection scanner in Dispatcher.run()" as a security requirement without indicating it's optional. The spec should note that llm-guard is an optional extra and the hook is the hard requirement, not the dependency itself. `docs/brimley-configuration.md` will need a new `security:` config section documenting `prompt_injection_screening` (B07-S15).

### ~~OQ-8: CliRunner `env` Block — Two-Mode Behavior~~ — RESOLVED
**Decision:** Two-mode environment behavior for CLI functions:
- **`env:` is declared** (even if empty dict `{}`): subprocess receives ONLY the explicitly declared keys. No inheritance from parent process. This is the strict-security path for MCP-exposed commands.
- **`env:` is omitted** (`None` / key absent from YAML): subprocess inherits the parent process environment (`os.environ` copy). This is the convenience path for simple commands that need standard system env (e.g., `PATH`, `HOME`, `LANG`).

This resolves the `PATH` usability problem without compromising the strict-security guarantee when `env:` is explicitly declared.

**Spec update required:** Yes — `brimley-0.7-cli-functions.md` §5 states "Only explicitly declared `env:` keys are passed to the subprocess" without distinguishing the omitted-env case. The spec must document the two-mode behavior: declared = strict whitelist, omitted = inherit. The schema example already shows an explicit `env:` block, which is correct for the strict path. A second example or note should show the omitted case.

### ~~OQ-9: Jinja2 SandboxedEnvironment for All Runner Templates~~ — RESOLVED
**Decision:** Use `jinja2.sandbox.SandboxedEnvironment` for **all** Jinja2 template rendering in `ApiRunner` and `CliRunner`. This includes URL, headers, body (API), and command, args, env (CLI). The sandbox restrictions (no attribute access on unsafe objects, no `__` dunder access, etc.) are minimal for the template patterns used (simple `{{ variable }}` substitution). This is a defense-in-depth measure — even though templates are developer-authored, the values injected at call time come from user/LLM input.

**Spec update required:** No — the specs do not prescribe a specific Jinja2 environment type. This is an implementation-level security decision. However, the new canonical docs (`docs/brimley-api-functions.md`, `docs/brimley-cli-functions.md` created in B07-S15) should document that sandbox mode is used and note any template-authoring restrictions that result (e.g., no calling methods on objects, no `import` expressions).

### ~~OQ-10: CLI Function `arg_schema` / `allowed_args` Validation~~ — RESOLVED (SD-4)
**Decision:** Continue to use the inherited `arguments:` block on `BrimleyFunction` for user-facing input validation. The `ArgumentResolver` already handles type casting, required-field checks, and `from_context` injection — no separate `arg_schema` model is needed. The subprocess argument vector is defined by the new `command_arguments:` field (renamed from `args:` — see SD-4), which is a `List[str]` of Jinja2 templates that can reference validated function arguments (`{{ args.<name> }}`), resolved secrets (`{{ secrets.<name> }}`), and correlation ID.

**Spec update required:** Yes — see SD-4.

### ~~OQ-11: API Function `results` Block — Result Code Granularity~~ — RESOLVED (SD-3, SD-5)
Resolved: Both API and CLI functions use a unified `results:` block. API supports mixed exact and wildcard status code keys (`"200"`, `"2xx"`, `"default"`); CLI supports exact exit code keys (`"0"`, `"1"`, `"default"`). Both use ordered first-match semantics. See SD-3 and SD-5.

### ~~OQ-12: Startup Validation Depth for `provider` Sources~~ — RESOLVED
**Decision:** Raise `BrimleySecretResolutionError` at startup ONLY if `provider` is declared as the secret's **only** source (no preceding `env` source in the resolution order). If `env` is listed first and `provider` is a fallback, emit a **diagnostic WARNING** (not error) since the `env` path may succeed at runtime. This avoids breaking valid YAML that includes forward-compatible `provider` fallbacks while still failing fast when no runtime-resolvable source exists.

**Spec update required:** No — ADR-0003 says "raises `BrimleySecretResolutionError` at startup until DI is available" which is accurate for the provider-only case. The nuance of warning-vs-error for mixed sources is an implementation detail. The new canonical `docs/brimley-secrets.md` (B07-S15) should document both behaviors.

---

## Copilot Execution Protocol

When Copilot uses this plan:
1. Set current step to `In Progress` before coding.
2. Implement only the current step scope.
3. Run listed tests for the step.
4. Update step status to `Completed` (or `Blocked`) with notes.
5. Continue to next step only after validation is recorded.
