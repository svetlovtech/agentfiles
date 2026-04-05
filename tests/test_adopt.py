"""Tests for the ``agentfiles adopt`` command."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import pytest

from syncode.cli import _COMMAND_MAP, build_parser, cmd_adopt
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
    only: str | None = None,
    except_items: str | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        command="adopt",
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


class TestAdoptParser:
    """Parser registration and flag parsing for adopt.

    Note: adopt uses ``_add_common_args`` only — no ``--symlinks``,
    no ``--format`` flag.
    """

    def test_registered(self) -> None:
        assert "adopt" in _COMMAND_MAP
        assert _COMMAND_MAP["adopt"] is cmd_adopt

    def test_yes(self) -> None:
        args = build_parser().parse_args(["adopt", "--yes"])
        assert args.non_interactive is True

    def test_dry_run(self) -> None:
        args = build_parser().parse_args(["adopt", "--dry-run"])
        assert args.dry_run is True

    def test_target(self) -> None:
        args = build_parser().parse_args(["adopt", "--target", "opencode"])
        assert args.target == "opencode"

    def test_type(self) -> None:
        args = build_parser().parse_args(["adopt", "--type", "agent"])
        assert args.item_type == "agent"

    def test_only(self) -> None:
        args = build_parser().parse_args(["adopt", "--only", "my-agent"])
        assert args.only == "my-agent"

    def test_except(self) -> None:
        args = build_parser().parse_args(["adopt", "--except", "test-*"])
        assert args.except_items == "test-*"

    def test_source_positional(self) -> None:
        args = build_parser().parse_args(["adopt", "/path/to/repo"])
        assert args.source == "/path/to/repo"

    def test_config(self) -> None:
        args = build_parser().parse_args(["adopt", "--config", "custom.yaml"])
        assert args.config is not None

    def test_cache_dir(self) -> None:
        args = build_parser().parse_args(["adopt", "--cache-dir", "/tmp"])
        assert args.cache_dir == "/tmp"

    def test_default_interactive(self) -> None:
        args = build_parser().parse_args(["adopt"])
        assert args.non_interactive is False

    def test_default_no_dry_run(self) -> None:
        args = build_parser().parse_args(["adopt"])
        assert args.dry_run is False

    def test_all_targets(self) -> None:
        args = build_parser().parse_args(["adopt", "--target", "all"])
        assert args.target == "all"


# ---------------------------------------------------------------------------
# Integration tests
# ---------------------------------------------------------------------------


class TestCmdAdoptIntegration:
    """Integration tests for cmd_adopt with mocked dependencies."""

    @mock.patch("syncode.cli._apply_item_filter")
    @mock.patch("syncode.cli._resolve_item_filter")
    @mock.patch("syncode.cli._find_adopt_candidates")
    @mock.patch("syncode.cli._discover_targets")
    @mock.patch("syncode.cli._resolve_platforms")
    @mock.patch("syncode.cli._resolve_item_types")
    @mock.patch("syncode.cli._get_source")
    @mock.patch("syncode.config.SyncodeConfig.load")
    def test_adopt_no_candidates(
        self,
        mock_config_load: mock.MagicMock,
        mock_get_source: mock.MagicMock,
        mock_resolve_types: mock.MagicMock,
        mock_resolve_platforms: mock.MagicMock,
        mock_discover: mock.MagicMock,
        mock_find: mock.MagicMock,
        mock_resolve_filter: mock.MagicMock,
        mock_apply_filter: mock.MagicMock,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """When no candidates found, returns 0 with info message."""
        mock_config_load.return_value = mock.MagicMock(cache_dir=None)
        mock_get_source.return_value = tmp_path
        mock_resolve_types.return_value = [ItemType.AGENT]
        mock_resolve_platforms.return_value = [Platform.OPENCODE]
        mock_discover.return_value = mock.MagicMock()
        mock_find.return_value = []
        mock_resolve_filter.return_value = (None, None)
        mock_apply_filter.return_value = []

        args = _make_args(non_interactive=True)
        result = cmd_adopt(args)

        assert result == 0
        output = capsys.readouterr().out
        assert "No items to adopt" in output

    @mock.patch("syncode.cli._apply_item_filter")
    @mock.patch("syncode.cli._resolve_item_filter")
    @mock.patch("syncode.cli._find_adopt_candidates")
    @mock.patch("syncode.cli._discover_targets")
    @mock.patch("syncode.cli._resolve_platforms")
    @mock.patch("syncode.cli._resolve_item_types")
    @mock.patch("syncode.cli._get_source")
    @mock.patch("syncode.config.SyncodeConfig.load")
    def test_adopt_dry_run(
        self,
        mock_config_load: mock.MagicMock,
        mock_get_source: mock.MagicMock,
        mock_resolve_types: mock.MagicMock,
        mock_resolve_platforms: mock.MagicMock,
        mock_discover: mock.MagicMock,
        mock_find: mock.MagicMock,
        mock_resolve_filter: mock.MagicMock,
        mock_apply_filter: mock.MagicMock,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Dry-run shows candidates but does not adopt."""
        item = _make_item()

        mock_config_load.return_value = mock.MagicMock(cache_dir=None)
        mock_get_source.return_value = tmp_path
        mock_resolve_types.return_value = [ItemType.AGENT]
        mock_resolve_platforms.return_value = [Platform.OPENCODE]
        mock_discover.return_value = mock.MagicMock()
        mock_find.return_value = [item]
        mock_resolve_filter.return_value = (None, None)
        mock_apply_filter.return_value = [item]

        args = _make_args(non_interactive=True, dry_run=True)
        result = cmd_adopt(args)

        assert result == 0
        output = capsys.readouterr().out
        assert "Dry-run" in output

    @mock.patch("syncode.cli._apply_item_filter")
    @mock.patch("syncode.cli._resolve_item_filter")
    @mock.patch("syncode.cli._find_adopt_candidates")
    @mock.patch("syncode.cli._discover_targets")
    @mock.patch("syncode.cli._resolve_platforms")
    @mock.patch("syncode.cli._resolve_item_types")
    @mock.patch("syncode.cli._get_source")
    @mock.patch("syncode.config.SyncodeConfig.load")
    def test_adopt_non_interactive_success(
        self,
        mock_config_load: mock.MagicMock,
        mock_get_source: mock.MagicMock,
        mock_resolve_types: mock.MagicMock,
        mock_resolve_platforms: mock.MagicMock,
        mock_discover: mock.MagicMock,
        mock_find: mock.MagicMock,
        mock_resolve_filter: mock.MagicMock,
        mock_apply_filter: mock.MagicMock,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Non-interactive adopt succeeds and reports summary."""
        item = _make_item()

        engine = mock.MagicMock()
        report = mock.MagicMock()
        report.is_success = True
        report.success_count = 1
        report.summary.return_value = "1 adopted"
        engine.push.return_value = report

        target_manager = mock.MagicMock()

        mock_config_load.return_value = mock.MagicMock(cache_dir=None)
        mock_get_source.return_value = tmp_path
        mock_resolve_types.return_value = [ItemType.AGENT]
        mock_resolve_platforms.return_value = [Platform.OPENCODE]
        mock_discover.return_value = target_manager
        mock_find.return_value = [item]
        mock_resolve_filter.return_value = (None, None)
        mock_apply_filter.return_value = [item]

        with mock.patch("syncode.engine.SyncEngine", return_value=engine):
            args = _make_args(non_interactive=True)
            result = cmd_adopt(args)

        assert result == 0
        output = capsys.readouterr().out
        assert "Adopt Summary" in output

    @mock.patch("syncode.cli._apply_item_filter")
    @mock.patch("syncode.cli._resolve_item_filter")
    @mock.patch("syncode.cli._find_adopt_candidates")
    @mock.patch("syncode.cli._discover_targets")
    @mock.patch("syncode.cli._resolve_platforms")
    @mock.patch("syncode.cli._resolve_item_types")
    @mock.patch("syncode.cli._get_source")
    @mock.patch("syncode.config.SyncodeConfig.load")
    def test_adopt_failure_returns_1(
        self,
        mock_config_load: mock.MagicMock,
        mock_get_source: mock.MagicMock,
        mock_resolve_types: mock.MagicMock,
        mock_resolve_platforms: mock.MagicMock,
        mock_discover: mock.MagicMock,
        mock_find: mock.MagicMock,
        mock_resolve_filter: mock.MagicMock,
        mock_apply_filter: mock.MagicMock,
        tmp_path: Path,
    ) -> None:
        """When adopt engine fails, returns 1."""
        item = _make_item()

        engine = mock.MagicMock()
        report = mock.MagicMock()
        report.is_success = False
        report.success_count = 0
        report.summary.return_value = "0 adopted, 1 failed"
        engine.push.return_value = report

        mock_config_load.return_value = mock.MagicMock(cache_dir=None)
        mock_get_source.return_value = tmp_path
        mock_resolve_types.return_value = [ItemType.AGENT]
        mock_resolve_platforms.return_value = [Platform.OPENCODE]
        mock_discover.return_value = mock.MagicMock()
        mock_find.return_value = [item]
        mock_resolve_filter.return_value = (None, None)
        mock_apply_filter.return_value = [item]

        with mock.patch("syncode.engine.SyncEngine", return_value=engine):
            args = _make_args(non_interactive=True)
            result = cmd_adopt(args)

        assert result == 1
