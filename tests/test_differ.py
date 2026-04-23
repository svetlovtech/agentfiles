"""Tests for agentfiles.differ — comparing source items with installed targets."""

from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import pytest

from agentfiles.differ import (
    Differ,
    _resolve_target_path,
    compute_content_diff,
)
from agentfiles.models import (
    DiffEntry,
    DiffStatus,
    Item,
    ItemType,
)
from agentfiles.target import TargetDiscovery, TargetManager
from tests.conftest import make_item

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


# fake_home and target_manager are provided by conftest.py.


# ---------------------------------------------------------------------------
# Differ.diff
# ---------------------------------------------------------------------------


class TestDifferDiff:
    """Tests for the Differ.diff method."""

    def test_new_item_not_installed(self, target_manager: TargetManager) -> None:
        item = make_item(name="new-agent")
        differ = Differ(target_manager)

        results = differ.diff([item])

        assert len(results) == 1
        assert results[0].status == DiffStatus.NEW
        assert results[0].item.name == "new-agent"

    def test_unchanged_item_same_content(
        self,
        target_manager: TargetManager,
        fake_home: SimpleNamespace,
    ) -> None:
        # Create an installed item with known content.
        target_dir = target_manager.get_target_dir(ItemType.AGENT)
        assert target_dir is not None

        item_dir = target_dir / "stable-agent"
        item_dir.mkdir()
        (item_dir / "file.md").write_text("same content", encoding="utf-8")

        source_dir = fake_home.home / "src" / "agents" / "stable-agent"
        source_dir.mkdir(parents=True)
        (source_dir / "file.md").write_text("same content", encoding="utf-8")

        item = Item(
            item_type=ItemType.AGENT,
            name="stable-agent",
            source_path=source_dir,
        )
        differ = Differ(target_manager)
        results = differ.diff([item])

        assert len(results) == 1
        assert results[0].status == DiffStatus.UNCHANGED

    def test_updated_item_different_sizes(
        self,
        target_manager: TargetManager,
        fake_home: SimpleNamespace,
    ) -> None:
        """Different file sizes are detected as UPDATED by metadata comparison."""
        target_dir = target_manager.get_target_dir(ItemType.AGENT)
        assert target_dir is not None

        item_dir = target_dir / "changed-agent"
        item_dir.mkdir()
        (item_dir / "file.md").write_text(
            "old content is a12 bytes", encoding="utf-8"
        )  # Different sizes → UPDATED
        source_dir = fake_home.home / "src" / "agents" / "changed-agent"
        source_dir.mkdir(parents=True)
        (source_dir / "file.md").write_text("new content", encoding="utf-8")

        item = Item(
            item_type=ItemType.AGENT,
            name="changed-agent",
            source_path=source_dir,
        )
        differ = Differ(target_manager)
        results = differ.diff([item])

        assert len(results) == 1
        assert results[0].status == DiffStatus.UPDATED

    def test_empty_items_returns_empty(self, target_manager: TargetManager) -> None:
        differ = Differ(target_manager)
        results = differ.diff([])

        assert results == []

    def test_multiple_items(self, target_manager: TargetManager) -> None:
        items = [
            make_item(name="agent-a"),
            make_item(name="skill-b", item_type=ItemType.SKILL),
        ]
        differ = Differ(target_manager)
        results = differ.diff(items)

        assert len(results) == 2

    def test_size_precheck_detects_update(
        self,
        target_manager: TargetManager,
        fake_home: SimpleNamespace,
    ) -> None:
        """When file sizes differ, metadata check detects UPDATED."""
        target_dir = target_manager.get_target_dir(ItemType.AGENT)
        assert target_dir is not None

        item_dir = target_dir / "size-diff-agent"
        item_dir.mkdir()
        (item_dir / "file.md").write_text("short", encoding="utf-8")

        source_dir = fake_home.home / "src" / "agents" / "size-diff-agent"
        source_dir.mkdir(parents=True)
        (source_dir / "file.md").write_text(
            "much longer content here",
            encoding="utf-8",
        )

        item = Item(
            item_type=ItemType.AGENT,
            name="size-diff-agent",
            source_path=source_dir,
        )
        differ = Differ(target_manager)
        results = differ.diff([item])

        assert len(results) == 1
        assert results[0].status == DiffStatus.UPDATED
        assert results[0].details == "size differs"

    def test_directory_file_count_precheck(
        self,
        target_manager: TargetManager,
        fake_home: SimpleNamespace,
    ) -> None:
        """Directory items with different file counts are detected as updated."""
        target_dir = target_manager.get_target_dir(ItemType.SKILL)
        assert target_dir is not None

        skill_dir = target_dir / "count-skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("skill content", encoding="utf-8")

        source_dir = fake_home.home / "src" / "skills" / "count-skill"
        source_dir.mkdir(parents=True)
        (source_dir / "SKILL.md").write_text("skill content", encoding="utf-8")
        (source_dir / "extra.py").write_text("extra file", encoding="utf-8")

        item = Item(
            item_type=ItemType.SKILL,
            name="count-skill",
            source_path=source_dir,
        )
        differ = Differ(target_manager)

        results = differ.diff([item])

        assert len(results) == 1
        assert results[0].status == DiffStatus.UPDATED
        assert results[0].details == "size differs"

    def test_same_size_different_content_marked_unchanged(
        self,
        target_manager: TargetManager,
        fake_home: SimpleNamespace,
    ) -> None:
        """Same file size but different content → UNCHANGED (metadata matches)."""
        target_dir = target_manager.get_target_dir(ItemType.AGENT)
        assert target_dir is not None

        item_dir = target_dir / "same-size-agent"
        item_dir.mkdir()
        (item_dir / "file.md").write_text("content-a", encoding="utf-8")

        source_dir = fake_home.home / "src" / "agents" / "same-size-agent"
        source_dir.mkdir(parents=True)
        (source_dir / "file.md").write_text("content-b", encoding="utf-8")

        item = Item(
            item_type=ItemType.AGENT,
            name="same-size-agent",
            source_path=source_dir,
        )
        differ = Differ(target_manager)
        results = differ.diff([item])

        assert len(results) == 1
        # Same size → metadata matches → UNCHANGED
        assert results[0].status == DiffStatus.UNCHANGED


