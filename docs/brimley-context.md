# BrimleyContext Design Specification
> Version 0.2

The `BrimleyContext` is the central orchestration object in the Brimley framework. It acts as a unified "Execution Context" that is injected into every Brimley function (Python, SQL, or Template-based). It facilitates communication between disparate system components, manages shared state, and provides a secure interface for accessing infrastructure resources.

## 1. Object Architecture

The `BrimleyContext` is composed of four primary pillars, categorized by their mutability and purpose.

|Attribute|Category|Mutability|Description|
|---|---|---|---|
|`app`|State|**Mutable**|Global or session-specific shared state.|
|`config`|Environment|**Read-Only**|Static configuration loaded at startup.|
|`functions`|Logic|**Resolved**|Registry of internal Brimley functions.|
|`databases`|Infrastructure|**Managed**|Named SQL connection pools for data persistence.|

## 2. Component Details

### A. Application State (`app`)

The `app` attribute is a thread-safe, key-value store intended for runtime data.

- **Scope:** Can be scoped to a single request lifecycle or persisted globally depending on the runner configuration.
    
- **Best Practice:** Use namespaced keys (e.g., `context.app["plugin_name.variable"]`) to prevent collisions across different modules.
    

### B. Configuration (`config`)

A read-only object containing environmental settings.

- **Sources:** Populated from `.yaml` config files, `.env` variables, or system defaults.
    
- **Access:** Typically accessed via a dot-notation or `get()` method to handle missing keys gracefully (e.g., `context.config.llm.model_name`).
    

### C. Function Registry (`functions`)

Provides a lookup mechanism for calling other Brimley functions.

- **Composition:** Enables a "lego-block" architecture where complex functions are built by invoking multiple smaller, specialized functions.
    
- **Resolution:** Handles the discovery of functions defined in various file formats (YAML, Markdown, Python).
    

### D. Database Manager (`databases`)

A registry of named SQL connection pools.

- **Default Pool:** A specific pool designated as `default` to simplify configurations.
    
- **Connection Routing:** SQL functions use a `connection` key to determine which pool to utilize.
    
- **Python Integration:** Python functions can acquire a connection from the pool for transactional logic or raw queries.
    

## 3. Implementation Example (Python Reflection & Annotations)

Brimley supports defining functions using native Python type hints and decorators. By convention, the first argument is reserved for the `BrimleyContext`. Subsequent arguments are automatically parsed by the framework, allowing for automatic schema generation via reflection.

```
from typing import List
from brimley import brimley_function, BrimleyContext

@brimley_function(name="generate_user_report")
def generate_user_report(context: BrimleyContext, user_id: str, tags: List[str] = None):
    """
    Brimley automatically extracts the schema for 'user_id' and 'tags' 
    using reflection, while keeping 'context' as the injected engine.
    """
    # 1. Read static config for branding
    company_name = context.config.get("branding.company_name", "Brimley Corp")
    
    # 2. Access a specific database pool
    orders_db = context.databases["orders_db"]
    with orders_db.get_connection() as conn:
        orders = conn.execute("SELECT * FROM orders WHERE user_id = :id", {"id": user_id})
    
    # 3. Call another Brimley function to format the data
    formatter = context.functions.get("markdown_table_generator")
    table = formatter.run(data=orders)
    
    # 4. Update shared state
    context.app["reports_generated"] = context.app.get("reports_generated", 0) + 1
    
    return f"# {company_name} Report for {user_id}\n\n{table}"
```

## 4. Design Advantages

1. **Dependency Injection:** Functions do not need to import database drivers or configuration loaders; they are "pushed" into the function at runtime.
    
2. **Reflection-Driven Schema:** By using typed Python arguments instead of a generic `args` dictionary, Brimley can automatically generate JSON schemas for tools and API documentation.
    
3. **Standardized SQL:** By moving connection logic to the context, SQL functions remain pure and portable across different environments.
    
4. **Observability:** Centralizing access to databases and state changes allows the framework to implement global logging, auditing, and performance monitoring.
    
5. **Environment Isolation:** Testing becomes trivial—developers can inject a "Mock Context" with in-memory databases and static config to verify logic in isolation.