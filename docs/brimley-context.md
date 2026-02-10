# BrimleyContext Design Specification

> Version 0.2

The `BrimleyContext` is the central orchestration object in the Brimley framework. It acts as the "Engine Room" that holds configuration, database connections, and application state.

Execution Runners use the `BrimleyContext` to resolve dependencies and inject arguments explicitly requested by the function definitions.

## 1. Object Architecture

The `BrimleyContext` is composed of four primary pillars, categorized by their mutability and purpose.

|**Attribute**|**Category**|**Mutability**|**Description**|
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

### D. Database Manager (`databases`)

A registry of named SQL connection pools.

- **Default Pool:** A specific pool designated as `default` to simplify configurations.
    

## 3. Usage in Execution

**The `BrimleyContext` is never passed directly to functions.**

Instead, the Execution Runners use the context as a reservoir to resolve dependencies before invoking logic:

1. **Argument Resolution:** The runner looks at the function's `arguments` spec. If an argument defines `from_context: "app.user_id"`, the runner extracts that value from the Context and passes it as a standard argument.
    
2. **Dependency Injection (Python):** The runner inspects Python type hints. If a function requests `Annotated[Connection, "orders_db"]`, the runner retrieves the specific pool from `context.databases` and injects it.
    

## 4. Design Advantages

1. **Decoupling:** Functions are pure and testable. A Python function can be tested by passing simple mock objects instead of a complex Framework Context.
    
2. **Security (Least Privilege):** Functions only receive the specific data and connections they explicitly request.
    
3. **Reflection-Driven Schema:** By using typed Python arguments, Brimley can automatically generate JSON schemas for tools and API documentation.
    
4. **Observability:** Centralizing access to databases and state changes allows the framework to implement global logging, auditing, and performance monitoring.