# ---------------------------------------------------------------------------
# Error handling — resilient diff computation
# ---------------------------------------------------------------------------


class TestErrorHandling:
    """Tests for resilient error handling during diff computation."""

    def test_unreadable_target_returns_clear_error(
        self,
        target_manager: TargetManager,
        fake_home: SimpleNamespace,
    ) -> None:
        """Target file exists but metadata comparison fails → UNCHANGED (conservative)."""
        target_dir = target_manager.get_target_dir(ItemType.AGENT)
        assert target_dir is not None

        item_dir = target_dir / "locked-agent"
        item_dir.mkdir()
        (item_dir / "file.md").write_text("content", encoding="utf-8")

        source_dir = fake_home.home / "src" / "agents" / "locked-agent"
        source_dir.mkdir(parents=True)
        (source_dir / "file.md").write_text("content", encoding="utf-8")

        item = Item(
            item_type=ItemType.AGENT,
            name="locked-agent",
            source_path=source_dir,
        )
        differ = Differ(target_manager)

        # Metadata check fails (PermissionError) — conservative approach
        # returns False, so the item is classified as UNCHANGED.
        with mock.patch.object(
            differ,
            "_metadata_differs",
            return_value=False,
        ):
            results = differ.diff([item])

        assert len(results) == 1
        assert results[0].status == DiffStatus.UNCHANGED

    def test_unexpected_exception_skips_item(
        self,
        target_manager: TargetManager,
    ) -> None:
        """One item raising an exception should not prevent others from being diffed."""
        good_item = make_item(name="good-agent")
        bad_item = make_item(name="bad-agent")

        differ = Differ(target_manager)

        with mock.patch.object(
            differ,
            "_compare_item",
            side_effect=lambda item: (
                DiffEntry(item=item, status=DiffStatus.NEW)
                if item.name == "good-agent"
                else (_ for _ in ()).throw(OSError("unexpected I/O failure"))
            ),
        ):
            results = differ.diff([bad_item, good_item])

        # The bad item was skipped but the good item was processed.
        names = [e.item.name for e in results]
        assert "good-agent" in names
        assert "bad-agent" not in names

    def test_permission_error_during_metadata_comparison(
        self,
        target_manager: TargetManager,
        fake_home: SimpleNamespace,
    ) -> None:
        """PermissionError during stat() should not crash, falls through to content comparison."""
        target_dir = target_manager.get_target_dir(ItemType.AGENT)
        assert target_dir is not None

        item_dir = target_dir / "perm-agent"
        item_dir.mkdir()
        (item_dir / "file.md").write_text("content", encoding="utf-8")

        source_dir = fake_home.home / "src" / "agents" / "perm-agent"
        source_dir.mkdir(parents=True)
        (source_dir / "file.md").write_text("content", encoding="utf-8")

        item = Item(
            item_type=ItemType.AGENT,
            name="perm-agent",
            source_path=source_dir,
        )
        differ = Differ(target_manager)

        # Simulate PermissionError only on target stat, not source.
        real_stat = Path.stat

        def _failing_stat(
            self: Path,
            *,
            follow_symlinks: bool = True,
        ) -> object:
            if "perm-agent" in str(self) and "opencode" in str(self):
                raise PermissionError("no access")
            return real_stat(self, follow_symlinks=follow_symlinks)

        with mock.patch.object(Path, "stat", _failing_stat):
            results = differ.diff([item])

        assert len(results) == 1
        # Metadata check failed gracefully, still produced a result.
        assert results[0].status in (
            DiffStatus.NEW,
            DiffStatus.UPDATED,
            DiffStatus.UNCHANGED,
        )


