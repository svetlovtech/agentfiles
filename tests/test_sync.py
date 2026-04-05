"""Tests for the ``agentfiles sync`` command."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import pytest

from syncode.cli import _COMMAND_MAP, build_parser, cmd_sync
from syncode.models import Item, ItemType, Platform

# ---------------------------------------------------------------------------
# Helpers
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
        supported_platforms=(Platform.OPENCODE,),
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
    only: str | None = None,
    except_items: str | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        command="sync",
        source=source,
        config=config,
        cache_dir=cache_dir,
        target=target,
        item_type=item_type,
        non_interactive=non_interactive,
        dry_run=dry_run,
        only=only,
        except_items=except_items,
    )


# ---------------------------------------------------------------------------
# Parser tests
# ---------------------------------------------------------------------------


class TestSyncParser:
    """Parser registration and flag parsing for sync."""

    def test_registered(self) -> None:
        assert "sync" in _COMMAND_MAP
        assert _COMMAND_MAP["sync"] is cmd_sync

    def test_yes(self) -> None:
        args = build_parser().parse_args(["sync", "--yes"])
        assert args.non_interactive is True

    def test_dry_run(self) -> None:
        args = build_parser().parse_args(["sync", "--dry-run"])
        assert args.dry_run is True

    def test_target(self) -> None:
        args = build_parser().parse_args(["sync", "--target", "claude_code"])
        assert args.target == "claude_code"

    def test_type(self) -> None:
        args = build_parser().parse_args(["sync", "--type", "plugin"])
        assert args.item_type == "plugin"

    def test_only(self) -> None:
        args = build_parser().parse_args(["sync", "--only", "coder"])
        assert args.only == "coder"

    def test_except(self) -> None:
        args = build_parser().parse_args(["sync", "--except", "deprecated"])
        assert args.except_items == "deprecated"

    def test_source_positional(self) -> None:
        args = build_parser().parse_args(["sync", "/path/to/repo"])
        assert args.source == "/path/to/repo"

    def test_config(self) -> None:
        args = build_parser().parse_args(["sync", "--config", "cfg.yaml"])
        assert args.config is not None

    def test_cache_dir(self) -> None:
        args = build_parser().parse_args(["sync", "--cache-dir", "/tmp/cache"])
        assert args.cache_dir == "/tmp/cache"

    def test_default_no_yes(self) -> None:
        args = build_parser().parse_args(["sync"])
        assert args.non_interactive is False

    def test_default_no_dry_run(self) -> None:
        args = build_parser().parse_args(["sync"])
        assert args.dry_run is False

    def test_all_targets(self) -> None:
        args = build_parser().parse_args(["sync", "--target", "all"])
        assert args.target == "all"


# ---------------------------------------------------------------------------
# Integration tests
# ---------------------------------------------------------------------------


class TestCmdSyncIntegration:
    """Integration tests for cmd_sync with mocked heavy dependencies.

    cmd_sync calls many internal helpers (_get_source, _create_sync_pipeline,
    _filter_items, etc.).  We patch these at their definition site in
    ``syncode.cli`` so the deferred imports inside cmd_sync still resolve
    correctly.
    """

    @mock.patch("syncode.cli._update_sync_state_from_results")
    @mock.patch("syncode.cli._execute_sync_actions")
    @mock.patch("syncode.cli._apply_item_filter")
    @mock.patch("syncode.cli._resolve_item_filter")
    @mock.patch("syncode.cli._resolve_platforms")
    @mock.patch("syncode.cli._filter_items")
    @mock.patch("syncode.cli._resolve_item_types")
    @mock.patch("syncode.cli._scan_filtered")
    @mock.patch("syncode.cli._create_sync_pipeline")
    @mock.patch("syncode.cli._get_source")
    @mock.patch("syncode.config.load_sync_state")
    @mock.patch("syncode.config.SyncodeConfig.load")
    def test_sync_no_plan_returns_0(
        self,
        mock_config_load: mock.MagicMock,
        mock_load_state: mock.MagicMock,
        mock_get_source: mock.MagicMock,
        mock_pipeline: mock.MagicMock,
        mock_scan: mock.MagicMock,
        mock_resolve_types: mock.MagicMock,
        mock_filter_items: mock.MagicMock,
        mock_resolve_platforms: mock.MagicMock,
        mock_resolve_filter: mock.MagicMock,
        mock_apply_filter: mock.MagicMock,
        mock_execute: mock.MagicMock,
        mock_update_state: mock.MagicMock,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """When sync plan is empty, everything is already in sync."""
        scanner = mock.MagicMock()
        engine = mock.MagicMock()
        engine.compute_sync_plan.return_value = []

        mock_config_load.return_value = mock.MagicMock(cache_dir=None)
        mock_get_source.return_value = tmp_path
        mock_pipeline.return_value = (scanner, mock.MagicMock(), engine)
        mock_load_state.return_value = mock.MagicMock()
        mock_scan.return_value = []
        mock_resolve_types.return_value = [ItemType.AGENT]
        mock_filter_items.return_value = []
        mock_resolve_platforms.return_value = [Platform.OPENCODE]
        mock_resolve_filter.return_value = (None, None)
        mock_apply_filter.return_value = []

        args = _make_args(non_interactive=True)
        result = cmd_sync(args)

        assert result == 0
        output = capsys.readouterr().out
        assert "already in sync" in output

    @mock.patch("syncode.config.save_sync_state")
    @mock.patch("syncode.cli._update_sync_state_from_results")
    @mock.patch("syncode.cli._execute_sync_actions")
    @mock.patch("syncode.cli._apply_item_filter")
    @mock.patch("syncode.cli._resolve_item_filter")
    @mock.patch("syncode.cli._resolve_platforms")
    @mock.patch("syncode.cli._filter_items")
    @mock.patch("syncode.cli._resolve_item_types")
    @mock.patch("syncode.cli._scan_filtered")
    @mock.patch("syncode.cli._create_sync_pipeline")
    @mock.patch("syncode.cli._get_source")
    @mock.patch("syncode.config.load_sync_state")
    @mock.patch("syncode.config.SyncodeConfig.load")
    def test_sync_non_interactive_executes_plan(
        self,
        mock_config_load: mock.MagicMock,
        mock_load_state: mock.MagicMock,
        mock_get_source: mock.MagicMock,
        mock_pipeline: mock.MagicMock,
        mock_scan: mock.MagicMock,
        mock_resolve_types: mock.MagicMock,
        mock_filter_items: mock.MagicMock,
        mock_resolve_platforms: mock.MagicMock,
        mock_resolve_filter: mock.MagicMock,
        mock_apply_filter: mock.MagicMock,
        mock_execute: mock.MagicMock,
        mock_update_state: mock.MagicMock,
        mock_save_state: mock.MagicMock,
        tmp_path: Path,
    ) -> None:
        """Non-interactive sync executes the sync plan."""
        item = _make_item()

        scanner = mock.MagicMock()
        engine = mock.MagicMock()
        sync_plan = [(item, Platform.OPENCODE, "pull")]
        engine.compute_sync_plan.return_value = sync_plan

        sync_result = mock.MagicMock()
        sync_result.is_success = True
        engine.aggregate.return_value = mock.MagicMock(
            is_success=True,
            summary=lambda: "1 pulled",
        )

        mock_config_load.return_value = mock.MagicMock(cache_dir=None)
        mock_get_source.return_value = tmp_path
        mock_pipeline.return_value = (scanner, mock.MagicMock(), engine)
        mock_load_state.return_value = mock.MagicMock()
        mock_scan.return_value = [item]
        mock_resolve_types.return_value = [ItemType.AGENT]
        mock_filter_items.return_value = [item]
        mock_resolve_platforms.return_value = [Platform.OPENCODE]
        mock_resolve_filter.return_value = (None, None)
        mock_apply_filter.return_value = [item]
        mock_execute.return_value = [sync_result]

        args = _make_args(non_interactive=True)
        result = cmd_sync(args)

        assert result == 0
        mock_execute.assert_called_once()

    @mock.patch("syncode.cli._update_sync_state_from_results")
    @mock.patch("syncode.cli._execute_sync_actions")
    @mock.patch("syncode.cli._apply_item_filter")
    @mock.patch("syncode.cli._resolve_item_filter")
    @mock.patch("syncode.cli._resolve_platforms")
    @mock.patch("syncode.cli._filter_items")
    @mock.patch("syncode.cli._resolve_item_types")
    @mock.patch("syncode.cli._scan_filtered")
    @mock.patch("syncode.cli._create_sync_pipeline")
    @mock.patch("syncode.cli._get_source")
    @mock.patch("syncode.config.load_sync_state")
    @mock.patch("syncode.config.SyncodeConfig.load")
    def test_sync_dry_run_no_state_save(
        self,
        mock_config_load: mock.MagicMock,
        mock_load_state: mock.MagicMock,
        mock_get_source: mock.MagicMock,
        mock_pipeline: mock.MagicMock,
        mock_scan: mock.MagicMock,
        mock_resolve_types: mock.MagicMock,
        mock_filter_items: mock.MagicMock,
        mock_resolve_platforms: mock.MagicMock,
        mock_resolve_filter: mock.MagicMock,
        mock_apply_filter: mock.MagicMock,
        mock_execute: mock.MagicMock,
        mock_update_state: mock.MagicMock,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Dry-run sync prints warning and does not save state."""
        item = _make_item()

        scanner = mock.MagicMock()
        engine = mock.MagicMock()
        sync_plan = [(item, Platform.OPENCODE, "pull")]
        engine.compute_sync_plan.return_value = sync_plan

        sync_result = mock.MagicMock()
        sync_result.is_success = True
        engine.aggregate.return_value = mock.MagicMock(
            is_success=True,
            summary=lambda: "1 pulled",
        )

        mock_config_load.return_value = mock.MagicMock(cache_dir=None)
        mock_get_source.return_value = tmp_path
        mock_pipeline.return_value = (scanner, mock.MagicMock(), engine)
        mock_load_state.return_value = mock.MagicMock()
        mock_scan.return_value = [item]
        mock_resolve_types.return_value = [ItemType.AGENT]
        mock_filter_items.return_value = [item]
        mock_resolve_platforms.return_value = [Platform.OPENCODE]
        mock_resolve_filter.return_value = (None, None)
        mock_apply_filter.return_value = [item]
        mock_execute.return_value = [sync_result]

        args = _make_args(non_interactive=True, dry_run=True)
        result = cmd_sync(args)

        assert result == 0
        output = capsys.readouterr().out
        assert "Dry-run" in output
        mock_update_state.assert_not_called()
