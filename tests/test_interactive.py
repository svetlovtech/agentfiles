"""Tests for agentfiles.interactive — interactive prompts, menus, and parsing."""

from __future__ import annotations

import logging
from collections.abc import Generator
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from agentfiles.interactive import (
    InputParser,
    InteractiveSession,
    MenuRenderer,
    _parse_comma_list,
    _parse_ranges,
)
from agentfiles.models import (
    Item,
    ItemType,
    SyncAction,
    SyncPlan,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def renderer() -> MenuRenderer:
    """Plain-text renderer for predictable output."""
    return MenuRenderer(use_colors=False)


@pytest.fixture
def parser(renderer: MenuRenderer) -> InputParser:
    """InputParser using a plain-text renderer."""
    return InputParser(renderer)


@pytest.fixture
def sample_items() -> list[Item]:
    """Build a small list of Items for testing."""
    return [
        Item(
            item_type=ItemType.AGENT,
            name="python-reviewer",
            source_path=Path("/src/agents/python-reviewer"),
        ),
        Item(
            item_type=ItemType.SKILL,
            name="python-reviewer",
            source_path=Path("/src/skills/python-reviewer"),
        ),
        Item(
            item_type=ItemType.AGENT,
            name="code-stylist",
            source_path=Path("/src/agents/code-stylist"),
        ),
    ]


@pytest.fixture(autouse=True)
def _isolate_output_colors() -> Generator[None, None, None]:
    """Save and restore the output module's ``_use_colors`` flag.

    ``agentfiles.output._use_colors`` is module-level mutable state mutated
    by ``init_logging()``.  Without this fixture a test (in this file or
    any other) that calls ``init_logging()`` would change the flag for
    every subsequent test in the same process, causing flaky failures.
    """
    import agentfiles.output as _output_mod

    original = _output_mod._use_colors
    yield
    _output_mod._use_colors = original


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------


class TestParseCommaList:
    """Tests for _parse_comma_list()."""

    def test_single_token(self) -> None:
        assert _parse_comma_list("hello") == ["hello"]

    def test_comma_separated(self) -> None:
        assert _parse_comma_list("a,b,c") == ["a", "b", "c"]

    def test_space_separated(self) -> None:
        assert _parse_comma_list("a b c") == ["a", "b", "c"]

    def test_mixed_separators(self) -> None:
        result = _parse_comma_list("a, b c, d  e")
        assert result == ["a", "b", "c", "d", "e"]

    def test_empty_string(self) -> None:
        assert _parse_comma_list("") == []

    def test_whitespace_only(self) -> None:
        assert _parse_comma_list("   ") == []

    def test_strips_whitespace_and_lowercases(self) -> None:
        result = _parse_comma_list("  HELLO , World  ")
        assert result == ["hello", "world"]

    def test_discards_empty_tokens(self) -> None:
        result = _parse_comma_list("a,,b,  ,c")
        assert result == ["a", "b", "c"]

    def test_leading_trailing_commas(self) -> None:
        result = _parse_comma_list(",a,b,")
        assert result == ["a", "b"]


class TestParseRanges:
    """Tests for _parse_ranges()."""

    def test_single_number(self) -> None:
        assert _parse_ranges("3", 10) == [3]

    def test_multiple_numbers(self) -> None:
        assert _parse_ranges("1,3,5", 10) == [1, 3, 5]

    def test_range_expression(self) -> None:
        assert _parse_ranges("2-5", 10) == [2, 3, 4, 5]

    def test_mixed_ranges_and_singles(self) -> None:
        assert _parse_ranges("1,3-5,8", 10) == [1, 3, 4, 5, 8]

    def test_ignores_out_of_range(self) -> None:
        assert _parse_ranges("0,1,11", 10) == [1]

    def test_ignores_duplicates(self) -> None:
        assert _parse_ranges("3,3,3", 10) == [3]

    def test_empty_input(self) -> None:
        assert _parse_ranges("", 10) == []

    def test_clamps_range_upper_bound(self) -> None:
        assert _parse_ranges("8-12", 10) == [8, 9, 10]

    def test_invalid_tokens_ignored(self) -> None:
        assert _parse_ranges("abc,3,foo-5", 10) == [3]

    def test_invalid_range_ignored(self) -> None:
        # "a-" split on "-" gives ["a", ""] which causes ValueError on int("")
        assert _parse_ranges("a-", 10) == []

    def test_max_value_of_zero(self) -> None:
        assert _parse_ranges("1,2", 0) == []

    def test_returns_sorted_unique(self) -> None:
        assert _parse_ranges("5,1,3,3", 10) == [1, 3, 5]


# ---------------------------------------------------------------------------
# MenuRenderer
# ---------------------------------------------------------------------------


class TestMenuRenderer:
    """Tests for MenuRenderer display formatting."""

    def test_init_defaults_to_colors_enabled(self) -> None:
        r = MenuRenderer()
        assert r._use_colors is True

    def test_init_with_colors_false(self) -> None:
        r = MenuRenderer(use_colors=False)
        assert r._use_colors is False

    def test_c_returns_plain_when_colors_disabled(self, renderer: MenuRenderer) -> None:
        assert renderer._c("text", "\033[92m") == "text"

    def test_c_returns_colored_when_colors_enabled(self) -> None:
        import agentfiles.output as _output_mod
        from agentfiles.output import Colors, colorize

        r = MenuRenderer(use_colors=True)
        # Explicitly set the module-level flag so the test is deterministic
        # even when another test has called init_logging() first.
        with patch.object(_output_mod, "_use_colors", True):
            result = r._c("text", Colors.GREEN)
            expected = colorize("text", Colors.GREEN)
        # Verify ANSI escape codes are actually present (not stripped).
        assert result == expected
        assert "\033[" in result

    def test_show_item_types_prints_numbered_list(
        self, renderer: MenuRenderer, capsys: pytest.CaptureFixture
    ) -> None:
        types = list(ItemType)
        renderer.show_item_types(types)
        captured = capsys.readouterr()
        assert "1)" in captured.out
        assert "Agents" in captured.out

    def test_show_items_grouped_returns_index_map(
        self, renderer: MenuRenderer, sample_items: list[Item], capsys: pytest.CaptureFixture
    ) -> None:
        index_map = renderer.show_items_grouped(sample_items)
        assert len(index_map) == 3
        # Check continuous numbering
        assert 1 in index_map
        assert 2 in index_map
        assert 3 in index_map
        # Items are grouped by type: Agents first (2 items), then Skills (1 item)
        assert index_map[1].name == "python-reviewer"
        assert index_map[1].item_type == ItemType.AGENT
        assert index_map[2].name == "code-stylist"
        assert index_map[2].item_type == ItemType.AGENT
        assert index_map[3].name == "python-reviewer"
        assert index_map[3].item_type == ItemType.SKILL

    def test_show_items_grouped_prints_groups(
        self, renderer: MenuRenderer, sample_items: list[Item], capsys: pytest.CaptureFixture
    ) -> None:
        renderer.show_items_grouped(sample_items)
        captured = capsys.readouterr()
        assert "Agents" in captured.out
        assert "Skills" in captured.out
        assert "[1]" in captured.out
        assert "[2]" in captured.out
        assert "[3]" in captured.out

    def test_show_items_grouped_empty_list(
        self, renderer: MenuRenderer, capsys: pytest.CaptureFixture
    ) -> None:
        index_map = renderer.show_items_grouped([])
        assert index_map == {}

    def test_show_sync_modes_prints_menu(
        self, renderer: MenuRenderer, capsys: pytest.CaptureFixture
    ) -> None:
        renderer.show_sync_modes()
        captured = capsys.readouterr()
        assert "Install all" in captured.out
        assert "Full sync" in captured.out
        assert "Load mode:" in captured.out

    def test_show_no_plans_message(
        self, renderer: MenuRenderer, capsys: pytest.CaptureFixture
    ) -> None:
        renderer.show_no_plans_message()
        captured = capsys.readouterr()
        assert "No load actions planned" in captured.out

    def test_show_plan_summary_displays_plans(
        self, renderer: MenuRenderer, capsys: pytest.CaptureFixture
    ) -> None:
        item = Item(
            item_type=ItemType.AGENT,
            name="test-agent",
            source_path=Path("/src/test"),
        )
        plans = [
            SyncPlan(
                item=item,
                action=SyncAction.INSTALL,
                target_dir=Path("/opencode"),
                reason="new item",
            ),
        ]
        renderer.show_plan_summary(plans)
        captured = capsys.readouterr()
        assert "Load plan:" in captured.out
        assert "Install" in captured.out
        assert "test-agent" in captured.out

    def test_show_plan_summary_with_empty_plans(
        self, renderer: MenuRenderer, capsys: pytest.CaptureFixture
    ) -> None:
        renderer.show_plan_summary([])
        captured = capsys.readouterr()
        # Should just print "Load plan:" header with no action lines
        assert "Load plan:" in captured.out

    def test_show_plan_summary_multiple_actions(
        self, renderer: MenuRenderer, capsys: pytest.CaptureFixture
    ) -> None:
        item = Item(
            item_type=ItemType.SKILL,
            name="my-skill",
            source_path=Path("/src/skill"),
        )
        plans = [
            SyncPlan(item=item, action=SyncAction.INSTALL, target_dir=Path("/oc"), reason="new"),
            SyncPlan(
                item=item, action=SyncAction.UNINSTALL, target_dir=Path("/cc"), reason="removed"
            ),
        ]
        renderer.show_plan_summary(plans)
        captured = capsys.readouterr()
        assert "Install" in captured.out
        assert "Uninstall" in captured.out


# ---------------------------------------------------------------------------
# InputParser
# ---------------------------------------------------------------------------


class TestInputParser:
    """Tests for InputParser input collection and parsing."""

    def test_prompt_returns_stripped_input(self, parser: InputParser) -> None:
        with patch("builtins.input", return_value="  hello  "):
            result = parser.prompt("Enter: ")
        assert result == "hello"

    def test_prompt_propagates_keyboard_interrupt(self, parser: InputParser) -> None:
        with (
            patch("builtins.input", side_effect=KeyboardInterrupt),
            pytest.raises(KeyboardInterrupt),
        ):
            parser.prompt("Enter: ")

    def test_prompt_eof_prints_newline(self, parser: InputParser) -> None:
        """EOFError should print a newline to avoid broken terminal output."""
        with (
            patch("builtins.input", side_effect=EOFError),
            patch("builtins.print") as mock_print,
        ):
            parser.prompt("Enter: ")
        mock_print.assert_called_once()

    def test_confirm_returns_default_on_eof(self, parser: InputParser) -> None:
        """EOFError during confirm should use the default value."""
        with patch("builtins.input", side_effect=EOFError):
            assert parser.confirm("Continue?", default=True) is True
        with patch("builtins.input", side_effect=EOFError):
            assert parser.confirm("Continue?", default=False) is False


class TestInteractiveSessionRetry:
    """Tests for selection retry prompts in InteractiveSession."""

    def test_select_item_types_retries_on_invalid(self) -> None:
        """Invalid item type input triggers retry; valid input on second try."""
        session = InteractiveSession(use_colors=False)
        with patch("builtins.input", side_effect=["bad", "1"]):
            result = session.select_item_types()
        assert result == [ItemType.AGENT]

    def test_select_item_types_returns_all_after_retries(self) -> None:
        """Exhausting retries falls back to all item types."""
        session = InteractiveSession(use_colors=False)
        invalid = ["bad"] * 10
        with patch("builtins.input", side_effect=invalid):
            result = session.select_item_types()
        assert result == list(ItemType)

    def test_select_items_retries_on_invalid(self, sample_items: list[Item]) -> None:
        """Invalid item selection triggers retry; valid input works."""
        session = InteractiveSession(use_colors=False)
        # "99" is out of range → empty result → retry
        with patch("builtins.input", side_effect=["99", "1"]):
            result = session.select_items(sample_items)
        assert len(result) == 1
        assert result[0].name == "python-reviewer"
        assert result[0].item_type == ItemType.AGENT

    def test_select_items_returns_all_after_retries(self, sample_items: list[Item]) -> None:
        """Exhausting retries falls back to all items."""
        session = InteractiveSession(use_colors=False)
        invalid = ["99"] * 10
        with patch("builtins.input", side_effect=invalid):
            result = session.select_items(sample_items)
        assert result == list(sample_items)


class TestInteractiveSessionColorAutoDetection:
    """Tests for automatic color detection in InteractiveSession."""

    def test_auto_detect_no_color_env(self) -> None:
        """NO_COLOR env var disables colors automatically."""
        with patch.dict("os.environ", {"NO_COLOR": "1"}):
            session = InteractiveSession()
        assert session._renderer._use_colors is False

    def test_auto_detect_non_tty(self) -> None:
        """Non-TTY stdout disables colors automatically."""
        with patch("sys.stdout.isatty", return_value=False):
            session = InteractiveSession()
        assert session._renderer._use_colors is False

    def test_auto_detect_tty(self) -> None:
        """TTY stdout with no NO_COLOR enables colors."""
        with (
            patch.dict("os.environ", {}, clear=True),
            patch("sys.stdout.isatty", return_value=True),
        ):
            session = InteractiveSession()
        assert session._renderer._use_colors is True

    def test_explicit_true_overrides_auto_detect(self) -> None:
        """Explicit use_colors=True overrides auto-detection."""
        with patch.dict("os.environ", {"NO_COLOR": "1"}):
            session = InteractiveSession(use_colors=True)
        assert session._renderer._use_colors is True

    def test_explicit_false_overrides_auto_detect(self) -> None:
        """Explicit use_colors=False overrides auto-detection."""
        with patch("sys.stdout.isatty", return_value=True):
            session = InteractiveSession(use_colors=False)
        assert session._renderer._use_colors is False


# ---------------------------------------------------------------------------
# Additional InputParser coverage — confirmation edge cases
# ---------------------------------------------------------------------------


class TestInputParserConfirmEdgeCases:
    """Extended tests for confirm() and prompt() edge cases."""

    def test_confirm_n_returns_false(self, parser: InputParser) -> None:
        """Lowercase 'n' explicitly returns False."""
        with patch("builtins.input", return_value="n"):
            assert parser.confirm("Continue?") is False

    def test_confirm_case_insensitive_yes(self, parser: InputParser) -> None:
        """'YES' (uppercase) returns True."""
        with patch("builtins.input", return_value="YES"):
            assert parser.confirm("Continue?") is True

    def test_confirm_case_insensitive_no(self, parser: InputParser) -> None:
        """'NO' (uppercase) returns False."""
        with patch("builtins.input", return_value="NO"):
            assert parser.confirm("Continue?") is False

    def test_confirm_non_y_returns_false(self, parser: InputParser) -> None:
        """Any input not starting with 'y' is treated as negative."""
        for value in ["maybe", "sure", "ok", "please", "1"]:
            with patch("builtins.input", return_value=value):
                assert parser.confirm("Continue?") is False, f"'{value}' should be False"

    def test_prompt_passes_colored_prompt_to_input(self, parser: InputParser) -> None:
        """prompt() calls input() with the message coloured via the renderer."""
        with patch("builtins.input", return_value="ok") as mock_input:
            parser.prompt("Choose: ")
        # The prompt message is passed through the renderer — it may or may
        # not contain ANSI codes depending on colour settings.  We verify the
        # raw string was forwarded.
        call_args = mock_input.call_args[0][0]
        assert "Choose" in call_args


# ---------------------------------------------------------------------------
# Additional MenuRenderer coverage
# ---------------------------------------------------------------------------


class TestMenuRendererWelcome:
    """Tests for MenuRenderer.show_welcome()."""

    def test_show_welcome_prints_banner(self, capsys: pytest.CaptureFixture) -> None:
        """show_welcome() prints a banner with the project name."""
        renderer = MenuRenderer(use_colors=False)
        renderer.show_welcome()
        captured = capsys.readouterr()
        assert "agentfiles" in captured.out

    def test_show_welcome_with_colors(self, capsys: pytest.CaptureFixture) -> None:
        """show_welcome() works without error when colours are enabled."""
        import agentfiles.output as _output_mod

        renderer = MenuRenderer(use_colors=True)
        with patch.object(_output_mod, "_use_colors", True):
            renderer.show_welcome()
        captured = capsys.readouterr()
        assert "agentfiles" in captured.out


# ---------------------------------------------------------------------------
# Additional InteractiveSession — choose_sync_mode & select_items
# ---------------------------------------------------------------------------


class TestChooseSyncModeExtended:
    """Extended tests for choose_sync_mode with specific modes."""

    def test_choose_install_mode(self, capsys: pytest.CaptureFixture) -> None:
        session = InteractiveSession(use_colors=False)
        with patch("builtins.input", return_value="1"):
            result = session.choose_sync_mode()
        assert result == "install"

    def test_choose_update_mode(self, capsys: pytest.CaptureFixture) -> None:
        session = InteractiveSession(use_colors=False)
        with patch("builtins.input", return_value="2"):
            result = session.choose_sync_mode()
        assert result == "update"

    def test_choose_custom_mode(self, capsys: pytest.CaptureFixture) -> None:
        session = InteractiveSession(use_colors=False)
        with patch("builtins.input", return_value="4"):
            result = session.choose_sync_mode()
        assert result == "custom"


class TestSelectItemsExtended:
    """Extended tests for select_items with range expressions."""

    def test_select_items_by_range(
        self, sample_items: list[Item], capsys: pytest.CaptureFixture
    ) -> None:
        """Items can be selected by range expression like '1-2'."""
        session = InteractiveSession(use_colors=False)
        # Indices 1-2 → both agents
        with patch("builtins.input", return_value="1-2"):
            result = session.select_items(sample_items)
        assert len(result) == 2
        assert all(it.item_type == ItemType.AGENT for it in result)

    def test_select_items_single_index(
        self, sample_items: list[Item], capsys: pytest.CaptureFixture
    ) -> None:
        """Single item selection by index."""
        session = InteractiveSession(use_colors=False)
        with patch("builtins.input", return_value="2"):
            result = session.select_items(sample_items)
        assert len(result) == 1
        assert result[0].name == "code-stylist"

    def test_select_items_eof_returns_all(
        self, sample_items: list[Item], capsys: pytest.CaptureFixture
    ) -> None:
        """EOFError during item selection returns all items."""
        session = InteractiveSession(use_colors=False)
        with patch("builtins.input", side_effect=EOFError):
            result = session.select_items(sample_items)
        assert result == list(sample_items)

    def test_select_items_keyboard_interrupt_propagates(
        self, sample_items: list[Item], capsys: pytest.CaptureFixture
    ) -> None:
        """KeyboardInterrupt during item selection propagates to caller."""
        session = InteractiveSession(use_colors=False)
        with (
            patch("builtins.input", side_effect=KeyboardInterrupt),
            pytest.raises(KeyboardInterrupt),
        ):
            session.select_items(sample_items)


# ---------------------------------------------------------------------------
# Additional InteractiveSession — EOF / interrupt in selection methods
# ---------------------------------------------------------------------------


class TestSelectionEOFHandling:
    """Tests for EOF/interrupt handling in selection methods."""

    def test_select_item_types_eof_returns_all(self) -> None:
        """EOFError during item type selection returns all types."""
        session = InteractiveSession(use_colors=False)
        with patch("builtins.input", side_effect=EOFError):
            result = session.select_item_types()
        assert result == list(ItemType)

    def test_select_item_types_interrupt_raises(self) -> None:
        """KeyboardInterrupt during item type selection propagates to caller."""
        session = InteractiveSession(use_colors=False)
        with (
            patch("builtins.input", side_effect=KeyboardInterrupt),
            pytest.raises(KeyboardInterrupt),
        ):
            session.select_item_types()
