# Brimley Functions
> Version 0.5

Brimley functions are the core execution units of the framework. In 0.5, Python functions are defined with decorators, while SQL/template functions continue to use embedded metadata frontmatter.

## Metadata Schema

Function metadata defines the function's name, type, arguments, return shape, and optional MCP exposure settings.

- **Python functions**: metadata comes from `@function(...)` decorators and type hints.
- **SQL/template functions**: metadata comes from frontmatter in source files.

## Core Properties

All functions share core properties.

| **Property**      | **Type**        | **Required** | **Description**                                                                 |
| ----------------- | --------------- | ------------ | ------------------------------------------------------------------------------- |
| `name`            | string          | Yes          | Unique function name. See [naming conventions](brimley-naming-conventions.md). |                                                                               |
| `type`            | string          | Yes          | Indicates the type of function.                                                     |
| `description`     | string          | No           |                                                                                 |
| `arguments`       | dict            | No           | See [arguments](brimley-function-arguments.md). |        
| `return_shape`    | string \| dict  | Yes          | See [return shape](brimley-function-return-shape.md). |                             |
|`mcp`|object|Configuration for exposing the function via Model Context Protocol.|No|


## Types of Functions

| **Function Type** | **File Extension(s)** | **Description** |
| -- | -- | -- |
| [Template Functions](brimley-template-functions.md) | `*.md` (and metadata-backed templates) | Jinja-based prompt/text rendering with argument mapping. |
| [Python Functions](brimley-python-functions.md) | `*.py` | Native Python handlers discovered from `@function` / `@function(...)`. |
| [SQL Functions](brimley-sql-functions.md) | `*.sql` | Parameterized SQL execution with metadata frontmatter. |

### The `mcp` Block

The `mcp` block marks a function as eligible for MCP tool export via FastMCP.

For Python functions, the equivalent is typically `@function(mcpType="tool")`.

```
mcp:
  type: tool
  # Optional: overrides the main description specifically for the LLM
  description: "Use this tool to calculate user metrics. Do not pass PII."
```

_(See_ [_MCP Integration_](brimley-model-context-protocol-integration.md "null") _for more details on argument filtering and MCP server behavior)._

## Example Definition

```
---
name: hello_world
type: template_function
description: "Greets the user and provides support contact info."
arguments:
  inline:
    name:
      type: string
      default: "World"
  support_email:
    type: string
    from_context: "config.support_email"
mcp:
  type: tool
---

# Hello {{ args.name }}!
Welcome to Brimley.
Contact us at: {{ args.support_email }}
```