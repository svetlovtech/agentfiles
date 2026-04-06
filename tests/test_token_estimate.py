"""Tests for token estimation — TokenEstimate, estimate_tokens_*, token_estimate."""

from __future__ import annotations

from pathlib import Path

import pytest

from agentfiles.models import (
    CHARS_PER_TOKEN,
    Item,
    ItemMeta,
    ItemType,
    TokenEstimate,
    _compute_total_size,
    _estimate_overhead_tokens,
    _resolve_item_files,
    estimate_tokens_from_content,
    estimate_tokens_from_files,
    token_estimate,
)
from agentfiles.tokens import estimate_name_description_tokens

# ---------------------------------------------------------------------------
# estimate_tokens_from_content
# ---------------------------------------------------------------------------


class TestEstimateTokensFromContent:
    """Tests for estimate_tokens_from_content function."""

    def test_empty_string_returns_zero(self) -> None:
        assert estimate_tokens_from_content("") == 0

    def test_single_char_returns_one(self) -> None:
        # max(1, 1 // 4) = 1  — consistent with tokens.estimate_tokens_from_content
        assert estimate_tokens_from_content("a") == 1

    def test_exact_multiple(self) -> None:
        content = "a" * (CHARS_PER_TOKEN * 10)
        assert estimate_tokens_from_content(content) == 10

    def test_non_exact_division_floors(self) -> None:
        # 7 // 4 = 1
        assert estimate_tokens_from_content("abcdefg") == 1

    def test_long_content(self) -> None:
        content = "Hello world " * 100  # 1200 chars
        expected = len(content) // CHARS_PER_TOKEN
        assert estimate_tokens_from_content(content) == expected

    def test_ascii_content(self) -> None:
        content = "Hello, world! This is a test."
        assert estimate_tokens_from_content(content) == len(content) // CHARS_PER_TOKEN

    def test_whitespace_only(self) -> None:
        content = "    "  # 4 spaces -> 4 // 4 = 1
        assert estimate_tokens_from_content(content) == 1

    def test_unicode_content(self) -> None:
        # len() counts characters, not bytes
        content = "héllo wörld 日本語"
        expected = len(content) // CHARS_PER_TOKEN
        assert estimate_tokens_from_content(content) == expected

    def test_emoji_content(self) -> None:
        # Emoji are single characters in len(); 3 chars -> max(1, 3 // 4) = 1
        content = "🎉🎊🎁"
        assert estimate_tokens_from_content(content) == 1

    def test_large_content(self) -> None:
        content = "a" * 100_000
        assert estimate_tokens_from_content(content) == 25_000

    def test_newlines_counted_as_chars(self) -> None:
        content = "line1\nline2\nline3\nline4\n"
        assert estimate_tokens_from_content(content) == len(content) // CHARS_PER_TOKEN

    def test_short_text_returns_one(self) -> None:
        # Consistent with tokens.estimate_tokens_from_content: returns 1 for any non-empty text
        assert estimate_tokens_from_content("a") == 1
        assert estimate_tokens_from_content("ab") == 1
        assert estimate_tokens_from_content("abc") == 1


# ---------------------------------------------------------------------------
# estimate_tokens_from_files
# ---------------------------------------------------------------------------


