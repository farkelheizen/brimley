# ADR-0001: Swap DI and Mocking Release Order

**Date:** 2026-03-16  
**Status:** Accepted  
**Superseded by:** —

---

## Context

The original roadmap placed the Mocking Framework at v0.7 and Dependency Injection (DI) at v0.8. During design review of the v0.7 Mocking spec, it became clear that this ordering created a structural problem: the Mocking spec itself acknowledged that building a mock interception layer before DI was standardized would likely result in duplicated effort and a forced rewrite.

Specifically:

- The v0.8 DI spec explicitly integrates mocking via `BrimleyContainer` dependency overriding: *"The `MockRegistry` is integrated into the DI system."* Building `MockRegistry` before `BrimleyContainer` exists means inventing an ad-hoc interception mechanism (Dispatcher-level patching, module replacement) that becomes redundant when DI lands.
- The `@brimley.mock` decorator is most naturally implemented as a DI provider override. Without the container, it requires its own independent registry — a parallel system that must then be reconciled with DI in v0.8.
- DI provides the foundational scaffolding (`BrimleyContext`, provider resolution, scoped lifecycles) that makes unit tests for virtually everything else meaningful. The project's test-first mandate is harder to satisfy without it.

## Decision

Swap the release order: DI ships as v0.7, Mocking ships as v0.8.

The Mocking spec will be redesigned after DI is stable to:
- Use `BrimleyContainer` provider overriding as the primary interception mechanism instead of a standalone `MockRegistry`
- Map `@brimley.mock` to provider registration in the container
- Remove or replace any Dispatcher-level intercept approach with a DI-native override

## Additional Constraints Surfaced

**Brimley requires a custom AST-aware DI system.** Brimley discovers Python functions via zero-execution AST scanning (`ast.parse()` without importing user modules). Standard DI libraries (`dependency-injector`, `injector`, etc.) require importing and executing modules to wire up the container — incompatible with the scanner model. The v0.8 DI system must follow the same two-phase pattern as function/entity discovery: scan phase (AST, record metadata only) and startup phase (import + construct).

**DI scope is intentionally minimal.** The v0.8 implementation is not a general-purpose injection framework. Supported: `singleton` scope, `request` scope, `Depends()`, `@on_startup`, `@on_shutdown`. Everything else (named bindings, multibindings, interceptors, hierarchical containers, circular dependency resolution) is explicitly out of scope and deferred indefinitely.

**`MockRegistry` design is reset.** The original 0.7 Mocking spec's `MockRegistry` (standalone parallel registry, Dispatcher-level intercept) is dropped. The new 0.9 Mocking spec will be written from scratch: `MockRegistry` is a thin override layer on `BrimleyContainer.override()`, and `@brimley.mock` is syntactic sugar for a test-scoped provider override.

## Consequences

**Positive:**
- Mocking is built on a stable, well-defined seam from day one. No rewrite risk.
- DI scaffolding is available earlier, making the test-first mandate easier to satisfy for all subsequent features.
- The `httpx.AsyncClient` singleton and other shared resources can be properly managed as `@provider` instances from v0.8 onward.
- The custom AST-aware design keeps DI consistent with the rest of Brimley's zero-execution discovery model.

**Trade-offs:**
- A custom DI system requires more upfront design work than adopting an existing library. The narrow scope (§ Additional Constraints) bounds this risk.
- The v0.7 Mocking spec is abandoned entirely; the new 0.9 spec must be written from scratch before that release begins.
- Front-loading DI delays the developer-experience improvements (REPL interactive mocking, offline development) that original v0.7 Mocking was intended to deliver.
