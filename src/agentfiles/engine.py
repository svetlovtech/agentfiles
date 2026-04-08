"""Core sync engine — plans and executes install, update, and uninstall operations.

The ``SyncEngine`` bridges source items discovered by :class:`SourceScanner`
with target directories provided by any object satisfying the
:class:`SyncTarget` protocol.

Pipeline overview (plan → execute → report)::

    ┌──────────┐     ┌───────────────┐     ┌──────────┐
    │ plan_sync │ ──► │ execute_plan  │ ──► │ aggregate │
    └──────────┘     └───────────────┘     └──────────┘

1. **Plan** — :meth:`plan_sync` iterates over every (item, platform) pair
   and dispatches to a *planning handler* (see ``_plan_handlers``) that
   decides the concrete :class:`SyncAction` (INSTALL, UPDATE, UNINSTALL,
   SKIP).  The result is an ordered list of :class:`SyncPlan` objects.

2. **Execute** — :meth:`execute_plan` walks the plan list and dispatches
   each entry to an *execution handler* (see ``_action_handlers``) that
   performs the actual filesystem operation (copy, symlink, remove).
   Failures are caught per-plan so one bad item never aborts the batch.

3. **Report** — :meth:`aggregate` classifies every :class:`SyncResult`
   into a :class:`SyncReport` bucket (installed / updated / skipped /
   uninstalled / failed).

Convenience methods :meth:`sync`, :meth:`uninstall`, and :meth:`push`
wrap the full pipeline for common use-cases.  A ``dry_run`` mode is
available to log planned actions without touching the filesystem.

Usage::

    engine = SyncEngine(target_manager)
    report = engine.sync(items, platforms=(Platform.OPENCODE,))
    print(report.summary())
"""

from __future__ import annotations

import filecmp
import logging
import os
import shutil
import stat
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol, runtime_checkable

from agentfiles.config import load_sync_state, save_sync_state
from agentfiles.models import (
    AgentfilesError,
    Item,
    ItemState,
    ItemType,
    Platform,
    PlatformState,
    SyncAction,
    SyncPlan,
    SyncResult,
    SyncState,
)
from agentfiles.paths import get_item_dest_path, get_push_dest_path

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------

_DEFAULT_PLATFORMS: tuple[Platform, ...] = (
    Platform.OPENCODE,
    Platform.CLAUDE_CODE,
    Platform.WINDSURF,
    Platform.CURSOR,
)


def _iter_candidate_platforms(
    item: Item,
    platforms: tuple[Platform, ...] | list[Platform],
) -> list[Platform]:
    """Return platforms that are both supported by item and requested, sorted."""
    return sorted(
        set(item.supported_platforms) & set(platforms),
        key=lambda p: p.value,
    )


# ---------------------------------------------------------------------------
# SyncReport
# ---------------------------------------------------------------------------


@dataclass
class SyncReport:
    """Aggregated result of a full sync or uninstall operation.

    Attributes:
        installed: Results for items that were freshly installed.
        updated: Results for items that were updated in place.
        skipped: Results for items that needed no changes.
        uninstalled: Results for items that were removed.
        failed: Results for items that encountered errors.

    """

    installed: list[SyncResult] = field(default_factory=list)
    updated: list[SyncResult] = field(default_factory=list)
    skipped: list[SyncResult] = field(default_factory=list)
    uninstalled: list[SyncResult] = field(default_factory=list)
    failed: list[SyncResult] = field(default_factory=list)

    @property
    def success_count(self) -> int:
        """Total number of successful operations."""
        return len(self.installed) + len(self.updated) + len(self.skipped) + len(self.uninstalled)

    @property
    def failure_count(self) -> int:
        """Total number of failed operations."""
        return len(self.failed)

    @property
    def is_success(self) -> bool:
        """``True`` when every operation succeeded."""
        return self.failure_count == 0

    def summary(self) -> str:
        """Human-readable summary string.

        Example::

            "Installed 15, Updated 3, Skipped 40, Uninstalled 2, Failed 1"
        """
        parts: list[str] = []
        if self.installed:
            parts.append(f"Installed {len(self.installed)}")
        if self.updated:
            parts.append(f"Updated {len(self.updated)}")
        if self.skipped:
            parts.append(f"Skipped {len(self.skipped)}")
        if self.uninstalled:
            parts.append(f"Uninstalled {len(self.uninstalled)}")
        if self.failed:
            parts.append(f"Failed {len(self.failed)}")
        total_files = sum(r.files_copied for r in self.installed + self.updated)
        if total_files:
            parts.append(f"Files copied: {total_files}")
        return ", ".join(parts) if parts else "No operations performed"


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def _copy_item(source: Path, dest: Path, use_symlinks: bool) -> tuple[int, str | None]:
    """Copy or symlink *source* to *dest*.

    Args:
        source: Resolved source file or directory.
        dest: Destination path (may or may not exist).
        use_symlinks: When ``True``, create a symbolic link instead of copying.

    Returns:
        ``(files_copied, error_message)``.  On success *error_message* is
        ``None``.  ``files_copied`` is ``0`` for symlinks since no files are
        physically copied.

    """
    try:
        if use_symlinks:
            real_source = Path(os.path.realpath(source))
            # Guard against symlinks escaping the source tree.
            try:
                real_source.relative_to(source.parent)
            except ValueError:
                msg = f"Symlink target escapes source tree: {real_source}"
                logger.error(msg)
                return 0, msg
            dest.parent.mkdir(parents=True, exist_ok=True)
            os.symlink(real_source, dest)
            logger.debug("Symlinked %s -> %s", dest, real_source)
            return 0, None

        if source.is_dir():
            try:
                shutil.copytree(source, dest, dirs_exist_ok=True)
            except (PermissionError, OSError) as copy_exc:
                # Clean up partial directory copy so the filesystem is not
                # left in an inconsistent state with half-copied files.
                if dest.is_dir():
                    try:
                        shutil.rmtree(dest)
                    except OSError as rm_exc:
                        logger.error("Partial copy cleanup failed at %s: %s", dest, rm_exc)
                msg = f"Cannot copy directory {source} -> {dest}: {copy_exc}"
                logger.error(msg)
                return 0, msg
            count = sum(len(files) for _, _, files in os.walk(dest))
            logger.debug("Copied %d files to %s", count, dest)
            return count, None

        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, dest)
        logger.debug("Copied %s to %s", source, dest)
        return 1, None

    except (PermissionError, OSError) as exc:
        msg = f"Cannot copy {source} -> {dest}: {exc}"
        logger.error(msg)
        return 0, msg


