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

Scope-aware discovery
~~~~~~~~~~~~~~~~~~~~~
Items can be organized by :class:`~agentfiles.models.Scope` inside the
content directory:

- ``agents/`` (flat files) → :attr:`~agentfiles.models.Scope.GLOBAL`
  (backward compatible)
- ``agents/global/`` → explicit :attr:`~agentfiles.models.Scope.GLOBAL`
- ``agents/project/`` → :attr:`~agentfiles.models.Scope.PROJECT`
- ``agents/local/`` → :attr:`~agentfiles.models.Scope.LOCAL`

:func:`_find_item_dirs` returns ``list[tuple[Path, Scope]]`` so that
:meth:`SourceScanner.scan_type` can assign the correct scope to each
discovered item.  Items from the base content directory take priority
over items from explicit scope subdirectories when both share the same
``(name, scope)`` key.

Scanner registry
~~~~~~~~~~~~~~~
Each :class:`~agentfiles.models.ItemType` maps 1-to-1 to a scanner
function via the module-level ``_SCANNER_REGISTRY`` dict.  This
registry is populated once at import time through
:func:`_register_scanner`.

Adding a new item type requires only:

1. Define a scanner function with signature ``(dir_path, *, gitignore) -> list[Item]``.
2. Call ``_register_scanner(NewType, _scan_new_type_dir)``.

No existing scanner code needs modification (Open/Closed Principle).

Error resilience
~~~~~~~~~~~~~~~
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

