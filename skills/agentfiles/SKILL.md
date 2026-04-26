---
name: agentfiles
description: >
  CLI tool that syncs AI coding assistant configurations (agents, skills, commands,
  plugins, configs, workflows) between a source repository and a local OpenCode
  installation. Use when: (1) pulling/pushing agents, skills, commands, plugins,
  configs, or workflows between a source repo and OpenCode, (2) running CI drift
  detection with `agentfiles verify`, (3) creating a new agentfiles repository with
  `agentfiles init`, (4) managing scopes (global, project, local) for item
  installation, (5) checking installed-item status or comparing source vs installed,
  (6) removing orphaned items, (7) diagnosing environment issues, (8) working with
  YAML frontmatter in agent or skill definition files, (9) token estimation for
  context window budgeting, (10) any mention of "agentfiles", "opencode config",
  "sync agents", "sync skills", "sync commands", "sync plugins", "opencode
  configuration management".
---

# agentfiles

Sync AI tool configurations between a source repository and OpenCode. The source repo
is the single source of truth.

## Quick Start

```bash
agentfiles init                   # scaffold a new source repository
agentfiles pull                   # install/update all items interactively
agentfiles pull --yes             # non-interactive pull (for CI/scripts)
agentfiles pull --dry-run         # preview changes without applying
agentfiles verify                 # CI drift detection (exit 0=clean, 1=drift)
```

## Commands

| Command | Description |
|---------|-------------|
| `pull [source]` | Install/update items from source to OpenCode |
| `push [source]` | Push locally-installed items back to source repo |
| `status` | Show installed-item counts per platform |
| `status --list` | List source items |
| `status --list --tokens` | List items with token cost estimates |
| `status --diff` | Compare source vs installed items |
| `clean` | Remove orphaned items (installed but deleted from source) |
| `init [path]` | Scaffold a new repository with standard layout |
| `doctor` | Run environment diagnostics |
| `verify` | CI drift detection (exit 0=no drift, 1=drift) |
| `completion {bash,zsh,fish}` | Print shell completion script |

### Global flags

Apply to all commands: `--color {always,auto,never}`, `-v`/`--verbose`, `-q`/`--quiet`.

### Common flags (pull, push, clean, verify)

**Source options:**

| Flag | Description |
|------|-------------|
| `[source]` | URL, git repo, or local directory (auto-detected) |
| `--config PATH` | Path to config file |
| `--cache-dir DIR` | Cache directory for git clones |
| `--project-dir DIR` | Project directory for project/local scope (default: CWD) |

**Filter options:**

| Flag | Description |
|------|-------------|
| `--type {agent,skill,command,plugin,config,workflow,all}` | Filter by item type |
| `--scope {global,project,local,all}` | Filter by installation scope |
| `--only ITEMS` | Only include named items (comma-separated) |
| `--except ITEMS` | Exclude named items (comma-separated) |
| `--item KEY` | Select by type/name key, e.g. `agent/coder` (repeatable) |

**Output / sync options:**

| Flag | Description |
|------|-------------|
| `--dry-run`, `-n` | Preview without applying |
| `--format {text,json}` | Output format |
| `--yes`, `-y` | Non-interactive mode (skip prompts) |

### Pull-specific flags

| Flag | Description |
|------|-------------|
| `--symlinks` | Use symlinks instead of copying |
| `--update`, `-u` | Run `git pull` on source before syncing |
| `--full-clone` | Disable shallow clone optimization |

### Push-specific flags

| Flag | Description |
|------|-------------|
| `--create-pr` | Create a GitHub PR after push (requires `gh` CLI) |
| `--pr-title TITLE` | Custom PR title |
| `--pr-branch BRANCH` | Custom branch name |

### Status-specific flags

| Flag | Description |
|------|-------------|
| `--list` | List source items instead of platform summary |
| `--tokens` | Show token estimates (with `--list`) |
| `--diff` | Compare source vs installed |
| `--verbose` | Show content-level diffs (with `--diff`) |

