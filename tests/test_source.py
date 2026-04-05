"""Tests for agentfiles.source — source detection and resolution."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import ANY, MagicMock, patch

import pytest

from syncode.git import is_git_repo
from syncode.models import SourceError, SourceInfo, SourceType
from syncode.source import (
    GitBackend,
    SourceResolver,
    SubprocessGitBackend,
    _classify_git_stderr,
    _count_source_dirs,
    _find_source_dir,
    _git_error_from_file_not_found,
    _git_error_from_os_error,
    _git_error_from_timeout,
    _is_git_url,
    _repo_name_from_url,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_dir_with_subdirs(base: Path, subdirs: list[str]) -> Path:
    """Create *base* and the requested subdirectories inside it."""
    base.mkdir(parents=True, exist_ok=True)
    for sd in subdirs:
        (base / sd).mkdir()
    return base


# ---------------------------------------------------------------------------
# _is_git_url
# ---------------------------------------------------------------------------


class TestIsGitUrl:
    """Tests for the _is_git_url helper."""

    @pytest.mark.parametrize(
        "url",
        [
            "https://github.com/user/repo.git",
            "http://example.com/repo.git",
            "git://example.com/repo",
            "git@github.com:user/repo.git",
            "ssh://git@github.com/user/repo.git",
        ],
    )
    def test_should_return_true_for_recognised_prefixes(self, url: str) -> None:
        assert _is_git_url(url) is True

    @pytest.mark.parametrize(
        "value",
        [
            "/local/path",
            "~/relative/path",
            "../relative",
            "not-a-url",
            "ftp://example.com",
            "file:///some/path",
            "",
        ],
    )
    def test_should_return_false_for_non_git_values(self, value: str) -> None:
        assert _is_git_url(value) is False


# ---------------------------------------------------------------------------
# _repo_name_from_url
# ---------------------------------------------------------------------------


class TestRepoNameFromUrl:
    """Tests for the _repo_name_from_url helper."""

    @pytest.mark.parametrize(
        "url, expected",
        [
            ("https://github.com/user/my-agents.git", "my-agents"),
            ("git@github.com:user/my-agents.git", "my-agents"),
            ("https://github.com/user/repo", "repo"),
            ("git@github.com:user/repo", "repo"),
            ("ssh://git@github.com/user/repo.git", "repo"),
            ("http://example.com/a/b/c/my-repo.git/", "my-repo"),
            ("  https://github.com/user/repo.git  ", "repo"),
        ],
    )
    def test_should_extract_repo_name(self, url: str, expected: str) -> None:
        assert _repo_name_from_url(url) == expected

    def test_should_return_unknown_for_edge_case(self) -> None:
        # A URL that resolves to an empty basename after stripping.
        assert _repo_name_from_url("https://github.com/.git") == "unknown_repo"


# ---------------------------------------------------------------------------
# is_git_repo
# ---------------------------------------------------------------------------


class TestIsGitRepo:
    """Tests for the is_git_repo helper."""

    def test_should_return_true_when_git_dir_exists(self, tmp_path: Path) -> None:
        (tmp_path / ".git").mkdir()
        assert is_git_repo(tmp_path) is True

    def test_should_return_true_when_git_file_exists(self, tmp_path: Path) -> None:
        (tmp_path / ".git").write_text("gitdir: …")
        assert is_git_repo(tmp_path) is True

    def test_should_return_false_when_no_git(self, tmp_path: Path) -> None:
        assert is_git_repo(tmp_path) is False


# ---------------------------------------------------------------------------
# _count_source_dirs / _find_source_dir
# ---------------------------------------------------------------------------


class TestFindSourceDir:
    """Tests for _count_source_dirs and _find_source_dir."""

    def test_count_zero(self, tmp_path: Path) -> None:
        assert _count_source_dirs(tmp_path) == 0

    def test_count_two(self, tmp_path: Path) -> None:
        _make_dir_with_subdirs(tmp_path, ["agents", "skills"])
        assert _count_source_dirs(tmp_path) == 2

    def test_count_four(self, tmp_path: Path) -> None:
        _make_dir_with_subdirs(tmp_path, ["agents", "skills", "commands", "plugins"])
        assert _count_source_dirs(tmp_path) == 4

    def test_find_in_current(self, tmp_path: Path) -> None:
        _make_dir_with_subdirs(tmp_path, ["agents", "skills"])
        found = _find_source_dir(tmp_path)
        assert found is not None
        assert found == tmp_path.resolve()

    def test_find_in_parent(self, tmp_path: Path) -> None:
        root = _make_dir_with_subdirs(tmp_path / "project", ["agents", "skills"])
        child = root / "subdir" / "deep"
        child.mkdir(parents=True)
        found = _find_source_dir(child)
        assert found is not None
        assert found == root.resolve()

    def test_find_returns_none_when_not_found(self, tmp_path: Path) -> None:
        assert _find_source_dir(tmp_path) is None

    def test_find_returns_none_for_single_subdir(self, tmp_path: Path) -> None:
        _make_dir_with_subdirs(tmp_path, ["agents"])
        assert _find_source_dir(tmp_path) is None


# ---------------------------------------------------------------------------
# SourceInfo
# ---------------------------------------------------------------------------


class TestSourceInfo:
    """Tests for the SourceInfo data model."""

    def test_creation_and_properties(self) -> None:
        info = SourceInfo(
            source_type=SourceType.LOCAL_DIR,
            path=Path("/tmp/my-project"),
            original_input="/tmp/my-project",
            is_git_repo=False,
        )
        assert info.source_type == SourceType.LOCAL_DIR
        assert info.path == Path("/tmp/my-project")
        assert info.original_input == "/tmp/my-project"
        assert info.is_git_repo is False

    def test_frozen(self) -> None:
        info = SourceInfo(
            source_type=SourceType.GIT_URL,
            path=Path("/tmp/repo"),
            original_input="https://github.com/user/repo.git",
            is_git_repo=False,
        )
        with pytest.raises(AttributeError):
            info.source_type = SourceType.LOCAL_DIR  # type: ignore[misc]


# ---------------------------------------------------------------------------
# SourceResolver.detect
# ---------------------------------------------------------------------------


class TestSourceResolverDetect:
    """Tests for SourceResolver.detect()."""

    def test_detect_local_directory(self, tmp_path: Path) -> None:
        _make_dir_with_subdirs(tmp_path / "project", ["agents", "skills"])
        resolver = SourceResolver()
        info = resolver.detect(str(tmp_path / "project"))
        assert info.source_type == SourceType.LOCAL_DIR
        assert info.path == (tmp_path / "project").resolve()
        assert info.is_git_repo is False

    def test_detect_git_directory(self, tmp_path: Path) -> None:
        project = _make_dir_with_subdirs(tmp_path / "project", ["agents", "skills"])
        (project / ".git").mkdir()
        resolver = SourceResolver()
        info = resolver.detect(str(project))
        assert info.source_type == SourceType.GIT_DIR
        assert info.is_git_repo is True

    def test_detect_git_url(self) -> None:
        resolver = SourceResolver()
        info = resolver.detect("https://github.com/user/repo.git")
        assert info.source_type == SourceType.GIT_URL
        assert info.is_git_repo is False
        assert info.original_input == "https://github.com/user/repo.git"

    @pytest.mark.parametrize(
        "url",
        ["git@github.com:user/repo.git", "http://example.com/repo.git", "ssh://git@host/repo"],
    )
    def test_detect_various_git_url_prefixes(self, url: str) -> None:
        resolver = SourceResolver()
        info = resolver.detect(url)
        assert info.source_type == SourceType.GIT_URL

    def test_detect_auto_from_cwd(self, tmp_path: Path) -> None:
        project = _make_dir_with_subdirs(tmp_path / "project", ["agents", "commands"])
        with patch("syncode.source.Path.cwd", return_value=project):
            resolver = SourceResolver()
            info = resolver.detect()
        assert info.source_type == SourceType.LOCAL_DIR
        assert info.path == project.resolve()
        assert info.original_input == ""

    def test_detect_auto_with_git_repo(self, tmp_path: Path) -> None:
        project = _make_dir_with_subdirs(tmp_path / "project", ["skills", "plugins"])
        (project / ".git").mkdir()
        with patch("syncode.source.Path.cwd", return_value=project):
            resolver = SourceResolver()
            info = resolver.detect()
        assert info.source_type == SourceType.GIT_DIR
        assert info.is_git_repo is True

    def test_detect_auto_raises_when_no_source_found(self, tmp_path: Path) -> None:
        empty = tmp_path / "empty"
        empty.mkdir()
        with patch("syncode.source.Path.cwd", return_value=empty):
            resolver = SourceResolver()
            with pytest.raises(SourceError, match="cannot auto-detect"):
                resolver.detect()

    def test_detect_raises_for_file_input(self, tmp_path: Path) -> None:
        file_path = tmp_path / "file.md"
        file_path.write_text("content")
        resolver = SourceResolver()
        with pytest.raises(SourceError, match="expected a directory"):
            resolver.detect(str(file_path))

    def test_detect_raises_for_nonexistent_path(self) -> None:
        resolver = SourceResolver()
        with pytest.raises(SourceError, match="does not exist"):
            resolver.detect("/nonexistent/path/that/does/not/exist")

    def test_detect_expands_tilde(self, tmp_path: Path) -> None:
        """Ensure that a ``~/...`` path gets expanded."""
        tmp_path.mkdir(exist_ok=True)
        with patch("syncode.source.Path.expanduser", return_value=tmp_path.resolve()):
            resolver = SourceResolver()
            info = resolver.detect("~/some/path")
            assert info.source_type in (SourceType.LOCAL_DIR, SourceType.GIT_DIR)


# ---------------------------------------------------------------------------
# SourceResolver.resolve
# ---------------------------------------------------------------------------


class TestSourceResolverResolve:
    """Tests for SourceResolver.resolve()."""

    def test_resolve_local_dir(self, tmp_path: Path) -> None:
        project = _make_dir_with_subdirs(tmp_path / "project", ["agents", "skills"])
        info = SourceInfo(
            source_type=SourceType.LOCAL_DIR,
            path=project.resolve(),
            original_input=str(project),
            is_git_repo=False,
        )
        resolver = SourceResolver()
        result = resolver.resolve(info)
        assert result == project.resolve()

    def test_resolve_git_dir(self, tmp_path: Path) -> None:
        project = _make_dir_with_subdirs(tmp_path / "project", ["agents", "skills"])
        (project / ".git").mkdir()
        info = SourceInfo(
            source_type=SourceType.GIT_DIR,
            path=project.resolve(),
            original_input=str(project),
            is_git_repo=True,
        )
        resolver = SourceResolver()
        result = resolver.resolve(info)
        assert result == project.resolve()

    def test_resolve_git_url_clones(self, tmp_path: Path) -> None:
        """Git URL should trigger clone into cache dir."""
        info = SourceInfo(
            source_type=SourceType.GIT_URL,
            path=Path("https://github.com/user/repo.git"),
            original_input="https://github.com/user/repo.git",
            is_git_repo=False,
        )
        mock_git = MagicMock(spec=GitBackend, instance=True)
        mock_git.is_git_repo.return_value = False
        resolver = SourceResolver(git_backend=mock_git)
        cache = tmp_path / "cache"

        result = resolver.resolve(info, cache_dir=cache)

        assert result == (cache / "repo").resolve()
        mock_git.clone.assert_called_once_with(
            "https://github.com/user/repo.git",
            result,
        )
        # is_git_repo is not called because target doesn't exist on disk
        # (short-circuit: `target.exists() and self._git.is_git_repo(target)`).
        mock_git.is_git_repo.assert_not_called()

    def test_resolve_git_url_updates_existing(self, tmp_path: Path) -> None:
        """Existing clone should trigger git pull instead of clone."""
        cache = tmp_path / "cache"
        repo_dir = cache / "repo"
        repo_dir.mkdir(parents=True)
        (repo_dir / ".git").mkdir()

        info = SourceInfo(
            source_type=SourceType.GIT_URL,
            path=Path("https://github.com/user/repo.git"),
            original_input="https://github.com/user/repo.git",
            is_git_repo=False,
        )
        mock_git = MagicMock(spec=GitBackend, instance=True)
        mock_git.is_git_repo.return_value = True
        resolver = SourceResolver(git_backend=mock_git)

        result = resolver.resolve(info, cache_dir=cache)

        assert result == repo_dir.resolve()
        mock_git.pull.assert_called_once_with(repo_dir.resolve())
        mock_git.clone.assert_not_called()

    def test_resolve_git_url_clone_failure(self, tmp_path: Path) -> None:
        """Clone failure should raise SourceError."""
        info = SourceInfo(
            source_type=SourceType.GIT_URL,
            path=Path("https://github.com/user/repo.git"),
            original_input="https://github.com/user/repo.git",
            is_git_repo=False,
        )
        mock_git = MagicMock(spec=GitBackend, instance=True)
        mock_git.is_git_repo.return_value = False
        mock_git.clone.side_effect = SourceError("git clone failed (exit 128): fatal")
        resolver = SourceResolver(git_backend=mock_git)
        cache = tmp_path / "cache"

        with pytest.raises(SourceError, match="git clone failed"):
            resolver.resolve(info, cache_dir=cache)

    def test_resolve_git_url_pull_failure(self, tmp_path: Path) -> None:
        """Pull failure on existing clone should raise SourceError."""
        cache = tmp_path / "cache"
        repo_dir = cache / "repo"
        repo_dir.mkdir(parents=True)
        (repo_dir / ".git").mkdir()

        info = SourceInfo(
            source_type=SourceType.GIT_URL,
            path=Path("https://github.com/user/repo.git"),
            original_input="https://github.com/user/repo.git",
            is_git_repo=False,
        )
        mock_git = MagicMock(spec=GitBackend, instance=True)
        mock_git.is_git_repo.return_value = True
        mock_git.pull.side_effect = SourceError("git pull failed (exit 1): merge conflict")
        resolver = SourceResolver(git_backend=mock_git)

        with pytest.raises(SourceError, match="git pull failed"):
            resolver.resolve(info, cache_dir=cache)

    def test_resolve_git_url_path_traversal_rejected(self, tmp_path: Path) -> None:
        """A repo name that resolves outside cache dir should be rejected."""
        info = SourceInfo(
            source_type=SourceType.GIT_URL,
            path=Path("https://github.com/user/repo.git"),
            original_input="https://github.com/user/repo.git",
            is_git_repo=False,
        )
        resolver = SourceResolver()
        cache = tmp_path / "cache"
        # Inject a malicious repo name that resolves outside cache via symlink-style traversal.
        with (
            patch("syncode.source._repo_name_from_url", return_value="../../../etc/evil"),
            pytest.raises(SourceError, match="resolves outside the cache"),
        ):
            resolver.resolve(info, cache_dir=cache)

    def test_resolve_default_cache_root(self) -> None:
        """When no cache_dir is given, the default should be used."""
        info = SourceInfo(
            source_type=SourceType.LOCAL_DIR,
            path=Path("/some/dir"),
            original_input="/some/dir",
            is_git_repo=False,
        )
        resolver = SourceResolver()
        # Local dir doesn't need cache — just verify it doesn't crash.
        # We can't easily test the default path without mocking Path.home().
        result = resolver.resolve(info)
        assert result == Path("/some/dir")


# ---------------------------------------------------------------------------
# SourceResolver._cache_root
# ---------------------------------------------------------------------------


class TestCacheRoot:
    """Tests for the _cache_root static method."""

    def test_uses_provided_cache_dir(self, tmp_path: Path) -> None:
        result = SourceResolver._cache_root(tmp_path)
        assert result == tmp_path.resolve()

    def test_uses_default_when_none(self, tmp_path: Path) -> None:
        """When no cache_dir is given, the module-level default is returned."""
        expected = tmp_path / ".cache" / "agentfiles" / "repos"
        with patch("syncode.source._DEFAULT_CACHE_ROOT", expected):
            result = SourceResolver._cache_root(None)
        assert result == expected

    def test_expands_user(self, tmp_path: Path) -> None:
        tilde_path = Path("~/my-cache")
        with patch("syncode.source.Path.expanduser", return_value=tmp_path):
            result = SourceResolver._cache_root(tilde_path)
        assert result == tmp_path.resolve()


# ---------------------------------------------------------------------------
# GitBackend protocol & SubprocessGitBackend
# ---------------------------------------------------------------------------


class TestGitBackendProtocol:
    """Tests for the GitBackend protocol and SubprocessGitBackend."""

    def test_subprocess_backend_satisfies_protocol(self) -> None:
        """SubprocessGitBackend should implement the GitBackend protocol."""
        backend = SubprocessGitBackend()
        assert isinstance(backend, GitBackend)

    def test_mock_satisfies_protocol(self) -> None:
        """A MagicMock with the right spec should satisfy GitBackend."""
        mock = MagicMock(spec=GitBackend, instance=True)
        assert isinstance(mock, GitBackend)

    def test_default_backend_used_when_none(self) -> None:
        """SourceResolver defaults to SubprocessGitBackend."""
        resolver = SourceResolver()
        assert isinstance(resolver._git, SubprocessGitBackend)

    def test_custom_backend_injected(self) -> None:
        """SourceResolver uses an injected custom backend."""
        mock = MagicMock(spec=GitBackend, instance=True)
        resolver = SourceResolver(git_backend=mock)
        assert resolver._git is mock

    def test_detect_uses_backend_is_git_repo(self, tmp_path: Path) -> None:
        """detect() should delegate is_git_repo to the injected backend."""
        project = _make_dir_with_subdirs(tmp_path / "project", ["agents", "skills"])
        mock_git = MagicMock(spec=GitBackend, instance=True)
        mock_git.is_git_repo.return_value = True
        resolver = SourceResolver(git_backend=mock_git)

        info = resolver.detect(str(project))

        assert info.source_type == SourceType.GIT_DIR
        assert info.is_git_repo is True
        mock_git.is_git_repo.assert_called_once_with(project.resolve())

    def test_detect_auto_uses_backend(self, tmp_path: Path) -> None:
        """Auto-detect should delegate is_git_repo to the injected backend."""
        project = _make_dir_with_subdirs(tmp_path / "project", ["agents", "commands"])
        mock_git = MagicMock(spec=GitBackend, instance=True)
        mock_git.is_git_repo.return_value = False
        resolver = SourceResolver(git_backend=mock_git)

        with patch("syncode.source.Path.cwd", return_value=project):
            info = resolver.detect()

        assert info.source_type == SourceType.LOCAL_DIR
        assert info.is_git_repo is False
        mock_git.is_git_repo.assert_called_once_with(project.resolve())

    def test_subprocess_backend_clone_success(self, tmp_path: Path) -> None:
        """SubprocessGitBackend.clone delegates to run_git."""
        target = tmp_path / "repo"
        mock_result = MagicMock(spec=subprocess.CompletedProcess)
        mock_result.returncode = 0
        mock_result.stderr = ""

        with patch("syncode.source.run_git", return_value=mock_result) as mock_git:
            backend = SubprocessGitBackend()
            backend.clone("https://example.com/repo.git", target)

        mock_git.assert_called_once_with(
            "clone",
            "--depth",
            "1",
            "https://example.com/repo.git",
            str(target),
            cwd=None,
            timeout=ANY,
        )

    def test_subprocess_backend_clone_failure(self, tmp_path: Path) -> None:
        """SubprocessGitBackend.clone raises SourceError on failure."""
        target = tmp_path / "repo"
        mock_result = MagicMock(spec=subprocess.CompletedProcess)
        mock_result.returncode = 128
        mock_result.stderr = "fatal: not found"

        with patch("syncode.source.run_git", return_value=mock_result):
            backend = SubprocessGitBackend()
            with pytest.raises(SourceError, match="git clone failed"):
                backend.clone("https://example.com/repo.git", target)

    def test_subprocess_backend_pull_success(self, tmp_path: Path) -> None:
        """SubprocessGitBackend.pull fetches and skips merge when up-to-date."""
        mock_fetch = MagicMock(spec=subprocess.CompletedProcess)
        mock_fetch.returncode = 0
        mock_fetch.stderr = ""

        mock_head = MagicMock(spec=subprocess.CompletedProcess)
        mock_head.returncode = 0
        mock_head.stdout = "abc123def456"

        mock_fetch_head = MagicMock(spec=subprocess.CompletedProcess)
        mock_fetch_head.returncode = 0
        mock_fetch_head.stdout = "abc123def456"

        with patch(
            "syncode.source.run_git", side_effect=[mock_fetch, mock_head, mock_fetch_head]
        ) as mock_git:
            backend = SubprocessGitBackend()
            backend.pull(tmp_path)

        assert mock_git.call_count == 3
        mock_git.assert_any_call("fetch", "--depth", "1", cwd=str(tmp_path), timeout=ANY)
        mock_git.assert_any_call("rev-parse", "HEAD", cwd=str(tmp_path), timeout=ANY)
        mock_git.assert_any_call("rev-parse", "FETCH_HEAD", cwd=str(tmp_path), timeout=ANY)

    def test_subprocess_backend_pull_with_new_commits(self, tmp_path: Path) -> None:
        """SubprocessGitBackend.pull resets when new commits are available."""
        mock_fetch = MagicMock(spec=subprocess.CompletedProcess)
        mock_fetch.returncode = 0
        mock_fetch.stderr = ""

        mock_head = MagicMock(spec=subprocess.CompletedProcess)
        mock_head.returncode = 0
        mock_head.stdout = "aaa111"

        mock_fetch_head = MagicMock(spec=subprocess.CompletedProcess)
        mock_fetch_head.returncode = 0
        mock_fetch_head.stdout = "bbb222"

        mock_reset = MagicMock(spec=subprocess.CompletedProcess)
        mock_reset.returncode = 0
        mock_reset.stderr = ""

        with patch(
            "syncode.source.run_git",
            side_effect=[mock_fetch, mock_head, mock_fetch_head, mock_reset],
        ) as mock_git:
            backend = SubprocessGitBackend()
            backend.pull(tmp_path)

        assert mock_git.call_count == 4
        mock_git.assert_any_call("reset", "--hard", "FETCH_HEAD", cwd=str(tmp_path), timeout=ANY)

    def test_subprocess_backend_pull_failure(self, tmp_path: Path) -> None:
        """SubprocessGitBackend.pull raises SourceError on fetch failure."""
        mock_result = MagicMock(spec=subprocess.CompletedProcess)
        mock_result.returncode = 1
        mock_result.stderr = "network error"

        with patch("syncode.source.run_git", return_value=mock_result):
            backend = SubprocessGitBackend()
            with pytest.raises(SourceError, match="git fetch failed"):
                backend.pull(tmp_path)

    def test_subprocess_backend_pull_reset_failure(self, tmp_path: Path) -> None:
        """SubprocessGitBackend.pull raises SourceError on reset failure."""
        mock_fetch = MagicMock(spec=subprocess.CompletedProcess)
        mock_fetch.returncode = 0
        mock_fetch.stderr = ""

        mock_head = MagicMock(spec=subprocess.CompletedProcess)
        mock_head.returncode = 0
        mock_head.stdout = "aaa"

        mock_fetch_head = MagicMock(spec=subprocess.CompletedProcess)
        mock_fetch_head.returncode = 0
        mock_fetch_head.stdout = "bbb"

        mock_reset = MagicMock(spec=subprocess.CompletedProcess)
        mock_reset.returncode = 1
        mock_reset.stderr = "reset error"

        with patch(
            "syncode.source.run_git",
            side_effect=[mock_fetch, mock_head, mock_fetch_head, mock_reset],
        ):
            backend = SubprocessGitBackend()
            with pytest.raises(SourceError, match="git reset failed"):
                backend.pull(tmp_path)


# ---------------------------------------------------------------------------
# _rev_parse helper
# ---------------------------------------------------------------------------


class TestRevParse:
    """Tests for SubprocessGitBackend._rev_parse."""

    def test_returns_sha_on_success(self, tmp_path: Path) -> None:
        mock_result = MagicMock(spec=subprocess.CompletedProcess)
        mock_result.returncode = 0
        mock_result.stdout = "abc123\n"

        with patch("syncode.source.run_git", return_value=mock_result):
            sha = SubprocessGitBackend._rev_parse(tmp_path, "HEAD")

        assert sha == "abc123"

    def test_returns_empty_on_failure(self, tmp_path: Path) -> None:
        mock_result = MagicMock(spec=subprocess.CompletedProcess)
        mock_result.returncode = 128
        mock_result.stdout = ""

        with patch("syncode.source.run_git", return_value=mock_result):
            sha = SubprocessGitBackend._rev_parse(tmp_path, "HEAD")

        assert sha == ""


# ---------------------------------------------------------------------------
# SourceResolver — git repo detection cache
# ---------------------------------------------------------------------------


class TestGitRepoCache:
    """Tests for SourceResolver's is_git_repo caching."""

    def test_cache_avoids_redundant_calls(self, tmp_path: Path) -> None:
        """is_git_repo should be called only once per unique path."""
        project = _make_dir_with_subdirs(tmp_path / "project", ["agents", "skills"])
        mock_git = MagicMock(spec=GitBackend, instance=True)
        mock_git.is_git_repo.return_value = True
        resolver = SourceResolver(git_backend=mock_git)

        # detect() calls _classify_dir which calls _is_git_repo_cached
        resolver.detect(str(project))
        # resolve() for GIT_DIR doesn't call is_git_repo again
        info = SourceInfo(
            source_type=SourceType.GIT_DIR,
            path=project.resolve(),
            original_input=str(project),
            is_git_repo=True,
        )
        resolver.resolve(info)

        # is_git_repo should be called only once (during detect)
        mock_git.is_git_repo.assert_called_once_with(project.resolve())

    def test_cache_primed_after_clone(self, tmp_path: Path) -> None:
        """After cloning, the cache should be primed for the target path."""
        info = SourceInfo(
            source_type=SourceType.GIT_URL,
            path=Path("https://github.com/user/repo.git"),
            original_input="https://github.com/user/repo.git",
            is_git_repo=False,
        )
        mock_git = MagicMock(spec=GitBackend, instance=True)
        mock_git.is_git_repo.return_value = False
        resolver = SourceResolver(git_backend=mock_git)
        cache = tmp_path / "cache"

        resolver.resolve(info, cache_dir=cache)

        target = (cache / "repo").resolve()
        assert target.resolve() in resolver._git_repo_cache
        assert resolver._git_repo_cache[target.resolve()] is True

    def test_detect_permission_error(self, tmp_path: Path) -> None:
        """detect() should raise SourceError when stat() fails with PermissionError."""
        resolver = SourceResolver()
        with (
            patch.object(Path, "stat", side_effect=PermissionError("denied")),
            pytest.raises(SourceError, match="cannot access source"),
        ):
            resolver.detect("/some/path")


