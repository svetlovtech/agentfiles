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
~/.config/opencode/    # OpenCode
~/.claude/             # Claude Code
~/.codeium/windsurf/   # Windsurf
~/.cursor/rules/       # Cursor
```

`agentfiles` lets you maintain **one repository** and sync everywhere:

```
                    ┌─── OpenCode
                    │
source repo ────────┼─── Claude Code
(agentfiles pull)   │
                    ├─── Windsurf
                    │
                    └─── Cursor
```

## Features

- **4 platforms** — OpenCode, Claude Code, Windsurf, Cursor
- **4 item types** — agents, skills, commands, plugins
- **Bidirectional sync** — pull, push, or smart 3-way merge
- **CI-friendly** — `agentfiles verify` exits 0/1 for drift detection
- **Surgical filtering** — `--only`, `--except`, `--type`, `--target`
- **Dry-run** — preview changes without applying
- **Shell completion** — bash, zsh, fish
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
| [`push`](#push) | Push local items back to source |
| [`adopt`](#adopt) | Adopt items from platforms into source |
| [`sync`](#sync) | Bidirectional 3-way merge |
| [`status`](#status) | Show installed items per platform |
| [`list`](#list) | List source items (`--tokens` for costs) |
| [`diff`](#diff) | Compare source vs installed |
| [`verify`](#verify) | CI drift detection (exit 0/1) |
| [`clean`](#clean) | Remove orphaned items |
| [`uninstall`](#uninstall) | Remove installed items |
| [`init`](#init) | Scaffold a new repository |
| [`update`](#update) | Git pull + sync in one step |
| [`branch`](#branch) | Show or switch git branches |
| [`show`](#show) | Preview an item's content |
| [`doctor`](#doctor) | Diagnose environment issues |
| [`completion`](#completion) | Generate shell completions |

### `pull`

Install or update items from a source repository to local platform configs.

```bash
agentfiles pull                                    # interactive (default)
agentfiles pull --yes                              # non-interactive
agentfiles pull --target opencode --type agent     # only agents → OpenCode
agentfiles pull --only coder,solid-principles      # specific items
agentfiles pull --dry-run --verbose                # preview with details
agentfiles pull --symlinks                         # use symlinks instead of copies
```

### `push`

Push locally-installed items back into the source repository. Useful when you've edited configs on one machine and want to propagate.

```bash
agentfiles push                # interactive
agentfiles push --yes          # non-interactive
```

### `adopt`

Adopt items that already exist on your local platforms into the source repository. Great for bootstrapping a new source repo from existing configs.

```bash
agentfiles adopt --yes
```

### `sync`

Smart bidirectional sync using checksums stored in `.agentfiles.state.yaml`. Detects whether each item needs a pull, push, or manual conflict resolution.

```bash
agentfiles sync
```

### `verify`

CI-friendly drift detection. Exit 0 if all items match, 1 if drift detected.

```bash
agentfiles verify                  # text output
agentfiles verify --format json    # machine-readable
agentfiles verify --quiet          # errors only
```

Example CI step:

```yaml
- name: Check config drift
  run: agentfiles verify
```

### `status`

Show installed-item counts per discovered platform.

```bash
agentfiles status
agentfiles status --format json
```

### `list`

List items available in the source repository.

```bash
agentfiles list                # text table
agentfiles list --tokens       # include token estimates
agentfiles list --format json  # machine-readable
```

### `diff`

Show differences between source items and installed counterparts.

```bash
agentfiles diff
agentfiles diff --target opencode
agentfiles diff --format json
```

### `show`

Preview the content of a specific item. Supports partial name matching.

```bash
agentfiles show coder
agentfiles show solid-principles --format json
```

### `update`

Git pull + sync in one step. The primary multi-machine workflow.

```bash
agentfiles update
```

### `clean`

Remove installed items whose source no longer exists in the repository.

```bash
agentfiles clean --dry-run      # preview
agentfiles clean --yes          # non-interactive
```

### `uninstall`

Remove installed items from target platforms.

```bash
agentfiles uninstall --yes
```

### `init`

Scaffold a new agentfiles repository with `agents/`, `skills/`, `commands/`, `plugins/` directories and a `.agentfiles.yaml` config.

```bash
agentfiles init
```

### `branch`

List or switch git branches in the source repository.

```bash
agentfiles branch              # list branches
agentfiles branch feature-x    # switch branch
```

### `doctor`

Diagnose common environment and configuration problems.

```bash
agentfiles doctor
```

### `completion`

Generate shell completion scripts.

```bash
agentfiles completion bash   > ~/.local/share/bash-completion/completions/agentfiles
agentfiles completion zsh    > ~/.zfunc/_agentfiles
agentfiles completion fish   > ~/.config/fish/completions/agentfiles.fish
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
--target {opencode,claude_code,windsurf,cursor,all}   Target platform
--type {agent,skill,command,plugin,all}                Item type
--only coder,solid-principles                          Only these items
--except old-plugin,deprecated                         Exclude these items
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
└── .agentfiles.yaml              # Config (auto-generated)
```

## Supported Platforms

| Platform | Config path | Agents | Skills | Commands | Plugins |
|----------|------------|--------|--------|----------|---------|
| **OpenCode** | `~/.config/opencode/` | ✅ | ✅ | ✅ | ✅ |
| **Claude Code** | `~/.claude/` | ✅ | ✅ | ✅ | — |
| **Windsurf** | `~/.codeium/windsurf/` | — | ✅ | — | — |
| **Cursor** | `~/.cursor/rules/` | — | ✅ | — | — |

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
pytest tests/ -v --cov=syncode --cov-report=term-missing

# Build package
python -m build
```

## License

[MIT](LICENSE)
