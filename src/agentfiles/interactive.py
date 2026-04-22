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
            if start > end:
                start, end = end, start
            result.update(range(start, end + 1))
        else:
            try:
                result.add(int(token))
            except ValueError:
                continue

    return sorted(i for i in result if 1 <= i <= max_value)


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
            "Manage AI tool configurations for OpenCode",
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

    def show_item_types(self, types: list[ItemType]) -> None:
        """Display a numbered list of item types."""
        lines = [f"\n{self._c('Item types:', Colors.BOLD)}"]
        lines.extend(f"  {idx}) {t.plural.title()}" for idx, t in enumerate(types, start=1))
        sys.stdout.write("\n".join(lines) + "\n")

    def show_items_grouped(
        self,
        items: list[Item],
        source_dir: Path | None = None,
    ) -> dict[int, Item]:
        """Display items grouped by type with continuous numbering.

        When *source_dir* is provided, each item is compared against the
        source repository and annotated with a push-status marker:

        - ``+`` (green) — new (not in repo)
        - ``~`` (yellow) — changed (differs from repo)
        - ``·`` (dim) — unchanged (already in repo)

        Args:
            items: Items to display.
            source_dir: Optional source-repository root for push-status
                comparison.

        Returns:
            Mapping of 1-based index to :class:`Item}.

        """
        by_type: dict[ItemType, list[Item]] = defaultdict(list)
        for item in items:
            by_type[item.item_type].append(item)

        # Pre-compute push statuses when source_dir is given.
        push_statuses: dict[int, str] = {}
        if source_dir is not None:
            from agentfiles.engine import _compare_push_item
            from agentfiles.paths import get_push_dest_path

            for idx, item in enumerate(items):
                dest = get_push_dest_path(source_dir, item)
                push_statuses[idx] = _compare_push_item(item.source_path, dest)

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
                src = item.source_path
                # Show parent directory for concise output
                location = src.parent if src.is_absolute() and src.parent != src else src
                # Show token count for agents and skills (fast, size-based estimate)
                token_str = ""
                if item.item_type in (ItemType.AGENT, ItemType.SKILL):
                    from agentfiles.tokens import count_item_tokens

                    tokens = count_item_tokens(item.source_path)
                    token_str = f"  ~{tokens:,} tokens"
                # Push-status marker
                status_marker = ""
                item_idx = next((i for i, it in enumerate(items) if it is item), None)
                if item_idx is not None and item_idx in push_statuses:
                    status = push_statuses[item_idx]
                    if status == "new":
                        status_marker = " " + self._c("+", Colors.GREEN)
                    elif status == "changed":
                        status_marker = " " + self._c("~", Colors.YELLOW)
                    else:  # unchanged
                        status_marker = " " + self._c("·", Colors.DIM)
                buf.append(
                    f"    [{counter}]{status_marker} {item.name}{token_str}"
                    f"  {self._c(str(location), Colors.DIM)}"
                )
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

        The summary groups items by action type.
        """
        by_action: dict[SyncAction, list[SyncPlan]] = defaultdict(list)

        for plan in plans:
            by_action[plan.action].append(plan)

        buf: list[str] = ["", self._c("Load plan:", Colors.BOLD)]

        for action in SyncAction:
            action_plans = by_action.get(action, [])
            if not action_plans:
                continue
            symbol, colour = _ACTION_SYMBOLS[action]
            label = self._c(f"{symbol} {action.value.title()}", colour)
            buf.append(f"  {label}: {len(action_plans)} items")

        buf.append("")

        for action in SyncAction:
            action_plans = by_action.get(action, [])
            if not action_plans:
                continue
            symbol, colour = _ACTION_SYMBOLS[action]
            header = self._c(f"  {symbol} {action.value.title()}:", colour)
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

        Returns:
            The stripped user input, or an empty string on empty input.

        Raises:
            KeyboardInterrupt: When the user presses Ctrl+C, so callers
            can distinguish cancellation from an empty response.
        """
        try:
            return input(self._renderer._c(message, Colors.BOLD)).strip()
        except EOFError:
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

        choose_sync_mode()      → str              # cmd_pull
        select_platforms(...)   → list[Platform]   # cmd_pull (no-op)
        select_item_types()     → list[ItemType]   # cmd_pull
        select_items(...)       → list[Item]       # cmd_pull, cmd_push

    **Confirmation prompts** — used by most commands that modify state::

        confirm_action(...)              → bool  # internal base method
        confirm_plans(...)               → bool  # internal base method
        confirm_action_or_abort(...)     → bool  # cmd_clean, cmd_init
        confirm_plans_or_abort(...)      → bool  # cmd_pull

    **Navigation** — used by :class:`InteractiveRunner` only::

        welcome()       → None   # banner display
        main_menu()     → str    # menu choice dispatch

    **Conflict resolution** — used by push workflows::

        prompt_push_conflicts(...)       → dict[str, str]

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

        Raises:
            KeyboardInterrupt: When the user presses Ctrl+C.

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
        """Return all available platforms unchanged.

        Since only OpenCode is supported, platform selection is a no-op.
        """
        return list(available)

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

    def select_items(
        self,
        items: list[Item],
        source_dir: Path | None = None,
    ) -> list[Item]:
        """Let the user pick items from a grouped, numbered list.

        Items are grouped by :class:`ItemType` with continuous numbering
        across groups.  Supports ranges like ``1,3,5-10,21-30`` and the
        keyword ``all``.

        When *source_dir* is provided, each item is annotated with a
        push-status marker (new / changed / unchanged).

        Args:
            items: Items to choose from.
            source_dir: Optional source-repository root for push-status
                comparison.

        Returns:
            List of selected :class:`Item} instances.

        """
        if not items:
            return []

        index_map = self._renderer.show_items_grouped(items, source_dir=source_dir)
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

        The summary groups items by action type.

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

    # -- public API: conflict resolution (push) ---------------------------

    _PUSH_CONFLICT_MAP: dict[str, str] = {
        "t": "keep-target",
        "keep-target": "keep-target",
        "s": "keep-source",
        "keep-source": "keep-source",
        "d": "show-diff",
        "show-diff": "show-diff",
    }

    def prompt_push_conflicts(
        self,
        conflicts: list[tuple[str, str, Path, Path]],
    ) -> dict[str, str]:
        """Let the user resolve push conflicts interactively.

        For each conflict the user can choose:

        - **keep-target** (``t``) — overwrite source with the target version
          (default push behaviour).
        - **keep-source** (``s``) — skip this item, keep source as-is.
        - **show-diff** (``d``) — display a unified diff, then re-prompt.

        Args:
            conflicts: List of ``(item_key, item_type,
                source_path, target_path)`` tuples.

        Returns:
            Mapping of item_key to ``"keep-target"`` or ``"keep-source"``.
        """
        if not conflicts:
            return {}

        print()
        print(self._renderer._c("Push conflicts detected:", Colors.BOLD))
        print("  Both the source repo and local install have changed since last sync.")
        print()

        result: dict[str, str] = {}
        apply_to_all: str | None = None

        for item_key, _item_type, source_path, target_path in conflicts:
            if apply_to_all is not None:
                result[item_key] = apply_to_all
                continue

            resolved = False
            while not resolved:
                print(f"  {self._renderer._c('CONFLICT', Colors.RED)}: {item_key}")
                print("  [t] Keep target (overwrite source — push)")
                print("  [s] Keep source (skip this item)")
                print("  [d] Show diff")
                print("  [a] Apply choice to all remaining")

                raw = self._parser.prompt("  Choice [s]: ")
                key = raw.strip().lower() if raw else "s"

                if key in ("a", "all"):
                    raw_all = self._parser.prompt(
                        "  Apply which to all? [t]arget/[s]ource: ",
                    )
                    all_key = raw_all.strip().lower() if raw_all else "s"
                    if all_key in ("t", "keep-target"):
                        apply_to_all = "keep-target"
                    else:
                        apply_to_all = "keep-source"
                    result[item_key] = apply_to_all
                    resolved = True
                elif key in ("d", "show-diff"):
                    self._show_push_conflict_diff(source_path, target_path)
                else:
                    action = self._PUSH_CONFLICT_MAP.get(key, "keep-source")
                    result[item_key] = action
                    resolved = True

                print()

        return result

    def _show_push_conflict_diff(
        self,
        source_path: Path,
        target_path: Path,
    ) -> None:
        """Display a unified diff between source and target versions."""
        import difflib

        try:
            if source_path.is_file():
                src_lines = source_path.read_text(encoding="utf-8").splitlines(keepends=True)
            else:
                src_lines = ["(directory — diff not available)\n"]
            if target_path.is_file():
                tgt_lines = target_path.read_text(encoding="utf-8").splitlines(keepends=True)
            else:
                tgt_lines = ["(directory — diff not available)\n"]
        except (OSError, UnicodeDecodeError):
            print("  (cannot read files for diff)")
            return

        diff = list(
            difflib.unified_diff(
                src_lines,
                tgt_lines,
                fromfile=f"source: {source_path}",
                tofile=f"target: {target_path}",
                n=3,
            )
        )

        if not diff:
            print("  (no textual differences)")
            return

        for line in diff:
            line = line.rstrip("\n")
            if line.startswith("+"):
                print(f"  {self._renderer._c(line, Colors.GREEN)}")
            elif line.startswith("-"):
                print(f"  {self._renderer._c(line, Colors.RED)}")
            else:
                print(f"  {line}")


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
