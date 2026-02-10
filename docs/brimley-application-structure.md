# Brimley Application Structure

> Version 0.2

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
    
- **`.env`**: Secrets and local overrides. Variables defined here can be referenced in `brimley.yaml` using `${VAR_NAME}` syntax.
    

## Source Directory (`src/`)

The `src` directory is scanned recursively. You can organize it however you like, but grouping by domain is recommended.

```
src/
├── sales/
│   ├── calculate_tax.py      # Python Function
│   ├── monthly_report.sql    # SQL Function
│   └── customer.yaml         # Entity Definition
└── marketing/
    ├── welcome_email.md      # Template Function
    └── campaign.yaml         # Entity Definition
```