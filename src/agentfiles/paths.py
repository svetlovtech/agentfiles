"""Centralised path construction helpers for item resolution.

Provides a single source of truth for filesystem path patterns used
across the codebase.  All functions are pure (no side effects) and
return :class:`~pathlib.Path` objects, making them easy to test and
compose.

Path categories:
    * **Destination paths** — where items land on the target platform
      (see :func:`get_item_dest_path`, :func:`get_installed_item_path`).
    * **Push paths** — where items land in the source repository during
      a push operation (see :func:`get_push_dest_path`).
    * **Content reading** — reading item content from disk with
      optimised filesystem calls (see :func:`read_item_content`).
    * **Key generation** — stable string keys for sync state and diffs
      are available via the ``Item.item_key`` property on
      :class:`~agentfiles.models.Item`.
"""

from __future__ import annotations

import logging
import os
import stat as stat_mod
from pathlib import Path

from agentfiles.models import (
    SKILL_MAIN_FILE,
    Item,
    ItemType,
    resolve_target_name,
)

logger = logging.getLogger(__name__)


def get_item_dest_path(target_dir: Path, item: Item) -> Path:
    """Return the on-disk destination path for *item* within *target_dir*.

    Delegates to :func:`agentfiles.models.resolve_target_name` to determine
    the correct filename (which handles platform-specific naming rules).

    Args:
        target_dir: Platform configuration directory (e.g.
            ``~/.config/opencode/agents``).
        item: The :class:`Item` whose destination path is needed.

    Returns:
        Absolute ``Path`` combining *target_dir* with the item's
        resolved target name.

    """
    return target_dir / resolve_target_name(item)


def get_installed_item_path(
    target_dir: Path,
    item_type: ItemType,
    name: str,
) -> Path:
    """Return the filesystem path for an installed item by type and name.

    Config items use the filename as-is (e.g. ``opencode.json``).
    File-based items (agents, commands) get a ``.md`` extension appended.
    Directory-based items (skills) and plugin directories use the name as-is.

    Args:
        target_dir: Platform configuration directory.
        item_type: The :class:`ItemType` that determines whether a
            ``.md`` extension is appended.
        name: Item name without extension (or full filename for configs).

    Returns:
        Path under *target_dir* for the installed item.

    """
    if item_type == ItemType.CONFIG:
        # Config items are .json files; ensure the extension is present.
        return target_dir / f"{name}.json"
    if item_type in (ItemType.AGENT, ItemType.COMMAND):
        return target_dir / f"{name}.md"
    return target_dir / name


def get_push_dest_path(source_dir: Path, item: Item) -> Path:
    """Compute the destination path in the source repo for a push.

    Markdown file items (agents, commands) land at
    ``source_dir/<plural>/<name>/<filename>.md``.
    File-based items (plugins, configs) land at
    ``source_dir/<plural>/<filename>`` preserving the original extension.
    Directory-based items (skills) land at ``source_dir/<plural>/<name>/``.

    Args:
        source_dir: Root of the source repository.
        item: The :class:`Item` being pushed back to the repo.

    Returns:
        Absolute path where the item should be written in the repo.

    """
    if item.item_type in (ItemType.AGENT, ItemType.COMMAND):
        return source_dir / item.item_type.plural / item.name / item.source_path.name
    # File-based items (plugins, configs): preserve original filename with extension.
    if item.item_type in (ItemType.PLUGIN, ItemType.CONFIG) and item.source_path.is_file():
        return source_dir / item.item_type.plural / item.source_path.name
    return source_dir / item.item_type.plural / item.name


def read_item_content(path: Path) -> tuple[str, Path] | None:
    """Read the primary content from a file or directory path.

    For regular files, returns the file text directly.  For directories,
    tries ``SKILL.md`` first, then the first non-hidden ``.md`` file
    (sorted alphabetically).

    Uses a single ``os.stat()`` call to classify the path, avoiding
    redundant syscalls from separate ``is_file()`` / ``is_dir()`` probes.

    Args:
        path: Filesystem path to a file or directory.

    Returns:
        A ``(content_text, actual_file_path)`` tuple on success, or
        ``None`` when the path does not exist, is not readable, or
        contains no suitable content files.

    """
    try:
        st = os.stat(path)
    except OSError:
        return None

    if stat_mod.S_ISREG(st.st_mode):
        try:
            content = path.read_text(encoding="utf-8", errors="replace")
            return (content, path)
        except OSError:
            logger.debug("Permission denied reading file %s", path, exc_info=True)
            return None

    if stat_mod.S_ISDIR(st.st_mode):
        return _read_dir_content(path)

    # Special file (socket, fifo, block/char device) or broken symlink
    # that somehow passed os.stat() — nothing to read.
    logger.debug(
        "Skipping non-regular/non-directory path %s (mode=%o)", path, stat_mod.S_IMODE(st.st_mode)
    )
    return None


def _read_dir_content(dir_path: Path) -> tuple[str, Path] | None:
    """Read content from a directory, trying SKILL.md first.

    Skips the extra ``is_file()`` probe before reading SKILL.md by
    catching ``FileNotFoundError`` directly, saving one stat syscall.

    For the fallback scan, filters to ``.md`` candidates *before*
    sorting so the sort operates on a smaller set.

    Args:
        dir_path: Directory to scan for content files.

    Returns:
        A ``(content_text, file_path)`` tuple, or ``None`` when the
        directory contains no readable ``.md`` files.

    """
    # Try SKILL.md — avoid a separate stat() probe; let read_text()
    # raise FileNotFoundError when absent.
    skill_md = dir_path / SKILL_MAIN_FILE
    try:
        return (skill_md.read_text(encoding="utf-8", errors="replace"), skill_md)
    except FileNotFoundError:
        pass
    except OSError:
        logger.debug("Cannot read %s in %s", SKILL_MAIN_FILE, dir_path, exc_info=True)

    # Fallback: first non-hidden .md file, sorted by name.
    # Filter candidates first so we only sort matching entries.
    try:
        candidates = sorted(
            (
                child
                for child in dir_path.iterdir()
                if not child.name.startswith(".") and child.suffix == ".md"
            ),
            key=lambda p: p.name,
        )
    except OSError:
        return None

    for candidate in candidates:
        try:
            if candidate.is_file():
                return (candidate.read_text(encoding="utf-8", errors="replace"), candidate)
        except OSError:
            # Permission error, broken symlink, or other I/O issue on one
            # candidate — skip it and try the next.
            logger.debug("Skipping unreadable candidate %s", candidate, exc_info=True)
            continue

    return None
