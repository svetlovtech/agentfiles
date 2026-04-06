"""Interactive prompts for the agentfiles CLI.

Provides terminal-based selection menus, confirmation dialogs, and diff
resolution using only the standard library.  All prompts use raw
``input()`` calls with optional ANSI colour output.

The module is organised into focused classes that follow the
Single Responsibility Principle:

- :class:`MenuRenderer` — display formatting and visual output.
- :class:`InputParser` — user input collection and parsing.
- :class:`InteractiveSession` — thin facade that composes the two
  above and preserves the public API.
- :class:`InteractiveRunner` — main interactive loop orchestration.

Respects the ``NO_COLOR`` environment variable and automatically disables
colours when stdout is not a TTY.
"""

from __future__ import annotations

import logging
import sys
from collections import defaultdict
from collections.abc import Callable
from pathlib import Path
from typing import Any

from agentfiles.models import (
    DiffEntry,
    DiffStatus,
    Item,
    ItemType,
    Platform,
    SyncAction,
    SyncPlan,
)
from agentfiles.output import (
    DIFF_STATUS_STYLES,
    Colors,
    colorize,
    error,
    info,
    print_banner,
    should_use_colors,
    warning,
)

# Message shown when a user declines a confirmation prompt.
_ABORTED_MESSAGE = "Aborted."

# Maximum number of re-prompts before falling back to defaults.
_MAX_INPUT_RETRIES = 3

logger = logging.getLogger(__name__)

# Maps SyncAction to display symbols and colours.
_ACTION_SYMBOLS: dict[SyncAction, tuple[str, str]] = {
    SyncAction.INSTALL: ("+", Colors.GREEN),
    SyncAction.UPDATE: ("~", Colors.YELLOW),
    SyncAction.SKIP: ("-", Colors.DIM),
    SyncAction.UNINSTALL: ("x", Colors.RED),
}

# DiffStatus display — derived from the canonical DIFF_STATUS_STYLES.
_STATUS_SYMBOLS: dict[DiffStatus, tuple[str, str]] = {
    status: (style.symbol, style.ansi_color) for status, style in DIFF_STATUS_STYLES.items()
}

# Menu definitions used by InteractiveSession.
_SYNC_MODES: list[tuple[str, str]] = [
    ("install", "Install all (copy new items)"),
    ("update", "Update all (update changed items)"),
    ("full", "Full sync (install new + update changed)"),
    ("custom", "Custom (select items manually)"),
]

_MAIN_MENU: list[tuple[str, str, str]] = [
    ("1", "pull", "Pull items from repo to local configs"),
    ("2", "push", "Push local changes back to repo"),
    ("3", "status", "Show installed items"),
    ("0", "quit", "Exit"),
]


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------


def _parse_comma_list(input_str: str) -> list[str]:
    """Split a user string by commas or whitespace into a cleaned list.

    Empty tokens are discarded.  Returns an empty list for blank input.
    """
    raw = input_str.replace(",", " ").split()
    return [token.strip().lower() for token in raw if token.strip()]


def _parse_ranges(input_str: str, max_value: int) -> list[int]:
    """Parse a range expression like ``"1,3,5-10"`` into a sorted int list.

    Out-of-range values and duplicates are silently ignored.

    Returns:
        Sorted list of unique 1-based indices within ``[1, max_value]``.

    """
    tokens = _parse_comma_list(input_str)
    result: set[int] = set()

    for token in tokens:
        if "-" in token:
            parts = token.split("-", maxsplit=1)
            if len(parts) != 2:
                continue
            try:
                start, end = int(parts[0]), int(parts[1])
            except ValueError:
                continue
            result.update(range(start, end + 1))
        else:
            try:
                result.add(int(token))
            except ValueError:
                continue

    return sorted(i for i in result if 1 <= i <= max_value)


def _guess_platform(target_dir: Path) -> Platform:
    """Heuristic: pick Platform based on directory path content."""
    path_str = str(target_dir).lower()
    if "opencode" in path_str:
        return Platform.OPENCODE
    if "windsurf" in path_str or "codeium" in path_str:
        return Platform.WINDSURF
    if "cursor" in path_str:
        return Platform.CURSOR
    return Platform.CLAUDE_CODE


def _item_key(item: Item) -> str:
    """Compute a unique key for an item — delegates to :attr:`Item.item_key`."""
    return item.item_key