# ---------------------------------------------------------------------------
# _classify_git_stderr — error pattern matching
# ---------------------------------------------------------------------------


class TestClassifyGitStderr:
    """Tests for _classify_git_stderr hint extraction."""

    @pytest.mark.parametrize(
        "stderr",
        [
            "fatal: could not read Username for 'https://github.com'",
            "Authentication failed for 'https://github.com/user/repo.git/'",
            "Permission denied (publickey).",
            "fatal: Could not read from remote repository.",
        ],
    )
    def test_returns_auth_hint(self, stderr: str) -> None:
        hint = _classify_git_stderr(stderr)
        assert hint is not None
        assert "credentials" in hint.lower() or "permissions" in hint.lower()

    @pytest.mark.parametrize(
        "stderr",
        [
            "fatal: repository not found",
            "fatal: not found",
        ],
    )
    def test_returns_repo_not_found_hint(self, stderr: str) -> None:
        hint = _classify_git_stderr(stderr)
        assert hint is not None
        assert "verify" in hint.lower() or "url" in hint.lower()

    @pytest.mark.parametrize(
        "stderr",
        [
            "fatal: unable to access 'https://github.com/': Could not resolve host",
            "fatal: unable to access 'url': Connection refused",
            "fatal: network is unreachable",
            "fatal: failed to connect to github.com",
        ],
    )
    def test_returns_network_hint(self, stderr: str) -> None:
        hint = _classify_git_stderr(stderr)
        assert hint is not None
        assert "network" in hint.lower()

    def test_returns_disk_space_hint(self) -> None:
        hint = _classify_git_stderr("fatal: write error: No space left on device")
        assert hint is not None
        assert "disk" in hint.lower() or "space" in hint.lower()

    def test_returns_existing_dir_hint(self) -> None:
        hint = _classify_git_stderr(
            "fatal: destination path 'repo' already exists and is not an empty directory"
        )
        assert hint is not None
        assert "already exists" in hint.lower()

    def test_returns_none_for_unknown_error(self) -> None:
        assert _classify_git_stderr("some random error message") is None

    def test_returns_none_for_empty_string(self) -> None:
        assert _classify_git_stderr("") is None


