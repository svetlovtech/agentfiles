"""Tests for syncode.tokens — TUI-focused token counting utilities."""

from __future__ import annotations

from pathlib import Path

import pytest

from syncode.tokens import count_item_tokens, estimate_tokens_from_content, format_token_count


class TestEstimateTokensFromContent:
    """Tests for estimate_tokens_from_content function."""

    def test_empty_string_returns_zero(self) -> None:
        assert estimate_tokens_from_content("") == 0

    def test_short_string_returns_one(self) -> None:
        # "abc" -> len=3 // 4 = 0, but max(1, 0) = 1
        assert estimate_tokens_from_content("abc") == 1

    def test_exact_four_chars(self) -> None:
        assert estimate_tokens_from_content("abcd") == 1

    def test_eight_chars(self) -> None:
        assert estimate_tokens_from_content("abcdefgh") == 2

    def test_long_text(self) -> None:
        text = "a" * 400
        assert estimate_tokens_from_content(text) == 100

    def test_one_char_returns_one(self) -> None:
        # 1 // 4 = 0, but max(1, 0) = 1
        assert estimate_tokens_from_content("a") == 1

    def test_five_chars_returns_one(self) -> None:
        # 5 // 4 = 1, max(1, 1) = 1
        assert estimate_tokens_from_content("abcde") == 1

    def test_seven_chars_returns_one(self) -> None:
        # 7 // 4 = 1
        assert estimate_tokens_from_content("abcdefg") == 1

    def test_unicode_text(self) -> None:
        # len() counts characters, not bytes
        text = "héllo wörld"  # 11 chars -> 11 // 4 = 2
        assert estimate_tokens_from_content(text) == 2

    def test_emoji_text(self) -> None:
        # Emoji are single characters in len()
        text = "🎉🎉🎉🎉"  # 4 chars -> max(1, 4 // 4) = 1
        assert estimate_tokens_from_content(text) == 1

    def test_very_long_text(self) -> None:
        text = "x" * 10_000
        assert estimate_tokens_from_content(text) == 2500

    def test_returns_at_least_one_for_nonempty(self) -> None:
        # Even 1-char strings should return >= 1
        assert estimate_tokens_from_content("a") >= 1
        assert estimate_tokens_from_content("ab") >= 1
        assert estimate_tokens_from_content("abc") >= 1


class TestCountItemTokens:
    """Tests for count_item_tokens function."""

    def test_single_file(self, tmp_path: Path) -> None:
        f = tmp_path / "agent.md"
        f.write_text("a" * 40, encoding="utf-8")
        assert count_item_tokens(f) == 10

    def test_empty_file_returns_zero(self, tmp_path: Path) -> None:
        f = tmp_path / "empty.md"
        f.write_text("", encoding="utf-8")
        # Empty file -> estimate_tokens("") -> 0
        assert count_item_tokens(f) == 0

    def test_directory_with_md_files(self, tmp_path: Path) -> None:
        skill_dir = tmp_path / "my-skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("a" * 40, encoding="utf-8")  # 10 tokens
        refs = skill_dir / "refs"
        refs.mkdir()
        (refs / "guide.md").write_text("b" * 20, encoding="utf-8")  # 5 tokens
        assert count_item_tokens(skill_dir) == 15

    def test_directory_ignores_non_md_files(self, tmp_path: Path) -> None:
        d = tmp_path / "item"
        d.mkdir()
        (d / "SKILL.md").write_text("a" * 40, encoding="utf-8")  # 10 tokens
        (d / "data.json").write_text("x" * 100, encoding="utf-8")  # ignored
        assert count_item_tokens(d) == 10

    def test_nonexistent_path_returns_zero(self, tmp_path: Path) -> None:
        missing = tmp_path / "nonexistent"
        assert count_item_tokens(missing) == 0

    def test_no_read_permission_uses_size(self, tmp_path: Path) -> None:
        """Token estimation uses file size, so works without read permission."""
        f = tmp_path / "restricted.md"
        f.write_text("a" * 40, encoding="utf-8")  # 40 bytes -> 10 tokens
        f.chmod(0o000)
        try:
            assert count_item_tokens(f) == 10
        finally:
            f.chmod(0o644)

    def test_large_file(self, tmp_path: Path) -> None:
        f = tmp_path / "large.md"
        f.write_text("a" * 10_000, encoding="utf-8")
        assert count_item_tokens(f) == 2500

    def test_nested_subdirectories(self, tmp_path: Path) -> None:
        d = tmp_path / "skill"
        d.mkdir()
        (d / "SKILL.md").write_text("a" * 40, encoding="utf-8")  # 10 tokens
        refs = d / "refs"
        refs.mkdir()
        (refs / "guide.md").write_text("b" * 40, encoding="utf-8")  # 10 tokens
        deep = refs / "deep"
        deep.mkdir()
        (deep / "advanced.md").write_text("c" * 20, encoding="utf-8")  # 5 tokens
        assert count_item_tokens(d) == 25

    def test_file_at_exact_token_boundary(self, tmp_path: Path) -> None:
        f = tmp_path / "boundary.md"
        f.write_text("a" * 4000, encoding="utf-8")  # 4000 // 4 = 1000
        assert count_item_tokens(f) == 1000

    def test_file_one_byte_under_token_boundary(self, tmp_path: Path) -> None:
        f = tmp_path / "under.md"
        f.write_text("a" * 3999, encoding="utf-8")  # 3999 // 4 = 999
        assert count_item_tokens(f) == 999

    def test_empty_directory_returns_zero(self, tmp_path: Path) -> None:
        d = tmp_path / "empty_dir"
        d.mkdir()
        assert count_item_tokens(d) == 0

    def test_size_vs_content_estimation_agree_for_ascii(
        self,
        tmp_path: Path,
    ) -> None:
        """For ASCII content, size-based and content-based estimates match."""
        f = tmp_path / "agent.md"
        content = "a" * 40
        f.write_text(content, encoding="utf-8")

        from syncode.tokens import estimate_tokens_from_files

        size_based = count_item_tokens(f)
        content_based = estimate_tokens_from_files([f])
        assert size_based == content_based == 10


class TestFormatTokenCount:
    """Tests for format_token_count function."""

    @pytest.mark.parametrize(
        ("count", "expected"),
        [
            (0, "0"),
            (1, "1"),
            (500, "500"),
            (999, "999"),
            (1000, "1.0k"),
            (1234, "1.2k"),
            (56789, "56.8k"),
            (1_000_000, "1000.0k"),
        ],
        ids=[
            "zero",
            "one",
            "small",
            "just-below-1k",
            "exactly-1k",
            "with-decimal",
            "large",
            "one-million",
        ],
    )
    def test_formats_count(self, count: int, expected: str) -> None:
        assert format_token_count(count) == expected

    def test_negative_count_formatted_as_string(self) -> None:
        # Edge case: function doesn't guard against negatives
        assert format_token_count(-1) == "-1"

    def test_999_does_not_get_k_suffix(self) -> None:
        assert format_token_count(999) == "999"
        assert "k" not in format_token_count(999)

    def test_1000_gets_k_suffix(self) -> None:
        result = format_token_count(1000)
        assert result == "1.0k"
        assert result.endswith("k")
