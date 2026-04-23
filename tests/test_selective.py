"""Tests for --item selective filtering by item key.

Covers:
- ``_apply_item_key_filter`` helper
- ``--item`` argument parsing
- Combination of ``--item`` with ``--only``
- Warning on nonexistent item keys
"""

from __future__ import annotations

import logging

import pytest

from agentfiles.cli import (
    _apply_item_key_filter,
    build_parser,
)
from tests.conftest import make_items

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# make_items() from conftest provides the standard test item set.


# ---------------------------------------------------------------------------
# _apply_item_key_filter
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestApplyItemKeyFilter:
    """Tests for _apply_item_key_filter() helper."""

    def test_none_returns_all(self) -> None:
        items = make_items()
        result = _apply_item_key_filter(items, None)
        assert result == items

    def test_empty_list_returns_all(self) -> None:
        items = make_items()
        result = _apply_item_key_filter(items, [])
        assert result == items

    def test_single_key(self) -> None:
        items = make_items()
        result = _apply_item_key_filter(items, ["agent/coder"])
        assert len(result) == 1
        assert result[0].name == "coder"

    def test_multiple_keys(self) -> None:
        items = make_items()
        result = _apply_item_key_filter(items, ["agent/coder", "skill/solid-principles"])
        assert len(result) == 2
        names = {i.name for i in result}
        assert names == {"coder", "solid-principles"}

    def test_key_not_found_returns_empty(self, caplog: pytest.LogCaptureFixture) -> None:
        items = make_items()
        with caplog.at_level(logging.WARNING):
            result = _apply_item_key_filter(items, ["agent/nonexistent"])
        assert result == []
        assert "No items matched --item filter" in caplog.text

    def test_partial_match(self) -> None:
        """Only exact key matches should work, not partial name matches."""
        items = make_items()
        # "coder" alone is not a valid key — must be "agent/coder"
        result = _apply_item_key_filter(items, ["coder"])
        assert result == []

    def test_mixed_types(self) -> None:
        items = make_items()
        result = _apply_item_key_filter(items, ["agent/debugger", "command/autopilot"])
        assert len(result) == 2
        names = {i.name for i in result}
        assert names == {"debugger", "autopilot"}


# ---------------------------------------------------------------------------
# --item argument parsing
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestItemArgParsing:
    """Tests for --item argument in the CLI parser."""

    def test_pull_single_item(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["pull", "--item", "agent/coder", "--yes"])
        assert args.item == ["agent/coder"]

    def test_pull_multiple_items(self) -> None:
        parser = build_parser()
        args = parser.parse_args(
            [
                "pull",
                "--item",
                "agent/coder",
                "--item",
                "skill/docker",
                "--yes",
            ]
        )
        assert args.item == ["agent/coder", "skill/docker"]

    def test_push_item(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["push", "--item", "agent/coder", "--yes"])
        assert args.item == ["agent/coder"]

    def test_clean_item(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["clean", "--item", "agent/coder", "--yes"])
        assert args.item == ["agent/coder"]

    def test_no_item_flag(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["pull", "--yes"])
        assert args.item is None


# ---------------------------------------------------------------------------
# --item combined with --only
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestItemWithOnlyFilter:
    """Tests for --item combined with --only (both filters apply)."""

    def test_item_and_only_both_apply(self) -> None:
        """--only filters by name, --item filters by key; both narrow."""
        from agentfiles.cli import _apply_item_filter

        items = make_items()
        # --only coder,debugger keeps both agents
        filtered = _apply_item_filter(items, {"coder", "debugger"}, None)
        # --item agent/coder narrows to just coder
        result = _apply_item_key_filter(filtered, ["agent/coder"])
        assert len(result) == 1
        assert result[0].name == "coder"
