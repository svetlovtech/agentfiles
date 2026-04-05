"""Tests for the ``agentfiles pull`` command."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import pytest

from syncode.cli import _COMMAND_MAP, build_parser, cmd_pull
from syncode.models import Item, ItemType, Platform

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_item(
    name: str = "coder",
    item_type: ItemType = ItemType.AGENT,
    checksum: str = "a" * 64,
) -> Item:
    return Item(
        item_type=item_type,
        name=name,
        source_path=Path("/src") / item_type.plural / name,
        supported_platforms=(Platform.OPENCODE, Platform.CLAUDE_CODE),
        checksum=checksum,
    )


def _make_args(
    *,
    non_interactive: bool = True,
    dry_run: bool = False,
    target: str | None = None,
    item_type: str | None = None,
    source: str | None = None,
    config: Path | None = None,
    cache_dir: str | None = None,
    symlinks: bool = False,
    fmt: str = "text",
    only: str | None = None,
    except_items: str | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        command="pull",
        source=source,
        config=config,
        cache_dir=cache_dir,
        target=target,
        item_type=item_type,
        non_interactive=non_interactive,
        dry_run=dry_run,
        symlinks=symlinks,
        format=fmt,
        only=only,
        except_items=except_items,
    )


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

    @mock.patch("syncode.cli._update_sync_state_from_results")
    @mock.patch("syncode.cli._display_update_indicators")
    @mock.patch("syncode.cli._build_context")
    def test_pull_no_items_returns_0(
        self,
        mock_build_ctx: mock.MagicMock,
        mock_display: mock.MagicMock,
        mock_state: mock.MagicMock,
        tmp_path: Path,
    ) -> None:
        """When source has no items, pull returns 0."""
        scanner = mock.MagicMock()
        scanner.scan.return_value = []
        scanner.get_summary.return_value = {}

        ctx = mock.MagicMock(
            scanner=scanner,
            target_manager=mock.MagicMock(),
            engine=mock.MagicMock(),
            source_dir=tmp_path,
            platforms=[Platform.OPENCODE],
            item_types=[ItemType.AGENT],
            dry_run=False,
            fmt="text",
            only_set=None,
            except_set=None,
        )
        mock_build_ctx.return_value = ctx

        args = _make_args(non_interactive=True)
        result = cmd_pull(args)

        assert result == 0

    @mock.patch("syncode.cli._update_sync_state_from_results")
    @mock.patch("syncode.cli._display_update_indicators")
    @mock.patch("syncode.cli._build_context")
    def test_pull_non_interactive_success(
        self,
        mock_build_ctx: mock.MagicMock,
        mock_display: mock.MagicMock,
        mock_state: mock.MagicMock,
        tmp_path: Path,
    ) -> None:
        """Non-interactive pull with items completes successfully."""
        item = _make_item()
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

        ctx = mock.MagicMock(
            scanner=scanner,
            target_manager=mock.MagicMock(),
            engine=engine,
            source_dir=tmp_path,
            platforms=[Platform.OPENCODE],
            item_types=[ItemType.AGENT],
            dry_run=False,
            fmt="text",
            only_set=None,
            except_set=None,
        )
        mock_build_ctx.return_value = ctx

        args = _make_args(non_interactive=True)
        result = cmd_pull(args)

        assert result == 0
        engine.plan_sync.assert_called_once()

    @mock.patch("syncode.cli._update_sync_state_from_results")
    @mock.patch("syncode.cli._display_update_indicators")
    @mock.patch("syncode.cli._build_context")
    def test_pull_dry_run_no_changes(
        self,
        mock_build_ctx: mock.MagicMock,
        mock_display: mock.MagicMock,
        mock_state: mock.MagicMock,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Dry-run mode prints warning and does not execute."""
        item = _make_item()
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

        ctx = mock.MagicMock(
            scanner=scanner,
            target_manager=mock.MagicMock(),
            engine=engine,
            source_dir=tmp_path,
            platforms=[Platform.OPENCODE],
            item_types=[ItemType.AGENT],
            dry_run=True,
            fmt="text",
            only_set=None,
            except_set=None,
        )
        mock_build_ctx.return_value = ctx

        args = _make_args(non_interactive=True, dry_run=True)
        result = cmd_pull(args)

        assert result == 0
        output = capsys.readouterr().out
        assert "Dry-run" in output

    @mock.patch("syncode.cli._format_plan_json", return_value=0)
    @mock.patch("syncode.cli._update_sync_state_from_results")
    @mock.patch("syncode.cli._display_update_indicators")
    @mock.patch("syncode.cli._build_context")
    def test_pull_json_dry_run_outputs_plan(
        self,
        mock_build_ctx: mock.MagicMock,
        mock_display: mock.MagicMock,
        mock_state: mock.MagicMock,
        mock_format_plan: mock.MagicMock,
        tmp_path: Path,
    ) -> None:
        """JSON + dry-run calls _format_plan_json and returns early."""
        item = _make_item()
        scanner = mock.MagicMock()
        scanner.scan.return_value = [item]
        scanner.get_summary.return_value = {ItemType.AGENT: 1}

        plan = mock.MagicMock()
        engine = mock.MagicMock()
        engine.plan_sync.return_value = [plan]

        target_manager = mock.MagicMock()
        ctx = mock.MagicMock(
            scanner=scanner,
            target_manager=target_manager,
            engine=engine,
            source_dir=tmp_path,
            platforms=[Platform.OPENCODE],
            item_types=[ItemType.AGENT],
            dry_run=True,
            fmt="json",
            only_set=None,
            except_set=None,
        )
        mock_build_ctx.return_value = ctx

        args = _make_args(non_interactive=True, dry_run=True, fmt="json")
        result = cmd_pull(args)

        assert result == 0
        mock_format_plan.assert_called_once_with([plan], target_manager, dry_run=True)
        engine.execute_plan.assert_not_called()

    @mock.patch("syncode.cli._update_sync_state_from_results")
    @mock.patch("syncode.cli._display_update_indicators")
    @mock.patch("syncode.cli._build_context")
    def test_pull_with_failure_returns_1(
        self,
        mock_build_ctx: mock.MagicMock,
        mock_display: mock.MagicMock,
        mock_state: mock.MagicMock,
        tmp_path: Path,
    ) -> None:
        """When engine reports failure, cmd_pull returns 1."""
        item = _make_item()
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

        ctx = mock.MagicMock(
            scanner=scanner,
            target_manager=mock.MagicMock(),
            engine=engine,
            source_dir=tmp_path,
            platforms=[Platform.OPENCODE],
            item_types=[ItemType.AGENT],
            dry_run=False,
            fmt="text",
            only_set=None,
            except_set=None,
        )
        mock_build_ctx.return_value = ctx

        args = _make_args(non_interactive=True)
        result = cmd_pull(args)

        assert result == 1