class TestEstimateTokensFromFiles:
    """Tests for estimate_tokens_from_files function."""

    def test_empty_list_returns_zero(self) -> None:
        assert estimate_tokens_from_files([]) == 0

    def test_single_file(self, tmp_path: Path) -> None:
        f = tmp_path / "test.md"
        content = "a" * 40  # 40 // 4 = 10 tokens
        f.write_text(content, encoding="utf-8")
        assert estimate_tokens_from_files([f]) == 10

    def test_multiple_files(self, tmp_path: Path) -> None:
        f1 = tmp_path / "a.txt"
        f2 = tmp_path / "b.txt"
        f1.write_text("a" * 20, encoding="utf-8")  # 5 tokens
        f2.write_text("b" * 12, encoding="utf-8")  # 3 tokens
        assert estimate_tokens_from_files([f1, f2]) == 8

    def test_nonexistent_file_skipped(self, tmp_path: Path) -> None:
        missing = tmp_path / "missing.txt"
        assert estimate_tokens_from_files([missing]) == 0

    def test_binary_file_skipped(self, tmp_path: Path) -> None:
        binary = tmp_path / "data.bin"
        binary.write_bytes(bytes(range(256)))
        # Should not crash; binary may decode as utf-8 with replacement
        result = estimate_tokens_from_files([binary])
        assert isinstance(result, int)

    def test_mixed_valid_and_invalid(self, tmp_path: Path) -> None:
        valid = tmp_path / "valid.md"
        valid.write_text("a" * 40, encoding="utf-8")
        missing = tmp_path / "missing.md"
        # Only the valid file should contribute
        assert estimate_tokens_from_files([valid, missing]) == 10

    def test_empty_file_returns_zero(self, tmp_path: Path) -> None:
        f = tmp_path / "empty.md"
        f.write_text("", encoding="utf-8")
        assert estimate_tokens_from_files([f]) == 0

    def test_file_with_unicode_content(self, tmp_path: Path) -> None:
        f = tmp_path / "unicode.md"
        content = "héllo wörld 日本語 テスト"
        f.write_text(content, encoding="utf-8")
        assert estimate_tokens_from_files([f]) == len(content) // CHARS_PER_TOKEN

    def test_large_file(self, tmp_path: Path) -> None:
        f = tmp_path / "large.md"
        content = "a" * 10_000
        f.write_text(content, encoding="utf-8")
        assert estimate_tokens_from_files([f]) == 2500

    def test_many_files_accumulate(self, tmp_path: Path) -> None:
        files = []
        for i in range(5):
            f = tmp_path / f"file{i}.md"
            f.write_text("a" * 40, encoding="utf-8")  # 10 tokens each
            files.append(f)
        assert estimate_tokens_from_files(files) == 50


# ---------------------------------------------------------------------------
# _resolve_item_files
# ---------------------------------------------------------------------------


class TestResolveItemFiles:
    """Tests for _resolve_item_files helper."""

    def test_file_based_item_returns_source_path(self, tmp_path: Path) -> None:
        f = tmp_path / "agent.md"
        f.write_text("content", encoding="utf-8")
        item = Item(
            item_type=ItemType.AGENT,
            name="agent",
            source_path=f,
            files=("agent.md",),
        )
        resolved = _resolve_item_files(item)
        assert resolved == [f]

    def test_directory_based_item_resolves_relative(self, tmp_path: Path) -> None:
        skill_dir = tmp_path / "my-skill"
        skill_dir.mkdir()
        skill_md = skill_dir / "SKILL.md"
        skill_md.write_text("content", encoding="utf-8")
        refs = skill_dir / "refs"
        refs.mkdir()
        ref_file = refs / "guide.md"
        ref_file.write_text("guide", encoding="utf-8")

        item = Item(
            item_type=ItemType.SKILL,
            name="my-skill",
            source_path=skill_dir,
            files=("SKILL.md", "refs/guide.md"),
        )
        resolved = _resolve_item_files(item)
        assert skill_md in resolved
        assert ref_file in resolved
        assert len(resolved) == 2

    def test_missing_files_excluded(self, tmp_path: Path) -> None:
        skill_dir = tmp_path / "skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("content", encoding="utf-8")

        item = Item(
            item_type=ItemType.SKILL,
            name="skill",
            source_path=skill_dir,
            files=("SKILL.md", "nonexistent.md"),
        )
        resolved = _resolve_item_files(item)
        assert len(resolved) == 1
        assert resolved[0].name == "SKILL.md"


# ---------------------------------------------------------------------------
# _compute_total_size
# ---------------------------------------------------------------------------


class TestComputeTotalSize:
    """Tests for _compute_total_size helper."""

    def test_empty_list(self) -> None:
        assert _compute_total_size([]) == 0

    def test_single_file(self, tmp_path: Path) -> None:
        f = tmp_path / "file.txt"
        f.write_bytes(b"hello")  # 5 bytes
        assert _compute_total_size([f]) == 5

    def test_multiple_files(self, tmp_path: Path) -> None:
        f1 = tmp_path / "a.txt"
        f2 = tmp_path / "b.txt"
        f1.write_bytes(b"abc")  # 3 bytes
        f2.write_bytes(b"defg")  # 4 bytes
        assert _compute_total_size([f1, f2]) == 7

    def test_nonexistent_file_contributes_zero(self, tmp_path: Path) -> None:
        missing = tmp_path / "missing.txt"
        assert _compute_total_size([missing]) == 0


