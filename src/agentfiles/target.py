"""Target platform discovery and management.

This module implements a two-phase pipeline for locating and managing
configuration directories used by AI coding tools:

1. **Discovery** (:class:`TargetDiscovery`) — scans well-known filesystem
   locations for each supported platform (OpenCode, Claude Code, Windsurf,
   Cursor), returning a mapping of :class:`Platform` to :class:`TargetPaths`.
   Candidate directories are tried in priority order so that user overrides
   (e.g. ``XDG_CONFIG_HOME``) take precedence over default paths.

2. **Management** (:class:`TargetManager`) — wraps discovered targets and
   exposes a query API for resolving item subdirectories, checking whether
   items are installed, listing installed items, and producing per-platform
   summaries.

Platform-specific knowledge (candidate paths, subdirectory naming conventions)
is encapsulated in two dispatch tables (``_PLATFORM_CANDIDATE_RESOLVERS`` and
``_PLATFORM_SUBDIR_RESOLVERS``).  Adding a new platform requires only:

1. Adding a :class:`Platform` enum value in ``models.py``.
2. Writing a candidate resolver function (``_<platform>_candidates``).
3. Writing a subdir resolver function (``_<platform>_subdirs``).
4. Registering both in the dispatch tables.

The convenience factory :func:`build_target_manager` ties everything together
by running discovery and then applying optional custom path overrides supplied
by the caller.
"""

from __future__ import annotations

import logging
import os
import sys
from collections import Counter
from collections.abc import Callable
from pathlib import Path
from types import MappingProxyType
from typing import ClassVar

from agentfiles.models import (
    Item,
    ItemType,
    Platform,
    TargetError,
    TargetPaths,
)
from agentfiles.paths import get_item_dest_path

logger = logging.getLogger(__name__)

# Well-known names that are NOT agentfiles items but may appear in platform
# directories (e.g. node_modules in OpenCode's plugin dir, blocklist.json in
# Claude Code's plugins dir).
_IGNORED_NAMES: frozenset[str] = frozenset(
    {
        "node_modules",
        "cache",
        "marketplaces",
        "package",
        "package-lock",
        "tsconfig",
        "vitest.config",
        "blocklist",
        "installed_plugins",
        "known_marketplaces",
    }
)

# Files that are NOT agentfiles configs — skip them during CONFIG scanning.
# These are common tool/IDE config files that happen to live in the same
# directory but are unrelated to agentfiles.
_NON_CONFIG_FILES: frozenset[str] = frozenset(
    {
        "package.json",
        "package-lock.json",
        "tsconfig.json",
        "settings.json",
        "settings.local.json",
        "stats-cache.json",
    }
)


# ---------------------------------------------------------------------------
# Convenience factory
# ---------------------------------------------------------------------------


def build_target_manager(
    custom_paths: dict[str, str] | None = None,
) -> TargetManager:
    """Discover target platforms and apply custom path overrides.

    Creates a :class:`TargetManager` by discovering all available platforms
    via :class:`TargetDiscovery` and then applying any custom path overrides.
    Custom paths that reference unknown platforms or non-existent directories
    are skipped with a warning.

    **Custom path handling:**

    * Keys must match a :class:`Platform` enum value (e.g. ``"opencode"``,
      ``"claude_code"``).  Unknown keys are logged and ignored.
    * Values are expanded via :meth:`Path.expanduser` so ``~`` is supported.
    * The path must point to an **existing directory** on disk; files and
      non-existent paths are skipped with a warning.
    * :func:`os.path.realpath` is used to resolve symlinks.  If resolution
      fails (e.g. stale mount), the path is skipped.
    * A custom path **replaces** any auto-discovered path for that platform,
      but does not affect other platforms.
    * Custom paths can also enable platforms that were **not** auto-discovered
      (e.g. providing an OpenCode path on a machine with no default install).

    Args:
        custom_paths: Mapping of platform name (e.g. ``"opencode"``) to an
            absolute or ``~``-expanded directory path.  ``None`` is treated
            as an empty mapping.

    Returns:
        A fully configured :class:`TargetManager`.  The caller should check
        ``manager.targets`` if an empty result needs special handling.

    """
    custom_paths = custom_paths or {}
    targets = TargetDiscovery().discover_all()

    for platform_name, custom_path_str in custom_paths.items():
        try:
            platform = Platform(platform_name)
        except ValueError:
            logger.warning("Unknown platform in custom_paths: %s", platform_name)
            continue

        custom_dir = Path(custom_path_str).expanduser()
        # Check existence *before* resolve() to avoid an unnecessary
        # realpath syscall when the directory is missing.
        if not custom_dir.is_dir():
            logger.warning("Custom path does not exist: %s", custom_dir)
            continue
        try:
            custom_dir = Path(os.path.realpath(custom_dir))
        except OSError as exc:
            logger.warning(
                "Cannot resolve custom path %s: %s",
                custom_dir,
                exc,
            )
            continue

        targets[platform] = TargetPaths(
            platform=platform,
            config_dir=custom_dir,
        )

    return TargetManager(targets)


