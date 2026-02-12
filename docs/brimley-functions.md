# Brimley Functions
> Version 0.2

Brimley functions are the core execution units of the framework. They are defined in files containing YAML frontmatter followed by the function body.

## Frontmatter Schema

Every Brimley function requires a YAML frontmatter block enclosed in `---`. The frontmatter defines the function's metadata, arguments, return shape, and external integrations (like MCP).

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
| [Template Functions](brimley-template-functions.md) | *.yaml, *.md | Used to define strings or a list of messages based upon the arguments and an internal template |
| [Python Functions](brimley-python-functions.md) | *.py | TBD |
| [SQL Functions](brimley-sql-functions.md) | *.sql | TBD |

### The `mcp` Block

The `mcp` block marks a function as eligible for MCP tool export via FastMCP.

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