# ---------------------------------------------------------------------------
# _git_error_from_* — error builder functions
# ---------------------------------------------------------------------------


class TestGitErrorBuilders:
    """Tests for the _git_error_from_* helper functions."""

    def test_timeout_error_message(self) -> None:
        err = _git_error_from_timeout("clone", "https://example.com/repo", 120)
        assert isinstance(err, SourceError)
        msg = str(err)
        assert "timed out" in msg
        assert "120s" in msg
        assert "clone" in msg
        assert "network" in msg.lower()

    def test_file_not_found_error_message(self) -> None:
        err = _git_error_from_file_not_found("clone", "https://example.com/repo")
        assert isinstance(err, SourceError)
        msg = str(err)
        assert "git" in msg
        assert "not found" in msg
        assert "install" in msg.lower()

    def test_os_error_generic(self) -> None:
        exc = OSError("something broke")
        err = _git_error_from_os_error("clone", "https://example.com/repo", exc)
        assert isinstance(err, SourceError)
        msg = str(err)
        assert "something broke" in msg

    def test_os_error_disk_full(self) -> None:
        exc = OSError(28, "No space left on device")
        err = _git_error_from_os_error("clone", "https://example.com/repo", exc)
        msg = str(err)
        assert "disk" in msg.lower() or "space" in msg.lower()

    def test_os_error_permission(self) -> None:
        exc = OSError(13, "Permission denied")
        err = _git_error_from_os_error("clone", "https://example.com/repo", exc)
        msg = str(err)
        assert "permission" in msg.lower()


