"""Tests for agentfiles.git module."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from agentfiles.git import (
    BranchInfo,
    GitError,
    GitNotFoundError,
    _branch_cache,
    _cache_key,
    _classify_error,
    _current_branch_from_cache,
    _log_switch_failure,
    _read_head_branch,
    _resolve_head_path,
    _run_git,
    get_current_branch,
    get_repo_name,
    invalidate_cache,
    is_detached_head,
    is_dirty,
    is_git_repo,
    list_branches,
    switch_branch,
)
from agentfiles.models import SyncodeError

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clear_branch_cache() -> None:
    """Ensure the module-level branch cache is empty before each test."""
    _branch_cache.clear()
    yield
    _branch_cache.clear()


# ---------------------------------------------------------------------------
# BranchInfo dataclass
# ---------------------------------------------------------------------------


class TestBranchInfo:
    """Tests for the BranchInfo frozen dataclass."""

    def test_fields_accessible(self) -> None:
        """Name and is_current should be readable."""
        info = BranchInfo(name="main", is_current=True)
        assert info.name == "main"
        assert info.is_current is True

    def test_frozen_prevents_mutation(self) -> None:
        """Assigning to a field should raise AttributeError."""
        info = BranchInfo(name="develop", is_current=False)
        with pytest.raises(AttributeError):
            info.name = "hotfix"  # type: ignore[misc]

    def test_equality(self) -> None:
        """Two instances with the same values should be equal."""
        a = BranchInfo(name="main", is_current=True)
        b = BranchInfo(name="main", is_current=True)
        assert a == b

    def test_inequality(self) -> None:
        """Instances differing in any field should not be equal."""
        a = BranchInfo(name="main", is_current=True)
        b = BranchInfo(name="main", is_current=False)
        assert a != b


# ---------------------------------------------------------------------------
# is_git_repo
# ---------------------------------------------------------------------------


class TestIsGitRepo:
    """Tests for the is_git_repo helper."""

    def test_returns_true_when_git_dir_exists(self, tmp_path: Path) -> None:
        """A directory containing a .git child should be detected as a repo."""
        (tmp_path / ".git").mkdir()
        assert is_git_repo(tmp_path) is True

    def test_returns_true_when_git_file_exists(self, tmp_path: Path) -> None:
        """A .git file (used by worktrees) also qualifies as a repo."""
        (tmp_path / ".git").write_text("gitdir: /somewhere/else")
        assert is_git_repo(tmp_path) is True

    def test_returns_false_without_git(self, tmp_path: Path) -> None:
        """A plain directory without .git should not be detected as a repo."""
        assert is_git_repo(tmp_path) is False


# ---------------------------------------------------------------------------
# get_repo_name
# ---------------------------------------------------------------------------


class TestGetRepoName:
    """Tests for the get_repo_name helper."""

    def test_returns_directory_name(self, tmp_path: Path) -> None:
        """Should return the final path component after resolution."""
        repo = tmp_path / "my-awesome-project"
        repo.mkdir()
        assert get_repo_name(repo) == "my-awesome-project"

    def test_resolves_symlinks(self, tmp_path: Path) -> None:
        """Should resolve symlinks before extracting the directory name."""
        target = tmp_path / "actual-repo"
        target.mkdir()
        link = tmp_path / "link"
        link.symlink_to(target)
        assert get_repo_name(link) == "actual-repo"


# ---------------------------------------------------------------------------
# _resolve_head_path
# ---------------------------------------------------------------------------


class TestResolveHeadPath:
    """Tests for the _resolve_head_path internal helper."""

    def test_regular_repo(self, tmp_path: Path) -> None:
        """Should locate .git/HEAD for a regular repository."""
        (tmp_path / ".git").mkdir()
        result = _resolve_head_path(tmp_path)
        assert result == tmp_path / ".git" / "HEAD"

    def test_worktree_repo(self, tmp_path: Path) -> None:
        """Should resolve HEAD via gitdir file for worktrees."""
        gitdir = tmp_path / "wt"
        gitdir.mkdir()
        (gitdir / "HEAD").write_text("ref: refs/heads/main\n")
        (tmp_path / ".git").write_text(f"gitdir: {gitdir}")
        result = _resolve_head_path(tmp_path)
        assert result == gitdir / "HEAD"

    def test_worktree_with_relative_path(self, tmp_path: Path) -> None:
        """Should resolve relative gitdir paths against repo_path."""
        # Place the worktree metadata outside .git so .git remains a file.
        wt_dir = tmp_path / "wt-data"
        wt_dir.mkdir()
        (wt_dir / "HEAD").write_text("ref: refs/heads/feature\n")
        (tmp_path / ".git").write_text("gitdir: wt-data")
        result = _resolve_head_path(tmp_path)
        assert result is not None
        assert result == wt_dir / "HEAD"

    def test_returns_none_when_no_git(self, tmp_path: Path) -> None:
        """Should return None when .git does not exist."""
        assert _resolve_head_path(tmp_path) is None

    def test_returns_none_for_invalid_gitdir(self, tmp_path: Path) -> None:
        """Should return None when .git file has unexpected content."""
        (tmp_path / ".git").write_text("not a gitdir line")
        assert _resolve_head_path(tmp_path) is None


# ---------------------------------------------------------------------------
# _read_head_branch
# ---------------------------------------------------------------------------


class TestReadHeadBranch:
    """Tests for the _read_head_branch filesystem-based branch reader."""

    def test_reads_branch_from_regular_repo(self, tmp_path: Path) -> None:
        """Should parse 'ref: refs/heads/<name>' from .git/HEAD."""
        (tmp_path / ".git").mkdir()
        (tmp_path / ".git" / "HEAD").write_text("ref: refs/heads/develop\n")
        assert _read_head_branch(tmp_path) == "develop"

    def test_returns_none_for_detached_head(self, tmp_path: Path) -> None:
        """Should return None when HEAD contains a raw SHA (detached)."""
        (tmp_path / ".git").mkdir()
        (tmp_path / ".git" / "HEAD").write_text("a1b2c3d4e5f6a7b8c9d0\n")
        assert _read_head_branch(tmp_path) is None

    def test_returns_none_when_no_head_file(self, tmp_path: Path) -> None:
        """Should return None when .git exists but HEAD does not."""
        (tmp_path / ".git").mkdir()
        assert _read_head_branch(tmp_path) is None

    def test_returns_none_when_no_git_dir(self, tmp_path: Path) -> None:
        """Should return None when .git does not exist."""
        assert _read_head_branch(tmp_path) is None

    def test_strips_whitespace(self, tmp_path: Path) -> None:
        """Should handle trailing newlines gracefully."""
        (tmp_path / ".git").mkdir()
        (tmp_path / ".git" / "HEAD").write_text("ref: refs/heads/main\n")
        assert _read_head_branch(tmp_path) == "main"

    def test_worktree_repo(self, tmp_path: Path) -> None:
        """Should read branch from worktree gitdir."""
        wt_dir = tmp_path / "wt"
        wt_dir.mkdir()
        (wt_dir / "HEAD").write_text("ref: refs/heads/feature/x\n")
        (tmp_path / ".git").write_text(f"gitdir: {wt_dir}")
        assert _read_head_branch(tmp_path) == "feature/x"


# ---------------------------------------------------------------------------
# _current_branch_from_cache
# ---------------------------------------------------------------------------


class TestCurrentBranchFromCache:
    """Tests for _current_branch_from_cache helper."""

    def test_returns_branch_from_cache(self, tmp_path: Path) -> None:
        """Should return the current branch from cached data."""
        _branch_cache[_cache_key(tmp_path)] = [
            BranchInfo(name="main", is_current=True),
            BranchInfo(name="dev", is_current=False),
        ]
        assert _current_branch_from_cache(tmp_path) == "main"

    def test_returns_none_when_cache_empty(self, tmp_path: Path) -> None:
        """Should return None when no cached data exists."""
        assert _current_branch_from_cache(tmp_path) is None

    def test_returns_none_when_no_current_branch(self, tmp_path: Path) -> None:
        """Should return None when no branch is marked as current."""
        _branch_cache[_cache_key(tmp_path)] = [
            BranchInfo(name="dev", is_current=False),
        ]
        assert _current_branch_from_cache(tmp_path) is None


# ---------------------------------------------------------------------------
# invalidate_cache
# ---------------------------------------------------------------------------


class TestInvalidateCache:
    """Tests for the invalidate_cache public function."""

    def test_invalidate_specific_repo(self, tmp_path: Path) -> None:
        """Should remove only the targeted repo from the cache."""
        key = _cache_key(tmp_path)
        other_key = tmp_path / "other"
        _branch_cache[key] = [BranchInfo(name="main", is_current=True)]
        _branch_cache[other_key] = [BranchInfo(name="dev", is_current=True)]

        invalidate_cache(tmp_path)

        assert key not in _branch_cache
        assert other_key in _branch_cache

    def test_invalidate_all(self, tmp_path: Path) -> None:
        """Should clear the entire cache when no repo_path given."""
        _branch_cache[_cache_key(tmp_path)] = [BranchInfo(name="main", is_current=True)]
        _branch_cache[Path("/other")] = [BranchInfo(name="dev", is_current=True)]

        invalidate_cache()

        assert len(_branch_cache) == 0

    def test_invalidate_nonexistent_is_noop(self, tmp_path: Path) -> None:
        """Should not raise when the repo is not in cache."""
        invalidate_cache(tmp_path)  # should not raise


# ---------------------------------------------------------------------------
# get_current_branch
# ---------------------------------------------------------------------------


class TestGetCurrentBranch:
    """Tests for get_current_branch."""

    def test_reads_head_file_directly(self, tmp_path: Path) -> None:
        """Should read .git/HEAD instead of spawning a subprocess."""
        git_dir = tmp_path / ".git"
        git_dir.mkdir()
        (git_dir / "HEAD").write_text("ref: refs/heads/main\n")

        with patch("agentfiles.git._run_git") as mock_git:
            branch = get_current_branch(tmp_path)

        assert branch == "main"
        mock_git.assert_not_called()

    def test_uses_cache_when_head_unavailable(self, tmp_path: Path) -> None:
        """Should fall back to cache when .git/HEAD cannot be read."""
        (tmp_path / ".git").mkdir()
        # No HEAD file — _read_head_branch returns None.
        # Populate cache with branch data.
        _branch_cache[_cache_key(tmp_path)] = [
            BranchInfo(name="cached-branch", is_current=True),
        ]

        with patch("agentfiles.git._run_git") as mock_git:
            branch = get_current_branch(tmp_path)

        assert branch == "cached-branch"
        mock_git.assert_not_called()

    def test_falls_back_to_subprocess(self, tmp_path: Path) -> None:
        """Should use git rev-parse when HEAD file and cache both miss."""
        (tmp_path / ".git").mkdir()
        mock_result = MagicMock(spec=subprocess.CompletedProcess)
        mock_result.returncode = 0
        mock_result.stdout = "main\n"
        mock_result.stderr = ""

        with patch("agentfiles.git._run_git", return_value=mock_result) as mock_git:
            branch = get_current_branch(tmp_path)

        assert branch == "main"
        mock_git.assert_called_once_with("rev-parse", "--abbrev-ref", "HEAD", cwd=str(tmp_path))

    def test_failure_when_git_returns_nonzero(self, tmp_path: Path) -> None:
        """Should return empty string when git rev-parse fails."""
        (tmp_path / ".git").mkdir()
        mock_result = MagicMock(spec=subprocess.CompletedProcess)
        mock_result.returncode = 128
        mock_result.stdout = ""
        mock_result.stderr = "fatal: not a git repository"

        with patch("agentfiles.git._run_git", return_value=mock_result):
            branch = get_current_branch(tmp_path)

        assert branch == ""

    def test_returns_empty_when_not_git_repo(self, tmp_path: Path) -> None:
        """Should return empty string when path has no .git directory."""
        branch = get_current_branch(tmp_path)
        assert branch == ""

    def test_strips_whitespace(self, tmp_path: Path) -> None:
        """Should strip trailing newline from git output."""
        (tmp_path / ".git").mkdir()
        mock_result = MagicMock(spec=subprocess.CompletedProcess)
        mock_result.returncode = 0
        mock_result.stdout = "  develop  \n"
        mock_result.stderr = ""

        with patch("agentfiles.git._run_git", return_value=mock_result):
            branch = get_current_branch(tmp_path)

        assert branch == "develop"

    def test_detached_head_returns_empty_via_filesystem(self, tmp_path: Path) -> None:
        """Detached HEAD (.git/HEAD has SHA) returns empty, then falls to cache/subprocess."""
        (tmp_path / ".git").mkdir()
        (tmp_path / ".git" / "HEAD").write_text("a1b2c3d4e5f6\n")
        # No cache, no subprocess mock → returns "" from rev-parse failure path
        mock_result = MagicMock(spec=subprocess.CompletedProcess)
        mock_result.returncode = 1
        mock_result.stdout = "HEAD\n"
        mock_result.stderr = ""

        with patch("agentfiles.git._run_git", return_value=mock_result):
            branch = get_current_branch(tmp_path)

        assert branch == ""


# ---------------------------------------------------------------------------
# list_branches
# ---------------------------------------------------------------------------


class TestListBranches:
    """Tests for list_branches."""

    def test_success_parses_output(self, tmp_path: Path) -> None:
        """Should parse git branch --list output into BranchInfo objects."""
        (tmp_path / ".git").mkdir()
        mock_result = MagicMock(spec=subprocess.CompletedProcess)
        mock_result.returncode = 0
        mock_result.stdout = "* main\n  develop\n  feature/test\n"
        mock_result.stderr = ""

        with patch("agentfiles.git._run_git", return_value=mock_result) as mock_git:
            branches = list_branches(tmp_path)

        assert len(branches) == 3
        mock_git.assert_called_once_with("branch", "--list", cwd=str(tmp_path))

        # Current branch should be sorted first.
        assert branches[0].name == "main"
        assert branches[0].is_current is True

        # Remaining branches are sorted alphabetically.
        assert branches[1].name == "develop"
        assert branches[1].is_current is False
        assert branches[2].name == "feature/test"
        assert branches[2].is_current is False

    def test_failure_returns_empty(self, tmp_path: Path) -> None:
        """Should return an empty list when git branch fails."""
        (tmp_path / ".git").mkdir()
        mock_result = MagicMock(spec=subprocess.CompletedProcess)
        mock_result.returncode = 128
        mock_result.stdout = ""
        mock_result.stderr = "fatal: not a git repository"

        with patch("agentfiles.git._run_git", return_value=mock_result):
            branches = list_branches(tmp_path)

        assert branches == []

    def test_not_git_repo_returns_empty(self, tmp_path: Path) -> None:
        """Should return an empty list when path is not a git repo."""
        branches = list_branches(tmp_path)
        assert branches == []

    def test_sorting_order(self, tmp_path: Path) -> None:
        """Current branch first, then remaining sorted alphabetically."""
        (tmp_path / ".git").mkdir()
        # Output order from git is arbitrary; verify our sort is correct.
        mock_result = MagicMock(spec=subprocess.CompletedProcess)
        mock_result.returncode = 0
        mock_result.stdout = "  zeta\n* main\n  alpha\n"
        mock_result.stderr = ""

        with patch("agentfiles.git._run_git", return_value=mock_result):
            branches = list_branches(tmp_path)

        assert branches[0].name == "main"
        assert branches[0].is_current is True
        assert branches[1].name == "alpha"
        assert branches[2].name == "zeta"

    def test_caches_result(self, tmp_path: Path) -> None:
        """Second call should return cached data without subprocess."""
        (tmp_path / ".git").mkdir()
        mock_result = MagicMock(spec=subprocess.CompletedProcess)
        mock_result.returncode = 0
        mock_result.stdout = "* main\n  develop\n"
        mock_result.stderr = ""

        with patch("agentfiles.git._run_git", return_value=mock_result) as mock_git:
            first = list_branches(tmp_path)
            second = list_branches(tmp_path)

        assert first == second
        # _run_git called only once — second call hits cache.
        assert mock_git.call_count == 1

    def test_returns_copy_not_cache_reference(self, tmp_path: Path) -> None:
        """Mutating the returned list should not affect the cache."""
        (tmp_path / ".git").mkdir()
        mock_result = MagicMock(spec=subprocess.CompletedProcess)
        mock_result.returncode = 0
        mock_result.stdout = "* main\n"
        mock_result.stderr = ""

        with patch("agentfiles.git._run_git", return_value=mock_result):
            result = list_branches(tmp_path)

        result.append(BranchInfo(name="injected", is_current=False))

        # Cache should not contain the injected branch.
        cached = _branch_cache[_cache_key(tmp_path)]
        assert len(cached) == 1
        assert cached[0].name == "main"


# ---------------------------------------------------------------------------
# switch_branch
# ---------------------------------------------------------------------------


class TestSwitchBranch:
    """Tests for switch_branch."""

    def test_success(self, tmp_path: Path) -> None:
        """Should return True when git checkout succeeds."""
        (tmp_path / ".git").mkdir()
        is_dirty_result = MagicMock(spec=subprocess.CompletedProcess)
        is_dirty_result.returncode = 0
        is_dirty_result.stdout = ""
        is_dirty_result.stderr = ""

        checkout_result = MagicMock(spec=subprocess.CompletedProcess)
        checkout_result.returncode = 0
        checkout_result.stderr = ""

        with patch(
            "agentfiles.git._run_git", side_effect=[is_dirty_result, checkout_result]
        ) as mock_git:
            result = switch_branch(tmp_path, "develop")

        assert result is True
        assert mock_git.call_count == 2

    def test_failure(self, tmp_path: Path) -> None:
        """Should return False when git checkout fails."""
        (tmp_path / ".git").mkdir()
        mock_result = MagicMock(spec=subprocess.CompletedProcess)
        mock_result.returncode = 1
        mock_result.stderr = "error: pathspec 'nonexistent' did not match"

        with patch("agentfiles.git._run_git", return_value=mock_result):
            result = switch_branch(tmp_path, "nonexistent")

        assert result is False

    def test_returns_false_when_not_git_repo(self, tmp_path: Path) -> None:
        """Should return False without calling git when path has no .git."""
        with patch("agentfiles.git._run_git") as mock_git:
            result = switch_branch(tmp_path, "develop")

        assert result is False
        mock_git.assert_not_called()

    def test_invalidates_cache_on_success(self, tmp_path: Path) -> None:
        """Should clear the branch cache after a successful checkout."""
        (tmp_path / ".git").mkdir()
        _branch_cache[_cache_key(tmp_path)] = [
            BranchInfo(name="main", is_current=True),
        ]
        is_dirty_result = MagicMock(spec=subprocess.CompletedProcess)
        is_dirty_result.returncode = 0
        is_dirty_result.stdout = ""
        is_dirty_result.stderr = ""

        checkout_result = MagicMock(spec=subprocess.CompletedProcess)
        checkout_result.returncode = 0
        checkout_result.stderr = ""

        with patch("agentfiles.git._run_git", side_effect=[is_dirty_result, checkout_result]):
            switch_branch(tmp_path, "develop")

        assert _cache_key(tmp_path) not in _branch_cache

    def test_does_not_invalidate_cache_on_failure(self, tmp_path: Path) -> None:
        """Should preserve cache when checkout fails."""
        (tmp_path / ".git").mkdir()
        _branch_cache[_cache_key(tmp_path)] = [
            BranchInfo(name="main", is_current=True),
        ]
        mock_result = MagicMock(spec=subprocess.CompletedProcess)
        mock_result.returncode = 1
        mock_result.stderr = "error"

        with patch("agentfiles.git._run_git", return_value=mock_result):
            switch_branch(tmp_path, "nonexistent")

        assert _cache_key(tmp_path) in _branch_cache


# ---------------------------------------------------------------------------
# _run_git
# ---------------------------------------------------------------------------


class TestRunGit:
    """Tests for the _run_git subprocess wrapper."""

    def test_invokes_subprocess_with_correct_args(self) -> None:
        """Should call subprocess.run with git as first arg and remaining args."""
        mock_result = MagicMock(spec=subprocess.CompletedProcess)
        mock_result.returncode = 0
        mock_result.stdout = "ok"
        mock_result.stderr = ""

        with patch("agentfiles.git.subprocess.run", return_value=mock_result) as mock_run:
            result = _run_git("status")

        mock_run.assert_called_once()
        call_kwargs = mock_run.call_args
        assert call_kwargs[0][0] == ["git", "status"]
        assert call_kwargs[1]["capture_output"] is True
        assert call_kwargs[1]["text"] is True
        assert call_kwargs[1]["cwd"] is None
        assert call_kwargs[1]["timeout"] > 0
        assert result.returncode == 0

    def test_passes_cwd(self) -> None:
        """Should forward the cwd kwarg to subprocess.run."""
        mock_result = MagicMock(spec=subprocess.CompletedProcess)
        mock_result.returncode = 0
        mock_result.stdout = ""
        mock_result.stderr = ""

        with patch("agentfiles.git.subprocess.run", return_value=mock_result) as mock_run:
            _run_git("branch", "--list", cwd="/some/repo")

        assert mock_run.call_args[1]["cwd"] == "/some/repo"

    def test_returns_completed_process(self) -> None:
        """Should return the CompletedProcess instance from subprocess.run."""
        mock_result = MagicMock(spec=subprocess.CompletedProcess)
        mock_result.returncode = 0
        mock_result.stdout = "output"
        mock_result.stderr = "errors"

        with patch("agentfiles.git.subprocess.run", return_value=mock_result):
            result = _run_git("log")

        assert result is mock_result
        assert result.stdout == "output"
        assert result.stderr == "errors"

    def test_run_git_timeout_returns_none(self) -> None:
        """Verify run_git converts TimeoutExpired to GitError."""
        mock_result = MagicMock(spec=subprocess.CompletedProcess)
        mock_result.returncode = 1
        mock_result.stderr = "timeout"
        with (
            patch(
                "agentfiles.git.subprocess.run",
                side_effect=subprocess.TimeoutExpired(cmd="git", timeout=30),
            ),
            pytest.raises(GitError, match="timed out"),
        ):
            _run_git("status", cwd="/tmp")

    def test_custom_timeout_overrides_default(self) -> None:
        """Should pass a custom timeout value to subprocess.run."""
        mock_result = MagicMock(spec=subprocess.CompletedProcess)
        mock_result.returncode = 0
        mock_result.stdout = ""
        mock_result.stderr = ""

        with patch("agentfiles.git.subprocess.run", return_value=mock_result) as mock_run:
            _run_git(
                "clone", "--depth", "1", "https://example.com/repo.git", "/tmp/repo", timeout=120
            )

        assert mock_run.call_args[1]["timeout"] == 120


# ---------------------------------------------------------------------------
# _parse_branch_output (internal)
# ---------------------------------------------------------------------------


class TestParseBranchOutput:
    """Tests for the internal _parse_branch_output helper."""

    def test_parses_current_branch(self) -> None:
        """Lines starting with '*' should be marked as current."""
        from agentfiles.git import _parse_branch_output

        result = _parse_branch_output("* main")
        assert len(result) == 1
        assert result[0].name == "main"
        assert result[0].is_current is True

    def test_parses_non_current_branch(self) -> None:
        """Lines with two-space indent should be marked as non-current."""
        from agentfiles.git import _parse_branch_output

        result = _parse_branch_output("  develop")
        assert len(result) == 1
        assert result[0].name == "develop"
        assert result[0].is_current is False

    def test_parses_multiple_branches(self) -> None:
        """Should return all branches in the order they appear."""
        from agentfiles.git import _parse_branch_output

        output = "* main\n  develop\n  feature/x\n"
        result = _parse_branch_output(output)
        assert len(result) == 3
        assert result[0].name == "main"
        assert result[1].name == "develop"
        assert result[2].name == "feature/x"

    def test_ignores_empty_lines(self) -> None:
        """Blank lines should be skipped."""
        from agentfiles.git import _parse_branch_output

        output = "* main\n\n\n  feature\n"
        result = _parse_branch_output(output)
        assert len(result) == 2

    def test_empty_string(self) -> None:
        """Empty input should produce an empty list."""
        from agentfiles.git import _parse_branch_output

        assert _parse_branch_output("") == []


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class TestExceptions:
    """Tests for custom git exceptions."""

    def test_git_error_is_base(self) -> None:
        """GitError should be the base for all git exceptions."""
        assert issubclass(GitNotFoundError, GitError)

    def test_git_error_inherits_agentfiles_error(self) -> None:
        """GitError should inherit from SyncodeError."""
        assert issubclass(GitError, SyncodeError)

    def test_git_not_found_error_message(self) -> None:
        """GitNotFoundError should carry the provided message."""
        exc = GitNotFoundError("git missing")
        assert "git missing" in str(exc)


# ---------------------------------------------------------------------------
# _run_git — FileNotFoundError handling
# ---------------------------------------------------------------------------


class TestRunGitGitNotFound:
    """Tests for _run_git when git is not installed."""

    def test_raises_git_not_found_error(self) -> None:
        """FileNotFoundError from subprocess should raise GitNotFoundError."""
        with (
            patch(
                "agentfiles.git.subprocess.run",
                side_effect=FileNotFoundError("git not found"),
            ),
            pytest.raises(GitNotFoundError, match="git is not installed"),
        ):
            _run_git("status")

    def test_git_not_found_error_is_git_error(self) -> None:
        """GitNotFoundError raised by _run_git should be a GitError."""
        with (
            patch(
                "agentfiles.git.subprocess.run",
                side_effect=FileNotFoundError("git not found"),
            ),
            pytest.raises(GitError),
        ):
            _run_git("status")

    def test_git_not_found_preserves_cause(self) -> None:
        """The original FileNotFoundError should be chained as __cause__."""
        original = FileNotFoundError("git not found")
        with (
            patch("agentfiles.git.subprocess.run", side_effect=original),
            pytest.raises(GitNotFoundError) as exc_info,
        ):
            _run_git("branch", "--list")

        assert exc_info.value.__cause__ is original


# ---------------------------------------------------------------------------
# is_detached_head
# ---------------------------------------------------------------------------


class TestIsDetachedHead:
    """Tests for the is_detached_head helper."""

    def test_returns_true_for_sha_head(self, tmp_path: Path) -> None:
        """HEAD containing a raw SHA indicates detached state."""
        (tmp_path / ".git").mkdir()
        (tmp_path / ".git" / "HEAD").write_text("a1b2c3d4e5f6a7b8c9d0\n")
        assert is_detached_head(tmp_path) is True

    def test_returns_false_for_branch_ref(self, tmp_path: Path) -> None:
        """HEAD containing a branch ref indicates attached state."""
        (tmp_path / ".git").mkdir()
        (tmp_path / ".git" / "HEAD").write_text("ref: refs/heads/main\n")
        assert is_detached_head(tmp_path) is False

    def test_returns_false_when_no_git(self, tmp_path: Path) -> None:
        """No .git directory should return False."""
        assert is_detached_head(tmp_path) is False

    def test_returns_false_when_no_head(self, tmp_path: Path) -> None:
        """Missing HEAD file should return False."""
        (tmp_path / ".git").mkdir()
        assert is_detached_head(tmp_path) is False

    def test_returns_false_for_empty_head(self, tmp_path: Path) -> None:
        """Empty HEAD (unborn branch) should return False."""
        (tmp_path / ".git").mkdir()
        (tmp_path / ".git" / "HEAD").write_text("")
        assert is_detached_head(tmp_path) is False

    def test_worktree_detached(self, tmp_path: Path) -> None:
        """Detached HEAD in worktree should be detected."""
        wt_dir = tmp_path / "wt"
        wt_dir.mkdir()
        (wt_dir / "HEAD").write_text("deadbeef1234\n")
        (tmp_path / ".git").write_text(f"gitdir: {wt_dir}")
        assert is_detached_head(tmp_path) is True


# ---------------------------------------------------------------------------
# is_dirty
# ---------------------------------------------------------------------------


class TestIsDirty:
    """Tests for the is_dirty helper."""

    def test_returns_true_when_dirty(self, tmp_path: Path) -> None:
        """Non-empty porcelain output should indicate dirty state."""
        (tmp_path / ".git").mkdir()
        mock_result = MagicMock(spec=subprocess.CompletedProcess)
        mock_result.returncode = 0
        mock_result.stdout = "M file.py\n"
        mock_result.stderr = ""

        with patch("agentfiles.git._run_git", return_value=mock_result):
            assert is_dirty(tmp_path) is True

    def test_returns_false_when_clean(self, tmp_path: Path) -> None:
        """Empty porcelain output should indicate clean state."""
        (tmp_path / ".git").mkdir()
        mock_result = MagicMock(spec=subprocess.CompletedProcess)
        mock_result.returncode = 0
        mock_result.stdout = ""
        mock_result.stderr = ""

        with patch("agentfiles.git._run_git", return_value=mock_result):
            assert is_dirty(tmp_path) is False

    def test_returns_false_when_not_git_repo(self, tmp_path: Path) -> None:
        """Non-git directory should return False."""
        assert is_dirty(tmp_path) is False

    def test_returns_false_on_git_failure(self, tmp_path: Path) -> None:
        """git status failure should return False."""
        (tmp_path / ".git").mkdir()
        mock_result = MagicMock(spec=subprocess.CompletedProcess)
        mock_result.returncode = 128
        mock_result.stdout = ""
        mock_result.stderr = "fatal: not a git repository"

        with patch("agentfiles.git._run_git", return_value=mock_result):
            assert is_dirty(tmp_path) is False


# ---------------------------------------------------------------------------
# _classify_error
# ---------------------------------------------------------------------------


class TestClassifyError:
    """Tests for the _classify_error helper."""

    def test_dirty_tree_local_changes(self) -> None:
        """Should detect dirty working tree — local changes message."""
        result = _classify_error(
            "error: Your local changes to the following files would be overwritten"
        )
        assert result is not None
        assert "dirty working tree" in result

    def test_dirty_tree_would_be_overwritten(self) -> None:
        """Should detect dirty working tree — would be overwritten."""
        result = _classify_error(
            "error: The following untracked files would be overwritten by checkout"
        )
        assert result is not None
        assert "dirty working tree" in result

    def test_dirty_tree_please_commit(self) -> None:
        """Should detect dirty working tree — please commit message."""
        result = _classify_error("error: Please commit your changes before you switch branches")
        assert result is not None
        assert "dirty working tree" in result

    def test_merge_conflict(self) -> None:
        """Should detect merge conflict messages."""
        result = _classify_error("CONFLICT (content): Merge conflict in file.py")
        assert result is not None
        assert "merge conflict" in result

    def test_branch_not_found(self) -> None:
        """Should detect branch not found messages."""
        result = _classify_error(
            "error: pathspec 'nonexistent' did not match any file(s) known to git"
        )
        assert result is not None
        assert "branch not found" in result

    def test_unknown_revision(self) -> None:
        """Should detect unknown revision messages."""
        result = _classify_error("fatal: unknown revision 'abc123'")
        assert result is not None
        assert "branch not found" in result

    def test_unrecognised_error_returns_none(self) -> None:
        """Unrecognised stderr should return None."""
        result = _classify_error("something completely unexpected happened")
        assert result is None

    def test_empty_stderr_returns_none(self) -> None:
        """Empty stderr should return None."""
        assert _classify_error("") is None


# ---------------------------------------------------------------------------
# switch_branch — error classification
# ---------------------------------------------------------------------------


class TestSwitchBranchErrorClassification:
    """Tests for switch_branch error message clarity."""

    def test_logs_dirty_tree_message(self, tmp_path: Path) -> None:
        """Should log a clear dirty-tree message when uncommitted changes block checkout."""
        (tmp_path / ".git").mkdir()
        mock_result = MagicMock(spec=subprocess.CompletedProcess)
        mock_result.returncode = 1
        mock_result.stderr = (
            "error: Your local changes to the following files would be overwritten by checkout"
        )

        with (
            patch("agentfiles.git._run_git", return_value=mock_result),
            patch("agentfiles.git.logger") as mock_logger,
        ):
            result = switch_branch(tmp_path, "develop")

        assert result is False
        # Find the warning call and verify it contains classification.
        warning_calls = [c for c in mock_logger.warning.call_args_list]
        assert len(warning_calls) == 1
        logged_msg = str(warning_calls[0])
        assert "dirty working tree" in logged_msg

    def test_logs_merge_conflict_message(self, tmp_path: Path) -> None:
        """Should log a clear merge-conflict message."""
        (tmp_path / ".git").mkdir()
        mock_result = MagicMock(spec=subprocess.CompletedProcess)
        mock_result.returncode = 1
        mock_result.stderr = "CONFLICT (content): Merge conflict in src/main.py"

        with (
            patch("agentfiles.git._run_git", return_value=mock_result),
            patch("agentfiles.git.logger") as mock_logger,
        ):
            result = switch_branch(tmp_path, "develop")

        assert result is False
        warning_calls = mock_logger.warning.call_args_list
        assert len(warning_calls) == 1
        logged_msg = str(warning_calls[0])
        assert "merge conflict" in logged_msg

    def test_logs_branch_not_found_message(self, tmp_path: Path) -> None:
        """Should log a clear branch-not-found message."""
        (tmp_path / ".git").mkdir()
        mock_result = MagicMock(spec=subprocess.CompletedProcess)
        mock_result.returncode = 1
        mock_result.stderr = "error: pathspec 'xyz' did not match any file(s) known to git"

        with (
            patch("agentfiles.git._run_git", return_value=mock_result),
            patch("agentfiles.git.logger") as mock_logger,
        ):
            result = switch_branch(tmp_path, "xyz")

        assert result is False
        warning_calls = mock_logger.warning.call_args_list
        assert len(warning_calls) == 1
        logged_msg = str(warning_calls[0])
        assert "branch not found" in logged_msg

    def test_logs_raw_stderr_for_unknown_error(self, tmp_path: Path) -> None:
        """Should fall back to raw git output when error is unclassified."""
        (tmp_path / ".git").mkdir()
        mock_result = MagicMock(spec=subprocess.CompletedProcess)
        mock_result.returncode = 1
        mock_result.stderr = "some completely novel error"

        with (
            patch("agentfiles.git._run_git", return_value=mock_result),
            patch("agentfiles.git.logger") as mock_logger,
        ):
            result = switch_branch(tmp_path, "develop")

        assert result is False
        warning_calls = mock_logger.warning.call_args_list
        assert len(warning_calls) == 1
        logged_msg = str(warning_calls[0])
        assert "some completely novel error" in logged_msg


# ---------------------------------------------------------------------------
# switch_branch — is_dirty pre-check
# ---------------------------------------------------------------------------


class TestSwitchBranchDirtyPreCheck:
    """Tests for the is_dirty pre-check in switch_branch."""

    def test_returns_false_when_dirty(self, tmp_path: Path) -> None:
        """Should return False early when working tree has uncommitted changes."""
        (tmp_path / ".git").mkdir()
        dirty_result = MagicMock(spec=subprocess.CompletedProcess)
        dirty_result.returncode = 0
        dirty_result.stdout = "M file.py\n"
        dirty_result.stderr = ""

        with (
            patch("agentfiles.git._run_git", return_value=dirty_result),
            patch("agentfiles.git.logger") as mock_logger,
        ):
            result = switch_branch(tmp_path, "develop")

        assert result is False
        warning_calls = mock_logger.warning.call_args_list
        assert len(warning_calls) == 1
        assert "uncommitted changes" in str(warning_calls[0])

    def test_skips_checkout_when_dirty(self, tmp_path: Path) -> None:
        """Should not attempt checkout when working tree is dirty."""
        (tmp_path / ".git").mkdir()
        dirty_result = MagicMock(spec=subprocess.CompletedProcess)
        dirty_result.returncode = 0
        dirty_result.stdout = "?? untracked.txt\n"
        dirty_result.stderr = ""

        with patch("agentfiles.git._run_git", return_value=dirty_result) as mock_git:
            switch_branch(tmp_path, "develop")

        # Only the is_dirty call — no checkout attempt.
        assert mock_git.call_count == 1
        assert mock_git.call_args_list[0].args == ("status", "--porcelain")


# ---------------------------------------------------------------------------
# get_current_branch — detached HEAD clarity
# ---------------------------------------------------------------------------


class TestGetCurrentBranchDetachedHead:
    """Tests for get_current_branch detached-HEAD logging."""

    def test_logs_detached_head_info(self, tmp_path: Path) -> None:
        """Should log an info message when repo is in detached HEAD state."""
        (tmp_path / ".git").mkdir()
        (tmp_path / ".git" / "HEAD").write_text("a1b2c3d4e5f6\n")

        with patch("agentfiles.git.logger") as mock_logger:
            branch = get_current_branch(tmp_path)

        assert branch == ""
        info_calls = [c for c in mock_logger.info.call_args_list if "detached HEAD" in str(c)]
        assert len(info_calls) == 1


# ---------------------------------------------------------------------------
# _resolve_head_path — additional edge cases
# ---------------------------------------------------------------------------


class TestResolveHeadPathEdgeCases:
    """Edge-case tests for _resolve_head_path."""

    def test_worktree_gitdir_points_to_nonexistent_path(self, tmp_path: Path) -> None:
        """Should return a Path even if the resolved gitdir does not exist on disk."""
        (tmp_path / ".git").write_text("gitdir: /nonexistent/path")
        result = _resolve_head_path(tmp_path)
        assert result == Path("/nonexistent/path") / "HEAD"

    def test_worktree_with_trailing_whitespace_in_gitdir(self, tmp_path: Path) -> None:
        """Should strip whitespace from the .git file content."""
        wt_dir = tmp_path / "wt"
        wt_dir.mkdir()
        (tmp_path / ".git").write_text(f"gitdir: {wt_dir}\n")
        result = _resolve_head_path(tmp_path)
        assert result == wt_dir / "HEAD"

    def test_oserror_reading_git_file_returns_none(self, tmp_path: Path) -> None:
        """Should return None when reading .git file raises OSError."""
        (tmp_path / ".git").write_text("gitdir: /some/path")
        with patch("pathlib.Path.read_text", side_effect=OSError("permission denied")):
            result = _resolve_head_path(tmp_path)
        assert result is None

    def test_git_file_with_only_gitdir_prefix_stripped(self, tmp_path: Path) -> None:
        """'gitdir: ' with trailing space stripped to 'gitdir:' — no match."""
        (tmp_path / ".git").write_text("gitdir: ")
        # After strip(), content becomes "gitdir:" which does not start with "gitdir: "
        result = _resolve_head_path(tmp_path)
        assert result is None

    def test_git_file_with_valid_gitdir_no_trailing_newline(self, tmp_path: Path) -> None:
        """Valid gitdir content without trailing newline should still work."""
        wt_dir = tmp_path / "wt"
        wt_dir.mkdir()
        (tmp_path / ".git").write_text(f"gitdir: {wt_dir}")  # no newline
        result = _resolve_head_path(tmp_path)
        assert result == wt_dir / "HEAD"


# ---------------------------------------------------------------------------
# _read_head_branch — additional edge cases
# ---------------------------------------------------------------------------


class TestReadHeadBranchEdgeCases:
    """Edge-case tests for _read_head_branch."""

    def test_oserror_reading_head_returns_none(self, tmp_path: Path) -> None:
        """Should return None when HEAD file read raises OSError."""
        (tmp_path / ".git").mkdir()
        (tmp_path / ".git" / "HEAD").write_text("ref: refs/heads/main\n")
        with patch("pathlib.Path.read_text", side_effect=OSError("permission denied")):
            result = _read_head_branch(tmp_path)
        assert result is None

    def test_head_with_only_ref_prefix_no_branch(self, tmp_path: Path) -> None:
        """Should return empty string when HEAD has prefix but no branch name."""
        (tmp_path / ".git").mkdir()
        (tmp_path / ".git" / "HEAD").write_text("ref: refs/heads/")
        result = _read_head_branch(tmp_path)
        assert result == ""

    def test_head_with_unexpected_ref_format(self, tmp_path: Path) -> None:
        """Should return None for HEAD pointing to a non-branch ref (e.g. tag)."""
        (tmp_path / ".git").mkdir()
        (tmp_path / ".git" / "HEAD").write_text("ref: refs/tags/v1.0\n")
        result = _read_head_branch(tmp_path)
        assert result is None

    def test_head_with_only_whitespace(self, tmp_path: Path) -> None:
        """Should return None when HEAD file contains only whitespace."""
        (tmp_path / ".git").mkdir()
        (tmp_path / ".git" / "HEAD").write_text("   \n")
        result = _read_head_branch(tmp_path)
        assert result is None


# ---------------------------------------------------------------------------
# Branch switching — edge cases
# ---------------------------------------------------------------------------


class TestSwitchBranchEdgeCases:
    """Additional edge-case tests for switch_branch."""

    def test_raises_git_not_found_during_checkout(self, tmp_path: Path) -> None:
        """Should propagate GitNotFoundError when _run_git raises it."""
        (tmp_path / ".git").mkdir()
        with (
            patch("agentfiles.git._run_git", side_effect=GitNotFoundError("git not found")),
            patch("agentfiles.git.logger"),
            pytest.raises(GitNotFoundError),
        ):
            switch_branch(tmp_path, "develop")

    def test_switch_with_empty_branch_name(self, tmp_path: Path) -> None:
        """Should invoke git checkout with empty string — git will fail."""
        (tmp_path / ".git").mkdir()
        is_dirty_result = MagicMock(spec=subprocess.CompletedProcess)
        is_dirty_result.returncode = 0
        is_dirty_result.stdout = ""
        is_dirty_result.stderr = ""

        checkout_result = MagicMock(spec=subprocess.CompletedProcess)
        checkout_result.returncode = 1
        checkout_result.stderr = "error: empty string not allowed"

        with patch(
            "agentfiles.git._run_git", side_effect=[is_dirty_result, checkout_result]
        ) as mock_git:
            result = switch_branch(tmp_path, "")

        assert result is False
        assert mock_git.call_count == 2
        assert mock_git.call_args_list[-1] == mock_git.call_args_list[1]
        assert mock_git.call_args_list[1].args == ("checkout", "")

    def test_switch_to_same_branch_succeeds(self, tmp_path: Path) -> None:
        """Switching to the already-active branch should succeed."""
        (tmp_path / ".git").mkdir()
        is_dirty_result = MagicMock(spec=subprocess.CompletedProcess)
        is_dirty_result.returncode = 0
        is_dirty_result.stdout = ""
        is_dirty_result.stderr = ""

        checkout_result = MagicMock(spec=subprocess.CompletedProcess)
        checkout_result.returncode = 0
        checkout_result.stderr = "Already on 'main'"

        with patch(
            "agentfiles.git._run_git", side_effect=[is_dirty_result, checkout_result]
        ) as mock_git:
            result = switch_branch(tmp_path, "main")

        assert result is True
        assert mock_git.call_count == 2
        assert mock_git.call_args_list[-1].args == ("checkout", "main")


# ---------------------------------------------------------------------------
# Cache invalidation — edge cases
# ---------------------------------------------------------------------------


class TestCacheInvalidationEdgeCases:
    """Additional edge-case tests for cache invalidation."""

    def test_cache_key_resolves_symlinks(self, tmp_path: Path) -> None:
        """Cache key should resolve symlinks to canonical paths."""
        real_dir = tmp_path / "real-repo"
        real_dir.mkdir()
        link = tmp_path / "link-repo"
        link.symlink_to(real_dir)

        key = _cache_key(link)
        assert key == real_dir.resolve()

    def test_invalidate_resolves_symlink_before_deleting(self, tmp_path: Path) -> None:
        """Invalidating via a symlink should remove the real path's entry."""
        real_dir = tmp_path / "real-repo"
        real_dir.mkdir()
        link = tmp_path / "link-repo"
        link.symlink_to(real_dir)

        real_key = _cache_key(real_dir)
        _branch_cache[real_key] = [BranchInfo(name="main", is_current=True)]

        # Invalidate using the symlink — should resolve to the same key.
        invalidate_cache(link)
        assert real_key not in _branch_cache

    def test_list_switch_list_cycle(self, tmp_path: Path) -> None:
        """list → switch → list should re-fetch after switch invalidates cache."""
        (tmp_path / ".git").mkdir()

        first_result = MagicMock(spec=subprocess.CompletedProcess)
        first_result.returncode = 0
        first_result.stdout = "* main\n  develop\n"
        first_result.stderr = ""

        # is_dirty pre-check inside switch_branch
        is_dirty_result = MagicMock(spec=subprocess.CompletedProcess)
        is_dirty_result.returncode = 0
        is_dirty_result.stdout = ""
        is_dirty_result.stderr = ""

        checkout_result = MagicMock(spec=subprocess.CompletedProcess)
        checkout_result.returncode = 0
        checkout_result.stderr = ""

        second_result = MagicMock(spec=subprocess.CompletedProcess)
        second_result.returncode = 0
        second_result.stdout = "  main\n* develop\n"
        second_result.stderr = ""

        with (
            patch(
                "agentfiles.git._run_git",
                side_effect=[first_result, is_dirty_result, checkout_result, second_result],
            ),
        ):
            branches1 = list_branches(tmp_path)
            assert branches1[0].name == "main"

            switched = switch_branch(tmp_path, "develop")
            assert switched is True

            branches2 = list_branches(tmp_path)
            assert branches2[0].name == "develop"

    def test_cache_populated_by_list_reused_by_get_branch(self, tmp_path: Path) -> None:
        """get_current_branch should use cache populated by list_branches."""
        (tmp_path / ".git").mkdir()
        # No HEAD file → _read_head_branch returns None.

        mock_result = MagicMock(spec=subprocess.CompletedProcess)
        mock_result.returncode = 0
        mock_result.stdout = "* cached-branch\n  other\n"
        mock_result.stderr = ""

        with patch("agentfiles.git._run_git", return_value=mock_result):
            list_branches(tmp_path)

        # Now get_current_branch should use cache without subprocess.
        with patch("agentfiles.git._run_git") as mock_git:
            branch = get_current_branch(tmp_path)

        assert branch == "cached-branch"
        mock_git.assert_not_called()


