"""Tests for the ``agentfiles branch`` command."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import pytest

from syncode.cli import _COMMAND_MAP, build_parser, cmd_branch

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_args(
    *,
    source: str | None = None,
    switch: str | None = None,
    non_interactive: bool = True,
    config: Path | None = None,
    cache_dir: str | None = None,
    target: str | None = None,
    item_type: str | None = None,
    dry_run: bool = False,
    only: str | None = None,
    except_items: str | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        command="branch",
        source=source,
        switch=switch,
        non_interactive=non_interactive,
        config=config,
        cache_dir=cache_dir,
        target=target,
        item_type=item_type,
        dry_run=dry_run,
        only=only,
        except_items=except_items,
    )


# ---------------------------------------------------------------------------
# Parser tests
# ---------------------------------------------------------------------------


class TestBranchParser:
    """Parser registration and flag parsing for branch."""

    def test_registered(self) -> None:
        assert "branch" in _COMMAND_MAP
        assert _COMMAND_MAP["branch"] is cmd_branch

    def test_yes(self) -> None:
        args = build_parser().parse_args(["branch", "--yes"])
        assert args.non_interactive is True

    def test_switch(self) -> None:
        args = build_parser().parse_args(["branch", "--switch", "main"])
        assert args.switch == "main"

    def test_switch_develop(self) -> None:
        args = build_parser().parse_args(["branch", "--switch", "develop"])
        assert args.switch == "develop"

    def test_switch_short(self) -> None:
        args = build_parser().parse_args(["branch", "-s", "feature-x"])
        assert args.switch == "feature-x"

    def test_yes_short(self) -> None:
        args = build_parser().parse_args(["branch", "-y"])
        assert args.non_interactive is True

    def test_source_positional(self) -> None:
        """branch uses positional source from _add_common_args."""
        args = build_parser().parse_args(["branch", "/path/to/repo"])
        assert args.source == "/path/to/repo"

    def test_source_with_switch_positional(self) -> None:
        """Source is positional; --switch is a flag."""
        args = build_parser().parse_args(["branch", "--switch", "main", "/repo"])
        assert args.source == "/repo"
        assert args.switch == "main"

    def test_config(self) -> None:
        args = build_parser().parse_args(["branch", "--config", "cfg.yaml"])
        assert args.config is not None

    def test_cache_dir(self) -> None:
        args = build_parser().parse_args(["branch", "--cache-dir", "/tmp"])
        assert args.cache_dir == "/tmp"

    def test_default_no_switch(self) -> None:
        args = build_parser().parse_args(["branch"])
        assert args.switch is None

    def test_default_interactive(self) -> None:
        args = build_parser().parse_args(["branch"])
        assert args.non_interactive is False

    def test_combined_yes_switch(self) -> None:
        args = build_parser().parse_args(["branch", "--yes", "--switch", "feature-y"])
        assert args.non_interactive is True
        assert args.switch == "feature-y"

    def test_target_flag(self) -> None:
        args = build_parser().parse_args(["branch", "--target", "opencode"])
        assert args.target == "opencode"

    def test_dry_run(self) -> None:
        args = build_parser().parse_args(["branch", "--dry-run"])
        assert args.dry_run is True

    def test_only_flag(self) -> None:
        args = build_parser().parse_args(["branch", "--only", "coder"])
        assert args.only == "coder"

    def test_except_flag(self) -> None:
        args = build_parser().parse_args(["branch", "--except", "test"])
        assert args.except_items == "test"


# ---------------------------------------------------------------------------
# Integration tests
# ---------------------------------------------------------------------------


class TestCmdBranchIntegration:
    """Integration tests for cmd_branch with mocked dependencies."""

    @mock.patch("syncode.cli._list_branches_display")
    @mock.patch("syncode.cli._get_source")
    def test_branch_list_no_switch(
        self,
        mock_get_source: mock.MagicMock,
        mock_list: mock.MagicMock,
        tmp_path: Path,
    ) -> None:
        """Without --switch, lists branches and returns 0."""
        mock_get_source.return_value = tmp_path

        args = _make_args(switch=None)
        result = cmd_branch(args)

        assert result == 0
        mock_list.assert_called_once_with(tmp_path)

    @mock.patch("syncode.cli._get_source")
    def test_branch_switch_already_on_branch(
        self,
        mock_get_source: mock.MagicMock,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Switching to current branch returns 0 with info."""
        mock_get_source.return_value = tmp_path

        with mock.patch("syncode.git.get_current_branch", return_value="main"):
            args = _make_args(switch="main")
            result = cmd_branch(args)

        assert result == 0
        output = capsys.readouterr().out
        assert "Already on branch" in output

    @mock.patch("syncode.cli._get_source")
    def test_branch_switch_success(
        self,
        mock_get_source: mock.MagicMock,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Successful branch switch returns 0."""
        mock_get_source.return_value = tmp_path

        with (
            mock.patch("syncode.git.get_current_branch", return_value="main"),
            mock.patch("syncode.git.switch_branch", return_value=True),
        ):
            args = _make_args(switch="develop", non_interactive=True)
            result = cmd_branch(args)

        assert result == 0
        output = capsys.readouterr().out
        assert "Now on branch" in output

    @mock.patch("syncode.cli._get_source")
    def test_branch_switch_failure(
        self,
        mock_get_source: mock.MagicMock,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Failed branch switch returns 1."""
        mock_get_source.return_value = tmp_path

        with (
            mock.patch("syncode.git.get_current_branch", return_value="main"),
            mock.patch("syncode.git.switch_branch", return_value=False),
        ):
            args = _make_args(switch="develop", non_interactive=True)
            result = cmd_branch(args)

        assert result == 1
        # error() writes to stderr, not stdout
        captured = capsys.readouterr()
        assert "Failed to switch" in captured.err

    @mock.patch("syncode.cli._get_source")
    def test_branch_list_displays_branches(
        self,
        mock_get_source: mock.MagicMock,
        tmp_path: Path,
    ) -> None:
        """List mode calls _list_branches_display with source dir."""
        mock_get_source.return_value = tmp_path

        with mock.patch("syncode.cli._list_branches_display") as mock_list:
            args = _make_args(switch=None)
            result = cmd_branch(args)

        assert result == 0
        mock_list.assert_called_once_with(tmp_path)
