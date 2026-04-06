"""Git branch operations for local repositories.

Provides lightweight helpers for querying and switching branches in
locally-cloned git repositories.  All operations use the ``subprocess``
module directly — no third-party git libraries are required.

Only local (on-disk) repositories are supported; no remote fetching
or network operations are performed.

Performance notes:
    * ``get_current_branch`` reads ``.git/HEAD`` directly (filesystem
      read) instead of spawning a subprocess.
    * ``list_branches`` caches results per repository and reuses them
      until the cache is explicitly invalidated or ``switch_branch``
      succeeds.
"""

from __future__ import annotations

import logging
import subprocess
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from agentfiles.models import SyncodeError

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_GIT_HEAD_REF_PREFIX: Final = "ref: refs/heads/"

# Patterns used to classify common git errors in stderr.
_DIRTY_TREE_PATTERNS: Final[tuple[str, ...]] = (
    "your local changes",
    "would be overwritten",
    "please commit your changes",
    "local changes to the following",
)
_MERGE_CONFLICT_PATTERNS: Final[tuple[str, ...]] = (
    "merge conflict",
    "conflicts during",
    "CONFLICT",
)
_BRANCH_NOT_FOUND_PATTERNS: Final[tuple[str, ...]] = (
    "did not match any",
    "unknown revision",
)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class GitError(SyncodeError):
    """Base exception for git-related errors."""


class GitNotFoundError(GitError):
    """Raised when git is not installed or not found in PATH."""


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BranchInfo:
    """Metadata for a single git branch.

    Attributes:
        name: Branch name (e.g. ``"main"``, ``"develop"``).
        is_current: ``True`` when this is the active (checked-out) branch.

    """

    name: str
    is_current: bool


# ---------------------------------------------------------------------------
# Internal: branch cache
# ---------------------------------------------------------------------------

_branch_cache: dict[Path, list[BranchInfo]] = {}
_branch_cache_lock = threading.Lock()


def _cache_key(repo_path: Path) -> Path:
    """Return a canonical, symlink-resolved cache key for *repo_path*."""
    return repo_path.resolve()


def _invalidate_cache(repo_path: Path | None = None) -> None:
    """Invalidate cached branch data.

    Call this when branch state may have changed outside this module
    (e.g. a manual ``git checkout`` in a terminal).

    Args:
        repo_path: If given, invalidate only for that repo.
            If ``None``, invalidate all cached data.

    """
    with _branch_cache_lock:
        if repo_path is None:
            _branch_cache.clear()
            logger.debug("Cleared entire branch cache")
        else:
            removed = _branch_cache.pop(_cache_key(repo_path), None)
            if removed is not None:
                logger.debug("Invalidated branch cache for %s", repo_path)


