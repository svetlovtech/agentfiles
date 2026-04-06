"""Source scanner for discovering agentfiles items (agents, skills, commands, plugins).

Scanning strategy
-----------------
The scanner uses **convention-based directory discovery**: for each
:class:`~agentfiles.models.ItemType`, it looks for a matching subdirectory
inside the source root — first the plural form (``agents/``), then the
singular (``agent/``).  Once a content directory is found, a
type-specific scanner function walks its children, identifies valid
item definitions, and delegates parsing to
:func:`~agentfiles.models.item_from_file` (flat files) or
:func:`~agentfiles.models.item_from_directory` (subdirectories).

Scanner registry
~~~~~~~~~~~~~~~~
Each :class:`~agentfiles.models.ItemType` maps 1-to-1 to a scanner
function and its supported :class:`~agentfiles.models.Platform` values
via the module-level ``_SCANNER_REGISTRY`` dict.  This registry is
populated once at import time through :func:`_register_scanner`.

Adding a new item type requires only:

1. Define a scanner function with signature ``(dir_path, *, gitignore) -> list[Item]``.
2. Call ``_register_scanner(NewType, _scan_new_type_dir, (Platform.A, …))``.

No existing scanner code needs modification (Open/Closed Principle).

Platform assignment
~~~~~~~~~~~~~~~~~~~
Every discovered :class:`~agentfiles.models.Item` starts with empty
``supported_platforms``.  The registry lookup in :func:`_apply_platforms`
replaces that field with the platforms declared at registration time.
An optional per-``SourceScanner`` platform filter then excludes items
whose platforms don't intersect with the requested set.

Error resilience
~~~~~~~~~~~~~~~~
Individual file/directory parse errors are caught and logged per-item
so that one malformed definition never prevents the remaining items
from being discovered.  Top-level :meth:`SourceScanner.scan` also
guards each item-type pass independently.

Performance notes
-----------------
Uses :func:`os.scandir` instead of :meth:`Path.iterdir` so that
``DirEntry.is_file()`` / ``DirEntry.is_dir()`` reuse the cached ``d_type``
from the kernel directory entry, avoiding extra ``stat()`` syscalls on every
child path.  The two-phase scan in :func:`_scan_with_subdirs` reuses a
single ``scandir`` result list for both the file pass and the directory
pass.
"""

from __future__ import annotations

import fnmatch
import logging
import os
from collections import Counter
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from typing import NamedTuple

