# ADR-0002: Accelerate API & CLI Functions to v0.7

**Date:** 2026-03-17  
**Status:** Accepted  
**Superseded by:** —  
**Related:** [ADR-0001](0001-swap-di-and-mocking-order.md), [ADR-0003](0003-secrets-block-ordered-resolution.md), [ADR-0004](0004-defer-plugin-architecture-to-v0.14.md)

---

## Context

An immediate production need arose to wrap OS commands and external HTTP APIs as first-class Brimley functions, surfaced to the Model Context Protocol. The feature set required — YAML-declared `api_function` and `cli_function` types, Jinja2 argument injection, `return_shape` mapping, and MCP registration — was fully specified in the existing v0.9 roadmap doc, but was scheduled behind DI (v0.7 per ADR-0001) and Mocking (v0.8 per ADR-0001).

Analysis of the v0.9 spec's dependencies showed that the core runner loop (YAML parsing → argument injection → execution → return-shape validation → MCP registration) has no structural dependency on either DI or Mocking in its v0.7 form. The only features that genuinely require those later building blocks are:

- `SecretProvider` credential injection (requires DI's `BrimleyContainer`)
- `MockRegistry` intercept for offline testing (requires the Mocking framework)

Both are additive enhancements, not prerequisites for functional execution.

The primary risk identified was **CLI runner security**: wrapping shell commands as MCP-exposed tools creates injection vectors if argument sanitization is not treated as a hard shipping requirement. A three-part Security Acceptance gate (threat model doc, injection test suite, code review checklist) was defined as a non-skippable prerequisite for the v0.7 release, supported by open source tooling: [PayloadAllTheThings](https://github.com/swisskyrepo/PayloadAllTheThings) for payload enumeration, [Bandit](https://github.com/PyCQA/bandit) and [Semgrep](https://github.com/returntypes/semgrep) for static analysis CI, [llm-guard](https://github.com/protectai/llm-guard) for runtime prompt injection screening at the `Dispatcher` layer, and [detect-secrets](https://github.com/Yelp/detect-secrets) as a pre-commit hook.

## Decision

Accelerate the API & CLI function runners to v0.7. The post-ADR-0001 sequence becomes:

| Release | Feature |
|---------|---------|
| v0.7 | API & CLI Functions (`api_function`, `cli_function`, `BaseRunner` interface) |
| v0.8 | Dependency Injection (`BrimleyContainer`, `@provider`, `Depends()`) |
| v0.9 | Application Server Boundary & Managed Tasks |
| v0.10 | Mocking Framework (`MockRegistry`, REPL offline development) |
| v0.11–v0.13 | Testing, DuckDB, Caching (unchanged) |

**v0.7 scope includes:**
- `BaseRunner` abstract interface (`can_handle`, `run`) as the stable internal contract
- `ApiRunner`: `httpx` async execution, Jinja2 URL/header/body templating, response status mapping, `return_shape` validation
- `CliRunner`: `asyncio.create_subprocess_exec` (list-form args only, `shell=False` enforced), stdout capture, regex/JSON parsing, `return_shape` validation
- MCP auto-registration via `mcp:` block for both runners
- Correlation ID propagation into request headers (API) and subprocess env (CLI)
- `secrets:` block with `env` source resolution (see ADR-0003); `provider` source deferred to v0.8
- `timeout_seconds` as a required field with no default-to-unlimited fallback
- `cwd` field defaulting to the project root, not inherited from the parent process
- Security Acceptance gate fully completed before release

**v0.7 scope explicitly excludes:**
- `provider` secret source resolution (deferred to v0.8 DI)
- `MockRegistry` intercept for ApiRunner/CliRunner (deferred to v0.10 Mocking); a documented stub intercept point is left in `Dispatcher.run()` to avoid a structural change later
- External plugin loading (see ADR-0004)
- `brimley manifest` command (see ADR-0005)

## Consequences

**Positive:**
- The immediate production need is unblocked without waiting for DI or Mocking.
- The `secrets:` schema (see ADR-0003) is defined stably now; no breaking change is needed when DI lands in v0.8.
- DI → Mocking ordering from ADR-0001 is fully preserved. API/CLI runners simply don't depend on either.
- When v0.8 DI lands, runners receive a free upgrade: `httpx.AsyncClient` becomes a `@provider` singleton and `SecretProvider` fills the credential gap — additive, not a rewrite.

**Trade-offs:**
- API/CLI functions cannot be unit-tested offline (no `MockRegistry` intercept) until v0.10 Mocking. This is a known, documented gap for the v0.7 release cycle.
- The Security Acceptance gate adds implementation overhead but is non-negotiable given MCP exposure of shell commands.
