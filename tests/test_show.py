"""Tests for the ``agentfiles show`` command."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import pytest

from syncode.cli import _COMMAND_MAP, build_parser, cmd_show
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
    item_name: str = "coder",
    source: str | None = None,
    fmt: str = "text",
) -> SimpleNamespace:
    return SimpleNamespace(
        command="show",
        item_name=item_name,
        source=source,
        format=fmt,
    )


# ---------------------------------------------------------------------------
# Parser tests
# ---------------------------------------------------------------------------


class TestShowParser:
    """Parser registration and flag parsing for show.

    Note: show only supports ``item_name`` (positional), ``--source``,
    and ``--format`` — no ``--yes``, ``--dry-run``, ``--target``, etc.
    """

    def test_registered(self) -> None:
        assert "show" in _COMMAND_MAP
        assert _COMMAND_MAP["show"] is cmd_show

    def test_item_name_required(self) -> None:
        """show requires an item_name positional argument."""
        args = build_parser().parse_args(["show", "coder"])
        assert args.item_name == "coder"

    def test_item_name_partial(self) -> None:
        """Partial names are accepted."""
        args = build_parser().parse_args(["show", "review"])
        assert args.item_name == "review"

    def test_source_flag(self) -> None:
        args = build_parser().parse_args(["show", "--source", "/repo", "coder"])
        assert args.source == "/repo"

    def test_format_json(self) -> None:
        args = build_parser().parse_args(["show", "--format", "json", "coder"])
        assert args.format == "json"

    def test_format_text_default(self) -> None:
        args = build_parser().parse_args(["show", "coder"])
        assert args.format == "text"

    def test_item_name_with_dashes(self) -> None:
        args = build_parser().parse_args(["show", "code-reviewer"])
        assert args.item_name == "code-reviewer"

    def test_missing_item_name_fails(self) -> None:
        """show without item_name raises SystemExit."""
        with pytest.raises(SystemExit):
            build_parser().parse_args(["show"])

    def test_source_default_none(self) -> None:
        args = build_parser().parse_args(["show", "coder"])
        assert args.source is None

    def test_combined_source_and_format(self) -> None:
        args = build_parser().parse_args(
            ["show", "--source", "/repo", "--format", "json", "agent"],
        )
        assert args.source == "/repo"
        assert args.format == "json"
        assert args.item_name == "agent"


# ---------------------------------------------------------------------------
# Integration tests
# ---------------------------------------------------------------------------


class TestCmdShowIntegration:
    """Integration tests for cmd_show with mocked dependencies."""

    @mock.patch("syncode.cli._get_source")
    def test_show_item_not_found(
        self,
        mock_get_source: mock.MagicMock,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """When item is not found, returns 1 (error goes to stderr)."""
        mock_get_source.return_value = tmp_path

        scanner = mock.MagicMock()
        scanner.scan.return_value = [
            _make_item(name="other-agent"),
        ]

        with mock.patch("syncode.scanner.SourceScanner", return_value=scanner):
            args = _make_args(item_name="nonexistent")
            result = cmd_show(args)

        assert result == 1
        captured = capsys.readouterr()
        # error() writes to stderr, info() to stdout
        assert "not found" in captured.err or "not found" in captured.out

    @mock.patch("syncode.cli._get_source")
    def test_show_ambiguous_match(
        self,
        mock_get_source: mock.MagicMock,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """When multiple items match, returns 1 and lists matches."""
        mock_get_source.return_value = tmp_path

        scanner = mock.MagicMock()
        scanner.scan.return_value = [
            _make_item(name="code-reviewer"),
            _make_item(name="code-stylist"),
        ]

        with mock.patch("syncode.scanner.SourceScanner", return_value=scanner):
            args = _make_args(item_name="code")
            result = cmd_show(args)

        assert result == 1
        output = capsys.readouterr().out
        assert "Multiple matches" in output

    @mock.patch("syncode.cli._get_source")
    def test_show_exact_match_text(
        self,
        mock_get_source: mock.MagicMock,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Exact match in text mode displays item content."""
        item = _make_item(name="coder")

        mock_get_source.return_value = tmp_path

        scanner = mock.MagicMock()
        scanner.scan.return_value = [item]

        with (
            mock.patch("syncode.scanner.SourceScanner", return_value=scanner),
            mock.patch("syncode.cli._display_item_content") as mock_display,
        ):
            args = _make_args(item_name="coder", fmt="text")
            result = cmd_show(args)

        assert result == 0
        mock_display.assert_called_once_with(item)

    @mock.patch("syncode.cli._get_source")
    def test_show_case_insensitive_match(
        self,
        mock_get_source: mock.MagicMock,
        tmp_path: Path,
    ) -> None:
        """Case-insensitive substring matching works."""
        item = _make_item(name="My-Agent")

        mock_get_source.return_value = tmp_path

        scanner = mock.MagicMock()
        scanner.scan.return_value = [item]

        with (
            mock.patch("syncode.scanner.SourceScanner", return_value=scanner),
            mock.patch("syncode.cli._display_item_content"),
        ):
            args = _make_args(item_name="my-agent")
            result = cmd_show(args)

        assert result == 0

    @mock.patch("syncode.cli._get_source")
    def test_show_json_output(
        self,
        mock_get_source: mock.MagicMock,
        tmp_path: Path,
    ) -> None:
        """JSON output calls _format_show_json with item data."""
        item = _make_item(name="coder")

        mock_get_source.return_value = tmp_path

        scanner = mock.MagicMock()
        scanner.scan.return_value = [item]

        with (
            mock.patch("syncode.scanner.SourceScanner", return_value=scanner),
            mock.patch(
                "syncode.paths.read_item_content",
                return_value=("content here", Path("/src/agents/coder.md")),
            ),
            mock.patch("syncode.cli._format_show_json", return_value=0) as mock_json,
        ):
            args = _make_args(item_name="coder", fmt="json")
            result = cmd_show(args)

        assert result == 0
        mock_json.assert_called_once()