from agentfiles.models import (
    SKILL_MAIN_FILE,
    AgentfilesError,
    Item,
    ItemType,
    Platform,
    SourceError,
    item_from_directory,
    item_from_file,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# .gitignore utilities
# ---------------------------------------------------------------------------


def parse_gitignore(gitignore_path: Path) -> list[str]:
    """Read a ``.gitignore`` file and return its patterns.

    Empty lines and comments (lines starting with ``#``) are skipped.
    Each remaining line is stripped of surrounding whitespace.

    Args:
        gitignore_path: Absolute path to a ``.gitignore`` file.

    Returns:
        A list of non-empty, non-comment pattern strings.

    Raises:
        SourceError: When *gitignore_path* cannot be read.

    """
    try:
        content = gitignore_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise SourceError(
            f"cannot read .gitignore at '{gitignore_path}': {exc}. "
            f"Check file permissions or encoding (expected UTF-8)"
        ) from exc

    return [
        line
        for raw_line in content.splitlines()
        if (line := raw_line.strip()) and not line.startswith("#")
    ]


class GitIgnoreMatcher:
    """Lightweight ``.gitignore``-style path matcher.

    Supports common patterns used in this project:

    * File extensions — ``*.pyc``, ``*.log``
    * Directory names — ``__pycache__/``, ``.venv/``, ``node_modules/``
    * Negation — ``!important.pyc``
    * Simple globs via :mod:`fnmatch`

    Args:
        root_dir: Repository root used to resolve relative paths.
        patterns: List of gitignore patterns.  When empty the matcher
            never reports a path as ignored.

    """

    def __init__(self, root_dir: Path, patterns: list[str] | None = None) -> None:
        """Initialise the matcher with a root directory and optional patterns."""
        self._root = root_dir.resolve()
        self._patterns = list(patterns) if patterns else []
        self._negations = [pat[1:] for pat in self._patterns if pat.startswith("!")]
        self._ignore_patterns = [pat for pat in self._patterns if not pat.startswith("!")]

    # -- public API -------------------------------------------------------

    def is_ignored(self, path: Path) -> bool:
        """Return ``True`` when *path* matches an ignore pattern.

        The path is resolved relative to :attr:`root_dir` before matching.
        Negation patterns (``!``) take priority and un-ignore a path.
        """
        try:
            rel = path.resolve().relative_to(self._root)
        except ValueError:
            return False

        rel_str = str(rel)
        parts = rel.parts

        if self._matches_any(rel_str, parts, self._negations):
            return False

        return self._matches_any(rel_str, parts, self._ignore_patterns)

    @classmethod
    def from_directory(cls, root_dir: Path) -> GitIgnoreMatcher | None:
        """Create a matcher from ``.gitignore`` in *root_dir*.

        Returns ``None`` when no ``.gitignore`` file is found.
        """
        gitignore = root_dir / ".gitignore"
        if not gitignore.is_file():
            return None
        patterns = parse_gitignore(gitignore)
        return cls(root_dir, patterns)

    # -- private helpers --------------------------------------------------

    @staticmethod
    def _matches_any(
        rel_str: str,
        parts: tuple[str, ...],
        patterns: list[str],
    ) -> bool:
        """Check whether *rel_str* or any path part matches a pattern."""
        for pat in patterns:
            stripped = pat.rstrip("/")
            # Directory pattern (ends with /) — match against path parts.
            if pat.endswith("/"):
                if any(fnmatch.fnmatch(part, stripped) for part in parts):
                    return True
            # Glob pattern (contains *) — match full relative path and parts.
            elif "*" in pat:
                if fnmatch.fnmatch(rel_str, pat):
                    return True
                if any(fnmatch.fnmatch(part, pat) for part in parts):
                    return True
            # Exact name — match against individual parts.
            else:
                if any(part == pat for part in parts):
                    return True
        return False


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Names to always skip during scanning (hidden names handled separately).
_SKIP_NAMES = frozenset({"__pycache__", "__init__.py"})

# File extensions recognised for single-file plugin items.
_PLUGIN_EXTENSIONS = frozenset({".ts", ".yaml", ".py"})

# Maximum directory nesting depth for _has_plugin_file recursion.
_PLUGIN_SCAN_MAX_DEPTH = 10


# ---------------------------------------------------------------------------
# Scanner registry (Open/Closed Principle)
# ---------------------------------------------------------------------------
#
# The registry is the single source of truth that maps each ItemType to:
#
#   1. A scanner function — responsible for discovering items in a directory.
#   2. A platform tuple — the platforms that the item type supports.
#
# EXTENSION POINT — Adding a new ItemType
# ========================================
# When a new ItemType is added to models.py:
#
#   1. Write a scanner function matching the
#      ``(dir_path: Path, *, gitignore: GitIgnoreMatcher | None) -> list[Item]``
#      signature.
#
#   2. Call ``_register_scanner(NewType, scanner_fn, (Platform.A, ...))``
#      in the registration block below.
#
# No other code in this module needs to change — ``_apply_platforms`` and
# ``SourceScanner.scan_type`` look up the dispatch table automatically
# with safe defaults for unregistered types.


class _ScannerEntry(NamedTuple):
    """Bundles a scanner function with its supported platforms."""

    scanner: Callable[..., list[Item]]
    platforms: tuple[Platform, ...]


# Single source of truth: each ItemType maps to its scanner + platforms.
# New types only require a ``_register_scanner()`` call — no other code
# in this module needs modification.
_SCANNER_REGISTRY: dict[ItemType, _ScannerEntry] = {}


def _register_scanner(
    item_type: ItemType,
    scanner: Callable[..., list[Item]],
    platforms: tuple[Platform, ...],
) -> None:
    """Register a scanner function and its supported platforms for *item_type*.

    This is the **only** place to touch when adding a new ``ItemType``,
    satisfying the Open/Closed Principle: the module is open for extension
    (new types) but closed for modification (no existing code changes).
    """
    _SCANNER_REGISTRY[item_type] = _ScannerEntry(scanner=scanner, platforms=platforms)


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------


def _should_skip(name: str) -> bool:
    """Return ``True`` when *name* is hidden or an internal file/dir."""
    return name.startswith(".") or name in _SKIP_NAMES


def _apply_platforms(item: Item) -> Item:
    """Replace ``supported_platforms`` on *item* based on its ``item_type``.

    Returns the item unchanged (empty platforms) when the item type is
    not registered, preventing a ``KeyError`` from propagating to callers.
    """
    entry = _SCANNER_REGISTRY.get(item.item_type)
    if entry is None:
        logger.warning(
            "No scanner registered for %s — leaving platforms empty", item.item_type.value
        )
        return item
    return replace(item, supported_platforms=entry.platforms)


def _scandir_sorted(dir_path: Path) -> list[os.DirEntry[str]]:
    """Return a name-sorted list of ``DirEntry`` objects for *dir_path*.

    Uses :func:`os.scandir` so that subsequent ``is_file()`` / ``is_dir()``
    calls on each entry reuse the cached ``d_type`` from the kernel, avoiding
    extra ``stat()`` syscalls.  Returns an empty list on OS errors (e.g. the
    directory does not exist or is not readable).
    """
    try:
        return sorted(os.scandir(dir_path), key=lambda e: e.name)
    except OSError:
        return []


def _find_item_dirs(source_dir: Path, item_type: ItemType) -> Path | None:
    """Locate the content directory for *item_type* inside *source_dir*.

    Checks the plural name first (``agents/``), then the singular form
    (``agent/``).  Returns ``None`` when neither exists.

    Args:
        source_dir: Root source directory.
        item_type: The item category to locate.

    Returns:
        Resolved path to the found directory, or ``None``.

    """
    plural = source_dir / item_type.plural
    singular = source_dir / item_type.value

    for candidate in (plural, singular):
        if candidate.is_dir():
            return candidate

    return None


# ---------------------------------------------------------------------------
# Per-type directory scanners
# ---------------------------------------------------------------------------


def _scan_with_subdirs(
    dir_path: Path,
    item_type: ItemType,
    gitignore: GitIgnoreMatcher | None = None,
) -> list[Item]:
    """Scan for flat ``.md`` files *and* subdirectories with ``<dirname>.md``.

    This is a **generic** two-phase scanner used by :func:`_scan_agents_dir`
    and :func:`_scan_commands_dir`.  It is **not** registered in the scanner
    registry directly; type-specific wrappers call it with the appropriate
    :class:`~agentfiles.models.ItemType`.

    Flat files take priority over subdirectories with the same stem.
    The implementation performs a **single** ``os.scandir()`` call and
    processes cached entries in two phases (files first, then directories)
    to guarantee priority without a redundant directory listing.

    Args:
        dir_path: Directory containing item definitions.
        item_type: The category of items to scan for.
        gitignore: Optional gitignore matcher to exclude ignored paths.

    Returns:
        Deduplicated list of discovered :class:`Item` instances.

    """
    entries = _scandir_sorted(dir_path)

    items: list[Item] = []

    # Phase 1: collect flat .md files — they take priority.
    seen_stems: set[str] = set()
    for entry in entries:
        if _should_skip(entry.name) or not entry.is_file():
            continue
        child = Path(entry.path)
        if gitignore and gitignore.is_ignored(child):
            continue
        if child.suffix != ".md":
            continue
        try:
            item = item_from_file(child, item_type)
            items.append(_apply_platforms(item))
            seen_stems.add(child.stem)
        except (AgentfilesError, OSError) as exc:
            logger.warning("Skipping %s file %s: %s", item_type.value, child, exc, exc_info=True)

    # Phase 2: process subdirectories that were not already claimed by a
    # flat file.  Reuses the same *entries* list — no second scandir call.
    for entry in entries:
        if _should_skip(entry.name) or not entry.is_dir():
            continue
        child = Path(entry.path)
        if gitignore and gitignore.is_ignored(child):
            continue

        if child.name in seen_stems:
            logger.debug(
                "Skipping nested %s '%s' — already found as flat file",
                item_type.value,
                child.name,
            )
            continue

        logger.debug("Found nested %s in subdirectory: %s", item_type.value, child.name)
        try:
            main_md = child / f"{child.name}.md"
            if not main_md.is_file():
                continue

            item = item_from_directory(child, item_type)
            items.append(_apply_platforms(item))
        except (AgentfilesError, OSError) as exc:
            logger.warning(
                "Skipping %s directory %s: %s", item_type.value, child.name, exc, exc_info=True
            )

    return items


def _scan_agents_dir(
    dir_path: Path,
    gitignore: GitIgnoreMatcher | None = None,
) -> list[Item]:
    """Scan *dir_path* for agent definitions.

    **Item type**: :attr:`~agentfiles.models.ItemType.AGENT`
    **Registry platforms**: ``(OPENCODE, CLAUDE_CODE)``

    Discovers both flat ``.md`` files and subdirectories containing
    ``<dirname>.md`` (e.g. ``agents/coder/coder.md``) by delegating
    to :func:`_scan_with_subdirs`.

    Flat files take priority: if both ``coder.md`` and ``coder/coder.md``
    exist, only the flat file is included.
    """
    return _scan_with_subdirs(dir_path, ItemType.AGENT, gitignore=gitignore)


def _scan_skills_dir(
    dir_path: Path,
    gitignore: GitIgnoreMatcher | None = None,
) -> list[Item]:
    """Scan *dir_path* for skill subdirectories.

    **Item type**: :attr:`~agentfiles.models.ItemType.SKILL`
    **Registry platforms**: ``(OPENCODE, CLAUDE_CODE, WINDSURF, CURSOR)``

    Unlike agents and commands, skills are **directory-only**: each
    subdirectory must contain :data:`~agentfiles.models.SKILL_MAIN_FILE`
    (``SKILL.md``).  Flat ``.md`` files at the top level of the skills
    directory are ignored.

    Args:
        dir_path: Directory containing skill definitions.
        gitignore: Optional gitignore matcher to exclude ignored paths.

    Returns:
        List of discovered skill :class:`Item` instances.

    """
    items: list[Item] = []

    for entry in _scandir_sorted(dir_path):
        if _should_skip(entry.name) or not entry.is_dir():
            continue
        child = Path(entry.path)
        if gitignore and gitignore.is_ignored(child):
            continue
        try:
            if not (child / SKILL_MAIN_FILE).is_file():
                logger.debug("Skipping %s — no %s found", child.name, SKILL_MAIN_FILE)
                continue
            item = item_from_directory(child, ItemType.SKILL)
            items.append(_apply_platforms(item))
        except (AgentfilesError, OSError) as exc:
            logger.warning("Skipping skill directory %s: %s", child.name, exc, exc_info=True)

    return items


def _scan_commands_dir(
    dir_path: Path,
    gitignore: GitIgnoreMatcher | None = None,
) -> list[Item]:
    """Scan *dir_path* for command definitions.

    **Item type**: :attr:`~agentfiles.models.ItemType.COMMAND`
    **Registry platforms**: ``(OPENCODE,)``

    Discovers both flat ``.md`` files and subdirectories containing
    ``<dirname>.md`` (e.g. ``commands/deploy/deploy.md``) by delegating
    to :func:`_scan_with_subdirs`.

    Flat files take priority: if both ``deploy.md`` and ``deploy/deploy.md``
    exist, only the flat file is included.
    """
    return _scan_with_subdirs(dir_path, ItemType.COMMAND, gitignore=gitignore)


def _has_plugin_file(directory: Path, *, _depth: int = 0) -> bool:
    """Return ``True`` if *directory* recursively contains a plugin file.

    Called by :func:`_scan_plugins_dir` to decide whether a subdirectory
    qualifies as a plugin item.  A "plugin file" is any non-hidden file
    whose extension is in :data:`_PLUGIN_EXTENSIONS` (``.ts``, ``.yaml``,
    ``.py``).

    Uses :func:`os.scandir` recursively so that ``DirEntry.is_file()``
    reuses cached ``d_type``, avoiding ``stat()`` syscalls on every entry.
    The file extension (cheap string comparison) is checked **before**
    ``is_file()`` so that non-plugin entries skip the type check entirely.

    A depth limit prevents runaway recursion caused by pathological
    nesting or filesystem oddities (e.g. bind mounts).
    """
    if _depth > _PLUGIN_SCAN_MAX_DEPTH:
        logger.debug("Max depth (%d) reached scanning %s", _PLUGIN_SCAN_MAX_DEPTH, directory)
        return False
    try:
        it = os.scandir(directory)
    except OSError:
        return False
    with it:
        for entry in it:
            # Directories are always traversed (matches rglob("*") behaviour).
            if entry.is_dir(follow_symlinks=False):
                if _has_plugin_file(Path(entry.path), _depth=_depth + 1):
                    return True
            # For files: check extension first (cheap), then type (stat-free
            # when d_type is available), then the name filter.
            elif (
                Path(entry.name).suffix in _PLUGIN_EXTENSIONS
                and entry.is_file()
                and not _should_skip(entry.name)
            ):
                return True
    return False


# Known platform directory names for platform-specific plugin scanning.
_PLATFORM_DIR_NAMES: frozenset[str] = frozenset(p.value for p in Platform)


def _scan_plugins_dir(
    dir_path: Path,
    gitignore: GitIgnoreMatcher | None = None,
) -> list[Item]:
    """Scan *dir_path* for plugin files and plugin directories.

    **Item type**: :attr:`~agentfiles.models.ItemType.PLUGIN`
    **Registry platforms**: ``(OPENCODE,)`` (default for non-platform-specific items)

    Supports two organization styles:

    1. **Platform-specific subdirectories** — directories named after a platform
       (e.g. ``plugins/opencode/``, ``plugins/claude_code/``) are scanned for
       plugin files/directories, and items found within are assigned only to
       that platform.

    2. **Flat files and directories** — at the top level of ``plugins/``,
       single files with recognised extensions or directories containing plugin
       files are parsed as before (backward compatible), using the default
       platform tuple from the registry.

    Args:
        dir_path: Directory containing plugin definitions.
        gitignore: Optional gitignore matcher to exclude ignored paths.

    Returns:
        List of discovered plugin :class:`Item` instances.

    """
    items: list[Item] = []

    for entry in _scandir_sorted(dir_path):
        if _should_skip(entry.name):
            continue
        child = Path(entry.path)
        if gitignore and gitignore.is_ignored(child):
            continue

        # Platform-specific subdirectory (e.g. plugins/opencode/)
        if entry.is_dir() and entry.name in _PLATFORM_DIR_NAMES:
            platform = Platform(entry.name)
            items.extend(_scan_platform_plugins_dir(child, platform, gitignore))
            continue

        # Top-level flat plugin file
        if entry.is_file():
            if child.suffix not in _PLUGIN_EXTENSIONS:
                continue
            try:
                item = item_from_file(child, ItemType.PLUGIN)
                items.append(_apply_platforms(item))
            except (AgentfilesError, OSError) as exc:
                logger.warning("Skipping plugin file %s: %s", child.name, exc, exc_info=True)

        # Top-level plugin directory (not a platform name)
        elif entry.is_dir():
            if not _has_plugin_file(child):
                logger.debug("Skipping plugin dir %s — no plugin files", child.name)
                continue
            try:
                item = item_from_directory(child, ItemType.PLUGIN)
                items.append(_apply_platforms(item))
            except (AgentfilesError, OSError) as exc:
                logger.warning("Skipping plugin directory %s: %s", child.name, exc, exc_info=True)

    return items


def _scan_platform_plugins_dir(
    platform_dir: Path,
    platform: Platform,
    gitignore: GitIgnoreMatcher | None = None,
) -> list[Item]:
    """Scan a platform-specific plugin subdirectory.

    Items found within are assigned only to *platform*.

    Args:
        platform_dir: Platform subdirectory (e.g. plugins/opencode/).
        platform: The platform these plugins belong to.
        gitignore: Optional gitignore matcher.

    Returns:
        List of plugin Items assigned to *platform*.
    """
    items: list[Item] = []

    for entry in _scandir_sorted(platform_dir):
        if _should_skip(entry.name):
            continue
        child = Path(entry.path)
        if gitignore and gitignore.is_ignored(child):
            continue

        if entry.is_file():
            if child.suffix not in _PLUGIN_EXTENSIONS:
                continue
            try:
                item = item_from_file(child, ItemType.PLUGIN)
                items.append(replace(item, supported_platforms=(platform,)))
            except (AgentfilesError, OSError) as exc:
                logger.warning("Skipping plugin file %s: %s", child.name, exc, exc_info=True)

        elif entry.is_dir():
            if not _has_plugin_file(child):
                logger.debug("Skipping plugin dir %s — no plugin files", child.name)
                continue
            try:
                item = item_from_directory(child, ItemType.PLUGIN)
                items.append(replace(item, supported_platforms=(platform,)))
            except (AgentfilesError, OSError) as exc:
                logger.warning("Skipping plugin directory %s: %s", child.name, exc, exc_info=True)

    return items


# Populate the registry once all scanner functions are defined.
#
# Summary of registered scanners and their platform support:
#
#   ItemType   | Scanner function      | Platforms
#   -----------|-----------------------|----------------------------------
#   AGENT      | _scan_agents_dir      | OPENCODE, CLAUDE_CODE
#   SKILL      | _scan_skills_dir      | OPENCODE, CLAUDE_CODE, WINDSURF, CURSOR
#   COMMAND    | _scan_commands_dir    | OPENCODE
#   PLUGIN     | _scan_plugins_dir     | OPENCODE
#
# Each call is atomic: adding a new ItemType only needs one more line here.
_register_scanner(
    ItemType.AGENT,
    _scan_agents_dir,
    (Platform.OPENCODE, Platform.CLAUDE_CODE),
)
_register_scanner(
    ItemType.SKILL,
    _scan_skills_dir,
    (Platform.OPENCODE, Platform.CLAUDE_CODE, Platform.WINDSURF, Platform.CURSOR),
)
_register_scanner(
    ItemType.COMMAND,
    _scan_commands_dir,
    (Platform.OPENCODE,),
)
_register_scanner(
    ItemType.PLUGIN,
    _scan_plugins_dir,
    (Platform.OPENCODE,),
)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


class SourceScanner:
    """Discovers agentfiles items in a source directory tree.

    The scan lifecycle is:

    1. :meth:`scan` iterates over every :class:`~agentfiles.models.ItemType`.
    2. For each type, :meth:`scan_type` locates the content directory
       (``agents/`` or ``agent/``, etc.) via :func:`_find_item_dirs`.
    3. The registry dispatches to the type-specific scanner function
       (e.g. :func:`_scan_agents_dir`).
    4. Each scanner delegates parsing to :func:`~agentfiles.models.item_from_file`
       or :func:`~agentfiles.models.item_from_directory`.
    5. Platform metadata is applied from the registry; if *platforms*
       was provided at construction, items whose platforms don't
       intersect with the filter are excluded.
    6. Results are sorted by ``(item_type, name)``.

    GitIgnore integration
    ~~~~~~~~~~~~~~~~~~~~~
    On construction, a :class:`GitIgnoreMatcher` is built
    from ``.gitignore`` files in *source_dir*.  Each scanner function
    receives this matcher and skips entries that match any gitignore rule.

    Args:
        source_dir: Root directory to scan (resolved to an absolute path).
        platforms: Optional platform filter.  When ``None``, all platforms
            are included (no filtering is applied).  When provided, only
            items whose ``supported_platforms`` intersect with *platforms*
            are returned.

    Example::

        scanner = SourceScanner(Path("~/my-tools"))
        items = scanner.scan()

        # Filter to a single platform
        scanner = SourceScanner(Path("~/my-tools"), platforms=(Platform.OPENCODE,))
        items = scanner.scan()

    """

    def __init__(
        self,
        source_dir: Path,
        platforms: tuple[Platform, ...] | None = None,
    ) -> None:
        """Initialise the scanner with a source directory and optional platform filter."""
        self._source_dir = source_dir.resolve()
        self._platforms = platforms
        self._gitignore = GitIgnoreMatcher.from_directory(source_dir)

    def scan(self) -> list[Item]:
        """Scan the source directory for all item types.

        Each item type is scanned independently; errors for one type are
        logged but do not prevent the remaining types from being scanned.

        Returns:
            Items sorted by ``(item_type, name)``.

        """
        all_items: list[Item] = []

        for item_type in ItemType:
            try:
                all_items.extend(self.scan_type(item_type))
            except (AgentfilesError, OSError) as exc:
                logger.warning("Failed to scan %s: %s", item_type.plural, exc, exc_info=True)

        all_items.sort(key=lambda it: it.sort_key)

        counts = self._count_by_type(all_items)
        parts = [f"{counts.get(t, 0)} {t.plural}" for t in ItemType if counts.get(t, 0) > 0]
        logger.info("Found %s", ", ".join(parts))

        return all_items

    def scan_type(self, item_type: ItemType) -> list[Item]:
        """Scan for a single item type.

        Args:
            item_type: The category to scan.

        Returns:
            Validated items for that type, filtered by ``self._platforms``.

        """
        dir_path = _find_item_dirs(self._source_dir, item_type)
        if dir_path is None:
            logger.debug(
                "No %s directory found in %s",
                item_type.plural,
                self._source_dir,
            )
            return []

        items = self._dispatch_scan(item_type, dir_path)

        # Apply optional platform filter.
        if self._platforms is not None:
            items = [
                item
                for item in items
                if any(p in item.supported_platforms for p in self._platforms)
            ]

        return items

    def get_summary(self) -> dict[ItemType, int]:
        """Return item counts per type.

        Calls :meth:`scan` and tallies results by type.

        Returns:
            Mapping of each :class:`ItemType` to its item count.

        """
        counts = Counter(item.item_type for item in self.scan())
        return {t: counts.get(t, 0) for t in ItemType}

    def _dispatch_scan(
        self,
        item_type: ItemType,
        dir_path: Path,
    ) -> list[Item]:
        """Dispatch to the scanner registered for *item_type*.

        Looks up ``_SCANNER_REGISTRY`` for *item_type* and delegates to
        the registered scanner function.  Returns an empty list with a
        warning when the item type has no registered scanner, preventing
        a ``KeyError`` from propagating.
        """
        entry = _SCANNER_REGISTRY.get(item_type)
        if entry is None:
            logger.warning("No scanner registered for %s — skipping", item_type.value)
            return []
        return entry.scanner(dir_path, gitignore=self._gitignore)

    @staticmethod
    def _count_by_type(items: list[Item]) -> dict[ItemType, int]:
        """Count items grouped by their type."""
        return dict(Counter(item.item_type for item in items))