# ---------------------------------------------------------------------------
# Platform candidate resolvers
# ---------------------------------------------------------------------------
# Each resolver returns a list of candidate config directories in **priority
# order** — the first existing candidate wins (see :func:`_find_existing`).
# All resolvers receive a pre-computed ``home`` Path so that ``Path.home()``
# is called only once per discovery cycle.


def _opencode_candidates(home: Path) -> list[Path]:
    """Return candidate OpenCode config directories in priority order.

    Resolution order:

    1. ``$XDG_CONFIG_HOME/opencode`` (when ``XDG_CONFIG_HOME`` is set).
    2. ``~/Library/Application Support/opencode`` (macOS only).
    3. ``~/.config/opencode`` (Linux / generic fallback).

    Args:
        home: Pre-resolved home directory (avoids repeated
            ``Path.home()`` calls when discovering multiple platforms).

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


def _claude_code_candidates(home: Path) -> list[Path]:
    """Return candidate Claude Code config directories in priority order.

    Resolution order:

    1. ``~/.claude`` — user-level configuration.
    2. ``<cwd>/.claude`` — project-level configuration.

    Args:
        home: Pre-resolved home directory.

    """
    return [home / ".claude", Path.cwd() / ".claude"]


def _windsurf_candidates(home: Path) -> list[Path]:
    """Return candidate Windsurf config directories in priority order.

    Resolution order:

    1. ``~/.codeium/windsurf/skills/`` — current Codeium-based layout.
    2. ``~/.windsurf`` — legacy fallback path.

    Args:
        home: Pre-resolved home directory.

    """
    return [home / ".codeium" / "windsurf" / "skills", home / ".windsurf"]


def _cursor_candidates(home: Path) -> list[Path]:
    """Return candidate Cursor config directories in priority order.

    Resolution order:

    1. ``~/.cursor/skills/`` — the standard Cursor skills directory.

    Args:
        home: Pre-resolved home directory.

    """
    return [home / ".cursor" / "skills"]


# ---------------------------------------------------------------------------
# Platform subdir resolvers
# ---------------------------------------------------------------------------
# Each resolver maps a platform's config directory to its item-type
# subdirectories.  The mapping key is the **plural** item-type name
# (e.g. ``"agents"``, ``"skills"``) and the value is the resolved Path.
# Platforms that share the same layout (e.g. Windsurf and Cursor both
# support only skills) can reuse the same resolver function.


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


def _claude_code_subdirs(config_dir: Path) -> dict[str, Path]:
    """Claude Code uses plural directory names.

    Supports agents, skills, commands, and plugins.

    Args:
        config_dir: Root Claude Code configuration directory.

    """
    supported: tuple[str, ...] = ("agents", "skills", "commands", "plugins", "workflows")
    return {name: config_dir / name for name in supported}


def _skills_only_subdirs(config_dir: Path) -> dict[str, Path]:
    """Shared resolver for platforms that support only skills.

    Used by Windsurf and Cursor.  The *config_dir* itself is treated as
    the skills directory (no additional subdirectory nesting).

    Args:
        config_dir: Root platform configuration directory.

    """
    return {"skills": config_dir, "workflows": config_dir / "workflows"}


# ---------------------------------------------------------------------------
# Platform dispatch tables
# ---------------------------------------------------------------------------
# Keeps a single source of truth instead of if/elif chains.
#
# EXTENSION POINT — Adding a new Platform
# ========================================
# When a new Platform is added to models.py:
#
#   1. Write a candidate resolver function above (e.g. ``_copilot_candidates``)
#      that returns config directory paths in priority order.
#
#   2. Write or reuse a subdir resolver function above (e.g. reuse
#      ``_skills_only_subdirs`` or write a new ``_copilot_subdirs``).
#
#   3. Register both in the dispatch tables below — add one entry to
#      ``_PLATFORM_CANDIDATE_RESOLVERS`` and one to
#      ``_PLATFORM_SUBDIR_RESOLVERS``.
#
# No other code in this module needs to change — ``TargetDiscovery.discover_all``
# iterates over all Platform enum values and looks up the dispatch tables
# automatically.

# Dispatch: Platform → candidate resolver function.
# Each resolver receives the pre-computed home directory to avoid
# redundant ``Path.home()`` syscalls when scanning all platforms.
_PLATFORM_CANDIDATE_RESOLVERS: dict[Platform, Callable[[Path], list[Path]]] = {
    Platform.OPENCODE: _opencode_candidates,
    Platform.CLAUDE_CODE: _claude_code_candidates,
    Platform.WINDSURF: _windsurf_candidates,
    Platform.CURSOR: _cursor_candidates,
}

# Dispatch: Platform → subdir resolver function.
_PLATFORM_SUBDIR_RESOLVERS: dict[Platform, Callable[[Path], dict[str, Path]]] = {
    Platform.OPENCODE: _opencode_subdirs,
    Platform.CLAUDE_CODE: _claude_code_subdirs,
    Platform.WINDSURF: _skills_only_subdirs,
    Platform.CURSOR: _skills_only_subdirs,
}

# ---------------------------------------------------------------------------
# Resolution helpers
# ---------------------------------------------------------------------------


def _resolve_subdirs(
    platform: Platform,
    config_dir: Path,
) -> dict[str, Path]:
    """Build the ``subdirs`` mapping for a discovered config directory.

    Looks up the platform in ``_PLATFORM_SUBDIR_RESOLVERS`` and delegates
    to the registered resolver.  Returns an empty dict for platforms with
    no registered resolver, which effectively disables item discovery for
    that platform.

    Args:
        platform: The target platform.
        config_dir: Root configuration directory (already verified to exist).

    Returns:
        Mapping of plural item-type names (e.g. ``"agents"``) to their
        resolved filesystem paths.

    """
    resolver = _PLATFORM_SUBDIR_RESOLVERS.get(platform)
    if resolver is not None:
        return resolver(config_dir)
    return {}


def _find_existing(candidates: list[Path]) -> Path | None:
    """Return the first candidate that exists on disk, or ``None``.

    Uses :func:`os.path.realpath` instead of :meth:`Path.resolve` to
    avoid the extra Python-level overhead while producing the same
    canonical path.  Short-circuits on the first match.

    Permission errors and other OS-level failures for individual
    candidates are logged as warnings and skipped so that a single
    inaccessible directory does not prevent discovering other platforms.
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
    """Discovers configuration directories for supported platforms.

    Computes ``Path.home()`` once per instance and reuses it across
    all platform candidate resolvers to avoid redundant lookups.

    Usage::

        discovery = TargetDiscovery()
        targets = discovery.discover_all()
        manager = TargetManager(targets)
    """

    def __init__(self) -> None:
        """Initialise the discovery with the current home directory."""
        self._home = Path.home()

    def discover_all(self) -> dict[Platform, TargetPaths]:
        """Discover all available platforms.

        Scans well-known filesystem locations for each supported platform
        and returns a mapping of discovered platforms to their resolved
        paths.  Platforms whose config directories are not found are
        silently omitted.

        Returns:
            Mapping of platform to its resolved :class:`TargetPaths`.

        """
        discovered: dict[Platform, TargetPaths] = {}

        for platform in Platform:
            result = self.discover(platform)
            if result is not None:
                discovered[platform] = result

        if not discovered:
            logger.warning("No target platforms discovered")

        return discovered

    def discover(self, platform: Platform) -> TargetPaths | None:
        """Discover a single platform's configuration directory.

        Args:
            platform: The platform to look for.

        Returns:
            :class:`TargetPaths` if the config directory exists, else ``None``.

        """
        candidates = self._get_candidates(platform)

        try:
            config_dir = _find_existing(candidates)
        except Exception:
            logger.warning(
                "Unexpected error scanning candidates for %s",
                platform.display_name,
                exc_info=True,
            )
            return None

        if config_dir is None:
            logger.debug(
                "Platform %s not found (checked: %s)",
                platform.display_name,
                ", ".join(str(p) for p in candidates),
            )
            return None

        try:
            subdirs = _resolve_subdirs(platform, config_dir)
        except Exception:
            logger.warning(
                "Failed to resolve subdirs for %s at %s",
                platform.display_name,
                config_dir,
                exc_info=True,
            )
            subdirs = {}

        return TargetPaths(
            platform=platform,
            config_dir=config_dir,
            subdirs=subdirs,
        )

    # -- private ---------------------------------------------------------

    def _get_candidates(self, platform: Platform) -> list[Path]:
        """Return candidate directories for the given platform."""
        resolver = _PLATFORM_CANDIDATE_RESOLVERS.get(platform)
        if resolver is None:
            return []
        return resolver(self._home)


