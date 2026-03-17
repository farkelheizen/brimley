# ADR-0003: Uniform `secrets:` Block with Ordered-Source Resolution

**Date:** 2026-03-17  
**Status:** Accepted  
**Superseded by:** —  
**Related:** [ADR-0002](0002-accelerate-api-cli-to-v0.7.md)

---

## Context

Shipping API and CLI functions in v0.7 (ADR-0002) creates an immediate need to handle credentials (Bearer tokens, API keys, AWS keys) inside YAML function definitions before the DI-backed `SecretProvider` exists. A naive approach — injecting values directly via `{{ env_var }}` Jinja2 references — would make secrets indistinguishable from regular arguments, preventing automatic log masking and making the schema incompatible with the DI-backed resolver arriving in v0.8.

Additionally, the credential need is not exclusive to API and CLI functions. SQL functions may need runtime-injected values (tenant schema names, row-level security tokens) and template functions may need internal system identifiers that cannot be user-supplied arguments. Defining a `secrets:` block only for `api_function` and `cli_function` would create schema inconsistency across function types.

A second concern: when the DI-backed `SecretProvider` lands in v0.8, any schema that assumes a single resolution mechanism (env var or provider, but not both) would require a breaking change to support the new source. The schema needs to be forward-compatible from day one.

## Decision

Define a uniform `secrets:` block applicable to all four YAML-based function types: `api_function`, `cli_function`, `sql_function`, and `template_function`. Within each named secret, resolution sources are declared as an **ordered list** — the runner tries each source in sequence and uses the first non-empty value. List order equals priority.

```yaml
secrets:
  my_secret:
    - env: ENV_VAR_NAME          # checked first
    - provider: provider_name    # fallback (v0.8+)
```

**Resolution rules:**
- `env`: resolved from `os.environ` at call time.
- `provider`: resolved via `BrimleyContainer` (v0.8+). In v0.7, declaring a `provider` source raises `BrimleySecretResolutionError` at **startup** (scanner load time), not at call time, with a clear message.
- If all sources are exhausted without a value, `BrimleySecretResolutionError` is raised at call time.
- All keys declared under `secrets:` are automatically redacted in all log output before resolved values are used in headers, env blocks, or SQL interpolation.

In v0.7, only `env` sources are implemented. The `provider` source is structurally recognized by the schema parser (so YAML files are syntactically valid) but raises immediately at startup until DI is available in v0.8.

## Consequences

**Positive:**
- Schema is stable across v0.7 and v0.8. A function YAML written for v0.7 (`env` only) gains DI-backed resolution in v0.8 by adding a `provider` entry — no breaking change.
- Uniform schema across all four function types. Developers learn one pattern regardless of function type.
- Automatic log masking is tied to schema declaration rather than ad-hoc redaction logic per runner.
- The ordered-list design supports real-world patterns: prefer a vault provider in production, fall back to env var in local development, without requiring separate YAML files per environment.
- Startup validation of `provider` sources surfaces misconfiguration immediately, not at first call time.

**Trade-offs:**
- In v0.7, a developer who accidentally declares a `provider` source gets a startup error rather than a runtime error. This is intentional (fail fast) but may be surprising. The error message must clearly explain that `provider` sources require v0.8 DI.
- SQL functions accessing `secrets:` via Jinja2 interpolation (e.g., `FROM {{ secrets.tenant_schema }}.orders`) introduces a template rendering step before SQL execution. This is consistent with existing template function behavior but represents a new execution path for SQL runners to validate.
