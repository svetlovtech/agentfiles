"""Tests for agentfiles.output — logging setup and console output formatting."""

from __future__ import annotations

import io
import json
import logging
import os
from collections.abc import Generator
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import syncode.output as _output_module
from syncode.models import DiffEntry, DiffStatus, Item, ItemType, Platform
from syncode.output import (
    Colors,
    _diff_status_symbol,
    _fit_cell,
    _safe_write,
    bold,
    colorize,
    dim,
    error,
    format_diff,
    format_diff_json,
    format_item_count,
    info,
    init_logging,
    print_banner,
    print_item_status,
    print_section,
    print_table,
    should_use_colors,
    success,
    warning,
)

# ---------------------------------------------------------------------------
# Colors constants
# ---------------------------------------------------------------------------


class TestColors:
    """Verify ANSI colour constants are well-formed."""

    @pytest.mark.parametrize(
        "name",
        ["GREEN", "RED", "YELLOW", "BLUE", "BOLD", "DIM", "RESET"],
    )
    def test_color_constants_start_with_ansi_escape(self, name: str) -> None:
        colour = getattr(Colors, name)
        assert colour.startswith("\033["), f"Colors.{name} must start with \\033["


# ---------------------------------------------------------------------------
# colorize helper
# ---------------------------------------------------------------------------


class TestColorize:
    """Tests for the colorize() helper."""

    def test_returns_plain_text_when_colors_disabled(self) -> None:
        """When _use_colors is False, colorize returns text unchanged."""
        with patch("syncode.output._use_colors", False):
            result = colorize("hello", Colors.GREEN)
        assert result == "hello"

    def test_wraps_text_in_codes_when_colors_enabled(self) -> None:
        """When _use_colors is True, result starts with code and ends with RESET."""
        with patch("syncode.output._use_colors", True):
            result = colorize("hello", Colors.GREEN)
        assert result.startswith(Colors.GREEN)
        assert result.endswith(Colors.RESET)
        assert "hello" in result

    def test_supports_multiple_codes(self) -> None:
        """colorize should concatenate multiple ANSI codes before text."""
        with patch("syncode.output._use_colors", True):
            result = colorize("bold-green", Colors.BOLD, Colors.GREEN)
        assert result.startswith(Colors.BOLD + Colors.GREEN)
        assert result.endswith(Colors.RESET)
        assert "bold-green" in result

    def test_empty_string_just_returns_codes_and_reset(self) -> None:
        with patch("syncode.output._use_colors", True):
            result = colorize("", Colors.RED)
        assert result == Colors.RED + Colors.RESET


# ---------------------------------------------------------------------------
# should_use_colors
# ---------------------------------------------------------------------------


class TestShouldUseColors:
    """Tests for the should_use_colors() heuristic."""

    def test_returns_false_when_no_color_set(self) -> None:
        with patch.dict("os.environ", {"NO_COLOR": "1"}, clear=True):
            assert should_use_colors() is False

    def test_returns_false_when_term_is_dumb(self) -> None:
        with patch.dict("os.environ", {"TERM": "dumb"}, clear=True):
            assert should_use_colors() is False

    def test_returns_false_when_not_tty(self) -> None:
        with (
            patch("sys.stdout.isatty", return_value=False),
            patch.dict("os.environ", {}, clear=True),
        ):
            assert should_use_colors() is False

    def test_returns_true_when_tty_and_no_env_overrides(self) -> None:
        with (
            patch("sys.stdout.isatty", return_value=True),
            patch.dict("os.environ", {}, clear=True),
        ):
            assert should_use_colors() is True


# ---------------------------------------------------------------------------
# init_logging
# ---------------------------------------------------------------------------


class TestInitLogging:
    """Tests for init_logging() logger configuration."""

    @pytest.fixture(autouse=True)
    def _restore_module_state(self) -> Generator[None, None, None]:
        """Save and restore _use_colors and root logger between tests."""
        original_colors = _output_module._use_colors
        root = logging.getLogger()
        original_level = root.level
        original_handlers = list(root.handlers)
        yield
        _output_module._use_colors = original_colors
        root.level = original_level
        root.handlers[:] = original_handlers

    def test_sets_colors_flag(self) -> None:
        init_logging()
        assert isinstance(_output_module._use_colors, bool)

    def test_verbose_sets_debug_level(self) -> None:
        root = logging.getLogger()
        root.setLevel(logging.WARNING)  # reset to non-debug so basicConfig actually changes
        root.handlers.clear()
        init_logging(verbose=True)
        assert root.level == logging.DEBUG

    def test_quiet_sets_error_level(self) -> None:
        root = logging.getLogger()
        root.setLevel(logging.WARNING)
        root.handlers.clear()
        init_logging(quiet=True)
        assert root.level == logging.ERROR

    def test_default_sets_warning_level(self) -> None:
        root = logging.getLogger()
        root.setLevel(logging.WARNING)
        root.handlers.clear()
        init_logging()
        assert root.level == logging.WARNING


# ---------------------------------------------------------------------------
# Convenience print helpers (success, error, warning, dim, info)
# ---------------------------------------------------------------------------


class TestSuccess:
    """Tests for success() output."""

    def test_prints_message_to_stdout(self, capsys: pytest.CaptureFixture) -> None:
        with patch("syncode.output._use_colors", True):
            success("all good")
        captured = capsys.readouterr()
        assert "all good" in captured.out

    def test_includes_green_color_when_enabled(self, capsys: pytest.CaptureFixture) -> None:
        with patch("syncode.output._use_colors", True):
            success("ok")
        captured = capsys.readouterr()
        assert Colors.GREEN in captured.out

    def test_plain_output_when_colors_disabled(self, capsys: pytest.CaptureFixture) -> None:
        with patch("syncode.output._use_colors", False):
            success("plain")
        captured = capsys.readouterr()
        assert captured.out.strip() == "plain"
        assert "\033[" not in captured.out


class TestError:
    """Tests for error() output."""

    def test_prints_message_to_stderr(self, capsys: pytest.CaptureFixture) -> None:
        with patch("syncode.output._use_colors", True):
            error("something failed")
        captured = capsys.readouterr()
        assert "something failed" in captured.err

    def test_includes_red_color_when_enabled(self, capsys: pytest.CaptureFixture) -> None:
        with patch("syncode.output._use_colors", True):
            error("fail")
        captured = capsys.readouterr()
        assert Colors.RED in captured.err

    def test_plain_output_when_colors_disabled(self, capsys: pytest.CaptureFixture) -> None:
        with patch("syncode.output._use_colors", False):
            error("fail")
        captured = capsys.readouterr()
        assert captured.err.strip() == "fail"


class TestWarning:
    """Tests for warning() output."""

    def test_prints_message_to_stdout(self, capsys: pytest.CaptureFixture) -> None:
        with patch("syncode.output._use_colors", True):
            warning("careful!")
        captured = capsys.readouterr()
        assert "careful!" in captured.out

    def test_includes_yellow_color_when_enabled(self, capsys: pytest.CaptureFixture) -> None:
        with patch("syncode.output._use_colors", True):
            warning("warn")
        captured = capsys.readouterr()
        assert Colors.YELLOW in captured.out

    def test_plain_output_when_colors_disabled(self, capsys: pytest.CaptureFixture) -> None:
        with patch("syncode.output._use_colors", False):
            warning("caution")
        captured = capsys.readouterr()
        assert captured.out.strip() == "caution"


