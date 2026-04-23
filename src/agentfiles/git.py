"""Git operations for local and remote repositories.

Provides lightweight helpers for interacting with git repositories.
All operations use the ``subprocess`` module directly — no third-party
git libraries are required.
"""

from __future__ import annotations

import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from agentfiles.models import AgentfilesError

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class GitError(AgentfilesError):
    """Base exception for git-related errors."""


class GitNotFoundError(GitError):
    """Raised when git is not installed or not found in PATH."""


# ---------------------------------------------------------------------------
# Core helpers
# ---------------------------------------------------------------------------


def run_git(
    *args: str,
    cwd: str | None = None,
    timeout: int = 30,
) -> subprocess.CompletedProcess[str]:
    """Run a git command and return the completed process result.

    Args:
        *args: Arguments passed to ``git`` (e.g. ``"clone"``, ``"pull"``).
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


# Backward-compatible alias — internal code references ``_run_git``.
_run_git = run_git


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

    # Detect "unknown option" -> older git without --autostash support.
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


def shallow_clone(
    url: str,
    dest: Path,
    branch: str | None = None,
    depth: int = 1,
    timeout: int = 120,
) -> subprocess.CompletedProcess[str]:
    """Shallow-clone *url* into *dest* with ``--depth``.

    Args:
        url: Remote repository URL.
        dest: Local directory to clone into.
        branch: If given, clone only this branch (``--branch``).
        depth: History depth (default ``1``).
        timeout: Seconds before timeout.

    Returns:
        The completed process result.

    Raises:
        GitError: On timeout.
        GitNotFoundError: When git is not installed.

    """
    args: list[str] = ["clone", "--depth", str(depth)]
    if branch is not None:
        args.extend(["--branch", branch])
    args.extend([url, str(dest)])
    return run_git(*args, timeout=timeout)


def sparse_checkout_init(
    repo_dir: Path,
    dirs: list[str],
    timeout: int = 30,
) -> None:
    """Enable sparse-checkout in *repo_dir* for only *dirs*.

    Runs ``git sparse-checkout init --cone`` followed by
    ``git sparse-checkout set <dirs...>``.

    Args:
        repo_dir: Root of an existing git clone.
        dirs: Directory names to include in the sparse checkout.
        timeout: Seconds before timeout per command.

    Raises:
        GitError: On timeout or command failure.
        GitNotFoundError: When git is not installed.

    """
    cwd = str(repo_dir)
    result = run_git("sparse-checkout", "init", "--cone", cwd=cwd, timeout=timeout)
    if result.returncode != 0:
        logger.warning(
            "sparse-checkout init failed (exit %d): %s",
            result.returncode,
            result.stderr.strip(),
        )
        return
    result = run_git("sparse-checkout", "set", *dirs, cwd=cwd, timeout=timeout)
    if result.returncode != 0:
        logger.warning(
            "sparse-checkout set failed (exit %d): %s",
            result.returncode,
            result.stderr.strip(),
        )
