# Brimley Roadmap: 0.6 to Beta Maturity
This document outlines the sequential release strategy for Brimley, focusing on one major architectural pillar per version. To ensure stability and battle-testing, v1.0 is deferred until the framework has been validated in production environments by the community.
## v0.6: The Observability Foundation (Logging & Correlation)
- **Significant Change:** [Logging Architecture](brimley-0.6-logging-architecture.md)
- **Why first?** Trace execution across async boundaries is foundational for debugging complex agentic loops.
- **Key Feature:** 8-character `correlation_id` propagation via `ContextVar`.
## v0.7: External Runners (API & CLI Functions)
- **Significant Change:** [API Functions](brimley-0.7-api-functions.md) · [CLI Functions](brimley-0.7-cli-functions.md)
- **Why now?** Immediate production need to wrap OS commands and HTTP APIs as first-class Brimley functions. The core runner loop has no structural dependency on DI or Mocking. See [ADR-0002](../decisions/0002-accelerate-api-cli-to-v0.7.md).
- **Key Features:** `BaseRunner` interface, `ApiRunner` (httpx), `CliRunner` (asyncio subprocess), `secrets:` block with ordered-source resolution (env only; provider deferred to v0.8), Security Acceptance gate required before release.
- **Secrets Design:** See [ADR-0003](../decisions/0003-secrets-block-ordered-resolution.md) for the ordered-resolution schema, applicable to all four YAML-based function types.

## v0.8: Core Infrastructure (Dependency Injection)
- **Significant Change:** [Dependency Injection & Managed Objects](brimley-0.8-dependency-injection-and-managed-objects.md)
- **Why before Mocking?** Mocking is a consumer of DI — `MockRegistry` integrates via `BrimleyContainer.override()`. Building Mocking before DI would produce a redundant standalone registry that gets rewritten. See [ADR-0001](../decisions/0001-swap-di-and-mocking-order.md).
- **Key Features:** Custom AST-aware `BrimleyContainer` (no off-the-shelf DI library — incompatible with zero-execution scanner), `@provider(scope="singleton"|"request")`, `Depends()`, `@on_startup`, `@on_shutdown`. Activates `provider` secret sources defined in v0.7 function YAMLs.

## v0.9: Developer Loop (Mocking Framework)
- **Significant Change:** [Mocking Framework & MCP Interactivity](brimley-0.9-mocking-framework-and-mcp-interactivity.md)
- **Why after DI?** The v0.9 spec is a complete rewrite of the original v0.7 draft: `MockRegistry` is replaced by `BrimleyContainer.override()`; `@brimley.mock` becomes syntactic sugar for a test-scoped provider override. See [ADR-0001](../decisions/0001-swap-di-and-mocking-order.md).
- **Key Features:** `container.override(provider_name, mock_impl)`, `@brimley.mock` decorator, `mocks/` directory scanning, REPL offline development for API/CLI functions.
## v0.10: The Quality Bar (Testing Framework)
- **Significant Change:** [Testing Framework](brimley-0.10-testing-framework.md)
- **Why?** Provides a unified way to verify Python, SQL, API, and CLI functions.
- **Feature Extension (Agent Critique):** `brimley test --agent` mode using an LLM to "critique" tool descriptions and logic.
- **Key Feature:** `brimley test --watch` and `pytest` integration
## v0.11: Live Analytics (DuckDB Introspection)
- **Significant Change:** [DuckDB Introspection & REPL Analytics](brimley-0.11-duckdb-introspection-and-repl-analytics.md)
- **Why?** Treats the app state and execution logs as a queryable database for deep debugging.
- **Feature Extension (Agent Studio):** A local web UI to visualize the "Agent Trace" and tool-call sequences stored in DuckDB.
- **Key Feature:** `/sql` command in REPL.
## v0.12: Performance & Logic (Smart Caching & Chains)
- **Significant Change:** [Smart Caching & Invalidation](brimley-0.12-smart-caching-and-invalidation.md)
- **Why?** Final structural enhancement. Optimizing execution via TTL and conditional watches.
- **Feature Extension (Agentic Flows):** `type: workflow` for declarative, YAML-based multi-step agent "macros" (Chains).
- **Key Feature:** `watch_sql` invalidation and LRU memory management.
## v0.13: External Extensibility (Plugin Architecture)
- **Significant Change:** [Plugin Architecture (Custom Function Types)](brimley-0.13-plugin-architecture-custom-function-types.md)
- **Why deferred?** The `BaseRunner` interface ships as an internal contract in v0.7. Dynamic external plugin loading (arbitrary module loading, startup security surface, 200ms startup budget) is a distinct problem. See [ADR-0004](../decisions/0004-defer-plugin-architecture-to-v0.13.md).
- **Key Features:** `plugins:` block in `brimley.yaml`, dynamic `can_handle`/scanner handshake for third-party runners, community runner ecosystem.

## v0.14: Manifest & Schema Export
- **Why deferred?** `brimley manifest` requires a stable, finalized API surface across all function types and runners. Deferring until v0.13+ ensures the schema is not a moving target. See [ADR-0005](../decisions/0005-defer-manifest-to-v0.14.md).
- **Key Features:** `brimley manifest` command, exports function/entity schemas for external Copilot platforms.

## The Path to v1.0

Brimley will remain in the 0.x series until the following "Real-World Validation" criteria are met:

---

## Deferred Ideas

Feature ideas and enhancements that surfaced during development but were intentionally deferred to avoid blocking a release are tracked in the [Brimley Wish List](brimley-wish-list.md).

1. **Production Adoption:** At least three distinct production-grade applications are running on the Brimley 0.12 core.
    
2. **Community Feedback:** A stable API surface area that has survived at least 3 months without breaking changes.
    
3. **Third-Party Plugins:** Successful implementation of at least two community-contributed Runners.
    
4. **Performance Benchmarks:** Documented proof of "Fast Startup" (under 200ms) for applications with 50+ mixed function types.