# ---------------------------------------------------------------------------
# TargetManager
# ---------------------------------------------------------------------------


class TargetManager:
    """Manages discovered target platforms and their installed items.

    Wraps the mapping produced by :class:`TargetDiscovery` and provides
    a query API for:

    * Resolving the on-disk directory for a given ``(Platform, ItemType)``
      pair (:meth:`get_target_dir`).
    * Checking whether a specific item is already installed at a target
      (:meth:`is_item_installed`).
    * Listing all installed items for a platform (:meth:`get_installed_items`).
    * Producing a count-based summary across platforms (:meth:`platform_summary`).

    All OS-level errors (permission denied, broken symlinks, etc.) are
    handled gracefully — individual methods return safe defaults (``None``,
    ``False``, or empty lists) rather than propagating exceptions, so that
    a single inaccessible directory never prevents scanning other platforms.

    Args:
        targets: Mapping of discovered platforms to their path info.
            Typically obtained via :meth:`TargetDiscovery.discover_all`.

    """

    def __init__(self, targets: dict[Platform, TargetPaths]) -> None:
        """Initialise the manager with discovered platform targets."""
        self._targets = targets
        logger.info(
            "TargetManager initialised with %d platform(s)",
            len(targets),
        )

    @property
    def targets(self) -> dict[Platform, TargetPaths]:
        """Return a read-only view of discovered platform targets."""
        return MappingProxyType(self._targets)  # type: ignore[return-value]

    # -- public API -------------------------------------------------------

    def get_target_dir(
        self,
        platform: Platform,
        item_type: ItemType,
    ) -> Path | None:
        """Resolve the target directory for a specific item type.

        Args:
            platform: The target platform.
            item_type: The category of item (agent, skill, …).

        Returns:
            Absolute path to the subdirectory, or ``None`` if the
            platform is not discovered or the subdirectory does not exist.

        Raises:
            TargetError: When *platform* has not been discovered.

        """
        target_paths = self._require_platform(platform)
        # Config files live directly in the platform config root, not a
        # subdirectory.  Return the config root so callers can compute the
        # full path as ``config_root / filename``.
        if item_type == ItemType.CONFIG:
            return target_paths.config_dir
        if item_type.plural in target_paths.subdirs:
            return target_paths.subdir_for(item_type)
        return None

    def is_item_installed(self, item: Item, platform: Platform) -> bool:
        """Check whether an item is already installed at the target.

        An item is considered installed when a directory (or file) matching
        its name exists inside the appropriate subdirectory for the platform.

        Returns ``False`` (never raises) when the platform has not been
        discovered, the subdirectory does not exist, or the directory
        cannot be accessed due to permission errors.

        Args:
            item: The source item to check.
            platform: The target platform.

        Returns:
            ``True`` if a matching entry exists on disk.

        """
        if platform not in self._targets:
            return False

        target_dir = self.get_target_dir(platform, item.item_type)
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
        platform: Platform,
    ) -> list[tuple[ItemType, str]]:
        """List all installed items for a platform.

        Scans the subdirectories that belong to *platform* and returns
        the type and name of every entry found.

        Permission errors and other OS-level failures while scanning
        individual subdirectories are logged as warnings and skipped
        so that a single inaccessible directory does not prevent listing
        items from other subdirectories.

        Args:
            platform: The platform to scan.

        Returns:
            List of ``(item_type, name)`` tuples.

        Raises:
            TargetError: When *platform* has not been discovered.

        """
        target_paths = self._require_platform(platform)
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
                        continue
                    # Plugins: only accept known extensions to skip
                    # extensionless duplicates (e.g. "memory-compact"
                    # alongside "memory-compact.ts").
                    if item_type == ItemType.PLUGIN and entry.suffix not in (
                        ".ts",
                        ".yaml",
                        ".yml",
                        ".py",
                        ".js",
                    ):
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
                name = entry.stem
                items.append((ItemType.CONFIG, name))

        return items

    def platform_summary(self) -> dict[Platform, dict[str, int]]:
        """Return a summary of installed items per platform.

        Returns:
            Nested dict mapping each platform to a count dict keyed by
            item type (plural form).

        """
        return {
            platform: dict(Counter(t.plural for t, _ in self.get_installed_items(platform)))
            for platform in self._targets
        }

    def resolve_platform_for(
        self,
        item_type: ItemType,
        target_dir: Path,
    ) -> Platform | None:
        """Reverse-lookup which platform owns a given target directory.

        Iterates all discovered platforms and compares their resolved target
        directory for *item_type* against *target_dir*.

        This is the canonical implementation — callers (CLI, engine) should
        use this instead of maintaining their own reverse-lookup loops.

        Args:
            item_type: The item category used to resolve the platform's
                target directory.
            target_dir: The directory to match.

        Returns:
            The matching :class:`Platform`, or ``None`` if no discovered
            platform's resolved directory matches *target_dir*.

        """
        for platform in self._targets:
            td = self.get_target_dir(platform, item_type)
            if td is not None and td == target_dir:
                return platform
        return None

    # -- private helpers --------------------------------------------------

    # Pre-built reverse lookup: plural name → ItemType.
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

    def _require_platform(self, platform: Platform) -> TargetPaths:
        """Return :class:`TargetPaths` for *platform* or raise.

        Centralised guard used by public methods that require a
        previously-discovered platform.  The raised :class:`TargetError`
        message lists the available platforms to aid debugging.

        Raises:
            TargetError: When *platform* is not in ``self._targets``.

        """
        if platform not in self._targets:
            raise TargetError(
                f"platform '{platform.display_name}' has not been discovered, "
                f"available: {', '.join(p.display_name for p in self._targets)}"
            )
        return self._targets[platform]

    @classmethod
    def _item_type_from_plural(cls, plural: str) -> ItemType | None:
        """Map a plural directory name back to an :class:`ItemType`."""
        return cls._PLURAL_TO_ITEM_TYPE.get(plural)
