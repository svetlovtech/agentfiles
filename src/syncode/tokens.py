"""Token counting utilities for estimating LLM context window usage.

Provides fast, heuristic-based token estimation for configuration items
(agents, skills, commands, plugins) to help users understand the "cost"
of each item in terms of context window consumption.

Uses a simple character-based heuristic (~4 chars per token) consistent
with common BPE/GPT tokenizers.

Public API
----------
:data:`CHARS_PER_TOKEN`      Approximate characters per LLM token.

:func:`estimate_tokens_from_content`  Token count for a text string.
:func:`estimate_tokens_from_files`    Token count across file contents.
:func:`token_estimate`                Full :class:`TokenEstimate` for an item.
:func:`count_item_tokens`             Fast size-based estimate for an item.
:func:`format_token_count`            Human-readable token display (``1.2k``).
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from syncode.models import Item, TokenEstimate

logger = logging.getLogger(__name__)

# Approximate number of characters per LLM token.  The standard heuristic
# for English text is ~4 characters per token; this is used for quick
# size-based estimates without a tokenizer dependency.
CHARS_PER_TOKEN: int = 4


# ---------------------------------------------------------------------------
# Content-based estimation
# ---------------------------------------------------------------------------


def estimate_tokens_from_content(content: str) -> int:
    """Estimate the token count for a text string.

    Uses a character-based heuristic (:data:`CHARS_PER_TOKEN`) so that
    no external tokenizer is required.

    Args:
        content: Text to estimate tokens for.

    Returns:
        Estimated number of tokens.  Returns ``0`` for empty strings
        and at least ``1`` for any non-empty string.

    """
    if not content:
        return 0
    return max(1, len(content) // CHARS_PER_TOKEN)


def estimate_tokens_from_files(files: list[Path]) -> int:
    """Estimate token count by reading file contents.

    Each file is read as UTF-8 text and its token count is estimated
    via :func:`estimate_tokens_from_content`.  Binary files and
    unreadable paths are silently skipped.

    Args:
        files: List of absolute file paths to read.

    Returns:
        Estimated number of tokens across all readable files.

    """
    total = 0
    for fpath in files:
        try:
            total += estimate_tokens_from_content(
                fpath.read_text(encoding="utf-8"),
            )
        except (OSError, UnicodeDecodeError):
            continue
    return total


# ---------------------------------------------------------------------------
# File-size-based estimation (fast, no I/O content read)
# ---------------------------------------------------------------------------


def _estimate_file_tokens_from_size(path: Path) -> int:
    """Estimate tokens from file size without reading content.

    Uses :func:`os.path.getsize` to obtain the byte count, avoiding the
    cost of reading file contents into memory.  For typical UTF-8 / ASCII
    Markdown files ``len(content) ≈ file_size``, making this a fast and
    accurate approximation.

    Args:
        path: Path to a file on disk.

    Returns:
        Estimated token count.  Returns ``0`` when the file cannot be
        stat'd or is empty.

    """
    try:
        file_size = os.path.getsize(path)
    except OSError:
        logger.debug("Cannot stat file for token count: %s", path)
        return 0
    if file_size == 0:
        return 0
    return max(1, file_size // CHARS_PER_TOKEN)


def count_item_tokens(source_path: Path) -> int:
    """Count estimated tokens for a configuration item.

    Handles both single-file items (agents, commands) and directory-based
    items (skills, plugins).  For directories, recursively scans for
    ``*.md`` files.

    Uses file size rather than reading content for fast estimation.

    Args:
        source_path: Path to a file or directory on disk.

    Returns:
        Estimated token count.  Returns ``0`` when the path does not
        exist.

    """
    if source_path.is_file():
        return _estimate_file_tokens_from_size(source_path)
    if source_path.is_dir():
        total = 0
        for f in source_path.rglob("*.md"):
            total += _estimate_file_tokens_from_size(f)
        return total
    logger.debug("Path is neither file nor directory: %s", source_path)
    return 0


# ---------------------------------------------------------------------------
# Full item token estimation (content + overhead breakdown)
# ---------------------------------------------------------------------------


def _resolve_item_files(item: Item) -> list[Path]:
    """Resolve an item's relative file paths to absolute paths.

    For file-based items (agents, commands) the ``source_path`` is the
    file itself and ``files`` contains just its name.  For directory-based
    items (skills, plugins) ``source_path`` is the directory and ``files``
    contains paths relative to it.

    Args:
        item: The item whose files to resolve.

    Returns:
        List of absolute paths that exist on disk.

    """
    if item.source_path.is_file():
        return [item.source_path]

    return [full for rel in item.files if (full := item.source_path / rel).is_file()]


def _compute_total_size(files: list[Path]) -> int:
    """Sum the byte sizes of all files in the list.

    Args:
        files: Absolute paths to files on disk.

    Returns:
        Total size in bytes.  Unreadable files contribute ``0``.

    """
    total = 0
    for fpath in files:
        try:
            total += fpath.stat().st_size
        except OSError:
            continue
    return total


def _estimate_overhead_tokens(item: Item) -> int:
    """Estimate tokens consumed by YAML frontmatter metadata.

    Approximates the token cost of rendering an item's metadata
    (name, description, version, file count) in the context window.

    Args:
        item: The item whose frontmatter overhead to estimate.

    Returns:
        Estimated overhead tokens (always ``>= 0``).

    """
    parts: list[str] = [item.name, item.version]

    if item.meta is not None:
        if item.meta.description:
            parts.append(item.meta.description)
        if item.meta.priority:
            parts.append(item.meta.priority)

    parts.extend(item.files)
    return estimate_tokens_from_content(" ".join(parts))


def token_estimate(item: Item) -> TokenEstimate:
    """Compute a detailed token estimate for *item*.

    Reads all item files on disk to produce an accurate per-item
    breakdown of content tokens versus frontmatter overhead.

    Args:
        item: The item to estimate.

    Returns:
        A :class:`~syncode.models.TokenEstimate` with the full breakdown.

    """
    resolved_files = _resolve_item_files(item)
    source_size = _compute_total_size(resolved_files)
    content_tokens = estimate_tokens_from_files(resolved_files)
    overhead = _estimate_overhead_tokens(item)

    return TokenEstimate(
        name=item.name,
        item_type=item.item_type,
        files=item.files,
        source_size_bytes=source_size,
        content_tokens=content_tokens,
        overhead_tokens=overhead,
        total_tokens=content_tokens + overhead,
    )


# ---------------------------------------------------------------------------
# Display formatting
# ---------------------------------------------------------------------------


def format_token_count(count: int) -> str:
    """Format a token count for compact display in a table column.

    Args:
        count: Raw token count.

    Returns:
        Human-readable string with ``k`` suffix for thousands
        (e.g. ``"1.2k"``, ``"500"``).

    """
    if count >= 1000:
        return f"{count / 1000:.1f}k"
    return str(count)