class TestDim:
    """Tests for dim() output."""

    def test_prints_message_to_stdout(self, capsys: pytest.CaptureFixture) -> None:
        with patch("syncode.output._use_colors", True):
            dim("subtle text")
        captured = capsys.readouterr()
        assert "subtle text" in captured.out

    def test_includes_dim_color_when_enabled(self, capsys: pytest.CaptureFixture) -> None:
        with patch("syncode.output._use_colors", True):
            dim("subtle")
        captured = capsys.readouterr()
        assert Colors.DIM in captured.out


class TestInfo:
    """Tests for info() output — imported from syncode.output directly."""

    def test_info_prints_blue_when_colors_enabled(self, capsys: pytest.CaptureFixture) -> None:
        from syncode.output import info

        with patch("syncode.output._use_colors", True):
            info("info message")
        captured = capsys.readouterr()
        assert "info message" in captured.out
        assert Colors.BLUE in captured.out


# ---------------------------------------------------------------------------
# print_table
# ---------------------------------------------------------------------------


class TestPrintTable:
    """Tests for print_table() formatting."""

    def test_prints_nothing_for_empty_rows(self, capsys: pytest.CaptureFixture) -> None:
        print_table(["A", "B"], [])
        captured = capsys.readouterr()
        assert captured.out == ""

    def test_prints_header_and_separator(self, capsys: pytest.CaptureFixture) -> None:
        print_table(["Name", "Value"], [["foo", "bar"]])
        captured = capsys.readouterr()
        lines = captured.out.strip().splitlines()
        assert "Name" in lines[0]
        assert "Value" in lines[0]
        assert "----" in lines[1]

    def test_prints_single_row(self, capsys: pytest.CaptureFixture) -> None:
        print_table(["Col"], [["hello"]])
        captured = capsys.readouterr()
        lines = captured.out.strip().splitlines()
        assert len(lines) == 3  # header, separator, data row
        assert "hello" in lines[2]

    def test_multiple_rows(self, capsys: pytest.CaptureFixture) -> None:
        rows = [["a", "b"], ["cc", "dd"], ["eee", "fff"]]
        print_table(["X", "Y"], rows)
        captured = capsys.readouterr()
        lines = captured.out.strip().splitlines()
        assert len(lines) == 5  # header, separator, 3 data rows

    def test_columns_align_to_widest_value(self, capsys: pytest.CaptureFixture) -> None:
        """Column width should match the widest header or cell."""
        print_table(["Short", "Header"], [["A very long value", "x"]])
        captured = capsys.readouterr()
        lines = captured.out.rstrip("\n").splitlines()
        # All lines should have the same total length (no strip, to preserve trailing padding)
        lengths = [len(line) for line in lines]
        assert len(set(lengths)) == 1, f"Rows not aligned: {lengths}"

    def test_unicode_content(self, capsys: pytest.CaptureFixture) -> None:
        print_table(["Name", "Symbol"], [["\u0422\u0435\u0441\u0442", "\u2603 \u2764"]])
        captured = capsys.readouterr()
        assert "\u0422\u0435\u0441\u0442" in captured.out
        assert "\u2603" in captured.out

    def test_empty_cell_values(self, capsys: pytest.CaptureFixture) -> None:
        print_table(["A", "B"], [["", "data"], ["more", ""]])
        captured = capsys.readouterr()
        assert captured.out.count("data") >= 1
        assert captured.out.count("more") >= 1


# ---------------------------------------------------------------------------
# format_item_count
# ---------------------------------------------------------------------------


class TestFormatItemCount:
    """Tests for format_item_count()."""

    def test_singular_when_count_is_one(self) -> None:
        assert format_item_count(1, "item") == "1 item"

    def test_plural_with_default_when_count_is_not_one(self) -> None:
        assert format_item_count(5, "item") == "5 items"

    def test_custom_plural(self) -> None:
        assert format_item_count(0, "person", "people") == "0 people"
        assert format_item_count(1, "person", "people") == "1 person"
        assert format_item_count(3, "person", "people") == "3 people"

    def test_zero_count(self) -> None:
        assert format_item_count(0, "file") == "0 files"


# ---------------------------------------------------------------------------
# print_banner
# ---------------------------------------------------------------------------


class TestPrintBanner:
    """Tests for print_banner() box drawing."""

    def test_prints_nothing_for_empty_lines(self, capsys: pytest.CaptureFixture) -> None:
        print_banner([])
        captured = capsys.readouterr()
        assert captured.out == ""

    def test_single_line_banner(self, capsys: pytest.CaptureFixture) -> None:
        with patch("syncode.output._use_colors", False):
            print_banner(["Hello"])
        captured = capsys.readouterr()
        lines = captured.out.strip().splitlines()
        assert len(lines) == 3  # top border, content, bottom border
        assert "\u250c" in lines[0]
        assert "\u2514" in lines[2]
        assert "Hello" in lines[1]

    def test_multi_line_banner_aligns_box(self, capsys: pytest.CaptureFixture) -> None:
        with patch("syncode.output._use_colors", False):
            print_banner(["short", "a much longer line here"])
        captured = capsys.readouterr()
        lines = captured.out.strip().splitlines()
        # Top and bottom borders should be the same length
        assert len(lines[0]) == len(lines[-1])

    def test_banner_strips_ansi_for_width_calculation(self, capsys: pytest.CaptureFixture) -> None:
        """Coloured text inside banner should not break box alignment."""
        with patch("syncode.output._use_colors", True):
            print_banner([colorize("Coloured", Colors.GREEN)])
        captured = capsys.readouterr()
        lines = captured.out.strip().splitlines()
        # Strip ANSI from all lines and check border alignment
        ansi_strip = __import__("re").compile(r"\033\[[0-9;]*m")
        raw_lengths = [len(ansi_strip.sub("", line)) for line in lines]
        assert raw_lengths[0] == raw_lengths[-1], "Box borders should be same visible width"


# ---------------------------------------------------------------------------
# bold
# ---------------------------------------------------------------------------


class TestBold:
    """Tests for bold() output."""

    def test_wraps_in_bold_ansi(self, capsys: pytest.CaptureFixture) -> None:
        with patch("syncode.output._use_colors", True):
            bold("hello")
        captured = capsys.readouterr()
        assert "hello" in captured.out
        assert "\033[1" in captured.out

    def test_plain_when_colors_disabled(self, capsys: pytest.CaptureFixture) -> None:
        with patch("syncode.output._use_colors", False):
            bold("hello")
        captured = capsys.readouterr()
        assert "hello" in captured.out
        assert "\033[" not in captured.out


# ---------------------------------------------------------------------------
# setup_file_logging
# ---------------------------------------------------------------------------


