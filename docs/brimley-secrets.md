# Brimley Secrets

> **Introduced in:** Brimley 0.7
> **ADR Reference:** [ADR-0003](decisions/0003-secrets-block-ordered-resolution.md) — ordered-source resolution schema.

The `secrets:` block on `ApiFunction` and `CliFunction` provides structured, ordered-source resolution for sensitive values. Resolved secret values are automatically redacted from all log output.

## 1. Schema

```yaml
secrets:
  github_token:
    - env: GITHUB_TOKEN           # checked first (v0.7)
    - provider: github_creds      # fallback when DI available (v0.8+)
  api_key:
    - env: MY_API_KEY
```

Each named secret maps to an **ordered list of sources**. Sources are tried in declaration order; the first source that returns a non-`None` value wins. An empty string (`""`) returned by an `env` source is treated as a valid resolved value.

### Source Types

| Source | Syntax | v0.7 Status |
|---|---|---|
| `env` | `- env: ENV_VAR_NAME` | Supported — reads from `os.environ` at call time. |
| `provider` | `- provider: provider_name` | Raises `BrimleySecretResolutionError` at scanner load time if `provider` is the **only** declared source. If `env` is listed first and `provider` is a fallback, a diagnostic **warning** is emitted (not an error) since the `env` path may succeed at runtime. |

## 2. Resolution Behavior

At **scanner load time** (`validate_secrets_no_provider`):
- Raises `BrimleySecretResolutionError` (converted to a `BrimleyDiagnostic`) if `provider` is the only source for any secret.
- Emits a diagnostic warning if `env` is listed first and `provider` is a fallback (forward-compatible pattern for v0.8 DI).

At **call time** (`resolve_secrets`):
- Iterates sources in declaration order.
- For `env` sources: reads `os.environ.get(env_var_name)`.
- `provider` sources are skipped silently (DI not available in v0.7).
- If all sources are exhausted without a value, raises `BrimleySecretResolutionError`.

### Forward-Compatible Pattern

To write secrets config that works in both v0.7 (env only) and v0.8+ (env + provider):

```yaml
secrets:
  api_token:
    - env: API_TOKEN        # used in v0.7 and v0.8+
    - provider: my_vault    # fallback in v0.8+ when env is absent
```

In v0.7: `API_TOKEN` env var is used; `provider` is skipped silently at call time. A diagnostic warning is emitted at scan time to note the deferred source.

## 3. Template Access

Resolved secret values are injected into Jinja2 templates via the `secrets` namespace:

```yaml
# In request headers (API function):
headers:
  Authorization: "Bearer {{ secrets.github_token }}"

# In command_arguments (CLI function):
command_arguments:
  - "--token"
  - "{{ secrets.api_token }}"
```

Secrets are **never** exposed in MCP tool schemas. The `secrets:` block is an internal implementation detail — LLM clients are not told which secrets a function requires or what their values are.

## 4. Log Redaction

Resolved secret values are redacted from all output in two layers:

1. **Loguru sink filter:** Scrubs all resolved secret values from structured log messages before they reach any sink (stderr or file). This covers `INFO`, `DEBUG`, `WARNING`, `ERROR`, and `SUCCESS` log records.

2. **`BrimleyExecutionError` messages:** Error messages constructed by runners pass through the same redaction function before being embedded in exception text. This ensures that secrets are not visible in CLI error output or REPL error messages.

**Known limitation:** Python debug tracebacks (e.g., `--log-level DEBUG` or unhandled exceptions) may still contain secret values in local variable `repr()`. Loguru's structured output is covered; raw stack frames in Python's standard exception renderer are not. This is documented as a known limitation for v0.7.

## 5. `BrimleySecretResolutionError`

`BrimleySecretResolutionError` inherits from `ValueError`. This means:
- Parsers can raise it during scanning, and the Scanner's existing `except ValueError` clause converts it into a `BrimleyDiagnostic` automatically.
- It does not crash the scanner — other functions continue to load.
- At call time it propagates as a runtime error (the function invocation fails).