def _remove_item(dest: Path) -> tuple[bool, str | None]:
    """Remove a file, directory, or symlink at *dest*.

    Returns:
        ``(success, error_message)``.

    """
    try:
        # Single lstat call replaces separate is_dir() + is_symlink() checks,
        # each of which would issue its own stat syscall.
        st = os.lstat(dest)
        if stat.S_ISDIR(st.st_mode) and not stat.S_ISLNK(st.st_mode):
            shutil.rmtree(dest)
            logger.debug("Removed directory %s", dest)
        else:
            os.unlink(dest)
            logger.debug("Removed %s", dest)
        return True, None
    except (PermissionError, OSError) as exc:
        msg = f"Cannot remove {dest}: {exc}"
        logger.error(msg)
        return False, msg


# ---------------------------------------------------------------------------
# Push diff helpers
# ---------------------------------------------------------------------------


def _human_size(size_bytes: int) -> str:
    """Format bytes as human-readable size."""
    for unit in ("B", "KB", "MB", "GB"):
        if abs(size_bytes) < 1024:
            return f"{size_bytes:.1f} {unit}" if unit != "B" else f"{size_bytes} {unit}"
        size_bytes /= 1024  # type: ignore[assignment]
    return f"{size_bytes:.1f} TB"


def _compare_push_item(local_path: Path, dest_path: Path) -> str:
    """Compare local (target) item with destination (source repo) item.

    Returns "new", "unchanged", or "changed".
    """
    if not dest_path.exists():
        return "new"
    try:
        if local_path.is_file() and dest_path.is_file():
            if filecmp.cmp(local_path, dest_path, shallow=False):
                return "unchanged"
            return "changed"
        if local_path.is_dir() and dest_path.is_dir():
            dcmp = filecmp.dircmp(local_path, dest_path)
            if _dir_differs(dcmp):
                return "changed"
            return "unchanged"
    except OSError:
        pass
    return "changed"


@dataclass(frozen=True)
class PushConflict:
    """A push item where both source and target changed since last sync.

    Attributes:
        item: The item with a conflict.
        platform: The platform the item was discovered on.
        source_path: Path to the source repo copy.
        target_path: Path to the locally-installed copy.
    """

    item: Item
    platform: Platform
    source_path: Path
    target_path: Path


def detect_push_conflicts(
    items: list[Item],
    platforms: tuple[Platform, ...],
    source_dir: Path,
    target_manager: SyncTarget,
) -> list[PushConflict]:
    """Detect items where both source repo and target changed since last sync.

    An item is a conflict when:
    1. It exists in both source repo and target (installed location).
    2. The source repo version differs from the target version.
    3. The source repo file was modified after the last sync timestamp.

    When there is no sync state (first run), no conflicts are reported
    because there is no baseline to compare against.

    Args:
        items: Installed items to check.
        platforms: Platforms to consider.
        source_dir: Root of the source repository.
        target_manager: Provides target directory resolution.

    Returns:
        List of :class:`PushConflict` instances.
    """
    try:
        state = load_sync_state(source_dir)
    except Exception:
        logger.debug("Cannot load sync state for conflict detection", exc_info=True)
        return []

    if not state.last_sync:
        return []

    conflicts: list[PushConflict] = []

    for item in items:
        candidate_platforms = _iter_candidate_platforms(item, platforms)
        for platform in candidate_platforms:
            try:
                conflict = _check_push_conflict(
                    item,
                    platform,
                    source_dir,
                    target_manager,
                    state,
                )
                if conflict is not None:
                    conflicts.append(conflict)
            except (AgentfilesError, OSError):
                logger.debug(
                    "Error checking conflict for %s on %s",
                    item.name,
                    platform.display_name,
                    exc_info=True,
                )

    return conflicts