# ---------------------------------------------------------------------------
# SubprocessGitBackend — timeout / git-not-installed handling
# ---------------------------------------------------------------------------


class TestSubprocessGitBackendExceptionHandling:
    """Tests for exception handling in SubprocessGitBackend."""

    @pytest.mark.parametrize(
        ("side_effect", "match"),
        [
            (subprocess.TimeoutExpired(cmd=["git"], timeout=120), "timed out"),
            (FileNotFoundError("git not found"), "not found"),
            (OSError("disk full"), "disk full"),
        ],
        ids=["timeout", "git-not-installed", "os-error"],
    )
    def test_clone_exception_raises_source_error(
        self,
        tmp_path: Path,
        side_effect: Exception,
        match: str,
    ) -> None:
        """clone() should raise SourceError for various subprocess failures."""
        with patch("syncode.source.run_git", side_effect=side_effect):
            backend = SubprocessGitBackend()
            with pytest.raises(SourceError, match=match):
                backend.clone("https://example.com/repo.git", tmp_path / "repo")

    @pytest.mark.parametrize(
        ("side_effect", "match"),
        [
            (subprocess.TimeoutExpired(cmd=["git"], timeout=120), "timed out"),
            (FileNotFoundError("git"), "not found"),
            (OSError(28, "No space left on device"), "space"),
        ],
        ids=["timeout", "git-not-installed", "os-error"],
    )
    def test_pull_exception_raises_source_error(
        self,
        tmp_path: Path,
        side_effect: Exception,
        match: str,
    ) -> None:
        """pull() should raise SourceError for various subprocess failures."""
        with patch("syncode.source.run_git", side_effect=side_effect):
            backend = SubprocessGitBackend()
            with pytest.raises(SourceError, match=match):
                backend.pull(tmp_path)

    def test_pull_reset_timeout_raises_source_error(self, tmp_path: Path) -> None:
        """pull() should raise SourceError on reset timeout."""
        mock_fetch = MagicMock(spec=subprocess.CompletedProcess)
        mock_fetch.returncode = 0
        mock_fetch.stderr = ""

        mock_head = MagicMock(spec=subprocess.CompletedProcess)
        mock_head.returncode = 0
        mock_head.stdout = "aaa"

        mock_fetch_head = MagicMock(spec=subprocess.CompletedProcess)
        mock_fetch_head.returncode = 0
        mock_fetch_head.stdout = "bbb"

        with patch(
            "syncode.source.run_git",
            side_effect=[
                mock_fetch,
                mock_head,
                mock_fetch_head,
                subprocess.TimeoutExpired(cmd=["git"], timeout=30),
            ],
        ):
            backend = SubprocessGitBackend()
            with pytest.raises(SourceError, match="timed out"):
                backend.pull(tmp_path)

    def test_clone_auth_failure_hint(self, tmp_path: Path) -> None:
        """clone() should include actionable hint for auth failures."""
        mock_result = MagicMock(spec=subprocess.CompletedProcess)
        mock_result.returncode = 128
        mock_result.stderr = "fatal: could not read Username for 'https://github.com'"

        with patch("syncode.source.run_git", return_value=mock_result):
            backend = SubprocessGitBackend()
            with pytest.raises(SourceError, match="credentials|permissions") as exc_info:
                backend.clone("https://github.com/private/repo.git", tmp_path / "repo")
            assert "→" in str(exc_info.value)

    def test_clone_network_failure_hint(self, tmp_path: Path) -> None:
        """clone() should include actionable hint for network failures."""
        mock_result = MagicMock(spec=subprocess.CompletedProcess)
        mock_result.returncode = 128
        mock_result.stderr = "fatal: unable to access 'https://github.com/': Could not resolve host"

        with patch("syncode.source.run_git", return_value=mock_result):
            backend = SubprocessGitBackend()
            with pytest.raises(SourceError, match="network") as exc_info:
                backend.clone("https://github.com/user/repo.git", tmp_path / "repo")
            assert "→" in str(exc_info.value)

    def test_clone_no_hint_for_unknown_error(self, tmp_path: Path) -> None:
        """clone() should not include hint arrow for unknown errors."""
        mock_result = MagicMock(spec=subprocess.CompletedProcess)
        mock_result.returncode = 1
        mock_result.stderr = "some unknown error"

        with patch("syncode.source.run_git", return_value=mock_result):
            backend = SubprocessGitBackend()
            with pytest.raises(SourceError, match="git clone failed") as exc_info:
                backend.clone("https://example.com/repo.git", tmp_path / "repo")
            assert "→" not in str(exc_info.value)

    def test_pull_fetch_with_auth_hint(self, tmp_path: Path) -> None:
        """pull() fetch failure should include auth hint."""
        mock_result = MagicMock(spec=subprocess.CompletedProcess)
        mock_result.returncode = 128
        mock_result.stderr = "Permission denied (publickey)."

        with patch("syncode.source.run_git", return_value=mock_result):
            backend = SubprocessGitBackend()
            with pytest.raises(SourceError, match="credentials|permissions") as exc_info:
                backend.pull(tmp_path)
            assert "→" in str(exc_info.value)


