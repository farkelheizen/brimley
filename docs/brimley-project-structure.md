# Brimley Project Structure & Dependencies
> Version 0.2

This document outlines the directory structure and required libraries for the initial Python implementation of Brimley.

## 1. Recommended Directory Layout

```
brimley-engine/
├── src/                    # Source Code
│   └── brimley/            # Core Library
│       ├── __init__.py
│       ├── cli/            # CLI & REPL logic
│       │   ├── main.py     # Uses Typer
│       │   └── repl.py
│       ├── core/           # Base classes (Context, Entity)
│       │   ├── context.py
│       │   └── entity.py
│       ├── discovery/      # Filesystem scanner & Parsers
│       │   ├── scanner.py
│       │   ├── python_parser.py
│       │   ├── sql_parser.py
│       │   └── template_parser.py
│       ├── execution/      # Runners for different types
│       │   ├── python_runner.py
│       │   ├── sql_runner.py
│       │   └── jinja_runner.py
│       └── utils/          # Diagnostics & Helpers
│           └── diagnostics.py
├── docs/                   # Documentation
│   ├── design/             # High-level Design & Plans
│   │   ├── brimley-0.2-design.md
│   │   └── brimley-0.2-plan.md
│   └── specs/              # Technical Specifications
│       ├── brimley-0.2-cli-harness.md
│       ├── brimley-0.2-discovery-loader.md
│       └── ...
├── examples/               # (Phase 5) Sample Brimley functions
├── tests/                  # Pytest suite
│   ├── test_discovery.py
│   ├── test_execution.py
│   └── mock_functions/     # Test cases for scanner
├── pyproject.toml          # Poetry configuration
└── README.md
```

## 2. Core Dependencies

|**Library**|**Purpose**|
|---|---|
|`pydantic`|Data validation.|
|`pydantic-settings`|Configuration loading (.env support).|
|`typer`|CLI command framework (replaces Click).|
|`jinja2`|Template engine for Markdown/YAML functions.|
|`pyyaml`|Parsing YAML frontmatter and config files.|
|`pytest`|Critical testing framework.|
|`rich`|For "Wall of Shame" diagnostic reporting and REPL UI.|
|`pandas`|(Optional) For SQL result formatting.|

## 3. Environment Setup for Copilot

The project uses **Poetry** for dependency management.

1. **Install:** `poetry install`
    
2. **Run Tests:** `poetry run pytest`
    
3. **Run CLI:** `poetry run brimley`
    

When starting in VS Code, ensure the Python interpreter is set to the virtual environment created by Poetry.