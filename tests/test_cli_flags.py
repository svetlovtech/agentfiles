"""Tests for --color, --only, and --except CLI flags.

Covers:
- ``--color`` tri-state global flag (always / auto / never)
- ``--only`` and ``--except`` per-subcommand item-name filtering
- ``_resolve_item_filter`` and ``_apply_item_filter`` helpers
- Integration with the argument parser and main() entry point
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from syncode.cli import (
    _apply_color_env,
    _apply_item_filter,
    _resolve_item_filter,
    build_parser,
)
from syncode.models import Item, ItemType

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_item(name: str, item_type: ItemType = ItemType.AGENT) -> Item:
    """Create a minimal Item for testing."""
    return Item(
        item_type=item_type,
        name=name,
        source_path=Path("/fake/source"),
    )


def _make_items() -> list[Item]:
    """Create a standard set of test items."""
    return [
        _make_item("coder", ItemType.AGENT),
        _make_item("debugger", ItemType.AGENT),
        _make_item("solid-principles", ItemType.SKILL),
        _make_item("dry-principle", ItemType.SKILL),
        _make_item("autopilot", ItemType.COMMAND),
    ]


# ---------------------------------------------------------------------------
# _resolve_item_filter
# ---------------------------------------------------------------------------


class TestResolveItemFilter:
    """Tests for _resolve_item_filter() helper."""

    def test_no_filters_returns_none_none(self) -> None:
        args = argparse.Namespace(only=None, except_items=None)
        only_set, except_set = _resolve_item_filter(args)
        assert only_set is None
        assert except_set is None

    def test_only_returns_set_of_names(self) -> None:
        args = argparse.Namespace(only="coder,debugger", except_items=None)
        only_set, except_set = _resolve_item_filter(args)
        assert only_set == {"coder", "debugger"}
        assert except_set is None

    def test_except_returns_set_of_names(self) -> None:
        args = argparse.Namespace(only=None, except_items="old-plugin,deprecated")
        only_set, except_set = _resolve_item_filter(args)
        assert only_set is None
        assert except_set == {"old-plugin", "deprecated"}

    def test_both_filters_return_both_sets(self) -> None:
        args = argparse.Namespace(
            only="coder,debugger",
            except_items="debugger",
        )
        only_set, except_set = _resolve_item_filter(args)
        assert only_set == {"coder", "debugger"}
        assert except_set == {"debugger"}

    def test_only_strips_whitespace(self) -> None:
        args = argparse.Namespace(only="  coder ,  debugger  ", except_items=None)
        only_set, except_set = _resolve_item_filter(args)
        assert only_set == {"coder", "debugger"}

    def test_except_strips_whitespace(self) -> None:
        args = argparse.Namespace(only=None, except_items=" old , new ")
        only_set, except_set = _resolve_item_filter(args)
        assert except_set == {"old", "new"}

    def test_only_empty_entries_ignored(self) -> None:
        args = argparse.Namespace(only="coder,,debugger,", except_items=None)
        only_set, except_set = _resolve_item_filter(args)
        assert only_set == {"coder", "debugger"}

    def test_only_single_item(self) -> None:
        args = argparse.Namespace(only="coder", except_items=None)
        only_set, except_set = _resolve_item_filter(args)
        assert only_set == {"coder"}

    def test_only_all_whitespace_produces_empty_set(self) -> None:
        """Whitespace-only entries produce an empty set (not None)."""
        args = argparse.Namespace(only="  ,  ,  ", except_items=None)
        only_set, except_set = _resolve_item_filter(args)
        assert only_set is not None
        assert len(only_set) == 0


# ---------------------------------------------------------------------------
# _apply_item_filter
# ---------------------------------------------------------------------------


class TestApplyItemFilter:
    """Tests for _apply_item_filter() helper."""

    def test_no_filters_returns_all_items(self) -> None:
        items = _make_items()
        result = _apply_item_filter(items, None, None)
        assert result == items

    def test_only_filters_to_matching_names(self) -> None:
        items = _make_items()
        result = _apply_item_filter(items, {"coder", "solid-principles"}, None)
        names = [i.name for i in result]
        assert names == ["coder", "solid-principles"]

    def test_except_removes_matching_names(self) -> None:
        items = _make_items()
        result = _apply_item_filter(items, None, {"debugger", "dry-principle"})
        names = [i.name for i in result]
        assert "debugger" not in names
        assert "dry-principle" not in names
        assert "coder" in names
        assert "solid-principles" in names
        assert "autopilot" in names

    def test_only_and_except_combined(self) -> None:
        """--only limits scope, then --except further excludes."""
        items = _make_items()
        result = _apply_item_filter(items, {"coder", "debugger"}, {"debugger"})
        names = [i.name for i in result]
        assert names == ["coder"]

    def test_only_with_no_match_returns_empty(self) -> None:
        items = _make_items()
        result = _apply_item_filter(items, {"nonexistent"}, None)
        assert result == []

    def test_except_with_all_match_returns_empty(self) -> None:
        items = _make_items()
        all_names = {i.name for i in items}
        result = _apply_item_filter(items, None, all_names)
        assert result == []

    def test_empty_items_list_returns_empty(self) -> None:
        result = _apply_item_filter([], {"coder"}, None)
        assert result == []

    def test_only_empty_set_returns_empty(self) -> None:
        """An empty only_set (from whitespace-only input) matches nothing."""
        items = _make_items()
        result = _apply_item_filter(items, set(), None)
        assert result == []

    def test_except_empty_set_returns_all(self) -> None:
        """An empty except_set excludes nothing."""
        items = _make_items()
        result = _apply_item_filter(items, None, set())
        assert result == items


# ---------------------------------------------------------------------------
# build_parser -- --color flag
# ---------------------------------------------------------------------------


class TestParserColorFlag:
    """Tests for the global --color flag in the argument parser."""

    def test_color_default_is_auto(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["pull"])
        assert args.color == "auto"

    def test_color_always(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["--color", "always", "pull"])
        assert args.color == "always"

    def test_color_never(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["--color", "never", "pull"])
        assert args.color == "never"

    def test_color_before_subcommand(self) -> None:
        """--color must be accepted before the subcommand name."""
        parser = build_parser()
        args = parser.parse_args(["--color", "never", "pull"])
        assert args.color == "never"
        assert args.command == "pull"

    def test_color_invalid_choice_rejected(self) -> None:
        parser = build_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["--color", "invalid", "pull"])

    @pytest.mark.parametrize(
        "subcommand",
        ["pull", "push", "sync", "list", "diff", "uninstall", "branch"],
    )
    def test_color_available_for_all_subcommands(self, subcommand: str) -> None:
        """--color should be available regardless of which subcommand is used."""
        parser = build_parser()
        args = parser.parse_args(["--color", "always", subcommand])
        assert args.color == "always"


# ---------------------------------------------------------------------------
# build_parser -- --only and --except flags
# ---------------------------------------------------------------------------


class TestParserItemFilterFlags:
    """Tests for --only and --except per-subcommand flags."""

    def test_only_flag_parsed(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["pull", "--only", "coder,debugger"])
        assert args.only == "coder,debugger"

    def test_except_flag_parsed(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["pull", "--except", "old-plugin"])
        assert args.except_items == "old-plugin"

    def test_only_and_except_together(self) -> None:
        parser = build_parser()
        args = parser.parse_args(
            [
                "pull",
                "--only",
                "coder",
                "--except",
                "debugger",
            ]
        )
        assert args.only == "coder"
        assert args.except_items == "debugger"

    def test_no_filter_defaults_to_none(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["pull"])
        assert args.only is None
        assert args.except_items is None

    @pytest.mark.parametrize(
        "subcommand",
        ["pull", "push", "sync", "list", "diff", "uninstall", "branch"],
    )
    def test_filter_flags_available_for_common_subcommands(
        self,
        subcommand: str,
    ) -> None:
        """--only and --except should be available on subcommands using _add_common_args."""
        parser = build_parser()
        args = parser.parse_args([subcommand, "--only", "test-item"])
        assert args.only == "test-item"

    def test_init_subcommand_has_no_filter_flags(self) -> None:
        """init does not use _add_common_args, so filter flags should not be present."""
        parser = build_parser()
        args = parser.parse_args(["init"])
        assert not hasattr(args, "only") or args.only is None
        assert not hasattr(args, "except_items") or args.except_items is None


# ---------------------------------------------------------------------------
# main() --color env var propagation
# ---------------------------------------------------------------------------


class TestMainColorEnvVars:
    """Tests for the --color flag setting environment variables in main()."""

    def test_color_never_sets_no_color_env(self) -> None:
        """--color never should set NO_COLOR and clear FORCE_COLOR."""
        with patch.dict(os.environ, {}, clear=True):
            _apply_color_env("never")
            assert os.environ.get("NO_COLOR") == "1"
            assert "FORCE_COLOR" not in os.environ
            assert "CLICOLOR_FORCE" not in os.environ

    def test_color_always_sets_force_color_env(self) -> None:
        """--color always should set FORCE_COLOR and clear NO_COLOR."""
        with patch.dict(os.environ, {}, clear=True):
            _apply_color_env("always")
            assert os.environ.get("FORCE_COLOR") == "1"
            assert "NO_COLOR" not in os.environ

    def test_color_auto_leaves_env_untouched(self) -> None:
        """--color auto should not modify environment variables."""
        with patch.dict(os.environ, {"SOME_VAR": "1"}, clear=True):
            _apply_color_env("auto")
            assert os.environ.get("SOME_VAR") == "1"
            assert "NO_COLOR" not in os.environ
            assert "FORCE_COLOR" not in os.environ

    def test_color_never_clears_existing_force_color(self) -> None:
        """If FORCE_COLOR is already set, --color never should clear it."""
        with patch.dict(os.environ, {"FORCE_COLOR": "1"}, clear=True):
            _apply_color_env("never")
            assert "FORCE_COLOR" not in os.environ
            assert os.environ.get("NO_COLOR") == "1"

    def test_color_always_clears_existing_no_color(self) -> None:
        """If NO_COLOR is already set, --color always should clear it."""
        with patch.dict(os.environ, {"NO_COLOR": "1"}, clear=True):
            _apply_color_env("always")
            assert "NO_COLOR" not in os.environ
            assert os.environ.get("FORCE_COLOR") == "1"


# ---------------------------------------------------------------------------
# End-to-end filter pipeline integration
# ---------------------------------------------------------------------------


class TestFilterPipelineIntegration:
    """Integration tests for the full filter pipeline: parse args → filter items."""

    def test_only_filters_items_end_to_end(self) -> None:
        """Parse --only, resolve filter, apply to items."""
        parser = build_parser()
        args = parser.parse_args(["list", "--only", "coder,debugger"])
        only_set, except_set = _resolve_item_filter(args)
        items = _make_items()
        filtered = _apply_item_filter(items, only_set, except_set)
        names = [i.name for i in filtered]
        assert names == ["coder", "debugger"]

    def test_except_filters_items_end_to_end(self) -> None:
        """Parse --except, resolve filter, apply to items."""
        parser = build_parser()
        args = parser.parse_args(["list", "--except", "autopilot"])
        only_set, except_set = _resolve_item_filter(args)
        items = _make_items()
        filtered = _apply_item_filter(items, only_set, except_set)
        names = [i.name for i in filtered]
        assert "autopilot" not in names
        assert len(filtered) == 4

    def test_no_filter_passes_all_items_end_to_end(self) -> None:
        """No --only / --except should pass all items through."""
        parser = build_parser()
        args = parser.parse_args(["list"])
        only_set, except_set = _resolve_item_filter(args)
        items = _make_items()
        filtered = _apply_item_filter(items, only_set, except_set)
        assert len(filtered) == len(items)