# ---------------------------------------------------------------------------
# SourceResolver._resolve_git_url — cache mkdir error handling
# ---------------------------------------------------------------------------


class TestResolveGitUrlCacheErrors:
    """Tests for cache directory creation failure handling."""

    def test_cache_mkdir_permission_error(self, tmp_path: Path) -> None:
        """Permission denied during cache dir creation should raise SourceError."""
        info = SourceInfo(
            source_type=SourceType.GIT_URL,
            path=Path("https://github.com/user/repo.git"),
            original_input="https://github.com/user/repo.git",
            is_git_repo=False,
        )
        resolver = SourceResolver()
        cache = tmp_path / "cache"

        with patch.object(Path, "mkdir", side_effect=OSError(13, "Permission denied")):
            with pytest.raises(SourceError, match="permission") as exc_info:
                resolver.resolve(info, cache_dir=cache)
            assert "cache directory" in str(exc_info.value)

    def test_cache_mkdir_disk_full_error(self, tmp_path: Path) -> None:
        """Disk full during cache dir creation should raise SourceError."""
        info = SourceInfo(
            source_type=SourceType.GIT_URL,
            path=Path("https://github.com/user/repo.git"),
            original_input="https://github.com/user/repo.git",
            is_git_repo=False,
        )
        resolver = SourceResolver()
        cache = tmp_path / "cache"

        with patch.object(Path, "mkdir", side_effect=OSError(28, "No space left on device")):
            with pytest.raises(SourceError, match="space") as exc_info:
                resolver.resolve(info, cache_dir=cache)
            assert "cache directory" in str(exc_info.value)

    def test_cache_mkdir_generic_os_error(self, tmp_path: Path) -> None:
        """Generic OSError during cache dir creation should raise SourceError."""
        info = SourceInfo(
            source_type=SourceType.GIT_URL,
            path=Path("https://github.com/user/repo.git"),
            original_input="https://github.com/user/repo.git",
            is_git_repo=False,
        )
        resolver = SourceResolver()
        cache = tmp_path / "cache"

        with patch.object(Path, "mkdir", side_effect=OSError("read-only filesystem")):
            with pytest.raises(SourceError, match="cache directory") as exc_info:
                resolver.resolve(info, cache_dir=cache)
            assert "read-only filesystem" in str(exc_info.value)


