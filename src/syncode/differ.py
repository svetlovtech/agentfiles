"""Compare source items with installed items and classify differences.

The :class:`Differ` uses a :class:`~syncode.target.TargetManager` to inspect
what is currently installed on each target platform, then compares checksums
against the source repository to produce :class:`~syncode.models.DiffEntry`
objects.

**Comparison strategy** — each item is evaluated through a three-stage pipeline:

1. **Installation check** — query ``TargetManager.is_item_installed`` to
   determine whether the item exists at all on the target platform.
   Missing items are classified as :attr:`~syncode.models.DiffStatus.NEW`
   immediately.

2. **Metadata pre-check** — compare lightweight filesystem metadata (file
   size for files; file count and total byte size for directories).  When
   metadata differs the item is classified as
   :attr:`~syncode.models.DiffStatus.UPDATED` without computing a checksum,
   avoiding the expensive SHA-256 I/O for large directories.

3. **Checksum comparison** — when metadata matches (or is unavailable),
   compute SHA-256 digests for both source and target and compare them.
   Matching digests yield :attr:`~syncode.models.DiffStatus.UNCHANGED`;
   mismatches yield :attr:`~syncode.models.DiffStatus.UPDATED`.

**Content diff** — when verbose output is requested,
:func:`compute_content_diff` reads both source and target file contents
and produces a unified diff using :func:`difflib.unified_diff`.  This is
only performed on-demand to avoid unnecessary I/O.

**Performance notes:**

* Source checksums are computed **once per item** and reused across all
  applicable platforms rather than recomputed per platform.  When
  ``item.checksum`` is already populated (e.g. from a scan cache) the
  source checksum computation is skipped entirely.
* The metadata pre-check short-circuits the SHA-256 computation when
  source and target clearly differ in size or file count.
* Content diff computation is deferred until explicitly requested via
  the ``--verbose`` CLI flag.

**Error resilience:**

* Individual item failures are caught and logged so that one broken item
  does not prevent the rest from being diffed.
* Permission errors, vanished files, and I/O failures produce meaningful
  :class:`~syncode.models.DiffEntry` objects rather than raising.
"""

from __future__ import annotations

import contextlib
import difflib
import logging
import os
from pathlib import Path

from syncode.models import (
    DiffEntry,
    DiffStatus,
    Item,
    Platform,
    SourceError,
    SyncodeError,
    TargetError,
    compute_checksum,
)
from syncode.paths import get_item_dest_path, read_item_content
from syncode.target import TargetManager

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------


def _resolve_target_path(
    item: Item,
    platform: Platform,
    target_manager: TargetManager,
) -> Path | None:
    """Resolve the on-disk path for *item* on *platform*.

    Returns ``None`` when the platform has not been discovered or does
    not support the item's type.
    """
    try:
        target_dir = target_manager.get_target_dir(platform, item.item_type)
    except TargetError:
        return None
    if target_dir is None:
        return None
    return get_item_dest_path(target_dir, item)


def _compute_target_checksum(
    item: Item,
    platform: Platform,
    target_manager: TargetManager,
) -> str | None:
    """Compute checksum of *item* at the target location.

    Resolves the target directory for the item's type on *platform*,
    locates the matching entry by name, and computes its checksum.

    Returns:
        Hex SHA-256 digest, or ``None`` when the item is not installed
        or the target path cannot be read.

    """
    target_path = _resolve_target_path(item, platform, target_manager)

    if target_path is None:
        logger.debug(
            "Platform %s not available for checksum of %s",
            platform.display_name,
            item.name,
        )
        return None

    if not target_path.exists():
        return None

    try:
        return compute_checksum(target_path)
    except PermissionError:
        logger.warning(
            "Permission denied computing checksum for %s at %s",
            item.name,
            target_path,
            exc_info=True,
        )
        return None
    except (SourceError, OSError):
        logger.debug(
            "Failed to compute checksum for %s at %s",
            item.name,
            target_path,
            exc_info=True,
        )
        return None


def _classify_checksums(
    source_checksum: str, target_checksum: str | None
) -> tuple[DiffStatus, str]:
    """Determine diff status by comparing source and target checksums.

    Decision tree:

    * ``target_checksum is None`` → ``NEW`` (target could not be read).
    * ``source_checksum == target_checksum`` → ``UNCHANGED``.
    * Otherwise → ``UPDATED`` (content differs).

    Args:
        source_checksum: Hex SHA-256 digest of the source content.
        target_checksum: Hex SHA-256 digest of the target content,
            or ``None`` when the target could not be read.

    Returns:
        Tuple of (status, human-readable details).

    """
    if target_checksum is None:
        return DiffStatus.NEW, "target checksum could not be read"
    if source_checksum == target_checksum:
        return DiffStatus.UNCHANGED, "checksums match"
    return DiffStatus.UPDATED, "checksum differs"


