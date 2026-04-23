"""Target platform discovery and management.

This module implements a two-phase pipeline for locating and managing
configuration directories used by AI coding tools:

1. **Discovery** (:class:`TargetDiscovery`) — scans well-known filesystem
   locations for OpenCode, returning a :class:`TargetPaths` (or ``None``
   when no config directory is found).  Candidate directories are tried
   in priority order so that user overrides (e.g. ``XDG_CONFIG_HOME``)
   take precedence over default paths.

2. **Management** (:class:`TargetManager`) — wraps the discovered target
   and exposes a query API for resolving item subdirectories, checking
   whether items are installed, listing installed items, and producing
   a summary.

The convenience factory :func:`build_target_manager` ties everything together
by running discovery and then applying optional custom path overrides supplied
by the caller.
"""

from __future__ import annotations

import logging
import os
import sys
from collections import Counter
from pathlib import Path
from typing import ClassVar

from agentfiles.models import (
    _PLUGIN_EXTENSIONS,
    TARGET_PLATFORM,
    Item,
    ItemType,
    TargetError,
    TargetPaths,
)
from agentfiles.paths import get_item_dest_path

logger = logging.getLogger(__name__)

# Files that are NOT agentfiles configs — skip them during CONFIG scanning.
# These are common tool/IDE config files that happen to live in the same
# directory but are unrelated to agentfiles.
_NON_CONFIG_FILES = (
    "package.json",
    "package-lock.json",
    "tsconfig.json",
    "settings.json",
    "settings.local.json",
    "stats-cache.json",
)


# ---------------------------------------------------------------------------
# Convenience factory
# ---------------------------------------------------------------------------


def build_target_manager(
    custom_paths: dict[str, str] | None = None,
) -> TargetManager:
    """Discover OpenCode config directory and apply custom path overrides.

    Creates a :class:`TargetManager` by discovering the OpenCode config
    directory via :class:`TargetDiscovery` and then applying any custom
    path override.  Custom paths that reference unknown keys or
    non-existent directories are skipped with a warning.

    **Custom path handling:**

    * Keys other than ``"opencode"`` are logged as warnings and ignored.
    * Values are expanded via :meth:`Path.expanduser` so ``~`` is supported.
    * The path must point to an **existing directory** on disk; files and
      non-existent paths are skipped with a warning.
    * :func:`os.path.realpath` is used to resolve symlinks.  If resolution
      fails (e.g. stale mount), the path is skipped.
    * A custom path **replaces** the auto-discovered path.

    Args:
        custom_paths: Mapping of platform name (e.g. ``"opencode"``) to an
            absolute or ``~``-expanded directory path.  ``None`` is treated
            as an empty mapping.

    Returns:
        A fully configured :class:`TargetManager`.  The caller should check
        ``manager.targets is not None`` if a missing target needs special
        handling.

    """
    custom_paths = custom_paths or {}
    discovery = TargetDiscovery()
    target = discovery.discover_all()

    # Apply custom path override if provided.
    custom_path_str = custom_paths.get(TARGET_PLATFORM)
    if custom_path_str is not None:
        custom_dir = Path(custom_path_str).expanduser()
        if not custom_dir.is_dir():
            logger.warning("Custom path does not exist: %s", custom_dir)
        else:
            try:
                custom_dir = Path(os.path.realpath(custom_dir))
            except OSError as exc:
                logger.warning(
                    "Cannot resolve custom path %s: %s",
                    custom_dir,
                    exc,
                )
            else:
                target = TargetPaths(
                    platform=TARGET_PLATFORM,
                    config_dir=custom_dir,
                )

    # Warn about unknown keys in custom_paths.
    for platform_name in custom_paths:
        if platform_name != TARGET_PLATFORM:
            logger.warning("Unknown platform in custom_paths: %s", platform_name)

    return TargetManager(target)


# ---------------------------------------------------------------------------
# OpenCode candidate resolver
# ---------------------------------------------------------------------------
# Returns candidate config directories in **priority order** — the first
# existing candidate wins (see :func:`_find_existing`).  Receives a
# pre-computed ``home`` Path so that ``Path.home()`` is called only once
# per discovery cycle.


