# Brimley 0.7: CLI Functions (.yaml)

> **ADR Reference:** [ADR-0002](../decisions/0002-accelerate-api-cli-to-v0.7.md) — accelerated from v0.9 to v0.7. [ADR-0003](../decisions/0003-secrets-block-ordered-resolution.md) — `secrets:` block ordered-resolution schema.

## Overview

CLI Functions wrap shell commands as first-class Brimley functions. This enables "tool-use" for legacy scripts, system utilities, or other CLI tools within the Brimley ecosystem, providing a structured interface over raw shell execution.

## 1. Specification

CLI functions are defined in standard `.yaml` files where the `type` is set to `cli_function`.

### Schema Example: `system_metrics.yaml`

```yaml
name: get_system_load
type: cli_function
description: "Returns the current system load average using the 'uptime' command"

# MCP Configuration Block
mcp:
  type: tool

# Root-level return_shape for consistency with other function types
return_shape: SystemLoad

secrets:
  aws_key:
    - env: AWS_ACCESS_KEY_ID
    - provider: aws_credentials   # fallback when DI available (v0.8+)

command: "uptime"
command_arguments: []              # ordered list of subprocess exec args (Jinja2 templates)
timeout_seconds: 10
cwd: "/tmp"                        # explicit cwd — never inherited from parent

env:                                # explicit env — strict whitelist mode
  PATH: "/usr/bin:/bin"
  DEBUG_MODE: "{{ args.debug_enabled }}"

results:
  "0":
    type: regex
    parse:
      pattern: "load average: (?P<load_1min>\\d+\\.\\d+)"
      capture_group: "load_1min"
  "default":
    error: "uptime failed"
```

### `command_arguments` — Subprocess Argument Vector

The `command_arguments` field defines the ordered list of strings passed to `asyncio.create_subprocess_exec` after the `command`. Each entry is a **Jinja2 template** rendered via `SandboxedEnvironment`.

> **Important:** `command_arguments` is distinct from `arguments` (inherited from `BrimleyFunction`). `arguments` defines the user-facing function input schema — what MCP exposes and what `ArgumentResolver` validates. `command_arguments` defines how validated inputs are assembled into the subprocess exec call.

**Template variables available in `command_arguments` entries:**
- `{{ args.<name> }}` — validated function argument
- `{{ secrets.<name> }}` — resolved secret
- `{{ correlation_id }}` — correlation ID
- Literal strings (no template expression)

```yaml
command_arguments:
  - "--user"                          # literal string
  - "{{ args.username }}"             # validated function argument
  - "--token"                         # literal
  - "{{ secrets.api_token }}"         # resolved secret
  - "--trace-id={{ correlation_id }}" # correlation ID
```

Each entry is rendered independently. The rendered list is passed as-is to `create_subprocess_exec` — no shell expansion, no concatenation.

### Result Code Matching

The `results:` block maps exit codes to parsing strategies, error messages, and empty-result signals. Keys are **strings** and are matched in **YAML declaration order** (first match wins).

- **Exact keys** (numeric, e.g., `"0"`, `"1"`): match only that specific exit code.
- **`"default"`**: catch-all key that matches any exit code. Should appear last.
- **No wildcard patterns** — exit codes 0–255 are cheap to enumerate explicitly and have no standardized range families.
- If `results:` is omitted entirely: default behavior is exit 0 → parse stdout as `text`, non-zero → raise `BrimleyExecutionError` with stderr.

**Per-exit-code result entry fields:**
- `type` — parser selector: `"text"` (default), `"json"`, or `"regex"`
- `parse` — parser-specific config (e.g., `pattern`/`capture_group` for regex, `path` for json)
- `error` — error message string (raises `BrimleyExecutionError`)
- `empty` — if `true`, signals a valid-but-empty result (no error, returns `None`)

**Example — grep with non-trivial exit codes:**

```yaml
name: search_logs
type: cli_function
command: "grep"
command_arguments: ["-c", "{{ args.pattern }}", "/var/log/app.log"]
timeout_seconds: 30

results:
  "0":
    type: text              # matches found — stdout has match count
  "1":
    empty: true             # no matches — valid result, not an error
  "default":
    error: "grep failed"
```

### Validation Rules (Scanner)

- Each key must be: a numeric string `"0"`–`"255"`, or the literal `"default"`.
- Duplicate keys are rejected at scan time.

> All keys declared under `secrets:` are automatically redacted from log output via a two-layer mechanism: (1) Loguru sink filter scrubs resolved secret values from all log messages, and (2) `BrimleyExecutionError` message construction passes messages through the same redaction function. Exception stack traces in debug mode may still contain secret values in local variable repr — this is a known limitation for v0.7. See [ADR-0003](../decisions/0003-secrets-block-ordered-resolution.md) for full resolution rules, source ordering, and examples across all function types.
## 2. MCP Integration

Like other Brimley functions, CLI functions can be surfaced to the Model Context Protocol using the `mcp` configuration block:

- **`mcp.type: tool`**: Exposes the CLI command as a tool. This is highly effective for giving LLMs access to local system utilities or custom automation scripts.
    
- **`mcp.type: resource`**: Good for CLI tools that strictly output state or logs.
    

## 3. Return Shapes & Output Mapping

The `return_shape` attribute defines the structural contract for the function output.

- **Unified Consistency:** CLI functions share the same metadata signature as SQL, Python, and API functions.
    
- **Per-Exit-Code Parsing:** The `results:` block maps each exit code to a `ResultParser` (same pluggable interface as API functions). Each entry specifies `type` (parser name), `parse` (parser config), `error` (error message), or `empty` (valid-but-empty signal). The parsed output is validated against the `return_shape`.
    

