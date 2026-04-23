# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.3.0] - 2026-04-12

### Changed
- **Multi-platform support removed** — The project now supports only OpenCode. Previous support for Claude Code, Windsurf, Cursor, GitHub Copilot, Aider, and Continue.dev has been removed.

### Added
- **WORKFLOW item type** — Sync pipeline/recipe files alongside agents, skills, commands, plugins, and configs (6 item types total).
- **Bidirectional conflict detection and resolution for push** — Detect and resolve conflicts when pushing changes back to the source repository.
- **`--create-pr` flag for push** — Automatically create a pull request via `gh` after pushing changes.
- **`--item` flag** — Selective pull/push/clean by item name.
- **Shallow clone + sparse checkout** — Efficient remote git source handling with minimal bandwidth and disk usage.
- **Force reinstall on update/full sync modes** — Ensures items are always in sync when using `update` or full sync.
- **`Typing :: Typed` classifier** — PEP 561 type checking support advertised on PyPI.

### Fixed
- **Config platform filtering** — Config files are now correctly filtered by filename prefix.
- **Three pull bugs** — Resolved edge cases in pull sync behavior.
- **Mypy strict compliance** — Fixed `Path | None` type narrowing in scanner scope resolution.
- **Import sorting** — Fixed isort compliance in paths module.
- **Removed stale `syncode/` package** — Cleaned up leftover directory from package rename.

### Quality
- **Tests**: 1,840 passing across 34 test files
- **Platforms**: 1 (OpenCode only)
- **Item types**: 6 (up from 4)

## [0.2.0] - 2026-04-03

### Breaking Changes
- **Removed TUI**: The Textual-based TUI (`agentfiles` with no subcommand) has been removed. Running `agentfiles` without a subcommand now prints help and exits with code 2.

### Added
- **`doctor` command** (`agentfiles doctor`) — Diagnose common environment and configuration problems. Checks config, source, git, platform directories, state file, and platform tools.
- **`verify` command** (`agentfiles verify`) — CI-friendly drift detection. Exit 0 if all items match, 1 if drift detected. Supports `--format json` and `--quiet`.
- **`update` command** (`agentfiles update`) — Git pull + sync in one step. Inspired by chezmoi's most-used multi-machine command.
- **`clean` command** (`agentfiles clean`) — Remove orphaned items that no longer exist in source. Inspired by dotbot.
- **`completion` command** (`agentfiles completion bash|zsh|fish`) — Generate shell completion scripts.
- **`--color always|auto|never`** — Modern CLI tri-state flag. Respects `NO_COLOR` and `FORCE_COLOR` environment variables.
- **`--only ITEMS` / `--except ITEMS`** — Surgical item filtering by name.
- **`--format json`** — Machine-readable JSON output on `status`, `show`, `pull`, `push` commands (in addition to existing `list` and `diff`).
- **Grouped `--help`** — Arguments organized by category (Source, Filter, Output, Sync) with example commands.
- **`print_section()` / `print_item_status()` / `pluralize()`** — New output formatting helpers.
- **Auto terminal-width tables** — Tables adapt to terminal size.
- **9.5x performance improvement** — `--type` filtering uses `scan_type()` instead of `scan()` + filter.

### Changed
- **Split `models.py`** (1638 → 952 lines, -42%) into focused modules:
  - `checksum.py` (279 lines) — SHA-256 checksum computation
  - `frontmatter.py` (311 lines) — YAML frontmatter parsing
  - `tokens.py` (262 lines, consolidated) — Token estimation
- **Moved gitignore** utilities from `models.py` to `scanner.py` (their sole consumer).
- **Extracted `CommandContext`** pattern to reduce CLI boilerplate.
- **Consolidated** `format_item_count`/`pluralize` into single `pluralize()` in `output.py`.

### Fixed
- **Critical**: `sync()` (pull) now updates state file after installing items, making bidirectional sync reliable.
- **URL parsing**: Strip query strings and fragments from git URLs (e.g., `?ref=main`).
- **Case-insensitive git URL detection**: `HTTPS://` and `Git@` URLs now recognized.
- **`is_dirty` pre-check**: `switch_branch()` now checks for uncommitted changes before attempting checkout.
- **`TimeoutExpired` handling**: `run_git()` now raises `GitError` instead of crashing.
- **Error isolation**: `execute_plan()` continues past individual item failures.
- **Atomic state writes**: State file uses temp+rename pattern.

### Removed
- `tui.py` (2454 lines) — Textual-based TUI removed entirely.
- `test_tui_push.py` — TUI-specific tests removed.
- `make_item_key` from `paths.py` — Dead code eliminated.

### Quality
- **Ruff**: 0 errors across 18 source files
- **Mypy**: 0 errors with strict checking
- **Tests**: 1858 passing (up from 1629)
- **Line count**: 12,467 total (down from 16,384 in models.py alone)

## [0.1.0] - 2026-03-31

### Added
- Initial release of syncode
- Source detection from local directory, git repo, or remote URL
- Sync agents, skills, commands, and plugins to OpenCode and Claude Code
- Interactive mode with menu-driven workflow
- Non-interactive mode (`--yes`) for CI/agent use
- `init` command to create new syncode repositories
- `sync`, `status`, `list`, `diff`, `uninstall` commands
- Dry-run mode for previewing changes
- Atomic file operations with backup-rollback safety
- YAML configuration file support (`.syncode.yaml`)
- Symlink mode as alternative to file copying
