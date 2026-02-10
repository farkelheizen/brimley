# Brimley Project Structure & Dependencies
> Version 0.2.0

This document outlines the directory structure and required libraries for the initial Python implementation of Brimley.

## 1. Current Directory Layout

```
brimley2/
├── src/                    # Source Code
│   └── brimley/            # Core Library
│       ├── __init__.py
│       ├── cli/            # CLI & REPL logic
│       │   ├── __init__.py
│       │   ├── main.py     # Uses Typer
│       │   └── repl.py
│       ├── core/           # Base classes and models
│       │   ├── __init__.py
│       │   ├── context.py
│       │   ├── entity.py
│       │   ├── models.py
│       │   └── registry.py
│       ├── discovery/      # Filesystem scanner & Parsers
│       │   ├── __init__.py
│       │   ├── scanner.py
│       │   ├── python_parser.py
│       │   ├── sql_parser.py
│       │   ├── template_parser.py
│       │   └── utils.py
│       ├── execution/      # Runners and argument resolution
│       │   ├── __init__.py
│       │   ├── arguments.py
│       │   ├── jinja_runner.py
│       │   ├── python_runner.py
│       │   └── sql_runner.py
│       └── utils/          # Diagnostics & Helpers
│           ├── __init__.py
│           └── diagnostics.py
├── docs/                   # Documentation (flat structure)
│   ├── brimley-cli-and-repl-harness.md
│   ├── brimley-context.md
│   ├── brimley-diagnostics-and-error-reporting.md
│   ├── brimley-discovery-and-loader-specification.md
│   ├── brimley-entities.md
│   ├── brimley-function-arguments.md
│   ├── brimley-function-return-shape.md
│   ├── brimley-functions.md
│   ├── brimley-high-level-design.md
│   ├── brimley-naming-conventions.md
│   ├── brimley-project-structure.md
│   ├── brimley-python-functions.md
│   ├── brimley-sql-functions.md
│   └── brimley-template-functions.md
├── examples/               # Sample Brimley functions
│   ├── calc.py
│   ├── hello.md
│   └── users.sql
├── tests/                  # Pytest suite
│   ├── __init__.py
│   ├── conftest.py
│   ├── test_arguments.py
│   ├── test_cli.py
│   ├── test_context.py
│   ├── test_diagnostics_display.py
│   ├── test_discovery.py
│   ├── test_e2e_examples.py
│   ├── test_entities.py
│   ├── test_execution_jinja.py
│   ├── test_execution_python.py
│   ├── test_execution_sql.py
│   ├── test_models.py
│   ├── test_parsers.py
│   ├── test_registry.py
│   ├── test_repl.py
│   ├── test_scanner.py
│   └── mock_functions/     # Test cases for scanner
├── pyproject.toml          # Poetry configuration
├── poetry.lock             # Lock file
├── README.md
└── .gitignore

## 2. Core Dependencies

|**Library**|**Purpose**|
|---|---|
|`pydantic`|Data validation.|
|`pydantic-settings`|Configuration loading (.env support).|
|`typer`|CLI command framework.|
|`jinja2`|Template engine for Markdown/YAML functions.|
|`pyyaml`|Parsing YAML frontmatter and config files.|
|`pytest`|Critical testing framework.|
|`rich`|For "Wall of Shame" diagnostic reporting and REPL UI.|

## 3. Environment Setup

The project uses **Poetry** for dependency management.

1. **Install:** `poetry install`
    
2. **Run Tests:** `poetry run pytest`
    
3. **Run CLI:** `PYTHONPATH=src poetry run brimley` (workaround for venv path resolution issue)
    

When starting in VS Code, ensure the Python interpreter is set to the virtual environment created by Poetry.