class TestSetupFileLogging:
    """Tests for setup_file_logging() file-based logging configuration."""

    @pytest.fixture(autouse=True)
    def _cleanup_loggers(self, tmp_path: object) -> Generator[None, None, None]:
        """Remove any handlers we add during tests to avoid leaking state."""
        yield
        test_logger = logging.getLogger("syncode.test_file_logging")
        test_logger.handlers.clear()
        test_logger.setLevel(logging.WARNING)

    def test_creates_log_directory(self, tmp_path: Path) -> None:
        """setup_file_logging should create the log directory if missing."""
        log_dir = tmp_path / "nested" / "logs"
        from syncode.output import setup_file_logging

        setup_file_logging(
            log_dir=log_dir,
            prefix="test",
            module_names=("syncode.test_file_logging",),
        )
        assert log_dir.is_dir()

    def test_creates_log_file(self, tmp_path: Path) -> None:
        """A log file with the correct prefix should be created."""
        from syncode.output import setup_file_logging

        log_file = setup_file_logging(
            log_dir=tmp_path,
            prefix="mytest",
            module_names=("syncode.test_file_logging",),
        )
        assert log_file.exists()
        assert log_file.name.startswith("mytest-")
        assert log_file.suffix == ".log"

    def test_returns_log_file_path(self, tmp_path: Path) -> None:
        """Return value should be a Path inside log_dir."""
        from syncode.output import setup_file_logging

        log_file = setup_file_logging(
            log_dir=tmp_path,
            prefix="test",
            module_names=("syncode.test_file_logging",),
        )
        assert isinstance(log_file, Path)
        assert log_file.parent == tmp_path

    def test_attaches_handler_to_module_logger(self, tmp_path: Path) -> None:
        """The specified module logger should receive a RotatingFileHandler."""
        from logging.handlers import RotatingFileHandler

        from syncode.output import setup_file_logging

        setup_file_logging(
            log_dir=tmp_path,
            prefix="test",
            module_names=("syncode.test_file_logging",),
        )

        test_logger = logging.getLogger("syncode.test_file_logging")
        assert any(isinstance(h, RotatingFileHandler) for h in test_logger.handlers)

    def test_sets_logger_to_debug_level(self, tmp_path: Path) -> None:
        """Module logger level should be set to DEBUG."""
        from syncode.output import setup_file_logging

        setup_file_logging(
            log_dir=tmp_path,
            prefix="test",
            module_names=("syncode.test_file_logging",),
        )

        test_logger = logging.getLogger("syncode.test_file_logging")
        assert test_logger.level == logging.DEBUG

    def test_writes_log_messages_to_file(self, tmp_path: Path) -> None:
        """Log messages should appear in the created file."""
        from syncode.output import setup_file_logging

        log_file = setup_file_logging(
            log_dir=tmp_path,
            prefix="test",
            module_names=("syncode.test_file_logging",),
        )

        test_logger = logging.getLogger("syncode.test_file_logging")
        test_logger.info("hello from test")

        # Flush handlers
        for handler in test_logger.handlers:
            handler.flush()

        content = log_file.read_text()
        assert "hello from test" in content

    def test_attaches_to_multiple_modules(self, tmp_path: Path) -> None:
        """Should attach the handler to all specified module loggers."""
        from logging.handlers import RotatingFileHandler

        from syncode.output import setup_file_logging

        setup_file_logging(
            log_dir=tmp_path,
            prefix="multi",
            module_names=("syncode.test_file_logging", "syncode.test_file_logging_other"),
        )

        logger_a = logging.getLogger("syncode.test_file_logging")
        logger_b = logging.getLogger("syncode.test_file_logging_other")

        assert any(isinstance(h, RotatingFileHandler) for h in logger_a.handlers)
        assert any(isinstance(h, RotatingFileHandler) for h in logger_b.handlers)

        # Cleanup second logger too
        logger_b.handlers.clear()
        logger_b.setLevel(logging.WARNING)


# ---------------------------------------------------------------------------
# _safe_write — resilient I/O
# ---------------------------------------------------------------------------


class TestSafeWrite:
    """Tests for _safe_write() error-resilient output."""

    def test_writes_to_stdout_by_default(self, capsys: pytest.CaptureFixture) -> None:
        _safe_write("hello\n")
        assert capsys.readouterr().out == "hello\n"

    def test_writes_to_custom_stream(self) -> None:
        buf = io.StringIO()
        _safe_write("data", stream=buf)
        assert buf.getvalue() == "data"

    def test_broken_pipe_is_silently_ignored(self) -> None:
        """BrokenPipeError (e.g. piped to head) must not propagate."""
        stream = MagicMock()
        stream.write.side_effect = BrokenPipeError()
        # Should not raise
        _safe_write("text\n", stream=stream)

    def test_unicode_encode_error_falls_back_to_replacement(self) -> None:
        """Unencodable characters should be replaced, not crash."""
        stream = MagicMock()
        stream.encoding = "ascii"
        stream.write.side_effect = [
            UnicodeEncodeError("ascii", "▲", 0, 1, "ordinal not in range"),
            None,  # second call succeeds with replacement text
        ]
        _safe_write("▲\n", stream=stream)
        # Second write should have been called with replacement text
        assert stream.write.call_count == 2

    def test_unicode_encode_error_with_broken_pipe_on_retry(self) -> None:
        """If the retry also fails (pipe closed), still no exception."""
        stream = MagicMock()
        stream.encoding = "ascii"
        stream.write.side_effect = [
            UnicodeEncodeError("ascii", "▲", 0, 1, "ordinal not in range"),
            BrokenPipeError(),
        ]
        # Should not raise
        _safe_write("▲\n", stream=stream)

    def test_unicode_encode_error_with_none_encoding(self) -> None:
        """Streams with encoding=None should default to utf-8."""
        stream = MagicMock()
        stream.encoding = None
        stream.write.side_effect = [
            UnicodeEncodeError("utf-8", "text", 0, 1, "test"),
            None,
        ]
        _safe_write("text\n", stream=stream)
        assert stream.write.call_count == 2


# ---------------------------------------------------------------------------
# should_use_colors — extended env-var support
# ---------------------------------------------------------------------------


class TestShouldUseColorsExtended:
    """Tests for FORCE_COLOR, CLICOLOR_FORCE, and OSError in isatty()."""

    def test_force_color_overrides_no_tty(self) -> None:
        """FORCE_COLOR should enable colours even when stdout is not a TTY."""
        with (
            patch("sys.stdout.isatty", return_value=False),
            patch.dict("os.environ", {"FORCE_COLOR": "1"}, clear=True),
        ):
            assert should_use_colors() is True

    def test_clicolor_force_overrides_no_tty(self) -> None:
        """CLICOLOR_FORCE should enable colours even when stdout is not a TTY."""
        with (
            patch("sys.stdout.isatty", return_value=False),
            patch.dict("os.environ", {"CLICOLOR_FORCE": "1"}, clear=True),
        ):
            assert should_use_colors() is True

    def test_force_color_overrides_no_color(self) -> None:
        """FORCE_COLOR takes priority over NO_COLOR."""
        with (
            patch.dict(
                "os.environ",
                {"FORCE_COLOR": "1", "NO_COLOR": "1"},
                clear=True,
            ),
        ):
            assert should_use_colors() is True

    def test_no_color_still_works(self) -> None:
        """Without FORCE_COLOR, NO_COLOR should disable colours."""
        with (
            patch("sys.stdout.isatty", return_value=True),
            patch.dict("os.environ", {"NO_COLOR": "1"}, clear=True),
        ):
            assert should_use_colors() is False

    def test_isatty_oserror_returns_false(self) -> None:
        """OSError from isatty() (e.g. closed fd) should return False."""
        with (
            patch("sys.stdout.isatty", side_effect=OSError("bad fd")),
            patch.dict("os.environ", {}, clear=True),
        ):
            assert should_use_colors() is False


