"""Console output formatting, logging configuration, and diff display.

This module provides the presentation layer for CLI output.  It handles:

* **Logging setup** — :func:`init_logging` configures the root logger with
  colour detection, and :func:`setup_file_logging` attaches rotating file
  handlers for persistent debug logs.
* **Colour management** — :class:`Colors` defines ANSI escape sequences,
  :func:`colorize` wraps text conditionally (respecting ``NO_COLOR`` /
  ``FORCE_COLOR`` env vars), and :func:`should_use_colors` encapsulates the
  terminal-capability heuristic.
* **Convenience print helpers** — :func:`success`, :func:`error`,
  :func:`warning`, :func:`info`, :func:`bold`, :func:`dim`,
  and :func:`print_section` provide one-call coloured output routed
  through the resilient :func:`_safe_write` I/O layer.
* **Table and banner formatting** — :func:`print_table` renders aligned
  columnar output with automatic terminal-width detection and column
  truncation; :func:`print_banner` draws a Unicode box-drawing frame.
* **Diff display** — :func:`format_diff` and :func:`format_diff_json`
  convert :class:`~agentfiles.models.DiffEntry` lists into human-readable
  or machine-consumable text.
* **Text utilities** — :func:`format_item_count` produces correct
  singular/plural forms for count display.

All I/O passes through :func:`_safe_write`, which silently handles
:class:`BrokenPipeError` (piped output) and falls back to replacement
characters for unencodable glyphs.
"""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import TextIO

from agentfiles.models import DiffEntry, DiffStatus, ItemType

# ---------------------------------------------------------------------------
# ANSI colour constants
# ---------------------------------------------------------------------------


class Colors:
    """ANSI CSI (Control Sequence Introducer) escape codes for styled output.

    Foreground colours use the *bright* set (9x codes) for readability on
    both light and dark terminal backgrounds.  ``RESET`` clears all active
    attributes and must always be appended to avoid colour bleed.

    Attributes:
        GREEN: Bright green foreground (success messages).
        RED: Bright red foreground (error messages).
        YELLOW: Bright yellow foreground (warning messages).
        BLUE: Bright blue foreground (informational messages).
        BOLD: Bold (increased intensity) attribute.
        DIM: Dim / faint attribute (subdued text).
        RESET: Reset all attributes to terminal defaults.

    """

    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RESET = "\033[0m"


@dataclass(frozen=True)
class StatusStyle:
    """Canonical display metadata for a DiffStatus value.

    Attributes:
        symbol: Single-character display symbol (e.g. ``"+"``, ``"~"``).
        label: Human-readable label (e.g. ``"new"``, ``"updated"``).
        ansi_color: ANSI escape code for CLI colouring.

    """

    symbol: str
    label: str
    ansi_color: str


# Single source of truth for DiffStatus display properties.
# Symbols and labels are canonical — consumers (TUI, interactive, differ)
# import from here and only add their own colour/formatting layer.
DIFF_STATUS_STYLES: dict[DiffStatus, StatusStyle] = {
    DiffStatus.NEW: StatusStyle(symbol="+", label="new", ansi_color=Colors.GREEN),
    DiffStatus.UPDATED: StatusStyle(symbol="~", label="updated", ansi_color=Colors.YELLOW),
    DiffStatus.UNCHANGED: StatusStyle(symbol="=", label="unchanged", ansi_color=Colors.DIM),
    DiffStatus.DELETED: StatusStyle(symbol="-", label="deleted", ansi_color=Colors.RED),
    DiffStatus.CONFLICT: StatusStyle(symbol="!", label="conflict", ansi_color=Colors.RED),
}

# Human-readable detail text for each DiffStatus value.
# Used by diff formatters to show parenthetical descriptions.
DIFF_STATUS_DETAILS: dict[DiffStatus, str] = {
    DiffStatus.NEW: "new",
    DiffStatus.UPDATED: "content differs",
    DiffStatus.DELETED: "deleted from source",
    DiffStatus.UNCHANGED: "unchanged",
    DiffStatus.CONFLICT: "conflict",
}

# Sort priority for DiffStatus values in formatted output.
DIFF_STATUS_ORDER: dict[DiffStatus, int] = {
    DiffStatus.NEW: 0,
    DiffStatus.UPDATED: 1,
    DiffStatus.DELETED: 2,
    DiffStatus.UNCHANGED: 3,
    DiffStatus.CONFLICT: 4,
}

