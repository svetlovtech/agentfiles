"""Source detection and resolution for agentfiles.

This module translates a user-supplied path string (or ``None`` for auto-
detection) into a concrete local filesystem directory that the scanner can
traverse.  The two-phase design separates *detection* from *resolution*:

**Phase 1 — Detection** (:meth:`SourceResolver.detect`)
    Classifies the input into one of three :class:`SourceType` values:

    - ``LOCAL_DIR`` — a plain directory on disk.
    - ``GIT_DIR``   — a directory that contains a ``.git`` entry.
    - ``GIT_URL``   — a remote URL (HTTPS, SSH, ``git://``).

    When the input is ``None``, the resolver walks from the CWD upward looking
    for a directory with at least two of the four recognised source
    sub-directories (``agents/``, ``skills/``, ``commands/``, ``plugins/``).

**Phase 2 — Resolution** (:meth:`SourceResolver.resolve`)
    Converts the detected :class:`SourceInfo` into a usable local path:

    - Local / git-directory sources are returned as-is (already absolute).
    - Remote URLs are shallow-cloned (``--depth 1``) into a cache directory
      (default ``~/.cache/agentfiles/repos``).  Subsequent resolves fetch the
      latest commit and ``reset --hard`` only when the remote HEAD differs,
      avoiding unnecessary merge overhead.

**Extensibility**
    Git operations are abstracted behind the :class:`GitBackend` protocol so
    that callers can inject mock implementations for testing or swap in
    alternative git libraries without touching the resolution logic.
"""

from __future__ import annotations

import logging
import os
import stat
import subprocess
from pathlib import Path
from typing import Final, Protocol, runtime_checkable

from agentfiles.git import is_git_repo, run_git
from agentfiles.models import ItemType, SourceError, SourceInfo, SourceType

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants (module-private)
# ---------------------------------------------------------------------------

_SOURCE_DIR_NAMES: Final = frozenset(t.plural for t in ItemType)
_DEFAULT_CACHE_ROOT: Final = Path.home() / ".cache" / "agentfiles" / "repos"

_GIT_URL_PREFIXES: Final = (
    "http://",
    "https://",
    "git://",
    "git@",
    "ssh://",
)

_AGENTFILES_CONFIG_NAMES: Final = (".agentfiles.yaml", ".agentfiles.yml")

# ---------------------------------------------------------------------------
# Git error classification — maps known stderr patterns to actionable hints
# ---------------------------------------------------------------------------


def _classify_git_stderr(stderr: str) -> str | None:
    """Return a human-readable hint for a recognised git error pattern.

    Scans *stderr* for well-known git error substrings and returns a
    short, actionable message.  Returns ``None`` when no pattern matches.
    """
    lower = stderr.lower()

    # Authentication failures
    if any(
        s in lower
        for s in (
            "could not read username",
            "authentication failed",
            "permission denied (publickey)",
            "fatal: could not read from remote repository",
        )
    ):
        return "check your credentials and repository access permissions"

    # Repository not found
    if "repository not found" in lower or "not found" in lower:
        return "verify the repository URL is correct and the repo exists"

    # Network connectivity
    if any(
        s in lower
        for s in (
            "could not resolve host",
            "unable to access",
            "connection refused",
            "network is unreachable",
            "failed to connect",
        )
    ):
        return "check your network connection and try again"

    # Disk space
    if "no space left on device" in lower:
        return "disk is full — free up space or change the cache directory"

    # Destination already exists (clone into non-empty dir)
    if "already exists and is not an empty directory" in lower:
        return "clone target directory already exists — remove it and retry"

    return None


def _git_error_from_timeout(operation: str, url_or_path: str, timeout: int) -> SourceError:
    """Build a :class:`SourceError` for a git timeout."""
    return SourceError(
        f"git {operation} timed out after {timeout}s for '{url_or_path}'. "
        f"Check your network connection or increase the timeout"
    )


def _git_error_from_file_not_found(operation: str, url_or_path: str) -> SourceError:
    """Build a :class:`SourceError` for missing git binary."""
    return SourceError(
        f"git {operation} failed: 'git' command not found. "
        f"Please install git and ensure it is on your PATH"
    )