def _check_push_conflict(
    item: Item,
    platform: Platform,
    source_dir: Path,
    target_manager: SyncTarget,
    state: SyncState,
) -> PushConflict | None:
    """Check whether a single (item, platform) pair is a push conflict.

    Returns a :class:`PushConflict` if both sides changed, else ``None``.
    """
    target_dir = target_manager.get_target_dir(platform, item.item_type)
    if target_dir is None:
        return None

    local_path = get_item_dest_path(target_dir, item)
    dest_path = get_push_dest_path(source_dir, item)

    # Both must exist for a conflict.
    if not local_path.exists() or not dest_path.exists():
        return None

    # If they are identical, no conflict.
    push_status = _compare_push_item(local_path, dest_path)
    if push_status == "unchanged":
        return None

    # Check if source repo version was modified after last sync.
    platform_key = platform.value
    item_key = item.item_key
    platform_state = state.platforms.get(platform_key)
    if platform_state is None:
        return None
    item_state = platform_state.items.get(item_key)
    if item_state is None or not item_state.synced_at:
        return None

    try:
        synced_at = datetime.fromisoformat(item_state.synced_at)
    except (ValueError, TypeError):
        return None

    # Check if source repo file was modified after sync.
    try:
        source_mtime = _get_mtime(dest_path)
    except OSError:
        return None

    if source_mtime <= synced_at:
        # Source repo unchanged since sync -- not a conflict, just target changed.
        return None

    return PushConflict(
        item=item,
        platform=platform,
        source_path=dest_path,
        target_path=local_path,
    )


def _get_mtime(path: Path) -> datetime:
    """Return the modification time of a file or directory as a datetime."""
    if path.is_file():
        ts = path.stat().st_mtime
    elif path.is_dir():
        # Use the most recent mtime among all files.
        ts = max(
            (f.stat().st_mtime for f in path.rglob("*") if f.is_file()),
            default=path.stat().st_mtime,
        )
    else:
        ts = path.stat().st_mtime
    return datetime.fromtimestamp(ts, tz=timezone.utc)


def _dir_differs(dcmp: filecmp.dircmp[str]) -> bool:
    """Recursively check if dircmp shows any differences."""
    if dcmp.left_only or dcmp.right_only or dcmp.diff_files:
        return True
    return any(_dir_differs(sub_dcmp) for sub_dcmp in dcmp.subdirs.values())


def _format_size_diff(local_path: Path, dest_path: Path) -> str:
    """Return human-readable size diff string."""
    try:
        if local_path.is_file() and dest_path.is_file():
            local_size = local_path.stat().st_size
            dest_size = dest_path.stat().st_size
            return f"({_human_size(dest_size)} -> {_human_size(local_size)})"
        if local_path.is_dir() and dest_path.is_dir():
            local_count = sum(1 for _ in local_path.rglob("*") if _.is_file())
            dest_count = sum(1 for _ in dest_path.rglob("*") if _.is_file())
            return f"({dest_count} files -> {local_count} files)"
    except OSError:
        pass
    return ""


# ---------------------------------------------------------------------------
# SyncEngine
# ---------------------------------------------------------------------------


@runtime_checkable
class SyncTarget(Protocol):
    """Interface that SyncEngine requires from a target manager.

    Any object implementing ``get_target_dir`` satisfies this protocol
    via structural subtyping — no explicit inheritance needed.

    This decouples SyncEngine from the concrete :class:`TargetManager`,
    making it testable with lightweight stubs or mocks.

    Because the protocol is ``@runtime_checkable``, ``isinstance`` checks
    work at runtime and ``MagicMock(spec=SyncTarget)`` in tests is accepted
    by ``SyncEngine``.
    """

    def get_target_dir(
        self,
        platform: Platform,
        item_type: ItemType,
    ) -> Path | None:
        """Return the target directory for a platform and item type."""

    def resolve_platform_for(
        self,
        item_type: ItemType,
        target_dir: Path,
    ) -> Platform | None:
        """Reverse-lookup which platform owns a given target directory."""