# ---------------------------------------------------------------------------
# _estimate_overhead_tokens
# ---------------------------------------------------------------------------


class TestEstimateOverheadTokens:
    """Tests for _estimate_overhead_tokens helper."""

    def test_item_without_meta(self) -> None:
        item = Item(
            item_type=ItemType.AGENT,
            name="test-agent",
            source_path=Path("/fake"),
            files=("agent.md",),
        )
        overhead = _estimate_overhead_tokens(item)
        assert overhead > 0  # At least name + version + file name

    def test_item_with_meta(self) -> None:
        meta = ItemMeta(
            name="skill",
            description="A useful skill",
            version="2.0.0",
            priority="critical",
        )
        item = Item(
            item_type=ItemType.SKILL,
            name="skill",
            source_path=Path("/fake"),
            meta=meta,
            files=("SKILL.md", "refs/guide.md"),
        )
        overhead = _estimate_overhead_tokens(item)
        assert overhead > 0

    def test_overhead_increases_with_more_files(self) -> None:
        item_few = Item(
            item_type=ItemType.AGENT,
            name="a",
            source_path=Path("/fake"),
            files=("a.md",),
        )
        item_many = Item(
            item_type=ItemType.AGENT,
            name="a",
            source_path=Path("/fake"),
            files=("a.md", "b.md", "c.md", "d.md"),
        )
        assert _estimate_overhead_tokens(item_many) > _estimate_overhead_tokens(item_few)

    def test_overhead_with_empty_description(self) -> None:
        meta = ItemMeta(
            name="agent",
            description="",
            version="1.0.0",
        )
        item = Item(
            item_type=ItemType.AGENT,
            name="agent",
            source_path=Path("/fake"),
            meta=meta,
            files=("agent.md",),
        )
        overhead = _estimate_overhead_tokens(item)
        # Still has name + version + filename
        assert overhead > 0

    def test_overhead_with_long_description(self) -> None:
        meta_short = ItemMeta(
            name="x",
            description="short",
            version="1.0.0",
        )
        meta_long = ItemMeta(
            name="x",
            description="a" * 500,
            version="1.0.0",
        )
        item_short = Item(
            item_type=ItemType.AGENT,
            name="x",
            source_path=Path("/fake"),
            meta=meta_short,
            files=("x.md",),
        )
        item_long = Item(
            item_type=ItemType.AGENT,
            name="x",
            source_path=Path("/fake"),
            meta=meta_long,
            files=("x.md",),
        )
        assert _estimate_overhead_tokens(item_long) > _estimate_overhead_tokens(item_short)

    def test_overhead_with_priority(self) -> None:
        meta_no_priority = ItemMeta(
            name="x",
            description="desc",
            version="1.0.0",
            priority=None,
        )
        meta_with_priority = ItemMeta(
            name="x",
            description="desc",
            version="1.0.0",
            priority="critical",
        )
        item_no = Item(
            item_type=ItemType.AGENT,
            name="x",
            source_path=Path("/fake"),
            meta=meta_no_priority,
            files=("x.md",),
        )
        item_with = Item(
            item_type=ItemType.AGENT,
            name="x",
            source_path=Path("/fake"),
            meta=meta_with_priority,
            files=("x.md",),
        )
        assert _estimate_overhead_tokens(item_with) > _estimate_overhead_tokens(item_no)


# ---------------------------------------------------------------------------
# token_estimate
# ---------------------------------------------------------------------------