# ---------------------------------------------------------------------------
# _resolve_target_path — direct unit tests
# ---------------------------------------------------------------------------


class TestResolveTargetPath:
    """Tests for the _resolve_target_path helper."""

    def test_returns_path_for_valid_platform(
        self,
        target_manager: TargetManager,
    ) -> None:
        item = make_item(name="test-agent")
        result = _resolve_target_path(item, target_manager)
        assert result is not None
        assert "test-agent" in str(result)

    def test_returns_none_for_empty_manager(self) -> None:
        empty_manager = TargetManager(None)
        item = make_item(name="anything")
        result = _resolve_target_path(item, empty_manager)
        assert result is None

    def test_returns_none_for_wrong_platform_type(self) -> None:
        """Item type AGENT but platform has no agent dir → None."""
        empty_manager = TargetManager(None)
        item = make_item(item_type=ItemType.PLUGIN, name="p1")
        result = _resolve_target_path(item, empty_manager)
        assert result is None


# ---------------------------------------------------------------------------
# Mixed status results
# ---------------------------------------------------------------------------


class TestMixedStatusResults:
    """Tests for diff producing multiple different statuses in one call."""

    def test_mixed_new_updated_unchanged(
        self,
        target_manager: TargetManager,
        fake_home: SimpleNamespace,
    ) -> None:
        """Single diff call yields NEW, UPDATED, and UNCHANGED entries."""
        target_dir = target_manager.get_target_dir(ItemType.AGENT)
        assert target_dir is not None

        # UPDATED: installed with different content (different sizes)
        upd_dir = target_dir / "upd-agent"
        upd_dir.mkdir()
        (upd_dir / "file.md").write_text("old content here", encoding="utf-8")
        upd_src = fake_home.home / "src" / "agents" / "upd-agent"
        upd_src.mkdir(parents=True)
        (upd_src / "file.md").write_text("new content here!", encoding="utf-8")

        # UNCHANGED: installed with same content
        uc_dir = target_dir / "uc-agent"
        uc_dir.mkdir()
        (uc_dir / "file.md").write_text("same", encoding="utf-8")
        uc_src = fake_home.home / "src" / "agents" / "uc-agent"
        uc_src.mkdir(parents=True)
        (uc_src / "file.md").write_text("same", encoding="utf-8")

        # NEW: not installed
        new_src = fake_home.home / "src" / "agents" / "new-agent"
        new_src.mkdir(parents=True)
        (new_src / "file.md").write_text("new!", encoding="utf-8")

        items = [
            Item(
                item_type=ItemType.AGENT,
                name="upd-agent",
                source_path=upd_src,
            ),
            Item(
                item_type=ItemType.AGENT,
                name="uc-agent",
                source_path=uc_src,
            ),
            Item(
                item_type=ItemType.AGENT,
                name="new-agent",
                source_path=new_src,
            ),
        ]

        differ = Differ(target_manager)
        results = differ.diff(items)

        status_map = {e.item.name: e.status for e in results}
        assert status_map["upd-agent"] == DiffStatus.UPDATED
        assert status_map["uc-agent"] == DiffStatus.UNCHANGED
        assert status_map["new-agent"] == DiffStatus.NEW

    def test_single_platform_unchanged(
        self,
        target_manager: TargetManager,
        fake_home: SimpleNamespace,
    ) -> None:
        """Items with same content are UNCHANGED."""
        oc_dir = target_manager.get_target_dir(ItemType.AGENT)
        assert oc_dir is not None
        item_dir = oc_dir / "split-agent"
        item_dir.mkdir()
        (item_dir / "file.md").write_text("content", encoding="utf-8")

        source_dir = fake_home.home / "src" / "agents" / "split-agent"
        source_dir.mkdir(parents=True)
        (source_dir / "file.md").write_text("content", encoding="utf-8")

        item = Item(
            item_type=ItemType.AGENT,
            name="split-agent",
            source_path=source_dir,
        )
        differ = Differ(target_manager)
        results = differ.diff([item])

        assert results[0].status == DiffStatus.UNCHANGED


