# Brimley 0.7: API Functions (.yaml)

> **ADR Reference:** [ADR-0002](../decisions/0002-accelerate-api-cli-to-v0.7.md) — accelerated from v0.9 to v0.7. [ADR-0003](../decisions/0003-secrets-block-ordered-resolution.md) — `secrets:` block ordered-resolution schema.

## Overview

API Functions allow developers to define HTTP-based integrations declaratively using YAML. These functions wrap `httpx` calls, treating external web services as first-class Brimley functions with MCP exposure.

## 1. Specification

API functions are defined in standard `.yaml` files where the `type` is set to `api_function`.

### Schema Example: `github_profile.yaml`

```yaml
name: get_user_profile
type: api_function
description: "Fetches user profile data from GitHub API"

# MCP Configuration Block
mcp:
  type: tool

# Root-level return_shape for consistency with other function types
return_shape: GitHubUser

secrets:
  github_token:
    - env: GITHUB_TOKEN           # checked first (v0.7)
    - provider: github_creds      # fallback when DI available (v0.8+)

request:
  method: GET
  url: "https://api.github.com/users/{{ username }}"
  headers:
    Authorization: "Bearer {{ secrets.github_token }}"
    Accept: "application/vnd.github.v3+json"
    X-Correlation-ID: "{{ correlation_id }}"
  timeout: 5.0

results:
  "200":
    type: json
    parse:
      path: "user_profile"
  "401":
    error: "Authentication failed — check GITHUB_TOKEN"
  "404":
    error: "User not found"
```

### Result Code Matching

The `results:` block maps HTTP status codes to parsing strategies and error messages. Keys are **strings** and are matched in **YAML declaration order** (first match wins).

- **Exact keys** (all digits, e.g., `"200"`, `"404"`): match only that specific status code.
- **Wildcard keys** (`Nxx` pattern, e.g., `"2xx"`, `"5xx"`): the first digit is literal, `xx` matches any value. `"2xx"` matches `200`–`299`.
- **`"default"`**: catch-all key that matches any status code. Should appear last.
- If no key matches: fall back to `text` parser (raw response body), no error raised.

Exact keys listed before a wildcard take priority by virtue of declaration order:

```yaml
results:
  "201":
    type: json
    parse:
      path: "id"
  "204":
    empty: true
  "2xx":
    type: json
    parse:
      path: "data"
  "4xx":
    error: "Client error"
  "default":
    error: "Unexpected response"
```

A `201` response uses the first entry. A `202` response falls through to `2xx`. A `500` response matches `default`.

### Validation Rules (Scanner)

- Each key must be: a 3-digit numeric string (`"200"`–`"599"`), a wildcard pattern matching `^[1-5]xx$`, or the literal `"default"`.
- Duplicate keys are rejected at scan time.
- A diagnostic warning is emitted if a wildcard key appears before an exact key in the same class (e.g., `"2xx"` before `"201"`) since the exact key would be unreachable.

> All keys declared under `secrets:` are automatically redacted from log output via a two-layer mechanism: (1) Loguru sink filter scrubs resolved secret values from all log messages, and (2) `BrimleyExecutionError` message construction passes messages through the same redaction function. Exception stack traces in debug mode may still contain secret values in local variable repr — this is a known limitation for v0.7. See [ADR-0003](../decisions/0003-secrets-block-ordered-resolution.md) for full resolution rules, source ordering, and examples across all function types.

## 2. MCP Integration

By defining the `mcp` block, API functions are automatically registered with the Model Context Protocol:

- **`mcp.type: tool`**: The function is exposed as a tool that an LLM can invoke. The `description` and `return_shape` are used to generate the tool's schema.
    
- **`mcp.type: resource`**: The function is exposed as a read-only resource.
    
- **`mcp.type: prompt`**: The function's output is treated as a prompt template.
    

## 3. Return Shapes & Entity Mapping

The root-level `return_shape` attribute defines the structural contract for the function output, ensuring it aligns with the rest of the Brimley ecosystem.

- **Unified Consistency:** API functions share the same signature metadata as SQL, Python, and Template functions.
    
- **Extraction Hints:** The `results` section provides the extraction logic via the `parse` block (e.g., `path`). The `parse.path` syntax is a custom dot-path expression — not JSONPath. See §4 for details.
    

## 4. Result Parsing — Pluggable `ResultParser`

Brimley v0.7 uses a **pluggable `ResultParser` interface** for parsing HTTP response bodies. The `results.<code>.type` field is a **parser name** (a registry key), not a content-type indicator.

