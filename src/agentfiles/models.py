"""Data models and helper utilities for the agentfiles CLI tool.

agentfiles manages AI tool configurations (agents, skills, commands, plugins)
by parsing YAML frontmatter and tracking sync operations for the OpenCode
platform.

Models are built with ``dataclasses`` from the standard library.  The only
external dependency is ``pyyaml`` for YAML frontmatter parsing.

Data model hierarchy
--------------------
The core flow turns source files on disk into syncable items and then
into installation plans::

    SourceInfo          Resolved metadata about a sync source directory.
        │
        ▼
    Item                A single syncable unit (agent, skill, command, plugin).
    ├── ItemMeta        Frontmatter metadata (name, description, version, …).
    ├── ItemType        Category enum (AGENT, SKILL, COMMAND, PLUGIN).
        │
        ▼
    SyncPlan            Planned action (install / update / skip) for one item.
        │
        ▼
    SyncResult          Outcome of executing a plan.

State tracking uses a two-level structure persisted as YAML::

    SyncState           Per-repository state file (``.agentfiles.state.yaml``).
    └── ItemState       Per-item timestamps.

Diffing (comparing source to target) produces::

    DiffEntry           Comparison result (NEW / UPDATED / DELETED / …).

Token estimation (for context-window budgeting) produces::

    TokenEstimate       Per-item breakdown of content vs. overhead tokens.

Utility layers
--------------
* **Frontmatter parsing** — :func:`parse_frontmatter` and related helpers
  (re-exported from :mod:`agentfiles.frontmatter`) extract YAML blocks from
  markdown files with automatic retry for bare-colon values.
* **Token estimation** — :func:`token_estimate` reads item files and produces
  a :class:`TokenEstimate` using a 4-chars-per-token heuristic.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Final

__all__ = [
    # Re-exported from agentfiles.frontmatter
    "SKILL_MAIN_FILE",
    "parse_frontmatter",
    # Exceptions
    "ConfigError",
    "SourceError",
    "AgentfilesError",
    "TargetError",
    # Enumerations
    "DiffStatus",
    "ItemType",
    "Scope",
    "SourceType",
    "SyncAction",
    "SyncDirection",
    # Platform constants
    "TARGET_PLATFORM",
    "TARGET_PLATFORM_DISPLAY",
    # Data models
    "DiffEntry",
    "Item",
    "ItemMeta",
    "ItemState",
    "SourceInfo",
    "SyncPlan",
    "SyncResult",
    "SyncState",
    "TargetPaths",
    "TokenEstimate",
    # Helper functions
    "item_from_directory",
    "item_from_file",
    "resolve_platform",
    "resolve_source_name_for_config",
    "resolve_target_name",
]

# ---------------------------------------------------------------------------
# Shared constants (used across modules and within dataclass defaults)
# ---------------------------------------------------------------------------

_DEFAULT_VERSION = "1.0.0"


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class AgentfilesError(Exception):
    """Base exception for all agentfiles operations."""


class ConfigError(AgentfilesError):
    """Raised when a configuration file cannot be found, read, or parsed."""


class SourceError(AgentfilesError):
    """Raised when a source path cannot be resolved or read."""


class TargetError(AgentfilesError):
    """Raised when a target platform directory cannot be found or accessed."""


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class SourceType(Enum):
    """Origin type for a configuration source.

    Members:
        LOCAL_DIR: A plain directory on the local filesystem.
        GIT_URL: A remote git repository referenced by HTTPS/SSH URL.
        GIT_DIR: A local git repository (already cloned on disk).
    """

    LOCAL_DIR = "local_dir"
    GIT_URL = "git_url"
    GIT_DIR = "git_dir"


class ItemType(Enum):
    """Categories of content that agentfiles manages."""

    AGENT = "agent"
    SKILL = "skill"
    COMMAND = "command"
    PLUGIN = "plugin"
    CONFIG = "config"
    WORKFLOW = "workflow"

    @property
    def plural(self) -> str:
        """Plural form used as directory name (e.g. ``"agents"``)."""
        _plurals: dict[ItemType, str] = {
            ItemType.AGENT: "agents",
            ItemType.SKILL: "skills",
            ItemType.COMMAND: "commands",
            ItemType.PLUGIN: "plugins",
            ItemType.CONFIG: "configs",
            ItemType.WORKFLOW: "workflows",
        }
        return _plurals[self]

    @property
    def is_file_based(self) -> bool:
        """``True`` for item types stored as flat files (agents, commands, plugins, configs).

        File-based items retain their source filename (including extension)
        when installed.  Directory-based items (skills, workflows) are installed
        by name only.
        """
        return self in (ItemType.AGENT, ItemType.COMMAND, ItemType.PLUGIN, ItemType.CONFIG)


TARGET_PLATFORM: Final = "opencode"
"""Canonical platform identifier — the only supported target."""

TARGET_PLATFORM_DISPLAY: Final = "OpenCode"
"""Human-readable platform name for UI output."""


# ---------------------------------------------------------------------------
# Platform name resolution
# ---------------------------------------------------------------------------

_OPENCODE_ALIASES: Final[frozenset[str]] = frozenset(
    {"opencode", "oc", "open-code", "open_code"},
)


def resolve_platform(name: str) -> str:
    """Normalize a platform name or alias to its canonical value.

    Accepts ``"opencode"`` and common aliases (``"oc"``, ``"open-code"``,
    ``"open_code"``), returning the canonical ``TARGET_PLATFORM`` string.

    Args:
        name: Platform name or alias (case-insensitive).

    Returns:
        Canonical platform value string (always :data:`TARGET_PLATFORM`).

    Raises:
        ValueError: When *name* is not a recognized platform or alias.

    """
    n = name.lower().strip()
    if n in _OPENCODE_ALIASES:
        return TARGET_PLATFORM
    raise ValueError(f"Unknown platform: {name!r}. Only 'opencode' is supported.")


class SyncAction(Enum):
    """Action to perform during a sync operation."""

    INSTALL = "install"
    UPDATE = "update"
    UNINSTALL = "uninstall"
    SKIP = "skip"


class DiffStatus(Enum):
    """Comparison result between source and target items.

    Members:
        NEW: Item exists in source but not at the target.
        UPDATED: Item exists at both; content differs.
        DELETED: Item exists at target but no longer in source.
        UNCHANGED: Content matches — no action needed.
        CONFLICT: Both sides changed independently since the last sync.
    """

    NEW = "new"
    UPDATED = "updated"
    DELETED = "deleted"
    UNCHANGED = "unchanged"
    CONFLICT = "conflict"


class SyncDirection(Enum):
    """Direction of a sync operation for an item."""

    PULL = "pull"
    PUSH = "push"
    CONFLICT = "conflict"
    SKIP = "skip"


class Scope(Enum):
    """Installation scope for items.

    Determines where items are installed on the target platform:

    - GLOBAL: User-level configs shared across all projects
      (e.g. ~/.config/opencode/)
    - PROJECT: Project-specific configs committed to VCS
      (e.g. .opencode/ in project root)
    - LOCAL: Personal project configs, git-ignored
      (e.g. .opencode/ with .gitignore entries)

    In the source repository, scope is determined by directory structure:

    - agents/ or agents/global/ → GLOBAL (default)
    - agents/project/ → PROJECT
    - agents/local/ → LOCAL
    """

    GLOBAL = "global"
    PROJECT = "project"
    LOCAL = "local"

    @property
    def display_name(self) -> str:
        _names: dict[Scope, str] = {
            Scope.GLOBAL: "Global",
            Scope.PROJECT: "Project",
            Scope.LOCAL: "Local",
        }
        return _names[self]

    @property
    def marker(self) -> str:
        """Short marker for display in item lists."""
        _markers: dict[Scope, str] = {
            Scope.GLOBAL: "●",
            Scope.PROJECT: "◆",
            Scope.LOCAL: "○",
        }
        return _markers[self]


# ---------------------------------------------------------------------------
# Shared file filter (used across models and tokens)
# ---------------------------------------------------------------------------

_SKIP_NAMES: Final[frozenset[str]] = frozenset({"__pycache__", "__init__.py"})


def _is_item_file(rel_path: Path) -> bool:
    """Whether a relative path should be included in item content."""
    return not any(part.startswith(".") or part in _SKIP_NAMES for part in rel_path.parts)


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SourceInfo:
    """Resolved metadata about a sync source.

    Attributes:
        source_type: Kind of source (local dir, git URL, local git repo).
        path: Absolute resolved filesystem path.
        original_input: The raw string the user provided.
        is_git_repo: Whether the resolved path is a git repository.

    """

    source_type: SourceType
    path: Path
    original_input: str
    is_git_repo: bool


@dataclass(frozen=True)
class ItemMeta:
    """Metadata parsed from YAML frontmatter of a ``.md`` file.

    Attributes:
        name: Human-readable identifier (e.g. ``"python-reviewer"``).
        description: Short summary of what the item does.
        version: Semantic version string.
        priority: Priority level (e.g. ``"critical"``, ``"normal"``).
        tools: Mapping of tool names to enabled/disabled flags.
        extra: Catch-all for any unrecognised frontmatter keys.

    """

    name: str
    description: str = ""
    version: str = _DEFAULT_VERSION
    priority: str | None = None
    tools: dict[str, bool] = field(default_factory=dict)
    extra: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Eager import from agentfiles.frontmatter.
# This MUST come after ItemMeta is defined because frontmatter.py imports
# ItemMeta from this module.  The noqa: E402 suppresses the "module level
# import not at top of file" warning — this placement is intentional.
# ---------------------------------------------------------------------------
from agentfiles.frontmatter import (  # noqa: E402
    SKILL_MAIN_FILE,
    _meta_from_frontmatter,
    parse_frontmatter,
)


@dataclass(frozen=True)
class Item:
    """A single syncable item (agent / skill / command / plugin).

    Attributes:
        item_type: Category of the item.
        name: Unique identifier parsed from frontmatter or directory name.
        source_path: Absolute path to the item in the source repository.
        meta: Parsed frontmatter metadata, if available.
        version: Semantic version (defaults to ``"1.0.0"``).
        files: All file paths (relative to *source_path*) in the item.

    """

    item_type: ItemType
    name: str
    source_path: Path
    meta: ItemMeta | None = None
    version: str = _DEFAULT_VERSION
    files: tuple[str, ...] = ()
    scope: Scope = Scope.GLOBAL

    # -- derived keys / sorting ---------------------------------------------

    @property
    def item_key(self) -> str:
        """Canonical key in ``"{type}/{name}"`` format.

        Used as a stable identifier for state tracking, diff indexing,
        and display.  Examples: ``"agent/coder"``, ``"skill/python-reviewer"``.
        """
        return f"{self.item_type.value}/{self.name}"

    @property
    def sort_key(self) -> tuple[str, str]:
        """Tuple suitable for sorting items by type then name.

        Usage::

            items.sort(key=lambda i: i.sort_key)
        """
        return (self.item_type.value, self.name)


@dataclass(frozen=True)
class TargetPaths:
    """Discovered paths for a target platform.

    Stores the resolved filesystem layout for a single platform target.

    Attributes:
        platform: Which platform this paths object refers to.
        config_dir: Root configuration directory for the platform.
        subdirs: Mapping of logical directory names to their resolved paths.
        config_file: Path to the platform's config file, if found.

    """

    config_dir: Path
    platform: str = TARGET_PLATFORM
    subdirs: dict[str, Path] = field(default_factory=dict)
    config_file: Path | None = None

    @property
    def is_valid(self) -> bool:
        """``True`` when :attr:`config_dir` exists on disk."""
        return self.config_dir.is_dir()

    def subdir_for(self, item_type: ItemType) -> Path:
        """Return the target subdirectory for a given item type.

        Looks up the plural name (e.g. ``"agents"``) in :attr:`subdirs`,
        falling back to a conventional path under :attr:`config_dir`.

        Returns:
            Resolved path for the item type's subdirectory.

        """
        key = item_type.plural
        if key in self.subdirs:
            return self.subdirs[key]
        return self.config_dir / key


@dataclass(frozen=True)
class SyncPlan:
    """Planned sync action for a single item.

    Attributes:
        item: The item to sync.
        action: What operation to perform.
        target_dir: Destination directory on the target platform.
        reason: Human-readable explanation for the chosen action.

    """

    item: Item
    action: SyncAction
    target_dir: Path
    reason: str


@dataclass
class SyncResult:
    """Outcome of executing a single sync plan.

    Attributes:
        plan: The plan that was executed.
        is_success: Whether the sync completed without errors.
        message: Human-readable status or error message.
        files_copied: Number of files successfully copied.
        files_skipped: Number of files that were already up-to-date.

    """

    plan: SyncPlan
    is_success: bool
    message: str = ""
    files_copied: int = 0
    files_skipped: int = 0
    push_status: str = ""
    push_detail: str = ""


@dataclass(frozen=True)
class DiffEntry:
    """Comparison result between a source item and its target.

    Attributes:
        item: The source item being compared.
        status: Result of the comparison.
        details: Human-readable description of the difference.

    """

    item: Item
    status: DiffStatus
    details: str = ""


# ---------------------------------------------------------------------------
# Token estimation
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TokenEstimate:
    """Token count estimate for a single syncable item.

    Provides a per-item breakdown of estimated context window consumption
    so callers can decide whether to read an item's content or display
    only metadata.

    Attributes:
        name: Human-readable item name.
        item_type: Category of the item (agent, skill, etc.).
        files: File paths relative to the item's source directory.
        source_size_bytes: Total file size in bytes across all source files.
        content_tokens: Estimated tokens from reading file contents.
        overhead_tokens: Estimated tokens for YAML frontmatter metadata
            (name, description, version, etc.).
        total_tokens: Sum of content and overhead tokens.

    """

    name: str
    item_type: ItemType
    files: tuple[str, ...]
    source_size_bytes: int
    content_tokens: int
    overhead_tokens: int
    total_tokens: int


# ---------------------------------------------------------------------------
# Sync State
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ItemState:
    """Sync state for a single item.

    Attributes:
        synced_at: ISO 8601 timestamp of the last successful sync.

    """

    synced_at: str = ""


# NOTE: SyncState intentionally remains mutable (no ``frozen=True``) because
# engine.py and cli.py reassign ``state.last_sync`` after each sync operation,
# and mutate ``state.items`` in-place.  Freezing would require all
# callers to switch to ``dataclasses.replace()`` — a change that is out of
# scope for this module alone.
@dataclass
class SyncState:
    """Complete sync state for the source repository.

    Stored as ``.agentfiles.state.yaml`` in the repository root.

    Attributes:
        version: State file format version.
        last_sync: ISO 8601 timestamp of the last full sync.
        items: Mapping of item key (e.g. ``"agent/coder"``) to ItemState.

    """

    version: str = "1.0"
    last_sync: str = ""
    items: dict[str, ItemState] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def resolve_source_name_for_config(target_filename: str) -> str:
    """Return the source filename for a config target filename.

    With only OpenCode supported, config filenames are not renamed
    during installation, so this returns *target_filename* unchanged.

    Args:
        target_filename: The filename as it appears on the target platform.

    Returns:
        The corresponding source repository filename.

    """
    return target_filename


def resolve_target_name(item: Item) -> str:
    """Return the on-disk destination name for *item*.

    File-based items (agents, commands, configs) are installed as flat files
    whose name includes the source extension (e.g. ``"api-architect.md"``).
    Directory-based items (skills, workflows) use their directory name.

    This function must be used everywhere the code resolves the expected
    name of an item at a target location — both during sync (install) and
    during diff (compare).

    Args:
        item: The source item.

    Returns:
        The name that the item should have on disk at the target.

    """
    if item.item_type.is_file_based:
        return item.source_path.name
    return item.name


def item_from_directory(
    path: Path,
    item_type: ItemType,
) -> Item:
    """Create an :class:`Item` by scanning a directory on disk.

    The directory is scanned recursively.  The primary markdown file is
    located via :func:`_find_main_md`, its frontmatter is parsed for
    metadata, and the full file list is collected.

    Args:
        path: Filesystem path to the item directory.
        item_type: The :class:`ItemType` category.

    Returns:
        A fully-populated :class:`Item` instance.

    Raises:
        SourceError: When the path is invalid, not a directory, the
            main markdown file is missing, or the directory is empty.

    """
    resolved = path.resolve()

    if not resolved.exists():
        raise SourceError(
            f"cannot create item from directory: path does not exist: '{path}'. "
            f"Ensure the directory is present before scanning"
        )

    if not resolved.is_dir():
        raise SourceError(
            f"expected a directory for {item_type.value}, got a file: '{path}'. "
            f"Provide a directory path instead"
        )

    main_md = _find_main_md(resolved, item_type)
    if main_md is None and item_type != ItemType.PLUGIN:
        expected_file = (
            f"'{SKILL_MAIN_FILE}'"
            if item_type == ItemType.SKILL
            else f"'{resolved.name}.md' (or any .md file)"
        )
        raise SourceError(
            f"cannot find main markdown file for {item_type.value} "
            f"in '{path}'. Expected {expected_file}."
        )

    meta, resolved_name = _parse_item_meta(main_md, resolved)
    name = resolved_name

    files = _collect_relative_files(resolved)
    if not files:
        raise SourceError(
            f"directory is empty: '{path}'. "
            f"Add at least one non-hidden file (e.g. a .md or .ts file) "
            f"to make this a valid {item_type.value} item"
        )

    return _build_item(item_type, resolved, meta, name, tuple(files))


def item_from_file(
    file_path: Path,
    item_type: ItemType,
) -> Item:
    """Create an Item from a single file (agents, commands, plugins).

    Parses YAML frontmatter to extract *name*, *description*, *version*,
    and other metadata.  Falls back to the stem of *file_path* when no
    ``name:`` field is present.

    Args:
        file_path: Path to the ``.md`` or ``.ts`` file.
        item_type: Category of the item being created.

    Returns:
        A fully populated :class:`Item` instance with meta.

    Raises:
        SourceError: When the file cannot be read or parsed.

    """
    resolved = file_path.resolve()

    if not resolved.is_file():
        raise SourceError(
            f"expected a regular file for {item_type.value}, "
            f"but '{file_path}' is not a file. "
            f"Provide a path to an existing .md or .ts file"
        )

    try:
        text = resolved.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise SourceError(
            f"cannot read file '{file_path}': {exc}. "
            f"Check file permissions, encoding (expected UTF-8), or whether it is corrupted"
        ) from exc

    parsed = parse_frontmatter(text)
    meta = _meta_from_frontmatter(parsed) if parsed else None
    name = meta.name if meta and meta.name else resolved.stem

    return _build_item(item_type, resolved, meta, name, (resolved.name,))


# ---------------------------------------------------------------------------
# Lazy re-exports — backward-compatible symbols from agentfiles.frontmatter
# and agentfiles.tokens
# ---------------------------------------------------------------------------
# Imports are resolved lazily to break the circular dependency chain:
# models.py ↔ frontmatter.py.  The public API is preserved so that
# existing imports continue to work.
# ---------------------------------------------------------------------------

_FRONTMATTER_NAMES = frozenset(
    {
        "SKILL_MAIN_FILE",
        "_meta_from_frontmatter",
        "parse_frontmatter",
    }
)

_TOKEN_NAMES = frozenset(
    {
        "CHARS_PER_TOKEN",
        "estimate_tokens_from_content",
        "estimate_tokens_from_files",
        "token_estimate",
        "_resolve_item_files",
        "_compute_total_size",
        "_estimate_overhead_tokens",
    }
)


def __getattr__(name: str) -> object:
    """Lazy re-export of symbols from frontmatter and tokens modules."""
    if name in _TOKEN_NAMES:
        from agentfiles import tokens as _tokens

        value = getattr(_tokens, name)
        # Cache in module globals so future access bypasses __getattr__.
        globals()[name] = value
        return value
    if name in _FRONTMATTER_NAMES:
        from agentfiles import frontmatter as _fm

        value = getattr(_fm, name)
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


# ---------------------------------------------------------------------------
# Internal helpers (module-private)
# ---------------------------------------------------------------------------


def _collect_relative_files(directory: Path) -> list[str]:
    """Return all file paths under *directory*, relative to it.

    Recursively walks *directory* using ``rglob("*")`` and returns
    file paths as strings relative to *directory*.

    Filtering rules (applied to each path component):

    * Names starting with ``.`` are excluded (hidden files/dirs like
      ``.git``, ``.DS_Store``).
    * ``__pycache__`` directories are excluded.

    The result is sorted alphabetically for deterministic ordering.

    Args:
        directory: Absolute path to scan.

    Returns:
        Sorted list of relative file paths (e.g. ``["SKILL.md", "refs/guide.md"]``).
    """
    files: list[str] = []
    for child in sorted(directory.rglob("*")):
        if not child.is_file():
            continue
        rel = child.relative_to(directory)
        if not _is_item_file(rel):
            continue
        files.append(str(rel))
    return files


def _find_main_md(path: Path, item_type: ItemType) -> Path | None:
    """Locate the primary markdown file for a given item type.

    Resolution order:

    * **Skills** — ``SKILL.md`` inside the directory.
    * **Agents / Commands** — ``<dirname>.md`` inside the directory.
    * **Fallback** — first ``.md`` file found (sorted alphabetically).
    * **Plugins** — returns ``None`` (no canonical markdown file).

    Args:
        path: Absolute path to the item directory.
        item_type: The :class:`ItemType` being scanned.

    Returns:
        Path to the main ``.md`` file, or ``None`` if not found.

    """
    if item_type == ItemType.SKILL:
        candidate = path / SKILL_MAIN_FILE
        if candidate.is_file():
            return candidate

    if item_type in (ItemType.AGENT, ItemType.COMMAND):
        candidate = path / f"{path.name}.md"
        if candidate.is_file():
            return candidate

    # Fallback: first .md file in the directory (non-recursive).
    for child in sorted(path.iterdir()):
        if child.is_file() and child.suffix == ".md":
            return child

    return None


def _build_item(
    item_type: ItemType,
    path: Path,
    meta: ItemMeta | None,
    name: str,
    files: tuple[str, ...],
) -> Item:
    """Construct an :class:`Item` with computed version.

    Centralises the shared logic used by both :func:`item_from_directory`
    and :func:`item_from_file` for building an :class:`Item` instance.

    Args:
        item_type: Category of the item.
        path: Absolute resolved source path.
        meta: Parsed frontmatter metadata (may be ``None``).
        name: Unique identifier for the item.
        files: Relative file paths belonging to the item.

    Returns:
        A fully-populated :class:`Item` instance with meta.

    """
    version = meta.version if meta else _DEFAULT_VERSION
    return Item(
        item_type=item_type,
        name=name,
        source_path=path,
        meta=meta,
        version=version,
        files=files,
    )


def _parse_item_meta(
    main_md: Path | None,
    fallback_dir: Path,
) -> tuple[ItemMeta | None, str]:
    """Parse frontmatter from *main_md* and return ``(meta, name)``.

    Reads the markdown file, extracts YAML frontmatter, and converts it
    to an :class:`ItemMeta`.  The *name* is taken from the frontmatter
    ``name:`` field; if absent or empty, it falls back to the directory
    name (``fallback_dir.name``).

    If *main_md* is ``None`` or parsing yields no data, *meta* will be
    ``None`` and *name* will default to the directory's stem.

    Args:
        main_md: Path to the primary markdown file, or ``None``.
        fallback_dir: Directory used to derive a default name when
            frontmatter is missing or has no ``name`` key.

    Returns:
        Tuple of ``(ItemMeta | None, str)`` — the parsed metadata and
        the resolved item name.

    Raises:
        SourceError: When *main_md* cannot be read.
    """
    if main_md is None:
        return None, fallback_dir.name

    try:
        content = main_md.read_text(encoding="utf-8")
    except OSError as exc:
        raise SourceError(
            f"cannot read markdown file '{main_md}' for item "
            f"'{fallback_dir.name}': {exc}. "
            f"Check file permissions or whether the path is accessible"
        ) from exc

    fm = parse_frontmatter(content)
    if not fm:
        return None, fallback_dir.name

    meta = _meta_from_frontmatter(fm)
    name = meta.name or fallback_dir.name
    return meta, name