# ---------------------------------------------------------------------------
# MenuRenderer — display formatting and visual output
# ---------------------------------------------------------------------------


class MenuRenderer:
    """Handles all display formatting and visual output for interactive prompts.

    Args:
        use_colors: When ``True`` (default), output is coloured with
            ANSI escape sequences.

    """

    def __init__(self, use_colors: bool = True) -> None:
        """Initialise the renderer with optional colour support."""
        self._use_colors = use_colors

    def _c(self, text: str, color: str) -> str:
        """Colour *text* only when colours are enabled."""
        if not self._use_colors:
            return text
        return colorize(text, color)

    # -- banner / headers --------------------------------------------------

    def show_welcome(self) -> None:
        """Display a welcome banner."""
        from agentfiles import __version__

        lines = [
            colorize("agentfiles", Colors.BOLD) + f" v{__version__}",
            "Load AI tool configurations across platforms",
        ]
        print_banner(lines)
        print()

    def show_diff_header(self) -> None:
        """Display the diff resolution header."""
        sys.stdout.write(
            f"\n{self._c('Resolve differences:', Colors.BOLD)}\n"
            "  [i]nstall  [u]pdate  [s]kip  [a]ll  [q]uit\n\n"
        )

    # -- selection lists ---------------------------------------------------

    def show_platforms(self, available: list[Platform]) -> None:
        """Display a numbered list of available platforms."""
        lines = [f"\n{self._c('Available platforms:', Colors.BOLD)}"]
        lines.extend(f"  {idx}) {p.display_name}" for idx, p in enumerate(available, start=1))
        sys.stdout.write("\n".join(lines) + "\n")

    def show_item_types(self, types: list[ItemType]) -> None:
        """Display a numbered list of item types."""
        lines = [f"\n{self._c('Item types:', Colors.BOLD)}"]
        lines.extend(f"  {idx}) {t.plural.title()}" for idx, t in enumerate(types, start=1))
        sys.stdout.write("\n".join(lines) + "\n")

    def show_items_grouped(self, items: list[Item]) -> dict[int, Item]:
        """Display items grouped by type with continuous numbering.

        Returns:
            Mapping of 1-based index to :class:`Item`.

        """
        by_type: dict[ItemType, list[Item]] = defaultdict(list)
        for item in items:
            by_type[item.item_type].append(item)

        index_map: dict[int, Item] = {}
        counter = 1
        buf: list[str] = [""]

        for item_type, group_items in by_type.items():
            label = self._c(
                f"{item_type.plural.title()} ({len(group_items)}):",
                Colors.BOLD,
            )
            buf.append(f"  {label}")
            for item in group_items:
                buf.append(f"    [{counter}] {item.name}")
                index_map[counter] = item
                counter += 1
            buf.append("")

        sys.stdout.write("\n".join(buf) + "\n")
        return index_map

    # -- menus -------------------------------------------------------------

    def show_sync_modes(self) -> None:
        """Display the sync mode selection menu."""
        lines = ["", self._c("Load mode:", Colors.BOLD)]
        lines.extend(f"  {idx}) {desc}" for idx, (_, desc) in enumerate(_SYNC_MODES, start=1))
        sys.stdout.write("\n".join(lines) + "\n")

    def show_main_menu(self) -> None:
        """Display the main action menu."""
        lines = [
            self._c("What would you like to do?", Colors.BOLD),
            "",
        ]
        lines.extend(f"  {self._c(num, Colors.BOLD)}) {desc}" for num, _, desc in _MAIN_MENU)
        lines.append("")
        sys.stdout.write("\n".join(lines) + "\n")

    # -- plan summary ------------------------------------------------------

    def show_no_plans_message(self) -> None:
        """Display a message when no sync actions are planned."""
        sys.stdout.write(self._c("\nNo load actions planned.\n", Colors.YELLOW))

    def show_plan_summary(self, plans: list[SyncPlan]) -> None:
        """Display a human-readable summary of sync plans.

        The summary groups items by action type, then by platform.
        """
        by_platform_action: dict[tuple[Platform, SyncAction], list[SyncPlan]] = defaultdict(list)
        action_counts: dict[SyncAction, int] = defaultdict(int)

        # Cache platform guesses to avoid redundant string conversions
        # for plans targeting the same directory.
        _platform_cache: dict[str, Platform] = {}

        for plan in plans:
            target_key = str(plan.target_dir)
            if target_key not in _platform_cache:
                _platform_cache[target_key] = _guess_platform(plan.target_dir)
            platform = _platform_cache[target_key]

            key = (platform, plan.action)
            by_platform_action[key].append(plan)
            action_counts[plan.action] += 1

        buf: list[str] = ["", self._c("Load plan:", Colors.BOLD)]

        for action in SyncAction:
            count = action_counts.get(action, 0)
            if not count:
                continue
            symbol, colour = _ACTION_SYMBOLS[action]
            label = self._c(f"{symbol} {action.value.title()}", colour)
            buf.append(f"  {label}: {count} items")

        buf.append("")

        for (platform, action), action_plans in sorted(
            by_platform_action.items(),
            key=lambda kv: (kv[0][0].value, kv[0][1].value),
        ):
            symbol, colour = _ACTION_SYMBOLS[action]
            header = self._c(
                f"  {symbol} {action.value.title()} to {platform.display_name}:",
                colour,
            )
            buf.append(header)
            for plan in action_plans:
                detail = f"    {symbol} {plan.item.name} ({plan.item.item_type.value})"
                if plan.reason:
                    detail += self._c(f" — {plan.reason}", Colors.DIM)
                buf.append(detail)
            buf.append("")

        sys.stdout.write("\n".join(buf) + "\n")

    # -- diff formatting ---------------------------------------------------

    def format_diff_status(self, status: DiffStatus) -> str:
        """Return a colour-formatted diff status label."""
        symbol, colour = _STATUS_SYMBOLS[status]
        return self._c(f"{symbol} {status.value}", colour)