def _dir_stats(path: Path) -> tuple[int, int]:
    """Return (file_count, total_bytes) for a directory in one walk.

    Returns ``-1, -1`` when the stats cannot be determined or *path* is
    not a directory.
    """
    if not path.is_dir():
        return -1, -1
    count = 0
    total = 0
    try:
        for root, _dirs, files in os.walk(path):
            for fname in files:
                with contextlib.suppress(OSError):
                    total += os.path.getsize(Path(root) / fname)
                count += 1
    except OSError:
        return -1, -1
    return count, total


def _path_total_size(path: Path) -> int:
    """Return total byte size for a file or directory.

    For files returns ``st_size`` directly.  For directories sums the
    sizes of all regular files found via :func:`os.walk`.

    Returns ``-1`` when the size cannot be determined.
    """
    if not path.exists():
        return -1

    if path.is_file():
        try:
            return path.stat().st_size
        except OSError:
            return -1

    if path.is_dir():
        count, total = _dir_stats(path)
        return total if count >= 0 else -1

    return -1


def _dir_file_count(path: Path) -> int:
    """Return the number of regular files under *path* (recursive).

    Returns ``-1`` when the count cannot be determined.
    """
    if not path.is_dir():
        return -1
    count, _total = _dir_stats(path)
    return count


# ---------------------------------------------------------------------------
# Differ class
# ---------------------------------------------------------------------------


