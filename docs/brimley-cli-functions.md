# Brimley CLI Functions

> **Introduced in:** Brimley 0.7; `provider` secrets activated in 0.8
> **ADR References:** [ADR-0002](decisions/0002-accelerate-api-cli-to-v0.7.md) — accelerated from v0.9. [ADR-0003](decisions/0003-secrets-block-ordered-resolution.md) — `secrets:` block schema.
> **Docs baseline: 0.8.x**

CLI Functions wrap shell commands as first-class Brimley functions. They enable tool-use for system utilities, legacy scripts, or any command-line tool within the Brimley ecosystem, providing a structured interface over subprocess execution.

## 1. Schema

CLI functions are defined in `.yaml` files where `type` is set to `cli_function`.

```yaml
name: get_system_load
type: cli_function
description: "Returns the current system load average using the uptime command"
return_shape: string

mcp:
  type: tool

command: "uptime"
command_arguments: []
timeout_seconds: 10

results:
  "0":
    type: regex
    parse:
      pattern: "load average[s]?:\\s*(?P<load_1min>[0-9]+\\.[0-9]+)"
      capture_group: "load_1min"
  "default":
    error: "uptime command failed"
```

### Core Fields

| Field | Type | Required | Description |
|---|---|---|---|
| `name` | string | Yes | Unique function name. See [naming conventions](brimley-naming-conventions.md). |
| `type` | string | Yes | Must be `"cli_function"`. |
| `description` | string | No | Human-readable description used in MCP tool schemas. |
| `return_shape` | string \| dict | Yes | See [return shape](brimley-function-return-shape.md). |
| `mcp` | object | No | MCP exposure config. See [MCP integration](brimley-model-context-protocol-integration.md). |
| `arguments` | dict | No | User-facing input schema. See [arguments](brimley-function-arguments.md). |
| `secrets` | dict | No | Secret resolution config. See [secrets](brimley-secrets.md). |
| `command` | string | Yes | Executable to invoke. Must not contain shell metacharacters. |
| `command_arguments` | list[string] | No | Ordered subprocess argument vector. Each entry is a Jinja2 template. Defaults to `[]`. |
| `timeout_seconds` | float | **Yes (required)** | Maximum execution time. No default — missing value fails at scan time. |
| `cwd` | string | No | Working directory. Defaults to project root. Never inherited from parent process. |
| `env` | dict | No | Environment variable whitelist. See two-mode behavior below. |
| `results` | dict | No | Per-exit-code outcome mapping. |

### `command_arguments` — Subprocess Argument Vector

`command_arguments` defines the ordered list of strings passed to `asyncio.create_subprocess_exec` after the `command`. Each entry is a **Jinja2 template** rendered via `SandboxedEnvironment`.

> **Important:** `command_arguments` is distinct from `arguments` (inherited from `BrimleyFunction`). `arguments` defines the user-facing function input schema — what MCP exposes and what `ArgumentResolver` validates. `command_arguments` defines how validated inputs are assembled into the subprocess exec call.

**Template variables available in `command_arguments` entries:**
- `{{ args.<name> }}` — validated function argument
- `{{ secrets.<name> }}` — resolved secret
- `{{ correlation_id }}` — correlation ID
- Literal strings (no template expression)

```yaml
command_arguments:
  - "--user"
  - "{{ args.username }}"
  - "--token"
  - "{{ secrets.api_token }}"
  - "--trace-id={{ correlation_id }}"
```

Each entry is rendered independently. The rendered list is passed as-is to `create_subprocess_exec` — no shell expansion, no string concatenation.

### Environment Variable Handling (Two-Mode)

- **`env:` is declared** (even if empty `{}`): subprocess receives **only** the explicitly declared keys. No inheritance from parent process. This is the strict-security path for MCP-exposed commands.
- **`env:` is omitted** (absent from YAML): subprocess **inherits** the parent process environment (`os.environ` copy). This is the convenience path for simple commands that need standard system env (e.g., `PATH`, `HOME`).

```yaml
# Strict mode — only PATH is forwarded
env:
  PATH: "/usr/bin:/bin"

# Convenience mode — parent env inherited (omit the env: key entirely)
```

## 2. Result Matching

The `results:` block maps exit codes to parsing strategies, error messages, and empty-result signals. Keys are **strings**, matched in **YAML declaration order** (first match wins).

- **Exact keys** (`"0"`, `"1"`, `"2"`): match only that specific exit code.
- **`"default"`**: catch-all key. Place last.
- **No wildcard patterns** — exit codes 0–255 are cheap to enumerate explicitly.
- **`results:` omitted**: exit 0 → parse stdout as `text`; non-zero → raise `BrimleyExecutionError` with stderr.

**Example — `grep` with non-trivial exit codes:**

