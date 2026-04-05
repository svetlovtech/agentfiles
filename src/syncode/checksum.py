"""Checksum computation for files and directories.

Provides deterministic SHA-256 digest computation for syncable items
(files, directories).  Used by the sync engine, differ, and CLI to
detect content changes between source and target installations.

Public API
----------
compute_checksum:
    SHA-256 hex digest for a file or directory, with optional size
    pre-check for fast skip.
compute_checksum_with_size:
    SHA-256 digest *and* total byte size in a single pass.
"""

from __future__ import annotations

import hashlib
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Lazy import helper — avoids circular import with syncode.models
# ---------------------------------------------------------------------------
# checksum.py is imported by models.py at module level.  If we imported
# SourceError from models.py at *our* module level, the two modules would
# deadlock during initial loading.  Instead, we resolve SourceError
# lazily on first use via ``_source_error()``.


_cached_source_error: type | None = None


def _source_error() -> type:
    """Return ``syncode.models.SourceError``, caching after first call."""
    global _cached_source_error
    if _cached_source_error is None:
        from syncode.models import SourceError

        _cached_source_error = SourceError
    return _cached_source_error


# ---------------------------------------------------------------------------
# Shared constants
# ---------------------------------------------------------------------------

# 64 KiB — optimal for most filesystems; avoids extra syscalls.
_SHA256_BLOCK_SIZE: int = 65_536

# ---------------------------------------------------------------------------
# Internal helpers (module-private)
# ---------------------------------------------------------------------------