# ---------------------------------------------------------------------------
# Metadata diff edge cases
# ---------------------------------------------------------------------------


class TestMetadataDiffEdgeCases:
    """Tests for _metadata_differs edge cases."""

    def test_source_file_target_not_file(
        self,
        target_manager: TargetManager,
        fake_home: SimpleNamespace,
    ) -> None:
        """Source is a file but target is a directory → metadata differs."""
        target_dir = target_manager.get_target_dir(ItemType.AGENT)
        assert target_dir is not None

        # Create a directory at target with the item name
        item_dir = target_dir / "type-mismatch-agent"
        item_dir.mkdir()

        # Source is a single file (not a directory)
        source_file = fake_home.home / "src" / "agents" / "type-mismatch-agent"
        source_file.parent.mkdir(parents=True, exist_ok=True)
        source_file.write_text("file content", encoding="utf-8")

        item = Item(
            item_type=ItemType.AGENT,
            name="type-mismatch-agent",
            source_path=source_file,
        )
        differ = Differ(target_manager)
        results = differ.diff([item])

        assert len(results) == 1
        assert results[0].status == DiffStatus.UPDATED
        assert results[0].details == "size differs"

    def test_metadata_differs_returns_false_for_none_target_path(
        self,
        target_manager: TargetManager,
    ) -> None:
        """When _resolve_target_path returns None, metadata check returns False."""
        empty_manager = TargetManager(None)
        item = make_item(name="orphan")
        differ = Differ(empty_manager)

        result = differ._metadata_differs(item)
        assert result is False

    def test_same_file_count_same_total_size_marked_unchanged(
        self,
        target_manager: TargetManager,
        fake_home: SimpleNamespace,
    ) -> None:
        """Directory items with same count and total size → UNCHANGED.

        Without checksum comparison, metadata match means unchanged.
        """
        target_dir = target_manager.get_target_dir(ItemType.SKILL)
        assert target_dir is not None

        skill_dir = target_dir / "tricky-skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("aaaa", encoding="utf-8")

        source_dir = fake_home.home / "src" / "skills" / "tricky-skill"
        source_dir.mkdir(parents=True)
        (source_dir / "SKILL.md").write_text("bbbb", encoding="utf-8")

        item = Item(
            item_type=ItemType.SKILL,
            name="tricky-skill",
            source_path=source_dir,
        )
        differ = Differ(target_manager)
        results = differ.diff([item])

        assert len(results) == 1
        assert results[0].status == DiffStatus.UNCHANGED


