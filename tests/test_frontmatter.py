"""Tests for agentfiles.frontmatter — edge cases not covered by test_models.py.

test_models.py already covers parse_frontmatter, _quote_colon_values,
_meta_from_frontmatter, and _validate_field_type basics. This file focuses
on edge cases: _is_quoted, unicode, delimiter oddities, retry paths.
"""

from __future__ import annotations

import pytest

from agentfiles.frontmatter import (
    _is_quoted,
    _quote_colon_values,
)
from agentfiles.models import (
    AgentfilesError,
    ItemMeta,
    _meta_from_frontmatter,
    parse_frontmatter,
)

# ---------------------------------------------------------------------------
# _is_quoted
# ---------------------------------------------------------------------------


class TestIsQuoted:
    def test_double_quoted(self) -> None:
        assert _is_quoted('"hello"') is True

    def test_single_quoted(self) -> None:
        assert _is_quoted("'hello'") is True

    def test_not_quoted(self) -> None:
        assert _is_quoted("hello") is False

    def test_empty_string(self) -> None:
        assert _is_quoted("") is False

    def test_single_char(self) -> None:
        assert _is_quoted('"') is False

    def test_mismatched_quotes(self) -> None:
        assert _is_quoted("\"hello'") is False

    def test_minimal_quoted(self) -> None:
        assert _is_quoted('""') is True

    def test_inner_quotes(self) -> None:
        assert _is_quoted('"it\'s a test"') is True


# ---------------------------------------------------------------------------
# _quote_colon_values — edge cases
# ---------------------------------------------------------------------------


class TestQuoteColonValuesEdgeCases:
    def test_nested_mapping_line_untouched(self) -> None:
        """Lines that don't match key: value pattern are passed through."""
        inp = "  nested_key: nested_value"
        assert _quote_colon_values(inp) == inp

    def test_hyphenated_key(self) -> None:
        inp = "my-key: value: with: colons"
        assert _quote_colon_values(inp) == 'my-key: "value: with: colons"'

    def test_underscored_key(self) -> None:
        inp = "my_key: A: B"
        assert _quote_colon_values(inp) == 'my_key: "A: B"'

    def test_value_with_hash(self) -> None:
        """Hash in value — not a colon, so not quoted."""
        inp = "name: test # comment"
        assert _quote_colon_values(inp) == inp

    def test_multiline_preserves_order(self) -> None:
        inp = "a: x: y\nb: plain\nc: p: q"
        result = _quote_colon_values(inp)
        lines = result.split("\n")
        assert lines[0] == 'a: "x: y"'
        assert lines[1] == "b: plain"
        assert lines[2] == 'c: "p: q"'

    def test_empty_input(self) -> None:
        assert _quote_colon_values("") == ""


# ---------------------------------------------------------------------------
# parse_frontmatter — edge cases
# ---------------------------------------------------------------------------


class TestParseFrontmatterEdgeCases:
    def test_unicode_content(self) -> None:
        content = "---\nname: агент-тест\ndescription: Описание\n---\n# Тело"
        result = parse_frontmatter(content)
        assert result["name"] == "агент-тест"
        assert result["description"] == "Описание"

    def test_triple_dash_in_body_ignored(self) -> None:
        content = "---\nname: test\n---\n# Body\n---\nMore text"
        result = parse_frontmatter(content)
        assert result == {"name": "test"}

    def test_leading_whitespace_before_delimiter(self) -> None:
        content = "  ---\nname: test\n---"
        # strip() removes leading whitespace, so frontmatter IS detected
        assert parse_frontmatter(content) == {"name": "test"}

    def test_version_as_float_in_yaml(self) -> None:
        """YAML parses 1.0 as float, not string."""
        content = "---\nname: test\nversion: 1.0\n---"
        result = parse_frontmatter(content)
        # version is parsed as float by YAML
        assert result["version"] == 1.0

    def test_retry_fixes_multiple_colons(self) -> None:
        content = "---\ntitle: Part 1: Section A: Overview\n---"
        result = parse_frontmatter(content)
        assert result["title"] == "Part 1: Section A: Overview"

    def test_tools_as_yaml_mapping(self) -> None:
        content = "---\nname: x\ntools:\n  bash: true\n  edit: false\n---"
        result = parse_frontmatter(content)
        assert result["tools"] == {"bash": True, "edit": False}

    def test_only_delimiters(self) -> None:
        """Two delimiters with nothing between."""
        content = "---\n---"
        assert parse_frontmatter(content) == {}

    def test_scalar_yaml(self) -> None:
        """Scalar (not mapping) raises."""
        content = "---\njust a string\n---"
        with pytest.raises(AgentfilesError, match="must be a YAML mapping"):
            parse_frontmatter(content)

    def test_integer_yaml(self) -> None:
        content = "---\n42\n---"
        with pytest.raises(AgentfilesError, match="must be a YAML mapping"):
            parse_frontmatter(content)


# ---------------------------------------------------------------------------
# _meta_from_frontmatter — edge cases
# ---------------------------------------------------------------------------


class TestMetaFromFrontmatterEdgeCases:
    def test_empty_dict(self) -> None:
        meta = _meta_from_frontmatter({})
        assert meta.name == ""
        assert meta.description == ""
        assert meta.tools == {}
        assert meta.extra == {}

    def test_priority_numeric_coerced_to_str(self) -> None:
        """priority=1 fails validation (not str), confirming type check."""
        with pytest.raises(AgentfilesError, match="priority"):
            _meta_from_frontmatter({"priority": 1})

    def test_tools_empty_dict(self) -> None:
        meta = _meta_from_frontmatter({"tools": {}})
        assert meta.tools == {}

    def test_extra_preserves_complex_values(self) -> None:
        raw = {"name": "x", "custom": {"nested": [1, 2, 3]}}
        meta = _meta_from_frontmatter(raw)
        assert meta.extra["custom"] == {"nested": [1, 2, 3]}

    def test_returns_item_meta(self) -> None:
        meta = _meta_from_frontmatter({"name": "x"})
        assert isinstance(meta, ItemMeta)