class TestTokenEstimate:
    """Tests for TokenEstimate dataclass."""

    def test_frozen_immutability(self) -> None:
        est = TokenEstimate(
            name="x",
            item_type=ItemType.AGENT,
            files=("x.md",),
            source_size_bytes=100,
            content_tokens=25,
            overhead_tokens=5,
            total_tokens=30,
        )
        with pytest.raises(AttributeError):
            est.name = "y"  # type: ignore[misc]

    def test_fields(self) -> None:
        est = TokenEstimate(
            name="test",
            item_type=ItemType.SKILL,
            files=("SKILL.md",),
            source_size_bytes=200,
            content_tokens=50,
            overhead_tokens=10,
            total_tokens=60,
        )
        assert est.name == "test"
        assert est.item_type == ItemType.SKILL
        assert est.files == ("SKILL.md",)
        assert est.source_size_bytes == 200
        assert est.content_tokens == 50
        assert est.overhead_tokens == 10
        assert est.total_tokens == 60

    def test_equality(self) -> None:
        a = TokenEstimate(
            name="x",
            item_type=ItemType.AGENT,
            files=(),
            source_size_bytes=0,
            content_tokens=0,
            overhead_tokens=0,
            total_tokens=0,
        )
        b = TokenEstimate(
            name="x",
            item_type=ItemType.AGENT,
            files=(),
            source_size_bytes=0,
            content_tokens=0,
            overhead_tokens=0,
            total_tokens=0,
        )
        assert a == b


class TestTokenEstimateFunction:
    """Tests for the token_estimate() function."""

    def test_agent_file(self, tmp_path: Path) -> None:
        f = tmp_path / "reviewer.md"
        content = "---\nname: reviewer\n---\n# Review\nSome body text here."
        f.write_text(content, encoding="utf-8")
        item = Item(
            item_type=ItemType.AGENT,
            name="reviewer",
            source_path=f,
            files=("reviewer.md",),
        )
        est = token_estimate(item)

        assert est.name == "reviewer"
        assert est.item_type == ItemType.AGENT
        assert est.files == ("reviewer.md",)
        assert est.source_size_bytes > 0
        assert est.content_tokens > 0
        assert est.overhead_tokens > 0
        assert est.total_tokens == est.content_tokens + est.overhead_tokens

    def test_skill_directory(self, tmp_path: Path) -> None:
        skill_dir = tmp_path / "python-stylist"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(
            "---\nname: python-stylist\nversion: 1.5.0\n---\n# Styling guide\nContent.",
            encoding="utf-8",
        )
        refs = skill_dir / "references"
        refs.mkdir()
        (refs / "patterns.md").write_text("Design patterns reference text.", encoding="utf-8")

        item = Item(
            item_type=ItemType.SKILL,
            name="python-stylist",
            source_path=skill_dir,
            version="1.5.0",
            files=("SKILL.md", "references/patterns.md"),
        )
        est = token_estimate(item)

        assert est.name == "python-stylist"
        assert est.item_type == ItemType.SKILL
        assert len(est.files) == 2
        assert est.source_size_bytes > 0
        assert est.content_tokens > 0
        assert est.overhead_tokens > 0
        assert est.total_tokens == est.content_tokens + est.overhead_tokens

    def test_item_with_meta_includes_description_overhead(self, tmp_path: Path) -> None:
        f = tmp_path / "agent.md"
        f.write_text("a" * 40, encoding="utf-8")

        meta = ItemMeta(
            name="agent",
            description="A very detailed description that adds overhead",
            version="2.0.0",
            priority="critical",
        )
        item_with_meta = Item(
            item_type=ItemType.AGENT,
            name="agent",
            source_path=f,
            meta=meta,
            files=("agent.md",),
        )
        item_without_meta = Item(
            item_type=ItemType.AGENT,
            name="agent",
            source_path=f,
            files=("agent.md",),
        )
        est_with = token_estimate(item_with_meta)
        est_without = token_estimate(item_without_meta)

        # Same content tokens but more overhead with meta
        assert est_with.content_tokens == est_without.content_tokens
        assert est_with.overhead_tokens > est_without.overhead_tokens

    def test_empty_content_item(self, tmp_path: Path) -> None:
        f = tmp_path / "empty.md"
        f.write_text("", encoding="utf-8")
        item = Item(
            item_type=ItemType.AGENT,
            name="empty",
            source_path=f,
            files=("empty.md",),
        )
        est = token_estimate(item)
        assert est.content_tokens == 0
        assert est.source_size_bytes == 0
        assert est.overhead_tokens > 0  # Still has name/version overhead
        assert est.total_tokens == est.overhead_tokens

    def test_command_item(self, tmp_path: Path) -> None:
        f = tmp_path / "build.md"
        content = "---\nname: build\n---\n# Build\nBuild command instructions."
        f.write_text(content, encoding="utf-8")
        item = Item(
            item_type=ItemType.COMMAND,
            name="build",
            source_path=f,
            files=("build.md",),
        )
        est = token_estimate(item)
        assert est.item_type == ItemType.COMMAND
        assert est.name == "build"
        assert est.content_tokens > 0
        assert est.overhead_tokens > 0
        assert est.total_tokens == est.content_tokens + est.overhead_tokens

    def test_size_matches_content_for_ascii(self, tmp_path: Path) -> None:
        """For ASCII text, byte size and char length agree."""
        from agentfiles.tokens import count_item_tokens

        f = tmp_path / "agent.md"
        content = "a" * 40
        f.write_text(content, encoding="utf-8")

        item = Item(
            item_type=ItemType.AGENT,
            name="agent",
            source_path=f,
            files=("agent.md",),
        )
        est = token_estimate(item)
        size_based = count_item_tokens(f)

        assert est.source_size_bytes == 40
        assert est.content_tokens == size_based == 10

    def test_large_skill_directory(self, tmp_path: Path) -> None:
        skill_dir = tmp_path / "big-skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("a" * 8000, encoding="utf-8")  # 2000 tokens
        refs = skill_dir / "refs"
        refs.mkdir()
        (refs / "ref1.md").write_text("b" * 4000, encoding="utf-8")  # 1000 tokens
        (refs / "ref2.md").write_text("c" * 4000, encoding="utf-8")  # 1000 tokens

        item = Item(
            item_type=ItemType.SKILL,
            name="big-skill",
            source_path=skill_dir,
            files=("SKILL.md", "refs/ref1.md", "refs/ref2.md"),
        )
        est = token_estimate(item)
        assert est.content_tokens == 4000  # 2000 + 1000 + 1000
        assert est.source_size_bytes == 16_000
        assert est.total_tokens == est.content_tokens + est.overhead_tokens


