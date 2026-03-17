# ADR-0004: Defer Plugin Architecture (External Runners) to v0.13

**Date:** 2026-03-17  
**Status:** Accepted  
**Superseded by:** —  
**Related:** [ADR-0002](0002-accelerate-api-cli-to-v0.7.md)

---

## Context

The original v0.9 spec bundled three distinct things under "Plugin Architecture & Custom Function Types":

1. The `BaseRunner` abstract interface (the contract every runner must implement)
2. First-party runners: `ApiRunner` and `CliRunner`
3. External plugin loading: dynamic registration of third-party runners via a `plugins:` block in `brimley.yaml`

When API & CLI functions were accelerated to v0.7 (ADR-0002), items 1 and 2 were pulled forward with them. Item 3 — external plugin loading — was evaluated separately.

External plugin loading allows community-developed runners (e.g., `brimley-lambda-plugin`, gRPC runners, Deno runners) to be registered by adding a module reference to `brimley.yaml`. This is a significant extensibility feature, but it carries two concerns:

- **Security surface:** Loading arbitrary Python modules at startup based on config file entries is an attack vector. A compromised or malicious `brimley.yaml` could cause arbitrary code execution. This requires careful sandboxing design that is not yet specified.
- **Startup time:** The v0.9 API Functions spec explicitly flagged that dynamic plugin loading risks violating the "under 200ms startup" target for applications with 50+ functions. Strict lazy-loading architecture is required, and that architecture is not yet designed.

Neither concern is relevant to the first-party `ApiRunner` and `CliRunner`, which are built-in and loaded deterministically. Deferring external plugin loading removes these unresolved concerns from the v0.7 critical path without any loss of immediate functionality.

## Decision

Defer external plugin loading to a new dedicated release: **v0.13**. The `BaseRunner` abstract interface ships in v0.7 as the stable internal contract for first-party runners. External plugin loading (dynamic module registration, the `plugins:` block in `brimley.yaml`, and the community runner ecosystem) is deferred entirely.

The existing `docs/roadmap/brimley-0.9-plugin-architecture-custom-function-types.md` spec is re-targeted to v0.13.

The revised roadmap tail:

| Release | Feature |
|---------|---------|
| v0.12 | Smart Caching & Invalidation |
| v0.13 | Plugin Architecture (External Runners) |
| v0.14 | Manifest & Schema Export |

## Consequences

**Positive:**
- v0.7 through v0.12 remain tightly scoped. No release is burdened by unresolved security or performance design work.
- The `BaseRunner` interface ships early as a stable internal contract. When v0.13 lands, community runners implement the same interface that first-party runners have been using since v0.7.
- The startup-time and sandboxing concerns can be properly designed during the v0.12 cycle with full knowledge of the complete runner ecosystem.

**Trade-offs:**
- Community extensibility (custom runners, third-party integrations) is not available until v0.13, which is later than the original v0.9 target. Developers who want custom function types before v0.13 must fork or monkey-patch rather than using a supported plugin mechanism.
