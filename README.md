<h1 align="center">agentfiles</h1>

<p align="center">
  <strong>Sync AI tool configurations across platforms</strong>
</p>

<p align="center">
  <a href="https://pypi.org/project/agentfiles/">
    <img src="https://img.shields.io/pypi/v/agentfiles?color=blue&label=pypi" alt="PyPI">
  </a>
  <a href="https://pypi.org/project/agentfiles/">
    <img src="https://img.shields.io/pypi/pyversions/agentfiles" alt="Python Versions">
  </a>
  <a href="https://github.com/svetlovtech/agentfiles/actions">
    <img src="https://img.shields.io/github/actions/workflow/status/svetlovtech/agentfiles/ci.yml?branch=main&label=CI" alt="CI">
  </a>
  <a href="LICENSE">
    <img src="https://img.shields.io/badge/license-MIT-blue" alt="License: MIT">
  </a>
</p>

<p align="center">
  <code>pip install agentfiles</code>
</p>

---

`agentfiles` is a CLI that keeps your AI coding assistant configurations — agents, skills, commands, and plugins — consistent across multiple platforms. It treats a source repository as the single source of truth and propagates changes to wherever you need them.

## Why?

You use multiple AI coding tools. Each stores its config in a different place:

```
~/.config/opencode/       # OpenCode
~/.claude/                # Claude Code
~/.codeium/windsurf/      # Windsurf
~/.cursor/rules/          # Cursor
.github/copilot/          # GitHub Copilot
.aider/                   # Aider
.continue/                # Continue.dev
```

`agentfiles` lets you maintain **one repository** and sync everywhere:

```
                    ┌─── OpenCode
                    ├─── Claude Code
source repo ────────┼─── Windsurf
(agentfiles pull)   ├─── Cursor
                    ├─── GitHub Copilot
                    ├─── Aider
                    └─── Continue.dev
```

## Features

- **7 platforms** — OpenCode, Claude Code, Windsurf, Cursor + GitHub Copilot, Aider, Continue.dev
- **6 item types** — agents, skills, commands, plugins, configs, workflows
- **Bidirectional sync** — pull and push with conflict detection
- **Surgical filtering** — `--only`, `--except`, `--type`, `--target`, `--item agent/coder`
- **Platform groups** — define profiles in config (`dev: [claude_code, cursor]`), use with `--target dev`
- **PR creation** — `push --create-pr` to auto-create a pull request via `gh`
- **Smart cloning** — shallow clone + sparse checkout for remote sources
- **Dry-run** — preview changes without applying
- **Diagnostics** — `doctor`, `verify` (CI drift detection), shell completions
- **One dependency** — `pyyaml` only

## Quick Start

```bash
pip install agentfiles
```

```bash
# Initialize a new repository
agentfiles init

# Pull to all platforms
agentfiles pull /path/to/source-repo

# Pull only agents to OpenCode
agentfiles pull --target opencode --type agent

# Preview without applying
agentfiles pull --dry-run
```

## Commands

