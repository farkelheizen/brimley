# Brimley 0.12: Smart Caching & Invalidation

## Overview

Brimley 0.12 introduces a declarative caching layer within the `Dispatcher`. This allows functions to skip execution if a valid result exists. Unlike standard memoization, Brimley caching supports complex invalidation strategies based on time, size, and **External Versioning**.

## 1. Declarative Configuration

Caching is defined at the function level (YAML for SQL/API/CLI or decorators for Python).

### Example: Multi-Key Versioned Caching (SQL)

```
name: get_user_dashboard
type: sql_function
cache:
  strategy: versioned
  # Supports single string or a list of keys
  keys: 
    - "users_table"
    - "permissions_table"
  provider: "db_version_tracker"
```

## 2. Invalidation Strategies

### A. Temporal (TTL)

Standard time-based expiration (e.g., `ttl: 10m`).

### B. Version-Based (The "cache_keys" Pattern)

Brimley supports invalidation based on a central version registry.

1. **The Version Registry:** A background thread (managed via a `singleton` provider) periodically polls a `cache_keys` table and maintains an in-memory map of `{key: version}`.
    
2. **The Cache Entry:** When a result is cached, Brimley stores the `result` alongside a map of all associated `keys` and their `versions` at that specific moment.
    
3. **The Validation:** On the next call, the `Dispatcher` iterates through all keys defined for that function. It compares the versions stored inside the cache entry with the current versions in the local registry. **If any single key's version has changed, the entire entry is invalidated.**
    

### C. Conditional (The "Watch" Pattern)

For simple checks, use `watch_sql` or `watch_api` to check a fingerprint before execution.

## 3. DI Framework Integration (Custom Mechanisms)

Brimley's caching is built on two DI-replaceable interfaces: `ICacheStore` and `IVersionProvider`.

### Customizing the Storage

You can define a custom store (e.g., Redis, Disk, or encrypted memory) by overriding the `cache_store` provider.

### Customizing the Version Tracking

You can implement your own version tracking logic (e.g., your trigger-based table polling) as a singleton provider that maintains the in-memory version map.

## 4. Key-Hashing Logic

Brimley generates a unique cache key based on:

1. **Function Name**.
    
2. **Arguments**: A deterministic hash of inputs.
    
3. **Context Sensitivity**: If `cache.scoped: true`, the `user_id` from the context is included in the hash.
    

## 5. Execution Flow in Dispatcher

1. **Request:** Function call initiated.
    
2. **Lookup:** Dispatcher checks if `cache` is defined.
    
3. **Key Gen:** Generates a hash of inputs to find the cache entry.
    
4. **Validation (If Versioned):**
    
    - Retrieve the `version_map` stored within the cache entry (e.g., `{"users_table": "2023-10-27 10:00:00"}`).
        
    - Loop through the keys:
        
        - Fetch `current_version` from the `VersionProvider` for the key.
            
        - Compare `entry.version` vs `current_version`.
            
        - If `entry.version != current_version` for **any** key -> **STALE/MISS**.
            
5. **Result:**
    
    - **HIT:** Returns cached value.
        
    - **MISS:** Executes runner, fetches current versions for all keys from the provider, and stores `[result, version_map]`.
        

## 6. Observability

The **DuckDB Introspection** engine exposes cache performance metrics:

```
-- View which keys are causing the most invalidations
/sql SELECT key, invalidation_count FROM brimley_cache_key_metrics ORDER BY 2 DESC;
```
## Unresolved Architectural Feedback

*   **Identity Crisis (Type: Workflow):** Introducing declarative YAML-based multi-step agent macros (`type: workflow`) starts moving Brimley from an MCP backend / context provider into a workflow orchestrator (like LangChain or Temporal). Is this out of scope for Brimley's core identity? 
*   **Cache Invalidation:** `watch_sql` for invalidation is exceptionally hard to get right in distributed systems. If Brimley instances scale horizontally, how is the cache invalidated across multiple running daemon instances?