# ---------------------------------------------------------------------------
# is_detached_head — additional edge cases
# ---------------------------------------------------------------------------


class TestIsDetachedHeadEdgeCases:
    """Additional edge-case tests for is_detached_head."""

    def test_oserror_reading_head_returns_false(self, tmp_path: Path) -> None:
        """Should return False when reading HEAD raises OSError."""
        (tmp_path / ".git").mkdir()
        (tmp_path / ".git" / "HEAD").write_text("abc123\n")
        with patch("pathlib.Path.read_text", side_effect=OSError("permission denied")):
            result = is_detached_head(tmp_path)
        assert result is False

    def test_worktree_attached_returns_false(self, tmp_path: Path) -> None:
        """Worktree with a branch ref should not be detected as detached."""
        wt_dir = tmp_path / "wt"
        wt_dir.mkdir()
        (wt_dir / "HEAD").write_text("ref: refs/heads/feature\n")
        (tmp_path / ".git").write_text(f"gitdir: {wt_dir}")
        assert is_detached_head(tmp_path) is False

    def test_head_with_ref_to_remotes_is_detached(self, tmp_path: Path) -> None:
        """HEAD with a remote-tracking ref is not refs/heads → detached."""
        (tmp_path / ".git").mkdir()
        (tmp_path / ".git" / "HEAD").write_text("ref: refs/remotes/origin/main\n")
        assert is_detached_head(tmp_path) is True

    def test_head_with_long_sha(self, tmp_path: Path) -> None:
        """Full 40-char SHA should be detected as detached."""
        (tmp_path / ".git").mkdir()
        (tmp_path / ".git" / "HEAD").write_text("a1b2c3d4e5f6a7b8c9d0a1b2c3d4e5f6a7b8c9d0\n")
        assert is_detached_head(tmp_path) is True