```yaml
name: search_logs
type: cli_function
command: "grep"
command_arguments: ["-c", "{{ args.pattern }}", "/var/log/app.log"]
timeout_seconds: 30

results:
  "0":
    type: text          # matches found — stdout has match count
  "1":
    empty: true         # no matches — valid result, not an error
  "default":
    error: "grep failed"
```

### Result Entry Fields

| Field | Description |
|---|---|
| `type` | Parser name: `"text"` (default), `"json"`, or `"regex"`. |
| `parse` | Parser-specific config. |
| `error` | Error message string — raises `BrimleyExecutionError`. |
| `empty` | If `true`, signals a valid-but-empty result (returns `None`). |

### Validation Rules (Scanner)

- Keys must be a numeric string `"0"`–`"255"`, or the literal `"default"`.
- Duplicate keys are rejected at scan time.

## 3. Result Parsers

Brimley 0.7 ships three built-in parsers for `stdout`:

| Parser | `type` value | Behavior | `parse` config |
|---|---|---|---|
| Text | `"text"` | Returns raw stdout as UTF-8 string. | None |
| JSON | `"json"` | Parses stdout as JSON. Optionally extracts via `parse.path` (dot-path). | `path` (optional) |
| Regex | `"regex"` | Applies regex to stdout. Extracts named capture group or full match. | `pattern` (required), `capture_group` (optional) |

If `type` is omitted, defaults to `"text"`.

## 4. Security

CLI functions exposed via MCP to LLMs carry inherent command injection risks. The following constraints are enforced in Brimley 0.7.

### No `shell=True`
Arguments are passed to `asyncio.create_subprocess_exec` as a list. `shell=True` is never used. Shell metacharacters in the command cannot trigger shell expansion.

### Shell Metacharacter Rejection
After Jinja2 rendering, each `command_arguments` entry is validated. Entries containing `;`, `|`, `&`, a backtick, `$()`, `>`, `<`, `\n`, `\r`, or bare `$` raise `BrimleyExecutionError`.

### `timeout_seconds` Required
`timeout_seconds` has no default. Missing value fails validation at scan time. This prevents unbounded subprocess execution.

### `cwd` Scoping
`cwd` defaults to the project root. It is never inherited from the parent process.

### Template Sandboxing
All Jinja2 rendering uses `jinja2.sandbox.SandboxedEnvironment`. User-provided values cannot execute arbitrary code or access restricted attributes.

**Template-authoring restrictions** enforced by SandboxedEnvironment:
- No access to `__dunder__` attributes (e.g., `__class__`, `__globals__`).
- No `import` expressions or module access.
- No calling unsafe methods on built-in types (e.g., `str.format_map`).
- Undefined variables raise `UndefinedError` immediately (`StrictUndefined` mode).

### Secrets Redaction
Resolved secret values are automatically redacted from all Loguru log output and from `BrimleyExecutionError` messages. See [secrets](brimley-secrets.md) for full redaction scope.

### Prompt Injection Screening
An optional `llm-guard` hook in `Dispatcher.run()` can screen arguments for prompt injection. Enable in `brimley.yaml`:

```yaml
config:
  security:
    prompt_injection_screening: true
```

Install the optional extra: `poetry install --extras security`. If `llm-guard` is not installed and screening is enabled, a warning is logged and screening is skipped gracefully.

## 5. MCP Registration

CLI functions with an `mcp:` block are automatically registered with the MCP provider:
- `secrets` keys are **not** exposed in the MCP tool schema.
- `from_context` arguments are excluded (injected at runtime).
- Only user-facing `arguments:` fields appear in the tool schema.

See [MCP integration](brimley-model-context-protocol-integration.md) for full details.

## 6. Execution Flow

1. Scanner detects `.yaml` files with `type: cli_function`.
2. `timeout_seconds` is validated (required, must be > 0). `provider:` secret sources are accepted at scan time (0.8+) and resolved via the DI container at call time.
3. If `mcp:` block is present, function is registered with the FastMCP provider.
4. At invocation, `Dispatcher` routes to `CliRunner`.
5. `CliRunner` resolves secrets, renders `command_arguments` templates, validates rendered entries for metacharacters.
6. Process is spawned via `asyncio.create_subprocess_exec` (list-form, `shell=False`) with `timeout_seconds`.
7. stdout is matched against the `results:` block (ordered first-match).
8. Matched parser extracts and returns the result, which is validated against `return_shape`.

## 7. Known Gaps / Open Items

- **MockRegistry intercept:** `CliRunner` cannot be intercepted in offline tests until v0.10 Mocking. Stub intercept point left in `Dispatcher`.
- **Path traversal:** `../` sequences in `command_arguments` are not rejected (shell=False already prevents shell interpretation of path sequences). Document in threat model.
- **Resource limits:** `timeout_seconds` is the only resource constraint. Memory and file descriptor limits are a future enhancement.

> **Resolved in 0.8:** `provider` secret sources now resolve via `BrimleyContainer.resolve()` at call time. `validate_secrets_no_provider()` is no longer called at scan time.