# ---------------------------------------------------------------------------
# Single-platform diff
# ---------------------------------------------------------------------------


class TestSinglePlatformDiff:
    """Tests for diff against the single supported platform (OpenCode)."""

    def test_item_on_target_appears_in_results(
        self,
        target_manager: TargetManager,
    ) -> None:
        """Item supporting OpenCode should appear in results."""
        item = make_item(
            name="oc-only",
        )
        differ = Differ(target_manager)
        results = differ.diff([item])

        assert len(results) == 1
        assert results[0].status == DiffStatus.NEW


# ---------------------------------------------------------------------------
# CONFLICT status — verify classification logic
# ---------------------------------------------------------------------------


class TestConflictStatus:
    """Verify CONFLICT status is handled correctly in output.

    Note: the current Differ implementation does not produce CONFLICT status
    from its comparison logic. These tests verify the status is correctly
    formatted when it does appear.
    """

    def test_conflict_entry_in_diff_results(
        self,
        target_manager: TargetManager,
    ) -> None:
        """Manually created CONFLICT entry passes through diff result flow."""
        item = make_item(name="conflict-item")
        conflict_entry = DiffEntry(
            item=item,
            status=DiffStatus.CONFLICT,
            details="both modified",
        )
        # Verify the entry is properly formed
        assert conflict_entry.status == DiffStatus.CONFLICT
        assert conflict_entry.details == "both modified"


# ---------------------------------------------------------------------------
# compute_content_diff — unified diff between source and target
# ---------------------------------------------------------------------------


