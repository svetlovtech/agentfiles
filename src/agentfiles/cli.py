"""Command-line interface for the agentfiles tool.

Exposes a single ``agentfiles`` CLI entry-point that orchestrates scanning,
synchronisation, and interactive workflows across AI tool platforms
(OpenCode, Claude Code, Cursor, Windsurf, etc.).

Subcommands:

- ``agentfiles pull``       — Install/update items from a source repository to
  local platform configs.  Interactive by default; pass ``--yes`` for
  non-interactive mode.  Use ``--update`` to run ``git pull`` on the source
  before syncing.
- ``agentfiles push``       — Push locally-installed items back into the source
  repository.  Discovers items from target platforms so it works even when
  the source repo is empty.
- ``agentfiles status``     — Show installed-item counts per discovered
  platform.  Use ``--list`` to list source items, ``--diff`` to compare
  source vs installed.
- ``agentfiles clean``      — Remove orphaned items (installed items whose
  source no longer exists in the repository).
- ``agentfiles init``       — Scaffold a new agentfiles repository with
  ``agents/``, ``skills/``, ``commands/``, ``plugins/`` directories and a
  ``.agentfiles.yaml`` config file.

Common usage patterns::

    # Pull everything interactively (default)
    agentfiles pull

    # Pull in CI / scripting mode
    agentfiles pull --yes --target opencode

    # Pull with git update first
    agentfiles pull --update

    # List items with token estimates
    agentfiles status --list --tokens

    # Compare source vs installed
    agentfiles status --diff

When invoked with no subcommand, a help message is printed and the process
exits with code 2.

**Performance note:** All ``agentfiles.*`` imports are deferred to function scope
so that ``import agentfiles.cli`` completes in < 1 ms.  Heavy modules (models,
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

if TYPE_CHECKING:
    from agentfiles.config import AgentfilesConfig
    from agentfiles.engine import SyncEngine
    from agentfiles.models import (
        Item,
        ItemType,
        Platform,
        SyncPlan,
        SyncResult,
        SyncState,
        TokenEstimate,
    )
    from agentfiles.scanner import SourceScanner
    from agentfiles.target import TargetManager

from agentfiles.cli_format import (  # noqa: F401
    _format_list_json,
    _format_plan_json,
    _format_results_json,
    _format_status_json,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _resolve_platforms(
    target_flag: str | None,
    config: AgentfilesConfig,
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
        config: Loaded ``AgentfilesConfig`` providing ``default_platforms``.

    Returns:
        List of ``Platform`` enums to operate on.

    """
    from agentfiles.models import Platform, resolve_platform

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
    from agentfiles.models import ItemType

    if type_flag == "all" or type_flag is None:
        return list(ItemType)
    try:
        return [ItemType(type_flag)]
    except ValueError:
        from agentfiles.output import warning

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


