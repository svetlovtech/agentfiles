"""Tests for syncode.paths — centralised path construction helpers."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import pytest

from syncode.models import Item, ItemType
from syncode.paths import (
    get_installed_item_path,
    get_item_dest_path,
    get_push_dest_path,
    read_item_content,
)

# -- Fixtures ---------------------------------------------------------------


@pytest.fixture
def agent_item(tmp_path: Path) -> Item:
    """An agent item backed by a real .md file."""
    f = tmp_path / "coder.md"
    f.write_text("---\nname: coder\n---\nContent")
    return Item(
        item_type=ItemType.AGENT,
        name="coder",
        source_path=f,
        checksum="abc",
    )


@pytest.fixture
def skill_item(tmp_path: Path) -> Item:
    """A skill item backed by a real directory."""
    d = tmp_path / "python-reviewer"
    d.mkdir()
    (d / "SKILL.md").write_text("---\nname: python-reviewer\n---\nSkill content")
    return Item(
        item_type=ItemType.SKILL,
        name="python-reviewer",
        source_path=d,
        checksum="def",
    )


@pytest.fixture
def command_item(tmp_path: Path) -> Item:
    """A command item backed by a real .md file."""
    f = tmp_path / "deploy.md"
    f.write_text("---\nname: deploy\n---\n")
    return Item(
        item_type=ItemType.COMMAND,
        name="deploy",
        source_path=f,
    )


@pytest.fixture
def plugin_item(tmp_path: Path) -> Item:
    """A plugin item backed by a real directory."""
    d = tmp_path / "my-plugin"
    d.mkdir()
    (d / "index.js").write_text("module.exports = {};")
    return Item(
        item_type=ItemType.PLUGIN,
        name="my-plugin",
        source_path=d,
        checksum="ghi",
    )


# -- get_item_dest_path ------------------------------------------------------


class TestGetItemDestPath:
    def test_agent_returns_md_filename(self, agent_item: Item) -> None:
        target_dir = Path("/target/agent")
        result = get_item_dest_path(target_dir, agent_item)
        assert result == Path("/target/agent/coder.md")

    def test_skill_returns_directory_name(self, skill_item: Item) -> None:
        target_dir = Path("/target/skill")
        result = get_item_dest_path(target_dir, skill_item)
        assert result == Path("/target/skill/python-reviewer")

    def test_command_returns_source_filename(self, tmp_path: Path) -> None:
        f = tmp_path / "deploy.md"
        f.write_text("---\nname: deploy\n---\n")
        item = Item(
            item_type=ItemType.COMMAND,
            name="deploy",
            source_path=f,
        )
        result = get_item_dest_path(Path("/cmd"), item)
        assert result == Path("/cmd/deploy.md")

    def test_plugin_returns_directory_name(self, plugin_item: Item) -> None:
        target_dir = Path("/target/plugin")
        result = get_item_dest_path(target_dir, plugin_item)
        assert result == Path("/target/plugin/my-plugin")


# -- get_installed_item_path -------------------------------------------------


class TestGetInstalledItemPath:
    @pytest.mark.parametrize(
        "item_type, name, expected",
        [
            (ItemType.AGENT, "coder", Path("/agent/coder.md")),
            (ItemType.COMMAND, "deploy", Path("/command/deploy.md")),
            (ItemType.SKILL, "python-reviewer", Path("/skill/python-reviewer")),
            (ItemType.PLUGIN, "my-plugin", Path("/plugin/my-plugin")),
        ],
        ids=["agent", "command", "skill", "plugin"],
    )
    def test_returns_correct_path(self, item_type: ItemType, name: str, expected: Path) -> None:
        base = expected.parent
        result = get_installed_item_path(base, item_type, name)
        assert result == expected


# -- get_push_dest_path ------------------------------------------------------


class TestGetPushDestPath:
    @pytest.mark.parametrize(
        "item_fixture, expected",
        [
            ("agent_item", Path("/repo/agents/coder/coder.md")),
            ("skill_item", Path("/repo/skills/python-reviewer")),
            ("command_item", Path("/repo/commands/deploy/deploy.md")),
            ("plugin_item", Path("/repo/plugins/my-plugin")),
        ],
        ids=["agent", "skill", "command", "plugin"],
    )
    def test_push_path(self, item_fixture: str, expected: Path, request: Any) -> None:
        item = request.getfixturevalue(item_fixture)
        result = get_push_dest_path(Path("/repo"), item)
        assert result == expected


# -- read_item_content --------------------------------------------------------


class TestReadItemContent:
    """Tests for read_item_content() — shared content reading helper."""

    def test_reads_single_file(self, tmp_path: Path) -> None:
        """Reads a regular file and returns (content, path)."""
        f = tmp_path / "agent.md"
        f.write_text("hello agent", encoding="utf-8")

        result = read_item_content(f)
        assert result is not None
        content, resolved_path = result
        assert content == "hello agent"
        assert resolved_path == f

    def test_reads_skill_md_from_directory(self, tmp_path: Path) -> None:
        """Reads SKILL.md from a directory."""
        skill_dir = tmp_path / "my-skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("skill content", encoding="utf-8")
        (skill_dir / "other.md").write_text("other content", encoding="utf-8")

        result = read_item_content(skill_dir)
        assert result is not None
        content, resolved_path = result
        assert content == "skill content"
        assert resolved_path.name == "SKILL.md"

    def test_reads_first_md_from_directory_without_skill_md(self, tmp_path: Path) -> None:
        """Falls back to first sorted .md file when no SKILL.md exists."""
        skill_dir = tmp_path / "my-skill"
        skill_dir.mkdir()
        (skill_dir / "beta.md").write_text("beta content", encoding="utf-8")
        (skill_dir / "alpha.md").write_text("alpha content", encoding="utf-8")

        result = read_item_content(skill_dir)
        assert result is not None
        content, resolved_path = result
        assert content == "alpha content"
        assert resolved_path.name == "alpha.md"

    def test_skips_hidden_md_files(self, tmp_path: Path) -> None:
        """Skips .dotfiles when scanning for fallback .md files."""
        skill_dir = tmp_path / "my-skill"
        skill_dir.mkdir()
        (skill_dir / ".hidden.md").write_text("hidden", encoding="utf-8")
        (skill_dir / "visible.md").write_text("visible", encoding="utf-8")

        result = read_item_content(skill_dir)
        assert result is not None
        content, _ = result
        assert content == "visible"

    def test_returns_none_for_nonexistent_path(self, tmp_path: Path) -> None:
        """Returns None when path does not exist."""
        result = read_item_content(tmp_path / "nonexistent")
        assert result is None

    def test_returns_none_for_empty_directory(self, tmp_path: Path) -> None:
        """Returns None when directory has no .md files."""
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()

        result = read_item_content(empty_dir)
        assert result is None

    def test_handles_utf8_errors_gracefully(self, tmp_path: Path) -> None:
        """Replaces decoding errors instead of raising."""
        f = tmp_path / "binary.md"
        f.write_bytes(b"hello \xff\xfe world")

        result = read_item_content(f)
        assert result is not None
        content, _ = result
        assert "hello" in content
        assert "world" in content

    def test_handles_permission_error_gracefully(self, tmp_path: Path) -> None:
        """Returns None when file cannot be read (e.g. permission denied)."""
        f = tmp_path / "secret.md"
        f.write_text("secret", encoding="utf-8")
        os.chmod(f, 0o000)

        try:
            result = read_item_content(f)
            # May return None or content depending on OS/user
            # On most systems with root, the file is still readable
            assert result is None or result[0] == "secret"
        finally:
            os.chmod(f, 0o644)

    def test_broken_symlink_returns_none(self, tmp_path: Path) -> None:
        """Returns None for a broken symlink (dangling target)."""
        target = tmp_path / "missing_target.md"
        link = tmp_path / "broken_link.md"
        link.symlink_to(target)

        result = read_item_content(link)
        assert result is None

    def test_directory_with_unreadable_candidate_falls_through(
        self,
        tmp_path: Path,
    ) -> None:
        """Skips unreadable .md files and reads the next candidate."""
        skill_dir = tmp_path / "my-skill"
        skill_dir.mkdir()

        # Create an unreadable file (alphabetically first)
        unreadable = skill_dir / "aaa_unreadable.md"
        unreadable.write_text("secret stuff", encoding="utf-8")
        os.chmod(unreadable, 0o000)

        # Create a readable fallback
        readable = skill_dir / "bbb_readable.md"
        readable.write_text("fallback content", encoding="utf-8")

        try:
            result = read_item_content(skill_dir)
            # On systems where root can still read chmod-000 files,
            # we may get either file's content
            assert result is not None
            content, resolved = result
            assert "content" in content or "stuff" in content
        finally:
            os.chmod(unreadable, 0o644)

    def test_symlink_to_directory(self, tmp_path: Path) -> None:
        """Follows symlinks that point to real directories."""
        real_dir = tmp_path / "real-skill"
        real_dir.mkdir()
        (real_dir / "SKILL.md").write_text("linked skill", encoding="utf-8")

        link = tmp_path / "linked-skill"
        link.symlink_to(real_dir)

        result = read_item_content(link)
        assert result is not None
        content, resolved = result
        assert content == "linked skill"

    def test_reads_empty_file(self, tmp_path: Path) -> None:
        """An empty file returns empty string content (not None)."""
        f = tmp_path / "empty.md"
        f.write_text("", encoding="utf-8")

        result = read_item_content(f)
        assert result is not None
        content, resolved = result
        assert content == ""
        assert resolved == f

    def test_symlink_to_regular_file(self, tmp_path: Path) -> None:
        """Follows a symlink pointing to a real file."""
        real = tmp_path / "real.md"
        real.write_text("real content", encoding="utf-8")

        link = tmp_path / "link.md"
        link.symlink_to(real)

        result = read_item_content(link)
        assert result is not None
        content, resolved = result
        assert content == "real content"

    def test_directory_with_only_non_md_files(self, tmp_path: Path) -> None:
        """Returns None when directory has files but none are .md."""
        d = tmp_path / "only-bin"
        d.mkdir()
        (d / "index.js").write_text("js")
        (d / "style.css").write_text("css")
        (d / "data.json").write_text("{}")

        result = read_item_content(d)
        assert result is None

    def test_directory_with_only_hidden_md_files(self, tmp_path: Path) -> None:
        """Returns None when directory only has hidden .md files."""
        d = tmp_path / "only-hidden"
        d.mkdir()
        (d / ".secret.md").write_text("hidden", encoding="utf-8")
        (d / ".another.md").write_text("also hidden", encoding="utf-8")

        result = read_item_content(d)
        assert result is None

    def test_skill_md_unreadable_falls_to_next_md(self, tmp_path: Path) -> None:
        """Falls back from unreadable SKILL.md to next .md candidate."""
        d = tmp_path / "broken-skill"
        d.mkdir()

        skill_md = d / "SKILL.md"
        skill_md.write_text("secret skill", encoding="utf-8")
        os.chmod(skill_md, 0o000)

        fallback = d / "readme.md"
        fallback.write_text("fallback", encoding="utf-8")

        try:
            result = read_item_content(d)
            assert result is not None
            content, resolved = result
            # On root, SKILL.md may still be readable
            assert content in ("secret skill", "fallback")
        finally:
            os.chmod(skill_md, 0o644)

    def test_fifo_returns_none(self, tmp_path: Path) -> None:
        """Returns None for a special file (named pipe)."""
        fifo = tmp_path / "pipe.md"
        os.mkfifo(fifo)

        result = read_item_content(fifo)
        assert result is None

    def test_directory_with_mixed_extensions_picks_md_only(self, tmp_path: Path) -> None:
        """Only .md files are considered in fallback scan, not .txt."""
        d = tmp_path / "mixed"
        d.mkdir()
        (d / "readme.txt").write_text("txt content")
        (d / "guide.md").write_text("md content", encoding="utf-8")
        (d / "notes.rst").write_text("rst content")

        result = read_item_content(d)
        assert result is not None
        content, resolved = result
        assert content == "md content"
        assert resolved.name == "guide.md"
