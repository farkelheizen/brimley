# Brimley Secrets

> **Introduced in:** Brimley 0.7; `provider` sources activated in 0.8
> **Docs baseline: 0.8.x**
> **ADR Reference:** [ADR-0003](decisions/0003-secrets-block-ordered-resolution.md) — ordered-source resolution schema.

The `secrets:` block on `ApiFunction` and `CliFunction` provides structured, ordered-source resolution for sensitive values. Resolved secret values are automatically redacted from all log output.

## 1. Schema

```yaml
secrets:
  github_token:
    - env: GITHUB_TOKEN           # checked first
    - provider: github_creds      # fallback when env is absent (0.8+)
  api_key:
    - env: MY_API_KEY
```


Each named secret maps to an **ordered list of sources**. Sources are tried in declaration order; the first source that returns a non-`None` value wins. An empty string (`""`) returned by an `env` source is treated as a valid resolved value.

### Source Types

| Source | Syntax | Status |
|---|---|---|
| `env` | `- env: ENV_VAR_NAME` | Supported — reads from `os.environ` at call time. |
| `provider` | `- provider: provider_name` | Supported in 0.8+ — resolved via `BrimleyContainer.resolve(provider_name)` at call time. The provider must return a `str`. Raises `BrimleySecretResolutionError` if the container is absent or the provider fails. |

## 2. Resolution Behavior

At **call time** (`resolve_secrets`):
- Iterates sources in declaration order.
- For `env` sources: reads `os.environ.get(env_var_name)`.
- For `provider` sources *(0.8+)*: calls `container.resolve(provider_name)`. The resolved value must be a `str`. Raises `BrimleySecretResolutionError` if the container is absent, the provider is not registered, or the provider returns a non-string value.
- If all sources are exhausted without a value, raises `BrimleySecretResolutionError`.

### Env + Provider Pattern

The following pattern declares `env` as the primary source with `provider` as the fallback:

```yaml
secrets:
  api_token:
    - env: API_TOKEN        # checked first
    - provider: my_vault    # fallback when env is absent (0.8+)
```

The `env` source is tried first; `provider` is only called when the environment variable is not set.

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

**Minimum length:** Secret values with two or fewer characters are excluded from redaction to avoid false-positive replacement of common short strings (e.g., single-digit numbers).

**Known limitation:** Python debug tracebacks (e.g., `--log-level DEBUG` or unhandled exceptions) may still contain secret values in local variable `repr()`. Loguru's structured output is covered; raw stack frames in Python's standard exception renderer are not. This is documented as a known limitation for v0.7.

## 5. `BrimleySecretResolutionError`

`BrimleySecretResolutionError` inherits from `ValueError`. This means:
- Parsers can raise it during scanning, and the Scanner's existing `except ValueError` clause converts it into a `BrimleyDiagnostic` automatically.
- It does not crash the scanner — other functions continue to load.
- At call time it propagates as a runtime error (the function invocation fails).
