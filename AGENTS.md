# OpenCode Configuration Catalog

This document describes the types of configuration items managed by [agentfiles](https://github.com/svetlovtech/agentfiles) -- a CLI tool that syncs AI coding assistant configurations from a source repository to a local OpenCode installation.

agentfiles manages six categories of items: **agents**, **skills**, **commands**, **plugins**, **configs**, and **workflows**. Each type has a defined directory layout, frontmatter schema, and sync behavior.

---

## Table of Contents

- [Agents](#agents)
- [Skills](#skills)
- [Commands](#commands)
- [Plugins](#plugins)
- [Configs](#configs)
- [Workflows](#workflows)
- [Scopes](#scopes)
- [Frontmatter Reference](#frontmatter-reference)
- [Sync Behavior](#sync-behavior)
- [Releasing & Deployment](#releasing--deployment)
- [How to Contribute](#how-to-contribute)

---

## Agents

Agents are AI persona definitions that include a system prompt, tool permissions, and behavioral instructions. They define how the AI assistant behaves for a particular task or role.

### What it is

An agent specifies a role (e.g., coder, reviewer, debugger) with instructions on how to approach its work, which tools it can use, and what constraints it follows.

### Directory structure

Agents can be defined as either a flat markdown file or a subdirectory containing a markdown file:

```
agents/
├── coder.md                        # Flat file agent
├── debugger.md                     # Flat file agent
└── code-reviewer/                  # Directory-based agent
    └── code-reviewer.md            # Must match directory name
```

Flat files take priority over directories with the same stem.

### Example frontmatter

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
```

### How agentfiles handles it

- **Pull**: Copies the agent file or directory to `~/.config/opencode/agents/`
- **Push**: Copies local agents back to the source repository
- **Diff**: Compares source vs installed by existence, metadata, then SHA-256 content hash
- **Storage**: File-based -- retains the source filename (including `.md` extension)

---

## Skills

Skills are domain-specific knowledge bases that provide the AI assistant with specialized expertise. Unlike agents, skills are reference material rather than behavioral instructions.

### What it is

A skill is a self-contained knowledge module (e.g., SOLID principles, TDD methodology, security best practices) that can be loaded into an agent's context. Skills can include supplementary reference files alongside their main content.

### Directory structure

Skills are **directory-only** items. Each directory must contain a `SKILL.md` file:

```
skills/
├── code-solid-principles/
│   ├── SKILL.md                    # Required main file
│   └── references/                 # Optional supporting files
│       └── examples.md
├── code-tdd-principle/
│   └── SKILL.md
└── python-code-reviewer/
    ├── SKILL.md
    └── references/
```

### Example frontmatter

```yaml
---
name: code-solid-principles
description: "Essential object-oriented design principles"
version: "1.0.0"
---
```

### How agentfiles handles it

- **Pull**: Copies the entire skill directory to `~/.config/opencode/skills/<name>/`
- **Push**: Copies local skill directories back to the source repository
- **Diff**: Compares all files within the skill directory
- **Storage**: Directory-based -- installed by name only (no file extension)

---

## Commands

Commands are custom slash-command definitions that extend the AI assistant with reusable prompt templates or workflow triggers.

### What it is

A command provides a named, reusable prompt or instruction that can be invoked via a slash command in the AI assistant interface (e.g., `/autopilot`, `/deploy`).

### Directory structure

Commands follow the same layout as agents -- flat files or subdirectories:

```
commands/
├── autopilot.md                    # Flat file command
└── deploy/                         # Directory-based command
    └── deploy.md
```

### Example frontmatter

```yaml
---
name: autopilot
description: "Run an autonomous coding session"
version: "1.0.0"
---
```

### How agentfiles handles it

- **Pull**: Copies to `~/.config/opencode/commands/`
- **Push**: Copies local commands back to the source repository
- **Diff**: Compares source vs installed by metadata and content hash
- **Storage**: File-based -- retains the source filename

---

## Plugins

Plugins are tool integrations that extend the AI assistant with external capabilities (MCP servers, security filters, memory systems, etc.).

### What it is

A plugin defines how the AI assistant connects to external tools and services. Plugins can be single configuration files (YAML, TypeScript, Python, JavaScript) or directories containing multiple related files.

### Directory structure

Plugins support flexible organization:

```
plugins/
├── patterns.yaml                   # Flat plugin file
├── security-output-filter/         # Directory-based plugin
│   └── filter.ts
└── opencode/                       # Platform-specific subdirectory
    ├── memory-remember.ts
    └── tool-confirm.ts
```

Recognized file extensions: `.ts`, `.yaml`, `.yml`, `.py`, `.js`

### Example frontmatter

```yaml
---
name: security-output-filter
description: "Filters sensitive data from AI outputs"
version: "1.0.0"
---
```

### How agentfiles handles it

- **Pull**: Copies plugin files/directories to `~/.config/opencode/plugins/`
- **Push**: Copies local plugins back to the source repository
- **Diff**: Compares all files within the plugin
- **Storage**: Can be file-based or directory-based depending on the source structure

---

## Configs

Configs are platform-level configuration files (e.g., `opencode.json`) that control global settings such as model selection, MCP server connections, and provider configuration.

### What it is

A config item is a JSON settings file that defines how the AI assistant platform itself is configured -- which models to use, which MCP servers to connect to, and other global preferences.

### Directory structure

```
configs/
└── opencode.json                   # Platform configuration file
```

Configs are flat `.json` files in the `configs/` directory.

### How agentfiles handles it

- **Pull**: Copies to the platform config root
- **Push**: Copies local config back to the source repository
- **Diff**: Compares by content hash
- **Storage**: File-based

---

## Workflows

Workflows are multi-step automation recipes that orchestrate agents, skills, and tools into coordinated pipelines.

### What it is

A workflow defines a sequence of steps or a reusable pipeline that coordinates multiple agents and skills to accomplish complex tasks (e.g., a full deployment pipeline, a code review cycle).

### Directory structure

Workflows are **directory-only** items, similar to skills:

```
workflows/
└── deploy-pipeline/
    └── deploy-pipeline.md          # Or any .md file
```

### How agentfiles handles it

- **Pull**: Copies the entire workflow directory to `~/.config/opencode/workflows/`
- **Push**: Copies local workflows back to the source repository
- **Diff**: Compares all files within the workflow directory
- **Storage**: Directory-based -- installed by name only

---

## Scopes

Every item has a scope that determines where it is installed:

| Scope | Target Location | Use Case |
|-------|----------------|----------|
| **Global** | `~/.config/opencode/` | Shared across all projects (default) |
| **Project** | `.opencode/` in project root | Committed to VCS, shared with team |
| **Local** | `.opencode/` in project root | Personal overrides, git-ignored |

### Scope-based directory layout

Items can be organized by scope within their type directory:

```
agents/
├── coder.md               # Global scope (default)
├── global/
│   └── reviewer.md        # Explicit global scope
├── project/
│   └── team-agent.md      # Project scope
└── local/
    └── my-tweaks.md       # Local scope
```

---

## Frontmatter Reference

All markdown-based items support YAML frontmatter between `---` delimiters at the top of the file.

### Standard fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `name` | string | Filename stem | Unique identifier for the item |
| `description` | string | `""` | Short summary of what the item does |
| `version` | string | `"1.0.0"` | Semantic version string |
| `priority` | string | `null` | Priority level (e.g., `"critical"`, `"normal"`) |
| `tools` | mapping | `{}` | Tool name to enabled/disabled boolean mapping |

### Additional fields

Agent definitions commonly include additional fields beyond the standard set:

| Field | Type | Description |
|-------|------|-------------|
| `color` | string | UI display color (hex) |
| `permissionMode` | string | Tool permission mode |
| `model` | string | Model identifier to use |
| `temperature` | number | Model temperature setting |

Any unrecognized keys are preserved in an `extra` dictionary for forward compatibility.

### Example

```yaml
---
name: my-agent
description: "A custom agent for specific tasks"
version: "2.1.0"
priority: "normal"
tools:
  Read: true
  Write: false
  Bash: true
  Edit: true
custom_field: "any value"
---

# Agent instructions follow here...
```

---

## Sync Behavior

agentfiles provides bidirectional sync between a source repository and the local OpenCode configuration.

### Pull (source to local)

```
agentfiles pull /path/to/source-repo
```

1. **Scan** the source directory for all item types
2. **Diff** source items against currently installed items
3. **Plan** actions: INSTALL (new), UPDATE (changed), SKIP (unchanged)
4. **Execute**: copy files/directories to the OpenCode config directory

### Push (local to source)

```
agentfiles push
```

1. **Scan** local OpenCode configuration for installed items
2. **Diff** local items against source repository
3. **Detect conflicts** when both sides have changed
4. **Plan** actions and execute with conflict resolution

### State tracking

Sync state is persisted in `.agentfiles.state.yaml` at the repository root, tracking the last sync timestamp and per-item sync history.

### Filtering

All sync operations support surgical filtering:

```bash
--type agent          # Only agents
--only coder,reviewer # Specific items by name
--except deprecated   # Exclude items
--item agent/coder    # Single item by type/name key
--scope global        # Only global-scope items
```

---

## Releasing & Deployment

### Version Management

- Version is defined in `pyproject.toml` under `[project]` → `version`
- Uses semantic versioning (MAJOR.MINOR.PATCH)
- **Always bump version when making changes** to the project

### Release Process

1. Update `version` in `pyproject.toml`
2. Commit with a descriptive message
3. Push to `main`
4. Create a GitHub Release with tag `v<version>` (e.g., `v0.5.0`)
5. The `publish.yml` workflow triggers automatically on release publication

### CI Pipeline

The CI pipeline runs on every push and pull request (defined in `.github/workflows/ci.yml`):

- **Lint**: ruff check + ruff format (parallel job)
- **Type check**: mypy strict (parallel job)
- **Security**: bandit (parallel job)
- **Tests**: pytest on Python 3.10, 3.11, 3.12, 3.13 (parallel job)
- **Gate**: all jobs must pass

### PyPI Publishing

- Uses Trusted Publishing (OIDC) — no API tokens needed
- Triggered automatically when a GitHub Release is published
- Requires one-time setup: register the package on PyPI as a GitHub publisher
- Environment: `pypi` in GitHub

---

## How to Contribute

### Adding a new item

1. Create the item in the appropriate directory (`agents/`, `skills/`, `commands/`, `plugins/`, `configs/`, or `workflows/`)
2. Include YAML frontmatter with at least a `name` and `description`
3. Run `agentfiles pull --dry-run` to verify the item is discovered
4. Submit a pull request

### Adding a new item type

The scanner follows the Open/Closed Principle. To add a new item type:

1. Add an `ItemType` enum value in `models.py`
2. Write a scanner function in `scanner.py`
3. Register via `_register_scanner()`

No other modules need changes.

### Guidelines

- Keep agent prompts focused on a single responsibility
- Skills should be self-contained with all necessary reference material
- Use semantic versioning in frontmatter
- Include a `description` field for discoverability
- Test with `agentfiles doctor` and `agentfiles verify` before submitting
- **Always bump the version in `pyproject.toml`** when making any changes to the project. Even small fixes should get a patch bump. This ensures every change is traceable and deployable.