# ---------------------------------------------------------------------------
# is_dirty — additional edge cases
# ---------------------------------------------------------------------------


class TestIsDirtyEdgeCases:
    """Additional edge-case tests for is_dirty."""

    def test_git_not_found_raises_exception(self, tmp_path: Path) -> None:
        """Should propagate GitNotFoundError from _run_git."""
        (tmp_path / ".git").mkdir()
        with (
            patch("agentfiles.git._run_git", side_effect=GitNotFoundError("git not found")),
            pytest.raises(GitNotFoundError),
        ):
            is_dirty(tmp_path)

    def test_multiple_dirty_entries(self, tmp_path: Path) -> None:
        """Multiple modified files should still return True."""
        (tmp_path / ".git").mkdir()
        mock_result = MagicMock(spec=subprocess.CompletedProcess)
        mock_result.returncode = 0
        mock_result.stdout = "M file1.py\n?? file2.py\nA file3.py\n"
        mock_result.stderr = ""

        with patch("agentfiles.git._run_git", return_value=mock_result):
            assert is_dirty(tmp_path) is True

    def test_only_staged_changes(self, tmp_path: Path) -> None:
        """Staged changes should be detected as dirty."""
        (tmp_path / ".git").mkdir()
        mock_result = MagicMock(spec=subprocess.CompletedProcess)
        mock_result.returncode = 0
        mock_result.stdout = "A  new_file.py\n"
        mock_result.stderr = ""

        with patch("agentfiles.git._run_git", return_value=mock_result):
            assert is_dirty(tmp_path) is True

    def test_whitespace_only_output_is_clean(self, tmp_path: Path) -> None:
        """Stdout with only whitespace should be treated as clean."""
        (tmp_path / ".git").mkdir()
        mock_result = MagicMock(spec=subprocess.CompletedProcess)
        mock_result.returncode = 0
        mock_result.stdout = "   \n"
        mock_result.stderr = ""

        with patch("agentfiles.git._run_git", return_value=mock_result):
            assert is_dirty(tmp_path) is False

    def test_passes_correct_args_to_git(self, tmp_path: Path) -> None:
        """Should call git status --porcelain with the repo path."""
        (tmp_path / ".git").mkdir()
        mock_result = MagicMock(spec=subprocess.CompletedProcess)
        mock_result.returncode = 0
        mock_result.stdout = ""
        mock_result.stderr = ""

        with patch("agentfiles.git._run_git", return_value=mock_result) as mock_git:
            is_dirty(tmp_path)

        mock_git.assert_called_once_with("status", "--porcelain", cwd=str(tmp_path))