from agentfiles.models import (
    SKILL_MAIN_FILE,
    TARGET_PLATFORM,
    AgentfilesError,
    Item,
    ItemType,
    Scope,
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

    **Limitations** (intentional — keeps the implementation dependency-free):

    * ``**`` recursive globs are not supported; use directory patterns instead.
    * Negation (``!``) always wins regardless of order (real gitignore is
      order-dependent).
    * Leading ``/`` (anchor to repo root) is not distinguished from a bare name.

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

        Args:
            path: Filesystem path to test.

        Returns:
            ``True`` when the path matches an ignore pattern.
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

        Args:
            root_dir: Directory containing a ``.gitignore`` file.

        Returns:
            A :class:`GitIgnoreMatcher` instance, or ``None``.
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
        """Check whether *rel_str* or any path part matches a pattern.

        Args:
            rel_str: Relative path as a string.
            parts: Individual path components of the relative path.
            patterns: Gitignore patterns to match against.

        Returns:
            ``True`` when any pattern matches.

        """
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
_SKIP_NAMES = ("__pycache__", "__init__.py")

# Scope subdirectory names inside content directories (e.g. agents/global/).
_SCOPE_DIR_NAMES: frozenset[str] = frozenset(s.value for s in Scope)

# File extensions recognised for single-file plugin items.
_PLUGIN_EXTENSIONS = (".ts", ".yaml", ".yml", ".py", ".js")

# Maximum directory nesting depth for _has_plugin_file recursion.
_PLUGIN_SCAN_MAX_DEPTH = 10


# ---------------------------------------------------------------------------
# Scanner registry (Open/Closed Principle)
# ---------------------------------------------------------------------------
#
# The registry is the single source of truth that maps each ItemType to
# a scanner function responsible for discovering items in a directory.
#
# EXTENSION POINT — Adding a new ItemType
# ========================================
# When a new ItemType is added to models.py:
#
#   1. Write a scanner function matching the
#      ``(dir_path: Path, *, gitignore: GitIgnoreMatcher | None) -> list[Item]``
#      signature.
#
#   2. Call ``_register_scanner(NewType, scanner_fn)`` in the
#      registration block below.
#
# No other code in this module needs to change —
# ``SourceScanner.scan_type`` looks up the dispatch table
# automatically with safe defaults for unregistered types.

_SCANNER_REGISTRY: dict[ItemType, Callable[..., list[Item]]] = {}


def _register_scanner(
    item_type: ItemType,
    scanner: Callable[..., list[Item]],
) -> None:
    """Register a scanner function for *item_type*.

    This is the **only** place to touch when adding a new ``ItemType``,
    satisfying the Open/Closed Principle: the module is open for extension
    (new types) but closed for modification (no existing code changes).
    """
    _SCANNER_REGISTRY[item_type] = scanner


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------


def _should_skip(name: str) -> bool:
    """Return ``True`` when *name* is hidden or an internal file/dir.

    Args:
        name: File or directory basename to check.

    Returns:
        ``True`` when *name* starts with ``.`` or is in the skip list.
    """
    return name.startswith(".") or name in _SKIP_NAMES


def _scandir_sorted(dir_path: Path) -> list[os.DirEntry[str]]:
    """Return a name-sorted list of ``DirEntry`` objects for *dir_path*.

    Uses :func:`os.scandir` so that subsequent ``is_file()`` / ``is_dir()``
    calls on each entry reuse the cached ``d_type`` from the kernel, avoiding
    extra ``stat()`` syscalls.  Returns an empty list on OS errors (e.g. the
    directory does not exist or is not readable).

    Args:
        dir_path: Directory to scan.

    Returns:
        Sorted list of :class:`os.DirEntry` objects, or an empty list on
        error.
    """
    try:
        return sorted(os.scandir(dir_path), key=lambda e: e.name)
    except OSError:
        return []


def _resolve_content_dir(source_dir: Path, item_type: ItemType) -> Path | None:
    """Return the base content directory for *item_type* (plural before singular).

    Checks ``source_dir / item_type.plural`` then ``source_dir / item_type.value``,
    returning the first one that exists on disk.

    Args:
        source_dir: Root source directory to search.
        item_type: The item category to locate.

    Returns:
        Path to the content directory, or ``None`` when neither candidate exists.
    """
    for candidate in (source_dir / item_type.plural, source_dir / item_type.value):
        if candidate.is_dir():
            return candidate
    return None


def _find_item_dirs(
    source_dir: Path,
    item_type: ItemType,
    scope: Scope | None = None,
) -> list[tuple[Path, Scope]]:
    """Locate content directories for *item_type* inside *source_dir*.

    Returns a list of ``(dir_path, scope)`` tuples representing directories
    to scan and the scope to assign to discovered items.

    Scope discovery
    ~~~~~~~~~~~~~~~
    When *scope* is ``None`` (default), **all** scopes are discovered:

    * The base content directory (e.g. ``agents/``) is returned as
      :attr:`Scope.GLOBAL` for backward compatibility — flat files and
      non-scope subdirectories inside it receive ``GLOBAL`` scope.
    * Each scope subdirectory that exists (``agents/global/``,
      ``agents/project/``, ``agents/local/``) is returned with its
      corresponding scope.

    When *scope* is specific, only directories matching that scope are
    returned.  For :attr:`Scope.GLOBAL`, this includes both the base
    content directory and the explicit ``global/`` subdirectory.

    Deduplication
    ~~~~~~~~~~~~~
    Items from the base content directory take priority over items from
    explicit scope subdirectories when both have the same ``(name, scope)``
    key.  Callers (see :meth:`SourceScanner.scan_type`) are responsible
    for enforcing this by processing results in order and skipping
    duplicates.

    Args:
        source_dir: Root source directory.
        item_type: The item category to locate.
        scope: Optional scope filter.  ``None`` discovers all scopes.

    Returns:
        List of ``(dir_path, scope)`` tuples ordered so that the base
        content directory comes first (for deduplication priority).

    """
    content_dir = _resolve_content_dir(source_dir, item_type)

    if content_dir is None:
        return []

    results: list[tuple[Path, Scope]] = []

    if scope is not None:
        # Specific scope requested — return only matching directories.
        if scope == Scope.GLOBAL:
            # GLOBAL: base dir (backward compat) + explicit global/ subdir.
            results.append((content_dir, Scope.GLOBAL))
            explicit_global = content_dir / Scope.GLOBAL.value
            if explicit_global.is_dir():
                results.append((explicit_global, Scope.GLOBAL))
        else:
            # PROJECT or LOCAL: only the scope subdirectory.
            scope_dir = content_dir / scope.value
            if scope_dir.is_dir():
                results.append((scope_dir, scope))
    else:
        # Discover all scopes — base dir first for dedup priority.
        results.append((content_dir, Scope.GLOBAL))
        for s in Scope:
            scope_dir = content_dir / s.value
            if scope_dir.is_dir():
                results.append((scope_dir, s))

    return results


def _is_in_scope_subdir(source_path: Path, content_dir: Path) -> bool:
    """Return ``True`` if *source_path* lives inside a scope subdirectory.

    Used to filter out items discovered in scope subdirectories when
    scanning the base content directory (to avoid double-counting).

    Args:
        source_path: Absolute path to an item's source.
        content_dir: The base content directory (e.g. ``agents/``).

    """
    try:
        rel = source_path.relative_to(content_dir)
    except ValueError:
        return False
    return bool(rel.parts) and rel.parts[0] in _SCOPE_DIR_NAMES


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
            items.append(item)
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
            items.append(item)
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

    Discovers both flat ``.md`` files and subdirectories containing
    ``<dirname>.md`` (e.g. ``agents/coder/coder.md``) by delegating
    to :func:`_scan_with_subdirs`.

    Flat files take priority: if both ``coder.md`` and ``coder/coder.md``
    exist, only the flat file is included.

    Args:
        dir_path: Directory containing agent definitions.
        gitignore: Optional gitignore matcher to exclude ignored paths.

    Returns:
        List of discovered agent :class:`Item` instances.

    """
    return _scan_with_subdirs(dir_path, ItemType.AGENT, gitignore=gitignore)


def _scan_skills_dir(
    dir_path: Path,
    gitignore: GitIgnoreMatcher | None = None,
) -> list[Item]:
    """Scan *dir_path* for skill subdirectories.

    **Item type**: :attr:`~agentfiles.models.ItemType.SKILL`

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
            items.append(item)
        except (AgentfilesError, OSError) as exc:
            logger.warning("Skipping skill directory %s: %s", child.name, exc, exc_info=True)

    return items


def _scan_commands_dir(
    dir_path: Path,
    gitignore: GitIgnoreMatcher | None = None,
) -> list[Item]:
    """Scan *dir_path* for command definitions.

    **Item type**: :attr:`~agentfiles.models.ItemType.COMMAND`

    Discovers both flat ``.md`` files and subdirectories containing
    ``<dirname>.md`` (e.g. ``commands/deploy/deploy.md``) by delegating
    to :func:`_scan_with_subdirs`.

    Flat files take priority: if both ``deploy.md`` and ``deploy/deploy.md``
    exist, only the flat file is included.

    Args:
        dir_path: Directory containing command definitions.
        gitignore: Optional gitignore matcher to exclude ignored paths.

    Returns:
        List of discovered command :class:`Item` instances.

    """
    return _scan_with_subdirs(dir_path, ItemType.COMMAND, gitignore=gitignore)


def _has_plugin_file(directory: Path, *, _depth: int = 0) -> bool:
    """Return ``True`` if *directory* recursively contains a plugin file.

    Called by :func:`_scan_plugins_dir` to decide whether a subdirectory
    qualifies as a plugin item.  A "plugin file" is any non-hidden file
    whose extension is in :data:`_PLUGIN_EXTENSIONS` (``.ts``, ``.yaml``,
    ``.py``, ``.yml``, ``.js``).

    Uses :func:`os.scandir` recursively so that ``DirEntry.is_file()``
    reuses cached ``d_type``, avoiding ``stat()`` syscalls on every entry.
    The file extension (cheap string comparison) is checked **before**
    ``is_file()`` so that non-plugin entries skip the type check entirely.

    A depth limit prevents runaway recursion caused by pathological
    nesting or filesystem oddities (e.g. bind mounts).

    Args:
        directory: Directory to scan recursively.
        _depth: Current recursion depth (internal; callers omit this).

    Returns:
        ``True`` when at least one plugin file is found.

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


def _scan_plugins_dir(
    dir_path: Path,
    gitignore: GitIgnoreMatcher | None = None,
) -> list[Item]:
    """Scan *dir_path* for plugin files and plugin directories.

    **Item type**: :attr:`~agentfiles.models.ItemType.PLUGIN`

    Supports two organization styles:

    1. **OpenCode subdirectory** — an ``opencode/`` subdirectory is scanned
       for plugin files and directories, identical to top-level scanning.

    2. **Top-level files and directories** — single files with recognised
       extensions or directories containing plugin files are parsed.

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

        # OpenCode subdirectory (e.g. plugins/opencode/)
        if entry.is_dir() and entry.name == TARGET_PLATFORM:
            for sub_entry in _scandir_sorted(child):
                if _should_skip(sub_entry.name):
                    continue
                sub_child = Path(sub_entry.path)
                if gitignore and gitignore.is_ignored(sub_child):
                    continue

                if sub_entry.is_file():
                    if sub_child.suffix not in _PLUGIN_EXTENSIONS:
                        continue
                    try:
                        item = item_from_file(sub_child, ItemType.PLUGIN)
                        items.append(item)
                    except (AgentfilesError, OSError) as exc:
                        logger.warning(
                            "Skipping plugin file %s: %s", sub_child.name, exc, exc_info=True
                        )

                elif sub_entry.is_dir():
                    if not _has_plugin_file(sub_child):
                        logger.debug("Skipping plugin dir %s — no plugin files", sub_child.name)
                        continue
                    try:
                        item = item_from_directory(sub_child, ItemType.PLUGIN)
                        items.append(item)
                    except (AgentfilesError, OSError) as exc:
                        logger.warning(
                            "Skipping plugin directory %s: %s",
                            sub_child.name,
                            exc,
                            exc_info=True,
                        )
            continue

        # Top-level flat plugin file
        if entry.is_file():
            if child.suffix not in _PLUGIN_EXTENSIONS:
                continue
            try:
                item = item_from_file(child, ItemType.PLUGIN)
                items.append(item)
            except (AgentfilesError, OSError) as exc:
                logger.warning("Skipping plugin file %s: %s", child.name, exc, exc_info=True)

        # Top-level plugin directory
        elif entry.is_dir():
            if not _has_plugin_file(child):
                logger.debug("Skipping plugin dir %s — no plugin files", child.name)
                continue
            try:
                item = item_from_directory(child, ItemType.PLUGIN)
                items.append(item)
            except (AgentfilesError, OSError) as exc:
                logger.warning("Skipping plugin directory %s: %s", child.name, exc, exc_info=True)

    return items


def _scan_workflows_dir(
    dir_path: Path,
    gitignore: GitIgnoreMatcher | None = None,
) -> list[Item]:
    """Scan *dir_path* for workflow subdirectories.

    **Item type**: :attr:`~agentfiles.models.ItemType.WORKFLOW`

    Workflows are **directory-only**: each subdirectory must contain a
    markdown file (``<dirname>.md`` or any ``.md`` file).  Flat ``.md``
    files at the top level of the workflows directory are ignored.

    Args:
        dir_path: Directory containing workflow definitions.
        gitignore: Optional gitignore matcher to exclude ignored paths.

    Returns:
        List of discovered workflow :class:`Item` instances.

    """
    items: list[Item] = []

    for entry in _scandir_sorted(dir_path):
        if _should_skip(entry.name) or not entry.is_dir():
            continue
        child = Path(entry.path)
        if gitignore and gitignore.is_ignored(child):
            continue
        try:
            item = item_from_directory(child, ItemType.WORKFLOW)
            items.append(item)
        except (AgentfilesError, OSError) as exc:
            logger.warning("Skipping workflow directory %s: %s", child.name, exc, exc_info=True)

    return items


def _scan_config_dirs(
    dir_path: Path,
    gitignore: GitIgnoreMatcher | None = None,
) -> list[Item]:
    """Scan *dir_path* for config files (``.json``).

    Config items are flat files (e.g. ``opencode.json``, ``settings.json``)
    that live directly in the platform config root.

    Args:
        dir_path: Directory containing config definitions.
        gitignore: Optional gitignore matcher to exclude ignored paths.

    Returns:
        List of discovered config :class:`Item` instances.
    """
    items: list[Item] = []

    for entry in _scandir_sorted(dir_path):
        if _should_skip(entry.name) or not entry.is_file():
            continue
        child = Path(entry.path)
        if gitignore and gitignore.is_ignored(child):
            continue
        if child.suffix != ".json":
            continue
        try:
            item = item_from_file(child, ItemType.CONFIG)
            items.append(item)
        except (AgentfilesError, OSError) as exc:
            logger.warning("Skipping config file %s: %s", child.name, exc, exc_info=True)

    return items


# Populate the registry once all scanner functions are defined.
#
# Summary of registered scanners:
#
#   ItemType   | Scanner function
#   -----------|-----------------------
#   AGENT      | _scan_agents_dir
#   SKILL      | _scan_skills_dir
#   COMMAND    | _scan_commands_dir
#   PLUGIN     | _scan_plugins_dir
#   CONFIG     | _scan_config_dirs
#   WORKFLOW   | _scan_workflows_dir
#
# Each call is atomic: adding a new ItemType only needs one more line here.
_register_scanner(
    ItemType.AGENT,
    _scan_agents_dir,
)
_register_scanner(
    ItemType.SKILL,
    _scan_skills_dir,
)
_register_scanner(
    ItemType.COMMAND,
    _scan_commands_dir,
)
_register_scanner(
    ItemType.PLUGIN,
    _scan_plugins_dir,
)
_register_scanner(
    ItemType.CONFIG,
    _scan_config_dirs,
)
_register_scanner(
    ItemType.WORKFLOW,
    _scan_workflows_dir,
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
    5. Results are sorted by ``(item_type, name)``.

    GitIgnore integration
    ~~~~~~~~~~~~~~~~~~~~~
    On construction, a :class:`GitIgnoreMatcher` is built
    from ``.gitignore`` files in *source_dir*.  Each scanner function
    receives this matcher and skips entries that match any gitignore rule.

    Args:
        source_dir: Root directory to scan (resolved to an absolute path).
        scope: Optional scope filter.  When ``None``, all scopes are
            discovered.  When provided, only items in the specified scope
            are returned.

    Example::

        scanner = SourceScanner(Path("~/my-tools"))
        items = scanner.scan()

        # Filter to a single scope
        scanner = SourceScanner(Path("~/my-tools"), scope=Scope.PROJECT)
        items = scanner.scan()

    """

    def __init__(
        self,
        source_dir: Path,
        scope: Scope | None = None,
    ) -> None:
        """Initialise the scanner with a source directory and optional scope filter."""
        self._source_dir = source_dir.resolve()
        self._scope = scope
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

        counts = Counter(item.item_type for item in all_items)
        parts = [f"{counts[t]} {t.plural}" for t in ItemType if counts[t] > 0]
        logger.info("Found %s", ", ".join(parts))

        return all_items

    def scan_type(self, item_type: ItemType) -> list[Item]:
        """Scan for a single item type.

        Args:
            item_type: The category to scan.

        Returns:
            Validated items for that type, filtered by ``self._scope``.

        """
        scope_dirs = _find_item_dirs(self._source_dir, item_type, self._scope)
        if not scope_dirs:
            logger.debug(
                "No %s directory found in %s",
                item_type.plural,
                self._source_dir,
            )
            return []

        all_items: list[Item] = []
        # Track items found in the base content directory so that items
        # in explicit scope subdirs (e.g. agents/global/) can be
        # deduplicated against them.  The key is ``(name, scope)``.
        base_dir_keys: set[tuple[str, Scope]] = set()

        base_dir = _resolve_content_dir(self._source_dir, item_type)

        for dir_path, discovered_scope in scope_dirs:
            items = self._dispatch_scan(item_type, dir_path)

            # When scanning the base content directory, filter out items
            # whose source_path is inside a scope subdirectory to avoid
            # double-counting (those will be found when the scope subdir
            # is scanned as its own entry).
            is_base = base_dir is not None and dir_path == base_dir
            if is_base:
                # Narrow type for mypy: is_base guarantees base_dir is not None.
                assert base_dir is not None
                items = [
                    item for item in items if not _is_in_scope_subdir(item.source_path, base_dir)
                ]

            # Apply scope to each item.  Deduplication only happens across
            # directories: items from the base content dir always win over
            # items with the same (name, scope) from an explicit scope subdir.
            for item in items:
                scoped_item = replace(item, scope=discovered_scope)
                key = (item.name, discovered_scope)

                if is_base:
                    base_dir_keys.add(key)
                    all_items.append(scoped_item)
                else:
                    if key in base_dir_keys:
                        logger.debug(
                            "Skipping duplicate %s '%s' in scope %s "
                            "(already found in base directory)",
                            item_type.value,
                            item.name,
                            discovered_scope.value,
                        )
                        continue
                    all_items.append(scoped_item)

        return all_items

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

        Args:
            item_type: Category of items to scan for.
            dir_path: Directory to scan.

        Returns:
            List of discovered items, or an empty list on failure.

        """
        scanner = _SCANNER_REGISTRY.get(item_type)
        if scanner is None:
            logger.warning("No scanner registered for %s — skipping", item_type.value)
            return []
        return scanner(dir_path, gitignore=self._gitignore)
