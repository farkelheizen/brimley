# Architecture Decision Records

This directory contains the Architecture Decision Records (ADRs) for Brimley.

An ADR captures a significant architectural or design decision, the context that forced it, and the consequences it produces. The goal is that a new contributor — or a future maintainer — can understand not just *what* the architecture is, but *why* it is that way.

## Format

Records follow the [MADR](https://adr.github.io/madr/) (Markdown Architectural Decision Records) convention:

- **Title:** Short imperative phrase describing the decision.
- **Status:** `Accepted`, `Superseded by ADR-XXXX`, or `Deprecated`.
- **Context:** The situation, pressure, or constraint that made a decision necessary.
- **Decision:** What was decided. Written as a definitive statement, not a proposal.
- **Consequences:** What becomes easier, harder, or different as a result. Includes both positive outcomes and accepted trade-offs.

## Index

| ADR | Title | Status |
|-----|-------|--------|
| [0001](0001-swap-di-and-mocking-order.md) | Swap DI and Mocking release order | Accepted |
| [0002](0002-accelerate-api-cli-to-v0.7.md) | Accelerate API & CLI functions to v0.7 | Accepted |
| [0003](0003-secrets-block-ordered-resolution.md) | Uniform `secrets:` block with ordered-source resolution | Accepted |
| [0004](0004-defer-plugin-architecture-to-v0.13.md) | Defer Plugin Architecture (external runners) to v0.13 | Accepted |
| [0005](0005-defer-manifest-to-v0.14.md) | Defer `brimley manifest` to v0.14 | Accepted |

## Process

- ADRs are numbered sequentially and never deleted. Superseded records are updated with a `Superseded by` status and a link to the replacement.
- New ADRs are proposed in `docs_local/` as analysis documents, finalized here once a decision is made.
- Any significant change to the release roadmap, public API surface, or core architectural pattern warrants an ADR.
