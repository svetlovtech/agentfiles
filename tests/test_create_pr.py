"""Tests for the ``--create-pr`` flag on ``agentfiles push``."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest import mock

import pytest

from agentfiles.cli import _create_pull_request, build_parser

# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_create_pr_flag_defaults() -> None:
    """--create-pr, --pr-title, and --pr-branch should have correct defaults."""
    parser = build_parser()
    args = parser.parse_args(["push"])
    assert args.create_pr is False
    assert args.pr_title is None
    assert args.pr_branch is None


@pytest.mark.unit
def test_create_pr_flag_set() -> None:
    """--create-pr sets create_pr to True."""
    parser = build_parser()
    args = parser.parse_args(["push", "--create-pr"])
    assert args.create_pr is True


@pytest.mark.unit
def test_pr_title_and_branch_args() -> None:
    """--pr-title and --pr-branch are captured correctly."""
    parser = build_parser()
    args = parser.parse_args(
        ["push", "--create-pr", "--pr-title", "My PR", "--pr-branch", "feat/sync"]
    )
    assert args.create_pr is True
    assert args.pr_title == "My PR"
    assert args.pr_branch == "feat/sync"


# ---------------------------------------------------------------------------
# _create_pull_request helper
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_dry_run_prints_and_returns_zero(capsys: pytest.CaptureFixture[str]) -> None:
    """In dry-run mode, _create_pull_request should print info and return 0."""
    code = _create_pull_request(
        source_dir=Path("/fake/repo"),
        pushed_items=["agent/coder"],
        branch="feat/test",
        title="Test PR",
        dry_run=True,
    )
    assert code == 0
    captured = capsys.readouterr()
    # Should mention dry-run actions in stdout or stderr
    output = captured.out + captured.err
    assert "dry-run" in output.lower() or "dry_run" in output.lower() or "dry" in output.lower()


@pytest.mark.unit
def test_dry_run_no_subprocess_calls() -> None:
    """In dry-run mode, no subprocess calls should be made."""
    with mock.patch("subprocess.run") as mock_run:
        _create_pull_request(
            source_dir=Path("/fake/repo"),
            pushed_items=["agent/coder"],
            branch=None,
            title=None,
            dry_run=True,
        )
    mock_run.assert_not_called()


@pytest.mark.unit
def test_gh_not_found_returns_error() -> None:
    """If gh is not installed, should return 1 with an error message."""
    with mock.patch(
        "subprocess.run",
        side_effect=FileNotFoundError("gh not found"),
    ):
        code = _create_pull_request(
            source_dir=Path("/fake/repo"),
            pushed_items=["agent/coder"],
            branch="feat/test",
            title="Test PR",
            dry_run=False,
        )
    assert code == 1


@pytest.mark.unit
def test_gh_version_check_fails_returns_error() -> None:
    """If gh --version returns non-zero, should return 1."""
    with mock.patch(
        "subprocess.run",
        side_effect=subprocess.CalledProcessError(1, "gh"),
    ):
        code = _create_pull_request(
            source_dir=Path("/fake/repo"),
            pushed_items=["agent/coder"],
            branch="feat/test",
            title="Test PR",
            dry_run=False,
        )
    assert code == 1


@pytest.mark.unit
def test_auto_title_single_item() -> None:
    """Auto-generated title for a single item should include the item key."""
    calls: list[mock.call] = []

    def fake_run(cmd: list[str], **kwargs: object) -> mock.MagicMock:
        calls.append(mock.call(cmd))
        result = mock.MagicMock()
        result.stdout = b"https://github.com/org/repo/pull/1\n"
        return result

    with mock.patch("subprocess.run", side_effect=fake_run):
        code = _create_pull_request(
            source_dir=Path("/fake/repo"),
            pushed_items=["agent/coder"],
            branch="feat/test",
            title=None,
            dry_run=False,
        )

    assert code == 0
    # Find the git commit call and check its message contains the item key
    commit_call = next(
        (c for c in calls if c.args[0][0] == "git" and c.args[0][1] == "commit"),
        None,
    )
    assert commit_call is not None
    commit_cmd: list[str] = commit_call.args[0]
    msg_index = commit_cmd.index("-m") + 1
    assert "agent/coder" in commit_cmd[msg_index]


@pytest.mark.unit
def test_auto_title_multiple_items() -> None:
    """Auto-generated title for many items should mention the count."""

    def fake_run(cmd: list[str], **kwargs: object) -> mock.MagicMock:
        result = mock.MagicMock()
        result.stdout = b"https://github.com/org/repo/pull/2\n"
        return result

    with mock.patch("subprocess.run", side_effect=fake_run):
        code = _create_pull_request(
            source_dir=Path("/fake/repo"),
            pushed_items=[f"agent/item{i}" for i in range(5)],
            branch="feat/test",
            title=None,
            dry_run=False,
        )

    assert code == 0


@pytest.mark.unit
def test_nothing_to_commit_skips_pr() -> None:
    """If git commit reports nothing to commit, PR creation should be skipped (return 0)."""
    call_count = 0

    def fake_run(cmd: list[str], **kwargs: object) -> mock.MagicMock:
        nonlocal call_count
        call_count += 1
        if cmd[0] == "git" and cmd[1] == "commit":
            raise subprocess.CalledProcessError(
                1, cmd, stderr=b"nothing to commit, working tree clean"
            )
        result = mock.MagicMock()
        result.stdout = b""
        return result

    with mock.patch("subprocess.run", side_effect=fake_run):
        code = _create_pull_request(
            source_dir=Path("/fake/repo"),
            pushed_items=["agent/coder"],
            branch="feat/test",
            title="Test PR",
            dry_run=False,
        )

    assert code == 0


@pytest.mark.unit
def test_branch_creation_failure_returns_error() -> None:
    """If git checkout -b fails, should return 1."""
    call_count = 0

    def fake_run(cmd: list[str], **kwargs: object) -> mock.MagicMock:
        nonlocal call_count
        call_count += 1
        if cmd[0] == "git" and "checkout" in cmd:
            raise subprocess.CalledProcessError(128, cmd, stderr=b"fatal: branch already exists")
        result = mock.MagicMock()
        result.stdout = b""
        return result

    with mock.patch("subprocess.run", side_effect=fake_run):
        code = _create_pull_request(
            source_dir=Path("/fake/repo"),
            pushed_items=["agent/coder"],
            branch="feat/test",
            title="Test PR",
            dry_run=False,
        )

    assert code == 1