# Status values to include in summary counts (stable iteration order).
# CONFLICT is excluded because it is surfaced separately, not tallied.
_SUMMARY_STATUSES: tuple[DiffStatus, ...] = (
    DiffStatus.NEW,
    DiffStatus.UPDATED,
    DiffStatus.DELETED,
    DiffStatus.UNCHANGED,
)


# Module-level flag controlling whether ANSI colours are emitted.
# Set once by :func:`init_logging` via :func:`should_use_colors`.
_use_colors: bool = True


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------


def should_use_colors() -> bool:
    """Return ``True`` when coloured output is appropriate.

    Resolution order (first match wins):

    1. ``FORCE_COLOR`` or ``CLICOLOR_FORCE`` set → force colours **on**.
    2. ``NO_COLOR`` set → force colours **off**.
    3. ``TERM=dumb`` → colours **off**.
    4. ``stdout.isatty()`` result (``False`` when piped).
    """
    if os.environ.get("FORCE_COLOR") or os.environ.get("CLICOLOR_FORCE"):
        return True
    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("TERM") == "dumb":
        return False
    try:
        return sys.stdout.isatty()
    except OSError:
        return False


def init_logging(verbose: bool = False, quiet: bool = False) -> None:
    """Configure the root logger.

    Args:
        verbose: Set log level to DEBUG.
        quiet: Set log level to ERROR (suppresses warnings).

    """
    global _use_colors
    _use_colors = should_use_colors()

    if verbose:
        level = logging.DEBUG
    elif quiet:
        level = logging.ERROR
    else:
        level = logging.WARNING

    logging.basicConfig(
        level=level,
        format="%(levelname)s: %(message)s",
        stream=sys.stderr,
    )


# ---------------------------------------------------------------------------
# File logging
# ---------------------------------------------------------------------------

# Default directory for debug log files.
_LOG_DIR = Path("/tmp/agentfiles")

# Default formatter for file-based log output.
_FILE_LOG_FORMAT = "%(asctime)s [%(levelname)-7s] %(name)s: %(message)s"
_FILE_LOG_DATE_FORMAT = "%H:%M:%S"

# Default rotation settings.
_FILE_LOG_MAX_BYTES = 5 * 1024 * 1024  # 5 MB
_FILE_LOG_BACKUP_COUNT = 3


def setup_file_logging(
    log_dir: Path = _LOG_DIR,
    prefix: str = "app",
    module_names: tuple[str, ...] = ("agentfiles",),
    level: int = logging.DEBUG,
) -> Path:
    """Configure DEBUG-level file logging for one or more module loggers.

    Creates a :class:`~logging.handlers.RotatingFileHandler` that writes
    timestamped log files to *log_dir*.  The handler is attached to every
    logger named in *module_names* (and their children via normal
    propagation).

    Args:
        log_dir: Directory where log files are written.
        prefix: Filename prefix (e.g. ``"tui"`` → ``tui-20260401-120000.log``).
        module_names: Logger names to attach the file handler to.
        level: Log level for the file handler.

    Returns:
        The :class:`Path` of the created log file.

    """
    log_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    log_file = log_dir / f"{prefix}-{timestamp}.log"

    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=_FILE_LOG_MAX_BYTES,
        backupCount=_FILE_LOG_BACKUP_COUNT,
        encoding="utf-8",
    )
    file_handler.setLevel(level)
    file_handler.setFormatter(logging.Formatter(_FILE_LOG_FORMAT, datefmt=_FILE_LOG_DATE_FORMAT))

    for module_name in module_names:
        module_logger = logging.getLogger(module_name)
        module_logger.setLevel(logging.DEBUG)
        module_logger.addHandler(file_handler)

    return log_file


# ---------------------------------------------------------------------------
# Colour helpers
# ---------------------------------------------------------------------------


def colorize(text: str, *codes: str) -> str:
    """Wrap *text* in ANSI escape codes when colours are enabled.

    When the module-level ``_use_colors`` flag is ``False`` (set by
    :func:`init_logging`), the *text* is returned unchanged.  Otherwise the
    provided *codes* are prepended and :data:`Colors.RESET` is appended to
    prevent colour bleed into subsequent output.

    Args:
        text: The string to wrap.
        *codes: One or more ANSI escape sequences (e.g. ``Colors.GREEN``,
            ``Colors.BOLD``).  Order matters — later codes may override
            earlier ones depending on terminal capabilities.

    Returns:
        The colour-wrapped string, or *text* unchanged when colours are
        disabled.

    """
    if not _use_colors:
        return text
    return "".join((*codes, text, Colors.RESET))


# ---------------------------------------------------------------------------
# Resilient I/O helper
# ---------------------------------------------------------------------------