### Built-in Parsers (v0.7)

| Parser Name | `type` Value | Behavior | `parse` Config |
|---|---|---|---|
| **Text** | `"text"` | Decodes response bytes to UTF-8 string. Returns raw text. | None (ignored) |
| **JSON** | `"json"` | Decodes response bytes as JSON. Optionally extracts a sub-object via `parse.path`. | `path` — dot-path expression (optional) |
| **Regex** | `"regex"` | Applies a regex pattern to the decoded UTF-8 string. Extracts a named capture group or full match. | `pattern` (required), `capture_group` (optional) |

If `type` is omitted, defaults to `"text"` (raw response body) — the safest zero-surprise default.

### Dot-Path Expression Syntax (`parse.path`)

Used by the `json` parser to extract nested data. No JSONPath dependency — implemented in-house.

- `"user_profile"` — top-level key extraction
- `"data.user.name"` — nested key traversal
- `"items[0]"` — list index access
- `"items[*].name"` — list-member projection (returns a list of `name` values)

### Future Extensibility

The `ResultParser` interface is designed for future extensibility (v0.13 plugin architecture). Additional parsers (`xml`, `binary`, `jsonpath`) can be registered without changing core code. If an unknown parser name is used, `BrimleyExecutionError` is raised with a clear message listing available parsers.

## 5. Key Features

- **Jinja2 Templating:** Support for argument injection in URL, headers, and body via `SandboxedEnvironment`.
    
- **Automatic Correlation Propagation:** The `correlation_id` is available for injection into headers.
    
- **Error Mapping:** Status codes mapped to `error` strings in the `results:` block raise `BrimleyExecutionError`.
    
- **Ordered First-Match:** The `results:` block supports exact codes, wildcard patterns (`2xx`, `4xx`), and a `default` catch-all, matched in YAML declaration order.
    

## 6. Execution Flow

1. **Discovery:** Scanner detects `.yaml` files with `type: api_function`.
    
2. **MCP Registration:** If the `mcp` block is present, the function is added to the FastMCP provider.
    
3. **Dispatch:** Routed to `ApiRunner`.
    
4. **Execution:** HTTP call is executed asynchronously.
    
5. **Mapping:** Response is parsed via the matched `ResultParser`, path-extracted (if configured), and mapped to the `return_shape`.
## 7. Security Requirements (Shipping Gate)

Before v0.7 can be released, a **Security Acceptance gate** must be completed — see [ADR-0002](../decisions/0002-accelerate-api-cli-to-v0.7.md) for the full requirement:

- **Threat model document** covering injection vectors for LLM-driven API calls
- **Injection test suite** using payloads from [PayloadAllTheThings](https://github.com/swisskyrepo/PayloadAllTheThings)
- **CI static analysis:** [Bandit](https://github.com/PyCQA/bandit) (B602/B603 rules) and [Semgrep](https://github.com/returntypes/semgrep)
- **Runtime prompt injection screening:** [llm-guard](https://github.com/protectai/llm-guard) `PromptInjection` scanner hook in `Dispatcher.run()`. `llm-guard` is an **optional Poetry extra** (`security = ["llm-guard"]`), installed via `poetry install --extras security`. The Dispatcher hook checks for runtime availability and skips gracefully if not installed. The hook is the hard requirement; the dependency is opt-in.
- **Pre-commit secret scanning:** [detect-secrets](https://github.com/Yelp/detect-secrets)
- **Code review checklist** signed off before merge

## 8. Known Gaps (v0.7 Release)

- **`provider` secret source:** Declared in `secrets:` YAML but raises `BrimleySecretResolutionError` at startup if `provider` is the **only** declared source (no `env` fallback). If `env` is listed first and `provider` is a fallback, a diagnostic **warning** is emitted (not error) since the `env` path may succeed at runtime. The ordered-resolution schema ([ADR-0003](../decisions/0003-secrets-block-ordered-resolution.md)) is forward-compatible with no breaking changes needed in v0.8.
- **MockRegistry intercept:** `ApiRunner` cannot be intercepted in offline tests until v0.9 Mocking. A documented stub intercept point is left in `Dispatcher.run()` to avoid a structural change when v0.9 lands.
- **Startup time:** `httpx.AsyncClient` is not yet a singleton provider; it will be refactored to a `@provider(scope="singleton")` when DI lands in v0.8.
- **Plugin architecture:** `BaseRunner` ships as an internal-only interface. External plugin loading is deferred to v0.13 ([ADR-0004](../decisions/0004-defer-plugin-architecture-to-v0.13.md)).