def _git_error_from_os_error(operation: str, url_or_path: str, exc: OSError) -> SourceError:
    """Build a :class:`SourceError` for a filesystem-level OSError."""
    hint = ""
    if exc.errno == 28 or "no space left" in str(exc).lower():
        hint = " — disk may be full, free up space and retry"
    elif exc.errno == 13:
        hint = " — permission denied, check directory ownership"
    return SourceError(f"git {operation} failed for '{url_or_path}': {exc}{hint}")


# ---------------------------------------------------------------------------
# GitBackend protocol — DIP abstraction for git operations
# ---------------------------------------------------------------------------


@runtime_checkable
class GitBackend(Protocol):
    """Abstraction for git operations used by :class:`SourceResolver`.

    Decouples the high-level source resolution logic from the low-level
    subprocess-based git implementation, allowing alternative backends
    (e.g. in-memory, GitPython) and easier testing via mock injection.

    **Protocol contract**

    Every backend must implement three methods:

    - :meth:`clone` — create a shallow clone of a remote repository.
    - :meth:`pull`  — update an existing clone to the latest remote commit.
    - :meth:`is_git_repo` — check whether a local path contains a ``.git`` entry.

    **Implementing a custom backend**

    Any object that provides the three methods with matching signatures
    satisfies the protocol automatically (structural sub-typing)::

        class InMemoryGitBackend:
            def clone(self, url: str, target: Path) -> None: ...
            def pull(self, repo_path: Path) -> None: ...
            def is_git_repo(self, path: Path) -> bool: ...

        resolver = SourceResolver(git_backend=InMemoryGitBackend())

    Because the protocol is ``@runtime_checkable``, ``isinstance`` checks
    work at runtime and ``MagicMock(spec=GitBackend)`` in tests is accepted
    by ``SourceResolver``.
    """

    def clone(self, url: str, target: Path) -> None:
        """Shallow-clone *url* into *target* directory.

        Args:
            url: Remote repository URL (HTTPS, SSH, etc.).
            target: Local directory to create.  May or may not exist
                when the method is called; the implementation must handle
                both cases.

        Raises:
            SourceError: When the clone fails (network, auth, disk, etc.).

        """
        ...

    def pull(self, repo_path: Path) -> None:
        """Update *repo_path* to the latest remote commit.

        The implementation is free to choose the update strategy (fetch +
        merge, fetch + reset, etc.).  See :class:`SubprocessGitBackend.pull`
        for the default fetch → compare → reset approach.

        Args:
            repo_path: Path to an existing local git clone.

        Raises:
            SourceError: When the update fails (network, auth, disk, etc.).

        """
        ...

    def is_git_repo(self, path: Path) -> bool:
        """Return ``True`` if *path* contains a ``.git`` entry.

        The check should recognise both a ``.git`` directory (standard
        clone) and a ``.git`` file (worktree or submodule).

        Args:
            path: Local filesystem path to inspect.

        Returns:
            ``True`` when a ``.git`` entry exists, ``False`` otherwise.

        """
        ...