def _safe_write(text: str, *, stream: TextIO | None = None) -> None:
    """Write *text* to *stream* with resilient error handling.

    Gracefully handles:

    * :exc:`BrokenPipeError` — silently ignored (output piped to
      ``head`` or similar).
    * :exc:`UnicodeEncodeError` — falls back to replacement characters
      (``?``) for glyphs the stream cannot represent.

    Args:
        text: String to write.
        stream: Target stream (defaults to ``sys.stdout``).

    """
    if stream is None:
        stream = sys.stdout
    try:
        stream.write(text)
    except BrokenPipeError:
        # Consumer closed the pipe early — nothing to do.
        pass
    except UnicodeEncodeError:
        encoding = getattr(stream, "encoding", "utf-8") or "utf-8"
        try:
            safe = text.encode(encoding, errors="replace").decode(
                encoding,
                errors="replace",
            )
            stream.write(safe)
        except (BrokenPipeError, OSError):
            pass


# ---------------------------------------------------------------------------
# Convenience print helpers
# ---------------------------------------------------------------------------


def success(msg: str) -> None:
    """Print a success message (green) to *stdout*, followed by a newline.

    Colour is suppressed when :func:`should_use_colors` returns ``False``.

    Args:
        msg: The message to display.

    """
    _safe_write(colorize(msg, Colors.GREEN) + "\n")


def error(msg: str) -> None:
    """Print an error message (red) to *stderr*, followed by a newline.

    Routed to ``sys.stderr`` so that it is not captured by pipes that
    redirect stdout.

    Args:
        msg: The message to display.

    """
    _safe_write(colorize(msg, Colors.RED) + "\n", stream=sys.stderr)


def warning(msg: str) -> None:
    """Print a warning message (yellow) to *stdout*, followed by a newline.

    Args:
        msg: The message to display.

    """
    _safe_write(colorize(msg, Colors.YELLOW) + "\n")


def info(msg: str) -> None:
    """Print an informational message (blue) to *stdout*, followed by a newline.

    Args:
        msg: The message to display.

    """
    _safe_write(colorize(msg, Colors.BLUE) + "\n")


def bold(msg: str) -> None:
    """Print a bold (high-intensity) message to *stdout*, followed by a newline.

    Args:
        msg: The message to display.

    """
    _safe_write(colorize(msg, Colors.BOLD) + "\n")


def dim(msg: str) -> None:
    """Print a dimmed (faint) message to *stdout*, followed by a newline.

    Useful for supplementary or de-emphasised text such as hints and
    separators.

    Args:
        msg: The message to display.

    """
    _safe_write(colorize(msg, Colors.DIM) + "\n")


# ---------------------------------------------------------------------------
# Table formatting
# ---------------------------------------------------------------------------

# Ellipsis character appended to truncated cell values.
_TRUNCATION_ELLIPSIS = "\u2026"  # …


def _fit_cell(text: str, width: int) -> str:
    """Fit *text* into exactly *width* visible characters.

    When *text* is shorter than *width*, it is left-justified with spaces.
    When longer, it is truncated and the final character is replaced with
    :data:`_TRUNCATION_ELLIPSIS`.

    Args:
        text: Cell content.
        width: Target visible width in characters.

    Returns:
        A string of exactly *width* characters.

    """
    if len(text) <= width:
        return text.ljust(width)
    if width <= 1:
        return text[:width].ljust(width)
    return text[: width - 1] + _TRUNCATION_ELLIPSIS


def print_table(
    headers: list[str],
    rows: list[list[str]],
    *,
    max_width: int | None = None,
) -> None:
    """Print a simple aligned table to stdout.

    Columns are separated by two spaces.  Each column is left-justified
    to the width of its widest header or cell value.

    When the natural table width would exceed *max_width*, columns are
    shrunk from right to left (each retains at least one character) and
    overflowing cell values are truncated with ``…``.

    Args:
        headers: Column headings.
        rows: Table rows (each a list of string cell values).
        max_width: Maximum line width in characters.  Defaults to the
            current terminal width via :func:`shutil.get_terminal_size`.

    """
    if not rows:
        return

    if max_width is None:
        max_width = shutil.get_terminal_size().columns

    col_widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            col_widths[i] = max(col_widths[i], len(cell))

    # Enforce max_width by shrinking columns from right to left.
    sep = "  "
    sep_count = max(0, len(col_widths) - 1)
    total_sep = len(sep) * sep_count
    available = max(0, max_width - total_sep)
    total_width = sum(col_widths)

    if total_width > available and available > 0:
        overflow = total_width - available
        for i in range(len(col_widths) - 1, -1, -1):
            if overflow <= 0:
                break
            can_shrink = max(0, col_widths[i] - 1)
            shrink = min(can_shrink, overflow)
            col_widths[i] -= shrink
            overflow -= shrink

    header_line = sep.join(_fit_cell(h, w) for h, w in zip(headers, col_widths, strict=True))
    separator = sep.join("-" * w for w in col_widths)
    data_lines = (
        sep.join(_fit_cell(c, w) for c, w in zip(row, col_widths, strict=True)) for row in rows
    )

    # Single buffered write avoids repeated I/O syscalls.
    _safe_write("\n".join((header_line, separator, *data_lines)) + "\n")


