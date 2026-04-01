# Roadmap: YAML Pipeline Functions and Tiered Function Architecture

> Status: Wish list. Captures a design direction explored through discussion; not yet scheduled for implementation.
> Last updated: 2026-03-31

## Motivation

Brimley currently supports three function types that are hot-reloadable (SQL, Jinja templates, Python) plus one that is partially so. The Python function type is the most powerful but introduces friction:

1. **AST/import split.** Discovery uses static AST parsing (no code execution), but execution uses `importlib.import_module()`. These are fundamentally different mechanisms operating on the same files.

2. **Partial hot-reload.** The reload engine calls `importlib.reload()` on modules that contain `@function`-decorated handlers, but **not** on their transitive dependencies. A utility module without `@function` decorators stays cached in `sys.modules` even after the importing module is reloaded. Changes to helper functions require a process restart.

3. **Mismatch between purpose and power.** Many Python functions in practice are orchestration glue: call a SQL function, check the result, call another SQL function, build a return value. They use Python's full import system and runtime for what amounts to sequential function-call wiring.

## Proposal: Three-Tier Function Architecture

Introduce a YAML-based pipeline function type and formalize the role of each tier:

| Tier | Defined in | Hot-reloadable | Purpose |
|---|---|---|---|
| **SQL / Template** | `.sql` / `.md.j2` files | Yes (stateless text) | Single atomic operations |
| **YAML Pipeline** | `.yaml` files | Yes (stateless data) | Orchestration of other Brimley function calls |
| **Python Extension** | `.py` modules | No — loaded once at startup | Arbitrary logic, third-party libraries, complex transforms |

### Tier 1: SQL and Template Functions (unchanged)

These already work well. Static files, trivially reloadable, no import system involved.

### Tier 2: YAML Pipeline Functions (new)

A pipeline is a sequence of named steps that call other Brimley functions, with lightweight control flow:

```yaml
name: approve_order
type: pipeline
mcpType: tool
arguments:
  order_id: int
  approver:
    type: string
    default: ""

steps:
  - call: get_order
    args:
      order_id: "$order_id"
    assign: order

  - when: "$order == null"
    return: { approved: false, reason: "order not found" }

  - call: mark_order_approved
    args:
      order_id: "$order.id"
      approved_by: "$approver or $order.assigned_to"

  - call: create_audit_event
    args:
      entity_id: "$order.id"
      event_type: "approved"
      actor: "$approver"

  - return:
      approved: true
      id: "$order.id"
      status: "$order.status"
```

**Design constraints for the pipeline language:**

- **Keep it minimal.** Support `call`, `assign`, `when`, `return`, and `for_each`. Resist adding general-purpose programming constructs.
- **No arbitrary expressions.** Variable references (`$var`, `$row.field`) and simple null/equality checks. Anything more complex belongs in a Python extension.
- **Funnel complexity to Tier 3.** When the pipeline syntax cannot express something, the answer is always "write a Python extension and call it by name," never "add more syntax to the pipeline language."
- **Discovery and execution are the same.** The YAML file is the function definition — no AST-vs-runtime split.

### Tier 3: Python Extensions (formalized)

Python modules loaded once at startup. No `@function` decorator needed. Instead, declared in `brimley.yaml`:

```yaml
extensions:
  - module: report_utils
    load_at: startup
  - module: custom_transformers
    load_at: startup
```

Each extension module's public functions become callable step targets from YAML pipelines. Changes require a process restart — this is explicit and honest, unlike the current partial hot-reload behavior.

**Third-party libraries** work through the standard Python packaging ecosystem. A Brimley project's `pyproject.toml` (managed by Poetry, pip, uv, or similar) declares dependencies. Extensions have access to everything installed in the active Python environment:

```yaml
extensions:
  - module: pandas            # third-party, installed via poetry/pip
    load_at: startup
  - module: report_utils      # local project module
    load_at: startup
```

Brimley does not manage packages itself — it runs inside whatever environment it is launched in.

## Benefits

1. **No more AST/import duality.** Pipelines are pure data. Python extensions are standard imports. Neither pretends to be the other.
2. **Honest hot-reload semantics.** Pipelines reload instantly (they are data files). Extensions do not reload (they require restart). No ambiguity about which modules are stale.
3. **Lower barrier for non-Python orchestration.** YAML pipelines can be authored by anyone who understands the Brimley function catalog, without Python knowledge.
4. **Cleaner separation of concerns.** Data flow (pipelines) is separate from computation (extensions). The pipeline language stays small because complex logic has an explicit escape hatch.

## Open Questions

1. **Expression syntax.** How should `$variable` references, null checks, and field access work? A minimal string-interpolation approach, or a small expression evaluator?
2. **Error handling in pipelines.** Should there be a `try`/`on_error` step, or should all error handling live in Python extensions?
3. **Conditional assignment.** Patterns like `$approver or $order.assigned_to` need either a small expression language or a dedicated `coalesce` / `default` step modifier.
4. **For-each semantics.** Should `for_each` support early exit (`break`) or filtering (`when` inside the loop)?
5. **Migration path.** Can existing Python `@function` files coexist with pipelines during a gradual transition, or is it an all-or-nothing switch?

## Alternatives Considered

| Alternative | Verdict |
|---|---|
| **Starlark** (Python-like sandboxed scripting) | Cleanest scripting option — familiar syntax, no import system, trivial hot-reload. Adds a native dependency. Best fit if pipeline expressiveness proves too limited. |
| **Lua** (embedded scripting via `lupa`) | Battle-tested embedding story. Unfamiliar syntax for most teams. |
| **Jinja templates with side effects** | Already partially supported. Poor error messages; templates were not designed for orchestration. |
| **CEL / Expr** (expression languages) | Designed for policy evaluation, not multi-step workflows. |
| **WASM plugins** | Maximum flexibility and sandboxing. Massive complexity overhead. |

Starlark remains the strongest fallback if YAML pipelines prove too restrictive for real-world orchestration patterns.
