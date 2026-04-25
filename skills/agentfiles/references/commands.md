# Command Reference

Complete reference for all `agentfiles` CLI commands and their flags.

## Global Options

```
--color {always,auto,never}   Color output (respects NO_COLOR/FORCE_COLOR)
--verbose, -v                 Verbose output
--quiet, -q                   Quiet mode (errors only)
--version                     Show version
--config PATH                 Path to config file
--cache-dir PATH              Cache directory for git clones
```

## pull

Install/update items from source to local platform configs.

```bash
agentfiles pull [SOURCE] [OPTIONS]
```

| Flag | Description |
|------|-------------|
| `--yes` | Non-interactive (skip all prompts) |
| `--target` | Platform filter (opencode, claude_code, windsurf, cursor, all) |
| `--type` | Item type filter (agent, skill, command, plugin, all) |
| `--only` | Comma-separated item names to include |
| `--except` | Comma-separated item names to exclude |
| `--dry-run` | Preview without applying |
| `--symlinks` | Use symlinks instead of copies |
| `--verbose` | Show detailed diff info |
| `--format` | Output format: text (default) or json |

**Interactive modes** (default, when `--yes` is not passed):
- `full` — sync all items
- `install` — only new (not yet installed) items
- `update` — only already-installed items that changed
- `custom` — select platforms, types, and items interactively

## push

Push locally-installed items back to source repository.

```bash
agentfiles push [SOURCE] [OPTIONS]
```

| Flag | Description |
|------|-------------|
| `--yes` | Non-interactive |
| `--target` | Platform filter |
| `--type` | Item type filter |
| `--only` | Specific items |
| `--except` | Exclude items |
| `--dry-run` | Preview only |
| `--format` | text or json |

## adopt

Adopt items from platforms into source (for bootstrapping a new repo).

```bash
agentfiles adopt [SOURCE] [OPTIONS]
```

| Flag | Description |
|------|-------------|
| `--yes` | Non-interactive |
| `--target` | Platform filter |
| `--type` | Item type filter |
| `--dry-run` | Preview only |

## sync

Bidirectional 3-way merge using `.agentfiles.state.yaml`.

```bash
agentfiles sync [SOURCE] [OPTIONS]
```

Uses checksums to detect:
- **pull** — source changed, target unchanged
- **push** — target changed, source unchanged
- **conflict** — both changed (requires manual resolution)
- **skip** — neither changed

| Flag | Description |
|------|-------------|
| `--yes` | Non-interactive |
| `--target` | Platform filter |
| `--type` | Item type filter |
| `--dry-run` | Preview only |
| `--skip-conflicts` | Suppress conflict warnings |
| `--format` | text or json |

## verify

CI drift detection. Exit 0 if clean, 1 if drift detected.

```bash
agentfiles verify [SOURCE] [OPTIONS]
```

| Flag | Description |
|------|-------------|
| `--target` | Platform filter |
| `--type` | Item type filter |
| `--format` | text or json |
| `--quiet` | Errors only (exit code only) |

JSON output structure:
```json
{
  "total": 42,
  "matching": 40,
  "drift": 1,
  "missing": 1,
  "items": [...]
}
```

## status

Show installed-item counts per platform.

```bash
agentfiles status [OPTIONS]
```

| Flag | Description |
|------|-------------|
| `--format` | text or json |

## list

List items in source repository.

```bash
agentfiles list [SOURCE] [OPTIONS]
```

| Flag | Description |
|------|-------------|
| `--type` | Item type filter |
| `--tokens` | Include token estimates |
| `--format` | text or json |
| `--only` | Specific items |
| `--except` | Exclude items |

## diff

Compare source vs installed items.

```bash
agentfiles diff [SOURCE] [OPTIONS]
```

| Flag | Description |
|------|-------------|
| `--target` | Platform filter |
| `--type` | Item type filter |
| `--format` | text or json |
| `--verbose-diff` | Show unified content diff for UPDATED items |

Diff statuses: `NEW`, `UPDATED`, `DELETED`, `UNCHANGED`, `CONFLICT`.

## show

Preview an item's content. Supports partial name matching.

```bash
agentfiles show <NAME> [OPTIONS]
```

| Flag | Description |
|------|-------------|
| `--format` | text or json |

## update

Git pull + sync in one step. Primary multi-machine workflow.

```bash
agentfiles update [OPTIONS]
```

## clean

Remove orphaned items (installed but source no longer exists).

```bash
agentfiles clean [SOURCE] [OPTIONS]
```

| Flag | Description |
|------|-------------|
| `--yes` | Non-interactive |
| `--dry-run` | Preview only |
| `--target` | Platform filter |
| `--type` | Item type filter |

## uninstall

Remove all installed items from target platforms.

```bash
agentfiles uninstall [OPTIONS]
```

| Flag | Description |
|------|-------------|
| `--yes` | Non-interactive |
| `--force` | Skip confirmation |
| `--dry-run` | Preview only |
| `--target` | Platform filter |
| `--only` | Specific items |
| `--except` | Exclude items |

## init

Scaffold a new agentfiles repository.

```bash
agentfiles init [OPTIONS]
```

Creates `agents/`, `skills/`, `commands/`, `plugins/` directories with `.gitkeep` files
and a `.agentfiles.yaml` config.

## branch

List or switch git branches in source repository.

```bash
agentfiles branch              # list
agentfiles branch feature-x    # switch
```

## doctor

Diagnose environment and configuration issues.

```bash
agentfiles doctor
```

## completion

Generate shell completion scripts.

```bash
agentfiles completion bash   > ~/.local/share/bash-completion/completions/agentfiles
agentfiles completion zsh    > ~/.zfunc/_agentfiles
agentfiles completion fish   > ~/.config/fish/completions/agentfiles.fish
```
