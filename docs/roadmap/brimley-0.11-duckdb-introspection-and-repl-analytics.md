# Brimley 0.11: DuckDB Introspection & REPL Analytics

## Overview

Brimley 0.11 integrates **DuckDB** into the REPL-client to provide real-time analytical capabilities. This allows developers to query the internal state, execution history, and structured logs of the Brimley application using SQL directly from the REPL prompt.

## 1. The Concept: "The App as a Database"

Brimley exposes internal data structures as virtual tables within an in-memory DuckDB instance. This avoids the need for a separate observability stack (like Prometheus/Grafana) during local development.

## 2. Virtual Tables

The following tables are automatically available for querying in the REPL:

|   |   |   |
|---|---|---|
|**Table Name**|**Description**|**Source**|
|`brimley_functions`|Metadata about all discovered functions.|`Registry`|
|`brimley_logs`|Real-time stream of structured logs.|`.brimley/logs.jsonl`|
|`brimley_executions`|Execution metrics (latency, success/fail, correlation IDs).|`Dispatcher`|
|`brimley_mocks`|List of active mocks and their hit counts.|`MockRegistry`|

## 3. REPL Commands

The REPL provides a `/sql` (or `/q`) command to interface with DuckDB.

### Examples:

```
# Find the 5 slowest functions in the last hour
/sql SELECT name, avg(latency_ms) FROM brimley_executions GROUP BY 1 ORDER BY 2 DESC LIMIT 5;

# Search logs for a specific correlation ID
/sql SELECT message, level FROM brimley_logs WHERE correlation_id = '8a2f1b3c';

# Count functions by runner type
/sql SELECT type, count(*) FROM brimley_functions GROUP BY 1;
```

## 4. DuckDB & JSONL Integration

Since Brimley 0.6 already supports **JSONL file sinks** for logging (see `docs/brimley-0.6-correlation-ids.md`), DuckDB can query these files directly without loading them into memory:

```
# Internal Implementation Snippet
import duckdb

def query_logs(sql_query):
    # DuckDB can query JSONL files directly with high performance
    return duckdb.query(f"""
        SELECT * FROM read_json_auto('.brimley/logs.jsonl') 
        WHERE {sql_query}
    """)
```

## 5. Execution Metrics (The "Flight Recorder")

The `Dispatcher` is updated to push a summary of every execution into a circular in-memory buffer that DuckDB can read.

- **Fields:** `function_name`, `runner_type`, `start_time`, `end_time`, `latency_ms`, `status`, `correlation_id`.
    

## 6. Real-time Dashboarding (Future)

The REPL can use these queries to provide a "Live View" (similar to `top` or `htop`) that shows function throughput and error rates in a dedicated pane.

## 7. Implementation Strategy

- **Lazy Initialization:** DuckDB is only initialized the first time a `/sql` command is run or when the file sink is first accessed.
    
- **In-Process:** DuckDB runs inside the REPL process, meaning zero network overhead for querying local state.
    
- **Schema-on-Read:** For logs, DuckDB's `read_json_auto` is used to ensure that as the log format evolves, the queries don't break.
## Unresolved Architectural Feedback

*   **Bloat vs. Value:** Introducing DuckDB specifically for REPL analytics after introducing SQLite for State Persistence in v0.8 seems redundant. Can the SQLite persistence layer from v0.8 just be queried directly for REPL analytics? Adding DuckDB significantly increases the footprint and dependency size of the framework.
*   **Startup Time Impact (v1.0 Concern):** With DuckDB loading introspections, achieving a 200ms startup is extremely ambitious for Python. Strict lazy-loading architectures will be necessary.
