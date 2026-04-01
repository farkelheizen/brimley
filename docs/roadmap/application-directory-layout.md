# Proposal: Application Directory Layout & Scan Isolation

> Status: Draft proposal
> Date: 2026-03-31

## Problem Summary

A Brimley application currently stores everything — configuration, source assets, runtime artifacts, and data files — in a single flat directory. When Brimley starts, the scanner (`os.walk`) and watcher (`Path.rglob`) traverse the entire root directory tree with **no hardcoded directory exclusions**. This produces several concrete problems:

1. **Wasted scan time.** The scanner reads every `.py`, `.sql`, `.md`, and `.yaml`/`.yml` file it finds. It walks into `__pycache__/`, `.brimley/`, `.pytest_cache/`, `logs/`, `.venv/`, `dist/`, and any other directory that happens to exist. Even though most files are silently discarded after a peek (e.g., a `.yaml` without `type: api_function|cli_function`), the I/O cost of opening and reading every matching file accumulates at startup and on every watch-mode poll cycle.

2. **Accidental parsing of non-function files.** The `brimley.yaml` config file is itself a `.yaml` file inside the root. The scanner opens it, calls `yaml.safe_load`, inspects `type:`, finds it missing, and discards it — but the work was still done. The same applies to `pyproject.toml`-adjacent YAML files, CI config, or any stray markdown.

3. **Generated/runtime directories pollute the tree.** A typical examples directory today looks like this:

   ```
   examples/
   ├── .brimley/          # daemon metadata (pid, attached client, history)
   ├── .pytest_cache/     # pytest artifacts
   ├── __pycache__/       # Python bytecode cache
   ├── logs/              # Brimley log files
   ├── data.db            # SQLite database
   ├── .env               # environment overrides
   ├── brimley.yaml       # configuration
   ├── calc.py            # ← actual Brimley function
   ├── hello.md           # ← actual Brimley function
   ├── users.sql          # ← actual Brimley function
   ├── github_profile.yaml # ← actual Brimley function
   └── ... (20+ more files)
   ```

   The ratio of scannable-function files to total files is roughly 1:2. In `examples2/`, which also contains `.venv/`, `dist/`, `poetry.lock`, test directories, and WAL files, the ratio is worse.

4. **Watch-mode false positives.** Because the watcher's default `include_patterns` are `["*.py", "*.sql", "*.md", "*.yaml"]` and `exclude_patterns` defaults to `[]`, log rotation, pytest runs, or pip installs can trigger unnecessary reload cycles.

5. **No convention for separating config from source.** The `brimley.yaml` must live at the root today. Moving it elsewhere is not supported — the CLI hardcodes `root_path / "brimley.yaml"` as the lookup path.

---

## Current Behavior (How Things Work Today)

### Scanner

- Entry point: `Scanner(root_dir).scan()`
- Traversal: `os.walk(self.root_dir)` — full recursive walk, no directory pruning.
- File identification: extension check (`.py`, `.sql`, `.md`, `.yaml`/`.yml`), then frontmatter/content peek.
- No hardcoded skip list for directories.

### Watcher

- Entry point: `PollingWatcher(root_dir, ..., include_patterns, exclude_patterns)`
- Traversal: `Path.rglob("*")` — full recursive glob.
- Filtering: `fnmatch` against `include_patterns` (default `["*.py", "*.sql", "*.md", "*.yaml"]`) and `exclude_patterns` (default `[]`).
- No hardcoded skip list for directories.

### Config resolution

- CLI parses `--root` (or defaults to `cwd`).
- Config path is always `root_path / "brimley.yaml"` (fallback: `cwd / "brimley.yaml"`).
- Scanner receives the same `root_path`.

### .brimley/ directory

- Created at `root_dir / ".brimley/"`.
- Contains `daemon.json`, `repl_client.json`, `repl_client_history`.
- Not excluded from scanning or watching.

---

## Proposals

Three options are presented below, from least to most disruptive. They are not mutually exclusive — Proposal A can be implemented immediately, and Proposals B/C build on top of it.

