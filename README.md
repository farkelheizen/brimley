# Brimley
> Version 0.2

**Brimley** is a lightweight, file-based function execution engine designed to bridge the gap between static logic definitions (SQL, Python, Templates) and dynamic execution environments (CLI, REPL, and AI Agents).

It emphasizes a **"Configuration over Code"** approach for discovery and a strict contract for inputs and outputs, making it the ideal engine for building modular toolsets for Large Language Models (LLMs).

## 🚀 Key Features

- **File-Based Discovery:** Just drop `.py`, `.sql`, `.md`, or `.yaml` files into a directory. Brimley automatically scans, validates, and registers them.
    
- **Unified Context:** Every function receives a `BrimleyContext` containing configuration, database pools, and shared application state.
    
- **Multi-Modal Functions:**
    
    - **Python:** Native logic with reflection-based schema inference.
        
    - **SQL:** Parameterized queries managed via connection pools.
        
    - **Templates:** Jinja2-based text/prompt generation.
        
- **Developer Experience:** Built-in CLI and interactive REPL with state persistence.
    
- **Strict Validation:** Inputs and outputs are validated against defined schemas before execution.
    

## 🛠️ Installation

Brimley uses **Poetry** for dependency management.

### Prerequisites

- Python 3.10+
    
- [Poetry](https://python-poetry.org/docs)


### Setup

```
# Clone the repository
git clone [https://github.com/farkelheizen/brimley.git](https://github.com/farkelheizen/brimley.git)
cd brimley

# Install dependencies
poetry install
```

## ⚡ Quick Start

### 1. Create a Function

Create a file named `hello.yaml` in your tools directory:

```
# ./tools/hello.yaml
name: greet_user
type: template_function
return_shape: string
arguments:
  inline:
    name: string
---
Hello, {{ name }}! Welcome to Brimley.
```

### 2. Run with CLI

Use the `invoke` command for single-shot execution:

```
poetry run brimley ./tools invoke greet_user --input "{name: 'Developer'}"
# Output: Hello, Developer! Welcome to Brimley.
```

### 3. Interactive REPL

Start the interactive loop to test stateful workflows:

```
poetry run brimley ./tools repl
```

```
[SYSTEM] Scanning ./tools...
[SYSTEM] Loaded 1 functions: greet_user

brimley > greet_user {name: "Arthur"}
Hello, Arthur! Welcome to Brimley.

brimley > quit
```

## 📚 Documentation

The detailed design and specifications are located in the `docs/` directory:

- **Architecture:** [High-Level Design](./docs/brimley-high-level-design.md)
- **Roadmap:** [Implementation Plan](./docs/brimley-implementation-plan.md)
- **CLI Guide:** [CLI & REPL Harness](./docs/brimley-cli-and-repl-harness.md)
- **Project Structure:** [Project Structure](./docs/brimley-project-structure.md)
- **Core Concepts:**
    - [Brimley Context](./docs/brimley-context.md)
    - [Discovery & Registry](./docs/brimley-discovery-and-loader-specification.md)
    - [Functions](./docs/brimley-functions.md)

## 🧪 Development

We follow a strict **Test-First** methodology.

```
# Run the test suite
poetry run pytest

# Run tests with coverage
poetry run pytest --cov=brimley
```