"""Tests for the ``agentfiles push`` command."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import pytest

from syncode.cli import _COMMAND_MAP, build_parser, cmd_push
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
    symlinks: bool = False,
    fmt: str = "text",
    only: str | None = None,
    except_items: str | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        command="push",
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


class TestPushParser:
    """Parser registration and flag parsing for push."""

    def test_registered(self) -> None:
        assert "push" in _COMMAND_MAP
        assert _COMMAND_MAP["push"] is cmd_push

    def test_yes(self) -> None:
        args = build_parser().parse_args(["push", "--yes"])
        assert args.non_interactive is True

    def test_dry_run(self) -> None:
        args = build_parser().parse_args(["push", "--dry-run"])
        assert args.dry_run is True

    def test_target(self) -> None:
        args = build_parser().parse_args(["push", "--target", "opencode"])
        assert args.target == "opencode"

    def test_type(self) -> None:
        args = build_parser().parse_args(["push", "--type", "skill"])
        assert args.item_type == "skill"

    def test_format_json(self) -> None:
        args = build_parser().parse_args(["push", "--format", "json"])
        assert args.format == "json"

    def test_symlinks(self) -> None:
        args = build_parser().parse_args(["push", "--symlinks"])
        assert args.symlinks is True

    def test_only(self) -> None:
        args = build_parser().parse_args(["push", "--only", "coder"])
        assert args.only == "coder"

    def test_except(self) -> None:
        args = build_parser().parse_args(["push", "--except", "old-agent"])
        assert args.except_items == "old-agent"

    def test_source_positional(self) -> None:
        args = build_parser().parse_args(["push", "/path/to/repo"])
        assert args.source == "/path/to/repo"

    def test_config(self) -> None:
        args = build_parser().parse_args(["push", "--config", "my.yaml"])
        assert args.config is not None

    def test_target_all(self) -> None:
        args = build_parser().parse_args(["push", "--target", "all"])
        assert args.target == "all"

    def test_cache_dir(self) -> None:
        args = build_parser().parse_args(["push", "--cache-dir", "/cache"])
        assert args.cache_dir == "/cache"


# ---------------------------------------------------------------------------
# Integration tests
# ---------------------------------------------------------------------------


class TestCmdPushIntegration:
    """Integration tests for cmd_push with mocked dependencies."""

    @mock.patch("syncode.cli._apply_item_filter")
    @mock.patch("syncode.cli._resolve_item_filter")
    @mock.patch("syncode.cli._discover_installed_from_targets")
    @mock.patch("syncode.cli._resolve_platforms")
    @mock.patch("syncode.cli._resolve_item_types")
    @mock.patch("syncode.cli._create_sync_pipeline")
    @mock.patch("syncode.cli._get_source")
    @mock.patch("syncode.config.SyncodeConfig.load")
    def test_push_no_installed_items(
        self,
        mock_config_load: mock.MagicMock,
        mock_get_source: mock.MagicMock,
        mock_pipeline: mock.MagicMock,
        mock_resolve_types: mock.MagicMock,
        mock_resolve_platforms: mock.MagicMock,
        mock_discover: mock.MagicMock,
        mock_resolve_filter: mock.MagicMock,
        mock_apply_filter: mock.MagicMock,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """When no installed items found, push returns 0."""
        mock_config_load.return_value = mock.MagicMock(cache_dir=None)
        mock_get_source.return_value = tmp_path
        mock_pipeline.return_value = (
            mock.MagicMock(),
            mock.MagicMock(),
            mock.MagicMock(),
        )
        mock_resolve_types.return_value = [ItemType.AGENT]
        mock_resolve_platforms.return_value = [Platform.OPENCODE]
        mock_discover.return_value = []
        mock_resolve_filter.return_value = (None, None)
        mock_apply_filter.return_value = []

        args = _make_args(non_interactive=True)
        result = cmd_push(args)

        assert result == 0
        output = capsys.readouterr().out
        assert "No installed items" in output

    @mock.patch("syncode.cli._apply_item_filter")
    @mock.patch("syncode.cli._resolve_item_filter")
    @mock.patch("syncode.cli._discover_installed_from_targets")
    @mock.patch("syncode.cli._resolve_platforms")
    @mock.patch("syncode.cli._resolve_item_types")
    @mock.patch("syncode.cli._create_sync_pipeline")
    @mock.patch("syncode.cli._get_source")
    @mock.patch("syncode.config.SyncodeConfig.load")
    def test_push_non_interactive_success(
        self,
        mock_config_load: mock.MagicMock,
        mock_get_source: mock.MagicMock,
        mock_pipeline: mock.MagicMock,
        mock_resolve_types: mock.MagicMock,
        mock_resolve_platforms: mock.MagicMock,
        mock_discover: mock.MagicMock,
        mock_resolve_filter: mock.MagicMock,
        mock_apply_filter: mock.MagicMock,
        tmp_path: Path,
    ) -> None:
        """Non-interactive push succeeds with installed items."""
        item = _make_item()

        engine = mock.MagicMock()
        report = mock.MagicMock()
        report.is_success = True
        report.installed = []
        report.updated = []
        report.skipped = []
        report.failed = []
        report.summary.return_value = "1 pushed"
        engine.push.return_value = report

        target_manager = mock.MagicMock()
        mock_config_load.return_value = mock.MagicMock(cache_dir=None)
        mock_get_source.return_value = tmp_path
        mock_pipeline.return_value = (mock.MagicMock(), target_manager, engine)
        mock_resolve_types.return_value = [ItemType.AGENT]
        mock_resolve_platforms.return_value = [Platform.OPENCODE]
        mock_discover.return_value = [item]
        mock_resolve_filter.return_value = (None, None)
        mock_apply_filter.return_value = [item]

        args = _make_args(non_interactive=True)
        result = cmd_push(args)

        assert result == 0
        engine.push.assert_called_once()

    @mock.patch("syncode.cli._apply_item_filter")
    @mock.patch("syncode.cli._resolve_item_filter")
    @mock.patch("syncode.cli._discover_installed_from_targets")
    @mock.patch("syncode.cli._resolve_platforms")
    @mock.patch("syncode.cli._resolve_item_types")
    @mock.patch("syncode.cli._create_sync_pipeline")
    @mock.patch("syncode.cli._get_source")
    @mock.patch("syncode.config.SyncodeConfig.load")
    def test_push_failure_returns_1(
        self,
        mock_config_load: mock.MagicMock,
        mock_get_source: mock.MagicMock,
        mock_pipeline: mock.MagicMock,
        mock_resolve_types: mock.MagicMock,
        mock_resolve_platforms: mock.MagicMock,
        mock_discover: mock.MagicMock,
        mock_resolve_filter: mock.MagicMock,
        mock_apply_filter: mock.MagicMock,
        tmp_path: Path,
    ) -> None:
        """When push fails, returns 1."""
        item = _make_item()

        engine = mock.MagicMock()
        report = mock.MagicMock()
        report.is_success = False
        report.installed = []
        report.updated = []
        report.skipped = []
        report.failed = [mock.MagicMock()]
        report.summary.return_value = "1 failed"
        engine.push.return_value = report

        mock_config_load.return_value = mock.MagicMock(cache_dir=None)
        mock_get_source.return_value = tmp_path
        mock_pipeline.return_value = (mock.MagicMock(), mock.MagicMock(), engine)
        mock_resolve_types.return_value = [ItemType.AGENT]
        mock_resolve_platforms.return_value = [Platform.OPENCODE]
        mock_discover.return_value = [item]
        mock_resolve_filter.return_value = (None, None)
        mock_apply_filter.return_value = [item]

        args = _make_args(non_interactive=True)
        result = cmd_push(args)

        assert result == 1

    @mock.patch("syncode.cli._apply_item_filter")
    @mock.patch("syncode.cli._resolve_item_filter")
    @mock.patch("syncode.cli._discover_installed_from_targets")
    @mock.patch("syncode.cli._resolve_platforms")
    @mock.patch("syncode.cli._resolve_item_types")
    @mock.patch("syncode.cli._create_sync_pipeline")
    @mock.patch("syncode.cli._get_source")
    @mock.patch("syncode.config.SyncodeConfig.load")
    def test_push_dry_run_no_state_update(
        self,
        mock_config_load: mock.MagicMock,
        mock_get_source: mock.MagicMock,
        mock_pipeline: mock.MagicMock,
        mock_resolve_types: mock.MagicMock,
        mock_resolve_platforms: mock.MagicMock,
        mock_discover: mock.MagicMock,
        mock_resolve_filter: mock.MagicMock,
        mock_apply_filter: mock.MagicMock,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Dry-run push prints warning and does not modify files."""
        item = _make_item()

        engine = mock.MagicMock()
        report = mock.MagicMock()
        report.is_success = True
        report.installed = []
        report.updated = []
        report.skipped = []
        report.failed = []
        report.summary.return_value = "1 pushed"
        engine.push.return_value = report

        mock_config_load.return_value = mock.MagicMock(cache_dir=None)
        mock_get_source.return_value = tmp_path
        mock_pipeline.return_value = (mock.MagicMock(), mock.MagicMock(), engine)
        mock_resolve_types.return_value = [ItemType.AGENT]
        mock_resolve_platforms.return_value = [Platform.OPENCODE]
        mock_discover.return_value = [item]
        mock_resolve_filter.return_value = (None, None)
        mock_apply_filter.return_value = [item]

        args = _make_args(non_interactive=True, dry_run=True)
        result = cmd_push(args)

        assert result == 0
        output = capsys.readouterr().out
        assert "Dry-run" in output