---

### Proposal A: Built-in Exclude List (Quick Win)

**Change:** Add a hardcoded set of directory names that the scanner and watcher always skip during traversal, regardless of user configuration.

**Suggested default skip list:**

```python
_ALWAYS_SKIP_DIRS = {
    "__pycache__",
    ".brimley",
    ".pytest_cache",
    ".git",
    ".venv",
    ".mypy_cache",
    ".ruff_cache",
    "node_modules",
    "dist",
    ".tox",
    ".nox",
    ".eggs",
    "*.egg-info",
}
```

**Scanner change** — prune `dirs` in-place during `os.walk`:

```python
for root, dirs, files in os.walk(self.root_dir):
    dirs[:] = [d for d in dirs if d not in _ALWAYS_SKIP_DIRS
               and not d.endswith(".egg-info")]
    ...
```

**Watcher change** — skip entries whose path components match:

```python
# In _is_tracked_path, before include/exclude check:
if any(part in _ALWAYS_SKIP_DIRS for part in relative_path.parts):
    return False
```

**Impact:** Zero config change required. Existing projects get faster scans immediately. No new CLI flags, no schema change.

**Risk:** A user who genuinely stores Brimley functions inside a directory named `dist/` or `.venv/` would need an escape hatch. This is an edge case that can be addressed later with an explicit `include_dirs` override if needed.

---

### Proposal B: Separate Source Directory (`scan_paths`)

**Change:** Introduce an optional `scan_paths` key in `brimley.yaml` that tells the scanner exactly which directories (relative to root) contain Brimley functions. When present, only those directories are scanned. When absent, the current behavior (scan from root) is preserved.

**Config schema addition:**

```yaml
brimley:
  app_name: "My App"
  scan_paths:          # NEW — optional
    - src/tools
    - src/entities
```

**Behavior:**

| `scan_paths` present? | Scanner root(s) |
|---|---|
| No | `root_dir` (current behavior) |
| Yes | Each listed path, resolved relative to `root_dir` |

**Benefits:**

- Users can isolate Brimley assets in a dedicated subdirectory, keeping config, data, tests, and runtime artifacts outside the scan tree.
- Combines naturally with Proposal A (skip list still applies within each scan path).
- No breaking change — omitting the key preserves existing behavior.

**Example layout:**

```
my-app/
├── brimley.yaml
├── .env
├── data.db
├── tools/                  # ← scan_paths: [tools]
│   ├── sales/
│   │   ├── pricing.py
│   │   ├── monthly_report.sql
│   │   └── customer_notes.md
│   └── marketing/
│       ├── campaigns.py
│       └── welcome_email.md
├── providers/              # ← scan_paths: [tools, providers]
│   └── di_provider.py
├── tests/
│   └── ...
├── logs/
└── .brimley/
```

The scanner would only walk `tools/` (and `providers/` if listed), ignoring everything else.

**Watcher change:** The watcher would also scope its `rglob` to the listed paths instead of the entire root, which directly reduces poll I/O.

---

### Proposal C: Separate Config Location (`--config`)

**Change:** Add a `--config` CLI option to decouple the config file location from the scan root. Today, `--root` controls both where `brimley.yaml` is found and where scanning starts. Splitting these concerns lets the config file live outside the scan tree entirely.

**CLI change:**

```
brimley repl --root ./tools --config ./brimley.yaml
brimley invoke calculate_tax --root ./tools --config ../brimley.yaml
```

**Resolution order:**

1. If `--config` is given, use that path.
2. Else if `root_path / "brimley.yaml"` exists, use that.
3. Else if `cwd / "brimley.yaml"` exists, use that.
4. Else error.

**Benefits:**

- Enables monorepo or multi-project layouts where config is at the workspace root but functions live in subdirectories.
- Eliminates the scanner parsing `brimley.yaml` as a potential YAML function file.
- Pairs well with Proposal B: `--root` can point to the scan directory, `--config` to the config file, or `scan_paths` can be relative to the `--config` file's parent.