# ---------------------------------------------------------------------------
# estimate_name_description_tokens
# ---------------------------------------------------------------------------


class TestEstimateNameDescriptionTokens:
    """Tests for estimate_name_description_tokens function."""

    def test_item_without_meta(self) -> None:
        """Returns tokens for the item name only when no meta is present."""
        item = Item(
            item_type=ItemType.AGENT,
            name="coder",
            source_path=Path("/fake"),
            files=("coder.md",),
        )
        result = estimate_name_description_tokens(item)
        assert result == estimate_tokens_from_content("coder")

    def test_item_with_description(self) -> None:
        """Returns tokens for name + description combined."""
        meta = ItemMeta(name="coder", description="A helpful coding assistant")
        item = Item(
            item_type=ItemType.AGENT,
            name="coder",
            source_path=Path("/fake"),
            meta=meta,
            files=("coder.md",),
        )
        result = estimate_name_description_tokens(item)
        expected = estimate_tokens_from_content("coder A helpful coding assistant")
        assert result == expected

    def test_item_with_empty_description(self) -> None:
        """Empty description is excluded, only name is counted."""
        meta = ItemMeta(name="x", description="")
        item = Item(
            item_type=ItemType.SKILL,
            name="x",
            source_path=Path("/fake"),
            meta=meta,
            files=("x.md",),
        )
        result = estimate_name_description_tokens(item)
        assert result == estimate_tokens_from_content("x")

    def test_returns_at_least_one_for_name(self) -> None:
        """Any non-empty name yields at least 1 token."""
        item = Item(
            item_type=ItemType.AGENT,
            name="a",
            source_path=Path("/fake"),
            files=("a.md",),
        )
        assert estimate_name_description_tokens(item) >= 1

    def test_long_description_increases_count(self) -> None:
        """A longer description produces more tokens."""
        meta_short = ItemMeta(name="x", description="short")
        meta_long = ItemMeta(name="x", description="a" * 200)
        item_short = Item(
            item_type=ItemType.AGENT,
            name="x",
            source_path=Path("/fake"),
            meta=meta_short,
            files=("x.md",),
        )
        item_long = Item(
            item_type=ItemType.AGENT,
            name="x",
            source_path=Path("/fake"),
            meta=meta_long,
            files=("x.md",),
        )
        assert estimate_name_description_tokens(item_long) > estimate_name_description_tokens(
            item_short
        )
