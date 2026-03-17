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

response:
  200:
    type: json
    parse:
      path: "$.user_profile"
  401:
    error: "Authentication failed â check GITHUB_TOKEN"
  404:
    error: "User not found"
```

> All keys declared under `secrets:` are automatically redacted from log output. See [ADR-0003](../decisions/0003-secrets-block-ordered-resolution.md) for full resolution rules, source ordering, and examples across all function types.

## 2. MCP Integration

By defining the `mcp` block, API functions are automatically registered with the Model Context Protocol:

- **`mcp.type: tool`**: The function is exposed as a tool that an LLM can invoke. The `description` and `return_shape` are used to generate the tool's schema.
    
- **`mcp.type: resource`**: The function is exposed as a read-only resource.
    
- **`mcp.type: prompt`**: The function's output is treated as a prompt template.
    

## 3. Return Shapes & Entity Mapping

The root-level `return_shape` attribute defines the structural contract for the function output, ensuring it aligns with the rest of the Brimley ecosystem.

- **Unified Consistency:** API functions share the same signature metadata as SQL, Python, and Template functions.
    
- **Extraction Hints:** The `response` section provides the extraction logic via the `parse` block (e.g., `path`, `is_list`).
    

## 4. Supported Content Types

Brimley 0.7 handles a variety of response formats including `json`, `xml`, `text`, and `binary`. The `auto` type uses the `Content-Type`header for intelligent detection.

## 5. Key Features

- **Jinja2 Templating:** Support for argument injection in URL, headers, and body.
    
- **Automatic Correlation Propagation:** The `correlation_id` is available for injection into headers.
    
- **Error Mapping:** Status codes map to `BrimleyExecutionError` strings.
    

## 6. Execution Flow

1. **Discovery:** Scanner detects `.yaml` files with `type: api_function`.
    
2. **MCP Registration:** If the `mcp` block is present, the function is added to the FastMCP provider.
    
3. **Dispatch:** Routed to `ApiRunner`.
    
4. **Execution:** HTTP call is executed asynchronously.
    
5. **Mapping:** Response is parsed, path-extracted, and mapped to the `return_shape`.
## 7. Security Requirements (Shipping Gate)

Before v0.7 can be released, a **Security Acceptance gate** must be completed — see [ADR-0002](../decisions/0002-accelerate-api-cli-to-v0.7.md) for the full requirement:

- **Threat model document** covering injection vectors for LLM-driven API calls
- **Injection test suite** using payloads from [PayloadAllTheThings](https://github.com/swisskyrepo/PayloadAllTheThings)
- **CI static analysis:** [Bandit](https://github.com/PyCQA/bandit) (B602/B603 rules) and [Semgrep](https://github.com/returntypes/semgrep)
- **Runtime prompt injection screening:** [llm-guard](https://github.com/protectai/llm-guard) `PromptInjection` scanner in `Dispatcher.run()`
- **Pre-commit secret scanning:** [detect-secrets](https://github.com/Yelp/detect-secrets)
- **Code review checklist** signed off before merge

## 8. Known Gaps (v0.7 Release)

- **`provider` secret source:** Declared in `secrets:` YAML but raises `BrimleySecretResolutionError` at startup until DI (v0.8) is available. The ordered-resolution schema ([ADR-0003](../decisions/0003-secrets-block-ordered-resolution.md)) is forward-compatible with no breaking changes needed in v0.8.
- **MockRegistry intercept:** `ApiRunner` cannot be intercepted in offline tests until v0.9 Mocking. A documented stub intercept point is left in `Dispatcher.run()` to avoid a structural change when v0.9 lands.
- **Startup time:** `httpx.AsyncClient` is not yet a singleton provider; it will be refactored to a `@provider(scope="singleton")` when DI lands in v0.8.
- **Plugin architecture:** `BaseRunner` ships as an internal-only interface. External plugin loading is deferred to v0.13 ([ADR-0004](../decisions/0004-defer-plugin-architecture-to-v0.13.md)).
