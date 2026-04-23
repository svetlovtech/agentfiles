"""Command-line interface for the agentfiles tool.

Exposes a single ``agentfiles`` CLI entry-point that orchestrates scanning,
synchronisation, and interactive workflows for the OpenCode platform.

Subcommands:

- ``agentfiles pull``       — Install/update items from a source repository to
  local OpenCode config.  Interactive by default; pass ``--yes`` for
  non-interactive mode.  Use ``--update`` to run ``git pull`` on the source
  before syncing.
- ``agentfiles push``       — Push locally-installed items back into the source
  repository.  Discovers items from the target platform so it works even when
  the source repo is empty.
- ``agentfiles status``     — Show installed-item counts for the discovered
  platform.  Use ``--list`` to list source items, ``--diff`` to compare
  source vs installed.
- ``agentfiles clean``      — Remove orphaned items (installed items whose
  source no longer exists in the repository).
- ``agentfiles init``       — Scaffold a new agentfiles repository with
  ``agents/``, ``skills/``, ``commands/``, ``plugins/`` directories and a
  ``.agentfiles.yaml`` config file.
- ``agentfiles verify``     — CI-friendly drift detection: compare source vs
  installed items, exit 0 if no drift, exit 1 if drift detected.  Supports
  ``--format json`` and ``--quiet``.
- ``agentfiles doctor``     — Run environment diagnostics (config, platform,
  git, state file, tool binaries).
- ``agentfiles completion``  — Generate shell completion scripts for bash, zsh,
  or fish.

Common usage patterns::

    # Pull everything interactively (default)
    agentfiles pull

    # Pull in CI / scripting mode
    agentfiles pull --yes

    # Pull with git update first
    agentfiles pull --update

    # Pull only global-scope items
    agentfiles pull --scope global

    # Pull project-scope items to a specific directory
    agentfiles pull --scope project --project-dir /path/to/project

    # List items with token estimates
    agentfiles status --list --tokens

    # List only project-scope items
    agentfiles status --list --scope project

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
        Scope,
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


def _resolve_scope(scope_flag: str | None) -> list[Scope]:
    """Resolve the ``--scope`` CLI flag to a list of Scope enums.

    Args:
        scope_flag: Value of the ``--scope`` flag (``"global"``,
            ``"project"``, ``"local"``, ``"all"``, or ``None``).

    Returns:
        List of ``Scope`` enums.  ``None`` or ``"all"`` returns all scopes
        (backward-compatible default behaviour).

    """
    from agentfiles.models import Scope

    if scope_flag is None or scope_flag == "all":
        return list(Scope)
    return [Scope(scope_flag)]


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


def _filter_items_by_scope(
    items: list[Item],
    scopes: list[Scope],
) -> list[Item]:
    """Keep only items whose ``scope`` is in *scopes*.

    When *scopes* contains every ``Scope`` value (the default / unfiltered
    case), the list is returned unchanged — no allocation overhead.

    Args:
        items: Scanned ``Item`` objects.
        scopes: Allowed ``Scope`` values.

    Returns:
        Filtered list of ``Item`` objects.

    """
    from agentfiles.models import Scope as _Scope

    if set(scopes) == set(_Scope):
        return items
    return [i for i in items if i.scope in scopes]


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
        if not items:
            logging.getLogger(__name__).warning(
                "No items matched --only filter: %s", ", ".join(sorted(only_set))
            )
    if except_set is not None:
        items = [i for i in items if i.name not in except_set]
    return items


def _apply_item_key_filter(
    items: list[Item],
    item_keys: list[str] | None,
) -> list[Item]:
    """Filter items by their full item key (``type/name``).

    When *item_keys* is provided, only items whose :attr:`Item.item_key`
    matches one of the given keys are kept.

    Args:
        items: Items to filter.
        item_keys: List of item keys like ``"agent/coder"`` (or ``None``).

    Returns:
        Filtered list of items.
    """
    if not item_keys:
        return items
    key_set = set(item_keys)
    filtered = [i for i in items if i.item_key in key_set]
    if not filtered:
        logging.getLogger(__name__).warning(
            "No items matched --item filter: %s", ", ".join(sorted(key_set))
        )
    return filtered


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


def _discover_targets(
    config: AgentfilesConfig,
) -> TargetManager:
    """Discover the installed AI tool (OpenCode) and build a ``TargetManager``.

    Scans common install paths for OpenCode.  Custom paths from the config
    override the defaults.

    Args:
        config: Loaded ``AgentfilesConfig`` (may provide ``custom_paths``).

    Returns:
        A ``TargetManager`` with the discovered OpenCode target.

    Raises:
        AgentfilesError: When OpenCode is not found on the system.

    """
    from agentfiles.models import AgentfilesError
    from agentfiles.target import build_target_manager

    target_manager = build_target_manager(config.custom_paths)

    if target_manager.targets is None:
        raise AgentfilesError(
            "OpenCode not found. Install it from https://opencode.ai. "
            "Alternatively, use --config to specify custom_paths for your installation"
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

    full_clone = getattr(args, "full_clone", False)
    resolver = SourceResolver(full_clone=full_clone)
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
    item_types: list[ItemType]
    scopes: list[Scope]
    project_dir: Path | None
    dry_run: bool
    fmt: str
    only_set: set[str] | None
    except_set: set[str] | None
    item_keys: list[str] | None


def _build_context(
    args: argparse.Namespace,
    *,
    needs_pipeline: bool = True,
) -> CommandContext:
    """Build shared command context from CLI arguments.

    Resolves config, source directory, sync pipeline (scanner, target
    manager, engine), item type filter, and ``--only``/
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
    scopes = _resolve_scope(getattr(args, "scope", None))
    only_set, except_set = _resolve_item_filter(args)
    item_keys: list[str] | None = getattr(args, "item", None)

    project_dir_arg: Path | None = getattr(args, "project_dir", None)

    return CommandContext(
        config=config,
        source_dir=source_dir,
        scanner=scanner,
        target_manager=target_manager,
        engine=engine,
        item_types=item_types,
        scopes=scopes,
        project_dir=project_dir_arg,
        dry_run=getattr(args, "dry_run", False),
        fmt=getattr(args, "format", "text"),
        only_set=only_set,
        except_set=except_set,
        item_keys=item_keys,
    )