def _opencode_candidates(home: Path) -> list[Path]:
    """Return candidate OpenCode config directories in priority order.

    Resolution order:

    1. ``$XDG_CONFIG_HOME/opencode`` (when ``XDG_CONFIG_HOME`` is set).
    2. ``~/Library/Application Support/opencode`` (macOS only).
    3. ``~/.config/opencode`` (Linux / generic fallback).

    Args:
        home: Pre-resolved home directory (avoids repeated
            ``Path.home()`` calls within a discovery cycle).

    """
    xdg = os.environ.get("XDG_CONFIG_HOME")
    candidates: list[Path] = []

    if xdg:
        candidates.append(Path(xdg).expanduser() / "opencode")

    if sys.platform == "darwin":
        candidates.append(home / "Library" / "Application Support" / "opencode")

    # Linux / other — standard XDG fallback.
    candidates.append(home / ".config" / "opencode")

    return candidates


# ---------------------------------------------------------------------------
# OpenCode subdir resolver
# ---------------------------------------------------------------------------


def _opencode_subdirs(config_dir: Path) -> dict[str, Path]:
    """OpenCode uses singular directory names on disk.

    Maps plural item-type keys (``"agents"``, ``"skills"``, etc.) to the
    singular on-disk names (``agent/``, ``skill/``, etc.) beneath
    *config_dir*.  All four item types are supported.

    Args:
        config_dir: Root OpenCode configuration directory.

    """
    singular_map: dict[str, str] = {
        "agents": "agent",
        "skills": "skill",
        "commands": "command",
        "plugins": "plugin",
        "workflows": "workflow",
    }
    return {
        plural_key: (config_dir / singular_name)
        for plural_key, singular_name in singular_map.items()
    }


# ---------------------------------------------------------------------------
# Resolution helpers
# ---------------------------------------------------------------------------


def _find_existing(candidates: list[Path]) -> Path | None:
    """Return the first candidate that exists on disk, or ``None``.

    Uses :func:`os.path.realpath` instead of :meth:`Path.resolve` to
    avoid the extra Python-level overhead while producing the same
    canonical path.  Short-circuits on the first match.

    Permission errors and other OS-level failures for individual
    candidates are logged as warnings and skipped so that a single
    inaccessible directory does not prevent discovering the platform.
    """
    for candidate in candidates:
        try:
            # is_dir() combines existence + directory check in a single stat.
            if candidate.is_dir():
                # realpath resolves symlinks just like Path.resolve() but
                # with less Python-level wrapping overhead.
                resolved = Path(os.path.realpath(candidate))
                logger.debug("Found platform directory: %s", resolved)
                return resolved
        except PermissionError:
            logger.warning(
                "Permission denied checking platform directory: %s",
                candidate,
                exc_info=True,
            )
        except OSError as exc:
            logger.warning(
                "OS error checking platform directory %s: %s",
                candidate,
                exc,
                exc_info=True,
            )
    return None


# ---------------------------------------------------------------------------
# TargetDiscovery
# ---------------------------------------------------------------------------


class TargetDiscovery:
    """Discovers the OpenCode configuration directory.

    Computes ``Path.home()`` once per instance and reuses it for
    candidate resolution to avoid redundant lookups.

    Usage::

        discovery = TargetDiscovery()
        targets = discovery.discover_all()
        manager = TargetManager(targets)
    """

    def __init__(self) -> None:
        """Initialise the discovery with the current home directory."""
        self._home = Path.home()

    def discover_all(self) -> TargetPaths | None:
        """Discover the OpenCode configuration directory.

        Scans well-known filesystem locations and returns the resolved
        :class:`TargetPaths` when found, or ``None`` otherwise.

        Returns:
            :class:`TargetPaths` for OpenCode, or ``None`` if not found.

        """
        result = self.discover()

        if result is None:
            logger.warning("OpenCode not found")

        return result

    def discover(self) -> TargetPaths | None:
        """Discover the OpenCode configuration directory.

        Returns:
            :class:`TargetPaths` if the config directory exists, else ``None``.

        """
        candidates = _opencode_candidates(self._home)

        try:
            config_dir = _find_existing(candidates)
        except Exception:
            logger.warning(
                "Unexpected error scanning OpenCode candidates",
                exc_info=True,
            )
            return None

        if config_dir is None:
            logger.debug(
                "OpenCode not found (checked: %s)",
                ", ".join(str(p) for p in candidates),
            )
            return None

        try:
            subdirs = _opencode_subdirs(config_dir)
        except Exception:
            logger.warning(
                "Failed to resolve subdirs for OpenCode at %s",
                config_dir,
                exc_info=True,
            )
            subdirs = {}

        return TargetPaths(
            platform=TARGET_PLATFORM,
            config_dir=config_dir,
            subdirs=subdirs,
        )

    # -- private ---------------------------------------------------------


# ---------------------------------------------------------------------------
# TargetManager
# ---------------------------------------------------------------------------


