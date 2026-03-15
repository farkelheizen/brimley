# Brimley Roadmap: 0.6 to Beta Maturity
This document outlines the sequential release strategy for Brimley, focusing on one major architectural pillar per version. To ensure stability and battle-testing, v1.0 is deferred until the framework has been validated in production environments by the community.
## v0.6: The Observability Foundation (Logging & Correlation)
- **Significant Change:** [Logging Architecture](brimley-0.6-logging-architecture.md)
- **Why first?** Trace execution across async boundaries is foundational for debugging complex agentic loops.
- **Key Feature:** 8-character `correlation_id` propagation via `ContextVar`.
## v0.7: The Developer Loop (Mocking Framework)
- **Significant Change:** [Mocking Framework & MCP Interactivity](brimley-0.7-mocking-framework-and-mcp-interactivity.md)
- **Why?** Enables "Offline Development" to simulate DBs, APIs, and LLM responses without leaving the REPL.
- **Key Feature:** The `MockRegistry` and `mocks/` directory scanning.
## v0.8: Core Refactor (Dependency Injection)
- **Significant Change:** [Dependency Injection & Managed Objects](brimley-0.8-dependency-injection-and-managed-objects.md)
- **Why?** Cleans up runner resource access (e.g., SQL connections) and enables lifecycle hooks.
- **Feature Extension (State Persistence):** Implementation of a persistence engine (SQLite-backed) for the existing `ctx.state` to ensure agent memory survives restarts.
- **Key Feature:** `@provider`, `Depends()`, and `on_startup` hooks.
## v0.9: Extensibility (Plugins, API & CLI Functions)
- **Significant Change:** [Plugin Architecture (Custom Function Types](brimley-0.9-plugin-architecture-custom-function-types.md) 
- **Why?** Formalizes the "Runner" interface to support [API](brimley-0.9-api-functions.md) and [CLI](brimley-0.9-cli-functions.md) functions as internal plugins.
- **Feature Extension (Secrets & Manifests):**
    - **Secrets:** A `SecretProvider` to safely inject credentials into API/CLI calls.
    - **Manifests:** `brimley manifest` to export function/entity [schemas](copilot-schema-reference-guide.md) for external Copilot platforms.
- **Key Feature:** `.yaml` based HTTP and Shell command wrapping.
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
## The Path to v1.0

Brimley will remain in the 0.x series until the following "Real-World Validation" criteria are met:

1. **Production Adoption:** At least three distinct production-grade applications are running on the Brimley 0.12 core.
    
2. **Community Feedback:** A stable API surface area that has survived at least 3 months without breaking changes.
    
3. **Third-Party Plugins:** Successful implementation of at least two community-contributed Runners.
    
4. **Performance Benchmarks:** Documented proof of "Fast Startup" (under 200ms) for applications with 50+ mixed function types.