class SubprocessGitBackend:
    """Default :class:`GitBackend` backed by the ``git`` subprocess.

    Delegates to :func:`agentfiles.git.run_git` for clone / fetch / reset
    operations and :func:`agentfiles.git.is_git_repo` for ``.git`` detection.

    **Error handling**

    Every git subprocess failure is translated into a :class:`SourceError`
    with an actionable hint extracted by :func:`_classify_git_stderr`.
    Recognised failure categories:

    - **Timeout** — ``subprocess.TimeoutExpired`` → message with elapsed time.
    - **Git not installed** — ``FileNotFoundError`` → install prompt.
    - **OSError** — disk full / permission denied → specific hint.
    - **Non-zero exit** — stderr is scanned for patterns (auth, network,
      repo-not-found, disk space) and the hint is appended after ``→``.

    **Smart pull strategy** (see :meth:`pull` for details)

    Uses a fetch → compare → reset sequence that skips the expensive merge
    machinery when the local clone is already up-to-date.
    """

    _CLONE_TIMEOUT: int = 120  # seconds

    def _run_git_checked(
        self,
        operation: str,
        url_or_path: str,
        timeout: int,
        *git_args: str,
        cwd: str | None = None,
    ) -> subprocess.CompletedProcess[str]:
        """Run a git subprocess with uniform error handling.

        Wraps :func:`agentfiles.git._run_git` and translates all failure modes
        (timeout, missing binary, OS errors, non-zero exit) into
        :class:`SourceError` with actionable hints.

        Args:
            operation: Human-readable name for error messages (e.g. ``"clone"``).
            url_or_path: URL or path included in error messages.
            timeout: Timeout in seconds.
            *git_args: Positional arguments forwarded to :func:`_run_git`.
            cwd: Working directory for the git command.

        Returns:
            A :class:`subprocess.CompletedProcess` with ``returncode == 0``.

        Raises:
            SourceError: On any failure (timeout, missing git, OS error,
                or non-zero exit code).

        """
        try:
            result = run_git(*git_args, cwd=cwd, timeout=timeout)
        except subprocess.TimeoutExpired:
            raise _git_error_from_timeout(operation, url_or_path, timeout) from None
        except FileNotFoundError:
            raise _git_error_from_file_not_found(operation, url_or_path) from None
        except OSError as exc:
            raise _git_error_from_os_error(operation, url_or_path, exc) from exc

        if result.returncode != 0:
            stderr = result.stderr.strip()
            hint = _classify_git_stderr(stderr)
            parts = [f"git {operation} failed for '{url_or_path}' (exit {result.returncode})"]
            if stderr:
                parts.append(stderr)
            if hint:
                parts.append(f"→ {hint}")
            raise SourceError(": ".join(parts))

        return result

    def clone(self, url: str, target: Path) -> None:
        """Shallow-clone *url* into *target*."""
        # --depth 1 fetches only the latest commit, not the full history.
        # Sync operations only need current file content, so the history
        # would be wasted bandwidth and disk space for a cache clone.
        self._run_git_checked(
            "clone",
            url,
            self._CLONE_TIMEOUT,
            "clone",
            "--depth",
            "1",
            url,
            str(target),
        )

    _FETCH_TIMEOUT: int = 120  # seconds
    _RESET_TIMEOUT: int = 30  # seconds
    _REV_PARSE_TIMEOUT: int = 10  # seconds

    def pull(self, repo_path: Path) -> None:
        """Fetch and update *repo_path*, skipping merge if already up-to-date.

        Uses a three-step "smart pull" strategy optimised for cached shallow
        clones that never carry user modifications:

        1. **Fetch** — ``git fetch --depth=1`` retrieves the latest remote
           commit SHA into ``FETCH_HEAD`` without touching the working tree.
        2. **Compare** — ``git rev-parse HEAD`` vs ``git rev-parse FETCH_HEAD``.
           If the SHAs match the clone is already current → **return early**,
           saving the cost of the reset and working-tree write.
        3. **Reset** — ``git reset --hard FETCH_HEAD`` updates the working
           tree to the newly fetched commit.  ``reset --hard`` is preferred
           over ``merge`` because cached clones have no local changes to
           preserve, and reset avoids the merge-driver overhead.

        Args:
            repo_path: Path to an existing local git clone.

        Raises:
            SourceError: On fetch failure, reset failure, timeout, or when
                git is not installed.

        """
        self._run_git_checked(
            "fetch",
            str(repo_path),
            self._FETCH_TIMEOUT,
            "fetch",
            "--depth",
            "1",
            cwd=str(repo_path),
        )

        local_head = self._rev_parse(repo_path, "HEAD")
        remote_head = self._rev_parse(repo_path, "FETCH_HEAD")

        if local_head and remote_head and local_head == remote_head:
            logger.info("Already up-to-date, skipping merge: %s", repo_path)
            return

        logger.info("New commits available, updating: %s", repo_path)
        # reset --hard is safe here because cached clones never carry
        # user modifications — this avoids the merge-driver overhead
        # that ``git pull`` would incur.
        self._run_git_checked(
            "reset",
            str(repo_path),
            self._RESET_TIMEOUT,
            "reset",
            "--hard",
            "FETCH_HEAD",
            cwd=str(repo_path),
        )

    def is_git_repo(self, path: Path) -> bool:
        """Return ``True`` when *path* contains a ``.git`` entry."""
        return is_git_repo(path)

    @staticmethod
    def _rev_parse(repo_path: Path, ref: str) -> str:
        """Resolve *ref* to a commit SHA inside *repo_path*.

        Returns an empty string when the ref cannot be resolved.
        """
        try:
            result = run_git(
                "rev-parse",
                ref,
                cwd=str(repo_path),
                timeout=SubprocessGitBackend._REV_PARSE_TIMEOUT,
            )
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            return ""
        if result.returncode != 0:
            return ""
        return result.stdout.strip()