def _discover_targets(config: AgentfilesConfig) -> TargetManager:
    """Discover installed AI tool platforms and build a ``TargetManager``.

    Scans common install paths for OpenCode, Claude Code, Cursor, Windsurf,
    etc.  Custom paths from the config override the defaults.

    Args:
        config: Loaded ``AgentfilesConfig`` (may provide ``custom_paths``).

    Returns:
        A ``TargetManager`` with at least one discovered platform.

    Raises:
        AgentfilesError: When no platforms are discovered on the system.

    """
    from agentfiles.models import AgentfilesError
    from agentfiles.target import build_target_manager

    target_manager = build_target_manager(config.custom_paths)

    if not target_manager.targets:
        raise AgentfilesError(
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
            that have already loaded a :class:`AgentfilesConfig`.

    Returns:
        Local ``Path`` to the resolved source directory.

    Raises:
        SourceError: When the source cannot be detected or resolved.

    """
    from agentfiles.models import SourceError
    from agentfiles.output import info
    from agentfiles.source import SourceResolver

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
    config: AgentfilesConfig,
    args: argparse.Namespace,
) -> tuple[SourceScanner, TargetManager, SyncEngine]:
    """Create the configured scanner, target manager, and sync engine.

    Shared by ``cmd_pull``, ``cmd_push``, and ``cmd_sync`` to avoid
    duplicating pipeline setup.

    Args:
        source_dir: Resolved local path to the source repository.
        config: Loaded ``AgentfilesConfig``.
        args: Parsed CLI namespace (reads ``symlinks`` and ``dry_run``).

    Returns:
        ``(scanner, target_manager, engine)`` tuple ready for use.

    """
    from agentfiles.engine import SyncEngine
    from agentfiles.scanner import SourceScanner

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

    config: AgentfilesConfig
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
    from agentfiles.config import AgentfilesConfig

    config = AgentfilesConfig.load(getattr(args, "config", None))

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
    from agentfiles.models import TargetError

    result = []
    for item in items:
        for platform in platforms:
            try:
                is_installed = target_manager.is_item_installed(item, platform)
            except TargetError:
                continue
            if is_installed == installed:
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
    from agentfiles.models import Item, TargetError
    from agentfiles.paths import get_installed_item_path

    # Collect (item_type, name) → (first on-disk path, all platforms).
    registry: dict[tuple[ItemType, str], tuple[Path, list[Platform]]] = {}

    for platform in platforms:
        try:
            installed = target_manager.get_installed_items(platform)
        except TargetError:
            # Platform not discovered on this machine — skip gracefully.
            continue
        for item_type, name in installed:
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
    from agentfiles.interactive import InteractiveSession
    from agentfiles.output import info, warning

    session = InteractiveSession()
    try:
        mode = session.choose_sync_mode()
    except KeyboardInterrupt:
        print()
        warning("Aborted.")
        return None

    if mode == "custom":
        try:
            selected_platforms = session.select_platforms(platforms)
        except KeyboardInterrupt:
            print()
            warning("Aborted.")
            return None
        if not selected_platforms:
            warning("No platforms selected.")
            return None
        platforms = selected_platforms

        try:
            selected_types = session.select_item_types()
        except KeyboardInterrupt:
            print()
            warning("Aborted.")
            return None
        items = _filter_items(items, selected_types)
        if not items:
            warning("No items selected.")
            return None

        try:
            items = session.select_items(items)
        except KeyboardInterrupt:
            print()
            warning("Aborted.")
            return None
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


def _print_token_summary(
    estimates: list[TokenEstimate],
    name_desc_total: int = 0,
) -> None:
    """Print an aggregate token-count summary table to stdout.

    Args:
        estimates: List of ``TokenEstimate`` objects to aggregate.
        name_desc_total: Aggregate name+description token count.

    """
    from agentfiles.output import bold

    total = sum(e.total_tokens for e in estimates)
    content_total = sum(e.content_tokens for e in estimates)
    overhead_total = sum(e.overhead_tokens for e in estimates)
    print()
    bold("Token Summary:")
    print(f"  Items: {len(estimates)}")
    print(f"  Content tokens: ~{content_total:,}")
    print(f"  Overhead tokens: ~{overhead_total:,}")
    print(f"  Total tokens: ~{total:,}")
    if name_desc_total > 0:
        print(f"  Name + Description tokens: ~{name_desc_total:,}")


def _format_list_text(items: list[Any], show_tokens: bool) -> int:
    """Format items as grouped, colourised text and print to stdout.

    Items are grouped by type (agents, skills, …) and sorted alphabetically
    within each group.  Token estimates are computed only for agents and
    skills.  An aggregate token summary is printed at the end when
    *show_tokens* is ``True`` and at least one agent or skill exists.

    Args:
        items: Items to display.
        show_tokens: If ``True``, include per-item and aggregate token counts.

    Returns:
        Exit code (always ``0``).
    """
    from agentfiles.models import _DEFAULT_VERSION, ItemType
    from agentfiles.output import Colors, bold, colorize
    from agentfiles.tokens import estimate_name_description_tokens, token_estimate

    current_type: ItemType | None = None
    estimates: list[TokenEstimate] = []
    name_desc_total = 0

    for item in sorted(items, key=lambda i: i.sort_key):
        if item.item_type != current_type:
            current_type = item.item_type
            print()
            bold(f"{current_type.plural}:")
        ver = f"  v{item.version}" if item.version != _DEFAULT_VERSION else ""
        if show_tokens and item.item_type in (ItemType.AGENT, ItemType.SKILL):
            est = token_estimate(item)
            estimates.append(est)
            name_desc_total += estimate_name_description_tokens(item)
            print(
                f"  {colorize(item.name, Colors.GREEN)}{ver}  "
                f"({len(item.files)} files)  "
                f"~{est.total_tokens:,} tokens"
            )
        else:
            print(f"  {colorize(item.name, Colors.GREEN)}{ver}  ({len(item.files)} files)")

    if show_tokens and estimates:
        _print_token_summary(estimates, name_desc_total)

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
        AgentfilesError: When directory or file creation fails due to
            permission or filesystem errors.
    """
    from agentfiles.models import AgentfilesError, ItemType

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
                raise AgentfilesError(
                    f"Failed to create directory '{subdir}': {exc}. "
                    f"Check that the parent directory exists and is writable, "
                    f"or run with appropriate permissions"
                ) from exc
            created_dirs.append(subdir_name)

    return created_dirs, skipped_dirs


def _display_update_indicators(plans: list[SyncPlan]) -> None:
    """Show diff indicators for items that will be updated.

    In non-interactive mode the user does not see a confirmation prompt,
    so this function prints explicit ``~ item_name`` lines for every plan
    whose action is ``UPDATE`` so the user knows which items changed.

    Args:
        plans: List of ``SyncPlan`` objects from the engine.
    """
    from agentfiles.models import SyncAction

    update_plans = [p for p in plans if p.action == SyncAction.UPDATE]
    if not update_plans:
        return
    print()
    for plan in update_plans:
        file_count = len(plan.item.files) if plan.item.files else 0
        file_info = f" — {file_count} files" if file_count else ""
        print(f"  ~ {plan.item.name} (content differs{file_info})")


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

    With ``--update`` / ``-u``, runs ``git pull`` on the source repository
    before scanning and syncing items.

    Args:
        args: Parsed CLI namespace.  Relevant flags: ``source``, ``target``,
            ``item_type``, ``non_interactive``, ``dry_run``, ``symlinks``,
            ``config``, ``cache_dir``, ``update``.

    Returns:
        ``0`` on success, ``1`` if any operation failed.
    """
    from agentfiles.engine import SyncEngine
    from agentfiles.interactive import InteractiveSession
    from agentfiles.output import bold, format_item_count, info, warning

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

    # --update: git pull first
    if getattr(args, "update", False):
        from agentfiles.git import is_git_repo, pull_repo

        if is_git_repo(source_dir):
            info("Updating source repository...")
            pull_repo(source_dir)
        else:
            warning("Source is not a git repository, --update ignored")

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
        from agentfiles.config import load_sync_state, save_sync_state

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


def _print_push_report(report: object, dry_run: bool) -> None:
    """Display a detailed push report grouped by diff status.

    Args:
        report: The SyncReport containing push results.
        dry_run: Whether this was a dry-run operation.
    """
    from agentfiles.output import bold, error, success, warning

    all_results = report.installed + report.updated + report.skipped + report.failed  # type: ignore[attr-defined]

    # Group by push_status.
    new_items: list[str] = []
    changed_items: list[tuple[str, str]] = []
    unchanged_count = 0
    failed_items: list[tuple[str, str]] = []

    for result in all_results:
        key = result.plan.item.item_key
        status = getattr(result, "push_status", "")
        detail = getattr(result, "push_detail", "")
        if not result.is_success:
            failed_items.append((key, result.message))
        elif status == "new":
            new_items.append(key)
        elif status == "changed":
            changed_items.append((key, detail))
        elif status == "unchanged":
            unchanged_count += 1
        else:
            # Fallback: treat successful items without a status as updated.
            new_items.append(key)

    bold("Push Summary:")
    if new_items:
        success(f"  + New ({len(new_items)})")
        for name in sorted(new_items):
            print(f"    {name}")
    if changed_items:
        success(f"  ~ Changed ({len(changed_items)})")
        for name, detail in sorted(changed_items):
            line = f"    {name}"
            if detail:
                line += f"  {detail}"
            print(line)
    if unchanged_count:
        print(f"  = Unchanged ({unchanged_count})")
    if failed_items:
        error(f"  x Failed ({len(failed_items)})")
        for name, msg in sorted(failed_items):
            print(f"    {name}: {msg}")

    # Custom summary based on push status, not SyncReport action.
    parts: list[str] = []
    if new_items:
        parts.append(f"New {len(new_items)}")
    if changed_items:
        parts.append(f"Changed {len(changed_items)}")
    if unchanged_count:
        parts.append(f"Unchanged {unchanged_count}")
    if failed_items:
        parts.append(f"Failed {len(failed_items)}")
    if parts:
        bold(f"  {', '.join(parts)}")
    if dry_run:
        warning("Dry-run mode: no changes were made.")


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
    from agentfiles.config import AgentfilesConfig
    from agentfiles.interactive import InteractiveSession
    from agentfiles.output import info, warning

    config = AgentfilesConfig.load(args.config)
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
        try:
            installed_items = session.select_items(installed_items, source_dir=source_dir)
        except KeyboardInterrupt:
            print()
            warning("Aborted.")
            return 1
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
    _print_push_report(report, args.dry_run)

    return 0 if report.is_success else 1


def cmd_status(args: argparse.Namespace) -> int:
    """Display a table of installed-item counts per discovered platform.

    Shows the platform name, config directory path, and number of agents,
    skills, commands, and plugins installed for each platform found on the
    system.

    With ``--list``, lists items available in the source repository instead
    of showing the platform table.  Supports ``--tokens`` for token-cost
    estimates and ``--format json`` for machine-readable output.

    With ``--diff``, shows differences between source items and their
    installed counterparts on target platforms.  Supports ``--verbose``
    for content-level diffs.

    Args:
        args: Parsed CLI namespace.  Relevant flags: ``config``,
            ``list_items``, ``tokens``, ``show_diff``, ``verbose_diff``,
            ``item_type``, ``source``, ``target``, ``format``.

    Returns:
        ``0`` on success.
    """
    from agentfiles.config import AgentfilesConfig

    # --list mode: list source items
    if getattr(args, "list_items", False):
        from agentfiles.scanner import SourceScanner

        source_dir = _get_source(
            args,
            quiet=(getattr(args, "format", "text") == "json"),
        )
        scanner = SourceScanner(source_dir)
        item_types = _resolve_item_types(args.item_type)
        items = _scan_filtered(scanner, item_types)
        show_tokens = getattr(args, "tokens", False)
        fmt = getattr(args, "format", "text")
        if fmt == "json":
            return _format_list_json(items, show_tokens)
        return _format_list_text(items, show_tokens)

    # --diff mode: show differences
    if getattr(args, "show_diff", False):
        from agentfiles.differ import Differ, compute_content_diff
        from agentfiles.models import DiffStatus
        from agentfiles.output import format_diff, format_diff_json
        from agentfiles.scanner import SourceScanner

        config = AgentfilesConfig.load(getattr(args, "config", None))
        source_dir = _get_source(
            args,
            config.cache_dir,
            quiet=(getattr(args, "format", "text") == "json"),
        )
        scanner = SourceScanner(source_dir)
        item_types = _resolve_item_types(getattr(args, "item_type", None))
        items = _scan_filtered(scanner, item_types)
        _, target_manager, _ = _create_sync_pipeline(source_dir, config, args)
        platforms = _resolve_platforms(getattr(args, "target", None), config)
        platform_tuple = tuple(platforms) if platforms else None
        differ = Differ(target_manager)
        diff_results = differ.diff(items, platforms=platform_tuple)
        fmt = getattr(args, "format", "text")
        if fmt == "json":
            print(json.dumps(format_diff_json(diff_results), indent=2))
            return 0
        verbose = getattr(args, "verbose_diff", False)
        # Build content_diffs dict keyed by (item_key, platform_value) only
        # for UPDATED entries so format_diff can render inline diffs.
        content_diffs = None
        if verbose:
            content_diffs = {}
            for _platform, entries in diff_results.items():
                for _entry in entries:
                    if _entry.status == DiffStatus.UPDATED:
                        diff_lines = compute_content_diff(
                            _entry,
                            _platform,
                            target_manager,
                        )
                        if diff_lines:
                            key = (_entry.item.item_key, _platform.value)
                            content_diffs[key] = diff_lines
        output = format_diff(
            diff_results,
            use_colors=False,
            verbose=verbose,
            content_diffs=content_diffs,
        )
        print(output)
        return 0

    from agentfiles.output import print_table

    config = AgentfilesConfig.load(args.config)
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
    from agentfiles.config import AgentfilesConfig
    from agentfiles.engine import SyncEngine
    from agentfiles.interactive import InteractiveSession
    from agentfiles.output import bold, info, warning
    from agentfiles.scanner import SourceScanner

    config = AgentfilesConfig.load(args.config)
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
        AgentfilesError: On filesystem permission or I/O errors.
    """
    from agentfiles.interactive import InteractiveSession
    from agentfiles.models import AgentfilesError
    from agentfiles.output import info, success

    base = Path(args.path).resolve()

    # Confirm unless --yes
    if not args.non_interactive:
        session = InteractiveSession()
        if not session.confirm_action_or_abort(f"Initialize agentfiles repo at {base}?"):
            return 0

    try:
        base.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise AgentfilesError(
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
            raise AgentfilesError(
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
            raise AgentfilesError(
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


def _update_sync_state_from_results(
    state: SyncState,
    results: list[SyncResult],
    target_manager: TargetManager,
) -> None:
    """Update sync state based on successful pull/push results.

    Records the sync timestamp for each successful result.
    """
    from datetime import datetime, timezone

    from agentfiles.models import ItemState, PlatformState

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
        state.platforms[platform_key].items[item_key] = ItemState(
            synced_at=datetime.now(timezone.utc).isoformat(),
        )

    state.last_sync = datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Command dispatch map (single source of truth)
# ---------------------------------------------------------------------------

_COMMAND_MAP: dict[str, Callable[[argparse.Namespace], int]] = {
    "pull": cmd_pull,
    "push": cmd_push,
    "status": cmd_status,
    "clean": cmd_clean,
    "init": cmd_init,
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
    from agentfiles.models import PLATFORM_NAMES

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
        choices=["agent", "skill", "command", "plugin", "config", "all"],
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
    from agentfiles import __version__

    parser = argparse.ArgumentParser(
        prog="agentfiles",
        description=(
            "Sync AI tool configurations (agents, skills, commands, plugins) across platforms."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
examples:
  agentfiles pull                    Sync all items to all platforms
  agentfiles pull --update           Git pull source, then sync
  agentfiles pull --target opencode  Sync only to OpenCode
  agentfiles pull --type agent       Sync only agents
  agentfiles pull --only coder       Sync only the coder agent
  agentfiles pull --dry-run          Preview what would change
  agentfiles push                    Push local items back to source
  agentfiles status                  Show installed items per platform
  agentfiles status --list --tokens  List source items with token counts
  agentfiles status --diff           Compare source vs installed
  agentfiles clean                   Remove orphaned items
  agentfiles init                    Initialize a new repository
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
  agentfiles pull --update                     Git pull source, then sync
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
    pull_groups["sync"].add_argument(
        "--update",
        "-u",
        action="store_true",
        help="Run git pull in source repository before syncing",
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

    # status
    status_p = subs.add_parser(
        "status",
        help="Show status of installed items",
        description="Display a table of installed-item counts per discovered platform.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
examples:
  agentfiles status                            Show all platforms
  agentfiles status --list                     List source items
  agentfiles status --list --tokens            List items with token counts
  agentfiles status --list --format json       JSON output
  agentfiles status --diff                     Compare source vs installed
  agentfiles status --diff --verbose           Show content-level diffs
  agentfiles status --config custom.yaml       Use custom config file
""",
    )
    status_src = status_p.add_argument_group("Source options")
    status_src.add_argument("--config", type=Path, default=None, help="Path to config file")
    status_src.add_argument(
        "--source",
        help="Path to source repository",
    )
    status_src.add_argument(
        "--cache-dir",
        type=str,
        default=None,
        help="Cache directory for git clones",
    )
    status_src.add_argument(
        "--list",
        action="store_true",
        dest="list_items",
        help="List items available in source repository",
    )
    status_src.add_argument(
        "--tokens",
        action="store_true",
        help="Show token estimates (with --list)",
    )
    status_src.add_argument(
        "--type",
        dest="item_type",
        help="Filter by item type (agent, skill, command, plugin)",
    )
    status_src.add_argument(
        "--target",
        help="Target platform filter",
    )
    status_src.add_argument(
        "--diff",
        action="store_true",
        dest="show_diff",
        help="Show differences between source and installed items",
    )
    status_src.add_argument(
        "--verbose",
        action="store_true",
        dest="verbose_diff",
        help="Show content-level diffs for changed items",
    )
    _add_format_arg(status_p)

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
    - ``1`` — application error (``AgentfilesError`` or unexpected exception)
    - ``2`` — usage error (no subcommand provided)
    - ``130`` — interrupted by ``Ctrl-C``
    """
    from agentfiles.models import AgentfilesError
    from agentfiles.output import error, init_logging, warning

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
    except AgentfilesError as exc:
        error(f"{exc}")
        code = 1
    except Exception as exc:
        logger.exception("Unexpected error")
        error(f"Error: {exc}")
        code = 1

    sys.exit(code)


if __name__ == "__main__":
    main()