# ---------------------------------------------------------------------------
# InputParser — user input collection and parsing
# ---------------------------------------------------------------------------


class InputParser:
    """Handles user input collection and parsing for interactive prompts.

    Delegates colour formatting to a :class:`MenuRenderer` instance.

    Args:
        renderer: The renderer used for colouring prompt text.

    """

    def __init__(self, renderer: MenuRenderer) -> None:
        """Initialise the parser with a renderer for colour output."""
        self._renderer = renderer

    def prompt(self, message: str) -> str:
        """Display a coloured prompt and wait for user input.

        Handles ``KeyboardInterrupt`` and ``EOFError`` gracefully by
        returning an empty string so callers can treat it as a
        cancellation.  ``EOFError`` occurs when stdin is closed or
        exhausted (e.g. piped input).
        """
        try:
            return input(self._renderer._c(message, Colors.BOLD)).strip()
        except (KeyboardInterrupt, EOFError):
            print()
            return ""

    def confirm(self, message: str, default: bool = False) -> bool:
        """Ask a yes/no confirmation question.

        Returns:
            ``True`` on confirmation, ``False`` on rejection or
            cancellation (Ctrl+C).

        """
        hint = "[Y/n]" if default else "[y/N]"
        raw = self.prompt(f"{message} {hint} ")
        if not raw:
            return default
        return raw.lower().startswith("y")

    # -- selection parsers -------------------------------------------------

    def parse_platforms(
        self,
        raw: str,
        available: list[Platform],
    ) -> list[Platform]:
        """Parse a raw input string into a list of selected platforms.

        Accepts numeric indices and platform enum values.
        """
        tokens = _parse_comma_list(raw)
        selected: dict[Platform, None] = {}

        for token in tokens:
            try:
                idx = int(token)
                if 1 <= idx <= len(available):
                    selected[available[idx - 1]] = None
                continue
            except ValueError:
                pass

            for platform in available:
                if platform.value == token:
                    selected[platform] = None

        return list(selected)

    def parse_item_type_selection(
        self,
        raw: str,
        types: list[ItemType],
    ) -> list[ItemType]:
        """Parse a range expression into selected item types."""
        indices = _parse_ranges(raw, len(types))
        return [types[i - 1] for i in indices if 1 <= i <= len(types)]

    def parse_ranges(self, raw: str, max_value: int) -> list[int]:
        """Delegate to module-level ``_parse_ranges``."""
        return _parse_ranges(raw, max_value)

    def parse_sync_mode(self, raw: str) -> str:
        """Parse user input into a sync mode key.

        Returns ``"full"`` on empty or unrecognised input.
        """
        if not raw:
            return "full"

        try:
            idx = int(raw)
            if 1 <= idx <= len(_SYNC_MODES):
                return _SYNC_MODES[idx - 1][0]
        except ValueError:
            pass

        for key, _ in _SYNC_MODES:
            if key.startswith(raw.lower()):
                return key

        return "full"

    def parse_main_menu_choice(self, raw: str) -> str:
        """Parse user input into a main menu action key.

        Returns ``"status"`` on empty or unrecognised input.
        """
        if not raw:
            return "status"

        try:
            idx = int(raw)
            if idx == 0:
                return "quit"
            for num, key, _ in _MAIN_MENU:
                if num == str(idx):
                    return key
        except ValueError:
            pass

        for _, key, _ in _MAIN_MENU:
            if key.startswith(raw.lower()):
                return key

        return "status"

    _DIFF_CHOICE_MAP: dict[str, SyncAction | None] = {
        "i": SyncAction.INSTALL,
        "install": SyncAction.INSTALL,
        "u": SyncAction.UPDATE,
        "update": SyncAction.UPDATE,
        "s": SyncAction.SKIP,
        "skip": SyncAction.SKIP,
        "a": SyncAction.INSTALL,
        "all": SyncAction.INSTALL,
        "q": None,
        "quit": None,
    }

    def resolve_diff_choice(self, raw: str) -> SyncAction | None:
        """Map user input to a :class:`SyncAction`.

        Returns ``None`` when the user quits.
        """
        key = raw.strip().lower() or "skip"
        return self._DIFF_CHOICE_MAP.get(key)