class TargetManager:
    """Manages the discovered OpenCode target and its installed items.

    Wraps the :class:`TargetPaths` produced by :class:`TargetDiscovery` and
    provides a query API for:

    * Resolving the on-disk directory for a given ``ItemType``
      (:meth:`get_target_dir`).
    * Checking whether a specific item is already installed
      (:meth:`is_item_installed`).
    * Listing all installed items (:meth:`get_installed_items`).
    * Producing a count-based summary (:meth:`platform_summary`).

    All OS-level errors (permission denied, broken symlinks, etc.) are
    handled gracefully — individual methods return safe defaults (``None``,
    ``False``, or empty lists) rather than propagating exceptions.

    Args:
        targets: Discovered platform paths, or ``None`` when nothing was
            found.  Typically obtained via :meth:`TargetDiscovery.discover_all`.

    """

    def __init__(self, targets: TargetPaths | None) -> None:
        """Initialise the manager with the discovered target."""
        self._targets = targets
        if targets is not None:
            logger.info(
                "TargetManager initialised with platform %s at %s",
                targets.platform,
                targets.config_dir,
            )
        else:
            logger.info("TargetManager initialised with no targets")

    @property
    def targets(self) -> TargetPaths | None:
        """Return the discovered platform targets, or ``None``."""
        return self._targets

    # -- public API -------------------------------------------------------

    def get_target_dir(
        self,
        item_type: ItemType,
    ) -> Path | None:
        """Resolve the target directory for a specific item type.

        Args:
            item_type: The category of item (agent, skill, …).

        Returns:
            Absolute path to the subdirectory, or ``None`` if no target
            has been discovered or the subdirectory does not exist.

        Raises:
            TargetError: When no target has been discovered.

        """
        target_paths = self._require_target()
        # Config files live directly in the platform config root, not a
        # subdirectory.  Return the config root so callers can compute the
        # full path as ``config_root / filename``.
        if item_type == ItemType.CONFIG:
            return target_paths.config_dir
        if item_type.plural in target_paths.subdirs:
            return target_paths.subdir_for(item_type)
        return None

    def is_item_installed(self, item: Item) -> bool:
        """Check whether an item is already installed at the target.

        An item is considered installed when a directory (or file) matching
        its name exists inside the appropriate subdirectory.

        Returns ``False`` (never raises) when no target has been discovered,
        the subdirectory does not exist, or the directory cannot be accessed
        due to permission errors.

        Args:
            item: The source item to check.
        Returns:
            ``True`` if a matching entry exists on disk.

        """
        if self._targets is None:
            return False

        target_dir = self.get_target_dir(item.item_type)
        if target_dir is None:
            return False

        candidate = get_item_dest_path(target_dir, item)
        try:
            return candidate.exists()
        except PermissionError:
            logger.debug(
                "Permission denied checking %s at %s",
                item.name,
                candidate,
            )
            return False
        except OSError:
            logger.debug(
                "OS error checking %s at %s",
                item.name,
                candidate,
            )
            return False

    def get_installed_items(
        self,
    ) -> list[tuple[ItemType, str]]:
        """List all installed items.

        Scans the subdirectories of the discovered target and returns
        the type and name of every entry found.

        Permission errors and other OS-level failures while scanning
        individual subdirectories are logged as warnings and skipped
        so that a single inaccessible directory does not prevent listing
        items from other subdirectories.

        Returns:
            List of ``(item_type, name)`` tuples.

        Raises:
            TargetError: When no target has been discovered.

        """
        target_paths = self._require_target()
        items: list[tuple[ItemType, str]] = []

        for plural_key, subdir_path in target_paths.subdirs.items():
            if not self._safe_is_dir(subdir_path, plural_key):
                continue

            item_type = self._item_type_from_plural(plural_key)
            if item_type is None:
                continue

            entries = self._safe_iterdir(subdir_path, plural_key)
            if entries is None:
                continue

            for entry in entries:
                if entry.name.startswith("."):
                    continue
                # For directory-based items (skills, plugins), only consider
                # directories — skip stray files like package.json, tsconfig.json.
                # For file-based items (agents, commands), only consider files.
                try:
                    is_file = entry.is_file()
                    is_dir = entry.is_dir()
                except OSError:
                    logger.debug(
                        "Cannot stat entry %s, skipping",
                        entry,
                    )
                    continue

                if item_type.is_file_based:
                    if not is_file:
                        # Also accept directory-installed items (e.g.
                        # agents synced as <name>/<name>.md) so that
                        # status counts match what was actually installed.
                        if is_dir and item_type in (ItemType.AGENT, ItemType.COMMAND):
                            main_md = entry / f"{entry.name}.md"
                            if main_md.is_file():
                                items.append((item_type, entry.name))
                        continue
                    # Plugins: only accept known extensions to skip
                    # extensionless duplicates (e.g. "memory-compact"
                    # alongside "memory-compact.ts").
                    if item_type == ItemType.PLUGIN and entry.suffix not in _PLUGIN_EXTENSIONS:
                        continue
                    name = entry.stem
                else:
                    if not is_dir:
                        continue
                    name = entry.name

                items.append((item_type, name))

        # Config items: .json files directly in the platform config root.
        config_dir = target_paths.config_dir
        config_entries = self._safe_iterdir(config_dir, "configs")
        if config_entries is not None:
            for entry in config_entries:
                if entry.name.startswith("."):
                    continue
                if entry.suffix != ".json":
                    continue
                if entry.name in _NON_CONFIG_FILES:
                    continue
                try:
                    if not entry.is_file():
                        continue
                except OSError:
                    continue
                name = Path(entry.name).stem
                items.append((ItemType.CONFIG, name))

        return items

    def platform_summary(self) -> dict[str, int]:
        """Return a summary of installed items.

        Returns:
            Dict mapping item type plural names to their count.
            Returns an empty dict when no target is discovered.

        """
        if self._targets is None:
            return {}
        return dict(Counter(t.plural for t, _ in self.get_installed_items()))

    def owns_target_dir(
        self,
        item_type: ItemType,
        target_dir: Path,
    ) -> bool:
        """Check whether a given target directory belongs to this manager.

        With only OpenCode supported, this is a simple existence check
        comparing the resolved target directory for *item_type* against
        *target_dir*.

        Args:
            item_type: The item category used to resolve the target directory.
            target_dir: The directory to match.

        Returns:
            ``True`` if the directory matches, ``False`` otherwise.

        """
        if self._targets is None:
            return False
        return self.get_target_dir(item_type) == target_dir

    # -- private helpers --------------------------------------------------

    # Pre-built reverse lookup: plural name -> ItemType.
    # Populated from both ``ItemType.value`` (e.g. ``"agent"``) and
    # ``ItemType.plural`` (e.g. ``"agents"``) so either form resolves.
    _PLURAL_TO_ITEM_TYPE: ClassVar[dict[str, ItemType]] = {
        key: t for t in ItemType for key in (t.value, t.plural)
    }

    @staticmethod
    def _safe_is_dir(path: Path, label: str) -> bool:
        """Check *path.is_dir()*, returning ``False`` on OS errors.

        Permission and other OS errors are logged as warnings so that a
        single inaccessible directory does not prevent listing items from
        other subdirectories.

        Args:
            path: Filesystem path to test.
            label: Human-readable label for log messages.

        Returns:
            ``True`` when *path* is a directory, ``False`` otherwise
            (including on OS errors).

        """
        try:
            return path.is_dir()
        except PermissionError:
            logger.warning(
                "Permission denied accessing %s directory: %s",
                label,
                path,
                exc_info=True,
            )
            return False
        except OSError as exc:
            logger.warning(
                "OS error accessing %s directory %s: %s",
                label,
                path,
                exc,
                exc_info=True,
            )
            return False

    @staticmethod
    def _safe_iterdir(path: Path, label: str) -> list[Path] | None:
        """Return sorted entries from *path.iterdir()*, or ``None`` on error.

        Permission and other OS errors are logged as warnings.

        Args:
            path: Directory to list.
            label: Human-readable label for log messages.

        Returns:
            Sorted list of child paths, or ``None`` when the directory
            cannot be read.

        """
        try:
            return sorted(path.iterdir())
        except PermissionError:
            logger.warning(
                "Permission denied scanning %s directory: %s",
                label,
                path,
                exc_info=True,
            )
            return None
        except OSError as exc:
            logger.warning(
                "OS error scanning %s directory %s: %s",
                label,
                path,
                exc,
                exc_info=True,
            )
            return None

    def _require_target(self) -> TargetPaths:
        """Return :class:`TargetPaths` or raise.

        Centralised guard used by public methods that require a
        previously-discovered target.

        Raises:
            TargetError: When no target has been discovered.

        """
        if self._targets is None:
            raise TargetError("OpenCode has not been discovered on this system")
        return self._targets

    @classmethod
    def _item_type_from_plural(cls, plural: str) -> ItemType | None:
        """Map a plural directory name back to an :class:`ItemType`."""
        return cls._PLURAL_TO_ITEM_TYPE.get(plural)