# Backward-compatible alias — tests import ``invalidate_cache`` directly.
invalidate_cache = _invalidate_cache


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def run_git(
    *args: str,
    cwd: str | None = None,
    timeout: int = 30,
) -> subprocess.CompletedProcess[str]:
    """Run a git command and return the completed process result.

    Args:
        *args: Arguments passed to ``git`` (e.g. ``"branch"``, ``"--list"``).
        cwd: Working directory for the command.  When ``None`` the current
            process working directory is used.
        timeout: Maximum seconds to wait before raising
            :exc:`GitError`.  Defaults to 30.

    Returns:
        :class:`subprocess.CompletedProcess` with captured ``stdout`` and
        ``stderr`` as text.

    Raises:
        GitError: When the command times out.
        GitNotFoundError: When git is not installed.

    """
    try:
        return subprocess.run(
            ["git", *args],
            capture_output=True,
            text=True,
            cwd=cwd,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        raise GitError(f"git {' '.join(args)} timed out after {timeout}s") from exc
    except FileNotFoundError as exc:
        raise GitNotFoundError(
            "git is not installed or not found in PATH. "
            "Please install git and ensure it is accessible."
        ) from exc


# Backward-compatible alias — internal code and tests reference ``_run_git``.
_run_git = run_git


def _resolve_head_path(repo_path: Path) -> Path | None:
    """Locate the HEAD file for *repo_path*, handling worktrees.

    Regular repos store HEAD at ``.git/HEAD``.  Worktrees have a ``.git``
    *file* whose contents point to the actual git directory.

    Returns:
        :class:`Path` to the HEAD file, or ``None`` if it cannot be located.

    """
    dot_git = repo_path / ".git"

    if dot_git.is_file():
        # Worktree: .git contains "gitdir: <path>"
        try:
            content = dot_git.read_text().strip()
        except OSError:
            return None
        if not content.startswith("gitdir: "):
            return None
        gitdir = Path(content[len("gitdir: ") :])
        if not gitdir.is_absolute():
            gitdir = repo_path / gitdir
        return gitdir / "HEAD"

    if dot_git.is_dir():
        return dot_git / "HEAD"

    return None


def _read_head_branch(repo_path: Path) -> str | None:
    """Read the current branch from ``.git/HEAD`` without spawning a subprocess.

    Parses the symbolic ref line (e.g. ``ref: refs/heads/main``) to
    extract the branch name.

    Returns:
        Branch name string, or ``None`` when the HEAD file cannot be read
        or the repo is in detached-HEAD state.

    """
    head_path = _resolve_head_path(repo_path)
    if head_path is None:
        return None

    try:
        content = head_path.read_text().strip()
    except OSError:
        return None

    if content.startswith(_GIT_HEAD_REF_PREFIX):
        return content[len(_GIT_HEAD_REF_PREFIX) :]

    # Detached HEAD (raw SHA) or unrecognised format.
    return None


def _current_branch_from_cache(repo_path: Path) -> str | None:
    """Extract the current branch name from cached branch data.

    Returns:
        Branch name, or ``None`` when no cached data is available.

    """
    with _branch_cache_lock:
        cached = _branch_cache.get(_cache_key(repo_path))
        if cached is None:
            return None
        for branch in cached:
            if branch.is_current:
                return branch.name
        return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def is_git_repo(path: Path) -> bool:
    """Return ``True`` if *path* contains a ``.git`` directory or file.

    Args:
        path: Filesystem path to check.

    Returns:
        ``True`` when ``path/.git`` exists, ``False`` otherwise.

    """
    return (path / ".git").exists()


def get_current_branch(repo_path: Path) -> str:
    """Return the name of the currently checked-out branch.

    Resolution strategy (fastest first):

    1. Read ``.git/HEAD`` directly (filesystem read — no subprocess).
    2. Use cached data from a previous :func:`list_branches` call.
    3. Fall back to ``git rev-parse --abbrev-ref HEAD``.

    Args:
        repo_path: Root directory of a local git repository.

    Returns:
        Branch name string (e.g. ``"main"``, ``"develop"``), or an empty
        string when the path is not a git repo or the command fails.

    """
    if not is_git_repo(repo_path):
        logger.debug("Not a git repo: %s", repo_path)
        return ""

    # 1. Fast path: read .git/HEAD directly (no subprocess).
    branch = _read_head_branch(repo_path)
    if branch is not None:
        return branch

    # HEAD was readable but not a branch ref — likely detached HEAD.
    if _is_detached_head(repo_path):
        logger.info(
            "Repository at %s is in detached HEAD state; no branch name available.",
            repo_path,
        )
        return ""

    # 2. Check cache from list_branches().
    cached = _current_branch_from_cache(repo_path)
    if cached is not None:
        return cached

    # 3. Slow path: subprocess.
    result = _run_git("rev-parse", "--abbrev-ref", "HEAD", cwd=str(repo_path))
    if result.returncode != 0:
        logger.debug(
            "git rev-parse failed (exit %d): %s",
            result.returncode,
            result.stderr.strip(),
        )
        return ""

    return result.stdout.strip()


def get_repo_name(repo_path: Path) -> str:
    """Return the directory name of *repo_path*.

    Args:
        repo_path: Filesystem path to a repository directory.

    Returns:
        The resolved directory name (e.g. ``"my-agents"``).

    """
    return repo_path.resolve().name


def _is_detached_head(repo_path: Path) -> bool:
    """Return ``True`` when the repository is in a detached-HEAD state.

    A detached HEAD means the working tree is checked out at a specific
    commit rather than a named branch (e.g. after ``git checkout <sha>``).

    Args:
        repo_path: Root directory of a local git repository.

    Returns:
        ``True`` when HEAD points to a commit SHA instead of a branch ref.

    """
    if not is_git_repo(repo_path):
        return False

    head_path = _resolve_head_path(repo_path)
    if head_path is None:
        return False

    try:
        content = head_path.read_text().strip()
    except OSError:
        return False

    # If HEAD does NOT start with "ref: refs/heads/", it is detached.
    # (Empty HEAD means an unborn branch — not detached.)
    if not content:
        return False

    return not content.startswith(_GIT_HEAD_REF_PREFIX)


# Backward-compatible alias — tests import ``is_detached_head`` directly.
is_detached_head = _is_detached_head


def is_dirty(repo_path: Path) -> bool:
    """Return ``True`` when the working tree has uncommitted changes.

    Detects modified, staged, and untracked files that would prevent
    a clean branch switch.

    Args:
        repo_path: Root directory of a local git repository.

    Returns:
        ``True`` when there are uncommitted changes, ``False`` when the
        working tree is clean or the path is not a valid git repo.

    """
    if not is_git_repo(repo_path):
        return False

    result = _run_git("status", "--porcelain", cwd=str(repo_path))
    if result.returncode != 0:
        logger.debug(
            "git status --porcelain failed (exit %d): %s",
            result.returncode,
            result.stderr.strip(),
        )
        return False

    return result.stdout.strip() != ""


def list_branches(repo_path: Path) -> list[BranchInfo]:
    """List all local branches in *repo_path*.

    Runs ``git branch --list`` and parses the output.  The current branch
    (marked with ``*``) is placed first; remaining branches are sorted
    alphabetically.

    Results are cached per repository and reused until the cache is
    invalidated (see :func:`invalidate_cache`) or :func:`switch_branch`
    succeeds.

    Args:
        repo_path: Root directory of a local git repository.

    Returns:
        A list of :class:`BranchInfo` instances.  Returns an empty list
        when the path is not a git repo or the command fails.

    """
    if not is_git_repo(repo_path):
        logger.debug("Cannot list branches — not a git repo: %s", repo_path)
        return []

    # Return cached data if available.
    key = _cache_key(repo_path)
    with _branch_cache_lock:
        if key in _branch_cache:
            logger.debug("Using cached branch data for %s", repo_path)
            return list(_branch_cache[key])

    result = _run_git("branch", "--list", cwd=str(repo_path))
    if result.returncode != 0:
        logger.debug(
            "git branch --list failed (exit %d): %s",
            result.returncode,
            result.stderr.strip(),
        )
        return []

    branches = _parse_branch_output(result.stdout)

    # Sort: current branch first, then alphabetically by name.
    branches.sort(key=lambda b: (not b.is_current, b.name))

    with _branch_cache_lock:
        _branch_cache[key] = branches
    return list(branches)


def switch_branch(repo_path: Path, branch_name: str) -> bool:
    """Switch the working tree to *branch_name*.

    Runs ``git checkout <branch_name>`` inside *repo_path*.
    Invalidates the branch cache on success.

    Performs a pre-check via :func:`is_dirty` to detect uncommitted
    changes *before* attempting checkout, producing a clear error
    message rather than relying on git's stderr parsing.

    Args:
        repo_path: Root directory of a local git repository.
        branch_name: Name of the branch to check out.

    Returns:
        ``True`` on success, ``False`` on failure (including when
        *repo_path* is not a git repository or the working tree is dirty).

    """
    if not is_git_repo(repo_path):
        logger.debug("Cannot switch branch — not a git repo: %s", repo_path)
        return False

    if is_dirty(repo_path):
        logger.warning(
            "Cannot switch to branch '%s' in %s: "
            "working tree has uncommitted changes. "
            "Commit, stash, or discard changes first.",
            branch_name,
            repo_path,
        )
        return False

    logger.info("Switching to branch '%s' in %s", branch_name, repo_path)

    result = _run_git("checkout", branch_name, cwd=str(repo_path))
    if result.returncode != 0:
        _log_switch_failure(branch_name, repo_path, result)
        return False

    logger.info("Successfully switched to branch '%s'", branch_name)
    _invalidate_cache(repo_path)
    return True


@dataclass(frozen=True)
class PullResult:
    """Outcome of a ``git pull`` operation.

    Attributes:
        success: Whether the pull completed without errors.
        stdout: Captured standard output from git.
        stderr: Captured standard error from git.
        error_hint: Human-readable classification of a failure, or ``None``.

    """

    success: bool
    stdout: str
    stderr: str
    error_hint: str | None = None


# Patterns that indicate transient network or connectivity issues.
_NETWORK_ERROR_PATTERNS: Final[tuple[str, ...]] = (
    "could not resolve host",
    "network is unreachable",
    "connection timed out",
    "connection refused",
    "ssl certificate problem",
    "fatal: unable to access",
    "early eof",
    "rpc failed",
)

# Patterns that indicate a local conflict preventing the pull.
_LOCAL_CONFLICT_PATTERNS: Final[tuple[str, ...]] = (
    "conflict",
    "would be overwritten",
    "your local changes",
    "please commit your changes",
    "error: your local changes",
    "merge conflict",
)


def pull_repo(repo_path: Path) -> PullResult:
    """Run ``git pull --autostash --rebase`` in *repo_path*.

    Uses ``--autostash`` so that uncommitted local changes are stashed
    before the pull and reapplied afterwards, reducing friction for
    multi-machine workflows (inspired by chezmoi's update command).

    Falls back to ``git pull`` (without ``--autostash --rebase``) when
    the primary command fails due to an older git version that does not
    support those flags.

    Args:
        repo_path: Root directory of a local git repository.

    Returns:
        A :class:`PullResult` with the operation outcome and an optional
        error hint when the pull failed.

    """
    if not is_git_repo(repo_path):
        return PullResult(
            success=False,
            stdout="",
            stderr="",
            error_hint="Not a git repository.",
        )

    cwd = str(repo_path)

    # Try the preferred pull strategy first.
    result = _run_git("pull", "--autostash", "--rebase", cwd=cwd, timeout=60)
    if result.returncode == 0:
        return PullResult(success=True, stdout=result.stdout, stderr=result.stderr)

    # Detect "unknown option" → older git without --autostash support.
    stderr_lower = result.stderr.lower()
    if "unknown option" in stderr_lower or "unrecognized option" in stderr_lower:
        logger.info("Falling back to plain git pull (older git version)")
        result = _run_git("pull", cwd=cwd, timeout=60)
        if result.returncode == 0:
            return PullResult(success=True, stdout=result.stdout, stderr=result.stderr)

    # Classify the error for a better user-facing message.
    error_hint = _classify_pull_error(result.stderr)
    return PullResult(
        success=False,
        stdout=result.stdout,
        stderr=result.stderr,
        error_hint=error_hint,
    )


def _classify_pull_error(stderr: str) -> str | None:
    """Classify a ``git pull`` stderr message into a known error category.

    Args:
        stderr: Raw stderr output from a failed git pull.

    Returns:
        A human-readable category string, or ``None`` when the error
        does not match any known pattern.

    """
    lower = stderr.lower()
    for pattern in _NETWORK_ERROR_PATTERNS:
        if pattern in lower:
            return (
                "Network error: check your internet connection and "
                "repository access, then try again."
            )
    for pattern in _LOCAL_CONFLICT_PATTERNS:
        if pattern in lower:
            return "Local conflict: commit, stash, or discard local changes before pulling."
    return None


# ---------------------------------------------------------------------------
# Internal parsing
# ---------------------------------------------------------------------------


def _classify_error(stderr: str) -> str | None:
    """Classify a git stderr message into a known error category.

    Args:
        stderr: Raw stderr output from a failed git command.

    Returns:
        A human-readable category string, or ``None`` when the error
        does not match any known pattern.

    """
    lower = stderr.lower()
    for pattern in _DIRTY_TREE_PATTERNS:
        if pattern in lower:
            return (
                "dirty working tree: uncommitted changes would be "
                "overwritten. Commit, stash, or discard changes first."
            )
    for pattern in _MERGE_CONFLICT_PATTERNS:
        if pattern in lower:
            return "merge conflict: resolve conflicts before switching branches."
    if any(p in lower for p in _BRANCH_NOT_FOUND_PATTERNS):
        return "branch not found: the specified branch does not exist in this repository."
    return None


def _log_switch_failure(
    branch_name: str,
    repo_path: Path,
    result: subprocess.CompletedProcess[str],
) -> None:
    """Log a clear, human-readable message for a failed branch switch.

    Tries to classify the error from stderr; falls back to logging the
    raw git output when classification is not possible.

    Args:
        branch_name: The branch that was targeted.
        repo_path: The repository where the switch was attempted.
        result: The failed ``CompletedProcess`` from ``git checkout``.

    """
    stderr = result.stderr.strip()
    classification = _classify_error(stderr)

    if classification is not None:
        logger.warning(
            "Cannot switch to branch '%s' in %s: %s",
            branch_name,
            repo_path,
            classification,
        )
    else:
        logger.warning(
            "git checkout %s failed (exit %d): %s",
            branch_name,
            result.returncode,
            stderr,
        )


def _parse_branch_output(output: str) -> list[BranchInfo]:
    """Parse ``git branch --list`` output into :class:`BranchInfo` instances.

    Each line of the output has one of two formats::

        * current_branch
          other_branch

    Lines starting with ``*`` mark the active branch.

    Args:
        output: Raw stdout from ``git branch --list``.

    Returns:
        A list of parsed :class:`BranchInfo` instances.

    """
    # git branch --list format: "* current_name" or "  other_name"
    # The prefix is always exactly 2 characters, so line[2:] extracts
    # the branch name portion regardless of which prefix is present.
    branches: list[BranchInfo] = []
    for line in output.splitlines():
        if not line.strip():
            continue

        is_current = line.startswith("*")
        name = line[2:].strip()

        if name:
            branches.append(BranchInfo(name=name, is_current=is_current))

    return branches
