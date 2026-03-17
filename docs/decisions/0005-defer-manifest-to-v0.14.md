# ADR-0005: Defer `brimley manifest` to v0.14

**Date:** 2026-03-17  
**Status:** Accepted  
**Superseded by:** —  
**Related:** [ADR-0002](0002-accelerate-api-cli-to-v0.7.md)

---

## Context

The original v0.9 roadmap listed `brimley manifest` as a Feature Extension alongside the Secrets and Plugin Architecture work. The command exports function and entity schemas in a format consumable by external Copilot platforms and agent orchestration tools.

When the v0.9 scope was restructured (ADR-0002, ADR-0004), `brimley manifest` was evaluated for inclusion in v0.7 or as a standalone addition to a near-term release. The evaluation found:

- `brimley manifest` has no dependency on any v0.7 machinery. It is a read operation over the function registry that could technically be implemented at any point after the scanner exists.
- However, the *value* of the manifest command grows with the breadth of function types registered. A manifest that only captures `sql_function` and `python_function` is less useful than one that also captures `api_function`, `cli_function`, and eventually plugin-provided types.
- Implementing manifest before the function type surface is stable (i.e., before Plugin Architecture lands in v0.13) risks needing schema revisions as new runner types are added.
- The feature is primarily a developer convenience and integration aid, not a runtime requirement. No production use case blocks on it.

## Decision

Defer `brimley manifest` to a new dedicated release: **v0.14**, after Plugin Architecture (v0.13). This ensures the manifest schema captures the complete, stable set of function types including community-contributed runners.

The revised roadmap tail:

| Release | Feature |
|---------|---------|
| v0.12 | Smart Caching & Invalidation |
| v0.13 | Plugin Architecture (External Runners) |
| v0.14 | Manifest & Schema Export |

## Consequences

**Positive:**
- The manifest schema is defined once against a complete, stable function type surface. No iterative revisions as new runners are added in v0.7 through v0.13.
- All releases from v0.7 to v0.13 remain focused on runtime features rather than tooling.
- v0.14 becomes a coherent "integration & export" release that pairs well with the community ecosystem landing in v0.13.

**Trade-offs:**
- External Copilot platform integrations that rely on schema export cannot use an official `brimley manifest` command until v0.14. Teams needing this earlier must generate schema manually or via custom tooling. Given that the MCP integration (`mcp:` block on each function) covers the primary LLM-facing exposure use case, this gap affects only teams needing static schema artifacts for non-MCP platforms.
