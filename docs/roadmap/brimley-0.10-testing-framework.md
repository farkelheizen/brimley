# Brimley 0.10: Testing Framework

## Overview

Brimley 0.10 provides a built-in testing harness designed to verify Python, SQL, and Template functions in isolation or as integrated flows. The testing framework leverages the existing `MockRegistry` and `Dispatcher` to provide a "flight simulator" for Brimley applications.

## 1. The `brimley test` Command

The CLI provides a dedicated entry point for executing tests.

- **Usage:**
    
    ```
    # Run all tests discovered in the project
    brimley test
    
    # Run tests for a specific function
    brimley test --function my_logic
    
    # Run tests and re-run on file changes
    brimley test --watch
    
    # Combined: Watch only a specific function's tests
    brimley test --function my_logic --watch
    ```
    
- **Discovery:** Brimley scans for files matching `test_*.py` or `*.test.yaml` within the project root or a `tests/` directory.
    

## 2. Testing Strategies

### A. Python-Based Tests (Recommended)

Brimley integrates with `pytest`. When `brimley test` is called, it initializes a `BrimleyContext` and provides it as a fixture.

```
# tests/test_agent.py
import pytest

def test_agent_logic(brimley_ctx):
    # This call uses the Dispatcher, automatically applying active mocks
    result = brimley_ctx.execute_function_by_name(
        "agent_sample", 
        {"prompt": "Hello"}
    )
    assert "mocked response" in result.lower()
```

### B. Declarative YAML Tests

For simple input/output verification (especially for SQL and Markdown functions), users can define tests in YAML.

```
# tests/user_queries.test.yaml
test_name: "Verify user lookup"
function: "get_users_sql"
input:
  age: 25
expect:
  - { id: 1, name: "Mock User", age: 25 }
```

## 3. Mock Integration

When running in `test` mode, Brimley automatically enables "Mock Discovery":

- **Automatic Sideloading:** All mocks found in the `mocks/` directory are loaded into the `MockRegistry` before tests run.
    
- **The Shim:** The `Dispatcher` ensures that any nested function calls (e.g., a Template calling a SQL function) check the `MockRegistry` first. This allows testing a "parent" function while "child" functions are mocked out.
    

## 4. MCP Context Mocking in Tests

Tests requiring an `mcp_ctx` will automatically receive the `BrimleyMockContext`.

- **Static Sampling:** If a test matches a `when_prompt` in the `MockRegistry`, the `sample()` call returns the pre-defined response.
    
- **Strict Mode:** In `test` mode, if `mcp_ctx.sample()` is called and no mock matches, Brimley will raise an error rather than prompting for interactive input (unlike REPL mode).
    

## 5. Execution Environment

- **Isolation:** Tests run with a "Clean State" version of `BrimleyContext.app`.
    
- **Safe Sinks:** During `brimley test`, logging is typically suppressed or routed to a `.brimley/test.log` file unless the `--verbose`flag is used.
    
- **TAP Output:** For CI/CD compatibility, `brimley test` can output results in Test Anything Protocol (TAP) format.
    

## Implementation Notes

- **Pytest Plugin:** Brimley will ship an internal pytest plugin that handles the `brimley_ctx` fixture and `MockRegistry`initialization.
    
- **Watch Mode Mechanics:** When `--watch` is used, Brimley utilizes the `ReloadEngine`. If `--function` is also provided, the engine filters the watch-set to only trigger re-runs when files associated with that specific function (or its tests) change.
## Unresolved Architectural Feedback

*   **Agent Critique Determinism:** `brimley test --agent` using an LLM to critique logic is highly innovative, but non-deterministic tests lead to flaky CI pipelines. This feature might need to be clearly separated strictly as a "linter" or "advisory" tool rather than a pass/fail test runner metric.
