# Brimley API Functions

> **Introduced in:** Brimley 0.7; `provider` secrets activated in 0.8
> **ADR References:** [ADR-0002](decisions/0002-accelerate-api-cli-to-v0.7.md) — accelerated from v0.9. [ADR-0003](decisions/0003-secrets-block-ordered-resolution.md) — `secrets:` block schema.
> **Docs baseline: 0.8.x**

API Functions allow developers to define HTTP-based integrations declaratively using YAML. These functions wrap `httpx` calls, treating external web services as first-class Brimley functions with full MCP exposure.

## 1. Schema

API functions are defined in `.yaml` files where `type` is set to `api_function`.

```yaml
name: get_github_profile
type: api_function
description: "Fetches a GitHub user's public profile data via the GitHub REST API"
return_shape: string

mcp:
  type: tool

arguments:
  inline:
    username:
      type: string
      description: "GitHub username to look up"

secrets:
  github_token:
    - env: GITHUB_TOKEN

request:
  method: GET
  url: "https://api.github.com/users/{{ username }}"
  headers:
    Authorization: "Bearer {{ secrets.github_token }}"
    Accept: "application/vnd.github.v3+json"
    X-Correlation-ID: "{{ correlation_id }}"
  timeout: 10.0

results:
  "200":
    type: json
    parse:
      path: "login"
  "401":
    error: "Authentication failed — check GITHUB_TOKEN environment variable"
  "404":
    error: "GitHub user not found"
  "default":
    error: "Unexpected response from GitHub API"
```

### Core Fields

| Field | Type | Required | Description |
|---|---|---|---|
| `name` | string | Yes | Unique function name. See [naming conventions](brimley-naming-conventions.md). |
| `type` | string | Yes | Must be `"api_function"`. |
| `description` | string | No | Human-readable description used in MCP tool schemas. |
| `return_shape` | string \| dict | Yes | See [return shape](brimley-function-return-shape.md). |
| `mcp` | object | No | MCP exposure config. See [MCP integration](brimley-model-context-protocol-integration.md). |
| `arguments` | dict | No | User-facing input schema. See [arguments](brimley-function-arguments.md). |
| `secrets` | dict | No | Secret resolution config. See [secrets](brimley-secrets.md). |
| `request` | object | Yes | HTTP request configuration. |
| `results` | dict | No | Per-status-code outcome mapping. |

### `request` Block

| Field | Type | Required | Description |
|---|---|---|---|
| `method` | string | No | HTTP method. Defaults to `GET`. |
| `url` | string | Yes | Request URL. Jinja2 template (SandboxedEnvironment). |
| `headers` | dict | No | Request headers. Values are Jinja2 templates. |
| `body` | string \| dict | No | Request body. String is treated as raw; dict is JSON-serialized. |
| `timeout` | float | No | Per-request timeout in seconds. Falls back to `execution.timeout_seconds` in `brimley.yaml`. |

All Jinja2 template fields have access to: validated function arguments, `secrets.<name>` (resolved), and `correlation_id`.

## 2. Result Matching

The `results:` block maps HTTP status codes to parsing strategies and error messages. Keys are **strings**, matched in **YAML declaration order** (first match wins).

- **Exact keys** (`"200"`, `"404"`): match only that specific status code.
- **Wildcard keys** (`"2xx"`, `"4xx"`, `"5xx"`): first digit is literal, `xx` matches any value.
- **`"default"`**: catch-all key. Place last.
- **No match**: falls back to `text` parser (raw response body), no error raised.

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

### Result Entry Fields

| Field | Description |
|---|---|
| `type` | Parser name: `"text"` (default), `"json"`, or `"regex"`. |
| `parse` | Parser-specific config. |
| `error` | Error message string — raises `BrimleyExecutionError`. |
| `empty` | If `true`, signals a valid-but-empty result (returns `None`). |

### Validation Rules (Scanner)

- Keys must be a 3-digit numeric string (`"200"`–`"599"`), a wildcard pattern (`^[1-5]xx$`), or `"default"`.
- Duplicate keys are rejected at scan time.
- A diagnostic warning is emitted if a wildcard key appears before an exact key in the same class.