# ---------------------------------------------------------------------------
# _parse_branch_output — additional edge cases
# ---------------------------------------------------------------------------


class TestParseBranchOutputEdgeCases:
    """Additional edge-case tests for _parse_branch_output."""

    def test_branch_with_slash_in_name(self) -> None:
        """Branch names containing slashes (e.g. feature/auth) should be preserved."""
        from agentfiles.git import _parse_branch_output

        result = _parse_branch_output("* feature/auth\n  bugfix/issue-42\n")
        assert len(result) == 2
        assert result[0].name == "feature/auth"
        assert result[1].name == "bugfix/issue-42"

    def test_line_with_only_prefix_chars(self) -> None:
        """A line with only '* ' should be skipped (empty name after strip)."""
        from agentfiles.git import _parse_branch_output

        result = _parse_branch_output("* \n  main\n")
        # "* " → name is "" after line[2:].strip() → skipped
        assert len(result) == 1
        assert result[0].name == "main"

    def test_no_current_branch_in_output(self) -> None:
        """All branches as non-current (e.g. detached HEAD)."""
        from agentfiles.git import _parse_branch_output

        result = _parse_branch_output("  develop\n  staging\n")
        assert len(result) == 2
        assert all(not b.is_current for b in result)

    def test_single_current_branch_only(self) -> None:
        """Output with only the current branch."""
        from agentfiles.git import _parse_branch_output

        result = _parse_branch_output("* main\n")
        assert len(result) == 1
        assert result[0].name == "main"
        assert result[0].is_current is True

    def test_branch_name_with_hyphens_and_dots(self) -> None:
        """Branch names with hyphens, dots, and numbers should be preserved."""
        from agentfiles.git import _parse_branch_output

        result = _parse_branch_output("  release-1.2.3\n")
        assert result[0].name == "release-1.2.3"


