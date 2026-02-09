# Brimley Naming Conventions
> Version 0.2

To ensure compatibility with the **Model Context Protocol (MCP)**, **FastMCP**, and various database engines, all Brimley objects (Functions, Resources, and Tools) must adhere to the following naming rules.

## 1. The "Identifier" Ruleset

A Brimley identifier must follow these constraints:

|**Rule**|**Specification**|
|---|---|
|**Start Character**|Must start with an ASCII letter (`a-z`, `A-Z`).|
|**Allowed Characters**|Letters, numbers (`0-9`), underscores (`_`), and hyphens (`-`).|
|**Prohibited**|Spaces, periods, and special symbols (e.g., `@`, `!`, `$`, `/`).|
|**Length**|Minimum 2 characters, Maximum 64 characters.|
|**Case Sensitivity**|Identifiers are **case-sensitive**, though `snake_case` is the recommended standard for Python-based functions.|

### Regex Pattern

```
^[a-zA-Z][a-zA-Z0-9_-]{1,63}$
```

## 2. Naming Styles by Component

While the ruleset allows both underscores and hyphens, we recommend the following styles to maintain consistency across different function types:

### A. Python Functions (`snake_case`)

Since Python functions are often defined via reflection, use standard Pythonic naming.

- **Good:** `generate_user_report`, `process_sql_queue`
    
- **Avoid:** `GenerateUserReport` (CamelCase)
    

### B. Template Functions (`kebab-case` or `snake_case`)

Templates often behave like "actions" or "prompts."

- **Good:** `creative-writer-prompt`, `email_validator`
    

### C. MCP Integration

When registering with **FastMCP**, Brimley will use the function name as the `tool_name`. Keeping these names within the 64-character limit ensures they are compatible with OpenAI and Anthropic tool-calling schemas, which often have strict identifier limits.

## 3. Reserved Prefixes

To prevent collisions with future core features, avoid starting custom function names with `brimley_` or `sys_`.

- **Reserved:** `brimley_init`, `sys_health_check`
    
- **User Defined:** `my_app_init`, `health_check_service`
    

## 4. Why these rules?

1. **URL Safety:** Hyphens and underscores are safe in URIs (e.g., `mcp://tools/get-user-data`).
    
2. **Database Compatibility:** Most SQL engines handle `snake_case` identifiers without requiring double quotes.
    
3. **LLM Reliability:** LLMs are trained heavily on code that uses these conventions, leading to better tool-selection accuracy when the model sees clear, delimited names.
