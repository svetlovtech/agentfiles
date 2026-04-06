"""YAML frontmatter parsing utilities for markdown-based configuration files.

This module handles extraction, validation, and processing of YAML
frontmatter blocks embedded in ``.md`` files.  Frontmatter is the
convention of embedding structured metadata at the top of a markdown
file between ``---`` delimiters::

    ---
    name: my-agent
    description: An AI agent
    version: "1.0.0"
    priority: critical
    tools:
      bash: true
      edit: false
    ---

    # Agent instructions follow…

The parsing pipeline:

1. :func:`parse_frontmatter` extracts the raw YAML block and parses it
   into a ``dict`` with an automatic retry mechanism that quotes bare
   colons in values.
2. :func:`_meta_from_frontmatter` converts the raw dict into a
   structured :class:`~agentfiles.models.ItemMeta` instance, validating
   field types and collecting unknown keys into an ``extra`` dict.

Both functions are re-exported from :mod:`agentfiles.models` for backward
compatibility.
"""

from __future__ import annotations

import re
from typing import Any

# Lazy import from models to avoid circular dependency at module load time.
# models.py imports from this module after defining SyncodeError, ItemMeta,
# and _DEFAULT_VERSION, so the circular import resolves correctly.
from agentfiles.models import _DEFAULT_VERSION, ItemMeta, SyncodeError

# ---------------------------------------------------------------------------
# Shared constants
# ---------------------------------------------------------------------------

SKILL_MAIN_FILE: str = "SKILL.md"
"""Canonical filename for the main markdown file in a skill directory."""

# ---------------------------------------------------------------------------
# Module-private constants
# ---------------------------------------------------------------------------

_FRONTMATTER_DELIMITER = "---"
"""Delimiter that marks the start and end of a YAML frontmatter block."""

_KNOWN_FRONTMATTER_KEYS = frozenset(
    {"name", "description", "version", "priority", "tools"},
)
"""Recognised frontmatter keys.  Unknown keys are collected into ``extra``."""

_SCALAR_FIELD_TYPES: dict[str, type | tuple[type, ...]] = {
    "name": str,
    "description": str,
    "version": str,
    "priority": str,
    "tools": dict,
}
"""Expected Python types for each known frontmatter field."""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def parse_frontmatter(content: str) -> dict[str, Any]:
    """Parse YAML frontmatter from markdown content.

    Expects the content to start with ``---`` on its own line, followed by
    a YAML block, terminated by another ``---`` line.

    **Retry mechanism**:  If the initial ``yaml.safe_load`` fails, the
    function retries once after auto-quoting values that contain bare
    colons via :func:`_quote_colon_values`.  This handles the common
    mistake of writing ``name: Architecture: Design Patterns`` without
    quotes around the value.

    The frontmatter parsing pipeline:

    1. Locate the YAML block between the opening and closing ``---``.
    2. Attempt ``yaml.safe_load`` on the raw block.
    3. On failure, re-quote colon-containing values and retry.
    4. Validate that the result is a YAML mapping (dict).
    5. Return the dict (or raise :class:`SyncodeError`).

    Args:
        content: Raw markdown file contents.

    Returns:
        Parsed YAML as a dictionary.  Returns an empty dict when no
        frontmatter is found or the YAML block is empty.

    Raises:
        SyncodeError: When the YAML block is present but cannot be parsed,
            or when the parsed result is not a mapping.

    """
    if not content:
        return {}

    stripped = content.strip()
    if not stripped:
        return {}

    if not stripped.startswith(_FRONTMATTER_DELIMITER):
        return {}

    # Split on the first two ``---`` occurrences.
    # parts layout: [before-first---, YAML-block, after-second---]
    parts = stripped.split(_FRONTMATTER_DELIMITER, 2)
    if len(parts) < 3:
        return {}

    yaml_block = parts[1].strip()
    if not yaml_block:
        return {}

    import yaml

    try:
        parsed = yaml.safe_load(yaml_block)
    except yaml.YAMLError:
        # Retry with quoted values for lines where an unquoted colon
        # appears inside the value (e.g. ``name: Architecture: Design Patterns``).
        yaml_block = _quote_colon_values(yaml_block)
        try:
            parsed = yaml.safe_load(yaml_block)
        except yaml.YAMLError as exc:
            raise SyncodeError(
                f"malformed YAML frontmatter: {exc}. "
                f"Fix: check for unquoted special characters, "
                f"indentation errors, or missing quotes around values "
                f"that contain ':', '#', or other YAML syntax."
            ) from exc

    if not isinstance(parsed, dict):
        raise SyncodeError(
            f"frontmatter must be a YAML mapping (key: value pairs), "
            f"got {type(parsed).__name__}. "
            f"Fix: use 'key: value' syntax instead of a list or scalar."
        )

    return parsed


# ---------------------------------------------------------------------------
# Internal helpers (module-private, re-exported by models.py for tests)
# ---------------------------------------------------------------------------


