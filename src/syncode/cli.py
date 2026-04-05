"""Command-line interface for the syncode tool.

Exposes a single ``agentfiles`` CLI entry-point that orchestrates scanning,
synchronisation, diffing, and interactive workflows across AI tool platforms
(OpenCode, Claude Code, Cursor, Windsurf, etc.).

Subcommands:

- ``agentfiles pull``       — Install/update items from a source repository to
  local platform configs.  Interactive by default; pass ``--yes`` for
  non-interactive mode.
- ``agentfiles push``       — Push locally-installed items back into the source
  repository.  Discovers items from target platforms so it works even when
  the source repo is empty.
- ``agentfiles sync``       — Three-way bidirectional sync using checksums
  stored in ``.agentfiles.state.yaml``.  Detects whether each item needs a
  pull, push, or manual conflict resolution.
- ``agentfiles status``     — Show installed-item counts per discovered
  platform.
- ``agentfiles list``       — List items available in the source repository.
  Supports ``--format json`` and ``--tokens`` for token-cost estimates.
- ``agentfiles diff``       — Show differences between source items and their
  installed counterparts on target platforms.
- ``agentfiles verify``     — Verify installed items match source checksums.
  CI-friendly: exit 0 if clean, 1 if drift detected.  Supports
  ``--format json`` and ``--quiet`` for scripting.
- ``agentfiles uninstall``  — Remove installed items from target platforms.
- ``agentfiles clean``      — Remove orphaned items (installed items whose
  source no longer exists in the repository).
- ``agentfiles init``       — Scaffold a new agentfiles repository with
  ``agents/``, ``skills/``, ``commands/``, ``plugins/`` directories and a
  ``.agentfiles.yaml`` config file.
- ``agentfiles update``     — Update source repository (``git pull``) and
  sync to local platforms in one step.  Primary multi-machine workflow.
- ``agentfiles branch``     — List or switch git branches in the source
  repository.
- ``agentfiles show``       — Preview the primary content file of a specific
  item (agent prompt, skill file, etc.).  Supports partial name matching.
- ``agentfiles completion``  — Generate shell completion scripts for bash,
  zsh, and fish.

Common usage patterns::

    # Pull everything interactively (default)
    agentfiles pull

    # Pull in CI / scripting mode
    agentfiles pull --yes --target opencode

    # Sync bidirectionally
    agentfiles sync

    # List items with token estimates as JSON
    agentfiles list --tokens --format json

    # Show an agent's prompt
    agentfiles show my-agent

When invoked with no subcommand, a help message is printed and the process
exits with code 2.

**Performance note:** All ``syncode.*`` imports are deferred to function scope
so that ``import syncode.cli`` completes in < 1 ms.  Heavy modules (models,
engine, differ, interactive, git) are loaded only when the corresponding
command is executed.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

# Re-exported from extraction modules for backward compatibility.
from syncode.cli_completion import (  # noqa: F401
    _PLATFORM_CHOICES,
    _SUBCOMMAND_INFO,
    _SUBCOMMANDS,
    _TYPE_CHOICES,
    cmd_completion,
)
from syncode.cli_format import (  # noqa: F401
    _SHORT_HASH_LEN,
    _build_verify_items,
    _format_list_json,
    _format_plan_json,
    _format_results_json,
    _format_show_json,
    _format_status_json,
    _print_verify_text,
)

if TYPE_CHECKING:
    from syncode.config import SyncodeConfig
    from syncode.engine import SyncEngine
    from syncode.models import (
        Item,
        ItemType,
        Platform,
        SyncPlan,
        SyncResult,
        SyncState,
        TokenEstimate,
    )
    from syncode.scanner import SourceScanner
    from syncode.target import TargetManager

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _resolve_platforms(
    target_flag: str | None,
    config: SyncodeConfig,
) -> list[Platform]:
    """Resolve which target platforms to operate on.

    Resolution order:

    1. ``"all"`` — return every known platform.
    2. Explicit flag value — return a single-element list.
    3. ``None`` — fall back to ``config.default_platforms``; if that list
       is empty or contains only unknown names, return every platform.

    Args:
        target_flag: Value of the ``--target`` CLI flag (``"all"``, a
            platform name, or ``None``).
        config: Loaded ``SyncodeConfig`` providing ``default_platforms``.

    Returns:
        List of ``Platform`` enums to operate on.

    """
    from syncode.models import Platform, resolve_platform

    if target_flag == "all":
        return list(Platform)

    if target_flag is not None:
        canonical = resolve_platform(target_flag)
        return [Platform(canonical)]

    result: list[Platform] = []
    for name in config.default_platforms:
        try:
            canonical = resolve_platform(name)
            result.append(Platform(canonical))
        except ValueError:
            logger.warning("Unknown platform in config: %s", name)
    # If config yielded no valid platforms, operate on all of them.
    return result or list(Platform)


def _resolve_item_types(type_flag: str | None) -> list[ItemType]:
    """Resolve which item types to include from the ``--type`` CLI flag.

    Args:
        type_flag: Value of the ``--type`` flag (``"agent"``, ``"skill"``,
            ``"command"``, ``"plugin"``, ``"all"``, or ``None``).

    Returns:
        List of ``ItemType`` enums.  Unknown values fall back to all types
        with a warning.

    """
    from syncode.models import ItemType

    if type_flag == "all" or type_flag is None:
        return list(ItemType)
    try:
        return [ItemType(type_flag)]
    except ValueError:
        from syncode.output import warning

        warning(f"Unknown item type '{type_flag}', showing all types.")
        return list(ItemType)


def _filter_items(
    items: list[Item],
    item_types: list[ItemType],
) -> list[Item]:
    """Keep only items whose ``item_type`` is in *item_types*.

    Args:
        items: Scanned ``Item`` objects.
        item_types: Allowed ``ItemType`` values.

    Returns:
        Filtered list of ``Item`` objects.

    """
    return [i for i in items if i.item_type in item_types]


def _scan_filtered(
    scanner: SourceScanner,
    item_types: list[ItemType],
) -> list[Item]:
    """Scan source items, using ``scan_type`` when a single type is requested.

    When *item_types* contains exactly one ``ItemType``, delegates to
    :meth:`SourceScanner.scan_type` to avoid scanning unrelated directories
    and computing checksums for items that would be discarded anyway.
    Falls back to :meth:`SourceScanner.scan` when all types are requested.

    Args:
        scanner: Configured source scanner.
        item_types: Resolved list of ``ItemType`` values.

    Returns:
        List of discovered ``Item`` objects (already filtered by type).

    """

    if len(item_types) == 1:
        return scanner.scan_type(item_types[0])
    return scanner.scan()


def _resolve_item_filter(
    args: argparse.Namespace,
) -> tuple[set[str] | None, set[str] | None]:
    """Resolve ``--only`` and ``--except`` flags into item-name filter sets.

    Args:
        args: Parsed CLI namespace (reads ``only`` and ``except_items``).

    Returns:
        ``(only_set, except_set)`` — at most one will be non-None.
        ``only_set`` is a set of item names to include exclusively.
        ``except_set`` is a set of item names to exclude.
    """
    only_raw: str | None = getattr(args, "only", None)
    except_raw: str | None = getattr(args, "except_items", None)

    only_set: set[str] | None = None
    except_set: set[str] | None = None

    if only_raw:
        only_set = {name.strip() for name in only_raw.split(",") if name.strip()}
    if except_raw:
        except_set = {name.strip() for name in except_raw.split(",") if name.strip()}

    return only_set, except_set


def _apply_item_filter(
    items: list[Item],
    only_set: set[str] | None,
    except_set: set[str] | None,
) -> list[Item]:
    """Apply ``--only`` and ``--except`` filters to a list of items.

    If *only_set* is provided, only items whose ``name`` is in the set
    are kept.  If *except_set* is provided, matching items are removed.
    Both can be ``None`` (no filtering on that axis).

    Args:
        items: Items to filter.
        only_set: Set of item names to include (or ``None``).
        except_set: Set of item names to exclude (or ``None``).

    Returns:
        Filtered list of items.
    """
    if only_set is not None:
        items = [i for i in items if i.name in only_set]
    if except_set is not None:
        items = [i for i in items if i.name not in except_set]
    return items


def _apply_color_env(color: str) -> None:
    """Apply color preference to environment variables.

    Sets ``NO_COLOR`` / ``FORCE_COLOR`` / ``CLICOLOR_FORCE`` so that
    downstream output helpers respect the user's ``--color`` choice.

    Args:
        color: One of ``"always"``, ``"never"``, or ``"auto"``.
    """
    if color == "never":
        os.environ["NO_COLOR"] = "1"
        os.environ.pop("FORCE_COLOR", None)
        os.environ.pop("CLICOLOR_FORCE", None)
    elif color == "always":
        os.environ["FORCE_COLOR"] = "1"
        os.environ["CLICOLOR_FORCE"] = "1"
        os.environ.pop("NO_COLOR", None)
    # "auto" → leave env untouched; init_logging() uses its heuristic


def _discover_targets(config: SyncodeConfig) -> TargetManager:
    """Discover installed AI tool platforms and build a ``TargetManager``.

    Scans common install paths for OpenCode, Claude Code, Cursor, Windsurf,
    etc.  Custom paths from the config override the defaults.

    Args:
        config: Loaded ``SyncodeConfig`` (may provide ``custom_paths``).

    Returns:
        A ``TargetManager`` with at least one discovered platform.

    Raises:
        SyncodeError: When no platforms are discovered on the system.

    """
    from syncode.models import SyncodeError
    from syncode.target import build_target_manager

    target_manager = build_target_manager(config.custom_paths)

    if not target_manager.targets:
        raise SyncodeError(
            "No target platforms found. Install at least one supported tool: "
            "OpenCode (https://opencode.ai), Claude Code (https://claude.ai/code), "
            "Windsurf (https://codeium.com/windsurf), or Cursor (https://cursor.com). "
            "Alternatively, use --config to specify custom_paths for your platform"
        )

    return target_manager


def _get_source(
    args: argparse.Namespace,
    fallback_cache_dir: str | None = None,
    *,
    quiet: bool = False,
) -> Path:
    """Resolve the source directory from CLI args or auto-detect from CWD.

    Supports local paths, git URLs, and shorthand identifiers.  Remote
    sources are cloned to a local cache directory.

    Args:
        args: Parsed CLI namespace (reads ``source`` and ``cache_dir``).
        fallback_cache_dir: Config file's ``cache_dir`` used when the
            CLI ``--cache-dir`` flag is not provided.  Passed by callers
            that have already loaded a :class:`SyncodeConfig`.

    Returns:
        Local ``Path`` to the resolved source directory.

    Raises:
        SourceError: When the source cannot be detected or resolved.

    """
    from syncode.models import SourceError
    from syncode.output import info
    from syncode.source import SourceResolver

    resolver = SourceResolver()
    source_arg = getattr(args, "source", None)
    try:
        source_info = resolver.detect(source_arg)
    except SourceError:
        raise
    except Exception as exc:
        raise SourceError(
            f"Failed to detect source: {exc}. "
            f"Navigate to a project with agents/, skills/, commands/, or plugins/ "
            f"directories, or provide an explicit path or git URL"
        ) from exc

    if not quiet:
        info(f"Source: {source_info.source_type.value} — {source_info.path}")
    cache_dir = getattr(args, "cache_dir", None) or fallback_cache_dir
    try:
        return resolver.resolve(
            source_info,
            cache_dir=Path(cache_dir) if cache_dir else None,
        )
    except SourceError:
        raise
    except Exception as exc:
        raise SourceError(
            f"Failed to resolve source '{source_info.path}': {exc}. "
            f"If using a git URL, check network connectivity and repository access"
        ) from exc


def _create_sync_pipeline(
    source_dir: Path,
    config: SyncodeConfig,
    args: argparse.Namespace,
) -> tuple[SourceScanner, TargetManager, SyncEngine]:
    """Create the configured scanner, target manager, and sync engine.

    Shared by ``cmd_pull``, ``cmd_push``, and ``cmd_sync`` to avoid
    duplicating pipeline setup.

    Args:
        source_dir: Resolved local path to the source repository.
        config: Loaded ``SyncodeConfig``.
        args: Parsed CLI namespace (reads ``symlinks`` and ``dry_run``).

    Returns:
        ``(scanner, target_manager, engine)`` tuple ready for use.

    """
    from syncode.engine import SyncEngine
    from syncode.scanner import SourceScanner

    scanner = SourceScanner(source_dir)
    target_manager = _discover_targets(config)
    engine = SyncEngine(
        target_manager=target_manager,
        use_symlinks=getattr(args, "symlinks", False) or config.use_symlinks,
        dry_run=getattr(args, "dry_run", False),
    )
    return scanner, target_manager, engine


@dataclass
class CommandContext:
    """Shared state for CLI command execution.

    Bundles the common resolution results (config, source directory,
    sync pipeline components, and user-specified filters) that most
    ``cmd_*`` functions need.  Constructed via :func:`_build_context`.

    Pipeline fields (*source_dir*, *scanner*, *target_manager*, *engine*)
    are ``None`` when the context is built with ``needs_pipeline=False``.
    """

    config: SyncodeConfig
    source_dir: Path | None
    scanner: SourceScanner | None
    target_manager: TargetManager | None
    engine: SyncEngine | None
    platforms: list[Platform]
    item_types: list[ItemType]
    dry_run: bool
    fmt: str
    only_set: set[str] | None
    except_set: set[str] | None


def _build_context(
    args: argparse.Namespace,
    *,
    needs_pipeline: bool = True,
) -> CommandContext:
    """Build shared command context from CLI arguments.

    Resolves config, source directory, sync pipeline (scanner, target
    manager, engine), platform list, item type filter, and ``--only``/
    ``--except`` name filters from the parsed CLI namespace.

    Args:
        args: Parsed CLI namespace from :func:`build_parser`.
        needs_pipeline: When ``True`` (default), resolve the source
            directory and create the full sync pipeline (scanner,
            target manager, engine).  When ``False``, skip pipeline
            creation — *source_dir*, *scanner*, *target_manager*, and
            *engine* will be ``None``.

    Returns:
        A populated :class:`CommandContext` instance.
    """
    from syncode.config import SyncodeConfig

    config = SyncodeConfig.load(getattr(args, "config", None))

    source_dir: Path | None = None
    scanner: SourceScanner | None = None
    target_manager: TargetManager | None = None
    engine: SyncEngine | None = None

    if needs_pipeline:
        source_dir = _get_source(
            args,
            config.cache_dir,
            quiet=(getattr(args, "format", "text") == "json"),
        )
        scanner, target_manager, engine = _create_sync_pipeline(
            source_dir,
            config,
            args,
        )

    item_types = _resolve_item_types(getattr(args, "item_type", None))
    platforms = _resolve_platforms(getattr(args, "target", None), config)
    only_set, except_set = _resolve_item_filter(args)

    return CommandContext(
        config=config,
        source_dir=source_dir,
        scanner=scanner,
        target_manager=target_manager,
        engine=engine,
        platforms=platforms,
        item_types=item_types,
        dry_run=getattr(args, "dry_run", False),
        fmt=getattr(args, "format", "text"),
        only_set=only_set,
        except_set=except_set,
    )


def _filter_items_by_installed(
    items: list[Item],
    target_manager: TargetManager,
    platforms: list[Platform],
    *,
    installed: bool,
) -> list[Item]:
    """Filter items by installation status.

    Args:
        items: Items to evaluate.
        target_manager: Provides access to installed-item lookups.
        platforms: Target platforms to check against.
        installed: If True, return only already-installed items.
                   If False, return only not-yet-installed items.

    Returns:
        Filtered list of items.

    """
    result = []
    for item in items:
        for platform in platforms:
            if target_manager.is_item_installed(item, platform) == installed:
                result.append(item)
                break
    return result


def _discover_installed_from_targets(
    target_manager: TargetManager,
    platforms: list[Platform],
    item_types: list[ItemType],
) -> list[Item]:
    """Discover installed items directly from target platforms.

    Unlike scanning the source repository, this method finds items that
    exist on disk in the target platform directories.  This allows push
    to work even when the source repository is empty.

    Args:
        target_manager: Configured target manager.
        platforms: Platforms to scan.
        item_types: Item types to include.

    Returns:
        Deduplicated list of ``Item`` objects with ``source_path``
        pointing to the on-disk location at the target platform.
        Items found on multiple platforms include all of them in
        ``supported_platforms``.

    """
    from syncode.models import Item
    from syncode.paths import get_installed_item_path

    # Collect (item_type, name) → (first on-disk path, all platforms).
    registry: dict[tuple[ItemType, str], tuple[Path, list[Platform]]] = {}

    for platform in platforms:
        for item_type, name in target_manager.get_installed_items(platform):
            if item_type not in item_types:
                continue

            target_dir = target_manager.get_target_dir(platform, item_type)
            if target_dir is None:
                continue

            item_path = get_installed_item_path(target_dir, item_type, name)

            if not item_path.exists():
                continue

            key = (item_type, name)
            if key in registry:
                registry[key][1].append(platform)
            else:
                registry[key] = (item_path, [platform])

    items: list[Item] = []
    for (item_type, name), (item_path, item_platforms) in registry.items():
        items.append(
            Item(
                item_type=item_type,
                name=name,
                source_path=item_path,
                supported_platforms=tuple(item_platforms),
            )
        )

    return items


def _find_adopt_candidates(
    source_dir: Path,
    target_manager: TargetManager,
    platforms: list[Platform],
    item_types: list[ItemType],
) -> list[Item]:
    """Find items installed on target platforms but absent from source.

    Scans the source repository for existing items and compares against
    items discovered on target platforms.  Returns only those items that
    exist on targets but have no counterpart in the source.

    Args:
        source_dir: Local path to the source repository.
        target_manager: Configured target manager.
        platforms: Platforms to scan.
        item_types: Item types to include.

    Returns:
        List of items eligible for adoption.
    """
    from syncode.scanner import SourceScanner

    scanner = SourceScanner(source_dir)
    source_items = scanner.scan()
    source_keys = {item.item_key for item in source_items}

    installed_items = _discover_installed_from_targets(
        target_manager,
        platforms,
        item_types,
    )

    return [item for item in installed_items if item.item_key not in source_keys]


def _display_adopt_candidates(candidates: list[Item]) -> None:
    """Print adopt candidates with platform and source-path info.

    Each line shows the item key, the first platform where it was found,
    and the on-disk path at that platform.

    Args:
        candidates: Items eligible for adoption.
    """
    for item in sorted(candidates, key=lambda i: i.sort_key):
        plat = item.supported_platforms[0] if item.supported_platforms else None
        plat_name = plat.display_name if plat else "unknown"
        print(f"  {item.item_key:<30s} [{plat_name}] — {item.source_path}")


def _run_pull_interactive(
    items: list[Item],
    target_manager: TargetManager,
    platforms: list[Platform],
) -> tuple[list[Item], list[Platform]] | None:
    """Run an interactive pull session to let the user choose what to install.

    Presents a mode chooser (``full``, ``install``, ``update``, ``custom``)
    and progressively filters items and platforms based on the selection.

    Args:
        items: All items scanned from the source repository.
        target_manager: Used to check per-platform installation status.
        platforms: Candidate platforms for installation.

    Returns:
        ``(filtered_items, filtered_platforms)`` when the user made a valid
        selection, or ``None`` if the user aborted or nothing matched.

    """
    from syncode.interactive import InteractiveSession
    from syncode.output import info, warning

    session = InteractiveSession()
    mode = session.choose_sync_mode()

    if mode == "custom":
        selected_platforms = session.select_platforms(platforms)
        if not selected_platforms:
            warning("No platforms selected.")
            return None
        platforms = selected_platforms

        selected_types = session.select_item_types()
        items = _filter_items(items, selected_types)
        if not items:
            warning("No items selected.")
            return None

        items = session.select_items(items)
        if not items:
            warning("No items selected.")
            return None
    elif mode == "install":
        items = _filter_items_by_installed(items, target_manager, platforms, installed=False)
        if not items:
            info("All items are already up-to-date.")
            return None
    elif mode == "update":
        items = _filter_items_by_installed(items, target_manager, platforms, installed=True)
        if not items:
            info("No items need updating.")
            return None
    # mode == "full": use all items as-is

    return items, platforms


def _print_token_summary(estimates: list[TokenEstimate]) -> None:
    """Print an aggregate token-count summary table to stdout.

    Args:
        estimates: List of ``TokenEstimate`` objects to aggregate.

    """
    from syncode.output import bold

    total = sum(e.total_tokens for e in estimates)
    content_total = sum(e.content_tokens for e in estimates)
    overhead_total = sum(e.overhead_tokens for e in estimates)
    print()
    bold("Token Summary:")
    print(f"  Items: {len(estimates)}")
    print(f"  Content tokens: ~{content_total:,}")
    print(f"  Overhead tokens: ~{overhead_total:,}")
    print(f"  Total tokens: ~{total:,}")


def _format_list_text(items: list[Any], show_tokens: bool) -> int:
    """Format items as grouped, colourised text and print to stdout.

    Items are grouped by type (agents, skills, …) and sorted alphabetically
    within each group.  An aggregate token summary is printed at the end
    when *show_tokens* is ``True``.

    Args:
        items: Items to display.
        show_tokens: If ``True``, include per-item and aggregate token counts.

    Returns:
        Exit code (always ``0``).
    """
    from syncode.output import Colors, bold, colorize
    from syncode.tokens import token_estimate

    current_type: ItemType | None = None
    estimates: list[TokenEstimate] = []

    for item in sorted(items, key=lambda i: i.sort_key):
        if item.item_type != current_type:
            current_type = item.item_type
            print()
            bold(f"{current_type.plural}:")
        if show_tokens:
            est = token_estimate(item)
            estimates.append(est)
            print(
                f"  {colorize(item.name, Colors.GREEN)}  "
                f"v{item.version}  "
                f"({len(item.files)} files)  "
                f"~{est.total_tokens:,} tokens"
            )
        else:
            print(
                f"  {colorize(item.name, Colors.GREEN)}  v{item.version}  ({len(item.files)} files)"
            )

    if show_tokens and estimates:
        _print_token_summary(estimates)

    return 0


def _create_init_structure(base: Path) -> tuple[list[str], list[str]]:
    """Create the standard directory layout for a new agentfiles repository.

    Generates ``agents/``, ``skills/``, ``commands/``, and ``plugins/``
    subdirectories, each with a ``.gitkeep`` file to ensure they are
    tracked by git even when empty.

    Args:
        base: Root directory for the new repository.

    Returns:
        ``(created_dirs, skipped_dirs)`` — names of directories that were
        created vs. already existed.  Useful for user-facing output.

    Raises:
        SyncodeError: When directory or file creation fails due to
            permission or filesystem errors.
    """
    from syncode.models import ItemType, SyncodeError

    created_dirs: list[str] = []
    skipped_dirs: list[str] = []

    for item_type in ItemType:
        subdir_name = item_type.plural
        subdir = base / subdir_name
        if subdir.exists():
            skipped_dirs.append(subdir_name)
        else:
            try:
                subdir.mkdir(parents=True, exist_ok=True)
                (subdir / ".gitkeep").touch()
            except OSError as exc:
                raise SyncodeError(
                    f"Failed to create directory '{subdir}': {exc}. "
                    f"Check that the parent directory exists and is writable, "
                    f"or run with appropriate permissions"
                ) from exc
            created_dirs.append(subdir_name)

    return created_dirs, skipped_dirs


def _execute_sync_actions(
    sync_plan: list[tuple[Item, Platform, str]],
    platforms: tuple[Platform, ...],
    engine: SyncEngine,
    source_dir: Path,
    dry_run: bool,
    skip_conflicts: bool,
) -> list[SyncResult]:
    """Execute the pull/push/conflict actions from a computed sync plan.

    Processes the plan in three phases:

    1. **Pull** — copy items from source to target platforms.
    2. **Push** — copy items from target platforms back to the source.
    3. **Conflicts** — log a warning; optionally skip silently.

    Args:
        sync_plan: List of ``(item, platform, action)`` tuples where
            *action* is ``"pull"``, ``"push"``, or ``"conflict"``.
        platforms: Target platforms for pull/push operations.
        engine: ``SyncEngine`` instance to execute the operations.
        source_dir: Local path to the source repository (needed for push).
        dry_run: If ``True``, preview changes without writing.
        skip_conflicts: If ``True``, suppress conflict warnings.

    Returns:
        Combined list of ``SyncResult`` objects from all phases.
    """
    from syncode.output import info, warning

    all_results: list[SyncResult] = []

    # Pulls: source → target (same as regular sync/install).
    pull_items = [item for item, _, action in sync_plan if action == "pull"]
    if pull_items:
        pull_plans = engine.plan_sync(pull_items, tuple(platforms))
        pull_results = engine.execute_plan(pull_plans)
        all_results.extend(pull_results)
        info(f"Pulled {sum(1 for r in pull_results if r.is_success)} item(s)")

    # Pushes: target → source.
    push_items = [item for item, _, action in sync_plan if action == "push"]
    if push_items:
        push_report = engine.push(
            push_items,
            platforms,
            source_dir=source_dir,
            dry_run=dry_run,
        )
        all_results.extend(push_report.installed + push_report.updated + push_report.failed)
        info(f"Pushed {push_report.success_count} item(s)")

    # Conflicts: skip unless interactive resolution is implemented.
    conflict_items = [
        (item, platform) for item, platform, action in sync_plan if action == "conflict"
    ]
    if conflict_items:
        for item, platform in conflict_items:
            label = f"{item.name} ({platform.display_name})"
            if skip_conflicts:
                warning(f"Conflict skipped: {label}")
            else:
                warning(f"Conflict: {label} — skipped (resolve manually)")

    return all_results


def _display_update_indicators(plans: list[SyncPlan]) -> None:
    """Show diff indicators for items that will be updated.

    In non-interactive mode the user does not see a confirmation prompt,
    so this function prints explicit ``~ item_name`` lines for every plan
    whose action is ``UPDATE`` so the user knows which items changed.

    Args:
        plans: List of ``SyncPlan`` objects from the engine.
    """
    from syncode.models import SyncAction

    update_plans = [p for p in plans if p.action == SyncAction.UPDATE]
    if not update_plans:
        return
    print()
    for plan in update_plans:
        file_count = len(plan.item.files) if plan.item.files else 0
        file_info = f" — {file_count} files" if file_count else ""
        print(f"  ~ {plan.item.name} (checksum differs{file_info})")


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


def cmd_pull(args: argparse.Namespace) -> int:
    """Install or update items from a source repository onto target platforms.

    Scans the source for available items, optionally filters by type and
    platform, then copies (or symlinks) files to each target's config
    directory.  By default an interactive session guides the user through
    mode selection (full / install-only / update-only / custom); pass
    ``--yes`` (``non_interactive``) to skip all prompts.

    Args:
        args: Parsed CLI namespace.  Relevant flags: ``source``, ``target``,
            ``item_type``, ``non_interactive``, ``dry_run``, ``symlinks``,
            ``config``, ``cache_dir``.

    Returns:
        ``0`` on success, ``1`` if any operation failed.
    """
    from syncode.engine import SyncEngine
    from syncode.interactive import InteractiveSession
    from syncode.output import bold, format_item_count, info, warning

    ctx = _build_context(args)
    scanner = ctx.scanner
    target_manager = ctx.target_manager
    engine = ctx.engine
    source_dir = ctx.source_dir

    # needs_pipeline=True guarantees non-None values.
    assert scanner is not None
    assert target_manager is not None
    assert engine is not None
    assert source_dir is not None

    all_items = scanner.scan()
    summary = scanner.get_summary()
    total = sum(summary.values())
    info(f"Found {format_item_count(total, 'item')} in source")
    for itype, count in sorted(summary.items(), key=lambda kv: kv[0].plural):
        print(f"  {itype.plural}: {count}")

    if not all_items:
        warning("No items found in source.")
        return 0

    items = _filter_items(all_items, ctx.item_types)
    platforms = ctx.platforms

    # Apply --only / --except item-name filters
    items = _apply_item_filter(items, ctx.only_set, ctx.except_set)

    # Interactive by default, non-interactive with --yes
    if not args.non_interactive:
        result = _run_pull_interactive(items, target_manager, platforms)
        if result is None:
            return 0
        items, platforms = result

    plans = engine.plan_sync(items, tuple(platforms))

    fmt = ctx.fmt

    # JSON dry-run: output plan and return early.
    if fmt == "json" and ctx.dry_run:
        return _format_plan_json(plans, target_manager, dry_run=True)

    # Show plan and confirm (unless --yes or --dry-run)
    needs_confirmation = plans and not args.non_interactive and not ctx.dry_run
    if needs_confirmation:
        session = InteractiveSession()
        if not session.confirm_plans_or_abort(plans):
            return 0

    # In non-interactive mode, display explicit diff indicators for updates
    if args.non_interactive and not ctx.dry_run:
        _display_update_indicators(plans)

    results = engine.execute_plan(plans)
    report = SyncEngine.aggregate(results)

    # Persist sync state for non-dry-run successful operations.
    if not ctx.dry_run and any(r.is_success for r in results):
        from syncode.config import load_sync_state, save_sync_state

        sync_state = load_sync_state(source_dir)
        _update_sync_state_from_results(sync_state, results, target_manager)
        save_sync_state(source_dir, sync_state)

    # JSON non-dry-run: output results and return.
    if fmt == "json":
        return _format_results_json(results, report, dry_run=False)

    # Text output
    print()
    bold("Pull Summary:")
    print(f"  {report.summary()}")

    if ctx.dry_run:
        warning("Dry-run mode: no changes were made.")

    return 0 if report.is_success else 1


def cmd_push(args: argparse.Namespace) -> int:
    """Push locally-installed items back into the source repository.

    Discovers items directly from target platform directories (not from the
    source scanner) so that push works even when the source repo is empty or
    out of date.

    Args:
        args: Parsed CLI namespace.  Relevant flags: ``source``, ``target``,
            ``item_type``, ``non_interactive``, ``dry_run``, ``config``,
            ``cache_dir``.

    Returns:
        ``0`` on success, ``1`` if any operation failed.
    """
    from syncode.config import SyncodeConfig
    from syncode.interactive import InteractiveSession
    from syncode.output import bold, info, warning

    config = SyncodeConfig.load(args.config)
    source_dir = _get_source(
        args,
        config.cache_dir,
        quiet=(getattr(args, "format", "text") == "json"),
    )
    _, target_manager, engine = _create_sync_pipeline(source_dir, config, args)

    item_types = _resolve_item_types(args.item_type)
    platforms = _resolve_platforms(args.target, config)

    # Discover items from target platforms, not from the source scanner.
    installed_items = _discover_installed_from_targets(
        target_manager,
        platforms,
        item_types,
    )

    # Apply --only / --except item-name filters
    only_set, except_set = _resolve_item_filter(args)
    installed_items = _apply_item_filter(installed_items, only_set, except_set)

    if not installed_items:
        info("No installed items to push.")
        return 0

    # Interactive selection unless --yes
    if not args.non_interactive:
        session = InteractiveSession()
        installed_items = session.select_items(installed_items)
        if not installed_items:
            warning("No items selected.")
            return 0

    report = engine.push(
        installed_items, tuple(platforms), source_dir=source_dir, dry_run=args.dry_run
    )

    fmt = getattr(args, "format", "text")
    if fmt == "json":
        all_results = report.installed + report.updated + report.skipped + report.failed
        if args.dry_run:
            return _format_plan_json(
                [r.plan for r in all_results if r.is_success],
                target_manager,
                dry_run=True,
            )
        return _format_results_json(all_results, report, dry_run=False)

    print()
    bold("Push Summary:")
    print(f"  {report.summary()}")

    if args.dry_run:
        warning("Dry-run mode: no changes were made.")

    return 0 if report.is_success else 1


def cmd_adopt(args: argparse.Namespace) -> int:
    """Adopt items from target platforms into the source repository.

    Discovers items installed on target platforms that don't exist in the
    source repository and copies them into the appropriate source directory
    structure.  Inspired by GNU Stow's ``--adopt`` flag.

    Args:
        args: Parsed CLI namespace.  Relevant flags: ``source``, ``target``,
            ``item_type``, ``non_interactive``, ``dry_run``, ``config``,
            ``cache_dir``.

    Returns:
        ``0`` on success, ``1`` if any operation failed.
    """
    from dataclasses import replace as dc_replace

    from syncode.config import SyncodeConfig
    from syncode.engine import SyncEngine
    from syncode.interactive import InteractiveSession
    from syncode.output import bold, info, success, warning

    config = SyncodeConfig.load(args.config)
    source_dir = _get_source(
        args,
        config.cache_dir,
        quiet=(getattr(args, "format", "text") == "json"),
    )
    target_manager = _discover_targets(config)

    item_types = _resolve_item_types(args.item_type)
    platforms = _resolve_platforms(args.target, config)

    print()
    info("Scanning target platforms for items not in source...")

    candidates = _find_adopt_candidates(
        source_dir,
        target_manager,
        platforms,
        item_types,
    )

    # Apply --only / --except item-name filters.
    only_set, except_set = _resolve_item_filter(args)
    candidates = _apply_item_filter(candidates, only_set, except_set)

    if not candidates:
        info("No items to adopt — all installed items already exist in source.")
        return 0

    # Display candidates.
    print()
    bold(f"Found {len(candidates)} item(s) to adopt:")
    _display_adopt_candidates(candidates)

    if args.dry_run:
        print()
        warning("Dry-run mode: no changes were made.")
        return 0

    # Confirmation (unless --yes).
    if not args.non_interactive:
        session = InteractiveSession()
        if not session.confirm_action_or_abort(
            f"Adopt {len(candidates)} item(s) into source?",
        ):
            return 0

    # Limit each item to one source platform to avoid duplicate copies.
    adopt_items = [
        dc_replace(item, supported_platforms=(item.supported_platforms[0],))
        for item in candidates
        if item.supported_platforms
    ]

    engine = SyncEngine(target_manager=target_manager)
    report = engine.push(
        adopt_items,
        tuple(platforms),
        source_dir=source_dir,
    )

    print()
    bold("Adopt Summary:")
    print(f"  {report.summary()}")

    if report.is_success:
        print()
        success(f"Adopted {report.success_count} item(s) into {source_dir}.")
        info("Run 'agentfiles pull' to sync to all platforms.")

    return 0 if report.is_success else 1


def cmd_status(args: argparse.Namespace) -> int:
    """Display a table of installed-item counts per discovered platform.

    Shows the platform name, config directory path, and number of agents,
    skills, commands, and plugins installed for each platform found on the
    system.

    Args:
        args: Parsed CLI namespace.  Relevant flags: ``config``.

    Returns:
        ``0`` on success.
    """
    from syncode.config import SyncodeConfig
    from syncode.output import print_table

    config = SyncodeConfig.load(args.config)
    target_manager = _discover_targets(config)
    summary = target_manager.platform_summary()

    fmt = getattr(args, "format", "text")
    if fmt == "json":
        return _format_status_json(target_manager, summary)

    headers = ["Platform", "Path", "Agents", "Skills", "Commands", "Plugins"]
    rows: list[list[str]] = []

    for platform, paths in target_manager.targets.items():
        counts = summary.get(platform, {})
        rows.append(
            [
                platform.display_name,
                str(paths.config_dir),
                str(counts.get("agents", 0)),
                str(counts.get("skills", 0)),
                str(counts.get("commands", 0)),
                str(counts.get("plugins", 0)),
            ]
        )

    print_table(headers, rows)
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    """List items available in the source repository.

    Scans the source directory and prints all items, optionally filtered by
    type.  Output can be plain text (default) or JSON (``--format json``).
    Use ``--tokens`` to include estimated token counts.

    Args:
        args: Parsed CLI namespace.  Relevant flags: ``source``,
            ``item_type``, ``format``, ``tokens``, ``cache_dir``.

    Returns:
        ``0`` on success.
    """
    from syncode.scanner import SourceScanner

    source_dir = _get_source(
        args,
        quiet=(getattr(args, "format", "text") == "json"),
    )

    scanner = SourceScanner(source_dir)
    item_types = _resolve_item_types(args.item_type)
    items = _scan_filtered(scanner, item_types)

    # Apply --only / --except item-name filters
    only_set, except_set = _resolve_item_filter(args)
    items = _apply_item_filter(items, only_set, except_set)

    show_tokens = getattr(args, "tokens", False)

    if args.format == "json":
        return _format_list_json(items, show_tokens)

    return _format_list_text(items, show_tokens)


def cmd_diff(args: argparse.Namespace) -> int:
    """Show differences between source items and installed counterparts.

    Compares the source repository against each target platform's config
    directory and reports items that are missing, outdated, or have
    diverged.  Output is colourised text by default or JSON with
    ``--format json``.

    With ``--verbose``, UPDATED entries include a unified diff showing
    the actual content differences between source and target files.

    Args:
        args: Parsed CLI namespace.  Relevant flags: ``source``,
            ``target``, ``item_type``, ``format``, ``config``,
            ``cache_dir``, ``verbose_diff``.

    Returns:
        ``0`` on success.
    """
    from syncode.config import SyncodeConfig
    from syncode.differ import Differ, compute_content_diff
    from syncode.models import DiffStatus
    from syncode.output import format_diff, format_diff_json
    from syncode.scanner import SourceScanner

    config = SyncodeConfig.load(args.config)
    source_dir = _get_source(
        args,
        config.cache_dir,
        quiet=(getattr(args, "format", "text") == "json"),
    )

    scanner = SourceScanner(source_dir)
    item_types = _resolve_item_types(args.item_type)
    items = _scan_filtered(scanner, item_types)

    # Apply --only / --except item-name filters
    only_set, except_set = _resolve_item_filter(args)
    items = _apply_item_filter(items, only_set, except_set)

    platforms = _resolve_platforms(args.target, config)
    target_manager = _discover_targets(config)

    differ = Differ(target_manager)
    diff_results = differ.diff(items, tuple(platforms))

    if args.format == "json":
        print(format_diff_json(diff_results))
        return 0

    verbose_diff = getattr(args, "verbose_diff", False)
    content_diffs: dict[tuple[str, str], list[str]] | None = None

    if verbose_diff:
        content_diffs = {}
        for platform, entries in diff_results.items():
            for entry in entries:
                if entry.status != DiffStatus.UPDATED:
                    continue
                diff_lines = compute_content_diff(entry, platform, target_manager)
                if diff_lines:
                    content_diffs[(entry.item.item_key, platform.value)] = diff_lines

    print(
        format_diff(
            diff_results,
            verbose=verbose_diff,
            content_diffs=content_diffs,
        )
    )
    return 0


def _use_colors_output() -> bool:
    """Check whether colors should be used in output.

    Delegates to :func:`syncode.output.should_use_colors` but is isolated
    as a helper so the verify command can be tested without side effects.
    """
    from syncode.output import should_use_colors

    return should_use_colors()


def cmd_verify(args: argparse.Namespace) -> int:
    """Verify installed items match source checksums (CI-friendly).

    Compares every source item against its installed counterpart on each
    target platform and classifies the result as ``matching``, ``drift``,
    or ``missing``.  Designed for CI/CD pipelines: exit code 0 means
    clean state, exit code 1 means drift or missing items detected.

    Output modes:

    * **text** (default) — human-readable per-item status lines.
    * **json** (``--format json``) — machine-parseable JSON object.
    * **quiet** (``--quiet``) — suppresses all output; exit code only.

    Exit codes:

    - ``0`` — all items verified, no drift.
    - ``1`` — drift or missing items detected.
    - ``2`` — usage error (handled by ``main()``).

    Args:
        args: Parsed CLI namespace.  Relevant flags: ``source``,
            ``target``, ``item_type``, ``format``, ``config``,
            ``cache_dir``, ``quiet``.

    Returns:
        ``0`` when clean, ``1`` when drift or missing items found.

    """
    from syncode.config import SyncodeConfig
    from syncode.differ import Differ
    from syncode.scanner import SourceScanner

    config = SyncodeConfig.load(args.config)
    source_dir = _get_source(
        args,
        config.cache_dir,
        quiet=(getattr(args, "format", "text") == "json"),
    )

    scanner = SourceScanner(source_dir)
    item_types = _resolve_item_types(args.item_type)
    items = _scan_filtered(scanner, item_types)
    platforms = _resolve_platforms(args.target, config)
    target_manager = _discover_targets(config)

    differ = Differ(target_manager)
    diff_results = differ.diff(items, tuple(platforms))

    verify_items = _build_verify_items(diff_results)

    matching_count = sum(1 for r in verify_items if r["status"] == "matching")
    drift_count = sum(1 for r in verify_items if r["status"] == "drift")
    missing_count = sum(1 for r in verify_items if r["status"] == "missing")
    has_issues = drift_count > 0 or missing_count > 0

    is_quiet = getattr(args, "quiet", False)
    fmt = getattr(args, "format", "text")

    if is_quiet:
        return 1 if has_issues else 0

    if fmt == "json":
        payload = {
            "total": len(verify_items),
            "matching": matching_count,
            "drift": drift_count,
            "missing": missing_count,
            "items": verify_items,
        }
        print(json.dumps(payload, indent=2))
        return 1 if has_issues else 0

    _print_verify_text(verify_items, matching_count, drift_count, missing_count)
    return 1 if has_issues else 0


def cmd_uninstall(args: argparse.Namespace) -> int:
    """Remove installed items from target platforms.

    Discovers all installed items across target platforms and prompts the
    user to select which ones to remove.  A confirmation step is shown
    unless ``--force`` is passed.  Supports ``--dry-run`` for preview.

    Args:
        args: Parsed CLI namespace.  Relevant flags: ``target``,
            ``non_interactive``, ``force``, ``dry_run``, ``config``.

    Returns:
        ``0`` on success, ``1`` if any uninstall operation failed.
    """
    from syncode.config import SyncodeConfig
    from syncode.engine import SyncEngine
    from syncode.interactive import InteractiveSession
    from syncode.output import bold, warning

    config = SyncodeConfig.load(args.config)
    target_manager = _discover_targets(config)
    platforms = _resolve_platforms(args.target, config)

    item_types = _resolve_item_types(None)
    installed_items = _discover_installed_from_targets(
        target_manager,
        platforms,
        item_types,
    )

    # Apply --only / --except item-name filters
    only_set, except_set = _resolve_item_filter(args)
    installed_items = _apply_item_filter(installed_items, only_set, except_set)

    if not installed_items:
        warning("No installed items found.")
        return 0

    session: InteractiveSession | None = None

    # Interactive selection unless --yes
    if not args.non_interactive:
        session = InteractiveSession()
        installed_items = session.select_items(installed_items)
        if not installed_items:
            warning("No items selected.")
            return 0

    if not args.force:
        if session is None:
            session = InteractiveSession()
        if not session.confirm_action_or_abort(
            f"Uninstall {len(installed_items)} item(s)?",
        ):
            return 0

    engine = SyncEngine(target_manager=target_manager, dry_run=args.dry_run)
    report = engine.uninstall(installed_items, tuple(platforms))
    print()
    bold("Uninstall Summary:")
    print(f"  {report.summary()}")

    return 0 if report.is_success else 1


def cmd_clean(args: argparse.Namespace) -> int:
    """Remove orphaned items that are installed but no longer exist in source.

    Compares the set of items in the source repository against items installed
    on target platforms.  Any installed item whose source no longer exists is
    considered orphaned and eligible for removal.

    The command prompts for confirmation before removing anything, unless
    ``--yes`` is passed.  Supports ``--dry-run`` for a preview of what would
    be removed.

    Args:
        args: Parsed CLI namespace.  Relevant flags: ``source``, ``target``,
            ``item_type``, ``non_interactive``, ``dry_run``, ``config``,
            ``cache_dir``.

    Returns:
        ``0`` on success, ``1`` if any uninstall operation failed.
    """
    from syncode.config import SyncodeConfig
    from syncode.engine import SyncEngine
    from syncode.interactive import InteractiveSession
    from syncode.output import bold, info, warning
    from syncode.scanner import SourceScanner

    config = SyncodeConfig.load(args.config)
    source_dir = _get_source(args, config.cache_dir)

    scanner = SourceScanner(source_dir)
    all_source_items = scanner.scan()

    # Build a set of source item keys for fast lookup.
    source_keys: set[str] = {item.item_key for item in all_source_items}

    target_manager = _discover_targets(config)
    platforms = _resolve_platforms(args.target, config)
    item_types = _resolve_item_types(args.item_type)

    # Discover all installed items across target platforms.
    installed_items = _discover_installed_from_targets(
        target_manager,
        platforms,
        item_types,
    )

    if not installed_items:
        info("No installed items found.")
        return 0

    # Build a map: item_key → (Item, list of platforms where installed).
    installed_by_key: dict[str, tuple[Item, list[Platform]]] = {}
    for item in installed_items:
        key = item.item_key
        if key in installed_by_key:
            existing_item, existing_platforms = installed_by_key[key]
            existing_platforms.extend(item.supported_platforms)
        else:
            installed_by_key[key] = (item, list(item.supported_platforms))

    # Orphans = installed items whose source no longer exists.
    orphan_keys = sorted(set(installed_by_key.keys()) - source_keys)

    if not orphan_keys:
        info("No orphaned items found.")
        return 0

    # Filter orphans by requested item types.
    orphan_items: list[Item] = []
    orphan_platforms_map: dict[str, list[Platform]] = {}
    for key in orphan_keys:
        item, item_platforms = installed_by_key[key]
        if item.item_type in item_types:
            orphan_items.append(item)
            orphan_platforms_map[key] = [p for p in item_platforms if p in platforms]

    if not orphan_items:
        info("No orphaned items found (after type filter).")
        return 0

    # Display orphans with their platform coverage.
    print()
    bold(f"Found {len(orphan_items)} orphaned items:")
    for item in orphan_items:
        plat_names = sorted(p.display_name for p in orphan_platforms_map.get(item.item_key, []))
        plat_str = ", ".join(plat_names) if plat_names else "unknown"
        print(f"  {item.item_key}{' ' * max(1, 30 - len(item.item_key))}[{plat_str}]")

    if args.dry_run:
        print()
        warning("Dry-run mode: no changes were made.")
        return 0

    # Confirmation (unless --yes).
    if not args.non_interactive:
        session = InteractiveSession()
        if not session.confirm_action_or_abort(
            f"Remove {len(orphan_items)} orphaned items?",
        ):
            return 0

    # Reuse the uninstall pipeline.
    engine = SyncEngine(target_manager=target_manager)

    total_removed = 0
    total_platforms_used: set[str] = set()

    for item in orphan_items:
        item_platforms = orphan_platforms_map.get(item.item_key, [])
        if not item_platforms:
            continue
        report = engine.uninstall([item], tuple(item_platforms))
        if report.is_success:
            total_removed += sum(1 for r in report.uninstalled if r.is_success)
            for p in item_platforms:
                total_platforms_used.add(p.display_name)

    print()
    if total_removed:
        bold(f"Removed {total_removed} items from {len(total_platforms_used)} platform(s).")
    else:
        warning("No items were removed.")

    return 0


def cmd_init(args: argparse.Namespace) -> int:
    """Initialize a new agentfiles source repository structure.

    Creates ``agents/``, ``skills/``, ``commands/``, and ``plugins/``
    subdirectories with ``.gitkeep`` files, plus a ``.agentfiles.yaml``
    config file with sensible defaults and an empty
    ``.agentfiles.state.yaml`` for sync-state tracking.

    Args:
        args: Parsed CLI namespace.  Relevant flags: ``path``,
            ``non_interactive``.

    Returns:
        ``0`` on success.

    Raises:
        SyncodeError: On filesystem permission or I/O errors.
    """
    from syncode.interactive import InteractiveSession
    from syncode.models import SyncodeError
    from syncode.output import info, success

    base = Path(args.path).resolve()

    # Confirm unless --yes
    if not args.non_interactive:
        session = InteractiveSession()
        if not session.confirm_action_or_abort(f"Initialize agentfiles repo at {base}?"):
            return 0

    try:
        base.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise SyncodeError(
            f"Failed to create directory '{base}': {exc}. "
            f"Check that the parent path exists and is writable, "
            f"or run with appropriate permissions (e.g. no sudo if needed)"
        ) from exc

    created_dirs, skipped_dirs = _create_init_structure(base)

    config_path = base / ".agentfiles.yaml"
    if config_path.exists():
        info(f"Config already exists: {config_path}")
    else:
        config_content = (
            "# agentfiles configuration\ndefault_platforms:\n  - opencode\n  - claude_code\n"
        )
        try:
            config_path.write_text(config_content)
        except OSError as exc:
            raise SyncodeError(
                f"Failed to write config file '{config_path}': {exc}. "
                f"Check that the directory is writable and there is sufficient disk space"
            ) from exc

    state_path = base / ".agentfiles.state.yaml"
    if state_path.exists():
        info(f"State file already exists: {state_path}")
    else:
        state_content = (
            "# Sync state — auto-generated, do not edit manually\n"
            "# Use 'agentfiles pull', 'agentfiles push', or 'agentfiles sync'\n"
            'version: "1.0"\nlast_sync: ""\nplatforms: {}\n'
        )
        try:
            state_path.write_text(state_content)
        except OSError as exc:
            raise SyncodeError(
                f"Failed to write state file '{state_path}': {exc}. "
                f"Check that the directory is writable and there is sufficient disk space"
            ) from exc

    success(f"Initialized agentfiles repository at {base}")
    print()
    print("  Created directories:")
    for name in created_dirs:
        print(f"    + {name}/")
    for name in skipped_dirs:
        print(f"    ~ {name}/ (already exists)")
    print("  + .agentfiles.yaml")
    print("  + .agentfiles.state.yaml")

    return 0


def _list_branches_display(source_dir: Path) -> None:
    """Print a colourised list of git branches to stdout.

    The current branch is highlighted with ``*`` and green text.

    Args:
        source_dir: Local path to the git source repository.
    """
    from syncode.git import get_repo_name, list_branches
    from syncode.output import Colors, bold, colorize, warning

    repo_name = get_repo_name(source_dir)
    branches = list_branches(source_dir)

    bold(f"Repository: {repo_name}")
    bold(f"Branches ({len(branches)}):")
    for branch in branches:
        marker = "* " if branch.is_current else "  "
        name = colorize(branch.name, Colors.GREEN) if branch.is_current else branch.name
        print(f"  {marker}{name}")

    if not branches:
        warning("No branches found or not a git repository.")


def cmd_branch(args: argparse.Namespace) -> int:
    """Show or switch git branches in the source repository.

    Without ``--switch``, lists all branches and highlights the current one.
    With ``--switch BRANCH``, switches to the specified branch after
    confirmation (unless ``--yes``).

    Args:
        args: Parsed CLI namespace.  Relevant flags: ``source``,
            ``switch``, ``non_interactive``, ``cache_dir``.

    Returns:
        ``0`` on success, ``1`` if the branch switch failed.
    """
    from syncode.git import get_current_branch, switch_branch
    from syncode.interactive import InteractiveSession
    from syncode.output import error, info, success

    source_dir = _get_source(args)

    if not args.switch:
        _list_branches_display(source_dir)
        return 0

    # Switch branch
    target_branch = args.switch
    current_branch = get_current_branch(source_dir)
    if target_branch == current_branch:
        info(f"Already on branch '{target_branch}'.")
        return 0

    if not args.non_interactive:
        session = InteractiveSession()
        if not session.confirm_action_or_abort(f"Switch to branch '{target_branch}'?"):
            return 0

    info(f"Switching to branch '{target_branch}'...")
    if switch_branch(source_dir, target_branch):
        success(f"Now on branch '{target_branch}'.")
        return 0

    error(f"Failed to switch to branch '{target_branch}'.")
    return 1


def cmd_doctor(args: argparse.Namespace) -> int:
    """Diagnose common environment and configuration problems.

    Checks the local system for issues that prevent agentfiles from
    working correctly: missing config files, inaccessible platform
    directories, stale checksums, absent tool binaries, and git
    availability.

    Output is a formatted table of checks with status icons.  Exit code
    is ``0`` when all checks pass, ``1`` when any ERROR is found.

    Args:
        args: Parsed CLI namespace.  Relevant flags: ``config``,
            ``source``.

    Returns:
        ``0`` if all OK, ``1`` if any error.
    """
    from syncode.config import SyncodeConfig
    from syncode.doctor import format_doctor_report, run_doctor
    from syncode.source import SourceResolver

    config_path = getattr(args, "config", None)

    # Try to resolve source, but don't fail hard — doctor is for diagnostics.
    source_dir: Path | None = None
    try:
        source_arg = getattr(args, "source", None)
        config = SyncodeConfig.load(config_path)
        resolver = SourceResolver()
        source_info = resolver.detect(source_arg)
        cache_dir = getattr(args, "cache_dir", None) or config.cache_dir
        source_dir = resolver.resolve(
            source_info,
            cache_dir=Path(cache_dir) if cache_dir else None,
        )
    except Exception:
        # Doctor runs even when source cannot be resolved.
        pass

    report = run_doctor(config_path=config_path, source_dir=source_dir)
    output = format_doctor_report(report)
    print(output)
    return report.exit_code


def cmd_update(args: argparse.Namespace) -> int:
    """Update source repository and sync to local platforms in one step.

    Performs ``git pull`` in the source repository followed by the standard
    pull pipeline (scan -> plan -> execute).  This is the primary
    multi-machine workflow command (inspired by chezmoi's ``update``).

    If the source is not a git repository, prints an error and suggests
    running ``agentfiles pull`` instead.

    Args:
        args: Parsed CLI namespace.  Relevant flags: ``source``, ``target``,
            ``item_type``, ``non_interactive``, ``dry_run``, ``symlinks``,
            ``config``, ``cache_dir``.

    Returns:
        ``0`` on success, ``1`` if git pull or sync failed.
    """
    from syncode.config import SyncodeConfig
    from syncode.engine import SyncEngine
    from syncode.git import is_git_repo, pull_repo
    from syncode.interactive import InteractiveSession
    from syncode.output import bold, error, info, success, warning

    config = SyncodeConfig.load(args.config)
    source_dir = _get_source(args, config.cache_dir)

    if not is_git_repo(source_dir):
        error(
            "Source is not a git repository. "
            "Use 'agentfiles pull' to sync without updating the source."
        )
        return 1

    info("Updating source repository...")
    pull_result = pull_repo(source_dir)

    if not pull_result.success:
        error("git pull failed.")
        if pull_result.stdout.strip():
            print(pull_result.stdout.strip())
        if pull_result.stderr.strip():
            print(pull_result.stderr.strip())
        if pull_result.error_hint:
            print(f"  {pull_result.error_hint}")
        return 1

    for line in pull_result.stdout.strip().splitlines():
        if line.strip():
            print(f"  {line}")

    info("Syncing to platforms...")
    scanner, target_manager, engine = _create_sync_pipeline(
        source_dir,
        config,
        args,
    )

    all_items = scanner.scan()
    summary = scanner.get_summary()
    total = sum(summary.values())
    info(f"Found {total} item(s) in source")

    if not all_items:
        warning("No items found in source.")
        return 0

    item_types = _resolve_item_types(args.item_type)
    items = _filter_items(all_items, item_types)
    platforms = _resolve_platforms(args.target, config)

    if not args.non_interactive:
        result = _run_pull_interactive(items, target_manager, platforms)
        if result is None:
            return 0
        items, platforms = result

    plans = engine.plan_sync(items, tuple(platforms))

    needs_confirmation = plans and not args.non_interactive and not args.dry_run
    if needs_confirmation:
        session = InteractiveSession()
        if not session.confirm_plans_or_abort(plans):
            return 0

    if args.non_interactive and not args.dry_run:
        _display_update_indicators(plans)

    results = engine.execute_plan(plans)
    report = SyncEngine.aggregate(results)
    print()
    bold("Update Summary:")
    print(f"  {report.summary()}")

    if args.dry_run:
        warning("Dry-run mode: no changes were made.")
    elif any(r.is_success for r in results):
        from syncode.config import load_sync_state, save_sync_state

        sync_state = load_sync_state(source_dir)
        _update_sync_state_from_results(sync_state, results, target_manager)
        save_sync_state(source_dir, sync_state)

    synced_count = report.success_count
    platform_names = {p.display_name for p in platforms}
    print()
    success(f"Done. {synced_count} item(s) synced across {len(platform_names)} platform(s).")

    return 0 if report.is_success else 1


def cmd_show(args: argparse.Namespace) -> int:
    """Display the content of a specific item from the source repository.

    Performs a case-insensitive substring match against item names.  Prints
    the item's primary content file (e.g. an agent's system prompt or a
    skill's instruction file) to stdout.

    Args:
        args: Parsed CLI namespace.  Relevant flags: ``item_name``,
            ``source``, ``cache_dir``.

    Returns:
        ``0`` on success, ``1`` if the item was not found or matched
        multiple items ambiguously.
    """
    from syncode.output import error, info, warning
    from syncode.scanner import SourceScanner

    source_dir = _get_source(args, quiet=(getattr(args, "format", "text") == "json"))
    item_name = args.item_name

    scanner = SourceScanner(source_dir)
    items = scanner.scan()

    # Find matching item(s) by name (case-insensitive substring match)
    matches = [i for i in items if item_name.lower() in i.name.lower()]

    if not matches:
        error(f"Item '{item_name}' not found in source.")
        info(f"Available items: {', '.join(i.name for i in items)}")
        return 1

    if len(matches) > 1:
        warning(f"Multiple matches found for '{item_name}':")
        for m in matches:
            print(f"  {m.item_key}")
        info("Please be more specific.")
        return 1

    item = matches[0]
    fmt = getattr(args, "format", "text")
    if fmt == "json":
        from syncode.paths import read_item_content

        content_result = read_item_content(item.source_path)
        if content_result is None:
            error(f"No readable content found for {item.name}")
            return 1
        content, file_path = content_result
        return _format_show_json(item, content, file_path)

    _display_item_content(item)
    return 0


def _display_item_content(item: Item) -> None:
    """Read and print the primary content file for an item.

    Args:
        item: ``Item`` whose ``source_path`` will be read.
    """
    from syncode.output import error
    from syncode.paths import read_item_content

    result = read_item_content(item.source_path)
    if result is None:
        error(f"No readable content found for {item.name}")
        return

    content, file_path = result
    _print_content_header(item, file_path)
    print(content)


def _print_content_header(item: Item, file_path: Path) -> None:
    """Print a formatted metadata header before the item's content.

    Shows the item type icon, key (``type/name``), version, source file
    path, and supported platforms — all in styled terminal output.

    Args:
        item: ``Item`` whose metadata is displayed.
        file_path: Path to the content file being shown.
    """
    from syncode.output import ITEM_TYPE_ICONS, bold, dim

    icon = ITEM_TYPE_ICONS.get(item.item_type, "?")
    bold(f"{icon} {item.item_key}")
    if item.version:
        dim(f"  Version: {item.version}")
    dim(f"  File: {file_path}")
    dim(f"  Platforms: {', '.join(p.display_name for p in item.supported_platforms)}")
    print()


def _update_sync_state_from_results(
    state: SyncState,
    results: list[SyncResult],
    target_manager: TargetManager,
) -> None:
    """Update sync state based on successful pull/push results.

    For each successful result, records the current source and target
    checksums in the state file.  This enables future ``cmd_sync`` calls
    to perform three-way comparison (source vs. target vs. last-synced)
    and correctly classify items as needing pull, push, or manual
    conflict resolution.

    Args:
        state: Mutable ``SyncState`` object loaded from
            ``.agentfiles.state.yaml``.
        results: ``SyncResult`` objects from the engine execution.
        target_manager: Used to reverse-lookup platforms from target dirs.
    """
    import contextlib
    from datetime import datetime, timezone

    from syncode.models import ItemState, PlatformState, compute_checksum
    from syncode.paths import get_item_dest_path

    for result in results:
        if not result.is_success:
            continue

        plan = result.plan
        item = plan.item
        platform = target_manager.resolve_platform_for(
            item.item_type,
            plan.target_dir,
        )
        if platform is None:
            continue

        platform_key = platform.value
        if platform_key not in state.platforms:
            state.platforms[platform_key] = PlatformState(
                path=str(plan.target_dir),
            )

        item_key = item.item_key
        source_hash = item.checksum
        target_path = get_item_dest_path(plan.target_dir, item)
        # Compute target-side checksum; tolerate missing/unreadable files
        # gracefully rather than aborting the entire state update.
        target_hash = ""
        if target_path.exists():
            with contextlib.suppress(Exception):
                target_hash = compute_checksum(target_path)

        state.platforms[platform_key].items[item_key] = ItemState(
            source_hash=source_hash,
            target_hash=target_hash,
            synced_at=datetime.now(timezone.utc).isoformat(),
        )

    state.last_sync = datetime.now(timezone.utc).isoformat()


def cmd_sync(args: argparse.Namespace) -> int:
    """Perform a smart bidirectional sync between repository and local configs.

    Uses checksums stored in ``.agentfiles.state.yaml`` to classify each
    item as needing a **pull** (source changed), **push** (target changed),
    or **conflict** (both sides changed since last sync).  Executes the
    appropriate operations and persists the updated state file.

    In non-interactive mode (``--yes``) conflicts are silently skipped.

    Args:
        args: Parsed CLI namespace.  Relevant flags: ``source``,
            ``target``, ``item_type``, ``non_interactive``, ``dry_run``,
            ``config``, ``cache_dir``.

    Returns:
        ``0`` on success, ``1`` if any operation failed.
    """
    from syncode.config import SyncodeConfig, load_sync_state, save_sync_state
    from syncode.engine import SyncEngine
    from syncode.interactive import InteractiveSession
    from syncode.output import bold, info, warning

    config = SyncodeConfig.load(args.config)
    source_dir = _get_source(args, config.cache_dir)
    scanner, target_manager, engine = _create_sync_pipeline(source_dir, config, args)

    sync_state = load_sync_state(source_dir)

    all_items = scanner.scan()
    item_types = _resolve_item_types(args.item_type)
    items = _filter_items(all_items, item_types)

    # Apply --only / --except item-name filters
    only_set, except_set = _resolve_item_filter(args)
    items = _apply_item_filter(items, only_set, except_set)

    platforms = _resolve_platforms(args.target, config)

    sync_plan = engine.compute_sync_plan(
        items,
        tuple(platforms),
        sync_state,
        source_dir,
    )

    if not sync_plan:
        info("Everything is already in sync.")
        return 0

    pull_count = sum(1 for _, _, a in sync_plan if a == "pull")
    push_count = sum(1 for _, _, a in sync_plan if a == "push")
    # Remaining items in the plan are conflicts by elimination.
    conflict_count = len(sync_plan) - pull_count - push_count

    if args.non_interactive:
        # Auto-pull/push, skip conflicts.
        skip_conflicts = True
    else:
        session = InteractiveSession()
        if not session.confirm_action_or_abort(
            f"Sync {pull_count} pull(s), {push_count} push(es), {conflict_count} conflict(s)?",
        ):
            return 0
        skip_conflicts = False

    # Execute sync plan: pull items, push items, handle conflicts.
    all_results = _execute_sync_actions(
        sync_plan,
        tuple(platforms),
        engine,
        source_dir,
        args.dry_run,
        skip_conflicts,
    )

    report = SyncEngine.aggregate(all_results)
    print()
    bold("Sync Summary:")
    print(f"  {report.summary()}")

    if args.dry_run:
        warning("Dry-run mode: no changes were made.")
    else:
        _update_sync_state_from_results(
            sync_state,
            all_results,
            target_manager,
        )
        save_sync_state(source_dir, sync_state)

    return 0 if report.is_success else 1


# ---------------------------------------------------------------------------
# Command dispatch map (single source of truth)
# ---------------------------------------------------------------------------

_COMMAND_MAP: dict[str, Callable[[argparse.Namespace], int]] = {
    "pull": cmd_pull,
    "push": cmd_push,
    "adopt": cmd_adopt,
    "sync": cmd_sync,
    "status": cmd_status,
    "list": cmd_list,
    "diff": cmd_diff,
    "verify": cmd_verify,
    "clean": cmd_clean,
    "doctor": cmd_doctor,
    "uninstall": cmd_uninstall,
    "init": cmd_init,
    "branch": cmd_branch,
    "update": cmd_update,
    "show": cmd_show,
    "completion": cmd_completion,
}


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------


def _add_common_args(
    parser: argparse.ArgumentParser,
) -> dict[str, argparse._ArgumentGroup]:
    """Add the shared set of CLI arguments used by most subcommands.

    Arguments are organised into named groups for cleaner ``--help`` output:

    * **Source options** — ``source``, ``--config``, ``--cache-dir``
    * **Filter options** — ``--target``, ``--type``, ``--only``, ``--except``
    * **Output options** — ``--dry-run``
    * **Sync options**  — ``--yes``

    Args:
        parser: The sub-parser to attach arguments to.

    Returns:
        Mapping of group names (``"source"``, ``"filter"``, ``"output"``,
        ``"sync"``) to their ``_ArgumentGroup`` objects so that callers
        can attach additional arguments to the same visual section.
    """
    from syncode.models import PLATFORM_NAMES

    source_group = parser.add_argument_group("Source options")
    source_group.add_argument(
        "source",
        nargs="?",
        default=None,
        help="Source: URL, git repo, or local directory (auto-detected)",
    )
    source_group.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Path to config file",
    )
    source_group.add_argument(
        "--cache-dir",
        type=str,
        default=None,
        help="Cache directory for git clones",
    )

    filter_group = parser.add_argument_group("Filter options")
    filter_group.add_argument(
        "--target",
        choices=sorted(PLATFORM_NAMES) + ["all"],
        default=None,
        help="Target platform(s)",
    )
    filter_group.add_argument(
        "--type",
        choices=["agent", "skill", "command", "plugin", "all"],
        default=None,
        dest="item_type",
        help="Filter by item type",
    )
    filter_group.add_argument(
        "--only",
        metavar="ITEMS",
        default=None,
        help="Only sync these items (comma-separated: coder,solid-principles)",
    )
    filter_group.add_argument(
        "--except",
        metavar="ITEMS",
        default=None,
        dest="except_items",
        help="Exclude these items from sync (comma-separated: old-plugin,deprecated)",
    )

    output_group = parser.add_argument_group("Output options")
    output_group.add_argument(
        "--dry-run",
        "-n",
        action="store_true",
        help="Preview changes without applying",
    )

    sync_group = parser.add_argument_group("Sync options")
    sync_group.add_argument(
        "--yes",
        "-y",
        action="store_true",
        dest="non_interactive",
        help="Non-interactive mode (accept all defaults, no prompts)",
    )

    return {
        "source": source_group,
        "filter": filter_group,
        "output": output_group,
        "sync": sync_group,
    }


def _add_format_arg(
    parser: argparse.ArgumentParser,
    group: argparse._ArgumentGroup | None = None,
) -> None:
    """Add the ``--format {text,json}`` flag for structured-output commands.

    Args:
        parser: The sub-parser to attach the argument to.
        group: Optional argument group to add the flag to.  When ``None``
            the flag is added directly to *parser*.
    """
    target = group or parser
    target.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Output format",
    )


def build_parser() -> argparse.ArgumentParser:
    """Construct the top-level ``argparse`` parser with all subcommands.

    Defines global flags (``--version``, ``--verbose``, ``--quiet``, ``--color``)
    and registers every sub-command with grouped arguments and usage examples.

    Returns:
        Fully configured ``ArgumentParser`` ready for ``parse_args()``.
    """
    from syncode import __version__

    parser = argparse.ArgumentParser(
        prog="agentfiles",
        description=(
            "Sync AI tool configurations (agents, skills, commands, plugins) across platforms."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
examples:
  agentfiles pull                    Sync all items to all platforms
  agentfiles pull --target opencode  Sync only to OpenCode
  agentfiles pull --type agent       Sync only agents
  agentfiles pull --only coder       Sync only the coder agent
  agentfiles pull --dry-run          Preview what would change
  agentfiles push                    Push local items back to source
  agentfiles sync                    Bidirectional smart sync
  agentfiles update                  Git pull + sync in one step
  agentfiles verify                  Check for drift (CI-friendly)
  agentfiles status                  Show installed items per platform
  agentfiles list --tokens           List items with token counts
  agentfiles diff                    Compare source vs installed
  agentfiles clean                   Remove orphaned items
  agentfiles doctor                  Diagnose common issues
  agentfiles init                    Initialize a new repository
  agentfiles show coder              Display an agent's prompt
""",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"agentfiles {__version__}",
    )

    # Global flags
    global_group = parser.add_argument_group("Global options")
    global_group.add_argument(
        "--color",
        choices=["always", "auto", "never"],
        default="auto",
        help="When to use colors: always, auto (default), never",
    )
    global_group.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    global_group.add_argument("--quiet", "-q", action="store_true", help="Quiet mode (errors only)")

    subs = parser.add_subparsers(dest="command")

    # pull
    pull_p = subs.add_parser(
        "pull",
        help="Pull items from repository to local configs",
        description="Scan source repository and sync items to target platforms.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
examples:
  agentfiles pull                              Sync all items interactively
  agentfiles pull --yes                        Non-interactive, accept all
  agentfiles pull --dry-run --verbose          Preview with detailed output
  agentfiles pull --target opencode --type agent  Only agents to OpenCode
  agentfiles pull --only coder,solid-principles   Sync specific items
""",
    )
    pull_groups = _add_common_args(pull_p)
    pull_groups["sync"].add_argument(
        "--symlinks",
        action="store_true",
        help="Use symlinks instead of copying",
    )
    _add_format_arg(pull_p, group=pull_groups["output"])

    # push
    push_p = subs.add_parser(
        "push",
        help="Push items from local configs back to the source repository",
        description="Discover installed items from target platforms and push them back to source.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
examples:
  agentfiles push                              Push all installed items interactively
  agentfiles push --yes                        Non-interactive, accept all
  agentfiles push --dry-run                    Preview what would be pushed
  agentfiles push --target opencode            Push only from OpenCode
""",
    )
    push_groups = _add_common_args(push_p)
    push_groups["sync"].add_argument(
        "--symlinks",
        action="store_true",
        help="Use symlinks instead of copying",
    )
    _add_format_arg(push_p, group=push_groups["output"])

    # adopt
    adopt_p = subs.add_parser(
        "adopt",
        help="Adopt items from target platforms into the source repository",
        description=(
            "Discover items installed on target platforms that don't exist in "
            "the source repository and copy them in."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
examples:
  agentfiles adopt                              Adopt all new items interactively
  agentfiles adopt --yes                        Non-interactive, accept all
  agentfiles adopt --dry-run                    Preview what would be adopted
  agentfiles adopt --target opencode            Adopt only from OpenCode
  agentfiles adopt --type agent                 Adopt only agents
""",
    )
    _add_common_args(adopt_p)

    # sync (smart bidirectional)
    sync_p = subs.add_parser(
        "sync",
        help="Smart bidirectional sync between repository and local configs",
        description="Three-way bidirectional sync using checksums from .agentfiles.state.yaml.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
examples:
  agentfiles sync                              Interactive bidirectional sync
  agentfiles sync --yes                        Non-interactive, auto-resolve
  agentfiles sync --dry-run                    Preview sync actions
  agentfiles sync --type skill                 Sync only skills
""",
    )
    _add_common_args(sync_p)

    # status
    status_p = subs.add_parser(
        "status",
        help="Show status of installed items",
        description="Display a table of installed-item counts per discovered platform.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
examples:
  agentfiles status                            Show all platforms
  agentfiles status --config custom.yaml       Use custom config file
""",
    )
    status_src = status_p.add_argument_group("Source options")
    status_src.add_argument("--config", type=Path, default=None, help="Path to config file")
    _add_format_arg(status_p)

    # list
    list_p = subs.add_parser(
        "list",
        help="List available items in source",
        description="List items available in the source repository with optional token estimates.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
examples:
  agentfiles list                              List all items
  agentfiles list --tokens                     Show token estimates
  agentfiles list --format json                JSON output for scripting
  agentfiles list --type agent                 Only agents
  agentfiles list --tokens --format json       Full JSON with token counts
""",
    )
    list_groups = _add_common_args(list_p)
    _add_format_arg(list_p, group=list_groups["output"])
    list_groups["output"].add_argument(
        "--tokens",
        action="store_true",
        help="Show estimated token counts for each item",
    )

    # diff
    diff_p = subs.add_parser(
        "diff",
        help="Show differences between source and target",
        description="Compare source items against installed counterparts on each target platform.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
examples:
  agentfiles diff                              Compare all platforms
  agentfiles diff --target opencode            Compare only OpenCode
  agentfiles diff --format json                JSON output for scripting
  agentfiles diff --type skill                 Compare only skills
  agentfiles diff --verbose                    Show content-level differences
""",
    )
    diff_groups = _add_common_args(diff_p)
    _add_format_arg(diff_p, group=diff_groups["output"])
    diff_groups["output"].add_argument(
        "--verbose",
        action="store_true",
        dest="verbose_diff",
        help="Show content-level unified diff for changed items",
    )

    # verify
    verify_p = subs.add_parser(
        "verify",
        help="Verify installed items match source checksums (CI-friendly)",
        description=(
            "Check that installed items match source checksums. Exits 0 on match, 1 on drift."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
examples:
  agentfiles verify                            Verify all platforms
  agentfiles verify --target opencode          Verify only OpenCode
  agentfiles verify --format json              JSON output (CI-friendly)
""",
    )
    verify_groups = _add_common_args(verify_p)
    _add_format_arg(verify_p, group=verify_groups["output"])

    # uninstall
    uninstall_p = subs.add_parser(
        "uninstall",
        help="Remove installed items from targets",
        description="Remove installed items from target platform config directories.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
examples:
  agentfiles uninstall                         Interactive item removal
  agentfiles uninstall --yes --force           Non-interactive, skip confirmation
  agentfiles uninstall --dry-run               Preview removals
""",
    )
    uninstall_groups = _add_common_args(uninstall_p)
    uninstall_groups["sync"].add_argument(
        "--force",
        "-f",
        action="store_true",
        help="Skip confirmation prompt",
    )

    # clean
    clean_p = subs.add_parser(
        "clean",
        help="Remove orphaned items that no longer exist in source",
        description=(
            "Remove items installed on target platforms that have been deleted from source."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
examples:
  agentfiles clean                             Interactive cleanup
  agentfiles clean --yes                       Non-interactive cleanup
  agentfiles clean --dry-run                   Preview what would be removed
""",
    )
    _add_common_args(clean_p)

    # init
    init_p = subs.add_parser(
        "init",
        help="Initialize a new agentfiles source repository",
        description="Scaffold a new agentfiles repository with standard directory layout.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
examples:
  agentfiles init                              Init in current directory
  agentfiles init /path/to/project             Init in specific directory
  agentfiles init --yes                        Skip confirmation
""",
    )
    init_p.add_argument(
        "path",
        nargs="?",
        default=".",
        help="Directory to initialize (default: current directory)",
    )
    init_p.add_argument(
        "--yes",
        "-y",
        action="store_true",
        dest="non_interactive",
        help="Non-interactive mode (skip confirmation)",
    )

    # branch
    branch_p = subs.add_parser(
        "branch",
        help="Show or switch git branches",
        description="List or switch git branches in the source repository.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
examples:
  agentfiles branch                            List all branches
  agentfiles branch --switch main              Switch to main branch
  agentfiles branch --switch feature-x --yes   Non-interactive switch
""",
    )
    branch_groups = _add_common_args(branch_p)
    branch_groups["sync"].add_argument(
        "--switch",
        "-s",
        type=str,
        default=None,
        metavar="BRANCH",
        help="Switch to the specified branch",
    )

    # update
    update_p = subs.add_parser(
        "update",
        help="Update source repository (git pull) and sync to local platforms",
        description="Pull latest changes from git remote, then sync items to target platforms.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
examples:
  agentfiles update                            Git pull + sync interactively
  agentfiles update --yes                      Non-interactive update
  agentfiles update --dry-run                  Preview update actions
""",
    )
    update_groups = _add_common_args(update_p)
    update_groups["sync"].add_argument(
        "--symlinks",
        action="store_true",
        help="Use symlinks instead of copying",
    )

    # show
    show_p = subs.add_parser(
        "show",
        help="Show content of an item (agent prompt, skill file)",
        description="Display the primary content file of a specific item from source.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
examples:
  agentfiles show coder                        Display the coder agent prompt
  agentfiles show solid                        Match by partial name
  agentfiles show --source /path my-agent      Use explicit source path
""",
    )
    show_p.add_argument(
        "item_name",
        type=str,
        help="Name of the item to show (partial match supported)",
    )
    show_p.add_argument(
        "--source",
        type=str,
        default=None,
        help="Source repository path (default: auto-detect from CWD)",
    )
    _add_format_arg(show_p)

    # completion
    comp_p = subs.add_parser(
        "completion",
        help="Generate shell completion scripts",
        description="Generate shell completion scripts for bash, zsh, and fish.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
examples:
  agentfiles completion bash > ~/.local/share/bash-completion/completions/agentfiles
  agentfiles completion zsh > ~/.zfunc/_agentfiles
  agentfiles completion fish > ~/.config/fish/completions/agentfiles.fish
  eval "$(agentfiles completion bash)"  # Or source in .bashrc
""",
    )
    comp_p.add_argument(
        "shell",
        choices=["bash", "zsh", "fish"],
        help="Target shell",
    )

    # doctor
    doctor_p = subs.add_parser(
        "doctor",
        help="Diagnose common environment and configuration problems",
        description="Check for common issues with installed platforms, configs, and paths.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
examples:
  agentfiles doctor                            Run all diagnostics
  agentfiles doctor --config custom.yaml       Use custom config file
""",
    )
    doctor_src = doctor_p.add_argument_group("Source options")
    doctor_src.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Path to config file",
    )
    doctor_src.add_argument(
        "source",
        nargs="?",
        default=None,
        help="Source directory (auto-detected from CWD)",
    )
    doctor_src.add_argument(
        "--cache-dir",
        type=str,
        default=None,
        help="Cache directory for git clones",
    )

    return parser


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Entry point for the ``agentfiles`` CLI.

    Parses command-line arguments and dispatches to the appropriate
    ``cmd_*`` handler.  When no subcommand is given, prints a help
    message and exits with code 2.

    Exit codes:

    - ``0`` — success
    - ``1`` — application error (``SyncodeError`` or unexpected exception)
    - ``2`` — usage error (no subcommand provided)
    - ``130`` — interrupted by ``Ctrl-C``
    """
    from syncode.models import SyncodeError
    from syncode.output import error, init_logging, warning

    parser = build_parser()
    args = parser.parse_args()

    # Apply --color flag before any output initialisation.
    # Sets NO_COLOR / FORCE_COLOR env vars so that init_logging()
    # and all downstream output helpers respect the user's choice.
    color = getattr(args, "color", "auto")
    _apply_color_env(color)

    init_logging(verbose=args.verbose, quiet=args.quiet)

    if not args.command:
        parser.print_help()
        sys.exit(2)

    handler = _COMMAND_MAP.get(args.command)
    if handler is None:
        error(f"Unknown command: {args.command}")
        sys.exit(1)

    try:
        code = handler(args)
    except KeyboardInterrupt:
        warning("\nAborted.")
        code = 130
    except SyncodeError as exc:
        error(f"{exc}")
        code = 1
    except Exception as exc:
        logger.exception("Unexpected error")
        error(f"Error: {exc}")
        code = 1

    sys.exit(code)


if __name__ == "__main__":
    main()