def _filter_items_by_installed(
    items: list[Item],
    target_manager: TargetManager,
    *,
    installed: bool,
) -> list[Item]:
    """Filter items by installation status.

    Args:
        items: Items to evaluate.
        target_manager: Provides access to installed-item lookups.
        installed: If True, return only already-installed items.
                   If False, return only not-yet-installed items.

    Returns:
        Filtered list of items.

    """
    from agentfiles.models import TargetError

    result = []
    for item in items:
        try:
            is_installed = target_manager.is_item_installed(item)
        except TargetError:
            continue
        if is_installed == installed:
            result.append(item)
    return result


def _discover_installed_from_targets(
    target_manager: TargetManager,
    item_types: list[ItemType],
) -> list[Item]:
    """Discover installed items directly from the target platform.

    Unlike scanning the source repository, this method finds items that
    exist on disk in the target platform directory.  This allows push
    to work even when the source repository is empty.

    Args:
        target_manager: Configured target manager.
        item_types: Item types to include.

    Returns:
        Deduplicated list of ``Item`` objects with ``source_path``
        pointing to the on-disk location at the target platform.

    """
    from agentfiles.models import Item, ItemType, TargetError
    from agentfiles.paths import get_installed_item_path

    items: list[Item] = []

    try:
        installed = target_manager.get_installed_items()
    except TargetError:
        return items

    for item_type, name in installed:
        if item_type not in item_types:
            continue

        target_dir = target_manager.get_target_dir(item_type)
        if target_dir is None:
            continue

        item_path = get_installed_item_path(target_dir, item_type, name)

        # For file-based items (agents, commands) installed as directories
        # (e.g. orchestrator/orchestrator.md), fall back to the directory
        # form if the flat-file path doesn't exist.
        if not item_path.exists() and item_type.is_file_based:
            dir_path = target_dir / name
            if dir_path.is_dir():
                item_path = dir_path

        if not item_path.exists():
            continue

        # For plugins, prefer the source file (.ts/.yaml/.yml/.py/.js)
        # over the compiled extensionless file so that push preserves
        # the original filename with extension.
        if item_type == ItemType.PLUGIN and item_path.is_file() and not item_path.suffix:
            for ext in (".ts", ".yaml", ".yml", ".py", ".js"):
                src_path = item_path.with_suffix(ext)
                if src_path.exists():
                    item_path = src_path
                    break

        items.append(
            Item(
                item_type=item_type,
                name=name,
                source_path=item_path,
            )
        )

    return items


