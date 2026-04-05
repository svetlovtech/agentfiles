"""Tests for the ``agentfiles diff`` command."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import pytest

from syncode.cli import _COMMAND_MAP, build_parser, cmd_diff
from syncode.models import DiffEntry, DiffStatus, Item, ItemType, Platform

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


def _make_diff_entry(
    status: DiffStatus,
    item: Item | None = None,
    source_checksum: str = "",
    target_checksum: str = "",
) -> DiffEntry:
    return DiffEntry(
        item=item or _make_item(),
        status=status,
        source_checksum=source_checksum,
        target_checksum=target_checksum,
    )


def _make_args(
    *,
    target: str | None = None,
    item_type: str | None = None,
    source: str | None = None,
    config: Path | None = None,
    cache_dir: str | None = None,
    fmt: str = "text",
    verbose_diff: bool = False,
    non_interactive: bool = True,
    dry_run: bool = False,
    only: str | None = None,
    except_items: str | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        command="diff",
        source=source,
        config=config,
        cache_dir=cache_dir,
        target=target,
        item_type=item_type,
        format=fmt,
        verbose_diff=verbose_diff,
        non_interactive=non_interactive,
        dry_run=dry_run,
        only=only,
        except_items=except_items,
    )


# ---------------------------------------------------------------------------
# Parser tests
# ---------------------------------------------------------------------------


class TestDiffParser:
    """Parser registration and flag parsing for diff."""

    def test_registered(self) -> None:
        assert "diff" in _COMMAND_MAP
        assert _COMMAND_MAP["diff"] is cmd_diff

    def test_target(self) -> None:
        args = build_parser().parse_args(["diff", "--target", "opencode"])
        assert args.target == "opencode"

    def test_type(self) -> None:
        args = build_parser().parse_args(["diff", "--type", "skill"])
        assert args.item_type == "skill"

    def test_format_json(self) -> None:
        args = build_parser().parse_args(["diff", "--format", "json"])
        assert args.format == "json"

    def test_format_text(self) -> None:
        args = build_parser().parse_args(["diff", "--format", "text"])
        assert args.format == "text"

    def test_verbose_flag(self) -> None:
        """--verbose stores as verbose_diff."""
        args = build_parser().parse_args(["diff", "--verbose"])
        assert args.verbose_diff is True

    def test_only(self) -> None:
        args = build_parser().parse_args(["diff", "--only", "coder"])
        assert args.only == "coder"

    def test_except(self) -> None:
        args = build_parser().parse_args(["diff", "--except", "test-*"])
        assert args.except_items == "test-*"

    def test_source_positional(self) -> None:
        args = build_parser().parse_args(["diff", "/path/to/repo"])
        assert args.source == "/path/to/repo"

    def test_config(self) -> None:
        args = build_parser().parse_args(["diff", "--config", "cfg.yaml"])
        assert args.config is not None

    def test_cache_dir(self) -> None:
        args = build_parser().parse_args(["diff", "--cache-dir", "/tmp"])
        assert args.cache_dir == "/tmp"

    def test_default_format(self) -> None:
        args = build_parser().parse_args(["diff"])
        assert args.format == "text"

    def test_default_no_verbose(self) -> None:
        args = build_parser().parse_args(["diff"])
        assert args.verbose_diff is False

    def test_all_targets(self) -> None:
        args = build_parser().parse_args(["diff", "--target", "all"])
        assert args.target == "all"

    def test_dry_run(self) -> None:
        args = build_parser().parse_args(["diff", "--dry-run"])
        assert args.dry_run is True

    def test_non_interactive(self) -> None:
        args = build_parser().parse_args(["diff", "--yes"])
        assert args.non_interactive is True


# ---------------------------------------------------------------------------
# Integration tests
# ---------------------------------------------------------------------------


class TestCmdDiffIntegration:
    """Integration tests for cmd_diff with mocked dependencies."""

    @mock.patch("syncode.cli._apply_item_filter")
    @mock.patch("syncode.cli._resolve_item_filter")
    @mock.patch("syncode.cli._scan_filtered")
    @mock.patch("syncode.cli._resolve_item_types")
    @mock.patch("syncode.cli._get_source")
    @mock.patch("syncode.config.SyncodeConfig.load")
    def test_diff_json_output(
        self,
        mock_config_load: mock.MagicMock,
        mock_get_source: mock.MagicMock,
        mock_resolve_types: mock.MagicMock,
        mock_scan: mock.MagicMock,
        mock_resolve_filter: mock.MagicMock,
        mock_apply_filter: mock.MagicMock,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """JSON diff output has correct structure."""
        item = _make_item()
        diff_results = {
            Platform.OPENCODE: [
                _make_diff_entry(DiffStatus.UNCHANGED, item, source_checksum="a" * 64),
            ],
        }

        mock_config_load.return_value = mock.MagicMock(cache_dir=None)
        mock_get_source.return_value = tmp_path
        mock_resolve_types.return_value = [ItemType.AGENT]
        mock_scan.return_value = [item]
        mock_resolve_filter.return_value = (None, None)
        mock_apply_filter.return_value = [item]

        with (
            mock.patch("syncode.cli._discover_targets"),
            mock.patch("syncode.cli._resolve_platforms", return_value=[Platform.OPENCODE]),
            mock.patch("syncode.differ.Differ") as mock_differ_cls,
            mock.patch("syncode.output.format_diff_json", return_value='{"items": []}'),
        ):
            mock_differ_cls.return_value.diff.return_value = diff_results

            args = _make_args(fmt="json")
            result = cmd_diff(args)

        assert result == 0
        output = capsys.readouterr().out
        parsed = json.loads(output)
        assert "items" in parsed

    @mock.patch("syncode.cli._apply_item_filter")
    @mock.patch("syncode.cli._resolve_item_filter")
    @mock.patch("syncode.cli._scan_filtered")
    @mock.patch("syncode.cli._resolve_item_types")
    @mock.patch("syncode.cli._get_source")
    @mock.patch("syncode.config.SyncodeConfig.load")
    def test_diff_text_output(
        self,
        mock_config_load: mock.MagicMock,
        mock_get_source: mock.MagicMock,
        mock_resolve_types: mock.MagicMock,
        mock_scan: mock.MagicMock,
        mock_resolve_filter: mock.MagicMock,
        mock_apply_filter: mock.MagicMock,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Text diff output uses format_diff for display."""
        item = _make_item()
        diff_results = {
            Platform.OPENCODE: [
                _make_diff_entry(DiffStatus.NEW, item),
            ],
        }

        mock_config_load.return_value = mock.MagicMock(cache_dir=None)
        mock_get_source.return_value = tmp_path
        mock_resolve_types.return_value = [ItemType.AGENT]
        mock_scan.return_value = [item]
        mock_resolve_filter.return_value = (None, None)
        mock_apply_filter.return_value = [item]

        with (
            mock.patch("syncode.cli._discover_targets"),
            mock.patch("syncode.cli._resolve_platforms", return_value=[Platform.OPENCODE]),
            mock.patch("syncode.differ.Differ") as mock_differ_cls,
            mock.patch("syncode.output.format_diff", return_value="diff output here"),
        ):
            mock_differ_cls.return_value.diff.return_value = diff_results

            args = _make_args(fmt="text")
            result = cmd_diff(args)

        assert result == 0
        output = capsys.readouterr().out
        assert "diff output here" in output

    @mock.patch("syncode.cli._apply_item_filter")
    @mock.patch("syncode.cli._resolve_item_filter")
    @mock.patch("syncode.cli._scan_filtered")
    @mock.patch("syncode.cli._resolve_item_types")
    @mock.patch("syncode.cli._get_source")
    @mock.patch("syncode.config.SyncodeConfig.load")
    def test_diff_no_items(
        self,
        mock_config_load: mock.MagicMock,
        mock_get_source: mock.MagicMock,
        mock_resolve_types: mock.MagicMock,
        mock_scan: mock.MagicMock,
        mock_resolve_filter: mock.MagicMock,
        mock_apply_filter: mock.MagicMock,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Diff with no items returns 0."""
        mock_config_load.return_value = mock.MagicMock(cache_dir=None)
        mock_get_source.return_value = tmp_path
        mock_resolve_types.return_value = [ItemType.AGENT]
        mock_scan.return_value = []
        mock_resolve_filter.return_value = (None, None)
        mock_apply_filter.return_value = []

        with (
            mock.patch("syncode.cli._discover_targets"),
            mock.patch("syncode.cli._resolve_platforms", return_value=[Platform.OPENCODE]),
            mock.patch("syncode.differ.Differ") as mock_differ_cls,
            mock.patch("syncode.output.format_diff", return_value="no differences"),
        ):
            mock_differ_cls.return_value.diff.return_value = {}
            args = _make_args(fmt="text")
            result = cmd_diff(args)

        assert result == 0