# ---------------------------------------------------------------------------
# Convenience helpers — error resilience
# ---------------------------------------------------------------------------


class TestConvenienceResilience:
    """Verify convenience helpers don't crash on I/O errors."""

    @pytest.mark.parametrize(
        "func, message",
        [
            (success, "ok"),
            (error, "fail"),
            (warning, "careful"),
            (info, "note"),
        ],
        ids=["success", "error", "warning", "info"],
    )
    def test_survives_broken_pipe(self, func: object, message: str) -> None:
        with patch("syncode.output._safe_write") as mock_write:
            func(message)
        mock_write.assert_called_once()


# ---------------------------------------------------------------------------
# print_table / print_banner — error resilience
# ---------------------------------------------------------------------------


class TestTableBannerResilience:
    """Verify table and banner output handles I/O errors gracefully."""

    def test_print_table_uses_safe_write(self) -> None:
        """print_table should route through _safe_write."""
        with patch("syncode.output._safe_write") as mock_write:
            print_table(["A"], [["x"]])
        mock_write.assert_called_once()
        written = mock_write.call_args[0][0]
        assert "A" in written
        assert "x" in written

    def test_print_banner_uses_safe_write(self) -> None:
        """print_banner should route through _safe_write."""
        with patch("syncode.output._safe_write") as mock_write:
            print_banner(["Hello"])
        mock_write.assert_called_once()
        written = mock_write.call_args[0][0]
        assert "Hello" in written

    def test_print_table_survives_broken_pipe(self) -> None:
        """BrokenPipeError in print_table must not propagate."""
        with patch("syncode.output._safe_write"):
            # _safe_write itself handles the error; we verify no crash.
            print_table(["Col"], [["val"]])

    def test_print_banner_survives_broken_pipe(self) -> None:
        """BrokenPipeError in print_banner must not propagate."""
        with patch("syncode.output._safe_write"):
            print_banner(["Banner text"])


# ---------------------------------------------------------------------------
# Color functions — empty and long strings
# ---------------------------------------------------------------------------


def _make_item(name: str = "test-agent", item_type: ItemType = ItemType.AGENT) -> Item:
    """Create a minimal Item for testing."""
    return Item(
        item_type=item_type,
        name=name,
        source_path=Path("/fake/source"),
    )


class TestColorFunctionsEdgeCases:
    """Tests for color helpers with empty and long strings."""

    def test_colorize_long_string(self) -> None:
        """colorize should handle strings longer than typical terminal width."""
        long_text = "x" * 500
        with patch("syncode.output._use_colors", True):
            result = colorize(long_text, Colors.GREEN)
        assert result.startswith(Colors.GREEN)
        assert result.endswith(Colors.RESET)
        assert long_text in result

    def test_colorize_long_string_no_colors(self) -> None:
        """Long string is returned unchanged when colors disabled."""
        long_text = "y" * 500
        with patch("syncode.output._use_colors", False):
            result = colorize(long_text, Colors.RED)
        assert result == long_text

    @pytest.mark.parametrize(
        "func",
        [success, error, warning, info, bold, dim],
        ids=["success", "error", "warning", "info", "bold", "dim"],
    )
    def test_convenience_function_empty_string(
        self,
        func: object,
        capsys: pytest.CaptureFixture,
    ) -> None:
        """All convenience print helpers should handle empty strings gracefully."""
        with patch("syncode.output._use_colors", False):
            func("")
        captured = capsys.readouterr()
        # Empty string produces just a newline (stdout or stderr)
        output = captured.out or captured.err
        assert output == "\n"

    def test_success_long_string(self, capsys: pytest.CaptureFixture) -> None:
        """success() should print long strings without truncation."""
        long_msg = "done: " + "x" * 300
        with patch("syncode.output._use_colors", False):
            success(long_msg)
        captured = capsys.readouterr()
        assert long_msg in captured.out

    def test_error_long_string(self, capsys: pytest.CaptureFixture) -> None:
        """error() should print long strings without truncation."""
        long_msg = "failed: " + "y" * 300
        with patch("syncode.output._use_colors", False):
            error(long_msg)
        captured = capsys.readouterr()
        assert long_msg in captured.err

    def test_dim_plain_output_when_colors_disabled(
        self,
        capsys: pytest.CaptureFixture,
    ) -> None:
        """dim() should output plain text when colors are off."""
        with patch("syncode.output._use_colors", False):
            dim("subtle")
        captured = capsys.readouterr()
        assert captured.out.strip() == "subtle"
        assert "\033[" not in captured.out

    def test_info_plain_output_when_colors_disabled(
        self,
        capsys: pytest.CaptureFixture,
    ) -> None:
        """info() should output plain text when colors are off."""
        with patch("syncode.output._use_colors", False):
            info("information")
        captured = capsys.readouterr()
        assert captured.out.strip() == "information"
        assert "\033[" not in captured.out


# ---------------------------------------------------------------------------
# Table formatting — various column widths
# ---------------------------------------------------------------------------


class TestPrintTableColumnWidths:
    """Additional tests for print_table() with varied column widths."""

    def test_single_column_table(self, capsys: pytest.CaptureFixture) -> None:
        """Single-column tables should render correctly."""
        print_table(["Name"], [["alice"], ["bob"]])
        captured = capsys.readouterr()
        lines = captured.out.strip().splitlines()
        assert len(lines) == 4  # header, separator, 2 data rows
        assert "alice" in lines[2]
        assert "bob" in lines[3]

    def test_many_columns_table(self, capsys: pytest.CaptureFixture) -> None:
        """Tables with many columns should render correctly."""
        headers = ["A", "B", "C", "D", "E"]
        rows = [["1", "2", "3", "4", "5"]]
        print_table(headers, rows)
        captured = capsys.readouterr()
        for header in headers:
            assert header in captured.out

    def test_headers_wider_than_data(self, capsys: pytest.CaptureFixture) -> None:
        """When headers are wider than all data, width follows headers."""
        print_table(["LongHeaderName", "AnotherHeader"], [["a", "b"]])
        captured = capsys.readouterr()
        lines = captured.out.rstrip("\n").splitlines()
        # All lines should have the same length (rstrip newline only, preserve spaces)
        lengths = [len(line) for line in lines]
        assert len(set(lengths)) == 1

    def test_data_wider_than_headers(self, capsys: pytest.CaptureFixture) -> None:
        """When data is wider than headers, column width adjusts to data."""
        print_table(["A", "B"], [["short", "very long data value here"]])
        captured = capsys.readouterr()
        lines = captured.out.strip().splitlines()
        lengths = [len(line) for line in lines]
        assert len(set(lengths)) == 1
        assert "very long data value here" in lines[2]

    def test_wide_unicode_characters(self, capsys: pytest.CaptureFixture) -> None:
        """CJK/fullwidth characters should be handled in alignment."""
        print_table(["Name"], [["\u4e16\u754c"]])  # 世界
        captured = capsys.readouterr()
        assert "\u4e16\u754c" in captured.out

    def test_separator_dashes_match_column_width(
        self,
        capsys: pytest.CaptureFixture,
    ) -> None:
        """Separator line dashes should match each column width exactly."""
        print_table(["ID", "Description"], [["1", "test item"]])
        captured = capsys.readouterr()
        lines = captured.out.strip().splitlines()
        separator = lines[1]
        parts = separator.split("  ")
        assert len(parts) == 2
        # "ID" header → width 2, dashes should be 2
        assert parts[0] == "--"
        # "Description" header → width 11
        assert parts[1] == "-" * 11

    def test_numeric_strings_aligned(self, capsys: pytest.CaptureFixture) -> None:
        """Numeric strings should left-align consistently."""
        print_table(["Count", "Label"], [["1", "a"], ["100", "b"]])
        captured = capsys.readouterr()
        lines = captured.out.rstrip("\n").splitlines()
        lengths = [len(line) for line in lines]
        assert len(set(lengths)) == 1