# ---------------------------------------------------------------------------
# InteractiveSession — thin facade (preserves public API)
# ---------------------------------------------------------------------------


class InteractiveSession:
    """Terminal-based interactive prompts for agentfiles operations.

    Composes :class:`MenuRenderer` for display formatting and
    :class:`InputParser` for input handling.

    The public API is organised into four interface segments.  Callers
    typically only need one or two segments:

    **Selection prompts** — used by pull/push commands::

        choose_sync_mode()      → str          # cmd_pull
        select_platforms(...)   → list[Platform]  # cmd_pull
        select_item_types()     → list[ItemType]  # cmd_pull
        select_items(...)       → list[Item]       # cmd_pull, cmd_push

    **Confirmation prompts** — used by most commands that modify state::

        confirm_action(...)              → bool  # internal base method
        confirm_plans(...)               → bool  # internal base method
        confirm_action_or_abort(...)     → bool  # cmd_clean, cmd_init
        confirm_plans_or_abort(...)      → bool  # cmd_pull

    **Navigation** — used by :class:`InteractiveRunner` only::

        welcome()       → None   # banner display
        main_menu()     → str    # menu choice dispatch

    **Diff / conflict resolution** — reserved for interactive sync
    workflows (currently exercised by tests only)::

        select_diff_action(...)          → dict[str, SyncAction]
        choose_push_items(...)           → list[tuple[Item, Platform]]
        resolve_sync_conflicts(...)      → dict[str, str]

    Args:
        use_colors: When ``None`` (default), colour output is
            automatically enabled when stdout is a TTY and the
            ``NO_COLOR`` environment variable is unset.  Pass ``True``
            to force colours or ``False`` to disable them.

    """

    def __init__(self, use_colors: bool | None = None) -> None:
        """Initialise the session with auto-detected or explicit colour settings."""
        if use_colors is None:
            use_colors = should_use_colors()
        self._renderer = MenuRenderer(use_colors)
        self._parser = InputParser(self._renderer)

    # -- private helpers -------------------------------------------------------

    def _retry_selection(
        self,
        raw: str,
        parse_fn: Callable[[str], list[Any]],
        prompt_msg: str,
        fallback: list[Any],
    ) -> list[Any]:
        """Re-prompt when non-empty input parses to an empty result.

        Args:
            raw: Current user input (non-empty, not ``"all"``).
            parse_fn: Callable that turns raw input into a typed list.
            prompt_msg: Prompt text shown on retry.
            fallback: Value returned after exhausting retries.

        Returns:
            Parsed result, or *fallback* when retries are exhausted
            or the user submits empty/``"all"`` input.

        """
        for attempt in range(_MAX_INPUT_RETRIES):
            result = parse_fn(raw)
            if result:
                return result

            remaining = _MAX_INPUT_RETRIES - attempt - 1
            if remaining > 0:
                warning("No valid selection found. Please try again.")
                raw = self._parser.prompt(prompt_msg)
                if not raw or raw.lower() == "all":
                    return fallback
            else:
                warning("No valid selection found. Using defaults.")
                return fallback

        return fallback

    # -- public API: selection prompts -------------------------------------

    def select_platforms(self, available: list[Platform]) -> list[Platform]:
        """Let the user pick one or more platforms from *available*.

        Accepts: ``all``, numbers (``1``), comma-separated (``1,2``),
        space-separated (``1 2``), or platform enum values
        (``opencode``, ``claude_code``).

        Re-prompts up to :data:`_MAX_INPUT_RETRIES` times when the
        user enters non-empty input that resolves to no valid platform.

        Returns:
            List of selected :class:`Platform` values.
            Returns all platforms on cancellation (Ctrl+C), EOF, or
            after exhausting retries.

        """
        if not available:
            return []

        prompt_msg = "Select platforms to load (comma-separated, or 'all'): "
        self._renderer.show_platforms(available)
        raw = self._parser.prompt(prompt_msg)

        if not raw or raw.lower() == "all":
            return list(available)

        return self._retry_selection(
            raw=raw,
            parse_fn=lambda r: self._parser.parse_platforms(r, available),
            prompt_msg=prompt_msg,
            fallback=list(available),
        )

    def select_item_types(self) -> list[ItemType]:
        """Let the user pick one or more item types to sync.

        Re-prompts on non-empty input that resolves to no valid types.

        Returns:
            List of selected :class:`ItemType` values.

        """
        types = list(ItemType)
        prompt_msg = "Select item types to load (comma-separated, or 'all'): "
        self._renderer.show_item_types(types)
        raw = self._parser.prompt(prompt_msg)

        if not raw or raw.lower() == "all":
            return types

        return self._retry_selection(
            raw=raw,
            parse_fn=lambda r: self._parser.parse_item_type_selection(r, types),
            prompt_msg=prompt_msg,
            fallback=types,
        )

    def select_items(self, items: list[Item]) -> list[Item]:
        """Let the user pick items from a grouped, numbered list.

        Items are grouped by :class:`ItemType` with continuous numbering
        across groups.  Supports ranges like ``1,3,5-10,21-30`` and the
        keyword ``all``.

        Re-prompts on non-empty input that resolves to no valid indices.

        Returns:
            List of selected :class:`Item` instances.

        """
        if not items:
            return []

        index_map = self._renderer.show_items_grouped(items)
        total = len(items)
        prompt_msg = f"Select items to load (ranges ok: 1,3,5-10,{total}): "
        raw = self._parser.prompt(prompt_msg)

        if not raw or raw.lower() == "all":
            return list(items)

        def _parse(raw_input: str) -> list[Item]:
            indices = self._parser.parse_ranges(raw_input, total)
            return [index_map[i] for i in indices]

        return self._retry_selection(
            raw=raw,
            parse_fn=_parse,
            prompt_msg=prompt_msg,
            fallback=list(items),
        )

    # -- public API: confirmation prompts ----------------------------------

    def confirm_action(self, message: str, default: bool = False) -> bool:
        """Ask a yes/no confirmation question.

        The prompt shows ``[y/N]`` when *default* is ``False``,
        or ``[Y/n]`` when *default* is ``True``.

        Returns:
            ``True`` on confirmation, ``False`` on rejection or
            cancellation (Ctrl+C).

        """
        return self._parser.confirm(message, default)

    def confirm_plans(self, plans: list[SyncPlan]) -> bool:
        """Display a human-readable summary of sync plans and ask to proceed.

        The summary groups items by action type, then by platform.

        Returns:
            ``True`` if the user confirms, ``False`` otherwise.

        """
        if not plans:
            self._renderer.show_no_plans_message()
            return False

        self._renderer.show_plan_summary(plans)
        return self._parser.confirm("Proceed?", default=False)

    def confirm_action_or_abort(
        self,
        message: str,
        default: bool = False,
    ) -> bool:
        """Confirm an action; print abort message on rejection.

        Convenience method that combines :meth:`confirm_action` with
        the standard "Aborted." feedback so callers can write::

            if not session.confirm_action_or_abort("Continue?"):
                return 0

        Returns:
            ``True`` if the user confirms, ``False`` otherwise (after
            printing the abort message).

        """
        if self.confirm_action(message, default):
            return True
        info(_ABORTED_MESSAGE)
        return False

    def confirm_plans_or_abort(self, plans: list[SyncPlan]) -> bool:
        """Confirm sync plans; print abort message on rejection.

        Convenience method that combines :meth:`confirm_plans` with
        the standard "Aborted." feedback so callers can write::

            if not session.confirm_plans_or_abort(plans):
                return 0

        Returns:
            ``True`` if the user confirms, ``False`` otherwise (after
            printing the abort message).

        """
        if self.confirm_plans(plans):
            return True
        info(_ABORTED_MESSAGE)
        return False

    def select_diff_action(
        self,
        diff_entries: list[tuple[DiffEntry, Platform]],
    ) -> dict[str, SyncAction]:
        """Interactively resolve diffs by choosing an action per item.

        The user is prompted for each entry unless they pick ``all``
        (apply current choice to remaining items) or ``quit``.

        Returns:
            Mapping of ``"{item_type}:{item_name}"`` to the chosen
            :class:`SyncAction`.

        """
        if not diff_entries:
            return {}

        self._renderer.show_diff_header()
        result: dict[str, SyncAction] = {}
        batch_action: SyncAction | None = None

        for entry, platform in diff_entries:
            if batch_action is not None:
                result[_item_key(entry.item)] = batch_action
                continue

            status_label = self._renderer.format_diff_status(entry.status)
            prompt_msg = (
                f"  {entry.item.name} ({entry.item.item_type.value}) "
                f"[{platform.display_name}] {status_label}: "
            )
            raw = self._parser.prompt(prompt_msg)

            action = self._parser.resolve_diff_choice(raw)
            if action is None:
                break

            # "a"/"all" means apply this action to all remaining entries
            if raw.strip().lower() in ("a", "all"):
                batch_action = action

            result[_item_key(entry.item)] = action

        return result

    def choose_sync_mode(self) -> str:
        """Let the user pick a sync mode.

        Returns:
            One of ``"install"``, ``"update"``, ``"full"``, or
            ``"custom"``.  Returns ``"full"`` on empty input.

        """
        self._renderer.show_sync_modes()
        raw = self._parser.prompt("Choose mode [3]: ")
        return self._parser.parse_sync_mode(raw)

    # -- public API: navigation (used by InteractiveRunner) ----------------

    def welcome(self) -> None:
        """Display a welcome banner."""
        self._renderer.show_welcome()

    def main_menu(self) -> str:
        """Display the main menu and return the user's choice.

        Returns:
            One of: ``"pull"``, ``"push"``, ``"status"``, ``"quit"``.

        """
        self._renderer.show_main_menu()
        raw = self._parser.prompt("Choose [1]: ")
        return self._parser.parse_main_menu_choice(raw)

    # -- public API: diff / conflict resolution (reserved for sync) -------

    def choose_push_items(
        self,
        items: list[Item],
        platforms: list[Platform],
    ) -> list[tuple[Item, Platform]]:
        """Let user select which locally-modified items to push back to repo.

        Shows items grouped by type with their current status.
        Returns list of (item, platform) tuples to push.
        """
        if not items:
            info("No locally-modified items to push.")
            return []

        index_map = self._renderer.show_items_grouped(items)
        self._renderer.show_platforms(platforms)

        raw_platforms = self._parser.prompt(
            "Select target platforms (comma-separated, or 'all'): ",
        )
        if not raw_platforms or raw_platforms.lower() == "all":
            selected_platforms = list(platforms)
        else:
            selected_platforms = self._parser.parse_platforms(
                raw_platforms,
                platforms,
            )

        if not selected_platforms:
            return []

        total = len(items)
        raw_items = self._parser.prompt(
            f"Select items to push (ranges ok: 1,3,5-10,{total}): ",
        )
        if not raw_items or raw_items.lower() == "all":
            selected_items = list(items)
        else:
            indices = self._parser.parse_ranges(raw_items, total)
            selected_items = [index_map[i] for i in indices]

        return [(item, platform) for item in selected_items for platform in selected_platforms]

    _CONFLICT_ACTION_MAP: dict[str, str] = {
        "p": "pull",
        "pull": "pull",
        "u": "push",
        "push": "push",
        "s": "skip",
        "skip": "skip",
    }

    def resolve_sync_conflicts(
        self,
        conflicts: list[tuple[str, str, str]],
    ) -> dict[str, str]:
        """Let user resolve sync conflicts one by one.

        Args:
            conflicts: List of (item_name, item_type, platform) tuples.

        Returns:
            Dict mapping ``"item_name/platform"`` to ``"pull" | "push" | "skip"``.

        """
        if not conflicts:
            return {}

        print()
        print(self._renderer._c("Resolve sync conflicts:", Colors.BOLD))
        print()

        result: dict[str, str] = {}
        apply_to_all: str | None = None

        for item_name, item_type, platform in conflicts:
            conflict_key = f"{item_name}/{platform}"

            if apply_to_all is not None:
                result[conflict_key] = apply_to_all
                continue

            print(
                f"  "
                f"{self._renderer._c('CONFLICT', Colors.RED)}: "
                f"{item_type}/{item_name} on {platform}"
            )
            print("  Both repo and local have changes.")
            print("  [p] Pull (take repo version)")
            print("  [u] Push (take local version)")
            print("  [s] Skip")
            print("  [a] Apply to all remaining")

            raw = self._parser.prompt("  Choice [s]: ")
            key = raw.strip().lower() if raw else "s"

            if key in ("a", "all"):
                raw_all = self._parser.prompt(
                    "  Apply which to all? [p]ull/[u]push/[s]kip: ",
                )
                all_key = raw_all.strip().lower() if raw_all else "s"
                apply_to_all = self._CONFLICT_ACTION_MAP.get(all_key, "skip")
                result[conflict_key] = apply_to_all
            else:
                result[conflict_key] = self._CONFLICT_ACTION_MAP.get(key, "skip")

            print()

        return result