# ---------------------------------------------------------------------------
# URL parsing edge cases — GitLab, Bitbucket, SSH with ports, nested paths
# ---------------------------------------------------------------------------


class TestUrlParsingEdgeCases:
    """Extended tests for _is_git_url and _repo_name_from_url."""

    # -- _is_git_url: GitLab / Bitbucket / custom hosts ----------------------

    @pytest.mark.parametrize(
        "url",
        [
            "https://gitlab.com/user/repo.git",
            "https://gitlab.com/org/subgroup/repo.git",
            "https://bitbucket.org/team/project.git",
            "https://dev.azure.com/org/project/_git/repo",
        ],
    )
    def test_is_git_url_various_https_hosts(self, url: str) -> None:
        assert _is_git_url(url) is True

    def test_is_git_url_ssh_with_port(self) -> None:
        """SSH URL with explicit port should be recognised."""
        assert _is_git_url("ssh://git@github.com:22/user/repo.git") is True

    @pytest.mark.parametrize(
        "value",
        [
            "HTTPS://github.com/user/repo.git",
            "Git@github.com:user/repo.git",
        ],
    )
    def test_is_git_url_case_insensitive_scheme(self, value: str) -> None:
        """Uppercase or mixed-case schemes should still be recognised."""
        assert _is_git_url(value) is True

    def test_is_git_url_leading_whitespace_not_recognised(self) -> None:
        """Leading whitespace should cause a mismatch — not a valid URL."""
        assert _is_git_url("  https://github.com/user/repo.git") is False

    # -- _repo_name_from_url: GitLab subgroups / Bitbucket / nested paths ----

    @pytest.mark.parametrize(
        "url, expected",
        [
            ("https://gitlab.com/org/subgroup/repo.git", "repo"),
            ("https://gitlab.com/org/subgroup/deep/repo.git", "repo"),
            ("https://bitbucket.org/team/project.git", "project"),
            ("ssh://git@gitlab.com/org/subgroup/repo.git", "repo"),
            ("git@gitlab.com:org/subgroup/repo.git", "repo"),
            ("https://dev.azure.com/org/proj/_git/repo", "repo"),
        ],
    )
    def test_repo_name_from_various_hosts(self, url: str, expected: str) -> None:
        assert _repo_name_from_url(url) == expected

    def test_repo_name_ssh_with_port(self) -> None:
        """SSH URL containing port number in path should extract repo name."""
        assert _repo_name_from_url("ssh://git@github.com:22/user/repo.git") == "repo"

    @pytest.mark.parametrize(
        "url, expected",
        [
            ("https://github.com/user/repo.git/", "repo"),
            ("https://github.com/user/repo.git///", "repo"),
            ("git@github.com:user/repo.git/", "repo"),
        ],
    )
    def test_repo_name_trailing_slashes(self, url: str, expected: str) -> None:
        """All trailing slashes should be stripped before extraction."""
        assert _repo_name_from_url(url) == expected

    def test_repo_name_url_with_only_domain_and_git(self) -> None:
        """A URL like 'https://example.com/.git' resolves to unknown_repo."""
        assert _repo_name_from_url("https://example.com/.git") == "unknown_repo"

    def test_repo_name_url_without_git_extension(self) -> None:
        """URLs without .git should still extract the basename."""
        assert _repo_name_from_url("https://github.com/user/my-project") == "my-project"

    @pytest.mark.parametrize(
        "url",
        [
            "https://github.com/user/repo.git?ref=main",
            "https://github.com/user/repo.git#v1.0",
        ],
    )
    def test_repo_name_with_query_or_fragment(self, url: str) -> None:
        """Query strings and fragments should be stripped before extraction."""
        result = _repo_name_from_url(url)
        assert result == "repo"


# ---------------------------------------------------------------------------
# _count_source_dirs / _find_source_dir — edge cases
# ---------------------------------------------------------------------------


class TestCountAndFindSourceDirEdgeCases:
    """Extended tests for filesystem-based source detection helpers."""

    def test_count_source_dirs_oserror_returns_zero(self, tmp_path: Path) -> None:
        """OSError during scandir should be silently handled as 0."""
        with patch("syncode.source.os.scandir", side_effect=OSError("permission denied")):
            assert _count_source_dirs(tmp_path) == 0

    def test_count_source_dirs_mixed_dirs(self, tmp_path: Path) -> None:
        """Only recognised source dirs should be counted, not random dirs."""
        _make_dir_with_subdirs(tmp_path, ["agents", "random_dir", "skills", "docs"])
        assert _count_source_dirs(tmp_path) == 2

    def test_count_source_dirs_files_not_dirs(self, tmp_path: Path) -> None:
        """Files with source-dir names should not be counted."""
        tmp_path.mkdir(parents=True, exist_ok=True)
        (tmp_path / "agents").write_text("I am a file, not a directory")
        assert _count_source_dirs(tmp_path) == 0

    def test_find_source_dir_stops_at_root(self, tmp_path: Path) -> None:
        """_find_source_dir should not loop infinitely walking upwards."""
        # Walk from a deeply nested directory with no source dirs anywhere.
        deep = tmp_path / "a" / "b" / "c" / "d"
        deep.mkdir(parents=True)
        # The walk will stop at filesystem root; just ensure it returns None
        # without hanging or raising.
        result = _find_source_dir(deep)
        # Depending on system root contents this may or may not find something,
        # but it must complete and return a Path or None.
        assert result is None or isinstance(result, Path)

    def test_find_source_dir_with_symlinked_parent(self, tmp_path: Path) -> None:
        """Symlinks to source directories should be followed by resolve()."""
        project = _make_dir_with_subdirs(tmp_path / "real_project", ["agents", "skills"])
        link = tmp_path / "linked_project"
        link.symlink_to(project)

        child = link / "subdir"
        child.mkdir()
        found = _find_source_dir(child)
        assert found is not None
        # resolve() follows symlinks, so result should be the real path.
        assert found == project.resolve()

    def test_find_source_dir_nested_source_roots(self, tmp_path: Path) -> None:
        """When nested directories both qualify, the nearest wins."""
        outer = _make_dir_with_subdirs(tmp_path / "outer", ["agents", "skills"])
        inner = _make_dir_with_subdirs(outer / "inner", ["commands", "plugins"])

        # Starting from inner should find inner first (nearest ancestor).
        found = _find_source_dir(inner)
        assert found == inner.resolve()

        # Starting from a child of outer (but not inside inner) should find outer.
        other = outer / "other"
        other.mkdir()
        found = _find_source_dir(other)
        assert found == outer.resolve()


