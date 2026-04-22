"""Tests for the ``agentfiles pull`` command."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import pytest

from agentfiles.cli import _COMMAND_MAP, build_parser, cmd_pull
from agentfiles.models import ItemType, Platform
from tests.conftest import make_args, make_item

# ---------------------------------------------------------------------------
# Parser tests
# ---------------------------------------------------------------------------


class TestPullParser:
    """Parser registration and flag parsing for pull."""

    def test_registered(self) -> None:
        assert "pull" in _COMMAND_MAP
        assert _COMMAND_MAP["pull"] is cmd_pull

    def test_yes(self) -> None:
        args = build_parser().parse_args(["pull", "--yes"])
        assert args.non_interactive is True

    def test_dry_run(self) -> None:
        args = build_parser().parse_args(["pull", "--dry-run"])
        assert args.dry_run is True

    def test_target(self) -> None:
        args = build_parser().parse_args(["pull", "--target", "opencode"])
        assert args.target == "opencode"

    def test_type(self) -> None:
        args = build_parser().parse_args(["pull", "--type", "agent"])
        assert args.item_type == "agent"

    def test_format_json(self) -> None:
        args = build_parser().parse_args(["pull", "--format", "json"])
        assert args.format == "json"

    def test_symlinks(self) -> None:
        args = build_parser().parse_args(["pull", "--symlinks"])
        assert args.symlinks is True

    def test_only(self) -> None:
        args = build_parser().parse_args(["pull", "--only", "coder,reviewer"])
        assert args.only == "coder,reviewer"

    def test_except(self) -> None:
        args = build_parser().parse_args(["pull", "--except", "old-plugin"])
        assert args.except_items == "old-plugin"

    def test_source_positional(self) -> None:
        args = build_parser().parse_args(["pull", "/path/to/repo"])
        assert args.source == "/path/to/repo"

    def test_config(self) -> None:
        args = build_parser().parse_args(["pull", "--config", "my.yaml"])
        assert args.config is not None


# ---------------------------------------------------------------------------
# Integration tests
# ---------------------------------------------------------------------------


class TestCmdPullIntegration:
    """Integration tests for cmd_pull with mocked dependencies."""

    @staticmethod
    def _make_ctx(
        tmp_path: Path,
        *,
        scanner: mock.MagicMock | None = None,
        engine: mock.MagicMock | None = None,
        target_manager: mock.MagicMock | None = None,
        dry_run: bool = False,
        fmt: str = "text",
    ) -> mock.MagicMock:
        """Build a mock context object for cmd_pull tests."""
        return mock.MagicMock(
            scanner=scanner or mock.MagicMock(),
            target_manager=target_manager or mock.MagicMock(),
            engine=engine or mock.MagicMock(),
            source_dir=tmp_path,
            platforms=[Platform.OPENCODE],
            item_types=[ItemType.AGENT],
            dry_run=dry_run,
            fmt=fmt,
            only_set=None,
            except_set=None,
        )

    def test_pull_no_items_returns_0(
        self,
        pull_mocks: SimpleNamespace,
        tmp_path: Path,
    ) -> None:
        """When source has no items, pull returns 0."""
        scanner = mock.MagicMock()
        scanner.scan.return_value = []
        scanner.get_summary.return_value = {}

        pull_mocks.build_ctx.return_value = self._make_ctx(tmp_path, scanner=scanner)

        args = make_args(command="pull", non_interactive=True)
        result = cmd_pull(args)

        assert result == 0

    def test_pull_non_interactive_success(
        self,
        pull_mocks: SimpleNamespace,
        tmp_path: Path,
    ) -> None:
        """Non-interactive pull with items completes successfully."""
        item = make_item()
        scanner = mock.MagicMock()
        scanner.scan.return_value = [item]
        scanner.get_summary.return_value = {ItemType.AGENT: 1}

        plan = mock.MagicMock()
        sync_result = mock.MagicMock()
        sync_result.is_success = True

        engine = mock.MagicMock()
        engine.plan_sync.return_value = [plan]
        engine.execute_plan.return_value = [sync_result]
        engine.aggregate.return_value = mock.MagicMock(
            is_success=True,
            summary=lambda: "1 installed, 0 updated, 0 skipped",
        )

        pull_mocks.build_ctx.return_value = self._make_ctx(
            tmp_path,
            scanner=scanner,
            engine=engine,
        )

        args = make_args(command="pull", non_interactive=True)
        result = cmd_pull(args)

        assert result == 0
        engine.plan_sync.assert_called_once()

    def test_pull_dry_run_no_changes(
        self,
        pull_mocks: SimpleNamespace,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Dry-run mode prints warning and does not execute."""
        item = make_item()
        scanner = mock.MagicMock()
        scanner.scan.return_value = [item]
        scanner.get_summary.return_value = {ItemType.AGENT: 1}

        plan = mock.MagicMock()
        sync_result = mock.MagicMock()
        sync_result.is_success = True

        engine = mock.MagicMock()
        engine.plan_sync.return_value = [plan]
        engine.execute_plan.return_value = [sync_result]
        engine.aggregate.return_value = mock.MagicMock(
            is_success=True,
            summary=lambda: "1 installed",
        )

        pull_mocks.build_ctx.return_value = self._make_ctx(
            tmp_path,
            scanner=scanner,
            engine=engine,
            dry_run=True,
        )

        args = make_args(command="pull", non_interactive=True, dry_run=True)
        result = cmd_pull(args)

        assert result == 0
        output = capsys.readouterr().out
        assert "Dry-run" in output

    def test_pull_json_dry_run_outputs_plan(
        self,
        pull_mocks: SimpleNamespace,
        tmp_path: Path,
    ) -> None:
        """JSON + dry-run calls _format_plan_json and returns early."""
        item = make_item()
        scanner = mock.MagicMock()
        scanner.scan.return_value = [item]
        scanner.get_summary.return_value = {ItemType.AGENT: 1}

        plan = mock.MagicMock()
        engine = mock.MagicMock()
        engine.plan_sync.return_value = [plan]

        target_manager = mock.MagicMock()
        pull_mocks.build_ctx.return_value = self._make_ctx(
            tmp_path,
            scanner=scanner,
            engine=engine,
            target_manager=target_manager,
            dry_run=True,
            fmt="json",
        )

        with mock.patch("agentfiles.cli._format_plan_json", return_value=0) as mock_fmt:
            args = make_args(command="pull", non_interactive=True, dry_run=True, format="json")
            result = cmd_pull(args)

        assert result == 0
        mock_fmt.assert_called_once_with([plan], target_manager, dry_run=True)
        engine.execute_plan.assert_not_called()

    def test_pull_with_failure_returns_1(
        self,
        pull_mocks: SimpleNamespace,
        tmp_path: Path,
    ) -> None:
        """When engine reports failure, cmd_pull returns 1."""
        item = make_item()
        scanner = mock.MagicMock()
        scanner.scan.return_value = [item]
        scanner.get_summary.return_value = {ItemType.AGENT: 1}

        plan = mock.MagicMock()
        sync_result = mock.MagicMock()
        sync_result.is_success = False

        engine = mock.MagicMock()
        engine.plan_sync.return_value = [plan]
        engine.execute_plan.return_value = [sync_result]
        engine.aggregate.return_value = mock.MagicMock(
            is_success=False,
            summary=lambda: "0 installed, 1 failed",
        )

        pull_mocks.build_ctx.return_value = self._make_ctx(
            tmp_path,
            scanner=scanner,
            engine=engine,
        )

        args = make_args(command="pull", non_interactive=True)
        result = cmd_pull(args)

        assert result == 1