# ---------------------------------------------------------------------------
# InteractiveRunner — main interactive loop
# ---------------------------------------------------------------------------


class InteractiveRunner:
    """Orchestrates the main interactive menu loop.

    Displays a welcome banner, status summary, and main menu; dispatches
    the chosen command through a callback; then loops until the user
    quits.

    This class has a narrow public interface — only :meth:`run`.
    Internally it delegates to :class:`InteractiveSession` but uses
    only the ``welcome()`` and ``main_menu()`` navigation methods,
    keeping its dependency surface small.

    Args:
        command_dispatch: Callable that takes a menu choice string
            (e.g. ``"pull"``, ``"status"``) and executes the
            corresponding command.
        status_provider: Optional callable that returns a dict mapping
            platform display names to installed item counts.
        use_colors: When ``None`` (default), colour output is
            automatically enabled based on terminal capabilities.
            Pass ``True`` or ``False`` to override.

    """

    def __init__(
        self,
        *,
        command_dispatch: Callable[[str], None],
        status_provider: Callable[[], dict[str, int]] | None = None,
        use_colors: bool | None = None,
    ) -> None:
        """Initialise the interactive TUI shell."""
        if use_colors is None:
            use_colors = should_use_colors()
        self._session = InteractiveSession(use_colors)
        self._command_dispatch = command_dispatch
        self._status_provider = status_provider

    def run(self) -> None:
        """Run the interactive loop until the user quits.

        Handles ``KeyboardInterrupt`` (Ctrl+C) at the loop level for
        a clean exit.  Also handles ``EOFError`` when stdin is
        exhausted (e.g. piped input) by breaking out of the loop.
        """
        try:
            while True:
                self._session.welcome()
                self._show_status()

                choice = self._session.main_menu()
                if choice == "quit":
                    info("Goodbye!")
                    break

                try:
                    self._command_dispatch(choice)
                except Exception as exc:
                    error(f"Command failed: {exc}")
                    logger.debug("Interactive command error", exc_info=True)

                print()
                try:
                    input("Press Enter to continue...")
                except (EOFError, KeyboardInterrupt):
                    info("Goodbye!")
                    break
        except KeyboardInterrupt:
            print()
            info("Goodbye!")

    def _show_status(self) -> None:
        """Display a quick status summary if a provider is available."""
        if self._status_provider is None:
            return

        try:
            summary = self._status_provider()
            for name, count in summary.items():
                print(f"  {name}: {count} items installed")
            if summary:
                print()
        except Exception:
            logger.debug("Failed to display status", exc_info=True)