class SyncEngine:
    """Plans and executes sync operations across target platforms.

    Args:
        target_manager: Provides target directory resolution.  Accepts any
            object that satisfies the :class:`SyncTarget` protocol.
        use_symlinks: Create symlinks instead of copying files.
        dry_run: Plan operations without executing them.

    """

    def __init__(
        self,
        target_manager: SyncTarget,
        use_symlinks: bool = False,
        dry_run: bool = False,
    ) -> None:
        """Initialise the SyncEngine."""
        self._target_manager = target_manager
        self._use_symlinks = use_symlinks
        self._dry_run = dry_run

        # Strategy dispatch: map each SyncAction to a dedicated *planning*
        # handler.  Adding a new action only requires writing a new handler
        # method and registering it here — no if/elif chain to modify.
        #
        # EXTENSION POINT — Adding a new SyncAction
        # ==========================================
        # When a new SyncAction is added to models.py:
        #
        #   1. Write a plan handler method (e.g. ``_plan_backup``) with
        #      signature ``(Item, Platform, Path, SyncAction) -> SyncPlan | None``.
        #      Add it to ``_plan_handlers`` below.
        #
        #   2. Write an execute handler method (e.g. ``_execute_backup``) with
        #      signature ``(SyncPlan) -> SyncResult``.  Add it to
        #      ``_action_handlers`` below.
        #
        #   3. If the new action should appear in ``SyncReport.summary()``,
        #      add it to the ``aggregate()`` method's ``action_to_list`` dict.
        #
        # The ``_plan_single`` and ``_execute_single`` methods dispatch
        # through these dicts automatically — no other changes needed.
        self._plan_handlers: dict[
            SyncAction,
            Callable[[Item, Platform, Path, SyncAction], SyncPlan | None],
        ] = {
            SyncAction.INSTALL: self._plan_install_or_update,
            SyncAction.UPDATE: self._plan_install_or_update,
            SyncAction.UNINSTALL: self._plan_uninstall,
        }

        # Strategy dispatch: map each SyncAction to a dedicated *execution*
        # handler.  Mirrors the planning dispatch above for consistency.
        self._action_handlers: dict[SyncAction, Callable[[SyncPlan], SyncResult]] = {
            SyncAction.SKIP: self._execute_skip,
            SyncAction.INSTALL: self._execute_install,
            SyncAction.UPDATE: self._execute_update,
            SyncAction.UNINSTALL: self._execute_uninstall,
        }

    # -- public API -------------------------------------------------------

    def plan_sync(
        self,
        items: list[Item],
        platforms: tuple[Platform, ...],
        action: SyncAction = SyncAction.INSTALL,
    ) -> list[SyncPlan]:
        """Build a :term:`SyncPlan` for every (item, platform) pair.

        For each item the set of candidate platforms is intersected with the
        caller-supplied *platforms* filter so that only supported combinations
        are considered.

        The *action* parameter controls the planning strategy:

        * ``INSTALL`` — items that are not yet on the target are planned for
          installation; already-installed items are skipped.
        * ``UPDATE`` — items that are already installed are planned for
          update.
        * ``UNINSTALL`` — installed items are planned for removal.

        Args:
            items: Source items to plan for.
            platforms: Platform filter.
            action: Desired sync action.

        Returns:
            List of :class:`SyncPlan` instances.

        """
        plans: list[SyncPlan] = []

        for item in items:
            candidate_platforms = _iter_candidate_platforms(item, platforms)
            for platform in candidate_platforms:
                try:
                    plan = self._plan_single(item, platform, action)
                except (AgentfilesError, OSError) as exc:
                    logger.warning(
                        "Failed to plan %s for %s on %s: %s",
                        action.value,
                        item.name,
                        platform.display_name,
                        exc,
                    )
                    continue
                if plan is not None:
                    plans.append(plan)

        logger.info(
            "Planned %d operation(s) for %d item(s) across %d platform(s)",
            len(plans),
            len(items),
            len(platforms),
        )
        return plans

    def execute_plan(self, plans: list[SyncPlan]) -> list[SyncResult]:
        """Carry out each plan and collect results.

        If ``dry_run`` is enabled the plans are logged but no filesystem
        changes are made.  Failures are caught per-plan so that one bad item
        does not abort the entire batch.

        Args:
            plans: Plans to execute.

        Returns:
            List of :class:`SyncResult` instances in the same order.

        """
        results: list[SyncResult] = []

        for plan in plans:
            try:
                result = self._execute_single(plan)
            except Exception as exc:
                # Isolate failures: a single unhandled exception must not
                # abort the remaining plans in the batch.
                logger.error(
                    "Unexpected error executing %s for %s: %s",
                    plan.action.value,
                    plan.item.name,
                    exc,
                    exc_info=True,
                )
                result = SyncResult(
                    plan=plan,
                    is_success=False,
                    message=f"Unexpected error: {exc}",
                )
            results.append(result)

        return results

    def _run(
        self,
        items: list[Item],
        platforms: tuple[Platform, ...],
        action: SyncAction,
        source_dir: Path | None = None,
    ) -> SyncReport:
        """Orchestrate the full plan → execute → report pipeline.

        This is the shared implementation behind :meth:`sync` and
        :meth:`uninstall`.  It delegates to :meth:`plan_sync`,
        :meth:`execute_plan`, and :meth:`aggregate` in sequence and
        logs the resulting summary.

        When *source_dir* is provided and *action* is ``INSTALL``, the
        sync state file is updated after successful execution so that
        subsequent ``compute_sync_plan`` calls can determine which items
        have been synced.
        """
        plans = self.plan_sync(items, platforms, action=action)
        results = self.execute_plan(plans)
        report = self.aggregate(results)
        logger.info(report.summary())

        # Persist sync state after pull operations so that bidirectional
        # sync (compute_sync_plan) can track which items have been synced.
        if (
            source_dir is not None
            and not self._dry_run
            and action == SyncAction.INSTALL
            and any(r.is_success for r in results)
        ):
            self._update_sync_state(results, source_dir)

        return report

    def sync(
        self,
        items: list[Item],
        platforms: tuple[Platform, ...] = _DEFAULT_PLATFORMS,
        *,
        source_dir: Path | None = None,
    ) -> SyncReport:
        """Plan and execute installation of items to target platforms.

        Args:
            items: Items to sync.
            platforms: Platforms to target.
            source_dir: Root of the source repository.  When provided,
                the sync state file (``.agentfiles.state.yaml``) is
                updated after successful installation so that
                ``compute_sync_plan`` can track which items have been
                synced on subsequent runs.

        Returns:
            Aggregated :class:`SyncReport`.

        """
        return self._run(items, platforms, action=SyncAction.INSTALL, source_dir=source_dir)

    def uninstall(
        self,
        items: list[Item],
        platforms: tuple[Platform, ...] = _DEFAULT_PLATFORMS,
    ) -> SyncReport:
        """Plan and execute removal of items from target platforms.

        Args:
            items: Items to uninstall.
            platforms: Platforms to remove from.

        Returns:
            Aggregated :class:`SyncReport`.

        """
        return self._run(items, platforms, action=SyncAction.UNINSTALL)

    def push(
        self,
        items: list[Item],
        platforms: tuple[Platform, ...],
        *,
        source_dir: Path,
        dry_run: bool = False,
    ) -> SyncReport:
        """Push items from local configs back to the source repository.

        This is the reverse of :meth:`sync`: copies FROM target directories
        TO *source_dir*.  For file-based items (agents, commands) the
        installed file is copied back to its original location under
        *source_dir*.  For directory-based items (skills, plugins) the
        entire installed directory is copied back.

        Args:
            items: Items to push.
            platforms: Platforms to push from.
            source_dir: Root directory of the source repository.
            dry_run: If ``True``, plan operations without executing them.

        Returns:
            Aggregated :class:`SyncReport`.

        """
        results: list[SyncResult] = []
        # Track (item, platform) for each result so we can update state.
        push_contexts: list[tuple[Item, Platform]] = []

        for item in items:
            candidate_platforms = _iter_candidate_platforms(item, platforms)
            for platform in candidate_platforms:
                target_dir = self._target_manager.get_target_dir(
                    platform,
                    item.item_type,
                )
                if target_dir is None:
                    logger.warning(
                        "No target directory for %s on %s — skipping push",
                        item.name,
                        platform.display_name,
                    )
                    continue

                result = self._push_item(
                    item,
                    target_dir,
                    source_dir,
                    dry_run,
                )
                results.append(result)
                push_contexts.append((item, platform))

        report = self.aggregate(results)
        logger.info("Push complete: %s", report.summary())

        # Update state file after successful push.
        has_successful_push = any(r.is_success for r in results)
        if not dry_run and has_successful_push:
            self._update_push_state(
                results,
                push_contexts,
                source_dir,
            )

        return report

    def compute_sync_plan(
        self,
        items: list[Item],
        platforms: tuple[Platform, ...],
        state: SyncState,
        source_dir: Path,
    ) -> list[tuple[Item, Platform, str]]:
        """Compute what needs to be pulled, pushed, or is in conflict.

        Checks each item against the target platform to determine whether
        it needs to be pulled from the source repository.

        Args:
            items: Source items to evaluate.
            platforms: Platforms to check.
            state: Previously recorded sync state.
            source_dir: Root directory of the source repository.

        Returns:
            List of ``(item, platform, action)`` tuples where *action* is
            ``"pull"``, ``"push"``, ``"conflict"``, or ``"skip"``.

        Logic:
            - item not at target → ``"pull"``
            - item exists at target → ``"skip"``

        """
        plan: list[tuple[Item, Platform, str]] = []

        for item in items:
            candidate_platforms = _iter_candidate_platforms(item, platforms)
            for platform in candidate_platforms:
                action = self._compute_item_action(
                    item,
                    platform,
                    state,
                    source_dir,
                )
                plan.append((item, platform, action))

        counts = Counter(action for _, _, action in plan)
        logger.info(
            "Sync plan: %d pull, %d push, %d conflict, %d skip",
            counts["pull"],
            counts["push"],
            counts["conflict"],
            counts["skip"],
        )
        return plan

    # -- private helpers --------------------------------------------------

    @staticmethod
    def _dest_path(item: Item, target_dir: Path) -> Path:
        """Compute the full destination path for *item* within *target_dir*."""
        return get_item_dest_path(target_dir, item)

    def _plan_single(
        self,
        item: Item,
        platform: Platform,
        action: SyncAction,
    ) -> SyncPlan | None:
        """Build a single plan for (item, platform).

        Dispatches to the handler registered in ``_plan_handlers`` for the
        given *action*.  Adding a new action type only requires registering
        a new handler in ``__init__`` — this method stays unchanged.
        """
        target_dir = self._target_manager.get_target_dir(platform, item.item_type)
        if target_dir is None:
            logger.warning(
                "No target directory for %s on %s — skipping",
                item.name,
                platform.display_name,
            )
            return None

        handler = self._plan_handlers.get(action)
        if handler is not None:
            return handler(item, platform, target_dir, action)

        logger.warning("Unsupported plan action %s for %s", action.value, item.name)
        return None

    def _plan_install_or_update(
        self,
        item: Item,
        platform: Platform,
        target_dir: Path,
        requested_action: SyncAction,
    ) -> SyncPlan | None:
        """Plan install or update based on whether the item exists on disk."""
        dest_path = self._dest_path(item, target_dir)
        try:
            is_installed = dest_path.exists()
        except OSError:
            logger.warning("Cannot check existence of %s", dest_path)
            return None

        if is_installed:
            determined_action = SyncAction.SKIP
            reason = "already installed"
        else:
            determined_action = SyncAction.INSTALL
            reason = "not installed"

        if requested_action == SyncAction.UPDATE and determined_action == SyncAction.INSTALL:
            return None  # Skip items not yet installed when action=UPDATE requested

        return SyncPlan(
            item=item,
            action=determined_action,
            target_dir=target_dir,
            reason=reason,
        )

    def _plan_uninstall(
        self,
        item: Item,
        platform: Platform,
        target_dir: Path,
        _requested_action: SyncAction,
    ) -> SyncPlan | None:
        """Plan uninstall — only if the item actually exists.

        *_requested_action* is accepted for interface consistency with the
        dispatch table but is intentionally unused — the planned action is
        always ``UNINSTALL`` (or ``SKIP`` if the item is absent).
        """
        dest_path = self._dest_path(item, target_dir)

        if not dest_path.exists():
            return SyncPlan(
                item=item,
                action=SyncAction.SKIP,
                target_dir=target_dir,
                reason="not installed — nothing to remove",
            )

        return SyncPlan(
            item=item,
            action=SyncAction.UNINSTALL,
            target_dir=target_dir,
            reason="installed — scheduled for removal",
        )

    def _execute_single(self, plan: SyncPlan) -> SyncResult:
        """Execute a single plan via the action-handler dispatch table.

        When ``dry_run`` is enabled the action is logged but no filesystem
        changes are made.  Otherwise the plan's ``action`` field is used as
        a key into ``_action_handlers`` to locate the appropriate execution
        method (e.g. ``_execute_install`` for ``SyncAction.INSTALL``).
        """
        if self._dry_run:
            msg = f"dry-run: would {plan.action.value} {plan.item.name}"
            logger.info(msg)
            return SyncResult(plan=plan, is_success=True, message=msg)

        handler = self._action_handlers.get(plan.action)
        if handler is not None:
            return handler(plan)

        # Fallback — should be unreachable given the SyncAction enum.
        return SyncResult(
            plan=plan,
            is_success=False,
            message=f"Unknown action: {plan.action.value}",
        )

    def _execute_skip(self, plan: SyncPlan) -> SyncResult:
        """Handle a SKIP action — log and return success."""
        logger.debug("Skipped %s: %s", plan.item.name, plan.reason)
        return SyncResult(plan=plan, is_success=True, message=plan.reason)

    def _execute_install(self, plan: SyncPlan) -> SyncResult:
        """Perform a fresh install by copying or symlinking to the target."""
        source = plan.item.source_path
        dest = self._dest_path(plan.item, plan.target_dir)

        try:
            plan.target_dir.mkdir(parents=True, exist_ok=True)
        except (PermissionError, OSError) as exc:
            msg = f"Cannot create target directory {plan.target_dir}: {exc}"
            logger.error(msg)
            return SyncResult(plan=plan, is_success=False, message=msg)

        # Remove stale symlinks or files before installing.
        # os.path.lexists returns True for regular files, directories, and
        # symlinks (even broken ones) — a single syscall vs two.
        if os.path.lexists(dest):
            removed, rm_err = _remove_item(dest)
            if not removed:
                msg = f"Cannot remove stale destination {dest}: {rm_err}"
                logger.error(msg)
                return SyncResult(plan=plan, is_success=False, message=msg)

        files_copied, err = _copy_item(source, dest, self._use_symlinks)
        if err:
            return SyncResult(plan=plan, is_success=False, message=err)

        return SyncResult(
            plan=plan,
            is_success=True,
            message=f"Installed {plan.item.name}",
            files_copied=files_copied,
        )

    def _execute_update(self, plan: SyncPlan) -> SyncResult:
        """Perform an atomic update using a temp file + backup swap."""
        source = plan.item.source_path
        dest = self._dest_path(plan.item, plan.target_dir)

        plan.target_dir.mkdir(parents=True, exist_ok=True)

        files_copied, err = self._atomic_copy_to(
            source,
            dest,
            use_symlinks=self._use_symlinks,
        )
        if err:
            return SyncResult(plan=plan, is_success=False, message=err)

        return SyncResult(
            plan=plan,
            is_success=True,
            message=f"Updated {plan.item.name}",
            files_copied=files_copied,
        )

    def _execute_uninstall(self, plan: SyncPlan) -> SyncResult:
        """Remove an installed item from the target."""
        dest = self._dest_path(plan.item, plan.target_dir)

        removed, error = _remove_item(dest)
        if not removed:
            return SyncResult(plan=plan, is_success=False, message=error or "Unknown error")

        return SyncResult(
            plan=plan,
            is_success=True,
            message=f"uninstalled {plan.item.name}",
        )

    def _push_item(
        self,
        item: Item,
        target_dir: Path,
        source_dir: Path,
        dry_run: bool,
    ) -> SyncResult:
        """Push a single item from target back to source.

        Uses the same atomic copy pattern as sync (temp → backup → rename).
        Compares local (target) with destination (source repo) to classify
        the push as "new", "changed", or "unchanged".
        """
        local_path = get_item_dest_path(target_dir, item)
        dest_path = get_push_dest_path(source_dir, item)

        plan = SyncPlan(
            item=item,
            action=SyncAction.UPDATE,
            target_dir=target_dir,
            reason="push to source repository",
        )

        if not local_path.exists():
            return SyncResult(
                plan=plan,
                is_success=False,
                message=f"Item not found at target: {local_path}",
            )

        # Compute diff status before any early returns.
        push_status = _compare_push_item(local_path, dest_path)
        push_detail = _format_size_diff(local_path, dest_path) if push_status == "changed" else ""

        if push_status == "unchanged":
            return SyncResult(
                plan=plan,
                is_success=True,
                message=f"Unchanged {item.name}",
                push_status="unchanged",
                push_detail=push_detail,
            )

        if dry_run:
            msg = f"dry-run: would push {item.name} to {dest_path}"
            logger.info(msg)
            return SyncResult(
                plan=plan,
                is_success=True,
                message=msg,
                push_status=push_status,
                push_detail=push_detail,
            )

        dest_path.parent.mkdir(parents=True, exist_ok=True)

        files_copied, err = self._atomic_copy_to(
            local_path,
            dest_path,
            use_symlinks=False,
        )
        if err:
            return SyncResult(
                plan=plan,
                is_success=False,
                message=err,
                push_status=push_status,
                push_detail=push_detail,
            )

        return SyncResult(
            plan=plan,
            is_success=True,
            message=f"Pushed {item.name}",
            files_copied=files_copied,
            push_status=push_status,
            push_detail=push_detail,
        )

    def _update_sync_state(
        self,
        results: list[SyncResult],
        source_dir: Path,
    ) -> None:
        """Update the state file after a successful pull (install/update).

        Records the sync timestamp for each successful result.
        """
        try:
            state = load_sync_state(source_dir)
        except Exception:
            logger.warning(
                "Failed to load sync state from %s — state will not be updated",
                source_dir,
                exc_info=True,
            )
            return

        now = datetime.now(tz=timezone.utc).isoformat()

        for result in results:
            if not result.is_success:
                continue

            plan = result.plan
            if plan.action == SyncAction.UNINSTALL:
                continue

            platform = self._target_manager.resolve_platform_for(
                plan.item.item_type,
                plan.target_dir,
            )
            if platform is None:
                logger.debug(
                    "Cannot resolve platform for %s — skipping state update",
                    plan.item.name,
                )
                continue

            item = plan.item
            item_key = item.item_key
            platform_key = platform.value

            if platform_key not in state.platforms:
                target_dir = self._target_manager.get_target_dir(
                    platform,
                    item.item_type,
                )
                state.platforms[platform_key] = PlatformState(
                    path=str(target_dir) if target_dir else "",
                )

            state.platforms[platform_key].items[item_key] = ItemState(
                synced_at=now,
            )

        state.last_sync = now

        try:
            save_sync_state(source_dir, state)
        except Exception:
            logger.warning(
                "Failed to save sync state to %s — state file may be stale",
                source_dir,
                exc_info=True,
            )

    def _update_push_state(
        self,
        results: list[SyncResult],
        push_contexts: list[tuple[Item, Platform]],
        source_dir: Path,
    ) -> None:
        """Update the state file after a successful push operation."""
        try:
            state = load_sync_state(source_dir)
        except Exception:
            logger.warning(
                "Failed to load sync state from %s — push state will not be updated",
                source_dir,
                exc_info=True,
            )
            return

        now = datetime.now(tz=timezone.utc).isoformat()

        for result, (item, platform) in zip(results, push_contexts, strict=True):
            if not result.is_success:
                continue

            item_key = item.item_key
            platform_key = platform.value

            target_dir = self._target_manager.get_target_dir(
                platform,
                item.item_type,
            )

            if platform_key not in state.platforms:
                state.platforms[platform_key] = PlatformState(
                    path=str(target_dir) if target_dir else "",
                )
            state.platforms[platform_key].items[item_key] = ItemState(
                synced_at=now,
            )

        state.last_sync = now

        try:
            save_sync_state(source_dir, state)
        except Exception:
            logger.warning(
                "Failed to save sync state to %s — state file may be stale",
                source_dir,
                exc_info=True,
            )

    @staticmethod
    def _atomic_copy_to(
        source: Path,
        dest: Path,
        *,
        use_symlinks: bool = False,
    ) -> tuple[int, str | None]:
        """Atomically copy *source* to *dest* via temp file + backup swap.

        The algorithm proceeds in four steps:

        1. **Stage** — copy *source* to a ``.agentfiles_tmp`` file next to
           *dest*.  Any stale temp file from a previous interrupted run is
           removed first.

        2. **Backup** — if *dest* already exists, rename it to ``.bak``.
           This preserves the old content for rollback.

        3. **Commit** — atomically rename the temp file into *dest*.  On
           POSIX, ``rename(2)`` is atomic within a single filesystem, so
           readers of *dest* never see a partially-written file.

        4. **Cleanup** — on success, delete the ``.bak`` file.  On failure
           at step 3, restore *dest* from backup (rollback) or simply
           remove the temp file if no backup was created.

        Returns ``(files_copied, error_message)`` where *error_message*
        is ``None`` on success.
        """
        # Place the temp file next to dest so that rename() stays within the
        # same filesystem — cross-device renames are not atomic on POSIX.
        tmp_dest = dest.with_suffix(dest.suffix + ".agentfiles_tmp")

        # Clean stale tmp from a previous interrupted operation.
        if os.path.lexists(tmp_dest):
            removed, rm_err = _remove_item(tmp_dest)
            if not removed:
                msg = f"Cannot remove stale temp file {tmp_dest}: {rm_err}"
                logger.error(msg)
                return 0, msg

        files_copied, err = _copy_item(source, tmp_dest, use_symlinks)
        if err:
            # Best-effort cleanup of partial temp file.
            if os.path.lexists(tmp_dest):
                _remove_item(tmp_dest)
            return 0, err

        backup = dest.with_suffix(dest.suffix + ".bak")
        backup_existed = False
        if os.path.lexists(dest):
            try:
                dest.rename(backup)
                backup_existed = True
            except OSError as move_err:
                # Could not back up existing dest — clean up temp and bail.
                _remove_item(tmp_dest)
                msg = f"Cannot back up existing {dest} to {backup}: {move_err}"
                logger.error(msg)
                return 0, msg

        try:
            tmp_dest.rename(dest)
        except OSError as rename_err:
            # Attempt rollback: restore backup.
            if backup_existed and os.path.lexists(backup):
                try:
                    backup.rename(dest)
                except OSError as restore_err:
                    logger.critical(
                        "CRITICAL: Failed to restore backup %s -> %s: %s. "
                        "Manual recovery required.",
                        backup,
                        dest,
                        restore_err,
                    )
                else:
                    logger.info("Rolled back %s after rename failure", dest)
            else:
                # No backup existed — clean up temp file.
                if os.path.lexists(tmp_dest):
                    _remove_item(tmp_dest)
            msg = f"Atomic rename failed for {dest}: {rename_err}"
            logger.error(msg)
            return 0, msg

        # Success — clean up backup.
        if os.path.lexists(backup):
            _, rm_err = _remove_item(backup)
            if rm_err:
                logger.warning(
                    "Orphaned backup file at %s after successful atomic copy: %s",
                    backup,
                    rm_err,
                )

        return files_copied, None

    def _compute_item_action(
        self,
        item: Item,
        platform: Platform,
        state: SyncState,
        source_dir: Path,
    ) -> str:
        """Determine the sync action for a single (item, platform) pair.

        Without checksums, checks if the item exists at the target.
        Returns "pull" if not installed, "skip" if installed.
        """
        target_dir = self._target_manager.get_target_dir(platform, item.item_type)
        if target_dir is None:
            return "skip"

        target_path = get_item_dest_path(target_dir, item)
        if not target_path.exists():
            return "pull"

        return "skip"

    @staticmethod
    def aggregate(results: list[SyncResult]) -> SyncReport:
        """Classify results into a :class:`SyncReport`.

        EXTENSION POINT — Adding a new SyncAction
        ==========================================
        When a new SyncAction is added, update ``action_to_list`` below
        to map the new action to a list attribute on ``SyncReport``.
        Unmapped actions fall through to ``report.skipped`` by default.
        """
        report = SyncReport()
        action_to_list: dict[SyncAction, list[SyncResult]] = {
            SyncAction.INSTALL: report.installed,
            SyncAction.UPDATE: report.updated,
            SyncAction.UNINSTALL: report.uninstalled,
            SyncAction.SKIP: report.skipped,
        }
        for result in results:
            if not result.is_success:
                report.failed.append(result)
                continue
            target = action_to_list.get(result.plan.action, report.skipped)
            target.append(result)
        return report
