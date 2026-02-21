# Brimley SQL Execution

> Version 0.3

This document specifies how Brimley executes `SqlFunction` definitions using SQLAlchemy. It covers configuration, connection management, parameter binding, and result formatting.

## 1. Configuration (`brimley.yaml`)

Database connections are defined in the `databases` section of the configuration file.

```
databases:
  default:
    url: "sqlite:///./brimley.db"
    # Optional connection arguments passed to create_engine
    connect_args: 
      check_same_thread: false
  
  warehouse:
    url: "postgresql://user:pass@localhost:5432/warehouse"
```

For SQLite URLs that use relative filesystem paths (for example `sqlite:///./brimley.db`), Brimley resolves the path against the active project root (`--root` when provided, otherwise the current project root).

## 2. Infrastructure Layer

### Connection Management

Brimley uses **SQLAlchemy** as its database abstraction layer.

- **Initialization**: At startup, the context hydration process reads `ctx.settings.databases` (the config dicts).
    
- **Engine Creation**: It iterates through these definitions and creates a SQLAlchemy `Engine` for each.
    
- **Storage**: These engines are stored in `ctx.databases` (a `Dict[str, Engine]`), keyed by the definition name (e.g., "default", "warehouse").
    

## 3. The SQL Runner (`SqlRunner`)

The `SqlRunner` is responsible for executing the SQL defined in `.sql` files.

### 3.1 Parameter Binding

Brimley leverages SQLAlchemy's native named parameter support.

- **Function Arguments**: The arguments passed to the function are already a dictionary (e.g., `{"min_age": 25, "status": "active"}`).
    
- **SQL Syntax**: The SQL file uses standard colon-prefixed parameters (`:min_age`, `:status`).
    
- **Binding**: The runner passes the argument dictionary directly to SQLAlchemy's `execute()` method.
    

### 3.2 Execution Flow

1. **Resolution**: The runner identifies the target connection name from `func.connection` (defaults to "default").
    
2. **Lookup**: It retrieves the corresponding `Engine` from `ctx.databases`.
    
3. **Connection**: It establishes a connection (`with engine.connect() as conn:`).
    
4. **Preparation**: The raw SQL string is wrapped in `sqlalchemy.text()`.
    
5. **Execution**: `result = conn.execute(text_obj, args)`
    
6. **Commit**: If the SQL is a DML statement (INSERT/UPDATE/DELETE), the transaction is committed.
    

### 3.3 Return Types

For now, SQL functions return raw dictionaries (or lists of dictionaries).

- **Select Queries**: Returns `List[Dict[str, Any]]` using `result.mappings().all()`.
    
- **Action Queries**: Returns a status dictionary, e.g., `{"rows_affected": result.rowcount}`.
    

_(Future Phase: Automatic casting of results to defined Entities)_

## 4. Dependencies

- **`sqlalchemy`**: Core ORM and expression language.
    
- **Drivers**: Users must install drivers appropriate for their connection strings (e.g., `psycopg2` for Postgres). SQLite is included in Python.