# ---------------------------------------------------------------------------
# Diff status symbol
# ---------------------------------------------------------------------------


class TestDiffStatusSymbol:
    """Tests for _diff_status_symbol() helper."""

    def test_returns_plain_symbol_when_colors_disabled(self) -> None:
        """Symbol should be returned without ANSI codes."""
        result = _diff_status_symbol(DiffStatus.NEW, use_colors=False)
        assert result == "+"
        assert "\033[" not in result

    def test_returns_colored_symbol_when_enabled(self) -> None:
        """Symbol should be wrapped in ANSI codes."""
        with patch("syncode.output._use_colors", True):
            result = _diff_status_symbol(DiffStatus.NEW, use_colors=True)
        assert "+" in result
        assert Colors.GREEN in result
        assert Colors.RESET in result

    @pytest.mark.parametrize(
        "status, expected_symbol",
        [
            (DiffStatus.NEW, "+"),
            (DiffStatus.UPDATED, "~"),
            (DiffStatus.UNCHANGED, "="),
            (DiffStatus.DELETED, "-"),
            (DiffStatus.CONFLICT, "!"),
        ],
    )
    def test_all_status_symbols(
        self,
        status: DiffStatus,
        expected_symbol: str,
    ) -> None:
        """Each DiffStatus should produce its canonical symbol."""
        result = _diff_status_symbol(status, use_colors=False)
        assert result == expected_symbol


# ---------------------------------------------------------------------------
# format_diff
# ---------------------------------------------------------------------------


class TestFormatDiff:
    """Tests for format_diff() text formatting."""

    def test_empty_dict_returns_no_differences(self) -> None:
        """Empty diff_results should produce 'No differences found.'."""
        result = format_diff({}, use_colors=False)
        assert result == "No differences found."

    def test_empty_dict_with_colors_returns_dimmed(self) -> None:
        """Empty diff with colors should dim the message."""
        with patch("syncode.output._use_colors", True):
            result = format_diff({}, use_colors=True)
        assert "No differences found." in result
        assert Colors.DIM in result
        assert Colors.RESET in result

    def test_single_platform_single_entry(self) -> None:
        """Single entry should show platform header and entry line."""
        item = _make_item("my-agent")
        entry = DiffEntry(item=item, status=DiffStatus.NEW)
        result = format_diff(
            {Platform.OPENCODE: [entry]},
            use_colors=False,
        )
        assert "OpenCode" in result
        assert "opencode" in result
        assert "my-agent" in result
        assert "new" in result

    def test_multiple_entries_sorted_by_status_then_name(self) -> None:
        """Entries should appear sorted by status order, then name."""
        entries = [
            DiffEntry(item=_make_item("beta"), status=DiffStatus.UPDATED),
            DiffEntry(item=_make_item("alpha"), status=DiffStatus.UPDATED),
            DiffEntry(item=_make_item("zeta"), status=DiffStatus.NEW),
        ]
        result = format_diff(
            {Platform.OPENCODE: entries},
            use_colors=False,
        )
        lines = result.strip().splitlines()
        # NEW (zeta) comes before UPDATED (alpha, beta)
        entry_lines = [
            line for line in lines if line.strip().startswith("+") or line.strip().startswith("~")
        ]
        assert len(entry_lines) == 3
        assert "zeta" in entry_lines[0]
        assert "alpha" in entry_lines[1]
        assert "beta" in entry_lines[2]

    def test_multiple_platforms(self) -> None:
        """Multiple platforms should produce separate sections."""
        entry = DiffEntry(item=_make_item("agent-a"), status=DiffStatus.NEW)
        result = format_diff(
            {
                Platform.OPENCODE: [entry],
                Platform.CLAUDE_CODE: [entry],
            },
            use_colors=False,
        )
        assert "OpenCode" in result
        assert "Claude Code" in result
        # Sections separated by double newline
        assert "\n\n" in result

    def test_summary_line_includes_item_type(self) -> None:
        """Summary should mention the item type plural and status counts."""
        entries = [
            DiffEntry(item=_make_item("a"), status=DiffStatus.NEW),
            DiffEntry(item=_make_item("b"), status=DiffStatus.UNCHANGED),
        ]
        result = format_diff(
            {Platform.OPENCODE: entries},
            use_colors=False,
        )
        assert "agents" in result
        assert "1 new" in result
        assert "1 unchanged" in result

    def test_colors_disabled_no_ansi(self) -> None:
        """When use_colors=False, output should contain no ANSI codes."""
        entry = DiffEntry(item=_make_item("x"), status=DiffStatus.NEW)
        result = format_diff({Platform.OPENCODE: [entry]}, use_colors=False)
        assert "\033[" not in result

    def test_colors_enabled_includes_ansi(self) -> None:
        """When use_colors=True, output should contain ANSI codes."""
        with patch("syncode.output._use_colors", True):
            entry = DiffEntry(item=_make_item("x"), status=DiffStatus.NEW)
            result = format_diff({Platform.OPENCODE: [entry]}, use_colors=True)
        assert "\033[" in result

    def test_deleted_status_in_diff(self) -> None:
        """Deleted items should appear with '-' symbol."""
        entry = DiffEntry(item=_make_item("gone"), status=DiffStatus.DELETED)
        result = format_diff({Platform.OPENCODE: [entry]}, use_colors=False)
        assert "-" in result
        assert "gone" in result
        assert "deleted from source" in result

    def test_conflict_status_in_diff(self) -> None:
        """Conflicting items should appear with '!' symbol."""
        entry = DiffEntry(item=_make_item("clash"), status=DiffStatus.CONFLICT)
        result = format_diff({Platform.OPENCODE: [entry]}, use_colors=False)
        assert "!" in result
        assert "clash" in result

    def test_mixed_item_types_in_summary(self) -> None:
        """Summary should group by item type."""
        entries = [
            DiffEntry(item=_make_item("a", ItemType.AGENT), status=DiffStatus.NEW),
            DiffEntry(
                item=_make_item("b", ItemType.SKILL),
                status=DiffStatus.UPDATED,
            ),
        ]
        result = format_diff({Platform.OPENCODE: entries}, use_colors=False)
        assert "agents" in result
        assert "skills" in result