# ---------------------------------------------------------------------------
# _classify_error — additional edge cases
# ---------------------------------------------------------------------------


class TestClassifyErrorEdgeCases:
    """Additional edge-case tests for _classify_error."""

    def test_case_insensitive_matching(self) -> None:
        """Pattern matching should be case-insensitive."""
        result = _classify_error("YOUR LOCAL CHANGES would be overwritten")
        assert result is not None
        assert "dirty working tree" in result

    def test_local_changes_pattern_match(self) -> None:
        """Should match the 'local changes to the following' pattern."""
        result = _classify_error("error: local changes to the following files")
        assert result is not None
        assert "dirty working tree" in result

    def test_conflicts_during_pattern(self) -> None:
        """Should match the 'conflicts during' pattern."""
        result = _classify_error("error: conflicts during merge")
        assert result is not None
        assert "merge conflict" in result

    def test_multiple_patterns_first_match_wins(self) -> None:
        """When multiple patterns match, dirty-tree should win (checked first)."""
        result = _classify_error("error: your local changes conflict during merge")
        assert result is not None
        assert "dirty working tree" in result


# ---------------------------------------------------------------------------
# _log_switch_failure — direct tests
# ---------------------------------------------------------------------------


class TestLogSwitchFailure:
    """Direct tests for _log_switch_failure helper."""

    def test_logs_classified_error(self) -> None:
        """Should log a classified error message."""
        mock_result = MagicMock(spec=subprocess.CompletedProcess)
        mock_result.returncode = 1
        mock_result.stderr = "error: pathspec 'x' did not match any file(s) known to git"

        with patch("agentfiles.git.logger") as mock_logger:
            _log_switch_failure("x", Path("/repo"), mock_result)

        warning_calls = mock_logger.warning.call_args_list
        assert len(warning_calls) == 1
        assert "branch not found" in str(warning_calls[0])

    def test_logs_raw_stderr_when_unclassified(self) -> None:
        """Should log raw stderr when classification fails."""
        mock_result = MagicMock(spec=subprocess.CompletedProcess)
        mock_result.returncode = 42
        mock_result.stderr = "some totally unknown error"

        with patch("agentfiles.git.logger") as mock_logger:
            _log_switch_failure("branch", Path("/repo"), mock_result)

        warning_calls = mock_logger.warning.call_args_list
        assert len(warning_calls) == 1
        logged = str(warning_calls[0])
        assert "42" in logged
        assert "some totally unknown error" in logged


