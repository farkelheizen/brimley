# Brimley 0.5: What’s Next
> Planning Document

This document captures the intended next architecture milestones after 0.4.

## 1. Direction for 0.5

Brimley 0.5 is focused on **architecture convergence**:
- align design intent and runtime behavior,
- remove remaining contract ambiguities,
- preserve 0.4 reliability gains while evolving process and MCP integration boundaries.

## 2. Confirmed Architectural Decisions

### ADR-001: Daemonized REPL Topology
- Move from single-process REPL runtime to a client/server REPL model.
- Thin REPL client connects to a Brimley daemon that owns runtime state.
- Define explicit attach/reconnect/shutdown lifecycle semantics.

### ADR-002: Provider-Native MCP Integration
- Make provider-based FastMCP integration the canonical embedding model.
- Converge MCP registration/execution around that contract.

## 3. Planned 0.5 Workstreams

### 3.1 Process Topology + Control Plane
- Introduce daemon metadata and liveness handling.
- Support stable client attach/re-attach behavior.
- Keep transport ownership boundaries explicit and testable.

### 3.2 MCP Contract Convergence
- Unify schema-mutation refresh/reinit behavior under one canonical model.
- Preserve strict restart/reconnect semantics for schema-shape changes.

### 3.3 Legacy Policy Finalization
- Finalize Python YAML frontmatter policy (remove or explicitly deprecate with timeline).
- Ensure parser behavior, tests, and docs are consistent.

### 3.4 Packaging/Install Clarity
- Finalize and document FastMCP packaging contract.
- Ensure install instructions and runtime expectations are unambiguous.

## 4. What 0.5 Is Not

- Not a broad feature-scope expansion release.
- Not a rewrite of the execution engine.
- Not a change to core Brimley value proposition (AST-first discovery, polyglot tooling, safe reload behavior).

## 5. Success Criteria for 0.5

0.5 is successful when:
- process topology is implemented and documented consistently,
- MCP integration contract is singular and clear,
- schema mutation behavior remains deterministic and actionable,
- legacy compatibility behavior is explicit and enforced,
- docs and runtime behavior match without contradictions.

## 6. Related Planning Docs

- [Brimley 0.4: What’s New](brimley-0.4-whats-new.md)
- [High-Level Design](brimley-high-level-design.md)
- [CLI & REPL Harness](brimley-cli-and-repl-harness.md)
- [MCP Integration](brimley-model-context-protocol-integration.md)
