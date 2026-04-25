# Architecture

Internal architecture of the `agentfiles` tool and extension points.

## Pipeline Overview

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

## Module Responsibilities

| Module | Purpose |
|--------|---------|
| `cli.py` | Argparse CLI, command handlers, interactive sessions |
| `source.py` | Detect source type (local/git URL), resolve to local path, clone/update |
| `scanner.py` | Walk source dirs, discover items, parse frontmatter |
| `differ.py` | Compare source vs installed items by checksum |
| `engine.py` | Plan actions (INSTALL/UPDATE/SKIP/UNINSTALL), execute copies, collect results |
| `target.py` | Discover platforms on local machine, manage installed items |
| `config.py` | Load/save `.agentfiles.yaml` config and `.agentfiles.state.yaml` state |
| `models.py` | Data models (Item, SyncPlan, SyncResult, etc.), enums, frontmatter parsing |
| `frontmatter.py` | YAML frontmatter extraction from markdown files |
| `tokens.py` | Token count estimation (4 chars/token heuristic) |
| `paths.py` | Path resolution helpers for install/push destinations |
| `git.py` | Git subprocess wrapper |
| `interactive.py` | Interactive CLI prompts (mode selection, confirmation) |
| `output.py` | Colourised terminal output utilities |
| `doctor.py` | Environment diagnostics |

## Key Design Patterns

### Open/Closed Principle (Extension Points)

The codebase uses **dispatch tables** instead of if/elif chains. Adding a new
platform or item type only requires registration — no existing code changes.

**Adding a new platform:**
1. Add `Platform` enum value in `models.py`
2. Write candidate resolver in `target.py` (`_DISCOVERY_TABLE`)
3. Add alias in `PLATFORM_ALIASES`

**Adding a new item type:**
1. Add `ItemType` enum value in `models.py`
2. Write scanner function in `scanner.py`
3. Register via `_register_scanner()`

**Adding a new sync action:**
1. Add `SyncAction` enum value in `models.py`
2. Write plan handler + execute handler in `engine.py`
3. Register in `__init__` dispatch dicts

### Strategy Dispatch (engine.py)

```python
# Plan handlers — keyed by SyncAction
self._plan_handlers = {
    SyncAction.INSTALL: self._plan_install_or_update,
    SyncAction.UPDATE:  self._plan_install_or_update,
    SyncAction.UNINSTALL: self._plan_uninstall,
}

# Execute handlers — keyed by SyncAction
self._action_handlers = {
    SyncAction.SKIP: self._execute_skip,
    SyncAction.INSTALL: self._execute_install,
    SyncAction.UPDATE: self._execute_update,
    SyncAction.UNINSTALL: self._execute_uninstall,
}
```

### Atomic Updates (engine.py)

Updates use a temp file + backup swap pattern:
1. Copy source to `.agentfiles_tmp`
2. Rename existing dest to `.bak`
3. Atomic rename temp → dest
4. Clean up `.bak` on success, rollback on failure

### Protocol-Based Decoupling

`SyncEngine` depends on `SyncTarget` protocol (not concrete `TargetManager`):
```python
@runtime_checkable
class SyncTarget(Protocol):
    def get_target_dir(self, platform, item_type) -> Path | None: ...
    def resolve_platform_for(self, item_type, target_dir) -> Platform | None: ...
```

Similarly, `SourceResolver` depends on `GitBackend` protocol for testability.

## Source Detection Strategy

When no explicit source is provided, `SourceResolver.detect()`:
1. Walks from CWD upward
2. Looks for directories with ≥2 of {agents/, skills/, commands/, plugins/}
3. Returns the first qualifying ancestor

For git URLs:
1. Shallow clone (`--depth 1`) into `~/.cache/agentfiles/repos/<repo-name>`
2. Subsequent resolves: fetch → compare HEAD vs FETCH_HEAD → reset only if changed

## Three-Way Sync (compute_sync_plan)

Uses `.agentfiles.state.yaml` to store per-item checksums at last sync time:

| Source changed | Target changed | Action |
|---------------|---------------|--------|
| Yes | No | `pull` |
| No | Yes | `push` |
| Yes | Yes | `conflict` |
| No | No | `skip` |
| (not in state) | — | `pull` (new item) |
