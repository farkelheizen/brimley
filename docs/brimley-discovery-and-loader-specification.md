# Brimley Discovery & Loader Specification

> Version 0.3

The Discovery Engine translates assets on disk (or reflected module metadata) into executable function/entity models, then loads them into Brimley registries.

## 1. Scanning Algorithm

1. **Initialization:** accept a `root_dir`.
2. **Traversal:** walk the tree recursively (`os.walk` / `Path.rglob`).
3. **Identification (extension-based):**
   - `.py` -> Python parser route
   - `.sql` -> SQL parser route only when SQL frontmatter marker is present
   - `.md` -> template parser route only when markdown frontmatter marker is present
   - `.yaml` -> not routed as standalone entities in the decorator-transition model
4. **Parsing dispatch:**
   - `sql_function` -> `parse_sql_file`
   - `template_function` -> `parse_template_file`
   - `python_function` -> `parse_python_file`
5. **Collection:** parser outputs are normalized into function/entity lists plus diagnostics.

This replaces the old Python 500-character YAML type probe for function identification.

## 2. Python AST Parsing (Zero-Execution)

`parse_python_file` is AST-first and does not import/execute target modules during scanner discovery.

Behavior summary:

- Parse with `ast.parse`.
- Detect decorators:
  - `@function` / `@brimley.function`
  - `@entity` / `@brimley.entity`
- Extract decorator literal kwargs when statically evaluable (`name`, `reload`, `mcpType`, `type`, etc.).
- Infer function arguments from signatures, including:
  - `Annotated[..., AppState("...")]`
  - `Annotated[..., Config("...")]`
  - system-injected context types (`BrimleyContext`, `Context`, `MockMCPContext`) filtered from public argument schema.
- Infer `return_shape` from return annotations.
- Build entity handlers as `{module_name}.{class_name}` for decorated classes.

Transition note: a legacy fallback for Python YAML frontmatter may still be applied when no decorators are discovered.

## 3. Validation Flow

For every identified object:

### Functions

1. **Schema check:** required metadata exists (for example `name`, `return_shape`).
2. **Name check:** must pass naming regex and uniqueness constraints.
3. **Handler check (Python):** handler path must be derivable/importable by runtime.
4. **MCP metadata check:** if MCP metadata exists, validate it against supported schema (`type: tool` + optional fields).

### Entities

1. **Decorator check:** class is marked with `@entity`/`@brimley.entity`.
2. **Name check:** name passes regex and uniqueness constraints.
3. **Registry check:** no duplicate names in `ctx.entities`.

## 4. Error Accumulation

Discovery should not abort on first failure. Scanner/parser errors are accumulated as diagnostics. If critical errors remain, Brimley emits diagnostics output and blocks normal startup/load flow.

## 5. Successful Registration

A successful scan returns:

1. `functions`: list of `BrimleyFunction` implementations.
2. `entities`: list of discovered entities.
3. `diagnostics`: warnings/errors encountered during scan.

Registration:

- `ctx.functions.register_all(scan_result.functions)`
- `ctx.entities.register_all(scan_result.entities)`

## 6. Hybrid Discovery for Runtime/Compiled Modes

When file-system scanning is constrained (embedded/compiled environments), Brimley supports runtime reflection discovery through `scan_module(module_obj)`.

- Reflection inspects members carrying `_brimley_meta`.
- Discovered members are converted into function/entity models.
- This enables discovery without direct source-file AST parsing.

## 7. Asset Compilation Bridge (`brimley build`)

To make SQL/Markdown assets discoverable in runtime reflection scenarios, Brimley provides `brimley build`.

Workflow:

1. Scan project with standard scanner.
2. Collect discovered SQL/template functions.
3. Generate `brimley_assets.py` containing shim functions decorated with `@function(...)` metadata.
4. Load/scan the generated module in runtime mode so non-Python assets are discoverable via reflection.

Default output target is `<root>/brimley_assets.py` (CLI options can override output path).