def _file_sha256(filepath: Path) -> str:
    """Return the SHA-256 hex digest of a single file.

    Reads the file in 64 KiB chunks to avoid loading the entire file
    into memory.

    Args:
        filepath: Absolute path to the file to hash.

    Returns:
        64-character lowercase hex string.

    Raises:
        OSError: When the file cannot be opened or read.

    """
    hasher = hashlib.sha256()
    with open(filepath, "rb") as fh:
        for chunk in iter(lambda: fh.read(_SHA256_BLOCK_SIZE), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _directory_size(directory: Path) -> int:
    """Return total byte size of all files in *directory*.

    Walks the directory tree recursively and sums ``st_size`` for every
    regular file.  Unreadable entries (permission errors, broken symlinks)
    are silently skipped and contribute ``0`` to the total.

    Args:
        directory: Absolute path to the directory to measure.

    Returns:
        Total size in bytes across all readable files.
    """
    total = 0
    for root, _dirs, filenames in os.walk(directory):
        for fname in filenames:
            try:
                total += os.stat(os.path.join(root, fname)).st_size
            except OSError:
                continue
    return total


def _directory_sha256(directory: Path) -> str:
    """Deterministic SHA-256 of all files in *directory*.

    Produces a single digest that changes when any file's content or
    the set of files changes.  The algorithm:

    1. Walk the directory tree and compute per-file SHA-256 digests.
    2. Build ``"<relative_path>:<hex_digest>"`` entries for each file.
    3. Sort entries alphabetically for determinism (``os.walk`` order
       varies across platforms and filesystems).
    4. Feed the sorted entries into a SHA-256 hasher (newline-separated)
       without building a single large intermediate string.

    An empty directory produces the SHA-256 of the empty string.

    Args:
        directory: Absolute path to the directory to hash.

    Returns:
        64-character lowercase hex string.

    Raises:
        SourceError: When any file in the tree cannot be read.
    """
    SourceError = _source_error()  # noqa: N806
    entries: list[str] = []
    for root, _dirs, filenames in os.walk(directory):
        for fname in sorted(filenames):
            fpath = Path(root) / fname
            rel = fpath.relative_to(directory)
            try:
                digest = _file_sha256(fpath)
            except OSError as exc:
                raise SourceError(
                    f"cannot read '{fpath}' while computing directory "
                    f"checksum: {exc}. Check file permissions or whether "
                    f"the file is accessible"
                ) from exc
            entries.append(f"{rel}:{digest}")

    hasher = hashlib.sha256()
    # Sort by relative path so the checksum is deterministic regardless of
    # OS or filesystem — os.walk() and directory iteration order are not
    # guaranteed to be consistent across platforms.
    sorted_entries = sorted(entries)
    if sorted_entries:
        hasher.update(sorted_entries[0].encode("utf-8"))
        for entry in sorted_entries[1:]:
            hasher.update(b"\n")
            hasher.update(entry.encode("utf-8"))
    return hasher.hexdigest()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def compute_checksum(path: Path, *, expected_size: int | None = None) -> str:
    """Compute a SHA-256 hex checksum for a file or directory.

    For a **file** the digest is the SHA-256 of its binary contents.
    For a **directory** the digest is the SHA-256 of the concatenated
    per-file checksums sorted by relative path, ensuring determinism
    regardless of filesystem traversal order.

    When *expected_size* is provided and the actual size does not
    match, the expensive SHA-256 computation is skipped and an empty
    string is returned immediately.  This is useful during diff
    operations where a size mismatch already proves the content has
    changed.

    Args:
        path: Path to a file or directory.
        expected_size: Optional byte size to check before hashing.
            When the actual size differs, returns ``""`` without
            computing the digest.

    Returns:
        Hex-encoded SHA-256 digest string, or ``""`` when
        *expected_size* is set and does not match the actual size.

    Raises:
        SourceError: When *path* does not exist, is not a regular
            file or directory, or cannot be read.

    """
    SourceError = _source_error()  # noqa: N806
    if not path.exists():
        raise SourceError(
            f"cannot compute checksum: path does not exist: '{path}'. "
            f"Ensure the file or directory is present before syncing"
        )

    if path.is_file():
        if expected_size is not None:
            try:
                actual_size = os.stat(path).st_size
            except OSError as exc:
                raise SourceError(
                    f"cannot stat file '{path}' to verify size: {exc}. "
                    f"Check file permissions or whether the path is accessible"
                ) from exc
            if actual_size != expected_size:
                return ""
        try:
            return _file_sha256(path)
        except OSError as exc:
            raise SourceError(
                f"cannot read file '{path}' for checksum: {exc}. "
                f"Check file permissions or whether it is corrupted"
            ) from exc

    if path.is_dir():
        if expected_size is not None:
            actual_size = _directory_size(path)
            if actual_size != expected_size:
                return ""
        return _directory_sha256(path)

    raise SourceError(
        f"unsupported path type for checksum: '{path}' is neither a regular "
        f"file nor a directory. Symlinks, devices, and sockets are not supported"
    )


def compute_checksum_with_size(path: Path) -> tuple[str, int]:
    """Compute both SHA-256 checksum and total byte size in one pass.

    Useful for callers that need to cache both values for later
    size-based quick comparisons via :func:`compute_checksum`.

    Args:
        path: Path to a file or directory.

    Returns:
        Tuple of ``(hex_sha256_digest, total_byte_size)``.

    Raises:
        SourceError: When *path* does not exist, is not a regular
            file or directory, or cannot be read.

    """
    SourceError = _source_error()  # noqa: N806
    if not path.exists():
        raise SourceError(
            f"cannot compute checksum and size: path does not exist: '{path}'. "
            f"Ensure the file or directory is present before syncing"
        )

    if path.is_file():
        try:
            size = os.stat(path).st_size
            digest = _file_sha256(path)
        except OSError as exc:
            raise SourceError(
                f"cannot read file '{path}' for checksum: {exc}. "
                f"Check file permissions or whether it is corrupted"
            ) from exc
        return digest, size

    if path.is_dir():
        size = _directory_size(path)
        digest = _directory_sha256(path)
        return digest, size

    raise SourceError(
        f"unsupported path type for checksum: '{path}' is neither a regular "
        f"file nor a directory. Symlinks, devices, and sockets are not supported"
    )
