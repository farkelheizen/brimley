# Brimley High-Level Design
> Version 0.4

## 1. Executive Summary

Brimley is a lightweight, file-based function execution engine designed to bridge the gap between static definitions (SQL, Python, Templates) and dynamic execution environments (CLI, REPL, and FastMCP). It emphasizes a "Configuration over Code" approach for discovery and a strict contract for inputs and outputs.

## 2. Core Architecture

Brimley operates as a **Monolithic Engine** with a distinct lifecycle:

1. **Boot & Discovery:** On startup, the engine recursively scans a `ROOT_DIR`, identifying functions based on file extensions and internal metadata markers.
    
2. **Registration:** Valid functions are compiled into an in-memory `Registry`. Invalid functions generate `Diagnostics` but do not crash the boot process (until the "Wall of Shame" report).
    
3. **Context Injection:** Every execution is injected with a `BrimleyContext`, providing access to configuration, databases, and shared application state.
    
4. **Invocation:** The `CLI` or `REPL` invokes functions by name, passing arguments that are validated and merged against the function's schema. The REPL also supports [Admin Commands](brimley-repl-admin-commands.md) for inspecting engine state and can run an embedded MCP server over SSE when configured.

5. **Runtime Refresh (Optional):** When `auto_reload.enabled` is active, Brimley uses a polling watcher with debounce and partitioned reload policy to refresh entities/functions/MCP tools without tearing down unaffected runtime domains.
    

## 3. Key Components

### A. The Context Layer

The [BrimleyContext](brimley-context.md) is the spine of the application. It holds:

- **State (`app`)**: Mutable dictionary for session data.
    
- **Logic (`functions`)**: The registry of executable tools.
    
- **Infrastructure (`databases`)**: Connection pools.
    
- **Config (`config`)**: Immutable settings.
    

### B. The Discovery Engine

Defined in [Discovery & Loader](brimley-discovery-and-loader-specification.md), this component handles:

- **Scanning**: Recursively finding `.py`, `.sql`, `.md`, and `.yaml` files.
    
- **Parsing (Zero-Execution AST for Python)**: Parsing Python files with `ast.parse()` to discover `@function` and `@entity` markers without importing or executing user modules.

- **Compatibility**: Supporting transitional legacy Python YAML frontmatter where decorators are not yet present.
    
- **Validation**: Enforcing [Naming Conventions](brimley-naming-conventions.md) and schema requirements.
    
- **Diagnostics**: Accumulating errors for the [Wall of Shame](brimley-diagnostics-and-error-reporting.md).

### C. Hybrid Discovery Modes

Brimley uses two discovery strategies depending on runtime context:

- **Static Discovery (Default CLI/REPL)**: File-system scan + AST parsing for Python decorators and metadata parsing for SQL/template files.

- **Runtime Discovery (Embedded/Compiled)**: Reflection scan (`scan_module`) for callables/classes carrying `_brimley_meta`, enabling discovery when source files are unavailable at runtime.

- **Bridge for Non-Python Assets**: `brimley build` generates Python shim modules for SQL/template assets so runtime reflection can discover them uniformly.
    

### D. Function Types

Brimley supports three primary function primitives:

1. [Python Functions](brimley-python-functions.md): Native code execution with reflection-based schema inference.
    
2. [SQL Functions](brimley-sql-functions.md): Database queries wrapped in metadata, executed via the Context's connection pools.
    
3. [Template Functions](brimley-template-functions.md): Jinja2-based text generation returning strings or structured messages.
    

### E. The Interface Layer

Defined in [CLI & REPL Harness](brimley-cli-and-repl-harness.md):

- **`invoke`**: Single-shot execution for scripts/pipes.
    
- **`repl`**: Interactive loop with state persistence and multi-line input support.

- **`mcp-serve`**: Non-REPL MCP hosting with optional host-managed watch lifecycle.

- **`build`**: Generate shim modules for SQL/template runtime reflection discovery.

- **`validate`**: Emit diagnostics reports with configurable fail thresholds for CI/local checks.

- **`schema-convert`**: Convert constrained JSON Schema subsets into inline FieldSpec migration output.

- **`auto_reload`**: Optional watch-mode orchestration for dynamic updates, available in REPL and via host-managed runtime controller.

### F. The MCP Integration Layer

Defined in [MCP Integration](brimley-model-context-protocol-integration.md), this component handles:

- **Tool Exposure**: Functions tagged with `mcp: { type: tool }` are exposed to MCP clients.

- **Schema Filtering**: Arguments sourced from `from_context` are hidden from MCP tool input schemas.

- **Embedded Hosting**: REPL can host FastMCP over SSE without conflicting with interactive terminal input.

- **Adapter Reuse**: MCP tool registration is modular so external apps can attach Brimley tools to existing FastMCP servers.
    

## 4. Data Flow

1. **User Input** (CLI Args / YAML File)  ⬇
    
2. **Argument Merger** (Input + Context + Defaults) ⬇
    
3. **Validator** (Checks types against `arguments` spec) ⬇
    
4. **Runner** (Python/SQL/Jinja Execution) ⬇

5. **Result Mapper** (Marshals raw output into Typed Entities) ⬇
    
6. **Output Formatter** (Raw string or JSON) ⬇
    
7. **STDOUT**

## 5. Reference Documentation Map

- [What’s New in 0.4](brimley-0.4-whats-new.md)
- [What’s Next in 0.5](brimley-0.5-what-next.md)
- [Project Structure](brimley-application-structure.md)
- [Function Arguments](brimley-function-arguments.md)
- [Return Shapes](brimley-function-return-shape.md)
- [Entities](brimley-entities.md)
- [Model Context Protocol Integration](brimley-model-context-protocol-integration.md)