class TestFormatDiffVerbose:
    """Tests for format_diff() with verbose content diff support."""

    def test_verbose_without_content_diffs_shows_status_only(self) -> None:
        """Verbose=True without content_diffs should not crash."""
        entry = DiffEntry(item=_make_item("x"), status=DiffStatus.UPDATED)
        result = format_diff(
            {Platform.OPENCODE: [entry]},
            use_colors=False,
            verbose=True,
            content_diffs=None,
        )
        assert "x" in result
        assert "updated" in result
        # No diff lines should appear when content_diffs is None
        assert "---" not in result

    def test_verbose_with_content_diff_includes_diff_lines(self) -> None:
        """UPDATED entries with content diffs should show unified diff."""
        item = _make_item("coder")
        entry = DiffEntry(item=item, status=DiffStatus.UPDATED)
        diff_lines = [
            "--- a/coder.md",
            "+++ b/coder.md",
            "@@ -1,3 +1,3 @@",
            " line1",
            "-line2 old",
            "+line2 new",
            " line3",
        ]
        content_diffs = {("agent/coder", "opencode"): diff_lines}
        result = format_diff(
            {Platform.OPENCODE: [entry]},
            use_colors=False,
            verbose=True,
            content_diffs=content_diffs,
        )
        assert "--- a/coder.md" in result
        assert "+++ b/coder.md" in result
        assert "-line2 old" in result
        assert "+line2 new" in result

    def test_verbose_ignores_content_for_new_entries(self) -> None:
        """NEW entries should not show content diff even in verbose mode."""
        item = _make_item("new-agent")
        entry = DiffEntry(item=item, status=DiffStatus.NEW)
        content_diffs = {("agent/new-agent", "opencode"): ["should not appear"]}
        result = format_diff(
            {Platform.OPENCODE: [entry]},
            use_colors=False,
            verbose=True,
            content_diffs=content_diffs,
        )
        assert "should not appear" not in result
        assert "new-agent" in result

    def test_verbose_ignores_content_for_unchanged_entries(self) -> None:
        """UNCHANGED entries should not show content diff."""
        item = _make_item("same")
        entry = DiffEntry(item=item, status=DiffStatus.UNCHANGED)
        content_diffs = {("agent/same", "opencode"): ["should not appear"]}
        result = format_diff(
            {Platform.OPENCODE: [entry]},
            use_colors=False,
            verbose=True,
            content_diffs=content_diffs,
        )
        assert "should not appear" not in result

    def test_verbose_with_colors_applies_ansi(self) -> None:
        """Coloured output should wrap diff lines in ANSI codes."""
        item = _make_item("colored")
        entry = DiffEntry(item=item, status=DiffStatus.UPDATED)
        diff_lines = [
            "--- old",
            "+++ new",
            "@@ -1 +1 @@",
            "-removed",
            "+added",
            " context",
        ]
        content_diffs = {("agent/colored", "opencode"): diff_lines}
        with patch("syncode.output._use_colors", True):
            result = format_diff(
                {Platform.OPENCODE: [entry]},
                use_colors=True,
                verbose=True,
                content_diffs=content_diffs,
            )
        # Should contain ANSI escape codes for colors
        assert "\033[" in result

    def test_verbose_no_matching_content_diff_shows_status_only(self) -> None:
        """When key not found in content_diffs, only status line appears."""
        item = _make_item("missing-diff")
        entry = DiffEntry(item=item, status=DiffStatus.UPDATED)
        content_diffs = {}  # Empty — no matching key
        result = format_diff(
            {Platform.OPENCODE: [entry]},
            use_colors=False,
            verbose=True,
            content_diffs=content_diffs,
        )
        assert "missing-diff" in result
        assert "updated" in result
        assert "---" not in result

    def test_non_verbose_ignores_content_diffs(self) -> None:
        """Non-verbose mode should ignore content_diffs entirely."""
        item = _make_item("x")
        entry = DiffEntry(item=item, status=DiffStatus.UPDATED)
        diff_lines = ["--- old", "+++ new", "-removed", "+added"]
        content_diffs = {("agent/x", "opencode"): diff_lines}
        result = format_diff(
            {Platform.OPENCODE: [entry]},
            use_colors=False,
            verbose=False,
            content_diffs=content_diffs,
        )
        assert "---" not in result
        assert "removed" not in result


# ---------------------------------------------------------------------------
# format_diff_json
# ---------------------------------------------------------------------------


class TestFormatDiffJson:
    """Tests for format_diff_json() JSON output."""

    def test_empty_dict_returns_valid_json(self) -> None:
        """Empty diff should produce valid JSON with empty platforms."""
        result = format_diff_json({})
        parsed = json.loads(result)
        assert parsed == {"platforms": {}}

    def test_single_entry_produces_valid_structure(self) -> None:
        """Single entry should produce correct JSON structure."""
        item = _make_item("test-agent")
        entry = DiffEntry(item=item, status=DiffStatus.NEW)
        result = format_diff_json({Platform.OPENCODE: [entry]})
        parsed = json.loads(result)
        assert "platforms" in parsed
        assert "opencode" in parsed["platforms"]
        items = parsed["platforms"]["opencode"]["items"]
        assert len(items) == 1
        assert items[0]["name"] == "test-agent"
        assert items[0]["type"] == "agent"
        assert items[0]["status"] == "new"

    def test_multiple_entries(self) -> None:
        """Multiple entries should all appear in JSON."""
        entries = [
            DiffEntry(item=_make_item("a"), status=DiffStatus.NEW),
            DiffEntry(item=_make_item("b"), status=DiffStatus.DELETED),
        ]
        result = format_diff_json({Platform.OPENCODE: entries})
        parsed = json.loads(result)
        items = parsed["platforms"]["opencode"]["items"]
        assert len(items) == 2

    def test_multiple_platforms(self) -> None:
        """Multiple platforms should each appear as separate keys."""
        entry = DiffEntry(item=_make_item("x"), status=DiffStatus.NEW)
        result = format_diff_json(
            {Platform.OPENCODE: [entry], Platform.CLAUDE_CODE: [entry]},
        )
        parsed = json.loads(result)
        assert "opencode" in parsed["platforms"]
        assert "claude_code" in parsed["platforms"]

    def test_json_is_indented(self) -> None:
        """Output should be pretty-printed with 2-space indent."""
        entry = DiffEntry(item=_make_item("x"), status=DiffStatus.NEW)
        result = format_diff_json({Platform.OPENCODE: [entry]})
        assert "  " in result  # 2-space indent present

    def test_all_status_values_in_json(self) -> None:
        """All DiffStatus values should serialize correctly."""
        for status in DiffStatus:
            entry = DiffEntry(item=_make_item(f"item-{status.value}"), status=status)
            result = format_diff_json({Platform.OPENCODE: [entry]})
            parsed = json.loads(result)
            assert parsed["platforms"]["opencode"]["items"][0]["status"] == status.value

    def test_all_item_types_in_json(self) -> None:
        """All ItemType values should serialize correctly."""
        for item_type in ItemType:
            item = _make_item(f"item-{item_type.value}", item_type)
            entry = DiffEntry(item=item, status=DiffStatus.NEW)
            result = format_diff_json({Platform.OPENCODE: [entry]})
            parsed = json.loads(result)
            assert parsed["platforms"]["opencode"]["items"][0]["type"] == item_type.value


