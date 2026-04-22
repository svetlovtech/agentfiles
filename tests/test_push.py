"""Tests for the ``agentfiles push`` command."""

from __future__ import annotations

from types import SimpleNamespace
from unittest import mock

import pytest

from agentfiles.cli import _COMMAND_MAP, build_parser, cmd_push
from tests.conftest import make_args, make_item

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

    def test_cache_dir(self) -> None:
        args = build_parser().parse_args(["push", "--cache-dir", "/cache"])
        assert args.cache_dir == "/cache"


# ---------------------------------------------------------------------------
# Integration tests
# ---------------------------------------------------------------------------


class TestCmdPushIntegration:
    """Integration tests for cmd_push with mocked dependencies."""

    def test_push_no_installed_items(
        self,
        push_mocks: SimpleNamespace,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """When no installed items found, push returns 0."""
        push_mocks.discover.return_value = []
        push_mocks.apply_filter.return_value = []

        args = make_args(command="push", non_interactive=True)
        result = cmd_push(args)

        assert result == 0
        output = capsys.readouterr().out
        assert "No installed items" in output

    def test_push_non_interactive_success(
        self,
        push_mocks: SimpleNamespace,
    ) -> None:
        """Non-interactive push succeeds with installed items."""
        item = make_item()

        engine = mock.MagicMock()
        report = mock.MagicMock()
        report.is_success = True
        report.installed = []
        report.updated = []
        report.skipped = []
        report.failed = []
        report.summary.return_value = "1 pushed"
        engine.push.return_value = report

        push_mocks.pipeline.return_value = (mock.MagicMock(), mock.MagicMock(), engine)
        push_mocks.discover.return_value = [item]
        push_mocks.apply_filter.return_value = [item]

        args = make_args(command="push", non_interactive=True)
        result = cmd_push(args)

        assert result == 0
        engine.push.assert_called_once()

    def test_push_failure_returns_1(
        self,
        push_mocks: SimpleNamespace,
    ) -> None:
        """When push fails, returns 1."""
        item = make_item()

        engine = mock.MagicMock()
        report = mock.MagicMock()
        report.is_success = False
        report.installed = []
        report.updated = []
        report.skipped = []
        report.failed = [mock.MagicMock()]
        report.summary.return_value = "1 failed"
        engine.push.return_value = report

        push_mocks.pipeline.return_value = (mock.MagicMock(), mock.MagicMock(), engine)
        push_mocks.discover.return_value = [item]
        push_mocks.apply_filter.return_value = [item]

        args = make_args(command="push", non_interactive=True)
        result = cmd_push(args)

        assert result == 1

    def test_push_keyboard_interrupt_returns_1(
        self,
        push_mocks: SimpleNamespace,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Ctrl+C during interactive item selection aborts push and returns 1.

        Regression test: previously, KeyboardInterrupt was silently caught by
        ``InputParser.prompt()`` and treated as empty input (which selected all
        items).  Now it properly aborts the operation.
        """
        item = make_item()

        engine = mock.MagicMock()
        target_manager = mock.MagicMock()

        push_mocks.pipeline.return_value = (mock.MagicMock(), target_manager, engine)
        push_mocks.discover.return_value = [item]
        push_mocks.apply_filter.return_value = [item]

        # Interactive mode — user presses Ctrl+C at item selection.
        args = make_args(command="push", non_interactive=False)
        with mock.patch(
            "agentfiles.interactive.InputParser.prompt",
            side_effect=KeyboardInterrupt,
        ):
            result = cmd_push(args)

        assert result == 1
        # engine.push must NOT have been called — the user aborted.
        engine.push.assert_not_called()
        output = capsys.readouterr().out
        assert "Aborted" in output

    def test_push_dry_run_no_state_update(
        self,
        push_mocks: SimpleNamespace,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Dry-run push prints warning and does not modify files."""
        item = make_item()

        engine = mock.MagicMock()
        report = mock.MagicMock()
        report.is_success = True
        report.installed = []
        report.updated = []
        report.skipped = []
        report.failed = []
        report.summary.return_value = "1 pushed"
        engine.push.return_value = report

        push_mocks.pipeline.return_value = (mock.MagicMock(), mock.MagicMock(), engine)
        push_mocks.discover.return_value = [item]
        push_mocks.apply_filter.return_value = [item]

        args = make_args(command="push", non_interactive=True, dry_run=True)
        result = cmd_push(args)

        assert result == 0
        output = capsys.readouterr().out
        assert "Dry-run" in output
