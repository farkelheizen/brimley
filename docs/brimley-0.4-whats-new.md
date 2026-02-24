# Brimley 0.4: What’s New
> Version 0.4

This document summarizes the key capabilities delivered in Brimley 0.4.

## 1. Major Improvements

### 1.1 Constrained Type IR + Safer Contracts
- Brimley now normalizes runtime argument/return definitions through a constrained type pipeline.
- Type handling is stricter and more deterministic for validation and MCP schema projection.

### 1.2 Naming + Identity Hardening
- Function/entity naming constraints are enforced more consistently.
- Canonical identity handling is improved for reload and diagnostics workflows.

### 1.3 Hot-Reload Safety (Promote/Quarantine)
- Reload behavior uses partitioned, policy-driven apply semantics.
- Valid changed objects are promoted.
- Invalid changed objects are quarantined with explicit errors.
- Changed broken objects do not silently fall back to stale logic.

### 1.4 Better Diagnostics Surfaces
- Runtime diagnostics are persisted and visible in REPL via `/errors`.
- Validation/reporting is improved for local checks and CI usage.

## 2. CLI and Developer Experience Updates

### 2.1 `validate` Reporting
- `brimley validate --root .` supports deterministic report output.
- Supports format and failure-threshold controls for automation workflows.

### 2.2 Execution Runtime Controls
- Added execution controls in config for:
  - thread pool size
  - timeout budget
  - queue capacity and queue-full strategy

### 2.3 `schema-convert` Migration Utility
- Added JSON Schema conversion utility for migration into Brimley FieldSpec shape.
- Supports strict/default behavior plus lossy mode and issue reporting.

## 3. MCP / FastMCP Behavior in 0.4

### 3.1 Embedded MCP in REPL
- REPL can run with embedded FastMCP (`--mcp`).
- In 0.4, REPL and embedded FastMCP run in the same process.
- Embedded MCP serves over SSE to avoid terminal `stdio` conflicts.

### 3.2 Schema-Shape Change Contract
- Logic-only changes may refresh without schema rebuild.
- MCP schema-shape changes (args/defaults/requiredness/type shape) require restart/reinit behavior so clients receive updated schemas.
- When in-place schema update is not possible, Brimley surfaces actionable client-reconnect/restart diagnostics.

## 4. Discovery and Authoring Notes

- AST-first Python discovery remains core behavior (no import requirement for discovery).
- SQL (`.sql`) and template (`.md`) metadata authoring remain first-class.
- Standalone `.yaml` entity/tool scanning paths are removed from active scanner routing.

## 5. Versioning and Documentation Alignment

- Project and release-facing version markers aligned to 0.4.
- Core technical docs updated to reflect 0.4 contracts.

## 6. Related Docs

- [CLI & REPL Harness](brimley-cli-and-repl-harness.md)
- [MCP Integration](brimley-model-context-protocol-integration.md)
- [Configuration](brimley-configuration.md)
- [Diagnostics & Error Reporting](brimley-diagnostics-and-error-reporting.md)
- [Embedded Deployments & Port Management](brimley-embedded-deployments-and-port-management.md)
