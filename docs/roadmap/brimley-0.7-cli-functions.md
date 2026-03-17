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
args: []
timeout_seconds: 10
cwd: "/tmp"                        # explicit cwd — never inherited from parent

env:
  PATH: "/usr/bin:/bin"
  DEBUG_MODE: "{{ debug_enabled }}"

parsing:
  strategy: regex
  pattern: "load average: (?P<load_1min>\\d+\\.\\d+)"
  capture_group: "load_1min"
```

> All keys declared under `secrets:` are automatically redacted from log output. See [ADR-0003](../decisions/0003-secrets-block-ordered-resolution.md) for full resolution rules, source ordering, and examples across all function types.
## 2. MCP Integration

Like other Brimley functions, CLI functions can be surfaced to the Model Context Protocol using the `mcp` configuration block:

- **`mcp.type: tool`**: Exposes the CLI command as a tool. This is highly effective for giving LLMs access to local system utilities or custom automation scripts.
    
- **`mcp.type: resource`**: Good for CLI tools that strictly output state or logs.
    

## 3. Return Shapes & Output Mapping

The `return_shape` attribute defines the structural contract for the function output.

- **Unified Consistency:** CLI functions share the same metadata signature as SQL, Python, and API functions.
    
- **Parsing to Shape:** The `parsing` block (Regex or JSON strategies) transforms raw `stdout` into the Entity data defined in the `return_shape`.
    

## 4. Key Features

- **Input Injection:** Arguments are injected into `command`, `args`, or `env` via Jinja2.
    
- **Output Capture:** Captures `stdout` for results and `stderr` for diagnostics.
    
- **Error Handling:** Non-zero exit codes trigger `BrimleyExecutionError`.
    

## 5. Security Requirements

CLI functions exposed via MCP to LLMs create command injection risks. The following constraints are **non-negotiable** for v0.7 shipping:

- **No `shell=True`:** Arguments MUST be passed to `asyncio.create_subprocess_exec` as a list. `shell=True` is prohibited.
- **Arg list enforcement:** Only explicit `args:` list entries are passed to the subprocess. No string interpolation into the command itself.
- **`allowed_args` / `arg_schema` validation:** Arguments are validated against declared schema before subprocess creation.
- **`timeout_seconds` required:** No default-to-unlimited fallback. Missing `timeout_seconds` fails at scanner load time.
- **`cwd` scoping:** `cwd` field defaults to the project root. It must never be inherited from the parent process.
- **Environment var whitelisting:** Only explicitly declared `env:` keys are passed to the subprocess.

### Security Acceptance Gate (v0.7 Release Prerequisite)

Before v0.7 can be released:
1. A **threat model document** covering injection vectors for LLM-driven CLI calls
2. An **injection test suite** using payloads from [PayloadAllTheThings](https://github.com/swisskyrepo/PayloadAllTheThings)
3. **CI static analysis** with [Bandit](https://github.com/PyCQA/bandit) (B602/B603 rules) and [Semgrep](https://github.com/returntypes/semgrep)
4. **Runtime prompt injection screening:** [llm-guard](https://github.com/protectai/llm-guard) `PromptInjection` scanner in `Dispatcher.run()`
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
    
5. **Processing:** `stdout` is captured and parsed.
    
6. **Return:** Parsed object is validated against `return_shape` and returned.
## 8. Known Gaps (v0.7 Release)

- **`provider` secret source:** Raises `BrimleySecretResolutionError` at startup until DI (v0.8). Schema ([ADR-0003](../decisions/0003-secrets-block-ordered-resolution.md)) is forward-compatible.
- **MockRegistry intercept:** Deferred to v0.9. Stub intercept point left in `Dispatcher.run()`.
- **Plugin architecture:** `BaseRunner` is internal-only. External plugins deferred to v0.13 ([ADR-0004](../decisions/0004-defer-plugin-architecture-to-v0.13.md)).