def _run_pull_interactive(
    items: list[Item],
    target_manager: TargetManager,
) -> tuple[list[Item], str] | None:
    """Run an interactive pull session to let the user choose what to install.

    Presents a mode chooser (``full``, ``install``, ``update``, ``custom``)
    and progressively filters items based on the selection.

    Args:
        items: All items scanned from the source repository.
        target_manager: Used to check installation status.

    Returns:
        ``(filtered_items, mode)`` when the user made a valid selection,
        or ``None`` if the user aborted or nothing matched.

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
        items = _filter_items_by_installed(items, target_manager, installed=False)
        if not items:
            info("All items are already up-to-date.")
            return None
    elif mode == "update":
        items = _filter_items_by_installed(items, target_manager, installed=True)
        if not items:
            info("No items need updating.")
            return None
    # mode == "full": use all items as-is

    return items, mode


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


def _format_list_text(items: list[Any], show_tokens: bool, *, show_scope: bool = False) -> int:
    """Format items as grouped, colourised text and print to stdout.

    Items are grouped by type (agents, skills, …) and sorted alphabetically
    within each group.  Token estimates are computed only for agents and
    skills.  An aggregate token summary is printed at the end when
    *show_tokens* is ``True`` and at least one agent or skill exists.

    Args:
        items: Items to display.
        show_tokens: If ``True``, include per-item and aggregate token counts.
        show_scope: If ``True``, prefix each item with its scope marker.

    Returns:
        Exit code (always ``0``).
    """
    from agentfiles.models import _DEFAULT_VERSION, ItemType, Scope
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
        ver = f" v{item.version}" if item.version != _DEFAULT_VERSION else ""
        # Scope display — only show when show_scope is True and multiple scopes exist
        item_scope = getattr(item, "scope", None) or Scope.GLOBAL
        scope_parts: list[str] = []
        if show_scope:
            scope_parts.append(item_scope.marker)
        scope_prefix = f"{scope_parts[0]} " if scope_parts else ""
        scope_suffix = (
            f" {colorize(f'[{item_scope.display_name}]', Colors.DIM)}" if show_scope else ""
        )
        if show_tokens and item.item_type in (ItemType.AGENT, ItemType.SKILL):
            est = token_estimate(item)
            estimates.append(est)
            name_desc_total += estimate_name_description_tokens(item)
            print(
                f"  {scope_prefix}{colorize(item.name, Colors.GREEN)}{ver}{scope_suffix}  "
                f"({len(item.files)} files)  "
                f"~{est.total_tokens:,} tokens"
            )
        else:
            print(
                f"  {scope_prefix}{colorize(item.name, Colors.GREEN)}{ver}{scope_suffix}"
                f"  ({len(item.files)} files)"
            )

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
    """Install or update items from a source repository onto the target platform.

    Scans the source for available items, optionally filters by type,
    then copies (or symlinks) files to the target's config directory.
    By default an interactive session guides the user through mode
    selection (full / install-only / update-only / custom); pass
    ``--yes`` (``non_interactive``) to skip all prompts.

    With ``--update`` / ``-u``, runs ``git pull`` on the source repository
    before scanning and syncing items.

    Args:
        args: Parsed CLI namespace.  Relevant flags: ``source``,
            ``item_type``, ``scope``, ``project_dir``, ``non_interactive``,
            ``dry_run``, ``symlinks``, ``config``, ``cache_dir``, ``update``.

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
    if scanner is None or target_manager is None or engine is None or source_dir is None:
        from agentfiles.models import AgentfilesError

        raise AgentfilesError("Internal error: pipeline not initialized")

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
    items = _filter_items_by_scope(items, ctx.scopes)

    # Apply --only / --except item-name filters
    items = _apply_item_filter(items, ctx.only_set, ctx.except_set)

    # Apply --item key filters
    items = _apply_item_key_filter(items, ctx.item_keys)

    # Interactive by default, non-interactive with --yes
    pull_mode: str = "full"
    if not args.non_interactive:
        result = _run_pull_interactive(items, target_manager)
        if result is None:
            return 0
        items, pull_mode = result

    # For "update" and "full" modes, use UPDATE action so existing items
    # are reinstalled from source instead of being skipped.
    from agentfiles.models import SyncAction

    sync_action = SyncAction.UPDATE if pull_mode in ("update", "full") else SyncAction.INSTALL
    plans = engine.plan_sync(items, action=sync_action)

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


