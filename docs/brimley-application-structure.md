# Brimley Application Structure

> Version 0.3

A standard Brimley application follows a specific directory layout to ensure the **Discovery Engine** can locate functions, entities, and configuration.

## Root Directory

```
my-brimley-app/
├── brimley.yaml          # [NEW] Main configuration file
├── .env                  # Local environment variables (git-ignored)
├── README.md
├── pyproject.toml        # Python dependencies
└── src/
    └── ...
```

## Configuration

- **`brimley.yaml`**: The single source of truth for configuration. It defines database connections, application constants, and framework settings.

- **`auto_reload` in `brimley.yaml`**: Controls optional watch-mode behavior (`enabled`, polling interval, debounce, include/exclude filters).
    
- **`.env`**: Secrets and local overrides. Variables defined here can be referenced in `brimley.yaml` using `${VAR_NAME}` syntax.
    

## Source Directory (`src/` or `tools/`)

Brimley recursively scans your project root. Most apps keep executable assets in either `src/` or `tools/`. Python files should be standard modules using decorators (`@function`, `@entity`) and can contain multiple related functions/classes.

Grouping by domain is recommended.

```
src/
├── sales/
│   ├── pricing.py            # Python module: @function(s) + @entity class(es)
│   ├── monthly_report.sql    # SQL Function
│   └── customer_notes.md     # Template Function
└── marketing/
    ├── campaigns.py          # Python module with multiple decorators
    └── welcome_email.md      # Template Function
```

## Runtime Orchestration

Brimley supports two runtime orchestration modes:

- **REPL-managed:** use `brimley repl --watch` (or config `auto_reload.enabled: true`) for interactive dynamic reload.
- **Host-managed:** use `BrimleyRuntimeController` in external apps to start/stop auto-reload and run policy-based reload cycles.

In both modes, reload applies partitioned domain policy so unaffected domains remain available if downstream domains fail validation.