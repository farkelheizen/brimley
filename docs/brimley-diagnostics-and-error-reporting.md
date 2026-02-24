# Brimley Diagnostics & Error Reporting
> Version 0.4

This document defines how Brimley should handle and display errors during the "Discovery" and "Registration" phases to ensure developers can fix issues without digging through source code.

## 1. The Diagnostic Object

When a file fails to load, the scanner should generate a `BrimleyDiagnostic` object rather than just throwing a raw exception.

| **Property**  | **Description**                                                          |
| ------------- | ------------------------------------------------------------------------ |
| `file_path`   | Absolute or relative path to the offending file.                         |
| `error_code`  | A unique string code (e.g., `ERR_INVALID_NAME`, `ERR_MISSING_PROPERTY`). |
| `line_number` | If available (YAML/SQL parsing), the specific line causing the issue.    |
| `message`     | A human-readable explanation of what went wrong.                         |
| `suggestion`  | An actionable hint on how to fix it.                                     |

## 2. Common Error Categories & Suggestions

|**Error Code**|**Logic**|**Suggestion Example**|
|---|---|---|
|`ERR_INVALID_NAME`|Name fails regex `^[a-zA-Z][a-zA-Z0-9_-]{1,63}$`.|"Change '123_tool' to 'tool_123'. Names must start with a letter."|
|`ERR_DUPLICATE_NAME`|Two files define the same `name`.|"Function 'get_user' is already defined in 'auth/get_user.sql'. Rename this one."|
|`ERR_MISSING_REQ`|Missing `return_shape` or `type`.|"Add 'return_shape: string' to the YAML metadata block."|
|`ERR_YAML_SYNTAX`|YAML frontmatter is malformed.|"Check for missing quotes or incorrect indentation on line 4."|
|`ERR_PYTHON_IMPORT`|The `handler` path cannot be imported.|"Ensure 'my_module.my_func' exists and is in the PYTHONPATH."|

## 3. Visual Error Reporting (The "Wall of Shame")

Brimley should accumulate all errors during a scan and present them in a unified block.

### Example Console Output:

```
[SYSTEM] ❌ 3 Errors found during discovery in './functions':

1. [ERR_INVALID_NAME] in ./functions/users/1_list.sql
   - Message: '1_list' is an invalid function name.
   - Suggestion: Function names must start with a letter.

2. [ERR_DUPLICATE_NAME] in ./functions/utils/format.py
   - Message: Name 'format_data' is already registered by ./functions/core/formatter.py.
   - Suggestion: Ensure every brimley_function has a unique name.

3. [ERR_YAML_SYNTAX] in ./functions/prompts/welcome.md
   - Message: Mapping values are not allowed here (Line 4, Col 12).
   - Suggestion: Check your YAML frontmatter indentation.

[SYSTEM] Critical failure: Registry could not be initialized. Fix the errors above and restart.
```

## 4. Reload-Time Diagnostics (Watch Mode and `/reload`)

When auto-reload is active (or `/reload` is invoked), diagnostics are emitted for the attempted reload cycle and annotated with domain context.

- Domain labels: `entities`, `functions`, `mcp_tools`.
- Critical/error diagnostics in an upstream domain block dependent downstream swaps.
- Warning-only diagnostics do not block swap for that domain.
- Failed reload keeps unaffected runtime domains available.

### Example Reload Summary

```
[SYSTEM] Reload failed: functions=12 entities=2 tools=3 diagnostics=1 blocked=functions,mcp_tools
```

Use this summary to quickly identify which domains remained active and which were rolled back.

## 5. Persisted Runtime Error Surface (`/errors`)

Brimley persists runtime diagnostics into an active unresolved set plus resolved history entries.

- REPL command: `/errors [--limit N] [--offset N] [--history]`
- Default view: unresolved/current runtime issues only.
- `--history`: includes resolved entries for timeline/debugging context.
- Records are sorted deterministically (severity, then most recently updated) and paginated.

This surface allows developers to inspect current runtime health after startup, reload cycles, and watch-mode events without losing earlier context.

## 6. Validation Report Surface (`brimley validate`)

`brimley validate` emits structured diagnostics for CI/local quality gates:

- Formats: `text` (human readable) and `json` (machine readable).
- Thresholds: `--fail-on error|warning` control non-zero exit semantics.
- Output file: `--output PATH` writes rendered report while still printing to stdout.

Validation output includes per-issue severity/code/message/source location and aggregated summary counts.

## 7. Hot Reload Safety Warnings

When Python discovery detects reload-enabled functions (`reload=True`, default), Brimley also performs a top-level AST call scan to identify likely side effects that would re-run on every save.

Typical hazard identifiers include calls such as:

- `open`
- `connect`
- `start`
- `run`
- `thread`
- `popen`
- `call`

These findings should be emitted as **warnings** (not hard failures) so developers can choose whether to refactor top-level code or disable rehydration for that function/module.

### Example Warning

```
[SYSTEM] ⚠ Hot reload safety warning in ./tools/worker.py
- Message: Top-level execution detected in hot-reloaded module.
- Details: line 7: connect
- Suggestion: Move side effects into a function/class initializer or use @function(reload=False).
```

Hot reload safety warnings should not block normal discovery/registration when no critical errors are present.

## 8. Validating "Intent" vs "Content"

To avoid noise (like Brimley trying to parse a random `.md` file that isn't a function), the scanner should use a **Strict Filter**:

1. **Explicit Intent:** If a file has a `.py`, `.sql`, `.yaml`, or `.md` extension, check for the string `type: ..._function` in the first 500 characters.
    
2. **Silent Ignore:** If the file doesn't look like a Brimley function, ignore it silently.
    
3. **Loud Failure:** If it _does_ look like a function (e.g., contains `type: python_function`) but fails validation, it must trigger a diagnostic error.