def _meta_from_frontmatter(raw: dict[str, Any]) -> ItemMeta:
    """Build an :class:`ItemMeta` from a parsed frontmatter dict.

    Known keys (``name``, ``description``, ``version``, ``priority``,
    ``tools``) are extracted and type-checked via :func:`_validate_field_type`.
    Unrecognised keys are placed into the ``extra`` dict so nothing is
    silently dropped.

    Validation pipeline:

    1. Iterate over :data:`_SCALAR_FIELD_TYPES` and validate each
       present field's type (missing fields are allowed).
    2. Convert ``tools`` dict values to ``bool`` (accepts any truthy
       mapping, e.g. ``{"bash": true, "edit": false}``).
    3. Collect unknown keys into ``extra`` for forward compatibility.
    4. Coerce ``priority`` to ``str`` when present, or leave as ``None``.

    Args:
        raw: Dictionary returned by :func:`parse_frontmatter`.

    Returns:
        A fully-populated :class:`ItemMeta` instance.

    Raises:
        SyncodeError: When a known field has an unexpected type
            (e.g. ``tools`` is a string instead of a mapping).

    """
    for field_name, expected in _SCALAR_FIELD_TYPES.items():
        _validate_field_type(raw, field_name, expected)

    tools_raw: dict[str, Any] | None = raw.get("tools")
    tools: dict[str, bool] = {str(k): bool(v) for k, v in tools_raw.items()} if tools_raw else {}

    extra: dict[str, Any] = {k: v for k, v in raw.items() if k not in _KNOWN_FRONTMATTER_KEYS}

    priority_raw: str | None = raw.get("priority")
    priority: str | None = str(priority_raw) if priority_raw is not None else None

    return ItemMeta(
        name=str(raw.get("name", "")),
        description=str(raw.get("description", "")),
        version=str(raw.get("version", _DEFAULT_VERSION)),
        priority=priority,
        tools=tools,
        extra=extra,
    )


def _is_quoted(value: str) -> bool:
    """Return ``True`` when *value* is wrapped in matching quotes.

    Recognises single-quoted (``'...'``) and double-quoted (``"..."``) strings.
    Used by :func:`_quote_colon_values` to skip already-quoted values.

    Args:
        value: The string to check.

    Returns:
        Whether *value* starts and ends with the same quote character.
    """
    return len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'")


def _validate_field_type(
    raw: dict[str, Any],
    field_name: str,
    expected: type | tuple[type, ...],
) -> None:
    """Validate a frontmatter field's type, raising on mismatch.

    Checks whether *field_name* exists in *raw* and, if so, whether its
    value is an instance of *expected*.  Missing fields are allowed —
    only present-but-wrong-type values trigger an error.

    Args:
        raw: Parsed frontmatter dictionary.
        field_name: Key to validate.
        expected: Allowed Python type(s).

    Raises:
        SyncodeError: When the field is present but has the wrong type.

    """
    value = raw.get(field_name)
    if value is None:
        return

    if isinstance(value, expected):
        return

    type_label = (
        " or ".join(t.__name__ for t in expected)
        if isinstance(expected, tuple)
        else expected.__name__
    )
    raise SyncodeError(
        f"frontmatter field '{field_name}' must be {type_label}, "
        f"got {type(value).__name__}: {value!r}. "
        f"Fix: set '{field_name}' to a {type_label} value or remove it."
    )


def _quote_colon_values(yaml_block: str) -> str:
    r"""Quote YAML values that contain unquoted colons.

    Lines like ``name: Architecture: Design Patterns`` cause
    ``yaml.safe_load`` to fail because the second colon is interpreted
    as a mapping separator.  This helper wraps such values in double
    quotes so the parser treats them as plain strings.

    Only top-level scalar values are affected; block scalars (``|``),
    nested mappings, and already-quoted strings are left unchanged.

    Processing logic per line:

    1. Match lines of the form ``<key>: <value>`` where *key* is a
       word characters identifier (``\w[\w_-]*``).
    2. Skip lines whose value is a block-scalar indicator (``|``), empty,
       or already wrapped in matching quotes.
    3. If the remaining value contains a bare ``:``, wrap it in double
       quotes: ``key: "value: with: colons"``.

    Args:
        yaml_block: Raw YAML text (the content between the ``---`` delimiters).

    Returns:
        The YAML text with colon-containing values quoted.

    """
    out: list[str] = []
    for line in yaml_block.splitlines():
        m = re.match(r"^(\w[\w_-]*)\s*:\s*(.*)", line)
        if m is None:
            out.append(line)
            continue

        key = m.group(1)
        value = m.group(2)

        if value in ("|", "") or _is_quoted(value):
            out.append(line)
            continue

        if ":" in value:
            out.append(f'{key}: "{value}"')
        else:
            out.append(line)

    return "\n".join(out)