# ---------------------------------------------------------------------------
# Module-level helper functions
# ---------------------------------------------------------------------------


def _is_git_url(value: str) -> bool:
    """Return ``True`` if *value* looks like a git remote URL.

    Recognised prefixes: ``http://``, ``https://``, ``git://``,
    ``git@``, ``ssh://``.
    """
    return any(value.lower().startswith(prefix) for prefix in _GIT_URL_PREFIXES)


def _repo_name_from_url(url: str) -> str:
    """Extract the repository name from a git URL.

    Handles HTTPS, SSH (``git@host:org/repo``), and ``ssh://`` forms
    by normalising the colon separator used in SSH-style URLs to a
    slash before splitting on the last segment.

    Examples::

        _repo_name_from_url("https://github.com/user/my-agents.git")
        # => "my-agents"

        _repo_name_from_url("git@github.com:user/my-agents.git")
        # => "my-agents"
    """
    # Strip query strings and fragments — they are illegal in Windows
    # directory names and must not leak into the repo basename.
    url = url.split("?")[0].split("#")[0]

    # Normalise SSH colon separator to slash, then take the last segment.
    cleaned = url.rstrip("/").strip().replace(":", "/")
    basename = cleaned.rsplit("/", 1)[-1]
    if basename.endswith(".git"):
        basename = basename[:-4]
    return basename or "unknown_repo"


def _count_source_dirs(path: Path) -> int:
    """Count how many recognised source subdirectories exist under *path*.

    Uses a single ``os.scandir`` call so that only one filesystem
    traversal is needed regardless of how many source-directory names
    are checked.
    """
    try:
        dir_names = {e.name for e in os.scandir(path) if e.is_dir()}
    except OSError:
        return 0
    return len(_SOURCE_DIR_NAMES & dir_names)


def _find_source_dir(start: Path) -> Path | None:
    """Walk *start* and its ancestors looking for an agentfiles source root.

    A directory qualifies when it contains **at least two** of the four
    recognised source subdirectories (``agents``, ``skills``,
    ``commands``, ``plugins``).

    Returns:
        The qualifying ancestor path, or ``None`` if none is found.

    """
    current = start.resolve()
    # Safety: don't walk past the filesystem root.
    # Require >= 2 matching dirs to reduce false positives — a single
    # coincidental "agents/" or "skills/" in an unrelated project is not enough.
    while True:
        if _count_source_dirs(current) >= 2:
            return current
        parent = current.parent
        if parent == current:
            return None
        current = parent


# ---------------------------------------------------------------------------
# SourceResolver
# ---------------------------------------------------------------------------