def _create_pull_request(
    source_dir: Path,
    pushed_items: list[str],
    branch: str | None,
    title: str | None,
    dry_run: bool,
) -> int:
    """Create a pull request in the source repository via ``gh pr create``.

    Checks that ``gh`` is available, creates a new branch, commits any changes
    in *source_dir*, pushes the branch, and opens a PR.

    Args:
        source_dir: Path to the local source repository directory.
        pushed_items: List of item keys that were pushed (used for auto title).
        branch: Branch name to create.  Auto-generated if ``None``.
        title: PR title.  Auto-generated from *pushed_items* if ``None``.
        dry_run: When ``True``, print what would happen without doing it.

    Returns:
        ``0`` on success, ``1`` on error.
    """
    import datetime
    import subprocess

    from agentfiles.output import error, info, warning

    # Auto-generate branch name if not provided.
    if branch is None:
        timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        branch = f"agentfiles/push-{timestamp}"

    # Auto-generate PR title if not provided.
    if title is None:
        if len(pushed_items) == 1:
            title = f"agentfiles: push {pushed_items[0]}"
        elif len(pushed_items) <= 3:
            title = f"agentfiles: push {', '.join(pushed_items)}"
        else:
            title = f"agentfiles: push {len(pushed_items)} items"

    if dry_run:
        info(f"[dry-run] Would create branch: {branch}")
        info(f"[dry-run] Would commit and push changes in: {source_dir}")
        info(f"[dry-run] Would create PR with title: {title!r}")
        return 0

    # Check gh is available.
    try:
        subprocess.run(
            ["gh", "--version"],
            capture_output=True,
            check=True,
        )
    except FileNotFoundError:
        error("'gh' CLI not found. Install it from https://cli.github.com/")
        return 1
    except subprocess.CalledProcessError as exc:
        error(f"'gh' returned an error: {exc}")
        return 1

    cwd = str(source_dir)

    # Create and switch to new branch.
    try:
        subprocess.run(
            ["git", "checkout", "-b", branch],
            capture_output=True,
            check=True,
            cwd=cwd,
        )
    except subprocess.CalledProcessError as exc:
        error(f"Failed to create branch '{branch}': {exc.stderr.decode().strip()}")
        return 1

    # Stage all changes.
    try:
        subprocess.run(
            ["git", "add", "-A"],
            capture_output=True,
            check=True,
            cwd=cwd,
        )
    except subprocess.CalledProcessError as exc:
        error(f"Failed to stage changes: {exc.stderr.decode().strip()}")
        return 1

    # Commit.
    try:
        subprocess.run(
            ["git", "commit", "-m", title],
            capture_output=True,
            check=True,
            cwd=cwd,
        )
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr.decode().strip()
        if "nothing to commit" in stderr or "nothing added to commit" in stderr:
            warning("Nothing to commit in source repository — skipping PR creation.")
            return 0
        error(f"Failed to commit: {stderr}")
        return 1

    # Push branch.
    try:
        subprocess.run(
            ["git", "push", "-u", "origin", branch],
            capture_output=True,
            check=True,
            cwd=cwd,
        )
    except subprocess.CalledProcessError as exc:
        error(f"Failed to push branch: {exc.stderr.decode().strip()}")
        return 1

    # Create PR.
    try:
        result = subprocess.run(
            ["gh", "pr", "create", "--title", title, "--body", "", "--head", branch],
            capture_output=True,
            check=True,
            cwd=cwd,
        )
        pr_url = result.stdout.decode().strip()
        info(f"Pull request created: {pr_url}")
    except subprocess.CalledProcessError as exc:
        error(f"Failed to create PR: {exc.stderr.decode().strip()}")
        return 1

    return 0


