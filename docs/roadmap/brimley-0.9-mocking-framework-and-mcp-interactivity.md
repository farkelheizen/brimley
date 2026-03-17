# Brimley 0.9: Mocking Framework & MCP Interactivity

> **⚠ SPEC REQUIRES FULL REWRITE before v0.9 planning begins.**
>
> This document was originally written as the v0.7 spec when Mocking preceded DI. Since then, two decisions changed:
>
> 1. [ADR-0001](../decisions/0001-swap-di-and-mocking-order.md): DI (v0.8) precedes Mocking (v0.9). Mocking is a consumer of the DI container.
> 2. [ADR-0002](../decisions/0002-accelerate-api-cli-to-v0.7.md): API & CLI functions moved to v0.7.
>
> **The standalone `MockRegistry` pattern described below is abandoned.** The new design:
> - `MockRegistry` is replaced by `BrimleyContainer.override(provider_name, mock_impl)` (the `override()` API is exposed in v0.8).
> - `@brimley.mock` becomes syntactic sugar for registering a test-scoped provider override — not a distinct parallel concept.
> - `ApiRunner` and `CliRunner` (shipped in v0.7) are interceptable in tests via provider override, not a Dispatcher-level intercept.
> - REPL offline development for API/CLI functions is a v0.9 feature (not available in v0.7).
>
> The content below is preserved for historical reference. All new implementation work must follow the `BrimleyContainer.override()` integration model.

---

## Overview (Original v0.7 Draft — For Reference Only)

Brimley 0.7 introduces a dual-layered mocking strategy.

1. **Developer Mocking:** An internal registry used to simulate environment-specific behaviors (like MCP Sampling) and external dependencies (SQL/Templates) in the CLI/REPL.
    
2. **Test Mocking:** Integration with standard Python mocking tools for automated verification.
    

## Requirements

### 1. The Mocking Registry & Discovery

To keep `brimley.yaml` concise, Brimley supports externalized mock definitions.

- **Mock Files:** Mocks can be stored in `.yaml` files. By convention, Brimley looks for a `mocks/` directory in the project root.
    
- **Scanning Flag:** A new CLI flag `--mocks <path>` (defaulting to `./mocks`) tells Brimley to scan for mock definitions on startup.
    
- **Hot-Reloading:** The `ReloadEngine` must monitor mock files. If a mock file is updated, the `MockRegistry` is refreshed instantly, allowing iterative development in the REPL.
    
- **Registration Methods:**
    
    - External YAML files (multi-mock support).
        
    - `@brimley.mock` decorators in Python.
        
    - Dynamic entry via REPL commands (e.g., `/mock set ...`).
        

### 2. Multi-Runner Mocking (SQL & Markdown)

The `Dispatcher` intercepts calls before they reach the runners, enabling mocks for "pure" function types:

- **SQL Functions:** Mocks return a list of dictionaries, simulating a database result set. This bypasses the need for an active DB connection.
    
- **Markdown (Template) Functions:** Mocks return a raw string. This is useful for testing high-level agent flows without rendering complex, nested Jinja2 templates that might have their own side effects.
    
- **Matching Logic:** Mocks match based on `function_name` and an `input_pattern` (exact match or regex of arguments).
    

### 3. MCP Sampling Mock (Interactive & Static)

The `mcp_ctx.sample()` call is the primary consumer of this framework.

- **Detection:** The `Dispatcher` detects if a function requires an MCP context.
    
- **Prioritization:**
    
    1. **Direct Match:** If `MockRegistry` has a response for the specific prompt string or pattern, return it immediately.
        
    2. **REPL Interactive:** If in REPL-mode and no static mock exists, pause and prompt the user for a `SamplingResponse`.
        
    3. **Live Host:** If running in a real MCP host, use the real context.
        
- **REPL Interactivity:** Only `TextContent` is supported in interactive mode.
    

### 4. Logging & Progress Delegation

The Brimley Mock Context must delegate lifecycle methods to the unified logging structure without corrupting `stdout`:

- **Logging:** `ctx.info()`, `ctx.error()`, etc., are routed to `loguru` (stderr/file).
    
- **Progress:** `ctx.report_progress()` updates the REPL status line and emits an `INFO` log to the file/stderr sink.
    

### 5. Async Support & Model Contract

- All mock responses involving `sample()` must be `async`.
    
- Mock responses must return a `SamplingResponse` object with a `content.text` structure.
    

## Implementation Strategy

### Multi-Mock YAML File (e.g., `mocks/api_mocks.yaml`)

```
# Multiple mocks can be defined in a single file
- function: get_users_by_age
  when: { age: 25 }
  returns:
    - { id: 1, name: "Mock User", age: 25 }

- function: generate_welcome_email
  when: { name: "Alice" }
  returns: "Hello Alice! Welcome to the mocked world."

- function: mcp_sample
  when_prompt: ".*random numbers.*"
  returns_sample:
    content: "Here are your numbers: 42, 7, 99"
    model: "brimley-static-mock"
```

### Using the @brimley.mock Decorator

The decorator allows for dynamic Python-based mocking logic. It can return static values or be used as a factory.

```
import brimley

# 1. Simple static return for a SQL or Template function
@brimley.mock(function="get_users_sql", when={"active": True})
def mock_active_users():
    return [{"id": 1, "name": "Brimley Admin"}]

# 2. Mocking an MCP Sampling call specifically
@brimley.mock(mcp_sampling=True, when_prompt=r"calculate (.*)")
def mock_calculator_sample(match):
    # 'match' is the regex match object from the prompt
    expression = match.group(1)
    return f"The result of {expression} is 42."

# 3. Dynamic mocking based on complex logic
@brimley.mock(function="process_order")
def mock_order_logic(args):
    if args.get("amount", 0) > 1000:
        return {"status": "flagged", "reason": "High value"}
    return {"status": "approved"}
```

### Mock Object Definition

```
class MockSamplingResponse:
    def __init__(self, text, model="brimley-mock", role="assistant", stop_reason="end_turn"):
        # Mimics the FastMCP structure: sample.content.text
        self.content = type('obj', (object,), {'text': text})
        self.model = model
        self.role = role
        self.stopReason = stop_reason
    
    @property
    def text(self) -> str:
        return self.content.text
```
## Unresolved Architectural Feedback

*   **Mocking (v0.7) before Dependency Injection (v0.8):** Introducing a Mocking Framework before standardizing on Dependency Injection (DI) might result in duplicated effort. Usually, mocking relies heavily on DI interfaces to swap out real implementations for mocks. If v0.7 builds a custom module replacement strategy, v0.8’s `@provider` and `Depends()` might force a rewrite of the v0.7 mocking mechanics. *Recommendation:* Consider swapping v0.7 and v0.8, or explicitly design v0.7’s MockRegistry to stub the future DI container.
*   **Security & Isolation:** When doing "Offline Development", simulating DBs and APIs can be complex. Will the mocks run in the same process space, or isolated? 
*   **Mock State Persistence:** If LLM responses are mocked, how do we handle multi-turn conversations?
