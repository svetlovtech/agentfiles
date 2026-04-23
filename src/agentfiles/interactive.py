"""Interactive prompts for the agentfiles CLI.

Provides terminal-based selection menus, confirmation dialogs, and push
conflict resolution using only the standard library.  All prompts use raw
``input()`` calls with optional ANSI colour output.

The module is organised into focused classes that follow the
Single Responsibility Principle:

- :class:`MenuRenderer` — display formatting and visual output.
- :class:`InputParser` — user input collection and parsing.
- :class:`InteractiveSession` — thin facade that composes the two
  above and preserves the public API.

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
    Item,
    ItemType,
    SyncAction,
    SyncPlan,
)
from agentfiles.output import (
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

# Menu definitions used by InteractiveSession.
_SYNC_MODES: list[tuple[str, str]] = [
    ("install", "Install all (copy new items)"),
    ("update", "Update all (update changed items)"),
    ("full", "Full sync (install new + update changed)"),
    ("custom", "Custom (select items manually)"),
]


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------


def _parse_comma_list(input_str: str) -> list[str]:
    """Split a user string by commas or whitespace into a cleaned list.

    Empty tokens are discarded.  Returns an empty list for blank input.
    """
    # split() without args already discards empties and strips whitespace.
    return [token.lower() for token in input_str.replace(",", " ").split()]


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
        _push_status: dict[int, str] = {}
        if source_dir is not None:
            from agentfiles.engine import _compare_push_item
            from agentfiles.paths import get_push_dest_path

            for item in items:
                dest = get_push_dest_path(source_dir, item)
                _push_status[id(item)] = _compare_push_item(item.source_path, dest)

        # Deferred import — avoids circular dependency with engine module.
        from agentfiles.tokens import count_item_tokens

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
                    tokens = count_item_tokens(item.source_path)
                    token_str = f"  ~{tokens:,} tokens"
                # Push-status marker
                status_marker = ""
                status = _push_status.get(id(item))
                if status == "new":
                    status_marker = " " + self._c("+", Colors.GREEN)
                elif status == "changed":
                    status_marker = " " + self._c("~", Colors.YELLOW)
                elif status is not None:  # unchanged
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
        # _parse_ranges guarantees indices are within [1, len(types)].
        return [types[i - 1] for i in indices]

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
        select_item_types()     → list[ItemType]   # cmd_pull
        select_items(...)       → list[Item]       # cmd_pull, cmd_push

    **Confirmation prompts** — used by most commands that modify state::

        confirm_action_or_abort(...)     → bool  # cmd_clean, cmd_init
        confirm_plans_or_abort(...)      → bool  # cmd_pull

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

        return fallback  # unreachable; satisfies type checkers

    # -- public API: selection prompts -------------------------------------

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
            indices = _parse_ranges(raw_input, total)
            return [index_map[i] for i in indices]

        return self._retry_selection(
            raw=raw,
            parse_fn=_parse,
            prompt_msg=prompt_msg,
            fallback=list(items),
        )

    # -- public API: confirmation prompts ----------------------------------

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

        Convenience method that combines a yes/no prompt with
        the standard "Aborted." feedback so callers can write::

            if not session.confirm_action_or_abort("Continue?"):
                return 0

        Returns:
            ``True`` if the user confirms, ``False`` otherwise (after
            printing the abort message).

        """
        if self._parser.confirm(message, default):
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

    # -- public API: conflict resolution (push) ---------------------------

    _PUSH_CONFLICT_MAP: dict[str, str] = {
        "t": "keep-target",
        "s": "keep-source",
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