class Differ:
    """Compares source items with installed items on target platforms.

    For each source :class:`~syncode.models.Item`, the differ determines which
    platforms it applies to, then classifies the installed state as one of:

    * :attr:`~syncode.models.DiffStatus.NEW`        — not present at target.
    * :attr:`~syncode.models.DiffStatus.UPDATED`    — present but content
      differs from source.
    * :attr:`~syncode.models.DiffStatus.UNCHANGED`  — present and content
      matches source.
    * :attr:`~syncode.models.DiffStatus.DELETED`    — was installed during
      the check but vanished before the checksum could be read.

    The comparison uses a three-stage strategy (see module docstring) that
    minimises expensive I/O by short-circuiting on metadata mismatches.

    Errors during comparison (permission denied, vanished files, I/O
    failures) are caught per-item so that a single failure does not abort
    the entire diff operation.

    Args:
        target_manager: Provides access to discovered platform targets.

    """

    def __init__(self, target_manager: TargetManager) -> None:
        """Initialise the Differ with a target manager."""
        self._target_manager = target_manager
        logger.debug("Differ initialised")

    def diff(
        self,
        items: list[Item],
        platforms: tuple[Platform, ...] | None = None,
    ) -> dict[Platform, list[DiffEntry]]:
        """Compare source items against installed items on each platform.

        For every item, checks which platforms it supports (filtered by
        *platforms* if provided), then classifies the difference:

        * **NEW** — not installed at target.
        * **UPDATED** — installed but content differs from source.
        * **UNCHANGED** — installed and content matches.

        Performance: the source checksum is computed **once per item**
        and reused across all applicable platforms, and a lightweight
        metadata check (file size / directory file count) avoids the
        expensive SHA-256 computation when source and target clearly
        differ.

        Args:
            items: Source items to compare.
            platforms: Optional whitelist of platforms to check.
                When ``None``, all platforms supported by each item
                are considered.

        Returns:
            Mapping of platform to the list of :class:`DiffEntry` objects.

        """
        results: dict[Platform, list[DiffEntry]] = {}

        for item in items:
            try:
                applicable = self._applicable_platforms(item, platforms)
                if not applicable:
                    continue

                # PERFORMANCE: source checksum is computed once per item and
                # reused across all applicable platforms.  When item.checksum
                # is pre-populated (e.g. from a scan cache) we reuse it
                # directly, avoiding SHA-256 I/O on the source entirely.
                source_checksum = item.checksum or self._source_checksum(item)

                for platform in applicable:
                    entry = self._compare_item(
                        item,
                        platform,
                        source_checksum,
                    )
                    results.setdefault(platform, []).append(entry)
            except (SyncodeError, OSError):
                logger.warning(
                    "Failed to diff item %s, skipping",
                    item.name,
                    exc_info=True,
                )

        logger.info(
            "Diff complete: %d items across %d platform(s)",
            len(items),
            len(results),
        )
        return results

    # -- private helpers --------------------------------------------------

    def _applicable_platforms(
        self,
        item: Item,
        platforms: tuple[Platform, ...] | None,
    ) -> list[Platform]:
        """Return platforms that *item* supports, optionally filtered."""
        if platforms is not None:
            return [p for p in platforms if p in item.supported_platforms]
        return list(item.supported_platforms)

    def _compare_item(
        self,
        item: Item,
        platform: Platform,
        source_checksum: str,
    ) -> DiffEntry:
        """Classify the difference for a single item on a single platform.

        Implements the three-stage comparison pipeline:

        1. **Installation check** — if the item is not installed at the
           target, return ``NEW`` immediately.

        2. **Metadata pre-check** — compare file sizes (or directory file
           counts and total sizes).  When metadata clearly differs, return
           ``UPDATED`` without computing the expensive target checksum.

        3. **Checksum comparison** — compute the target SHA-256 digest.
           If it cannot be read, delegate to :meth:`_handle_unreadable_target`
           to distinguish between a vanished file (``DELETED``) and an
           unreadable one (``NEW``).  Otherwise compare digests to yield
           ``UNCHANGED`` or ``UPDATED``.
        """
        # Stage 1: installation check — not installed → NEW.
        is_installed = self._target_manager.is_item_installed(item, platform)

        if not is_installed:
            return DiffEntry(
                item=item,
                status=DiffStatus.NEW,
                details="not installed at target",
            )

        # Stage 2: metadata pre-check — cheap size/count comparison that
        # avoids the expensive SHA-256 computation when source and target
        # clearly differ.  This is the primary performance optimisation
        # for large directory trees.
        if self._metadata_differs(item, platform):
            return DiffEntry(
                item=item,
                status=DiffStatus.UPDATED,
                source_checksum=source_checksum,
                details="size differs",
            )

        # Stage 3: full checksum comparison — only reached when the
        # metadata check could not rule out a difference (matching sizes
        # or metadata unavailable).
        target_checksum = _compute_target_checksum(
            item,
            platform,
            self._target_manager,
        )

        # Target checksum could not be read — the file may have vanished
        # between the installation check and the checksum computation, or
        # may be unreadable due to permissions or I/O errors.
        if target_checksum is None:
            return self._handle_unreadable_target(
                item,
                platform,
                source_checksum,
            )

        # Both checksums available — compare digests to determine final status.
        status, details = _classify_checksums(source_checksum, target_checksum)
        return DiffEntry(
            item=item,
            status=status,
            source_checksum=source_checksum,
            target_checksum=target_checksum,
            details=details,
        )

    def _metadata_differs(
        self,
        item: Item,
        platform: Platform,
    ) -> bool:
        """Quick metadata comparison to skip expensive checksum computation.

        This is a **conservative** check: it only returns ``True`` when
        metadata *clearly* indicates a difference.  When metadata cannot
        be determined (permissions, missing files) it returns ``False``,
        causing the caller to fall through to the full checksum comparison.

        Strategy by item type:

        * **File items** — compare ``st_size`` directly.
        * **Directory items** — first compare recursive file counts, then
          compare total byte sizes.  Both checks must agree for the
          pre-check to pass (return ``False``).

        Returns:
            ``True`` if metadata indicates source and target differ,
            ``False`` otherwise (including when metadata is unavailable).

        """
        target_path = _resolve_target_path(
            item,
            platform,
            self._target_manager,
        )
        if target_path is None:
            return False

        source_path = item.source_path

        # File-based items: compare file sizes directly.
        if source_path.is_file():
            if not target_path.is_file():
                return True
            try:
                return source_path.stat().st_size != target_path.stat().st_size
            except PermissionError:
                logger.warning(
                    "Permission denied comparing metadata for %s",
                    item.name,
                    exc_info=True,
                )
                return False
            except OSError:
                return False

        # Directory-based items: compare file counts then total sizes.
        if source_path.is_dir() and target_path.is_dir():
            src_count, src_size = _dir_stats(source_path)
            tgt_count, tgt_size = _dir_stats(target_path)

            if src_count >= 0 and tgt_count >= 0 and src_count != tgt_count:
                return True

            if src_size >= 0 and tgt_size >= 0 and src_size != tgt_size:
                return True

        return False

    def _handle_unreadable_target(
        self,
        item: Item,
        platform: Platform,
        source_checksum: str,
    ) -> DiffEntry:
        """Handle an installed item whose target checksum could not be computed.

        Re-checks the target path to distinguish between a file that
        disappeared during comparison (returned as DELETED) and a file
        that exists but is unreadable (returned as NEW with a clear
        error message).
        """
        target_path = _resolve_target_path(
            item,
            platform,
            self._target_manager,
        )

        if target_path is None:
            return DiffEntry(
                item=item,
                status=DiffStatus.NEW,
                details="target path could not be resolved",
            )

        try:
            still_exists = target_path.exists()
        except OSError:
            still_exists = False

        if not still_exists:
            logger.warning(
                "Target file for %s disappeared during comparison on %s",
                item.name,
                platform.display_name,
            )
            return DiffEntry(
                item=item,
                status=DiffStatus.DELETED,
                source_checksum=source_checksum,
                details="target file disappeared during comparison",
            )

        logger.warning(
            "Cannot read target file for %s on %s (permission denied or I/O error)",
            item.name,
            platform.display_name,
        )
        return DiffEntry(
            item=item,
            status=DiffStatus.NEW,
            source_checksum=source_checksum,
            details="target file is unreadable (permission denied or I/O error)",
        )

    @staticmethod
    def _source_checksum(item: Item) -> str:
        """Compute checksum for the source item, returning empty on failure."""
        try:
            return compute_checksum(item.source_path)
        except (SourceError, OSError):
            logger.warning(
                "Cannot compute source checksum for %s",
                item.name,
                exc_info=True,
            )
            return ""