# ---------------------------------------------------------------------------
# get_current_branch — additional edge cases
# ---------------------------------------------------------------------------


class TestGetCurrentBranchEdgeCases:
    """Additional edge-case tests for get_current_branch."""

    def test_reads_branch_from_worktree(self, tmp_path: Path) -> None:
        """Should read branch name from worktree .git file."""
        wt_dir = tmp_path / "wt"
        wt_dir.mkdir()
        (wt_dir / "HEAD").write_text("ref: refs/heads/feature/x\n")
        (tmp_path / ".git").write_text(f"gitdir: {wt_dir}")

        with patch("agentfiles.git._run_git") as mock_git:
            branch = get_current_branch(tmp_path)

        assert branch == "feature/x"
        mock_git.assert_not_called()

    def test_detached_with_cache_falls_back_to_empty(self, tmp_path: Path) -> None:
        """Detached HEAD with no cache should return empty string."""
        (tmp_path / ".git").mkdir()
        (tmp_path / ".git" / "HEAD").write_text("deadbeef1234\n")

        mock_result = MagicMock(spec=subprocess.CompletedProcess)
        mock_result.returncode = 1
        mock_result.stdout = "(HEAD detached at deadbeef)\n"
        mock_result.stderr = ""

        with patch("agentfiles.git._run_git", return_value=mock_result):
            branch = get_current_branch(tmp_path)

        assert branch == ""

    def test_logs_debug_when_not_git_repo(self, tmp_path: Path) -> None:
        """Should log a debug message when path is not a git repo."""
        with patch("agentfiles.git.logger") as mock_logger:
            get_current_branch(tmp_path)

        debug_calls = [
            c for c in mock_logger.debug.call_args_list if "not a git repo" in str(c).lower()
        ]
        assert len(debug_calls) >= 1