**Example monorepo layout:**

```
workspace/
├── brimley.yaml            # shared config
├── .env
├── service-a/
│   ├── tools/
│   │   ├── pricing.py
│   │   └── report.sql
│   └── tests/
└── service-b/
    ├── tools/
    │   └── campaigns.py
    └── tests/
```

```bash
brimley repl --config ./brimley.yaml --root ./service-a/tools
```

---

### Proposal D: Conventional Project Layout (Documentation-Only)

**Change:** Define and document a recommended project layout in `brimley-application-structure.md`. This is a soft convention — Brimley does not enforce it, but documentation, examples, and scaffolding guide users toward it.

**Recommended layout:**

```
my-brimley-app/
├── brimley.yaml              # Configuration (at project root)
├── .env                      # Secrets/overrides (git-ignored)
├── pyproject.toml            # Python project metadata
├── README.md
│
├── functions/                # ← Brimley scans here (scan_paths: [functions])
│   ├── sales/
│   │   ├── pricing.py
│   │   ├── monthly_report.sql
│   │   └── customer_notes.md
│   ├── marketing/
│   │   ├── campaigns.py
│   │   └── welcome_email.md
│   └── shared/
│       ├── di_provider.py    # @provider definitions
│       └── entities.py       # @entity definitions
│
├── tests/                    # Test suite (outside scan tree)
│   └── ...
│
├── data/                     # Database files (outside scan tree)
│   └── app.db
│
└── .brimley/                 # Runtime metadata (auto-created, git-ignored)
    ├── daemon.json
    └── repl_client.json
```

**Gitignore template:**

```gitignore
# Brimley runtime
.brimley/
logs/

# Data
data/*.db
data/*.db-shm
data/*.db-wal

# Python
__pycache__/
.venv/
dist/
*.egg-info/
```

**SQLite path convention:** With this layout, the database URL in `brimley.yaml` changes to `sqlite:///./data/app.db` instead of `sqlite:///./data.db`, keeping data files out of the project root.

---

## Recommendation

Implement in this order:

1. **Proposal A** (hardcoded skip list) — immediate, zero-config performance improvement. Low risk, high value.
2. **Proposal D** (documented layout convention) — update `brimley-application-structure.md` and the `examples/` directories. Guides new users toward clean separation from day one.
3. **Proposal B** (`scan_paths`) — add the config key and wire it into scanner and watcher. This is the structural fix that makes isolation explicit and opt-in.
4. **Proposal C** (`--config` flag) — decouple config from root. This is the most flexible but least urgent, and primarily helps monorepo/multi-service setups.

Proposals A and D can ship in the next patch release. Proposals B and C are feature work and could target 0.10 or a dedicated minor release.

---

## Open Questions

1. **Should `scan_paths` also affect provider/lifecycle-hook discovery?** Providers and lifecycle hooks are discovered alongside functions in the same scan. If `scan_paths` is introduced, they should be scoped identically — but this should be confirmed.

2. **Should `logs/` always be in the skip list?** The default log path is `logs/brimley.log` relative to root. If users put function files in a `logs/` directory (unlikely but possible), the skip list would hide them. The Proposal A skip list above does not include `logs/` for this reason — it relies on the include-pattern extension filter to avoid false reloads from `.log` and `.jsonl` files. However, adding `logs/` to the skip list would avoid unnecessary directory traversal.

3. **Should Brimley support a `brimley init` scaffolding command?** A CLI command that generates the recommended layout (Proposal D) with a starter `brimley.yaml`, `functions/` directory, and `.gitignore` would lower the barrier to entry. This is a natural follow-up but out of scope for this proposal.

4. **Should `.brimley/` be relocatable?** Today it is always at `root_dir / ".brimley/"`. If `--config` (Proposal C) is implemented, should `.brimley/` follow the config file's parent directory or the `--root` directory? The daemon metadata is runtime state — it should follow `--root`.