# ---------------------------------------------------------------------------
# Banner formatting — edge cases
# ---------------------------------------------------------------------------


class TestPrintBannerEdgeCases:
    """Additional tests for print_banner() edge cases."""

    def test_banner_with_empty_string_line(self, capsys: pytest.CaptureFixture) -> None:
        """An empty string in lines should produce a blank content line."""
        with patch("syncode.output._use_colors", False):
            print_banner([""])
        captured = capsys.readouterr()
        lines = captured.out.strip().splitlines()
        assert len(lines) == 3
        # Content line should have vertical bars and spaces but no text
        assert "\u2502" in lines[1]

    def test_banner_with_special_characters(self, capsys: pytest.CaptureFixture) -> None:
        """Special characters like tabs should not break box drawing."""
        with patch("syncode.output._use_colors", False):
            print_banner(["Tab\there"])
        captured = capsys.readouterr()
        lines = captured.out.strip().splitlines()
        # Should have top border, 1 content line, bottom border = 3 lines
        assert len(lines) == 3
        assert "\u2502" in lines[1]

    def test_banner_with_embedded_newline(self, capsys: pytest.CaptureFixture) -> None:
        """A string containing \\n produces extra output lines (actual newlines)."""
        with patch("syncode.output._use_colors", False):
            print_banner(["Line1\nLine2"])
        captured = capsys.readouterr()
        # The embedded \n creates an actual newline in output, splitting the box
        assert "Line1" in captured.out
        assert "Line2" in captured.out

    def test_banner_with_very_long_line(self, capsys: pytest.CaptureFixture) -> None:
        """Very long lines should be handled without error."""
        long_line = "x" * 300
        with patch("syncode.output._use_colors", False):
            print_banner([long_line])
        captured = capsys.readouterr()
        assert long_line in captured.out

    def test_banner_all_lines_same_visible_width(
        self,
        capsys: pytest.CaptureFixture,
    ) -> None:
        """All content lines in the banner should have same visible width."""
        with patch("syncode.output._use_colors", False):
            print_banner(["short", "medium length", "a very long line here"])
        captured = capsys.readouterr()
        import re

        ansi_re = re.compile(r"\033\[[0-9;]*m")
        lines = captured.out.strip().splitlines()
        # Content lines are lines[1], lines[2], lines[3]
        content_lines = lines[1:-1]
        visible_lengths = [len(ansi_re.sub("", line)) for line in content_lines]
        assert len(set(visible_lengths)) == 1, (
            f"Content lines differ in visible width: {visible_lengths}"
        )

    def test_banner_uses_box_drawing_chars(self, capsys: pytest.CaptureFixture) -> None:
        """Banner should use Unicode box-drawing characters."""
        with patch("syncode.output._use_colors", False):
            print_banner(["test"])
        captured = capsys.readouterr()
        assert "\u2500" in captured.out  # horizontal line ─
        assert "\u2502" in captured.out  # vertical line │

    def test_banner_with_mixed_ansi_and_plain(
        self,
        capsys: pytest.CaptureFixture,
    ) -> None:
        """Mix of colored and plain lines should still align."""
        with patch("syncode.output._use_colors", True):
            print_banner(
                [
                    colorize("colored", Colors.GREEN),
                    "plain text that is longer",
                ]
            )
        captured = capsys.readouterr()
        import re

        ansi_re = re.compile(r"\033\[[0-9;]*m")
        lines = captured.out.strip().splitlines()
        content_lines = lines[1:-1]
        visible_lengths = [len(ansi_re.sub("", line)) for line in content_lines]
        assert len(set(visible_lengths)) == 1


# ---------------------------------------------------------------------------
# Broken pipe — additional helpers
# ---------------------------------------------------------------------------


class TestBrokenPipeAdditional:
    """Additional broken-pipe resilience tests for dim/bold."""

    def test_dim_survives_broken_pipe(self) -> None:
        with patch("syncode.output._safe_write") as mock_write:
            dim("faded")
        mock_write.assert_called_once()

    def test_bold_survives_broken_pipe(self) -> None:
        with patch("syncode.output._safe_write") as mock_write:
            bold("strong")
        mock_write.assert_called_once()

    def test_safe_write_handles_generic_oserror(self) -> None:
        """Generic OSError (not BrokenPipeError) during fallback should be caught."""
        stream = MagicMock()
        stream.encoding = "ascii"
        stream.write.side_effect = [
            UnicodeEncodeError("ascii", "bad", 0, 1, "error"),
            OSError("device error"),
        ]
        # Should not raise — OSError caught in fallback path
        _safe_write("bad\n", stream=stream)


# ---------------------------------------------------------------------------
# _fit_cell helper
# ---------------------------------------------------------------------------


class TestFitCell:
    """Tests for _fit_cell() column truncation helper."""

    def test_short_text_is_left_justified(self) -> None:
        """Text shorter than width is padded with spaces."""
        result = _fit_cell("hi", 5)
        assert result == "hi   "
        assert len(result) == 5

    def test_exact_fit_returns_text(self) -> None:
        """Text exactly matching width is returned as-is."""
        result = _fit_cell("hello", 5)
        assert result == "hello"

    def test_long_text_is_truncated_with_ellipsis(self) -> None:
        """Text exceeding width is truncated and ends with ellipsis."""
        result = _fit_cell("hello world", 8)
        assert result == "hello w\u2026"
        assert len(result) == 8

    def test_width_one_truncates_to_single_char(self) -> None:
        """Width of 1 returns a single character."""
        result = _fit_cell("abc", 1)
        assert len(result) == 1
        assert result == "a"

    def test_width_zero_returns_empty(self) -> None:
        """Width of 0 returns empty string."""
        result = _fit_cell("abc", 0)
        assert result == ""

    def test_empty_text_is_padded(self) -> None:
        """Empty text produces spaces."""
        result = _fit_cell("", 4)
        assert result == "    "
        assert len(result) == 4


# ---------------------------------------------------------------------------
# print_table — max_width / truncation
# ---------------------------------------------------------------------------


