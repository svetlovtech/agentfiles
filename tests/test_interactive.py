"""Tests for agentfiles.interactive — interactive prompts, menus, and parsing."""

from __future__ import annotations

import logging
from collections.abc import Generator
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from agentfiles.interactive import (
    InputParser,
    InteractiveRunner,
    InteractiveSession,
    MenuRenderer,
    _guess_platform,
    _item_key,
    _parse_comma_list,
    _parse_ranges,
)
from agentfiles.models import (
    DiffEntry,
    DiffStatus,
    Item,
    ItemType,
    Platform,
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


class TestGuessPlatform:
    """Tests for _guess_platform()."""

    def test_detects_opencode_from_path(self) -> None:
        assert _guess_platform("/home/.config/opencode") == Platform.OPENCODE

    def test_detects_opencode_case_insensitive(self) -> None:
        assert _guess_platform("/HOME/OpenCode") == Platform.OPENCODE

    def test_defaults_to_claude_code(self) -> None:
        assert _guess_platform("/home/.claude") == Platform.CLAUDE_CODE

    def test_defaults_for_plain_path(self) -> None:
        assert _guess_platform("/tmp/target") == Platform.CLAUDE_CODE

    def test_accepts_path_object(self) -> None:
        assert _guess_platform(Path("/config/opencode")) == Platform.OPENCODE


class TestItemKey:
    """Tests for _item_key()."""

    def test_returns_type_slash_name(self) -> None:
        item = Item(
            item_type=ItemType.AGENT,
            name="test-agent",
            source_path=Path("/src/test"),
        )
        assert _item_key(item) == "agent/test-agent"

    def test_different_types_different_keys(self) -> None:
        agent = Item(item_type=ItemType.AGENT, name="x", source_path=Path("/a"))
        skill = Item(item_type=ItemType.SKILL, name="x", source_path=Path("/s"))
        assert _item_key(agent) != _item_key(skill)


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

    def test_show_platforms_prints_numbered_list(
        self, renderer: MenuRenderer, capsys: pytest.CaptureFixture
    ) -> None:
        platforms = [Platform.OPENCODE, Platform.CLAUDE_CODE]
        renderer.show_platforms(platforms)
        captured = capsys.readouterr()
        assert "1)" in captured.out
        assert "OpenCode" in captured.out
        assert "2)" in captured.out
        assert "Claude Code" in captured.out

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

    def test_show_main_menu_prints_all_options(
        self, renderer: MenuRenderer, capsys: pytest.CaptureFixture
    ) -> None:
        renderer.show_main_menu()
        captured = capsys.readouterr()
        assert "Pull items" in captured.out
        assert "Exit" in captured.out

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

    def test_format_diff_status_all_statuses(self, renderer: MenuRenderer) -> None:
        for status in DiffStatus:
            result = renderer.format_diff_status(status)
            assert status.value in result.lower(), f"Missing status value for {status}"

    def test_show_diff_header(self, renderer: MenuRenderer, capsys: pytest.CaptureFixture) -> None:
        renderer.show_diff_header()
        captured = capsys.readouterr()
        assert "Resolve differences:" in captured.out
        assert "[i]nstall" in captured.out


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

    def test_select_platforms_retries_on_invalid_then_succeeds(
        self, capsys: pytest.CaptureFixture
    ) -> None:
        """Invalid platform input triggers retry; valid input on second try works."""
        session = InteractiveSession(use_colors=False)
        platforms = [Platform.OPENCODE, Platform.CLAUDE_CODE]
        # First input "xyz" (invalid), second input "1" (valid)
        with patch("builtins.input", side_effect=["xyz", "1"]):
            result = session.select_platforms(platforms)
        assert result == [Platform.OPENCODE]

    def test_select_platforms_returns_all_after_max_retries(self) -> None:
        """Exhausting retries on invalid input falls back to all platforms."""
        session = InteractiveSession(use_colors=False)
        platforms = [Platform.OPENCODE, Platform.CLAUDE_CODE]
        # All invalid inputs
        invalid = ["bad"] * 10  # More than _MAX_INPUT_RETRIES
        with patch("builtins.input", side_effect=invalid):
            result = session.select_platforms(platforms)
        assert result == list(platforms)

    def test_select_platforms_retry_then_all_keyword(self) -> None:
        """User can type 'all' during retry to select all platforms."""
        session = InteractiveSession(use_colors=False)
        platforms = [Platform.OPENCODE, Platform.CLAUDE_CODE]
        with patch("builtins.input", side_effect=["bad", "all"]):
            result = session.select_platforms(platforms)
        assert result == list(platforms)

    def test_select_platforms_retry_then_empty_selects_all(self) -> None:
        """User can press Enter during retry to accept all platforms."""
        session = InteractiveSession(use_colors=False)
        platforms = [Platform.OPENCODE, Platform.CLAUDE_CODE]
        with patch("builtins.input", side_effect=["bad", ""]):
            result = session.select_platforms(platforms)
        assert result == list(platforms)

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


class TestInteractiveRunnerErrorHandling:
    """Tests for InteractiveRunner error handling improvements."""

    def test_run_handles_keyboard_interrupt(self, capsys: pytest.CaptureFixture) -> None:
        """Ctrl+C during menu prompt exits cleanly."""
        dispatch = MagicMock()
        runner = InteractiveRunner(command_dispatch=dispatch, use_colors=False)

        def _raise_interrupt(message: str) -> str:
            raise KeyboardInterrupt

        with patch.object(runner._session._parser, "prompt", side_effect=_raise_interrupt):
            runner.run()

        captured = capsys.readouterr()
        assert "Goodbye" in captured.out

    def test_run_handles_eof_on_continue(self, capsys: pytest.CaptureFixture) -> None:
        """EOFError at 'Press Enter' prompt exits cleanly."""
        dispatch = MagicMock()
        runner = InteractiveRunner(command_dispatch=dispatch, use_colors=False)

        # prompt returns "1" (pull), then input("Press Enter") raises EOFError
        with (
            patch.object(runner._session._parser, "prompt", return_value="1"),
            patch("builtins.input", side_effect=EOFError),
        ):
            runner.run()

        captured = capsys.readouterr()
        assert "Goodbye" in captured.out

    def test_run_handles_interrupt_on_continue(self, capsys: pytest.CaptureFixture) -> None:
        """KeyboardInterrupt at 'Press Enter' prompt exits cleanly."""
        dispatch = MagicMock()
        runner = InteractiveRunner(command_dispatch=dispatch, use_colors=False)

        # prompt returns "1" (pull), then input("Press Enter") raises KeyboardInterrupt
        with (
            patch.object(runner._session._parser, "prompt", return_value="1"),
            patch("builtins.input", side_effect=KeyboardInterrupt),
        ):
            runner.run()

        captured = capsys.readouterr()
        assert "Goodbye" in captured.out

    def test_run_color_auto_detection(self) -> None:
        """InteractiveRunner auto-detects colors when use_colors is None."""
        with patch.dict("os.environ", {"NO_COLOR": "1"}):
            runner = InteractiveRunner(command_dispatch=MagicMock())
        assert runner._session._renderer._use_colors is False


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
# Additional InteractiveSession — select_diff_action edge cases
# ---------------------------------------------------------------------------


class TestSelectDiffActionEdgeCases:
    """Extended tests for select_diff_action with more action types."""

    @pytest.fixture
    def session(self) -> InteractiveSession:
        return InteractiveSession(use_colors=False)

    @pytest.fixture
    def sample_item(self) -> Item:
        return Item(
            item_type=ItemType.AGENT,
            name="diff-agent",
            source_path=Path("/src/diff-agent"),
        )

    def test_skip_action(
        self,
        session: InteractiveSession,
        sample_item: Item,
        capsys: pytest.CaptureFixture,
    ) -> None:
        """User picks 's' (skip) for a diff entry."""
        entry = DiffEntry(item=sample_item, status=DiffStatus.UPDATED)
        with patch("builtins.input", return_value="s"):
            result = session.select_diff_action([(entry, Platform.OPENCODE)])
        assert result["agent/diff-agent"] == SyncAction.SKIP

    def test_update_action(
        self,
        session: InteractiveSession,
        sample_item: Item,
        capsys: pytest.CaptureFixture,
    ) -> None:
        """User picks 'u' (update) for a diff entry."""
        entry = DiffEntry(item=sample_item, status=DiffStatus.UPDATED)
        with patch("builtins.input", return_value="u"):
            result = session.select_diff_action([(entry, Platform.OPENCODE)])
        assert result["agent/diff-agent"] == SyncAction.UPDATE

    def test_empty_input_defaults_to_skip(
        self,
        session: InteractiveSession,
        sample_item: Item,
        capsys: pytest.CaptureFixture,
    ) -> None:
        """Empty input during diff resolution defaults to skip."""
        entry = DiffEntry(item=sample_item, status=DiffStatus.NEW)
        with patch("builtins.input", return_value=""):
            result = session.select_diff_action([(entry, Platform.CLAUDE_CODE)])
        assert result["agent/diff-agent"] == SyncAction.SKIP

    def test_multiple_entries_with_individual_choices(
        self,
        session: InteractiveSession,
        capsys: pytest.CaptureFixture,
    ) -> None:
        """Each entry gets a separate prompt with individual choices."""
        item1 = Item(
            item_type=ItemType.AGENT,
            name="first",
            source_path=Path("/src/first"),
        )
        item2 = Item(
            item_type=ItemType.SKILL,
            name="second",
            source_path=Path("/src/second"),
        )
        entries = [
            (DiffEntry(item=item1, status=DiffStatus.NEW), Platform.OPENCODE),
            (DiffEntry(item=item2, status=DiffStatus.UPDATED), Platform.CLAUDE_CODE),
        ]
        # First: install, Second: update
        with patch("builtins.input", side_effect=["i", "u"]):
            result = session.select_diff_action(entries)
        assert result["agent/first"] == SyncAction.INSTALL
        assert result["skill/second"] == SyncAction.UPDATE

    def test_all_install_applies_to_remaining(
        self,
        session: InteractiveSession,
        capsys: pytest.CaptureFixture,
    ) -> None:
        """'all' on first entry applies install to all subsequent entries."""
        items = [
            Item(
                item_type=ItemType.AGENT,
                name=f"item-{i}",
                source_path=Path(f"/src/item-{i}"),
            )
            for i in range(4)
        ]
        entries = [(DiffEntry(item=it, status=DiffStatus.NEW), Platform.OPENCODE) for it in items]
        # Only one input call: "a" (install all)
        with patch("builtins.input", return_value="a"):
            result = session.select_diff_action(entries)
        assert len(result) == 4
        for it in items:
            assert result[it.item_key] == SyncAction.INSTALL


# ---------------------------------------------------------------------------
# Additional InteractiveSession — resolve_sync_conflicts edge cases
# ---------------------------------------------------------------------------


class TestResolveSyncConflictsEdgeCases:
    """Extended tests for resolve_sync_conflicts with more actions."""

    @pytest.fixture
    def session(self) -> InteractiveSession:
        return InteractiveSession(use_colors=False)

    def test_push_action(self, session: InteractiveSession) -> None:
        """'u' maps to 'push' action."""
        conflicts = [("my-agent", "agent", "OpenCode")]
        with patch("builtins.input", return_value="u"):
            result = session.resolve_sync_conflicts(conflicts)
        assert result["my-agent/OpenCode"] == "push"

    def test_apply_to_all_pull(self, session: InteractiveSession) -> None:
        """'a' then 'p' applies pull to all remaining conflicts."""
        conflicts = [
            ("agent-a", "agent", "OpenCode"),
            ("skill-b", "skill", "Claude Code"),
            ("agent-c", "agent", "OpenCode"),
        ]
        # First prompt: "a" (apply to all), second prompt: "p" (pull)
        with patch("builtins.input", side_effect=["a", "p"]):
            result = session.resolve_sync_conflicts(conflicts)
        assert len(result) == 3
        for key in result:
            assert result[key] == "pull"

    def test_apply_to_all_push(self, session: InteractiveSession) -> None:
        """'a' then 'u' applies push to all remaining conflicts."""
        conflicts = [
            ("agent-a", "agent", "OpenCode"),
            ("skill-b", "skill", "Claude Code"),
        ]
        with patch("builtins.input", side_effect=["a", "u"]):
            result = session.resolve_sync_conflicts(conflicts)
        assert result["agent-a/OpenCode"] == "push"
        assert result["skill-b/Claude Code"] == "push"

    def test_apply_to_all_defaults_to_skip(self, session: InteractiveSession) -> None:
        """'a' with unknown sub-choice defaults to skip."""
        conflicts = [
            ("agent-a", "agent", "OpenCode"),
            ("skill-b", "skill", "Claude Code"),
        ]
        # "a" (apply to all), then "xyz" (unknown) → defaults to skip
        with patch("builtins.input", side_effect=["a", "xyz"]):
            result = session.resolve_sync_conflicts(conflicts)
        assert result["agent-a/OpenCode"] == "skip"
        assert result["skill-b/Claude Code"] == "skip"

    def test_empty_input_defaults_to_skip(self, session: InteractiveSession) -> None:
        """Empty input during conflict resolution defaults to skip."""
        conflicts = [("my-agent", "agent", "OpenCode")]
        with patch("builtins.input", return_value=""):
            result = session.resolve_sync_conflicts(conflicts)
        assert result["my-agent/OpenCode"] == "skip"

    def test_unknown_action_defaults_to_skip(self, session: InteractiveSession) -> None:
        """Unrecognised action defaults to skip."""
        conflicts = [("my-agent", "agent", "OpenCode")]
        with patch("builtins.input", return_value="xyz"):
            result = session.resolve_sync_conflicts(conflicts)
        assert result["my-agent/OpenCode"] == "skip"

    def test_mixed_choices_across_conflicts(self, session: InteractiveSession) -> None:
        """Different conflicts can get different resolutions."""
        conflicts = [
            ("agent-a", "agent", "OpenCode"),
            ("skill-b", "skill", "Claude Code"),
        ]
        # First: pull, Second: skip
        with patch("builtins.input", side_effect=["p", "s"]):
            result = session.resolve_sync_conflicts(conflicts)
        assert result["agent-a/OpenCode"] == "pull"
        assert result["skill-b/Claude Code"] == "skip"

    def test_apply_to_all_with_push_keyword(self, session: InteractiveSession) -> None:
        """Full keyword 'push' works for apply-to-all sub-choice."""
        conflicts = [
            ("agent-a", "agent", "OpenCode"),
            ("skill-b", "skill", "Claude Code"),
        ]
        with patch("builtins.input", side_effect=["a", "push"]):
            result = session.resolve_sync_conflicts(conflicts)
        assert result["agent-a/OpenCode"] == "push"
        assert result["skill-b/Claude Code"] == "push"


# ---------------------------------------------------------------------------
# Additional InteractiveSession — choose_push_items edge cases
# ---------------------------------------------------------------------------


class TestChoosePushItemsEdgeCases:
    """Extended tests for choose_push_items with more scenarios."""

    @pytest.fixture
    def session(self) -> InteractiveSession:
        return InteractiveSession(use_colors=False)

    def test_no_matching_platforms_returns_empty(self, session: InteractiveSession) -> None:
        """When platform input matches nothing, returns empty list."""
        item = Item(
            item_type=ItemType.AGENT,
            name="push-agent",
            source_path=Path("/src/push-agent"),
        )
        platforms = [Platform.OPENCODE]
        # Platform "99" is out of range → no match
        with patch("builtins.input", side_effect=["99", "1"]):
            result = session.choose_push_items([item], platforms)
        assert result == []

    def test_specific_items_by_range(self, session: InteractiveSession) -> None:
        """Items can be selected by range expression."""
        items = [
            Item(
                item_type=ItemType.AGENT,
                name=f"agent-{i}",
                source_path=Path(f"/src/agent-{i}"),
            )
            for i in range(5)
        ]
        platforms = [Platform.OPENCODE]
        # Platforms: all, Items: "1-3" (first three)
        with patch("builtins.input", side_effect=["all", "1-3"]):
            result = session.choose_push_items(items, platforms)
        assert len(result) == 3
        for item in items[:3]:
            assert (item, Platform.OPENCODE) in result

    def test_empty_items_input_returns_all(self, session: InteractiveSession) -> None:
        """Empty items input after platform selection returns all items."""
        item1 = Item(
            item_type=ItemType.AGENT,
            name="a1",
            source_path=Path("/src/a1"),
        )
        item2 = Item(
            item_type=ItemType.SKILL,
            name="s1",
            source_path=Path("/src/s1"),
        )
        platforms = [Platform.OPENCODE]
        # Platforms: all, Items: empty → all items
        with patch("builtins.input", side_effect=["all", ""]):
            result = session.choose_push_items([item1, item2], platforms)
        assert len(result) == 2

    def test_multiple_platforms_expand_items(self, session: InteractiveSession) -> None:
        """Each selected item is paired with each selected platform."""
        item = Item(
            item_type=ItemType.AGENT,
            name="multi-agent",
            source_path=Path("/src/multi-agent"),
        )
        platforms = [Platform.OPENCODE, Platform.CLAUDE_CODE]
        with patch("builtins.input", side_effect=["1,2", "1"]):
            result = session.choose_push_items([item], platforms)
        assert len(result) == 2
        assert (item, Platform.OPENCODE) in result
        assert (item, Platform.CLAUDE_CODE) in result


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
# Additional InteractiveSession — welcome & main_menu
# ---------------------------------------------------------------------------


class TestSessionWelcomeAndMenu:
    """Tests for InteractiveSession.welcome() and main_menu() delegation."""

    def test_welcome_delegates_to_renderer(self, capsys: pytest.CaptureFixture) -> None:
        """welcome() delegates to MenuRenderer.show_welcome()."""
        session = InteractiveSession(use_colors=False)
        session.welcome()
        captured = capsys.readouterr()
        assert "agentfiles" in captured.out

    def test_main_menu_returns_pull(self, capsys: pytest.CaptureFixture) -> None:
        """Main menu returns 'pull' for input '1'."""
        session = InteractiveSession(use_colors=False)
        with patch("builtins.input", return_value="1"):
            result = session.main_menu()
        assert result == "pull"

    def test_main_menu_returns_status(self, capsys: pytest.CaptureFixture) -> None:
        """Main menu returns 'status' for input '3'."""
        session = InteractiveSession(use_colors=False)
        with patch("builtins.input", return_value="3"):
            result = session.main_menu()
        assert result == "status"

    def test_main_menu_returns_push(self, capsys: pytest.CaptureFixture) -> None:
        """Main menu returns 'push' for input '2'."""
        session = InteractiveSession(use_colors=False)
        with patch("builtins.input", return_value="2"):
            result = session.main_menu()
        assert result == "push"

    def test_main_menu_invalid_defaults_to_status(self, capsys: pytest.CaptureFixture) -> None:
        """Main menu returns 'status' for unrecognized numeric input."""
        session = InteractiveSession(use_colors=False)
        with patch("builtins.input", return_value="9"):
            result = session.main_menu()
        assert result == "status"


# ---------------------------------------------------------------------------
# Additional InteractiveRunner — run loop command dispatch
# ---------------------------------------------------------------------------


class TestInteractiveRunnerRunLoop:
    """Tests for InteractiveRunner.run() command dispatch and loop behavior."""

    def test_run_dispatches_pull_command(self, capsys: pytest.CaptureFixture) -> None:
        """Run loop dispatches 'pull' when user selects it from menu."""
        dispatch = MagicMock()
        runner = InteractiveRunner(command_dispatch=dispatch, use_colors=False)

        # prompt() calls: first returns "1" (pull), second returns "0" (quit).
        # builtins.input: "Press Enter" after dispatch (one call only).
        with (
            patch.object(runner._session._parser, "prompt", side_effect=["1", "0"]),
            patch("builtins.input", side_effect=[""]),
        ):
            runner.run()

        dispatch.assert_called_once_with("pull")
        captured = capsys.readouterr()
        assert "Goodbye" in captured.out

    def test_run_handles_command_exception(
        self,
        capsys: pytest.CaptureFixture,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Run loop catches and logs exceptions from command_dispatch."""
        caplog.set_level(logging.DEBUG, logger="agentfiles.interactive")
        dispatch = MagicMock(side_effect=RuntimeError("test error"))
        runner = InteractiveRunner(command_dispatch=dispatch, use_colors=False)

        # prompt() calls: first "1" (triggers error), second "0" (quit).
        with (
            patch.object(runner._session._parser, "prompt", side_effect=["1", "0"]),
            patch("builtins.input", side_effect=[""]),
        ):
            runner.run()

        captured = capsys.readouterr()
        # error() writes to stderr
        assert "Command failed" in captured.err
        assert any("Interactive command error" in r.message for r in caplog.records)

    def test_run_quit_immediately(self, capsys: pytest.CaptureFixture) -> None:
        """Choosing 'quit' on the first menu exits without dispatching."""
        dispatch = MagicMock()
        runner = InteractiveRunner(command_dispatch=dispatch, use_colors=False)

        with patch.object(runner._session._parser, "prompt", return_value="0"):
            runner.run()

        dispatch.assert_not_called()
        captured = capsys.readouterr()
        assert "Goodbye" in captured.out

    def test_run_multiple_commands_then_quit(self, capsys: pytest.CaptureFixture) -> None:
        """Run loop dispatches multiple commands before quitting."""
        dispatch = MagicMock()
        runner = InteractiveRunner(command_dispatch=dispatch, use_colors=False)

        # Simulate: prompt("Choose") returns pull, status, then quit
        prompt_returns = ["1", "4", "0"]
        # "Press Enter" input after each non-quit command
        press_enter_returns = ["", ""]

        with (
            patch.object(runner._session._parser, "prompt", side_effect=prompt_returns),
            patch(
                "builtins.input",
                side_effect=press_enter_returns,
            ),
        ):
            runner.run()

        assert dispatch.call_count == 2
        assert dispatch.call_args_list[0][0][0] == "pull"
        assert dispatch.call_args_list[1][0][0] == "status"

    def test_run_eof_during_command_exits_cleanly(self, capsys: pytest.CaptureFixture) -> None:
        """EOFError at 'Press Enter' after a command exits cleanly."""
        dispatch = MagicMock()
        runner = InteractiveRunner(command_dispatch=dispatch, use_colors=False)

        # prompt returns "1" (pull), then input("Press Enter") raises EOFError
        with (
            patch.object(runner._session._parser, "prompt", return_value="1"),
            patch("builtins.input", side_effect=EOFError),
        ):
            runner.run()

        dispatch.assert_called_once_with("pull")
        captured = capsys.readouterr()
        assert "Goodbye" in captured.out


# ---------------------------------------------------------------------------
# Additional InteractiveSession — confirmation with default values
# ---------------------------------------------------------------------------


class TestConfirmActionDefaults:
    """Tests for confirm_action with different default values."""

    def test_confirm_action_default_true_empty_input(self) -> None:
        """Empty input with default=True returns True."""
        session = InteractiveSession(use_colors=False)
        with patch("builtins.input", return_value=""):
            assert session.confirm_action("Proceed?", default=True) is True

    def test_confirm_action_default_false_empty_input(self) -> None:
        """Empty input with default=False returns False."""
        session = InteractiveSession(use_colors=False)
        with patch("builtins.input", return_value=""):
            assert session.confirm_action("Proceed?", default=False) is False

    def test_confirm_action_eof_uses_default(self) -> None:
        """EOFError during confirm returns the default value."""
        session = InteractiveSession(use_colors=False)
        with patch("builtins.input", side_effect=EOFError):
            assert session.confirm_action("Proceed?", default=True) is True
        with patch("builtins.input", side_effect=EOFError):
            assert session.confirm_action("Proceed?", default=False) is False


# ---------------------------------------------------------------------------
# Additional InteractiveSession — EOF / interrupt in selection methods
# ---------------------------------------------------------------------------


class TestSelectionEOFHandling:
    """Tests for EOF/interrupt handling in selection methods."""

    def test_select_platforms_eof_returns_all(self) -> None:
        """EOFError during platform selection returns all platforms."""
        session = InteractiveSession(use_colors=False)
        platforms = [Platform.OPENCODE, Platform.CLAUDE_CODE]
        with patch("builtins.input", side_effect=EOFError):
            result = session.select_platforms(platforms)
        assert result == list(platforms)

    def test_select_platforms_interrupt_raises(self) -> None:
        """KeyboardInterrupt during platform selection propagates to caller."""
        session = InteractiveSession(use_colors=False)
        with (
            patch("builtins.input", side_effect=KeyboardInterrupt),
            pytest.raises(KeyboardInterrupt),
        ):
            session.select_platforms([Platform.OPENCODE, Platform.CLAUDE_CODE])

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