### Examples

```bash
# Pull only agents
agentfiles pull --type agent

# Pull specific items
agentfiles pull --only coder,python-reviewer

# Pull only global-scope items
agentfiles pull --scope global

# Pull project items to a specific directory
agentfiles pull --scope project --project-dir /path/to/project

# Git pull source, then sync
agentfiles pull --update

# Push and open a PR
agentfiles push --yes --create-pr --pr-title "Add new agents"

# List items with token counts
agentfiles status --list --tokens

# List only project-scope items
agentfiles status --list --scope project

# Compare source vs installed with content diffs
agentfiles status --diff --verbose

# Check for drift in CI (JSON output)
agentfiles verify --format json
agentfiles verify --quiet    # exit code only
```

## Item Types

| Type | Directory | Storage | Extensions | Main File |
|------|-----------|---------|------------|-----------|
| Agent | `agents/` | File or dir | `.md` | `<name>.md` |
| Skill | `skills/` | Directory only | `.md` | `SKILL.md` |
| Command | `commands/` | File or dir | `.md` | `<name>.md` |
| Plugin | `plugins/` | File or dir | `.ts` `.yaml` `.yml` `.py` `.js` | Any recognized |
| Config | `configs/` | File only | `.json` | N/A |
| Workflow | `workflows/` | Directory only | `.md` | Any `.md` |

File-based items (agent, command, plugin, config) retain their filename on install.
Directory-based items (skill, workflow) are installed by directory name only.
A flat file at `agents/coder.md` takes priority over `agents/coder/coder.md`.

## Frontmatter

All markdown-based items support YAML frontmatter between `---` delimiters.
Minimum required fields: `name` and `description`.

### Standard fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `name` | string | Filename stem | Unique identifier |
| `description` | string | `""` | Short summary |
| `version` | string | `"1.0.0"` | Semantic version |
| `priority` | string | `null` | e.g. `"critical"`, `"normal"` |
| `tools` | mapping | `{}` | Tool name to boolean mapping |

### Agent-specific fields

| Field | Type | Description |
|-------|------|-------------|
| `color` | string | UI display color (hex) |
| `permissionMode` | string | Tool permission mode |
| `model` | string | Model identifier |
| `temperature` | number | Model temperature |
Extra keys are preserved for forward compatibility.

### Example

```yaml
---
name: coder
description: "Writing and refactoring high-quality production code"
version: "1.0.0"
priority: "critical"
tools:
  Read: true
  Write: true
  Edit: true
  Bash: true
---

# Agent instructions follow here...
```

## Scopes

| Scope | Target | Use Case |
|-------|--------|----------|
| **global** | `~/.config/opencode/` | Shared across all projects (default) |
| **project** | `.opencode/` in project root | Committed to VCS, shared with team |
| **local** | `.opencode/` in project root | Personal overrides, git-ignored |

Scope is determined by directory structure within the source repo:

```
agents/
├── coder.md                    # global (default)
├── global/
│   └── reviewer.md             # explicit global
├── project/
│   └── team-agent.md           # project scope
└── local/
    └── my-tweaks.md            # local scope
```

Filter with `--scope {global,project,local,all}`. For project scope, use
`--project-dir /path/to/project` to specify the target.

## Source Repository Layout

```
my-configs/
├── agents/
│   ├── coder.md
│   └── code-reviewer/
│       └── code-reviewer.md
├── skills/
│   └── solid-principles/
│       ├── SKILL.md
│       └── references/
│           └── examples.md
├── commands/
│   └── autopilot.md
├── plugins/
│   └── patterns.yaml
├── configs/
│   └── opencode.json
├── workflows/
│   └── deploy-pipeline/
│       └── deploy-pipeline.md
├── .agentfiles.yaml            # optional config
└── .agentfiles.state.yaml      # auto-managed sync state
```
Run `agentfiles doctor` to verify the environment.
Run `agentfiles verify` in CI to detect drift between source and installed items.