def cmd_push(args: argparse.Namespace) -> int:
    """Push locally-installed items back into the source repository.

    Discovers items directly from the target platform directory (not from the
    source scanner) so that push works even when the source repo is empty or
    out of date.

    Args:
        args: Parsed CLI namespace.  Relevant flags: ``source``,
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

    # Discover items from the target platform, not from the source scanner.
    installed_items = _discover_installed_from_targets(
        target_manager,
        item_types,
    )

    # Apply --only / --except item-name filters
    only_set, except_set = _resolve_item_filter(args)
    installed_items = _apply_item_filter(installed_items, only_set, except_set)

    # Apply --item key filters
    item_keys: list[str] | None = getattr(args, "item", None)
    installed_items = _apply_item_key_filter(installed_items, item_keys)

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

    # Conflict detection: check if both source and target changed since last sync.
    from agentfiles.engine import detect_push_conflicts

    conflicts = detect_push_conflicts(
        installed_items,
        source_dir,
        target_manager,
    )

    from agentfiles.models import TARGET_PLATFORM_DISPLAY

    skip_keys: set[str] = set()
    if conflicts:
        if args.non_interactive:
            # Non-interactive mode: skip conflicts and warn.
            for c in conflicts:
                warning(
                    f"Conflict: {c.item.item_key} on {TARGET_PLATFORM_DISPLAY} "
                    f"— both source and target changed. Skipping."
                )
                skip_keys.add(c.item.item_key)
        else:
            # Interactive mode: prompt user for each conflict.
            conflict_tuples = [
                (
                    c.item.item_key,
                    c.item.item_type.value,
                    c.source_path,
                    c.target_path,
                )
                for c in conflicts
            ]
            try:
                resolutions = session.prompt_push_conflicts(conflict_tuples)
            except KeyboardInterrupt:
                print()
                warning("Aborted.")
                return 1

            for c in conflicts:
                resolution = resolutions.get(c.item.item_key, "keep-source")
                if resolution == "keep-source":
                    skip_keys.add(c.item.item_key)

    if skip_keys:
        installed_items = [i for i in installed_items if i.item_key not in skip_keys]
        if not installed_items:
            info("All items skipped due to conflicts.")
            return 0

    report = engine.push(installed_items, source_dir=source_dir, dry_run=args.dry_run)

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

    exit_code = 0 if report.is_success else 1

    # Optionally create a PR after a successful push.
    if exit_code == 0 and getattr(args, "create_pr", False):
        synced_items = [
            r.plan.item.item_key for r in (report.installed + report.updated) if r.is_success
        ]
        pr_code = _create_pull_request(
            source_dir=source_dir,
            pushed_items=synced_items,
            branch=getattr(args, "pr_branch", None),
            title=getattr(args, "pr_title", None),
            dry_run=args.dry_run,
        )
        if pr_code != 0:
            exit_code = pr_code

    return exit_code


def cmd_status(args: argparse.Namespace) -> int:
    """Display a table of installed-item counts for the discovered platform.

    Shows the platform name, config directory path, and number of agents,
    skills, commands, and plugins installed for the platform found on the
    system.

    With ``--list``, lists items available in the source repository instead
    of showing the platform table.  Supports ``--tokens`` for token-cost
    estimates and ``--format json`` for machine-readable output.

    With ``--diff``, shows differences between source items and their
    installed counterparts on the target platform.  Supports ``--verbose``
    for content-level diffs.

    Args:
        args: Parsed CLI namespace.  Relevant flags: ``config``,
            ``list_items``, ``tokens``, ``show_diff``, ``verbose_diff``,
            ``item_type``, ``source``, ``format``.

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

        # Apply scope filtering.
        scopes = _resolve_scope(getattr(args, "scope", None))
        items = _filter_items_by_scope(items, scopes)

        # Show scope markers only when items have mixed scopes
        from agentfiles.models import Scope as _Scope

        has_mixed_scopes = len({getattr(i, "scope", _Scope.GLOBAL) for i in items}) > 1
        # Also show when user explicitly filtered by scope
        explicit_scope = getattr(args, "scope", None) is not None

        show_tokens = getattr(args, "tokens", False)
        fmt = getattr(args, "format", "text")
        if fmt == "json":
            return _format_list_json(items, show_tokens)
        return _format_list_text(items, show_tokens, show_scope=has_mixed_scopes or explicit_scope)

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
        differ = Differ(target_manager)
        diff_results = differ.diff(items)
        fmt = getattr(args, "format", "text")
        if fmt == "json":
            print(format_diff_json(diff_results))
            return 0
        verbose = getattr(args, "verbose_diff", False)
        # Build content_diffs dict keyed by item_key only
        # for UPDATED entries so format_diff can render inline diffs.
        content_diffs = None
        if verbose:
            content_diffs = {}
            for _entry in diff_results:
                if _entry.status == DiffStatus.UPDATED:
                    diff_lines = compute_content_diff(
                        _entry,
                        target_manager,
                    )
                    if diff_lines:
                        content_diffs[_entry.item.item_key] = diff_lines
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

    from agentfiles.models import TARGET_PLATFORM_DISPLAY

    headers = ["Platform", "Path", "Agents", "Skills", "Commands", "Plugins"]
    rows: list[list[str]] = []

    targets = target_manager.targets
    if targets is not None:
        rows.append(
            [
                TARGET_PLATFORM_DISPLAY,
                str(targets.config_dir),
                str(summary.get("agents", 0)),
                str(summary.get("skills", 0)),
                str(summary.get("commands", 0)),
                str(summary.get("plugins", 0)),
            ]
        )

    print_table(headers, rows)
    return 0