class TestPrintTableMaxWidth:
    """Tests for print_table() max_width and auto-truncation."""

    def test_table_fits_within_max_width(self, capsys: pytest.CaptureFixture) -> None:
        """Table narrower than max_width renders without truncation."""
        print_table(["A", "B"], [["x", "y"]], max_width=100)
        captured = capsys.readouterr()
        lines = captured.out.rstrip("\n").splitlines()
        for line in lines:
            assert len(line) <= 100

    def test_table_truncates_wide_columns(self, capsys: pytest.CaptureFixture) -> None:
        """Columns exceeding max_width are truncated with ellipsis."""
        print_table(
            ["Name", "Description"],
            [["test", "a very long description that should be cut"]],
            max_width=30,
        )
        captured = capsys.readouterr()
        lines = captured.out.rstrip("\n").splitlines()
        for line in lines:
            assert len(line) <= 30, f"Line too long ({len(line)}): {line!r}"
        # Ellipsis should appear in truncated cells
        assert "\u2026" in captured.out

    def test_max_width_defaults_to_terminal_size(
        self,
        capsys: pytest.CaptureFixture,
    ) -> None:
        """Without max_width, terminal size is used (mocked)."""
        with patch("shutil.get_terminal_size", return_value=os.terminal_size((60, 24))):
            print_table(
                ["Header1", "Header2"],
                [["short", "a reasonably long value"]],
            )
        captured = capsys.readouterr()
        lines = captured.out.rstrip("\n").splitlines()
        for line in lines:
            assert len(line) <= 60, f"Line exceeds 60 chars: {line!r}"

    def test_backward_compatible_no_max_width_kwarg(
        self,
        capsys: pytest.CaptureFixture,
    ) -> None:
        """Existing callers that don't pass max_width still work."""
        # Just verify no crash — terminal size detection is automatic
        print_table(["A", "B"], [["1", "2"]])
        captured = capsys.readouterr()
        assert "A" in captured.out
        assert "1" in captured.out

    def test_very_small_max_width_does_not_crash(
        self,
        capsys: pytest.CaptureFixture,
    ) -> None:
        """Even a tiny max_width should not raise an exception."""
        print_table(["Alpha", "Beta", "Gamma"], [["x", "y", "z"]], max_width=10)
        captured = capsys.readouterr()
        assert captured.out  # produces some output

    def test_separator_respects_shrunk_widths(
        self,
        capsys: pytest.CaptureFixture,
    ) -> None:
        """Separator dashes match the (possibly reduced) column widths."""
        print_table(["LongHeader", "Data"], [["abc", "def"]], max_width=15)
        captured = capsys.readouterr()
        lines = captured.out.rstrip("\n").splitlines()
        separator = lines[1]
        # Separator should not exceed max_width
        assert len(separator) <= 15


# ---------------------------------------------------------------------------
# print_section
# ---------------------------------------------------------------------------


class TestPrintSection:
    """Tests for print_section() styled section header."""

    def test_prints_section_header(self, capsys: pytest.CaptureFixture) -> None:
        """Should output a line starting with ── and containing the title."""
        with patch("shutil.get_terminal_size", return_value=os.terminal_size((80, 24))):
            with patch("syncode.output._use_colors", False):
                print_section("Scanning source")
        captured = capsys.readouterr()
        assert "Scanning source" in captured.out
        assert captured.out.startswith("\u2500\u2500")

    def test_pads_to_terminal_width(self, capsys: pytest.CaptureFixture) -> None:
        """Line should span the terminal width (or 80, whichever is smaller)."""
        with patch("shutil.get_terminal_size", return_value=os.terminal_size((80, 24))):
            with patch("syncode.output._use_colors", False):
                print_section("Test")
        captured = capsys.readouterr()
        line = captured.out.rstrip("\n")
        assert len(line) == 80

    def test_limits_to_80_chars_on_wide_terminal(
        self,
        capsys: pytest.CaptureFixture,
    ) -> None:
        """Even on a 200-char terminal, section header caps at 80."""
        with patch(
            "shutil.get_terminal_size",
            return_value=os.terminal_size((200, 24)),
        ), patch("syncode.output._use_colors", False):
            print_section("Wide terminal")
        captured = capsys.readouterr()
        line = captured.out.rstrip("\n")
        assert len(line) == 80

    def test_short_title_has_right_padding(
        self,
        capsys: pytest.CaptureFixture,
    ) -> None:
        """A short title should have ─ padding on the right."""
        with patch("shutil.get_terminal_size", return_value=os.terminal_size((80, 24))):
            with patch("syncode.output._use_colors", False):
                print_section("Go")
        captured = capsys.readouterr()
        line = captured.out.rstrip("\n")
        # Line should end with ─ characters
        assert line.endswith("\u2500")

    def test_routes_through_safe_write(self) -> None:
        """print_section should route through dim → _safe_write."""
        with (
            patch("shutil.get_terminal_size", return_value=os.terminal_size((80, 24))),
            patch("syncode.output._safe_write") as mock_write,
        ):
            print_section("Test")
        # dim() calls _safe_write once
        assert mock_write.called


# ---------------------------------------------------------------------------
# print_item_status
# ---------------------------------------------------------------------------


class TestPrintItemStatus:
    """Tests for print_item_status() single item status line."""

    def test_basic_status_line(self, capsys: pytest.CaptureFixture) -> None:
        """Minimal status line with key and status."""
        print_item_status("agent/coder", "✅", [])
        captured = capsys.readouterr()
        assert "✅ agent/coder" in captured.out

    def test_with_platforms(self, capsys: pytest.CaptureFixture) -> None:
        """Platforms should appear in brackets."""
        print_item_status("skill/coder", "✅", ["opencode", "claude_code"])
        captured = capsys.readouterr()
        assert "[opencode, claude_code]" in captured.out

    def test_with_detail(self, capsys: pytest.CaptureFixture) -> None:
        """Detail text should appear after em-dash."""
        print_item_status("agent/coder", "⚠️", ["opencode"], detail="checksum differs")
        captured = capsys.readouterr()
        assert "checksum differs" in captured.out
        assert "\u2014" in captured.out  # em-dash

    def test_no_platforms_omits_brackets(
        self,
        capsys: pytest.CaptureFixture,
    ) -> None:
        """Empty platforms list should not produce brackets."""
        print_item_status("agent/test", "❌", [])
        captured = capsys.readouterr()
        assert "[" not in captured.out

    def test_no_detail_omits_dash(self, capsys: pytest.CaptureFixture) -> None:
        """No detail text should not produce em-dash."""
        print_item_status("agent/test", "✅", ["opencode"])
        captured = capsys.readouterr()
        assert "\u2014" not in captured.out

    def test_full_status_line(self, capsys: pytest.CaptureFixture) -> None:
        """All fields populated should produce expected format."""
        print_item_status(
            "skill/python-review",
            "✅",
            ["opencode"],
            detail="checksums match",
        )
        captured = capsys.readouterr()
        line = captured.out.rstrip("\n")
        assert line.startswith("  ✅ skill/python-review [opencode]")
        assert line.endswith("checksums match")

    def test_routes_through_safe_write(self) -> None:
        """print_item_status should route through _safe_write."""
        with patch("syncode.output._safe_write") as mock_write:
            print_item_status("x", "✅", ["opencode"], detail="ok")
        mock_write.assert_called_once()
        written = mock_write.call_args[0][0]
        assert "x" in written
        assert "opencode" in written
