"""Tests for agentfiles.git module."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from agentfiles.git import (
    GitError,
    GitNotFoundError,
    _run_git,
    is_git_repo,
)
from agentfiles.models import AgentfilesError


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
# Exceptions
# ---------------------------------------------------------------------------


class TestExceptions:
    """Tests for custom git exceptions."""

    def test_git_error_is_base(self) -> None:
        """GitError should be the base for all git exceptions."""
        assert issubclass(GitNotFoundError, GitError)

    def test_git_error_inherits_agentfiles_error(self) -> None:
        """GitError should inherit from AgentfilesError."""
        assert issubclass(GitError, AgentfilesError)

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