def cmd_clean(args: argparse.Namespace) -> int:
    """Remove orphaned items that are installed but no longer exist in source.

    Compares the set of items in the source repository against items installed
    on the target platform.  Any installed item whose source no longer exists is
    considered orphaned and eligible for removal.

    The command prompts for confirmation before removing anything, unless
    ``--yes`` is passed.  Supports ``--dry-run`` for a preview of what would
    be removed.

    Args:
        args: Parsed CLI namespace.  Relevant flags: ``source``,
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
    item_types = _resolve_item_types(args.item_type)

    # Discover all installed items on the target platform.
    installed_items = _discover_installed_from_targets(
        target_manager,
        item_types,
    )

    if not installed_items:
        info("No installed items found.")
        return 0

    # Build a set of installed item keys for fast lookup.
    installed_keys: set[str] = {item.item_key for item in installed_items}

    # Orphans = installed items whose source no longer exists.
    orphan_keys = sorted(installed_keys - source_keys)

    if not orphan_keys:
        info("No orphaned items found.")
        return 0

    # Filter orphans by requested item types.
    orphan_items: list[Item] = []
    for item in installed_items:
        if item.item_key in orphan_keys and item.item_type in item_types:
            orphan_items.append(item)

    # Apply --item key filters
    item_keys: list[str] | None = getattr(args, "item", None)
    orphan_items = _apply_item_key_filter(orphan_items, item_keys)

    if not orphan_items:
        info("No orphaned items found (after type filter).")
        return 0

    # Display orphans.
    print()
    bold(f"Found {len(orphan_items)} orphaned items:")
    for item in orphan_items:
        print(f"  {item.item_key}")

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

    for item in orphan_items:
        report = engine.uninstall([item])
        if report.is_success:
            total_removed += sum(1 for r in report.uninstalled if r.is_success)

    print()
    if total_removed:
        bold(f"Removed {total_removed} items.")
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
        config_content = "# agentfiles configuration\ndefault_platforms:\n  - opencode\n"
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

    from agentfiles.models import ItemState

    for result in results:
        if not result.is_success:
            continue

        plan = result.plan
        item = plan.item

        item_key = item.item_key
        state.items[item_key] = ItemState(
            synced_at=datetime.now(timezone.utc).isoformat(),
        )

    state.last_sync = datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# cmd_doctor
# ---------------------------------------------------------------------------


def cmd_doctor(args: argparse.Namespace) -> int:
    """Run environment diagnostics and report results.

    Returns:
        ``0`` if all checks pass, ``1`` if any ERROR-level check fails.
    """
    from agentfiles.doctor import format_doctor_report, run_doctor

    config_path: Path | None = getattr(args, "config", None)
    source_dir: Path | None = None
    source_str: str | None = getattr(args, "source", None)
    if source_str is not None:
        candidate = Path(source_str).expanduser()
        if candidate.is_dir():
            source_dir = candidate

    report = run_doctor(config_path=config_path, source_dir=source_dir)
    print(format_doctor_report(report))
    return report.exit_code


# ---------------------------------------------------------------------------
# cmd_verify
# ---------------------------------------------------------------------------


def cmd_verify(args: argparse.Namespace) -> int:
    """CI-friendly drift detection between source and installed items.

    Compares source items against installed items on the target platform and
    returns a meaningful exit code:

    * ``0`` — no drift (all items UNCHANGED).
    * ``1`` — drift detected (at least one NEW, UPDATED, or MISSING item).

    Supports ``--format json`` for machine-readable output and ``--quiet``
    to suppress all output (only the exit code matters).

    Args:
        args: Parsed CLI namespace.  Relevant flags: ``config``, ``source``,
            ``item_type``, ``format``, ``quiet``.

    Returns:
        ``0`` if no drift, ``1`` if drift detected.
    """
    from agentfiles.config import AgentfilesConfig
    from agentfiles.differ import Differ
    from agentfiles.models import DiffStatus
    from agentfiles.scanner import SourceScanner

    quiet = getattr(args, "quiet", False)
    fmt = getattr(args, "format", "text")

    config = AgentfilesConfig.load(getattr(args, "config", None))
    source_dir = _get_source(args, config.cache_dir, quiet=(quiet or fmt == "json"))
    scanner = SourceScanner(source_dir)
    item_types = _resolve_item_types(getattr(args, "item_type", None))
    items = _scan_filtered(scanner, item_types)
    _, target_manager, _ = _create_sync_pipeline(source_dir, config, args)

    differ = Differ(target_manager)
    diff_results = differ.diff(items)

    # Classify drift
    drift_entries: list[dict[str, str]] = []
    for entry in diff_results:
        if entry.status != DiffStatus.UNCHANGED:
            drift_entries.append(
                {
                    "item": entry.item.name,
                    "type": entry.item.item_type.value,
                    "status": entry.status.value,
                    "details": entry.details or "",
                }
            )

    has_drift = len(drift_entries) > 0

    if not quiet:
        if fmt == "json":
            result = {
                "drift": has_drift,
                "total_items": len(diff_results),
                "drifted_items": len(drift_entries),
                "details": drift_entries,
            }
            print(json.dumps(result, indent=2))
        else:
            if has_drift:
                print(f"Drift detected: {len(drift_entries)} item(s) out of sync")
                for d in drift_entries:
                    print(f"  [{d['status']}] {d['item']}")
            else:
                print(f"No drift detected ({len(diff_results)} item(s) in sync)")

    return 1 if has_drift else 0


def cmd_completion(args: argparse.Namespace) -> int:
    """Output a shell completion script to stdout.

    The *shell* positional argument selects which script to emit
    (``bash``, ``zsh``, or ``fish``).

    Returns:
        ``0`` on success, ``1`` if the shell argument is missing or invalid.
    """
    from agentfiles.completion import get_completion_script

    shell: str | None = getattr(args, "shell", None)
    if not shell:
        from agentfiles.output import error

        error("Usage: agentfiles completion {bash,zsh,fish}")
        return 1

    try:
        print(get_completion_script(shell))
    except ValueError as exc:
        from agentfiles.output import error

        error(str(exc))
        return 1
    return 0


# ---------------------------------------------------------------------------
# Command dispatch map (single source of truth)
# ---------------------------------------------------------------------------

_COMMAND_MAP: dict[str, Callable[[argparse.Namespace], int]] = {
    "pull": cmd_pull,
    "push": cmd_push,
    "status": cmd_status,
    "clean": cmd_clean,
    "init": cmd_init,
    "doctor": cmd_doctor,
    "verify": cmd_verify,
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

    * **Source options** — ``source``, ``--config``, ``--cache-dir``,
      ``--project-dir``
    * **Filter options** — ``--type``, ``--scope``,
      ``--only``, ``--except``
    * **Output options** — ``--dry-run``
    * **Sync options**  — ``--yes``

    Args:
        parser: The sub-parser to attach arguments to.

    Returns:
        Mapping of group names (``"source"``, ``"filter"``, ``"output"``,
        ``"sync"``) to their ``_ArgumentGroup`` objects so that callers
        can attach additional arguments to the same visual section.
    """

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
    source_group.add_argument(
        "--project-dir",
        type=Path,
        default=None,
        help="Project directory for project/local scope installation (default: current directory)",
    )

    filter_group = parser.add_argument_group("Filter options")
    filter_group.add_argument(
        "--scope",
        choices=["global", "project", "local", "all"],
        default=None,
        help="Filter by scope: global, project, local, or all (default: all)",
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
    filter_group.add_argument(
        "--item",
        metavar="KEY",
        action="append",
        default=None,
        help="Select specific items by key (type/name, e.g. agent/coder). Repeatable.",
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
            "Sync AI tool configurations (agents, skills, commands, plugins) with OpenCode."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
examples:
  agentfiles pull                    Sync all items to OpenCode
  agentfiles pull --update           Git pull source, then sync
  agentfiles pull --type agent       Sync only agents
  agentfiles pull --scope global     Sync only global-scope items
  agentfiles pull --only coder       Sync only the coder agent
  agentfiles pull --dry-run          Preview what would change
  agentfiles push                    Push local items back to source
  agentfiles status                  Show installed items for platform
  agentfiles status --list --tokens  List source items with token counts
  agentfiles status --list --scope project  List project-scope items
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
        description="Scan source repository and sync items to the target platform.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
examples:
  agentfiles pull                              Sync all items interactively
  agentfiles pull --update                     Git pull source, then sync
  agentfiles pull --yes                        Non-interactive, accept all
  agentfiles pull --dry-run --verbose          Preview with detailed output
  agentfiles pull --type agent                 Only agents
  agentfiles pull --only coder,solid-principles   Sync specific items
  agentfiles pull --scope global               Sync only global-scope items
  agentfiles pull --scope project --project-dir /path  Sync project items to dir
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
    pull_groups["sync"].add_argument(
        "--full-clone",
        action="store_true",
        help="Disable shallow/sparse-checkout optimisation for git clones",
    )
    _add_format_arg(pull_p, group=pull_groups["output"])

    # push
    push_p = subs.add_parser(
        "push",
        help="Push items from local configs back to the source repository",
        description="Discover installed items from the target platform and push them back to source.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
examples:
  agentfiles push                              Push all installed items interactively
  agentfiles push --yes                        Non-interactive, accept all
  agentfiles push --dry-run                    Preview what would be pushed
  agentfiles push --create-pr                  Push and open a pull request
  agentfiles push --create-pr --pr-title "My PR" --pr-branch feat/sync
""",
    )
    push_groups = _add_common_args(push_p)
    push_groups["sync"].add_argument(
        "--symlinks",
        action="store_true",
        help="Use symlinks instead of copying",
    )
    push_pr_group = push_p.add_argument_group("Pull request options")
    push_pr_group.add_argument(
        "--create-pr",
        action="store_true",
        dest="create_pr",
        help="Create a pull request after pushing (requires 'gh' CLI)",
    )
    push_pr_group.add_argument(
        "--pr-title",
        dest="pr_title",
        default=None,
        metavar="TITLE",
        help="Title for the pull request (default: auto-generated from pushed items)",
    )
    push_pr_group.add_argument(
        "--pr-branch",
        dest="pr_branch",
        default=None,
        metavar="BRANCH",
        help="Branch name for the pull request (default: agentfiles/push-YYYYMMDD-HHMMSS)",
    )
    _add_format_arg(push_p, group=push_groups["output"])

    # status
    status_p = subs.add_parser(
        "status",
        help="Show status of installed items",
        description="Display a table of installed-item counts for the discovered platform.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
examples:
  agentfiles status                            Show platform status
  agentfiles status --list                     List source items
  agentfiles status --list --tokens            List items with token counts
  agentfiles status --list --scope global      List only global-scope items
  agentfiles status --list --scope project     List only project-scope items
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
        help="Filter by item type (agent, skill, command, plugin, config, workflow)",
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
    status_src.add_argument(
        "--scope",
        choices=["global", "project", "local", "all"],
        default=None,
        help="Filter by scope (with --list): global, project, local, or all",
    )
    _add_format_arg(status_p)

    # clean
    clean_p = subs.add_parser(
        "clean",
        help="Remove orphaned items that no longer exist in source",
        description=(
            "Remove items installed on the target platform that have been deleted from source."
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

    # doctor
    doctor_p = subs.add_parser(
        "doctor",
        help="Check environment health and diagnose common issues",
        description="Run diagnostic checks on config files, platform directories, git, and tools.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
examples:
  agentfiles doctor                            Run all checks
  agentfiles doctor --source ~/my-agents       Check specific source dir
  agentfiles doctor --config .agentfiles.yaml  Check specific config
""",
    )
    doctor_p.add_argument(
        "source",
        nargs="?",
        default=None,
        help="Source repository to check (optional)",
    )
    doctor_p.add_argument(
        "--config",
        "-c",
        default=None,
        help="Explicit path to config file",
    )

    # verify
    verify_p = subs.add_parser(
        "verify",
        help="CI-friendly drift detection (exit 0 = no drift, exit 1 = drift)",
        description="Compare source items vs installed items and exit with a meaningful code.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
examples:
  agentfiles verify                       Check for drift (human output)
  agentfiles verify --format json         Machine-readable JSON output
  agentfiles verify --quiet               Only exit code, no output
""",
    )
    _add_common_args(verify_p)
    verify_p.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Output format (default: text)",
    )
    verify_p.add_argument(
        "--quiet",
        "-q",
        action="store_true",
        default=False,
        help="Suppress output; only the exit code matters",
    )

    # completion
    completion_p = subs.add_parser(
        "completion",
        help="Generate shell completion scripts",
        description="Output a completion script for the given shell to stdout.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
examples:
  agentfiles completion bash               Print bash completions
  agentfiles completion zsh >> ~/.zshrc    Install zsh completions
  agentfiles completion fish > ~/.config/fish/completions/agentfiles.fish
""",
    )
    completion_p.add_argument(
        "shell",
        choices=["bash", "zsh", "fish"],
        help="Shell to generate completions for",
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