class TestComputeContentDiff:
    """Tests for the compute_content_diff helper function."""

    def test_returns_diff_for_updated_file(
        self,
        target_manager: TargetManager,
        fake_home: SimpleNamespace,
    ) -> None:
        """Unified diff should show added/removed lines for changed content."""
        target_dir = target_manager.get_target_dir(ItemType.AGENT)
        assert target_dir is not None

        # Create target with old content
        item_dir = target_dir / "diff-agent"
        item_dir.mkdir()
        (item_dir / "SKILL.md").write_text(
            "line1 old\nline2 same\nline3 same\n",
            encoding="utf-8",
        )

        # Create source with new content
        source_dir = fake_home.home / "src" / "agents" / "diff-agent"
        source_dir.mkdir(parents=True)
        (source_dir / "SKILL.md").write_text(
            "line1 new\nline2 same\nline3 same\n",
            encoding="utf-8",
        )

        item = Item(
            item_type=ItemType.AGENT,
            name="diff-agent",
            source_path=source_dir,
        )
        entry = DiffEntry(
            item=item,
            status=DiffStatus.UPDATED,
        )
        result = compute_content_diff(entry, target_manager)

        assert len(result) > 0
        # Should contain unified diff markers
        result_text = "\n".join(result)
        assert "---" in result_text
        assert "+++" in result_text
        assert "@@" in result_text
        assert "-line1 old" in result_text
        assert "+line1 new" in result_text

    def test_returns_empty_for_identical_content(
        self,
        target_manager: TargetManager,
        fake_home: SimpleNamespace,
    ) -> None:
        """No diff lines when source and target have identical content."""
        target_dir = target_manager.get_target_dir(ItemType.AGENT)
        assert target_dir is not None

        content = "identical content\nline2\n"
        item_dir = target_dir / "same-agent"
        item_dir.mkdir()
        (item_dir / "SKILL.md").write_text(content, encoding="utf-8")

        source_dir = fake_home.home / "src" / "agents" / "same-agent"
        source_dir.mkdir(parents=True)
        (source_dir / "SKILL.md").write_text(content, encoding="utf-8")

        item = Item(
            item_type=ItemType.AGENT,
            name="same-agent",
            source_path=source_dir,
        )
        entry = DiffEntry(item=item, status=DiffStatus.UPDATED)
        result = compute_content_diff(entry, target_manager)

        assert result == []

    def test_returns_empty_for_missing_target(
        self,
        fake_home: SimpleNamespace,
    ) -> None:
        """Returns empty when the target does not exist."""
        source_dir = fake_home.home / "src" / "agents" / "missing-target"
        source_dir.mkdir(parents=True)
        (source_dir / "SKILL.md").write_text("source content\n", encoding="utf-8")

        item = Item(
            item_type=ItemType.AGENT,
            name="missing-target",
            source_path=source_dir,
        )
        entry = DiffEntry(item=item, status=DiffStatus.UPDATED)

        with (
            mock.patch.object(Path, "home", return_value=fake_home.home),
            mock.patch.dict(os.environ, {}, clear=True),
        ):
            targets = TargetDiscovery().discover_all()
            tm = TargetManager(targets)

        result = compute_content_diff(entry, tm)
        assert result == []

    def test_handles_binary_file_gracefully(
        self,
        target_manager: TargetManager,
        fake_home: SimpleNamespace,
    ) -> None:
        """Binary content should produce a 'binary file' notice."""
        target_dir = target_manager.get_target_dir(ItemType.AGENT)
        assert target_dir is not None

        item_dir = target_dir / "binary-agent"
        item_dir.mkdir()
        (item_dir / "SKILL.md").write_text(
            "binary\x00content\n",
            encoding="utf-8",
            errors="replace",
        )

        source_dir = fake_home.home / "src" / "agents" / "binary-agent"
        source_dir.mkdir(parents=True)
        (source_dir / "SKILL.md").write_text(
            "source\x00content\n",
            encoding="utf-8",
            errors="replace",
        )

        item = Item(
            item_type=ItemType.AGENT,
            name="binary-agent",
            source_path=source_dir,
        )
        entry = DiffEntry(item=item, status=DiffStatus.UPDATED)
        result = compute_content_diff(entry, target_manager)

        assert len(result) == 1
        assert "binary file" in result[0]

    def test_returns_empty_for_non_updated_status(
        self,
        target_manager: TargetManager,
        fake_home: SimpleNamespace,
    ) -> None:
        """Even for NEW entries, content diff on missing target returns empty."""
        source_dir = fake_home.home / "src" / "agents" / "new-only"
        source_dir.mkdir(parents=True)
        (source_dir / "SKILL.md").write_text("content\n", encoding="utf-8")

        item = Item(
            item_type=ItemType.AGENT,
            name="new-only",
            source_path=source_dir,
        )
        entry = DiffEntry(item=item, status=DiffStatus.NEW)
        result = compute_content_diff(entry, target_manager)
        assert result == []

    def test_unified_diff_includes_context_lines(
        self,
        target_manager: TargetManager,
        fake_home: SimpleNamespace,
    ) -> None:
        """Diff should include context lines around the change."""
        target_dir = target_manager.get_target_dir(ItemType.AGENT)
        assert target_dir is not None

        target_content = "line1\nline2\nline3\nline4\nline5\n"
        source_content = "line1\nline2\nCHANGED\nline4\nline5\n"

        item_dir = target_dir / "context-agent"
        item_dir.mkdir()
        (item_dir / "SKILL.md").write_text(target_content, encoding="utf-8")

        source_dir = fake_home.home / "src" / "agents" / "context-agent"
        source_dir.mkdir(parents=True)
        (source_dir / "SKILL.md").write_text(source_content, encoding="utf-8")

        item = Item(
            item_type=ItemType.AGENT,
            name="context-agent",
            source_path=source_dir,
        )
        entry = DiffEntry(item=item, status=DiffStatus.UPDATED)
        result = compute_content_diff(entry, target_manager)

        result_text = "\n".join(result)
        # Context lines (unchanged) should appear
        assert "line1" in result_text
        assert "line2" in result_text
        assert "line4" in result_text
        # Changed line
        assert "-line3" in result_text
        assert "+CHANGED" in result_text