## 3. Result Parsers

Brimley 0.7 ships three built-in `ResultParser` implementations. The `results.<code>.type` field selects the parser by name.

| Parser | `type` value | Behavior | `parse` config |
|---|---|---|---|
| Text | `"text"` | Decodes response bytes to UTF-8 string. Returns raw text. | None |
| JSON | `"json"` | Decodes response as JSON. Optionally extracts a sub-value via `parse.path`. | `path` (optional) |
| Regex | `"regex"` | Applies a regex pattern to the decoded string. | `pattern` (required), `capture_group` (optional) |

If `type` is omitted, defaults to `"text"`.

### Dot-Path Expression Syntax (`parse.path`)

The `json` parser uses a custom dot-path expression — no JSONPath dependency.

| Expression | Meaning |
|---|---|
| `"login"` | Top-level key extraction |
| `"user.profile.name"` | Nested key traversal |
| `"items[0]"` | List index access |
| `"items[*].name"` | List-member projection (returns list of `name` values) |

## 4. Security

API functions use several layers of defense against injection attacks.

### URL Validation
After Jinja2 rendering, the final URL is validated:
- Only `http` and `https` schemes are allowed. `file://`, `ftp://`, etc. raise `BrimleyExecutionError`.
- URLs with embedded credentials (`http://user:pass@host`) are rejected.

### Header Injection Prevention
Rendered header values are checked for `\r\n` sequences (HTTP response splitting). Any header containing CRLF raises `BrimleyExecutionError`.

### Template Sandboxing
All Jinja2 rendering uses `jinja2.sandbox.SandboxedEnvironment`. User-provided argument values cannot execute arbitrary code or access restricted attributes.

**Template-authoring restrictions** enforced by SandboxedEnvironment:
- No access to `__dunder__` attributes (e.g., `__class__`, `__globals__`).
- No `import` expressions or module access.
- No calling unsafe methods on built-in types (e.g., `str.format_map`).
- Undefined variables raise `UndefinedError` immediately (`StrictUndefined` mode).

### Secrets Redaction
Resolved secret values are automatically redacted from all Loguru log output and from `BrimleyExecutionError` messages. See [secrets](brimley-secrets.md) for full redaction scope.

### Prompt Injection Screening
An optional `llm-guard` hook in `Dispatcher.run()` can screen arguments for prompt injection. Enable in `brimley.yaml`:

```yaml
config:
  security:
    prompt_injection_screening: true
```

Install the optional extra: `poetry install --extras security`. If `llm-guard` is not installed and screening is enabled, a warning is logged and screening is skipped gracefully.

## 5. MCP Registration

API functions with an `mcp:` block are automatically registered with the MCP provider:
- `secrets` keys are **not** exposed in the MCP tool schema.
- `from_context` arguments are excluded (injected at runtime).
- Only user-facing `arguments:` fields appear in the tool schema.

See [MCP integration](brimley-model-context-protocol-integration.md) for full details.

## 6. Execution Flow

1. Scanner detects `.yaml` files with `type: api_function`.
2. `timeout_seconds` is validated (required, must be > 0). `provider:` secret sources are accepted at scan time (0.8+) and resolved via the DI container at call time.
3. If `mcp:` block is present, function is registered with the FastMCP provider.
4. At invocation, `Dispatcher` routes to `ApiRunner`.
5. `ApiRunner` resolves secrets, renders templates, validates URL scheme and headers, then executes the HTTP call via `httpx.AsyncClient`.
6. Response is matched against the `results:` block (ordered first-match).
7. Matched parser extracts and returns the result, which is validated against `return_shape`.

## 7. Known Gaps / Open Items

- **MockRegistry intercept:** `ApiRunner` cannot be intercepted in offline tests until v0.10 Mocking. Stub intercept point left in `Dispatcher`.
- **Internal SSRF blocking:** URL scheme validation rejects non-HTTP(S) schemes. RFC-1918 host blocking is deferred to a future release (network-level controls recommended for production).

> **Resolved in 0.8:** `provider` secret sources now resolve via `BrimleyContainer.resolve()` at call time. `validate_secrets_no_provider()` is no longer called at scan time.