class SourceResolver:
    """Detect and resolve configuration sources to local filesystem paths.

    ``SourceResolver`` is the main entry-point for source handling.  It
    exposes two public methods that form a pipeline:

    1. :meth:`detect` — classify a user-supplied path string into a
       :class:`SourceInfo` (type, absolute path, git flag).
    2. :meth:`resolve` — translate that :class:`SourceInfo` into a concrete
       local directory, cloning or updating git URLs as needed.

    Args:
        git_backend: Backend for git operations (clone, pull, repo check).
            Defaults to :class:`SubprocessGitBackend` which shells out to
            the ``git`` binary.  Pass a mock or alternative implementation
            for testing or when git is unavailable.

    Usage — auto-detect from CWD::

        resolver = SourceResolver()
        info = resolver.detect()                    # walks up from CWD
        local_path = resolver.resolve(info)         # returns an absolute Path

    Usage — explicit local path::

        info = resolver.detect("/opt/my-project")
        local_path = resolver.resolve(info)

    Usage — remote git URL::

        info = resolver.detect("https://github.com/user/my-agents.git")
        local_path = resolver.resolve(info)         # clones into cache dir

    Usage — testing with a mock backend::

        from unittest.mock import MagicMock
        mock = MagicMock(spec=GitBackend, instance=True)
        resolver = SourceResolver(git_backend=mock)
        # … exercise detect / resolve without hitting the network

    """

    def __init__(self, git_backend: GitBackend | None = None) -> None:
        """Initialise the resolver with an optional git backend."""
        self._git: GitBackend = git_backend or SubprocessGitBackend()
        self._git_repo_cache: dict[Path, bool] = {}

    # -- public API ---------------------------------------------------------

    def detect(self, input_path: str | None = None) -> SourceInfo:
        """Analyse *input_path* and return a :class:`SourceInfo`.

        Detection strategy (in order):

        1. ``None`` — auto-detect by walking up from CWD looking for a
           directory with at least 2 of the 4 known source subdirs.
        2. Starts with a known git URL prefix → :data:`SourceType.GIT_URL`.
        3. Exists as a directory with ``.git`` → :data:`SourceType.GIT_DIR`.
        4. Exists as a plain directory → :data:`SourceType.LOCAL_DIR`.
        5. Exists as a file → :class:`SourceError`.
        6. Nothing matches → :class:`SourceError`.

        Args:
            input_path: User-supplied path string, or ``None`` for auto-detect.

        Returns:
            Fully populated :class:`SourceInfo`.

        Raises:
            SourceError: When the input cannot be classified or is invalid.

        """
        if input_path is None:
            return self._detect_auto()

        if _is_git_url(input_path):
            return SourceInfo(
                source_type=SourceType.GIT_URL,
                path=Path(input_path),
                original_input=input_path,
                is_git_repo=False,
            )

        candidate = Path(input_path).expanduser().resolve()

        # Single stat() call — avoids the redundant is_file()/is_dir()
        # pair which each trigger a separate syscall.
        try:
            st = candidate.stat()
        except FileNotFoundError:
            raise SourceError(
                f"cannot detect source: '{input_path}' does not exist on disk "
                f"and is not a recognised git URL"
            ) from None
        except PermissionError as exc:
            raise SourceError(
                f"cannot access source: '{input_path}'. "
                f"Permission denied — check directory ownership or run with appropriate privileges"
            ) from exc

        if not stat.S_ISDIR(st.st_mode):
            raise SourceError(
                f"expected a directory or git URL, got a file: '{input_path}'. "
                f"Provide a directory path or a git remote URL (https://, git@, ssh://)"
            )

        return self._classify_dir(candidate, original_input=input_path)

    def resolve(
        self,
        source_info: SourceInfo,
        cache_dir: Path | None = None,
    ) -> Path:
        """Resolve *source_info* to a concrete local directory path.

        - :data:`SourceType.LOCAL_DIR` / :data:`SourceType.GIT_DIR` —
          returned as-is (already absolute).
        - :data:`SourceType.GIT_URL` — cloned (shallow) into the cache
          directory; an existing clone is updated via ``git pull``.

        Args:
            source_info: The source to resolve.
            cache_dir: Root directory for cloning git URLs.  Defaults to
                ``~/.cache/agentfiles/repos``.

        Returns:
            Absolute path to the local directory containing the source.

        Raises:
            SourceError: When a git clone or pull fails.

        """
        if source_info.source_type in (SourceType.LOCAL_DIR, SourceType.GIT_DIR):
            logger.info("Source is local: %s", source_info.path)
            return source_info.path

        if source_info.source_type == SourceType.GIT_URL:
            return self._resolve_git_url(source_info, cache_dir)

        raise SourceError(
            f"internal error: unknown source type '{source_info.source_type}'. "
            f"This is likely a bug — please report it with the command that triggered it"
        )

    # -- private helpers ----------------------------------------------------

    def _detect_auto(self) -> SourceInfo:
        """Auto-detect source by walking up from CWD.

        Detection priority:

        1. If CWD contains ``.agentfiles.yaml`` / ``.agentfiles.yml``,
           treat CWD itself as the source root — unless CWD is the
           agentfiles *project* repository (detected by the presence
           of ``pyproject.toml`` with ``name = "agentfiles"``).
        2. Otherwise, walk upward from CWD looking for a directory
           with at least two recognised source subdirectories.
        """
        cwd = Path.cwd()

        # Check for local .agentfiles.yaml in CWD first.
        has_local_config = any((cwd / name).is_file() for name in _AGENTFILES_CONFIG_NAMES)
        if has_local_config:
            # Guard: skip if this is the agentfiles project repo itself.
            pyproject = cwd / "pyproject.toml"
            if not pyproject.is_file() or 'name = "agentfiles"' not in pyproject.read_text(
                errors="ignore"
            ):
                logger.info("Found local config in CWD: %s", cwd)
                return self._classify_dir(cwd, original_input="")

        found = _find_source_dir(cwd)

        if found is None:
            raise SourceError(
                "cannot auto-detect source from current directory. "
                "Navigate to a project with at least 2 of: "
                "agents/, skills/, commands/, plugins/ — or provide an explicit path"
            )

        return self._classify_dir(found, original_input="")

    def _classify_dir(self, path: Path, original_input: str) -> SourceInfo:
        """Classify a local directory as git or plain and build SourceInfo."""
        is_git = self._is_git_repo_cached(path)
        source_type = SourceType.GIT_DIR if is_git else SourceType.LOCAL_DIR
        logger.info("Detected %s at %s", source_type.value, path)
        return SourceInfo(
            source_type=source_type,
            path=path,
            original_input=original_input,
            is_git_repo=is_git,
        )

    def _resolve_git_url(
        self,
        source_info: SourceInfo,
        cache_dir: Path | None,
    ) -> Path:
        """Clone or update a git URL into the local cache."""
        url = source_info.original_input
        repo_name = _repo_name_from_url(url)
        cache = self._cache_root(cache_dir)
        target = (cache / repo_name).resolve()
        if not target.is_relative_to(cache.resolve()):
            raise SourceError(
                f"repository name '{repo_name}' derived from URL resolves "
                f"outside the cache directory '{cache}'. This can happen when "
                f"the URL contains path traversal components (e.g. '..'). "
                f"Use a clean git URL without '..' segments"
            )

        try:
            cache.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            hint = ""
            if exc.errno == 13:
                hint = " — permission denied, check directory ownership"
            elif exc.errno == 28 or "no space left" in str(exc).lower():
                hint = " — disk may be full, free up space and retry"
            raise SourceError(f"cannot create cache directory '{cache}': {exc}{hint}") from exc

        if target.exists() and self._is_git_repo_cached(target):
            logger.info("Updating existing clone: %s", target)
            self._git.pull(target)
            return target

        logger.info("Cloning %s into %s", url, target)
        self._git.clone(url, target)
        # Prime the cache — we just created a git repo.
        self._git_repo_cache[target.resolve()] = True
        return target

    def _is_git_repo_cached(self, path: Path) -> bool:
        """Check if *path* is a git repo, caching the result per instance."""
        resolved = path.resolve()
        if resolved not in self._git_repo_cache:
            self._git_repo_cache[resolved] = self._git.is_git_repo(resolved)
        return self._git_repo_cache[resolved]

    @staticmethod
    def _cache_root(cache_dir: Path | None) -> Path:
        """Return the resolved cache directory."""
        if cache_dir is not None:
            return cache_dir.expanduser().resolve()
        return _DEFAULT_CACHE_ROOT