# ---------------------------------------------------------------------------
# Utility formatters
# ---------------------------------------------------------------------------


def format_item_count(count: int, singular: str, plural: str | None = None) -> str:
    """Return a human-readable ``"<count> <noun>"`` string with correct plurality.

    When *count* is ``1`` the *singular* form is used; otherwise *plural* is
    used.  If *plural* is omitted it defaults to *singular* + ``"s"``.

    Examples::

        format_item_count(0, "file")       → "0 files"
        format_item_count(1, "file")       → "1 file"
        format_item_count(3, "file")       → "3 files"
        format_item_count(2, "person", "people")  → "2 people"

    Args:
        count: The numeric quantity.
        singular: Singular noun form.
        plural: Plural noun form (defaults to ``singular + "s"``).

    Returns:
        Formatted ``"<count> <noun>"`` string.

    """
    if plural is None:
        plural = singular + "s"
    return f"{count} {singular if count == 1 else plural}"


# ---------------------------------------------------------------------------
# Section headers and item status
# ---------------------------------------------------------------------------


def print_section(title: str) -> None:
    """Print a styled section header like ``── Scanning source ──``.

    The line spans up to 80 characters (or the terminal width, whichever
    is smaller), padded with ``─`` on the right.  Output is rendered in
    :data:`Colors.DIM` for visual de-emphasis.

    Args:
        title: Section title text.

    """
    width = min(shutil.get_terminal_size().columns, 80)
    box_char = "\u2500"
    content = f"\u2500\u2500 {title} "
    padding = max(0, width - len(content))
    dim(f"{content}{box_char * padding}")


# ---------------------------------------------------------------------------
# Banner / box drawing
# ---------------------------------------------------------------------------

_ANSI_RE = re.compile(r"\033\[[0-9;]*m")
"""Compiled regex to match ANSI escape sequences for visible-width calculation."""


def print_banner(lines: list[str]) -> None:
    """Print a framed banner box using Unicode box-drawing characters.

    The banner uses ``┌``/``┐`` for the top corners, ``└``/``┘`` for the
    bottom corners, ``│`` for vertical edges, and ``─`` for horizontal
    borders.  Frame lines are rendered in :data:`Colors.DIM`.

    Visible width is calculated by stripping ANSI escape codes so that
    coloured content inside the banner does not break alignment.

    Args:
        lines: Content strings to display inside the box.  Each string
            becomes one line.  May contain ANSI escape codes for colour.
            An empty list produces no output.

    """
    if not lines:
        return

    # Pre-compute visible lengths once to avoid double regex substitution.
    visible_lengths = [len(_ANSI_RE.sub("", line)) for line in lines]
    max_len = max(visible_lengths)
    border = "\u2500" * (max_len + 4)

    buf: list[str] = [colorize(f"\u250c{border}\u2510", Colors.DIM)]
    for line, raw_len in zip(lines, visible_lengths, strict=True):
        padding = " " * (max_len - raw_len)
        buf.append(
            colorize("\u2502 ", Colors.DIM) + line + padding + colorize(" \u2502", Colors.DIM)
        )
    buf.append(colorize(f"\u2514{border}\u2518", Colors.DIM))

    _safe_write("\n".join(buf) + "\n")


# ---------------------------------------------------------------------------
# Diff result formatting
# ---------------------------------------------------------------------------


def _diff_status_symbol(status: DiffStatus, *, use_colors: bool) -> str:
    """Return the single-character display symbol for *status*, optionally coloured.

    Looks up the canonical symbol from :data:`DIFF_STATUS_STYLES` and wraps
    it in the corresponding ANSI colour when *use_colors* is ``True``.

    Args:
        status: The diff status to render.
        use_colors: When ``True``, the symbol is wrapped in its associated
            ANSI colour from :data:`DIFF_STATUS_STYLES`.

    Returns:
        A one-character string (possibly colour-wrapped).

    """
    symbol = DIFF_STATUS_STYLES[status].symbol
    if not use_colors:
        return symbol
    return colorize(symbol, DIFF_STATUS_STYLES[status].ansi_color)


