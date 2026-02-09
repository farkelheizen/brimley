# Brimley High-Level Design
> Version 0.2

## 1. Executive Summary

Brimley is a lightweight, file-based function execution engine designed to bridge the gap between static definitions (SQL, Python, Templates) and dynamic execution environments (CLI, REPL, and eventually FastMCP). It emphasizes a "Configuration over Code" approach for discovery and a strict contract for inputs and outputs.

## 2. Core Architecture

Brimley operates as a **Monolithic Engine** with a distinct lifecycle:

1. **Boot & Discovery:** On startup, the engine recursively scans a `ROOT_DIR`, identifying functions based on file extensions and internal metadata markers.
    
2. **Registration:** Valid functions are compiled into an in-memory `Registry`. Invalid functions generate `Diagnostics` but do not crash the boot process (until the "Wall of Shame" report).
    
3. **Context Injection:** Every execution is injected with a `BrimleyContext`, providing access to configuration, databases, and shared application state.
    
4. **Invocation:** The `CLI` or `REPL` invokes functions by name, passing arguments that are validated and merged against the function's schema.
    

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
    
- **Parsing**: Extracting YAML frontmatter and code bodies.
    
- **Validation**: Enforcing [Naming Conventions](brimley-naming-conventions.md) and schema requirements.
    
- **Diagnostics**: Accumulating errors for the [Wall of Shame](brimley-diagnostics-and-error-reporting.md).
    

### C. Function Types

Brimley supports three primary function primitives:

1. [Python Functions](brimley-python-functions.md): Native code execution with reflection-based schema inference.
    
2. [SQL Functions](brimley-sql-functions.md): Database queries wrapped in metadata, executed via the Context's connection pools.
    
3. [Template Functions](brimley-template-functions.md): Jinja2-based text generation returning strings or structured messages.
    

### D. The Interface Layer

Defined in [CLI & REPL Harness](brimley-cli-and-repl-harness.md):

- **`invoke`**: Single-shot execution for scripts/pipes.
    
- **`repl`**: Interactive loop with state persistence and multi-line input support.
    

## 4. Data Flow

1. **User Input** (CLI Args / YAML File)  ⬇
    
2. **Argument Merger** (Input + Context + Defaults) ⬇
    
3. **Validator** (Checks types against `arguments` spec) ⬇
    
4. **Runner** (Python/SQL/Jinja Execution) ⬇
    
5. **Output Formatter** (Raw string or JSON) ⬇
    
6. **STDOUT**

## 5. Reference Documentation Map

- [Project Structure](brimley-project-structure.md)
- [Function Arguments](brimley-function-arguments.md)
- [Return Shapes](brimley-function-return-shape.md)
- [Entities](brimley-entities.md)
