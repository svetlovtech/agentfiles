"""Tests for the ``agentfiles update`` command and ``git.pull_repo``."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from syncode.cli import build_parser, cmd_update
from syncode.git import PullResult, _classify_pull_error, pull_repo

# ---------------------------------------------------------------------------
# PullResult dataclass
# ---------------------------------------------------------------------------


class TestPullResult:
    """Tests for the PullResult dataclass."""

    def test_success_result(self) -> None:
        result = PullResult(success=True, stdout="Already up to date.", stderr="")
        assert result.success is True
        assert result.error_hint is None

    def test_failure_result_with_hint(self) -> None:
        result = PullResult(
            success=False,
            stdout="",
            stderr="fatal: unable to access",
            error_hint="Network error: check your internet connection.",
        )
        assert result.success is False
        assert result.error_hint is not None

    def test_frozen(self) -> None:
        result = PullResult(success=True, stdout="", stderr="")
        with pytest.raises(AttributeError):
            result.success = False  # type: ignore[misc]


# ---------------------------------------------------------------------------
# pull_repo
# ---------------------------------------------------------------------------


class TestPullRepo:
    """Tests for the pull_repo function."""

    def test_non_git_repo_returns_error(self, tmp_path: Path) -> None:
        """A plain directory without .git should return a failure result."""
        result = pull_repo(tmp_path)
        assert result.success is False
        assert "not a git repository" in result.error_hint.lower()

    @patch("syncode.git._run_git")
    def test_successful_pull(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """A successful git pull returns success=True."""
        (tmp_path / ".git").mkdir()

        mock_run.return_value = subprocess.CompletedProcess(
            args=["git", "pull", "--autostash", "--rebase"],
            returncode=0,
            stdout="Already up to date.",
            stderr="",
        )

        result = pull_repo(tmp_path)
        assert result.success is True
        assert "Already up to date" in result.stdout

    @patch("syncode.git._run_git")
    def test_pull_fails_with_network_error(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """Network errors are classified in the error_hint."""
        (tmp_path / ".git").mkdir()

        mock_run.return_value = subprocess.CompletedProcess(
            args=["git", "pull", "--autostash", "--rebase"],
            returncode=1,
            stdout="",
            stderr="fatal: unable to access 'https://github.com/...': Connection timed out",
        )

        result = pull_repo(tmp_path)
        assert result.success is False
        assert "network" in result.error_hint.lower()

    @patch("syncode.git._run_git")
    def test_pull_fails_with_conflict(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """Local conflict errors are classified in the error_hint."""
        (tmp_path / ".git").mkdir()

        mock_run.return_value = subprocess.CompletedProcess(
            args=["git", "pull", "--autostash", "--rebase"],
            returncode=1,
            stdout="",
            stderr="error: Your local changes would be overwritten by merge",
        )

        result = pull_repo(tmp_path)
        assert result.success is False
        assert "conflict" in result.error_hint.lower()

    @patch("syncode.git._run_git")
    def test_fallback_to_plain_pull(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """When --autostash is not supported, falls back to plain git pull."""
        (tmp_path / ".git").mkdir()

        # First call (with --autostash) fails with "unknown option"
        first_call = subprocess.CompletedProcess(
            args=["git", "pull", "--autostash", "--rebase"],
            returncode=1,
            stdout="",
            stderr="error: unknown option `autostash'",
        )
        # Second call (plain pull) succeeds
        second_call = subprocess.CompletedProcess(
            args=["git", "pull"],
            returncode=0,
            stdout="Fast-forward",
            stderr="",
        )
        mock_run.side_effect = [first_call, second_call]

        result = pull_repo(tmp_path)
        assert result.success is True
        assert "Fast-forward" in result.stdout
        assert mock_run.call_count == 2

    @patch("syncode.git._run_git")
    def test_unknown_error_no_hint(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """Unclassified errors have error_hint=None."""
        (tmp_path / ".git").mkdir()

        mock_run.return_value = subprocess.CompletedProcess(
            args=["git", "pull", "--autostash", "--rebase"],
            returncode=1,
            stdout="",
            stderr="some unrecognized error message",
        )

        result = pull_repo(tmp_path)
        assert result.success is False
        assert result.error_hint is None


# ---------------------------------------------------------------------------
# _classify_pull_error
# ---------------------------------------------------------------------------


class TestClassifyPullError:
    """Tests for error classification."""

    def test_network_error(self) -> None:
        hint = _classify_pull_error("fatal: unable to access: Connection timed out")
        assert hint is not None
        assert "network" in hint.lower()

    def test_conflict_error(self) -> None:
        hint = _classify_pull_error("error: Your local changes would be overwritten")
        assert hint is not None
        assert "conflict" in hint.lower()

    def test_unknown_error(self) -> None:
        hint = _classify_pull_error("something completely unexpected")
        assert hint is None

    def test_ssl_error(self) -> None:
        hint = _classify_pull_error("fatal: SSL certificate problem")
        assert hint is not None
        assert "network" in hint.lower()


# ---------------------------------------------------------------------------
# cmd_update — non-git source
# ---------------------------------------------------------------------------


class TestCmdUpdateNonGit:
    """Tests for cmd_update when source is not a git repository."""

    def test_returns_1_when_not_git_repo(self, tmp_path: Path) -> None:
        """Should return 1 and print error when source is not a git repo."""
        parser = build_parser()
        args = parser.parse_args(["update", "--yes", str(tmp_path)])

        with (
            patch("syncode.cli._get_source", return_value=tmp_path),
            patch("syncode.cli._discover_targets"),
        ):
            exit_code = cmd_update(args)

        assert exit_code == 1


# ---------------------------------------------------------------------------
# cmd_update — parser registration
# ---------------------------------------------------------------------------


class TestUpdateParser:
    """Tests for the update subcommand argument parsing."""

    def test_update_subcommand_exists(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["update"])
        assert args.command == "update"

    def test_update_with_yes_flag(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["update", "--yes"])
        assert args.non_interactive is True

    def test_update_with_dry_run(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["update", "--dry-run"])
        assert args.dry_run is True

    def test_update_with_target(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["update", "--target", "opencode"])
        assert args.target == "opencode"

    def test_update_with_type_filter(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["update", "--type", "skill"])
        assert args.item_type == "skill"

    def test_update_with_symlinks(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["update", "--symlinks"])
        assert args.symlinks is True

    def test_update_with_source_path(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["update", "/path/to/repo"])
        assert args.source == "/path/to/repo"

    def test_update_in_command_map(self) -> None:
        from syncode.cli import _COMMAND_MAP

        assert "update" in _COMMAND_MAP
        assert _COMMAND_MAP["update"] is cmd_update

    @pytest.mark.parametrize(
        "flag,value_attr,expected",
        [
            ("--yes", "non_interactive", True),
            ("--dry-run", "dry_run", True),
            ("--symlinks", "symlinks", True),
        ],
    )
    def test_boolean_flags(self, flag: str, value_attr: str, expected: bool) -> None:
        parser = build_parser()
        args = parser.parse_args(["update", flag])
        assert getattr(args, value_attr) is expected