def format_diff(
    diff_results: list[DiffEntry],
    *,
    use_colors: bool = True,
    verbose: bool = False,
    content_diffs: dict[str, list[str]] | None = None,
) -> str:
    """Format diff results as human-readable coloured text.

    Groups entries by item type, then by status.  Shows a summary line
    followed by individual entries prefixed with status symbols.

    When *verbose* is ``True`` and *content_diffs* is provided, entries
    with ``UPDATED`` status include a unified diff showing the actual
    content changes between source and target.

    Args:
        diff_results: Flat list of diff entries.
        use_colors: Whether to include ANSI escape codes.  Automatically
            disabled when the ``NO_COLOR`` environment variable is set.
        verbose: When ``True``, include content-level unified diff for
            ``UPDATED`` entries.
        content_diffs: Mapping of ``item_key`` to a list of unified diff
            lines.  Only consulted when *verbose* is ``True``.

    Returns:
        Multi-line formatted string.

    """
    if not diff_results:
        text = "No differences found."
        return colorize(text, Colors.DIM) if use_colors else text

    # Group by item type for the summary line.
    type_groups: dict[ItemType, list[DiffEntry]] = {}
    for entry in diff_results:
        type_groups.setdefault(entry.item.item_type, []).append(entry)

    # Build summary line.
    summary_parts: list[str] = []
    for item_type in sorted(type_groups, key=lambda t: t.plural):
        group = type_groups[item_type]
        counts = Counter(e.status for e in group)
        parts: list[str] = [
            f"{counts[status]} {status.value}" for status in _SUMMARY_STATUSES if counts[status]
        ]
        if parts:
            summary_parts.append(f"{item_type.plural}: {', '.join(parts)}")

    lines: list[str] = []

    if summary_parts:
        lines.append(f"  {'; '.join(summary_parts)}")

    sorted_entries = sorted(
        diff_results,
        key=lambda e: (DIFF_STATUS_ORDER.get(e.status, 99), e.item.name),
    )

    for e in sorted_entries:
        status_line = (
            f"  {_diff_status_symbol(e.status, use_colors=use_colors)} "
            f"{e.item.name} ({DIFF_STATUS_DETAILS.get(e.status, e.status.value)})"
        )
        lines.append(status_line)

        # Append content diff for UPDATED entries when verbose mode is on.
        if verbose and e.status == DiffStatus.UPDATED and content_diffs is not None:
            diff_lines = content_diffs.get(e.item.item_key)
            if diff_lines:
                lines.extend(_format_content_diff_lines(diff_lines, use_colors))

    return "\n".join(lines)


def _format_content_diff_lines(
    diff_lines: list[str],
    use_colors: bool,
) -> list[str]:
    """Apply colours and indentation to unified diff lines.

    Each line is indented with two spaces and colour-coded:

    * Lines starting with ``---`` or ``+++`` — bold.
    * Lines starting with ``@@`` — cyan (dim when colours disabled).
    * Lines starting with ``+`` (additions) — green.
    * Lines starting with ``-`` (removals) — red.
    * All other lines (context) — dim.

    Args:
        diff_lines: Raw unified diff lines (no trailing newlines).
        use_colors: Whether to apply ANSI colour codes.

    Returns:
        List of formatted, colourised lines ready for output.

    """
    formatted: list[str] = []

    for line in diff_lines:
        if line.startswith("---") or line.startswith("+++"):
            color = Colors.BOLD
        elif line.startswith("@@"):
            color = Colors.CYAN
        elif line.startswith("+"):
            color = Colors.GREEN
        elif line.startswith("-"):
            color = Colors.RED
        else:
            color = Colors.DIM
        text = colorize(line, color) if use_colors else line
        formatted.append(f"  {text}")

    return formatted


def format_diff_json(diff_results: list[DiffEntry]) -> str:
    """Format diff results as JSON for machine consumption.

    Args:
        diff_results: Flat list of diff entries.

    Returns:
        JSON string with the structure::

            {
              "items": [
                {"name": "...", "type": "...", "status": "..."}
              ]
            }

    """
    items = [
        {
            "name": entry.item.name,
            "type": entry.item.item_type.value,
            "status": entry.status.value,
        }
        for entry in diff_results
    ]

    return json.dumps({"items": items}, indent=2)