### Built-in Parsers (v0.7)

| Parser Name | `type` Value | Behavior | `parse` Config |
|---|---|---|---|
| **Text** | `"text"` | Returns raw stdout as UTF-8 string. | None (ignored) |
| **JSON** | `"json"` | Parses stdout as JSON. Optionally extracts via `parse.path` (dot-path expression). | `path` (optional) |
| **Regex** | `"regex"` | Applies regex to stdout. Extracts named capture group or full match. | `pattern` (required), `capture_group` (optional) |

If `type` is omitted, defaults to `"text"`.
    

## 4. Key Features

- **Input Injection:** Validated function arguments (`{{ args.<name> }}`), resolved secrets (`{{ secrets.<name> }}`), and correlation ID (`{{ correlation_id }}`) are injected into `command`, `command_arguments`, and `env` via Jinja2 `SandboxedEnvironment`.
    
- **Output Capture:** Captures `stdout` for results and `stderr` for diagnostics.
    
- **Per-Exit-Code Handling:** The `results:` block maps each exit code to a parser, error message, or empty-result signal. This replaces the blanket "non-zero = error" behavior and supports commands like `grep` (exit 1 = no match) and `diff` (exit 1 = files differ) where non-zero codes are valid outcomes.
    
- **Default Behavior (when `results:` is omitted):** Exit 0 → parse stdout as `text`. Non-zero → raise `BrimleyExecutionError` with stderr.
    

## 5. Security Requirements

CLI functions exposed via MCP to LLMs create command injection risks. The following constraints are **non-negotiable** for v0.7 shipping:

- **No `shell=True`:** Arguments MUST be passed to `asyncio.create_subprocess_exec` as a list. `shell=True` is prohibited.
- **Command argument enforcement:** Only explicit `command_arguments:` list entries are passed to the subprocess. No string interpolation into the command itself.
- **Argument validation:** User-supplied values injected into `command_arguments` are validated against the inherited `arguments:` schema via `ArgumentResolver` before subprocess creation. Shell metacharacters (`;`, `|`, `&`, `` ` ``, `$()`, `>`, `<`, `\n`, `\r`) in rendered `command_arguments` entries are rejected.
- **`timeout_seconds` required:** No default-to-unlimited fallback. Missing `timeout_seconds` fails at scanner load time.
- **`cwd` scoping:** `cwd` field defaults to the project root. It must never be inherited from the parent process.
- **Environment variable handling (two-mode):**
  - **`env:` is declared** (even if empty `{}`): subprocess receives ONLY the explicitly declared keys. No inheritance from parent process. This is the strict-security path for MCP-exposed commands.
  - **`env:` is omitted** (`None` / key absent from YAML): subprocess inherits the parent process environment (`os.environ` copy). This is the convenience path for simple commands that need standard system env (e.g., `PATH`, `HOME`, `LANG`).

### Security Acceptance Gate (v0.7 Release Prerequisite)

Before v0.7 can be released:
1. A **threat model document** covering injection vectors for LLM-driven CLI calls
2. An **injection test suite** using payloads from [PayloadAllTheThings](https://github.com/swisskyrepo/PayloadAllTheThings)
3. **CI static analysis** with [Bandit](https://github.com/PyCQA/bandit) (B602/B603 rules) and [Semgrep](https://github.com/returntypes/semgrep)
4. **Runtime prompt injection screening:** [llm-guard](https://github.com/protectai/llm-guard) `PromptInjection` scanner hook in `Dispatcher.run()`. `llm-guard` is an **optional Poetry extra** (`security = ["llm-guard"]`), installed via `poetry install --extras security`. The Dispatcher hook checks for runtime availability and skips gracefully if not installed. The hook is the hard requirement; the dependency is opt-in.
5. **Pre-commit secret scanning:** [detect-secrets](https://github.com/Yelp/detect-secrets)
6. A **code review checklist** signed off before merge

These are prerequisites, not nice-to-haves. See [ADR-0002](../decisions/0002-accelerate-api-cli-to-v0.7.md) for rationale.

## 6. Testing & Mocking (v0.9)

- **Dry Run:** Available in v0.7 — logs the command without execution.
- **Offline Mocking:** Deferred to v0.9 (Mocking framework). `CliRunner` cannot be intercepted in tests until `BrimleyContainer.override()` is available. A documented stub intercept point is left in `Dispatcher.run()` to avoid a structural change when v0.9 lands.

## 7. Execution Flow

1. **Discovery:** Scanner detects `.yaml` files with `type: cli_function`.
    
2. **MCP Registration:** Function is registered with the MCP adapter if the `mcp` block is specified.
    
3. **Dispatch:** Routed to `CliRunner`.
    
4. **Execution:** Process spawned via `asyncio.create_subprocess_exec`.
    
5. **Processing:** `stdout` is captured and parsed via the matched `ResultParser` from the `results:` block.
    
6. **Return:** Parsed object is validated against `return_shape` and returned.
## 8. Known Gaps (v0.7 Release)

- **`provider` secret source:** Raises `BrimleySecretResolutionError` at startup if `provider` is the **only** declared source (no `env` fallback). If `env` is listed first and `provider` is a fallback, a diagnostic **warning** is emitted (not error). Schema ([ADR-0003](../decisions/0003-secrets-block-ordered-resolution.md)) is forward-compatible.
- **MockRegistry intercept:** Deferred to v0.9. Stub intercept point left in `Dispatcher.run()`.
- **Plugin architecture:** `BaseRunner` is internal-only. External plugins deferred to v0.13 ([ADR-0004](../decisions/0004-defer-plugin-architecture-to-v0.13.md)).