# ---------------------------------------------------------------------------
# Cache directory handling — existing dirs, multiple repos, non-git targets
# ---------------------------------------------------------------------------


class TestCacheDirectoryEdgeCases:
    """Extended tests for cache directory edge cases in resolve()."""

    def test_resolve_creates_cache_dir_if_missing(self, tmp_path: Path) -> None:
        """resolve() should create the cache directory when it does not exist."""
        info = SourceInfo(
            source_type=SourceType.GIT_URL,
            path=Path("https://github.com/user/repo.git"),
            original_input="https://github.com/user/repo.git",
            is_git_repo=False,
        )
        mock_git = MagicMock(spec=GitBackend, instance=True)
        mock_git.is_git_repo.return_value = False
        resolver = SourceResolver(git_backend=mock_git)
        cache = tmp_path / "new_cache"

        result = resolver.resolve(info, cache_dir=cache)

        assert cache.exists()
        assert cache.is_dir()
        assert result == (cache / "repo").resolve()

    def test_resolve_uses_existing_cache_dir(self, tmp_path: Path) -> None:
        """resolve() should work with an already-existing cache directory."""
        cache = tmp_path / "existing_cache"
        cache.mkdir()
        (cache / "other_file.txt").write_text("marker")

        info = SourceInfo(
            source_type=SourceType.GIT_URL,
            path=Path("https://github.com/user/repo.git"),
            original_input="https://github.com/user/repo.git",
            is_git_repo=False,
        )
        mock_git = MagicMock(spec=GitBackend, instance=True)
        mock_git.is_git_repo.return_value = False
        resolver = SourceResolver(git_backend=mock_git)

        result = resolver.resolve(info, cache_dir=cache)

        assert result == (cache / "repo").resolve()
        assert (cache / "other_file.txt").exists()  # existing contents preserved

    def test_resolve_multiple_repos_in_same_cache(self, tmp_path: Path) -> None:
        """Multiple git URLs resolved into the same cache should produce different dirs."""
        cache = tmp_path / "cache"
        mock_git = MagicMock(spec=GitBackend, instance=True)
        mock_git.is_git_repo.return_value = False
        resolver = SourceResolver(git_backend=mock_git)

        info_a = SourceInfo(
            source_type=SourceType.GIT_URL,
            path=Path("https://github.com/org/repo-a.git"),
            original_input="https://github.com/org/repo-a.git",
            is_git_repo=False,
        )
        info_b = SourceInfo(
            source_type=SourceType.GIT_URL,
            path=Path("https://github.com/org/repo-b.git"),
            original_input="https://github.com/org/repo-b.git",
            is_git_repo=False,
        )

        result_a = resolver.resolve(info_a, cache_dir=cache)
        result_b = resolver.resolve(info_b, cache_dir=cache)

        assert result_a != result_b
        assert result_a.name == "repo-a"
        assert result_b.name == "repo-b"
        assert mock_git.clone.call_count == 2

    def test_resolve_git_url_existing_non_git_dir_clones(self, tmp_path: Path) -> None:
        """An existing non-git directory at the target should trigger a clone."""
        cache = tmp_path / "cache"
        target = cache / "repo"
        target.mkdir(parents=True)
        (target / "README.md").write_text("not a git repo")

        info = SourceInfo(
            source_type=SourceType.GIT_URL,
            path=Path("https://github.com/user/repo.git"),
            original_input="https://github.com/user/repo.git",
            is_git_repo=False,
        )
        mock_git = MagicMock(spec=GitBackend, instance=True)
        mock_git.is_git_repo.return_value = False
        resolver = SourceResolver(git_backend=mock_git)

        result = resolver.resolve(info, cache_dir=cache)

        assert result == target.resolve()
        mock_git.clone.assert_called_once()
        mock_git.pull.assert_not_called()

    def test_resolve_default_cache_root_uses_home(self) -> None:
        """When cache_dir is None, _cache_root returns the module default."""
        from syncode.source import _DEFAULT_CACHE_ROOT

        result = SourceResolver._cache_root(None)
        assert result == _DEFAULT_CACHE_ROOT


# ---------------------------------------------------------------------------
# Error recovery paths
# ---------------------------------------------------------------------------


class TestErrorRecoveryPaths:
    """Tests for error recovery and unknown source types."""

    def test_resolve_unknown_source_type_raises(self, tmp_path: Path) -> None:
        """resolve() should raise SourceError for an unknown SourceType."""
        # We cannot construct an invalid SourceType easily, so we mock it.
        info = SourceInfo(
            source_type=SourceType.LOCAL_DIR,
            path=tmp_path,
            original_input=str(tmp_path),
            is_git_repo=False,
        )
        # Override source_type to a value not in the handled branches.
        object.__setattr__(info, "source_type", "unknown_type")  # type: ignore[frozen_attr]

        resolver = SourceResolver()
        with pytest.raises(SourceError, match="unknown source type"):
            resolver.resolve(info)

    def test_detect_oserror_from_stat_propagates(self) -> None:
        """detect() does not catch generic OSError from stat(); it propagates."""
        resolver = SourceResolver()
        with (
            patch.object(Path, "stat", side_effect=OSError("io error")),
            pytest.raises(OSError, match="io error"),
        ):
            resolver.detect("/some/path")

    def test_git_error_from_os_error_unknown_errno(self) -> None:
        """_git_error_from_os_error with unrecognised errno should not add hint."""
        exc = OSError(999, "something weird happened")
        err = _git_error_from_os_error("clone", "https://example.com/repo", exc)
        msg = str(err)
        assert "something weird happened" in msg
        # Should not include any specific hint suffix.
        assert "permission" not in msg.lower()
        assert "disk" not in msg.lower()

    def test_classify_git_stderr_combined_errors(self) -> None:
        """_classify_git_stderr should match the first matching pattern."""
        stderr = "fatal: repository not found — check credentials"
        hint = _classify_git_stderr(stderr)
        # "not found" appears before credential patterns in the check order,
        # so the hint should be about verifying the URL.
        assert hint is not None
        assert "verify" in hint.lower() or "url" in hint.lower()

    def test_classify_git_stderr_mixed_case(self) -> None:
        """Pattern matching is case-insensitive."""
        hint = _classify_git_stderr("FATAL: COULD NOT READ USERNAME")
        assert hint is not None
        assert "credentials" in hint.lower() or "permissions" in hint.lower()

    def test_resolve_git_dir_returns_path_directly(self, tmp_path: Path) -> None:
        """resolve() for GIT_DIR should return the path without touching git."""
        project = _make_dir_with_subdirs(tmp_path / "project", ["agents", "skills"])
        (project / ".git").mkdir()

        info = SourceInfo(
            source_type=SourceType.GIT_DIR,
            path=project.resolve(),
            original_input=str(project),
            is_git_repo=True,
        )
        mock_git = MagicMock(spec=GitBackend, instance=True)
        resolver = SourceResolver(git_backend=mock_git)

        result = resolver.resolve(info)
        assert result == project.resolve()
        mock_git.clone.assert_not_called()
        mock_git.pull.assert_not_called()

    def test_detect_local_dir_not_git(self, tmp_path: Path) -> None:
        """detect() for a plain directory (no .git) should return LOCAL_DIR."""
        project = _make_dir_with_subdirs(tmp_path / "project", ["agents", "skills"])
        mock_git = MagicMock(spec=GitBackend, instance=True)
        mock_git.is_git_repo.return_value = False
        resolver = SourceResolver(git_backend=mock_git)

        info = resolver.detect(str(project))

        assert info.source_type == SourceType.LOCAL_DIR
        assert info.is_git_repo is False
        mock_git.is_git_repo.assert_called_once_with(project.resolve())

    def test_detect_git_url_preserves_original_input(self) -> None:
        """detect() should preserve the exact URL in original_input."""
        url = "git@github.com:org/repo.git"
        resolver = SourceResolver()
        info = resolver.detect(url)
        assert info.original_input == url
        assert info.source_type == SourceType.GIT_URL
        assert str(info.path) == url

    def test_source_info_equality(self) -> None:
        """Two SourceInfo instances with the same values should be equal."""
        kwargs = dict(
            source_type=SourceType.LOCAL_DIR,
            path=Path("/tmp/project"),
            original_input="/tmp/project",
            is_git_repo=False,
        )
        a = SourceInfo(**kwargs)  # type: ignore[arg-type]
        b = SourceInfo(**kwargs)  # type: ignore[arg-type]
        assert a == b

    def test_source_info_hash(self) -> None:
        """Frozen dataclasses should be hashable for use in sets/dicts."""
        info = SourceInfo(
            source_type=SourceType.LOCAL_DIR,
            path=Path("/tmp/project"),
            original_input="/tmp/project",
            is_git_repo=False,
        )
        assert hash(info) == hash(info)  # deterministic
        assert {info} == {info}  # usable in sets