# ---------------------------------------------------------------------------
# Content diff — unified diff between source and target file contents
# ---------------------------------------------------------------------------

# Number of context lines to include around changes in unified diff output.
_UNIFIED_DIFF_CONTEXT_LINES = 3


def compute_content_diff(
    entry: DiffEntry,
    platform: Platform,
    target_manager: TargetManager,
) -> list[str]:
    """Compute a unified diff between source and target file contents.

    Reads the primary content file for both source and target items and
    produces a unified diff using :func:`difflib.unified_diff`.  Binary
    files and unreadable paths are handled gracefully.

    This function performs I/O and should only be called when verbose
    diff output is needed (``--verbose`` flag).

    Args:
        entry: The :class:`~syncode.models.DiffEntry` whose content to diff.
        platform: The target platform to read content from.
        target_manager: Provides access to target filesystem paths.

    Returns:
        A list of unified diff lines (without trailing newlines).
        Returns an empty list when both contents are identical or
        when the diff cannot be computed.

    """
    source_result = _read_content_safe(entry.item.source_path)

    target_path = _resolve_target_path(entry.item, platform, target_manager)
    if target_path is None:
        logger.debug(
            "No target path for %s on %s, skipping content diff",
            entry.item.name,
            platform.display_name,
        )
        return []

    target_result = _read_content_safe(target_path)

    if source_result is None or target_result is None:
        logger.debug(
            "Cannot read content for %s (source=%s, target=%s)",
            entry.item.name,
            "ok" if source_result else "unreadable",
            "ok" if target_result else "unreadable",
        )
        return []

    source_content, source_file = source_result
    target_content, target_file = target_result

    # Detect binary content by checking for null bytes in the first chunk.
    if _is_binary_content(source_content) or _is_binary_content(target_content):
        return ["  (binary file, content diff skipped)"]

    source_lines = source_content.splitlines(keepends=True)
    target_lines = target_content.splitlines(keepends=True)

    # Produce diff as "old → new" convention:
    # fromfile = installed (target/old), tofile = source (new).
    diff_lines = list(
        difflib.unified_diff(
            target_lines,
            source_lines,
            fromfile=str(target_file),
            tofile=str(source_file),
            n=_UNIFIED_DIFF_CONTEXT_LINES,
        )
    )

    # Strip trailing newlines from each line for consistent output formatting.
    return [line.rstrip("\n") for line in diff_lines]


def _read_content_safe(path: Path) -> tuple[str, Path] | None:
    """Read content from a path, returning None on any I/O failure."""
    try:
        return read_item_content(path)
    except (OSError, UnicodeDecodeError):
        logger.debug("Failed to read content from %s", path, exc_info=True)
        return None


def _is_binary_content(content: str, sample_size: int = 8192) -> bool:
    """Return True if *content* appears to be binary data.

    Checks for null bytes in the first *sample_size* characters, which
    is a reliable heuristic for distinguishing text from binary files.
    """
    return "\x00" in content[:sample_size]