| Command | Description |
|---------|-------------|
| [`pull`](#pull) | Install/update items from source to local configs |
| [`push`](#push) | Push local items back to source (with conflict detection) |
| [`status`](#status) | Show installed items per platform (`--list`, `--diff`) |
| [`clean`](#clean) | Remove orphaned items |
| [`init`](#init) | Scaffold a new repository |
| [`verify`](#verify) | CI-friendly drift detection (exit 1 if drift) |
| [`doctor`](#doctor) | Run environment diagnostics |
| [`completion`](#completion) | Generate shell completion scripts |

### `pull`

Install or update items from a source repository to local platform configs.

```bash
agentfiles pull                                    # interactive (default)
agentfiles pull --yes                              # non-interactive
agentfiles pull --update                           # git pull source, then sync
agentfiles pull --target opencode --type agent     # only agents → OpenCode
agentfiles pull --only coder,solid-principles      # specific items
agentfiles pull --item agent/coder                 # single item by key
agentfiles pull --dry-run --verbose                # preview with details
agentfiles pull --symlinks                         # use symlinks instead of copies
agentfiles pull --full-clone                       # disable shallow clone optimization
```

### `push`

Push locally-installed items back into the source repository. Useful when you've edited configs on one machine and want to propagate.

```bash
agentfiles push                         # interactive (with conflict detection)
agentfiles push --yes                   # non-interactive (skips conflicts)
agentfiles push --dry-run               # preview
agentfiles push --target opencode       # push only from OpenCode
agentfiles push --item agent/coder      # push a single item
agentfiles push --create-pr             # auto-create PR via gh
agentfiles push --create-pr --pr-title "Update agents" --pr-branch my-branch
```

### `status`

Show installed-item counts per discovered platform. Supports two sub-modes via flags:

- `--list` — list items available in the source repository
- `--diff` — compare source vs installed items

```bash
agentfiles status                            # show platforms
agentfiles status --format json              # JSON output

# --list mode: list source items
agentfiles status --list                     # text table
agentfiles status --list --tokens            # include token estimates
agentfiles status --list --format json       # machine-readable

# --diff mode: compare source vs installed
agentfiles status --diff                     # show differences
agentfiles status --diff --verbose           # content-level diffs
agentfiles status --diff --target opencode   # diff for one platform
agentfiles status --diff --format json       # machine-readable
```

### `clean`

Remove installed items whose source no longer exists in the repository.

```bash
agentfiles clean --dry-run      # preview
agentfiles clean --yes          # non-interactive
```

### `init`

Scaffold a new agentfiles repository with `agents/`, `skills/`, `commands/`, `plugins/` directories and a `.agentfiles.yaml` config.

```bash
agentfiles init                              # current directory
agentfiles init /path/to/project             # specific directory
agentfiles init --yes                        # skip confirmation
```

### `verify`

CI-friendly drift detection. Compares source vs installed items, exits 0 if in sync, 1 if drift detected.

```bash
agentfiles verify                    # human-readable output
agentfiles verify --format json      # machine-readable
agentfiles verify --quiet            # silent, exit code only
```

### `doctor`

Run environment diagnostics — checks config, source dir, git, platform directories, state file, and tool binaries.

```bash
agentfiles doctor
```

### `completion`

Generate shell completion scripts.

```bash
agentfiles completion bash    # bash completions
agentfiles completion zsh     # zsh completions
agentfiles completion fish    # fish completions

# Example: add to .bashrc
eval "$(agentfiles completion bash)"
```

## Global Options

```
--color {always,auto,never}   Color output control (respects NO_COLOR/FORCE_COLOR)
--verbose, -v                 Verbose output
--quiet, -q                   Quiet mode (errors only)
--version                     Show version
```

## Filter Options

Most commands support surgical filtering:

```bash
--target {platform,group,all}                          Target platform or group name
--type {agent,skill,command,plugin,config,workflow,all} Item type
--only coder,solid-principles                          Only these items (by name)
--except old-plugin,deprecated                         Exclude these items
--item agent/coder                                     Specific item by type/name key
```

## Source Repository Structure

```
my-agents/
├── agents/
│   ├── coder/
│   │   └── coder.md              # YAML frontmatter + prompt
│   └── debugger/
│       └── debugger.md
├── skills/
│   ├── solid-principles/
│   │   ├── SKILL.md
│   │   └── references/
│   └── dry-principle/
│       └── SKILL.md
├── commands/
│   └── autopilot/
│       └── autopilot.md
├── plugins/
│   └── patterns.yaml
├── configs/
│   └── global-settings.yaml
├── workflows/
│   └── deploy-pipeline/
│       └── workflow.md
└── .agentfiles.yaml              # Config (auto-generated)
```

## Supported Platforms

| Platform | Config path | Agents | Skills | Commands | Plugins | Configs | Workflows |
|----------|------------|--------|--------|----------|---------|---------|-----------|
| **OpenCode** | `~/.config/opencode/` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **Claude Code** | `~/.claude/` | ✅ | ✅ | ✅ | — | ✅ | ✅ |
| **Windsurf** | `~/.codeium/windsurf/` | — | ✅ | — | — | — | ✅ |
| **Cursor** | `~/.cursor/rules/` | — | ✅ | — | — | — | ✅ |
| **GitHub Copilot** | `.github/copilot/` | ✅ | — | — | — | ✅ | — |
| **Aider** | `.aider/` | ✅ | — | — | — | ✅ | — |
| **Continue.dev** | `.continue/` | ✅ | — | ✅ | — | ✅ | — |

## Platform Groups

Define named groups in `.agentfiles.yaml` to avoid repeating `--target` flags:

```yaml
source: ./
platform_groups:
  dev: [claude_code, cursor]
  ci: [opencode]
  editors: [copilot, aider, continue]
```

```bash
agentfiles pull --target dev       # → claude_code + cursor
agentfiles push --target editors   # → copilot + aider + continue
```

## Architecture

```
┌─────────────────┐    ┌──────────────┐    ┌──────────────┐
│ Source Resolution│───▶│    Scanner    │───▶│    Differ    │
│   (source.py)   │    │ (scanner.py) │    │ (differ.py)  │
└─────────────────┘    └──────────────┘    └──────────────┘
                                                    │
                                                    ▼
                                             ┌──────────────┐
┌──────────────┐    ┌──────────────┐         │    Engine    │
│  SyncReport  │◀──│ SyncResult[] │◀────────│ (engine.py)  │
│              │    │              │         │ plan→execute │
└──────────────┘    └──────────────┘         └──────────────┘
```

| Module | Purpose |
|--------|---------|
| `source.py` | Resolve user input → local directory (local dir, git URL, git clone) |
| `scanner.py` | Walk source dirs → `list[Item]` |
| `differ.py` | Compare source vs installed: existence → metadata → SHA-256 |
| `engine.py` | Plan actions (INSTALL/UPDATE/SKIP) → execute → collect results |
| `target.py` | Discover platforms, manage installed items |
| `config.py` | YAML config + sync-state persistence |
| `cli.py` | Argparse CLI with all subcommands |

### Extending

**Add a new platform:**

1. Add `Platform` enum value in `models.py`
2. Add discovery logic in `target.py` (`_DISCOVERY_TABLE`)
3. Add alias in `PLATFORM_ALIASES`

**Add a new item type:**

1. Add `ItemType` enum value in `models.py`
2. Write a scanner function in `scanner.py`
3. Register via `_register_scanner()`

No other modules need changes (Open/Closed Principle).

## Development

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Lint & format
ruff check src/ tests/
ruff format --check src/ tests/

# Type check
mypy src/

# Test
pytest tests/ -v

# Test with coverage
pytest tests/ -v --cov=agentfiles --cov-report=term-missing

# Build package
python -m build
```

## License

[MIT](LICENSE)