# ---------------------------------------------------------------------------
# Bug-fix regression tests
# ---------------------------------------------------------------------------


class TestRepoNameQueryStringFragmentFix:
    """Regression tests for query-string / fragment stripping in _repo_name_from_url."""

    @pytest.mark.parametrize(
        "url, expected",
        [
            # Query string with branch ref
            ("https://github.com/user/repo.git?ref=main", "repo"),
            # Fragment with tag
            ("https://github.com/user/repo.git#v1.0", "repo"),
            # Both query and fragment
            ("https://github.com/user/repo.git?ref=main#v1.0", "repo"),
            # SSH URL with query string
            ("git@github.com:user/repo.git?foo=bar", "repo"),
            # No .git extension with query
            ("https://github.com/user/my-project?ref=dev", "my-project"),
            # Query with empty value
            ("https://github.com/user/repo.git?", "repo"),
            # Fragment only
            ("https://github.com/user/repo.git#", "repo"),
        ],
    )
    def test_strips_query_and_fragment(self, url: str, expected: str) -> None:
        assert _repo_name_from_url(url) == expected


class TestIsGitUrlCaseInsensitive:
    """Regression tests for case-insensitive scheme matching in _is_git_url."""

    @pytest.mark.parametrize(
        "url",
        [
            "HTTPS://github.com/user/repo.git",
            "Http://example.com/repo.git",
            "GIT://example.com/repo",
            "SSH://git@github.com/user/repo.git",
        ],
    )
    def test_uppercase_scheme_recognised(self, url: str) -> None:
        assert _is_git_url(url) is True

    def test_mixed_case_git_prefix(self) -> None:
        """Mixed case 'Git@' prefix should be recognised."""
        assert _is_git_url("Git@github.com:user/repo.git") is True

    def test_all_caps_git_prefix(self) -> None:
        """All-caps 'GIT@' prefix should be recognised."""
        assert _is_git_url("GIT@github.com:user/repo.git") is True


class TestRunGitChecked:
    """Tests for the _run_git_checked helper in SubprocessGitBackend."""

    def test_returns_result_on_success(self, tmp_path: Path) -> None:
        """Successful git command should return the CompletedProcess."""
        mock_result = MagicMock(spec=subprocess.CompletedProcess)
        mock_result.returncode = 0

        with patch("syncode.source.run_git", return_value=mock_result) as mock_git:
            backend = SubprocessGitBackend()
            result = backend._run_git_checked(
                "clone", "url", 120, "clone", "--depth", "1", "url", "/tmp/repo"
            )

        assert result is mock_result
        mock_git.assert_called_once_with(
            "clone",
            "--depth",
            "1",
            "url",
            "/tmp/repo",
            cwd=None,
            timeout=120,
        )

    def test_passes_cwd_when_provided(self, tmp_path: Path) -> None:
        """cwd should be forwarded to _run_git when provided."""
        mock_result = MagicMock(spec=subprocess.CompletedProcess)
        mock_result.returncode = 0

        with patch("syncode.source.run_git", return_value=mock_result) as mock_git:
            backend = SubprocessGitBackend()
            backend._run_git_checked(
                "fetch",
                "/repo",
                60,
                "fetch",
                "--depth",
                "1",
                cwd="/repo",
            )

        mock_git.assert_called_once_with(
            "fetch",
            "--depth",
            "1",
            cwd="/repo",
            timeout=60,
        )

    @pytest.mark.parametrize(
        ("side_effect", "match"),
        [
            (subprocess.TimeoutExpired(cmd=["git"], timeout=30), "timed out"),
            (FileNotFoundError("git"), "not found"),
            (OSError(28, "No space left"), "space"),
        ],
        ids=["timeout", "git-not-installed", "os-error"],
    )
    def test_exception_translates_to_source_error(
        self,
        side_effect: Exception,
        match: str,
    ) -> None:
        """Subprocess exceptions should be translated to SourceError."""
        with patch("syncode.source.run_git", side_effect=side_effect):
            backend = SubprocessGitBackend()
            with pytest.raises(SourceError, match=match):
                backend._run_git_checked("fetch", "/repo", 30, "fetch")

    def test_nonzero_exit_raises_with_hint(self, tmp_path: Path) -> None:
        """Non-zero exit with a recognised pattern should include a hint arrow."""
        mock_result = MagicMock(spec=subprocess.CompletedProcess)
        mock_result.returncode = 128
        mock_result.stderr = "fatal: could not read Username"

        with patch("syncode.source.run_git", return_value=mock_result):
            backend = SubprocessGitBackend()
            with pytest.raises(SourceError) as exc_info:
                backend._run_git_checked("clone", "url", 120, "clone", "url")
            assert "→" in str(exc_info.value)

    def test_nonzero_exit_no_hint_for_unknown(self, tmp_path: Path) -> None:
        """Non-zero exit without a recognised pattern should omit hint arrow."""
        mock_result = MagicMock(spec=subprocess.CompletedProcess)
        mock_result.returncode = 1
        mock_result.stderr = "something unexpected"

        with patch("syncode.source.run_git", return_value=mock_result):
            backend = SubprocessGitBackend()
            with pytest.raises(SourceError) as exc_info:
                backend._run_git_checked("clone", "url", 120, "clone", "url")
            assert "→" not in str(exc_info.value)
