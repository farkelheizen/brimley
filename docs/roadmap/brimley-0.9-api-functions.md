# Brimley 0.9: API Functions (.yaml)

## Overview

API Functions allow developers to define HTTP-based integrations declaratively using YAML. These functions wrap `httpx`(or similar) calls, treating external web services as first-class Brimley functions.

## 1. Specification

API functions are defined in standard `.yaml` files where the `type` is set to `api_function`.

### Schema Example: `github_profile.yaml`

```
name: get_user_profile
type: api_function
description: "Fetches user profile data from GitHub API"

# MCP Configuration Block
mcp:
  type: tool

# Root-level return_shape for consistency with other function types
return_shape: GitHubUser

request:
  method: GET
  url: "[https://api.github.com/users/](https://api.github.com/users/){{ username }}"
  headers:
    Accept: "application/vnd.github.v3+json"
    X-Correlation-ID: "{{ correlation_id }}"
  timeout: 5.0

response:
  200: 
    type: "json"
    parse:
      path: "$.user_profile" 
  404: 
    error: "User not found"
```

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

Brimley 0.9 handles a variety of response formats including `json`, `xml`, `text`, and `binary`. The `auto` type uses the `Content-Type`header for intelligent detection.

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
## Unresolved Architectural Feedback

*   **Secret Management:** Providing a `SecretProvider` is great, but relying on environment variables or a specific vault integration opens questions about safe storage during local development versus containerized production.
*   **Startup Time Impact (v1.0 Concern):** With a plugin registry initiating via YAML, achieving a 200ms startup is extremely ambitious for Python. Strict lazy-loading architectures will be necessary.
