"""Tests for agentfiles.engine — the core sync engine."""

from __future__ import annotations

import os
from collections.abc import Callable, Generator
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import pytest

from agentfiles.engine import SyncEngine, SyncReport, SyncTarget, _copy_item, _remove_item
from agentfiles.models import (
    Item,
    ItemType,
    SyncAction,
    SyncPlan,
    SyncResult,
    SyncState,
    resolve_target_name,
)
from agentfiles.target import TargetManager

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


# fake_home and target_manager are provided by conftest.py.


def _make_dir_item(
    name: str,
    item_type: ItemType = ItemType.SKILL,
    source_dir: Path | None = None,
) -> Item:
    """Create a directory-based Item for testing."""
    src = source_dir or Path(f"/src/{item_type.plural}/{name}")
    return Item(
        item_type=item_type,
        name=name,
        source_path=src,
        files=("SKILL.md",) if item_type == ItemType.SKILL else (),
    )


def _make_file_item(
    name: str,
    item_type: ItemType = ItemType.AGENT,
    source_path: Path | None = None,
) -> Item:
    """Create a file-based Item for testing."""
    src = source_path or Path(f"/src/{item_type.plural}/{name}.md")
    return Item(
        item_type=item_type,
        name=name,
        source_path=src,
        files=(f"{name}.md",),
    )


# ---------------------------------------------------------------------------
# SyncReport
# ---------------------------------------------------------------------------


class TestSyncReport:
    """Tests for the SyncReport dataclass."""

    def test_empty_report(self) -> None:
        report = SyncReport()
        assert report.success_count == 0
        assert report.failure_count == 0
        assert report.is_success is True
        assert report.summary() == "No operations performed"

    def test_all_categories(self) -> None:
        plan = SyncPlan(
            item=_make_dir_item("x"),
            action=SyncAction.INSTALL,
            target_dir=Path("/t"),
            reason="test",
        )
        report = SyncReport(
            installed=[type("R", (), {"plan": plan, "success": True})()],  # type: ignore[arg-type]
            updated=[],
            skipped=[],
            uninstalled=[],
            failed=[],
        )
        assert report.success_count == 1
        assert report.is_success is True

    def test_summary_all_fields(self) -> None:
        report = SyncReport(
            installed=[mock.Mock(files_copied=0)],
            updated=[mock.Mock(files_copied=0), mock.Mock(files_copied=0)],
            skipped=[mock.Mock()],
            uninstalled=[mock.Mock()],
            failed=[mock.Mock()],
        )
        summary = report.summary()
        assert "Installed 1" in summary
        assert "Updated 2" in summary
        assert "Skipped 1" in summary
        assert "Uninstalled 1" in summary
        assert "Failed 1" in summary

    def test_is_success_false_when_failed(self) -> None:
        report = SyncReport(failed=[mock.Mock()])
        assert report.is_success is False


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


class TestResolveDestName:
    """Tests for resolve_target_name."""

    def test_file_item_returns_filename(self) -> None:
        item = Item(
            item_type=ItemType.AGENT,
            name="python-reviewer",
            source_path=Path("/src/agents/python-reviewer.md"),
            files=("python-reviewer.md",),
        )
        assert resolve_target_name(item) == "python-reviewer.md"

    def test_dir_item_returns_directory_name(self) -> None:
        item = Item(
            item_type=ItemType.SKILL,
            name="python-stylist",
            source_path=Path("/src/skills/python-stylist"),
            files=("SKILL.md",),
        )
        assert resolve_target_name(item) == "python-stylist"


class TestCopyItem:
    """Tests for _copy_item helper."""

    def test_copy_file(self, tmp_path: Path) -> None:
        source = tmp_path / "source.txt"
        source.write_text("hello")
        dest = tmp_path / "dest.txt"

        count, error = _copy_item(source, dest, use_symlinks=False)

        assert error is None
        assert count == 1
        assert dest.read_text() == "hello"

    def test_copy_directory(self, tmp_path: Path) -> None:
        src_dir = tmp_path / "src_dir"
        src_dir.mkdir()
        (src_dir / "a.txt").write_text("a")
        (src_dir / "b.txt").write_text("b")
        (src_dir / "sub").mkdir()
        (src_dir / "sub" / "c.txt").write_text("c")

        dest = tmp_path / "dest_dir"
        count, error = _copy_item(src_dir, dest, use_symlinks=False)

        assert error is None
        assert count == 3
        assert (dest / "a.txt").read_text() == "a"
        assert (dest / "sub" / "c.txt").read_text() == "c"

    def test_symlink_file(self, tmp_path: Path) -> None:
        source = tmp_path / "source.txt"
        source.write_text("hello")
        dest = tmp_path / "link.txt"

        count, error = _copy_item(source, dest, use_symlinks=True)

        assert error is None
        assert count == 0
        assert dest.is_symlink()
        assert dest.read_text() == "hello"

    def test_symlink_directory(self, tmp_path: Path) -> None:
        src_dir = tmp_path / "src_dir"
        src_dir.mkdir()
        (src_dir / "a.txt").write_text("a")

        dest = tmp_path / "link_dir"
        count, error = _copy_item(src_dir, dest, use_symlinks=True)

        assert error is None
        assert count == 0
        assert dest.is_symlink()
        assert (dest / "a.txt").read_text() == "a"

    def test_copy_to_nonexistent_parent(self, tmp_path: Path) -> None:
        source = tmp_path / "source.txt"
        source.write_text("data")
        dest = tmp_path / "deep" / "nested" / "dest.txt"

        count, error = _copy_item(source, dest, use_symlinks=False)

        assert error is None
        assert count == 1
        assert dest.exists()

    def test_copy_missing_source_returns_error(self, tmp_path: Path) -> None:
        source = tmp_path / "nonexistent.txt"
        dest = tmp_path / "dest.txt"

        count, error = _copy_item(source, dest, use_symlinks=False)

        assert error is not None
        assert count == 0


class TestRemoveItem:
    """Tests for _remove_item helper."""

    def test_remove_file(self, tmp_path: Path) -> None:
        target = tmp_path / "file.txt"
        target.write_text("data")

        success, error = _remove_item(target)

        assert success is True
        assert error is None
        assert not target.exists()

    def test_remove_directory(self, tmp_path: Path) -> None:
        target = tmp_path / "dir"
        target.mkdir()
        (target / "inner.txt").write_text("x")

        success, error = _remove_item(target)

        assert success is True
        assert error is None
        assert not target.exists()

    def test_remove_symlink(self, tmp_path: Path) -> None:
        real = tmp_path / "real.txt"
        real.write_text("data")
        link = tmp_path / "link.txt"
        link.symlink_to(real)

        success, error = _remove_item(link)

        assert success is True
        assert error is None
        assert not link.exists()
        # Real file untouched.
        assert real.exists()

    def test_remove_missing_returns_error(self, tmp_path: Path) -> None:
        target = tmp_path / "nonexistent"

        success, error = _remove_item(target)

        assert success is False
        assert error is not None


# ---------------------------------------------------------------------------
# SyncEngine — plan_sync
# ---------------------------------------------------------------------------


class TestPlanSync:
    """Tests for SyncEngine.plan_sync."""

    def test_plan_install_new_item(self, target_manager: TargetManager) -> None:
        engine = SyncEngine(target_manager)
        item = _make_dir_item("new-skill")

        plans = engine.plan_sync(
            [item],
            action=SyncAction.INSTALL,
        )

        assert len(plans) == 1
        assert plans[0].action == SyncAction.INSTALL
        assert plans[0].reason == "not installed"

    def test_plan_skip_up_to_date(
        self, target_manager: TargetManager, fake_home: SimpleNamespace
    ) -> None:
        # Pre-install a skill directory — engine sees it as already installed.
        skill_dir = fake_home.opencode / "skill" / "existing-skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("content")

        engine = SyncEngine(target_manager)
        item = _make_dir_item(
            "existing-skill",
            source_dir=skill_dir,
        )

        plans = engine.plan_sync(
            [item],
            action=SyncAction.INSTALL,
        )

        assert len(plans) == 1
        assert plans[0].action == SyncAction.SKIP

    def test_plan_skip_when_installed_different_content(
        self, target_manager: TargetManager, fake_home: SimpleNamespace
    ) -> None:
        # Pre-install with different content — engine only checks existence.
        skill_dir = fake_home.opencode / "skill" / "changed-skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("old content")

        src_dir = fake_home.home / "src" / "skills" / "changed-skill"
        src_dir.mkdir(parents=True)
        (src_dir / "SKILL.md").write_text("new content")

        engine = SyncEngine(target_manager)
        item = _make_dir_item(
            "changed-skill",
            source_dir=src_dir,
        )

        plans = engine.plan_sync(
            [item],
            action=SyncAction.INSTALL,
        )

        # Engine only checks existence, so installed item → SKIP
        assert len(plans) == 1
        assert plans[0].action == SyncAction.SKIP

    def test_plan_uninstall_installed(
        self, target_manager: TargetManager, fake_home: SimpleNamespace
    ) -> None:
        skill_dir = fake_home.opencode / "skill" / "to-remove"
        skill_dir.mkdir()

        engine = SyncEngine(target_manager)
        item = _make_dir_item("to-remove")

        plans = engine.plan_sync(
            [item],
            action=SyncAction.UNINSTALL,
        )

        assert len(plans) == 1
        assert plans[0].action == SyncAction.UNINSTALL

    def test_plan_uninstall_not_installed_skipped(self, target_manager: TargetManager) -> None:
        engine = SyncEngine(target_manager)
        item = _make_dir_item("ghost")

        plans = engine.plan_sync(
            [item],
            action=SyncAction.UNINSTALL,
        )

        assert len(plans) == 1
        assert plans[0].action == SyncAction.SKIP

    def test_plan_creates_plan_for_valid_target_dir(self, target_manager: TargetManager) -> None:
        """Commands on OpenCode get a valid plan (command dir exists)."""
        item = _make_file_item(
            "my-cmd",
            item_type=ItemType.COMMAND,
        )
        engine = SyncEngine(target_manager)

        plans = engine.plan_sync([item])

        assert len(plans) == 1
        assert plans[0].action == SyncAction.INSTALL

    def test_plan_multiple_items(self, target_manager: TargetManager) -> None:
        items = [
            _make_dir_item("skill-a"),
            _make_dir_item("skill-b"),
            _make_file_item("agent-a"),
        ]
        engine = SyncEngine(target_manager)

        plans = engine.plan_sync(items)

        assert len(plans) == 3


# ---------------------------------------------------------------------------
# SyncEngine — execute_plan
# ---------------------------------------------------------------------------


class TestExecutePlan:
    """Tests for SyncEngine.execute_plan."""

    def test_execute_dry_run(self, target_manager: TargetManager) -> None:
        engine = SyncEngine(target_manager, dry_run=True)
        item = _make_dir_item("x")
        plan = SyncPlan(
            item=item,
            action=SyncAction.INSTALL,
            target_dir=Path("/any"),
            reason="test",
        )

        results = engine.execute_plan([plan])

        assert len(results) == 1
        assert results[0].is_success is True
        assert "dry-run" in results[0].message

    def test_execute_skip(self, target_manager: TargetManager) -> None:
        engine = SyncEngine(target_manager)
        item = _make_dir_item("x")
        plan = SyncPlan(
            item=item,
            action=SyncAction.SKIP,
            target_dir=Path("/any"),
            reason="already up-to-date",
        )

        results = engine.execute_plan([plan])

        assert len(results) == 1
        assert results[0].is_success is True

    def test_execute_install_copies_files(
        self,
        target_manager: TargetManager,
        tmp_path: Path,
    ) -> None:
        src_dir = tmp_path / "skill_src"
        src_dir.mkdir()
        (src_dir / "SKILL.md").write_text("# My Skill")

        item = Item(
            item_type=ItemType.SKILL,
            name="my-skill",
            source_path=src_dir,
            files=("SKILL.md",),
        )
        target_dir = target_manager.get_target_dir(ItemType.SKILL)
        assert target_dir is not None

        plan = SyncPlan(
            item=item,
            action=SyncAction.INSTALL,
            target_dir=target_dir,
            reason="not installed",
        )
        engine = SyncEngine(target_manager)
        results = engine.execute_plan([plan])

        assert len(results) == 1
        assert results[0].is_success is True
        assert (target_dir / "my-skill" / "SKILL.md").exists()

    def test_execute_uninstall_removes_files(
        self,
        target_manager: TargetManager,
        tmp_path: Path,
    ) -> None:
        target_dir = target_manager.get_target_dir(ItemType.SKILL)
        assert target_dir is not None
        installed = target_dir / "old-skill"
        installed.mkdir()
        (installed / "SKILL.md").write_text("old")

        item = Item(
            item_type=ItemType.SKILL,
            name="old-skill",
            source_path=tmp_path / "src",
        )
        plan = SyncPlan(
            item=item,
            action=SyncAction.UNINSTALL,
            target_dir=target_dir,
            reason="removal",
        )
        engine = SyncEngine(target_manager)
        results = engine.execute_plan([plan])

        assert len(results) == 1
        assert results[0].is_success is True
        assert not installed.exists()

    def test_execute_install_with_symlinks(
        self,
        target_manager: TargetManager,
        tmp_path: Path,
    ) -> None:
        src_dir = tmp_path / "skill_src"
        src_dir.mkdir()
        (src_dir / "SKILL.md").write_text("content")

        item = Item(
            item_type=ItemType.SKILL,
            name="symlink-skill",
            source_path=src_dir,
            files=("SKILL.md",),
        )
        target_dir = target_manager.get_target_dir(ItemType.SKILL)
        assert target_dir is not None

        plan = SyncPlan(
            item=item,
            action=SyncAction.INSTALL,
            target_dir=target_dir,
            reason="not installed",
        )
        engine = SyncEngine(target_manager, use_symlinks=True)
        results = engine.execute_plan([plan])

        assert len(results) == 1
        assert results[0].is_success is True
        dest = target_dir / "symlink-skill"
        assert dest.is_symlink()

    def test_execute_failure_does_not_abort_batch(
        self,
        target_manager: TargetManager,
        tmp_path: Path,
    ) -> None:
        good_src = tmp_path / "good"
        good_src.mkdir()
        (good_src / "SKILL.md").write_text("ok")

        bad_src = tmp_path / "bad"
        bad_src.mkdir()

        target_dir = target_manager.get_target_dir(ItemType.SKILL)
        assert target_dir is not None

        good_plan = SyncPlan(
            item=Item(
                item_type=ItemType.SKILL,
                name="good-skill",
                source_path=good_src,
                files=("SKILL.md",),
            ),
            action=SyncAction.INSTALL,
            target_dir=target_dir,
            reason="test",
        )
        bad_plan = SyncPlan(
            item=Item(
                item_type=ItemType.SKILL,
                name="bad-skill",
                source_path=bad_src,
                files=(),
            ),
            action=SyncAction.INSTALL,
            target_dir=target_dir,
            reason="test",
        )
        engine = SyncEngine(target_manager)
        results = engine.execute_plan([good_plan, bad_plan])

        assert len(results) == 2
        assert results[0].is_success is True
        # The second install might succeed (empty dir) or fail —
        # but the batch should not abort.
        assert results[1].plan.item.name == "bad-skill"


# ---------------------------------------------------------------------------
# SyncEngine — sync (convenience)
# ---------------------------------------------------------------------------


class TestSync:
    """Tests for SyncEngine.sync convenience method."""

    def test_sync_new_items(
        self,
        target_manager: TargetManager,
        tmp_path: Path,
    ) -> None:
        src_a = tmp_path / "skill_a"
        src_a.mkdir()
        (src_a / "SKILL.md").write_text("A")

        item = Item(
            item_type=ItemType.SKILL,
            name="skill-a",
            source_path=src_a,
            files=("SKILL.md",),
        )
        engine = SyncEngine(target_manager)
        report = engine.sync([item])

        assert report.is_success
        assert len(report.installed) >= 1

    def test_sync_dry_run_no_changes(
        self,
        target_manager: TargetManager,
        tmp_path: Path,
    ) -> None:
        src = tmp_path / "src"
        src.mkdir()
        (src / "SKILL.md").write_text("x")

        item = Item(
            item_type=ItemType.SKILL,
            name="dry-skill",
            source_path=src,
            files=("SKILL.md",),
        )
        engine = SyncEngine(target_manager, dry_run=True)
        report = engine.sync([item])

        assert report.is_success
        # Nothing should be physically installed.
        target_dir = target_manager.get_target_dir(ItemType.SKILL)
        assert target_dir is not None
        assert not (target_dir / "dry-skill").exists()


# ---------------------------------------------------------------------------
# SyncEngine — uninstall (convenience)
# ---------------------------------------------------------------------------


class TestUninstall:
    """Tests for SyncEngine.uninstall convenience method."""

    def test_uninstall_removes_and_reports(
        self,
        target_manager: TargetManager,
        fake_home: SimpleNamespace,
    ) -> None:
        skill_dir = fake_home.opencode / "skill" / "removable"
        skill_dir.mkdir()

        item = _make_dir_item("removable")
        engine = SyncEngine(target_manager)
        report = engine.uninstall([item])

        assert report.is_success
        assert len(report.uninstalled) >= 1
        assert not skill_dir.exists()

    def test_uninstall_nonexistent_reports_skip(
        self,
        target_manager: TargetManager,
    ) -> None:
        item = _make_dir_item("ghost")
        engine = SyncEngine(target_manager)
        report = engine.uninstall([item])

        assert report.is_success
        assert len(report.skipped) >= 1


# ---------------------------------------------------------------------------
# SyncEngine — push
# ---------------------------------------------------------------------------


class TestPush:
    """Tests for SyncEngine.push — copying from target back to source."""

    def test_push_file_item_creates_in_empty_source(
        self,
        target_manager: TargetManager,
        fake_home: SimpleNamespace,
        tmp_path: Path,
    ) -> None:
        """Push a file-based item (agent) from target into an empty source."""
        # Create an agent file on the OpenCode target.
        agent_dir = fake_home.opencode / "agent"
        agent_dir.mkdir(parents=True, exist_ok=True)
        (agent_dir / "coder.md").write_text("# Coder Agent\n")

        # Build Item as if discovered from target (source_path = on-disk path).
        item = Item(
            item_type=ItemType.AGENT,
            name="coder",
            source_path=agent_dir / "coder.md",
        )

        source_dir = tmp_path / "source"
        source_dir.mkdir()

        engine = SyncEngine(target_manager)
        report = engine.push(
            [item],
            source_dir=source_dir,
        )

        assert report.is_success
        dest = source_dir / "agents" / "coder" / "coder.md"
        assert dest.exists()
        assert dest.read_text() == "# Coder Agent\n"

    def test_push_dir_item_creates_in_empty_source(
        self,
        target_manager: TargetManager,
        fake_home: SimpleNamespace,
        tmp_path: Path,
    ) -> None:
        """Push a directory-based item (skill) from target into empty source."""
        # Create a skill directory on the OpenCode target.
        skill_dir = fake_home.opencode / "skill" / "my-skill"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text("# My Skill\n")

        item = Item(
            item_type=ItemType.SKILL,
            name="my-skill",
            source_path=skill_dir,
        )

        source_dir = tmp_path / "source"
        source_dir.mkdir()

        engine = SyncEngine(target_manager)
        report = engine.push(
            [item],
            source_dir=source_dir,
        )

        assert report.is_success
        dest = source_dir / "skills" / "my-skill"
        assert dest.is_dir()
        assert (dest / "SKILL.md").read_text() == "# My Skill\n"

    def test_push_updates_existing_source(
        self,
        target_manager: TargetManager,
        fake_home: SimpleNamespace,
        tmp_path: Path,
    ) -> None:
        """Push overwrites an existing item in source with newer content."""
        # Create agent on target.
        agent_dir = fake_home.opencode / "agent"
        agent_dir.mkdir(parents=True, exist_ok=True)
        (agent_dir / "coder.md").write_text("updated content")

        # Pre-existing agent in source (stale content).
        source_dir = tmp_path / "source"
        (source_dir / "agents" / "coder").mkdir(parents=True)
        (source_dir / "agents" / "coder" / "coder.md").write_text("old content")

        item = Item(
            item_type=ItemType.AGENT,
            name="coder",
            source_path=agent_dir / "coder.md",
        )

        engine = SyncEngine(target_manager)
        report = engine.push(
            [item],
            source_dir=source_dir,
        )

        assert report.is_success
        content = (source_dir / "agents" / "coder" / "coder.md").read_text()
        assert content == "updated content"

    def test_push_dry_run_no_changes(
        self,
        target_manager: TargetManager,
        fake_home: SimpleNamespace,
        tmp_path: Path,
    ) -> None:
        """Dry-run push does not create or modify files in source."""
        agent_dir = fake_home.opencode / "agent"
        agent_dir.mkdir(parents=True, exist_ok=True)
        (agent_dir / "coder.md").write_text("content")

        source_dir = tmp_path / "source"
        source_dir.mkdir()

        item = Item(
            item_type=ItemType.AGENT,
            name="coder",
            source_path=agent_dir / "coder.md",
        )

        engine = SyncEngine(target_manager, dry_run=True)
        report = engine.push(
            [item],
            source_dir=source_dir,
            dry_run=True,
        )

        assert report.is_success
        assert not (source_dir / "agents").exists()

    def test_push_skips_missing_target(
        self,
        target_manager: TargetManager,
        tmp_path: Path,
    ) -> None:
        """Push reports failure when the item does not exist at target."""
        item = Item(
            item_type=ItemType.AGENT,
            name="ghost",
            source_path=Path("/nonexistent/ghost.md"),
        )

        source_dir = tmp_path / "source"
        source_dir.mkdir()

        engine = SyncEngine(target_manager)
        report = engine.push(
            [item],
            source_dir=source_dir,
        )

        assert not report.is_success


# ---------------------------------------------------------------------------
# SyncEngine — aggregate
# ---------------------------------------------------------------------------


class TestAggregate:
    """Tests for SyncEngine.aggregate static method."""

    def test_all_success(self) -> None:
        results = [
            SyncResult(
                plan=mock.Mock(action=SyncAction.INSTALL),
                is_success=True,
                files_copied=2,
            ),
            SyncResult(
                plan=mock.Mock(action=SyncAction.INSTALL),
                is_success=True,
                files_copied=1,
            ),
        ]
        report = SyncEngine.aggregate(results)
        assert len(report.installed) == 2
        assert len(report.updated) == 0
        assert len(report.failed) == 0
        assert len(report.skipped) == 0
        total_files = sum(r.files_copied for r in report.installed)
        assert total_files == 3

    def test_mixed_results(self) -> None:
        results = [
            SyncResult(
                plan=mock.Mock(action=SyncAction.INSTALL),
                is_success=True,
                files_copied=1,
            ),
            SyncResult(
                plan=mock.Mock(action=SyncAction.SKIP),
                is_success=True,
                files_copied=0,
            ),
            SyncResult(
                plan=mock.Mock(action=SyncAction.INSTALL),
                is_success=False,
                files_copied=0,
            ),
            SyncResult(
                plan=mock.Mock(action=SyncAction.UPDATE),
                is_success=True,
                files_copied=1,
            ),
        ]
        report = SyncEngine.aggregate(results)
        assert len(report.installed) == 1
        assert len(report.updated) == 1
        assert len(report.failed) == 1
        assert len(report.skipped) == 1
        total_files = sum(r.files_copied for r in report.installed + report.updated)
        assert total_files == 2

    def test_empty_results(self) -> None:
        report = SyncEngine.aggregate([])
        assert len(report.installed) == 0
        assert len(report.failed) == 0


# ---------------------------------------------------------------------------
# SyncEngine — compute_sync_plan
# ---------------------------------------------------------------------------


class TestComputeSyncPlan:
    """Tests for sync plan computation (existence-based)."""

    def test_new_item_in_source(
        self,
        target_manager: TargetManager,
        fake_home: SimpleNamespace,
        tmp_path: Path,
    ) -> None:
        """Item exists in source but not in target -> pull."""
        item = Item(
            item_type=ItemType.AGENT,
            name="new-agent",
            source_path=Path("/src/new-agent.md"),
        )
        state = SyncState()

        engine = SyncEngine(target_manager)
        plan = engine.compute_sync_plan(
            [item],
            state,
            tmp_path / "src",
        )

        assert len(plan) == 1
        assert plan[0][1] == "pull"

    def test_installed_item_skip(
        self,
        target_manager: TargetManager,
        fake_home: SimpleNamespace,
        tmp_path: Path,
    ) -> None:
        """Item exists at target -> skip."""
        agent_dir = fake_home.opencode / "agent"
        target_file = agent_dir / "existing.md"
        target_file.write_text("# Existing")

        item = Item(
            item_type=ItemType.AGENT,
            name="existing",
            source_path=Path("/src/existing.md"),
        )

        state = SyncState()

        engine = SyncEngine(target_manager)
        plan = engine.compute_sync_plan(
            [item],
            state,
            tmp_path / "src",
        )

        assert len(plan) == 1
        assert plan[0][1] == "skip"


# ---------------------------------------------------------------------------
# SyncEngine — _dest_path
# ---------------------------------------------------------------------------


class TestDestPath:
    """Tests for SyncEngine._dest_path static method."""

    def test_file_item(self) -> None:
        item = Item(
            item_type=ItemType.AGENT,
            name="coder",
            source_path=Path("/src/coder.md"),
        )
        target_dir = Path("/target/agent")
        result = SyncEngine._dest_path(item, target_dir)
        assert result == Path("/target/agent/coder.md")

    def test_directory_item(self) -> None:
        item = Item(
            item_type=ItemType.SKILL,
            name="python",
            source_path=Path("/src/python"),
        )
        target_dir = Path("/target/skill")
        result = SyncEngine._dest_path(item, target_dir)
        assert result == Path("/target/skill/python")


# ---------------------------------------------------------------------------
# Error handling — _copy_item
# ---------------------------------------------------------------------------


class TestCopyItemPartialCleanup:
    """Tests for _copy_item cleanup of partial directory copies."""

    def test_partial_directory_copy_is_cleaned_up(self, tmp_path: Path) -> None:
        """If shutil.copytree fails partway, partial destination is removed."""
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        (src_dir / "a.txt").write_text("a")
        (src_dir / "b.txt").write_text("b")

        dest = tmp_path / "dest_dir"

        with mock.patch("shutil.copytree", side_effect=PermissionError("denied")):
            count, err = _copy_item(src_dir, dest, use_symlinks=False)

        assert err is not None
        # Verify the error propagates the PermissionError message
        assert "denied" in err
        # Partial directory must be cleaned up.
        assert not dest.exists()

    def test_partial_directory_cleanup_survives_rmtree_failure(self, tmp_path: Path) -> None:
        """If both copytree and rmtree fail, error is still reported."""
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        (src_dir / "a.txt").write_text("a")

        dest = tmp_path / "dest_dir"

        with (
            mock.patch("shutil.copytree", side_effect=PermissionError("copy denied")),
            mock.patch("shutil.rmtree", side_effect=OSError("rmtree failed")),
        ):
            count, err = _copy_item(src_dir, dest, use_symlinks=False)

        assert err is not None
        # Verify the error propagates the original copy failure message
        assert "copy denied" in err

    def test_file_copy_failure_does_not_affect_parent(self, tmp_path: Path) -> None:
        """Single-file copy failure should not create any destination."""
        source = tmp_path / "nonexistent.txt"
        dest = tmp_path / "sub" / "dest.txt"

        count, err = _copy_item(source, dest, use_symlinks=False)

        assert err is not None
        assert count == 0
        assert not dest.exists()


# ---------------------------------------------------------------------------
# Error handling — _atomic_copy_to
# ---------------------------------------------------------------------------


class TestAtomicCopyErrorHandling:
    """Tests for _atomic_copy_to error paths and cleanup guarantees."""

    def test_stale_tmp_removal_failure_returns_error(self, tmp_path: Path) -> None:
        """If stale temp file cannot be removed, return error immediately."""
        # NOTE: This test mocks _remove_item (private function) to simulate
        # a stale temp file removal failure. If _remove_item is renamed/removed,
        # this test needs updating.
        source = tmp_path / "source.txt"
        source.write_text("content")
        dest = tmp_path / "dest.txt"

        with (
            mock.patch("agentfiles.engine._remove_item", return_value=(False, "permission denied")),
            mock.patch("os.path.lexists", return_value=True),
        ):
            files_copied, err = SyncEngine._atomic_copy_to(source, dest, use_symlinks=False)

        assert err is not None
        assert files_copied == 0

    def test_copy_failure_cleans_up_temp(self, tmp_path: Path) -> None:
        """If copy to temp location fails, temp file is cleaned up."""
        source = tmp_path / "nonexistent_source.txt"
        dest = tmp_path / "dest.txt"

        files_copied, err = SyncEngine._atomic_copy_to(source, dest, use_symlinks=False)

        assert err is not None
        assert files_copied == 0
        tmp_dest = dest.with_suffix(dest.suffix + ".agentfiles_tmp")
        assert not os.path.lexists(tmp_dest)

    def test_backup_move_failure_cleans_up_temp(self, tmp_path: Path) -> None:
        """If moving dest to backup fails, temp file is cleaned up."""
        # NOTE: This test mocks Path.rename to simulate a backup (.bak) creation
        # failure in _atomic_copy_to. Coupled to the rename-based backup protocol.
        source = tmp_path / "source.txt"
        source.write_text("new content")
        dest = tmp_path / "dest.txt"
        dest.write_text("original content")

        # Simulate dest.rename(backup) failing.
        original_rename = Path.rename

        def selective_rename(self_path: Path, target: Path) -> Path:
            # Fail when trying to rename dest to .bak
            if str(target).endswith(".bak"):
                raise OSError("cannot create backup")
            return original_rename(self_path, target)

        with mock.patch.object(Path, "rename", selective_rename):
            files_copied, err = SyncEngine._atomic_copy_to(source, dest, use_symlinks=False)

        assert err is not None
        # Verify the error mentions the backup creation failure
        assert "back up" in err.lower() or "backup" in err.lower()
        tmp_dest = dest.with_suffix(dest.suffix + ".agentfiles_tmp")
        assert not os.path.lexists(tmp_dest)
        # Original dest must still exist.
        assert dest.exists()
        assert dest.read_text() == "original content"

    def test_rename_failure_restores_backup(self, tmp_path: Path) -> None:
        """If tmp -> dest rename fails, backup is restored to dest."""
        # NOTE: This test mocks Path.rename to simulate a rename failure during
        # the temp-to-dest swap in _atomic_copy_to. Coupled to the rename-based
        # atomic swap protocol: dest -> .bak, tmp -> dest, .bak -> dest (restore).
        source = tmp_path / "source.txt"
        source.write_text("new content")
        dest = tmp_path / "dest.txt"
        dest.write_text("original content")

        original_rename = Path.rename

        def selective_rename(self_path: Path, target: Path) -> Path:
            # Fail when renaming the temp file to dest (tmp -> dest).
            # Allow dest -> .bak backup and .bak -> dest restore.
            if ".agentfiles_tmp" in str(self_path):
                raise OSError("rename failed")
            return original_rename(self_path, target)

        with mock.patch.object(Path, "rename", selective_rename):
            files_copied, err = SyncEngine._atomic_copy_to(source, dest, use_symlinks=False)

        assert err is not None
        # Verify the error reports the rename step that failed
        assert "rename failed" in err.lower()
        # Backup must have been restored.
        assert dest.exists()
        assert dest.read_text() == "original content"
        # Backup must be gone (restored).
        backup = dest.with_suffix(dest.suffix + ".bak")
        assert not os.path.lexists(backup)

    def test_rename_and_restore_failure_logs_critical(self, tmp_path: Path) -> None:
        """If both rename and backup restore fail, log CRITICAL."""
        # NOTE: This test mocks Path.rename to simulate both the tmp -> dest rename
        # failure AND the subsequent backup restore failure in _atomic_copy_to.
        # Coupled to the atomic swap protocol and the restore-on-failure logic.
        source = tmp_path / "source.txt"
        source.write_text("new content")
        dest = tmp_path / "dest.txt"
        dest.write_text("original content")

        original_rename = Path.rename

        def selective_rename(self_path: Path, target: Path) -> Path:
            # Allow only the dest -> .bak backup rename (target ends with .bak).
            # Fail all subsequent renames: tmp -> dest AND .bak -> dest restore,
            # so that both the main rename and the recovery restore fail.
            if not str(target).endswith(".bak"):
                raise OSError("broken")
            return original_rename(self_path, target)

        with (
            mock.patch.object(Path, "rename", selective_rename),
            mock.patch("agentfiles.engine.logger") as mock_logger,
        ):
            files_copied, err = SyncEngine._atomic_copy_to(source, dest, use_symlinks=False)

        assert err is not None
        # CRITICAL log should have been emitted for restore failure.
        mock_logger.critical.assert_called_once()
        assert "CRITICAL" in mock_logger.critical.call_args[0][0]

    def test_successful_copy_removes_backup(self, tmp_path: Path) -> None:
        """On success, backup file is removed."""
        source = tmp_path / "source.txt"
        source.write_text("new content")
        dest = tmp_path / "dest.txt"
        dest.write_text("original content")

        files_copied, err = SyncEngine._atomic_copy_to(source, dest, use_symlinks=False)

        assert err is None
        assert files_copied == 1
        assert dest.read_text() == "new content"
        backup = dest.with_suffix(dest.suffix + ".bak")
        assert not os.path.lexists(backup)

    def test_orphaned_backup_warning_logged(self, tmp_path: Path) -> None:
        """If backup cleanup fails on success path, a warning is logged."""
        # NOTE: This test mocks _remove_item (private function) to simulate
        # a backup file removal failure on the success path. If _remove_item
        # is renamed/removed, this test needs updating.
        source = tmp_path / "source.txt"
        source.write_text("new content")
        dest = tmp_path / "dest.txt"
        dest.write_text("original content")

        original_remove = _remove_item

        def selective_remove(path: Path) -> tuple[bool, str | None]:
            # Fail only when removing the .bak backup file.
            if str(path).endswith(".bak"):
                return False, "cannot remove backup"
            return original_remove(path)

        with (
            mock.patch("agentfiles.engine._remove_item", side_effect=selective_remove),
            mock.patch("agentfiles.engine.logger") as mock_logger,
        ):
            files_copied, err = SyncEngine._atomic_copy_to(source, dest, use_symlinks=False)

        assert err is None
        mock_logger.warning.assert_called_once()
        assert "orphaned" in mock_logger.warning.call_args[0][0].lower()

    def test_handles_stale_tmp_before_copy(self, tmp_path: Path) -> None:
        """Pre-existing stale temp file is cleaned before copy."""
        source = tmp_path / "source.txt"
        source.write_text("content")
        dest = tmp_path / "dest.txt"

        # Create a stale temp file.
        tmp_dest = dest.with_suffix(dest.suffix + ".agentfiles_tmp")
        tmp_dest.write_text("stale data")

        files_copied, err = SyncEngine._atomic_copy_to(source, dest, use_symlinks=False)

        assert err is None
        assert files_copied == 1
        assert dest.read_text() == "content"
        # Stale tmp was cleaned and no new tmp left behind.
        assert not os.path.lexists(tmp_dest)


# ---------------------------------------------------------------------------
# Error handling — _execute_install
# ---------------------------------------------------------------------------


class TestExecuteInstallErrorHandling:
    """Tests for _execute_install error paths."""

    def test_install_fails_when_stale_removal_fails(self, tmp_path: Path) -> None:
        """If stale destination cannot be removed, install should fail."""
        # NOTE: This test mocks _remove_item (private function) to simulate
        # a stale file removal failure. If _remove_item is renamed/removed,
        # this test needs updating.
        source = tmp_path / "source.txt"
        source.write_text("content")

        target_dir = tmp_path / "target"
        target_dir.mkdir()

        item = Item(
            item_type=ItemType.AGENT,
            name="item",
            source_path=source,
            files=("source.txt",),
        )
        plan = SyncPlan(
            item=item,
            action=SyncAction.INSTALL,
            target_dir=target_dir,
            reason="not installed",
        )

        # Create a stale file at the exact destination path
        # (dest = target_dir / source_path.name = target_dir / "source.txt").
        stale = target_dir / "source.txt"
        stale.write_text("stale")

        with mock.patch(
            "agentfiles.engine._remove_item", return_value=(False, "permission denied")
        ):
            engine = SyncEngine(mock.Mock(spec=SyncTarget))
            result = engine._execute_install(plan)

        assert not result.is_success
        # Verify the error message mentions the stale destination cleanup failure
        assert "stale" in result.message.lower()

    def test_install_fails_when_target_dir_creation_fails(self, tmp_path: Path) -> None:
        """If target directory cannot be created, install should fail."""
        # NOTE: This test mocks Path.mkdir to simulate a permission error during
        # target directory creation in _execute_install. Coupled to the mkdir
        # call in the install path.
        source = tmp_path / "source.txt"
        source.write_text("content")

        item = Item(
            item_type=ItemType.AGENT,
            name="item",
            source_path=source,
            files=("item.txt",),
        )
        plan = SyncPlan(
            item=item,
            action=SyncAction.INSTALL,
            target_dir=tmp_path / "readonly" / "target",
            reason="not installed",
        )

        with mock.patch.object(Path, "mkdir", side_effect=PermissionError("denied")):
            engine = SyncEngine(mock.Mock(spec=SyncTarget))
            result = engine._execute_install(plan)

        assert not result.is_success
        # Verify the error message mentions the permission denial from mkdir
        assert "denied" in result.message


# ---------------------------------------------------------------------------
# Empty item lists — edge case
# ---------------------------------------------------------------------------


class TestEmptyItemList:
    """All public API methods should handle empty item lists gracefully."""

    def test_plan_sync_empty(self, target_manager: TargetManager) -> None:
        engine = SyncEngine(target_manager)
        plans = engine.plan_sync([])
        assert plans == []

    def test_execute_plan_empty(self, target_manager: TargetManager) -> None:
        engine = SyncEngine(target_manager)
        results = engine.execute_plan([])
        assert results == []

    def test_sync_empty(self, target_manager: TargetManager) -> None:
        engine = SyncEngine(target_manager)
        report = engine.sync([])
        assert report.is_success
        assert report.summary() == "No operations performed"

    def test_uninstall_empty(self, target_manager: TargetManager) -> None:
        engine = SyncEngine(target_manager)
        report = engine.uninstall([])
        assert report.is_success
        assert report.summary() == "No operations performed"

    def test_push_empty(
        self,
        target_manager: TargetManager,
        tmp_path: Path,
    ) -> None:
        engine = SyncEngine(target_manager)
        report = engine.push(
            [],
            source_dir=tmp_path,
        )
        assert report.is_success
        assert report.summary() == "No operations performed"

    def test_compute_sync_plan_empty(
        self,
        target_manager: TargetManager,
        tmp_path: Path,
    ) -> None:
        engine = SyncEngine(target_manager)
        plan = engine.compute_sync_plan(
            [],
            SyncState(),
            tmp_path,
        )
        assert plan == []


# ---------------------------------------------------------------------------
# Mixed-action batch execution
# ---------------------------------------------------------------------------


class TestMixedActionBatch:
    """Execute plans with a mix of INSTALL, UPDATE, SKIP, UNINSTALL."""

    def test_mixed_actions_in_one_batch(
        self,
        target_manager: TargetManager,
        fake_home: SimpleNamespace,
        tmp_path: Path,
    ) -> None:
        """A single execute_plan call handles install, update, skip, uninstall."""
        skill_dir = fake_home.opencode / "skill"
        skill_dir.mkdir(parents=True, exist_ok=True)

        # -- Item 1: INSTALL (brand-new skill) --
        install_src = tmp_path / "new_skill"
        install_src.mkdir()
        (install_src / "SKILL.md").write_text("# New Skill")
        install_item = Item(
            item_type=ItemType.SKILL,
            name="new-skill",
            source_path=install_src,
            files=("SKILL.md",),
        )

        # -- Item 2: SKIP (up-to-date item) --
        skip_item = Item(
            item_type=ItemType.SKILL,
            name="skip-me",
            source_path=Path("/src/skip-me"),
        )

        # -- Item 3: UPDATE (existing target with different content) --
        update_src = tmp_path / "update_skill"
        update_src.mkdir()
        (update_src / "SKILL.md").write_text("# Updated")
        update_dest = skill_dir / "update-skill"
        update_dest.mkdir()
        (update_dest / "SKILL.md").write_text("# Old")
        update_item = Item(
            item_type=ItemType.SKILL,
            name="update-skill",
            source_path=update_src,
            files=("SKILL.md",),
        )

        # -- Item 4: UNINSTALL (existing target to remove) --
        uninstall_dest = skill_dir / "remove-skill"
        uninstall_dest.mkdir()
        (uninstall_dest / "SKILL.md").write_text("# Remove Me")
        uninstall_item = Item(
            item_type=ItemType.SKILL,
            name="remove-skill",
            source_path=Path("/src/remove-skill"),
        )

        plans = [
            SyncPlan(
                item=install_item,
                action=SyncAction.INSTALL,
                target_dir=skill_dir,
                reason="not installed",
            ),
            SyncPlan(
                item=skip_item,
                action=SyncAction.SKIP,
                target_dir=skill_dir,
                reason="already up-to-date",
            ),
            SyncPlan(
                item=update_item,
                action=SyncAction.UPDATE,
                target_dir=skill_dir,
                reason="content differs",
            ),
            SyncPlan(
                item=uninstall_item,
                action=SyncAction.UNINSTALL,
                target_dir=skill_dir,
                reason="scheduled for removal",
            ),
        ]

        engine = SyncEngine(target_manager)
        results = engine.execute_plan(plans)

        assert len(results) == 4
        assert results[0].is_success  # install
        assert results[1].is_success  # skip
        assert results[2].is_success  # update
        assert results[3].is_success  # uninstall

        report = SyncEngine.aggregate(results)
        assert len(report.installed) == 1
        assert len(report.skipped) == 1
        assert len(report.updated) == 1
        assert len(report.uninstalled) == 1
        assert report.is_success


# ---------------------------------------------------------------------------
# _execute_update — direct tests
# ---------------------------------------------------------------------------


class TestExecuteUpdate:
    """Direct tests for _execute_update via execute_plan."""

    def test_update_replaces_target_content(
        self,
        target_manager: TargetManager,
        fake_home: SimpleNamespace,
        tmp_path: Path,
    ) -> None:
        target_dir = target_manager.get_target_dir(ItemType.SKILL)
        assert target_dir is not None

        # Pre-install old content.
        old_dest = target_dir / "up-skill"
        old_dest.mkdir()
        (old_dest / "SKILL.md").write_text("old content")
        (old_dest / "extra.txt").write_text("extra")

        # New source with different files.
        new_src = tmp_path / "new_src"
        new_src.mkdir()
        (new_src / "SKILL.md").write_text("brand new")

        item = Item(
            item_type=ItemType.SKILL,
            name="up-skill",
            source_path=new_src,
            files=("SKILL.md",),
        )
        plan = SyncPlan(
            item=item,
            action=SyncAction.UPDATE,
            target_dir=target_dir,
            reason="content differs",
        )
        engine = SyncEngine(target_manager)
        results = engine.execute_plan([plan])

        assert results[0].is_success
        assert (old_dest / "SKILL.md").read_text() == "brand new"
        # Old extra file removed by atomic copy (backup restored on success).
        assert not (old_dest / "extra.txt").exists()

    def test_update_with_symlinks(
        self,
        target_manager: TargetManager,
        tmp_path: Path,
    ) -> None:
        target_dir = target_manager.get_target_dir(ItemType.AGENT)
        assert target_dir is not None

        # Pre-install old agent file.
        old_dest = target_dir / "my-agent.md"
        old_dest.write_text("old agent")

        # New source.
        new_src = tmp_path / "my-agent.md"
        new_src.write_text("updated agent content")

        item = Item(
            item_type=ItemType.AGENT,
            name="my-agent",
            source_path=new_src,
            files=("my-agent.md",),
        )
        plan = SyncPlan(
            item=item,
            action=SyncAction.UPDATE,
            target_dir=target_dir,
            reason="content differs",
        )
        engine = SyncEngine(target_manager, use_symlinks=True)
        results = engine.execute_plan([plan])

        assert results[0].is_success
        dest = target_dir / "my-agent.md"
        assert dest.is_symlink()


# ---------------------------------------------------------------------------
# _execute_uninstall — failure path
# ---------------------------------------------------------------------------


class TestExecuteUninstallFailure:
    """Tests for _execute_uninstall when removal fails."""

    def test_uninstall_permission_denied(
        self,
        target_manager: TargetManager,
        tmp_path: Path,
    ) -> None:
        # NOTE: This test mocks _remove_item (private function) to simulate
        # a permission error during uninstall. If _remove_item is renamed/removed,
        # this test needs updating.
        target_dir = tmp_path / "target"
        target_dir.mkdir()
        item = Item(
            item_type=ItemType.SKILL,
            name="protected",
            source_path=Path("/src/protected"),
        )
        plan = SyncPlan(
            item=item,
            action=SyncAction.UNINSTALL,
            target_dir=target_dir,
            reason="removal",
        )

        with mock.patch(
            "agentfiles.engine._remove_item", return_value=(False, "permission denied")
        ):
            engine = SyncEngine(target_manager)
            result = engine._execute_uninstall(plan)

        assert not result.is_success
        # Verify the error propagates the _remove_item failure reason
        assert "permission denied" in result.message


# ---------------------------------------------------------------------------
# plan_sync with UPDATE action
# ---------------------------------------------------------------------------


class TestPlanSyncUpdateAction:
    """Tests for plan_sync with action=UPDATE."""

    def test_update_action_installs_not_installed(self, target_manager: TargetManager) -> None:
        """Items not yet installed should be planned for INSTALL when action=UPDATE."""
        item = _make_dir_item("brand-new")
        engine = SyncEngine(target_manager)
        plans = engine.plan_sync(
            [item],
            action=SyncAction.UPDATE,
        )
        assert len(plans) == 1
        assert plans[0].action == SyncAction.INSTALL

    def test_update_action_updates_installed(
        self,
        target_manager: TargetManager,
        fake_home: SimpleNamespace,
    ) -> None:
        """Installed items should be planned for UPDATE (force reinstall)."""
        skill_dir = fake_home.opencode / "skill" / "diff-skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("old")

        item = _make_dir_item("diff-skill")
        engine = SyncEngine(target_manager)
        plans = engine.plan_sync(
            [item],
            action=SyncAction.UPDATE,
        )

        assert len(plans) == 1
        assert plans[0].action == SyncAction.UPDATE

    def test_update_action_updates_up_to_date(
        self,
        target_manager: TargetManager,
        fake_home: SimpleNamespace,
    ) -> None:
        """Installed items should be UPDATE even if content is identical."""
        skill_dir = fake_home.opencode / "skill" / "same-skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("content")

        item = _make_dir_item("same-skill")
        engine = SyncEngine(target_manager)
        plans = engine.plan_sync(
            [item],
            action=SyncAction.UPDATE,
        )

        assert len(plans) == 1
        assert plans[0].action == SyncAction.UPDATE


# ---------------------------------------------------------------------------
# _atomic_copy_to with symlinks
# ---------------------------------------------------------------------------


class TestAtomicCopySymlinks:
    """Tests for _atomic_copy_to with use_symlinks=True."""

    def test_atomic_copy_symlink_file(self, tmp_path: Path) -> None:
        source = tmp_path / "source.txt"
        source.write_text("content")
        dest = tmp_path / "dest.txt"

        files_copied, err = SyncEngine._atomic_copy_to(
            source,
            dest,
            use_symlinks=True,
        )

        assert err is None
        assert files_copied == 0
        assert dest.is_symlink()
        assert dest.read_text() == "content"

    def test_atomic_copy_symlink_directory(self, tmp_path: Path) -> None:
        src_dir = tmp_path / "src_dir"
        src_dir.mkdir()
        (src_dir / "a.txt").write_text("a")
        dest = tmp_path / "dest_dir"

        files_copied, err = SyncEngine._atomic_copy_to(
            src_dir,
            dest,
            use_symlinks=True,
        )

        assert err is None
        assert files_copied == 0
        assert dest.is_symlink()
        assert (dest / "a.txt").read_text() == "a"

    def test_atomic_copy_symlink_with_existing_dest(self, tmp_path: Path) -> None:
        source = tmp_path / "source.txt"
        source.write_text("new")
        dest = tmp_path / "dest.txt"
        dest.write_text("old")

        files_copied, err = SyncEngine._atomic_copy_to(
            source,
            dest,
            use_symlinks=True,
        )

        assert err is None
        assert dest.is_symlink()
        assert dest.read_text() == "new"
        # Backup should be cleaned up.
        backup = dest.with_suffix(dest.suffix + ".bak")
        assert not os.path.lexists(backup)


# ---------------------------------------------------------------------------
# _atomic_copy_to — pre-existing backup
# ---------------------------------------------------------------------------


class TestAtomicCopyExistingBackup:
    """Tests for _atomic_copy_to when a .bak file already exists."""

    def test_existing_backup_is_overwritten(self, tmp_path: Path) -> None:
        """A pre-existing .bak file should be replaced during the swap."""
        source = tmp_path / "source.txt"
        source.write_text("new content")
        dest = tmp_path / "dest.txt"
        dest.write_text("current content")
        # Create a stale .bak from a previous operation.
        backup = dest.with_suffix(dest.suffix + ".bak")
        backup.write_text("stale backup data")

        files_copied, err = SyncEngine._atomic_copy_to(
            source,
            dest,
            use_symlinks=False,
        )

        assert err is None
        assert files_copied == 1
        assert dest.read_text() == "new content"
        # The stale backup was overwritten by current dest, then cleaned up.
        assert not os.path.lexists(backup)

    def test_existing_backup_as_symlink(self, tmp_path: Path) -> None:
        """A pre-existing .bak symlink should be handled correctly."""
        source = tmp_path / "source.txt"
        source.write_text("new")
        dest = tmp_path / "dest.txt"
        dest.write_text("current")

        # Create a .bak that is a symlink.
        backup_target = tmp_path / "backup_content.txt"
        backup_target.write_text("backup via symlink")
        backup = dest.with_suffix(dest.suffix + ".bak")
        backup.symlink_to(backup_target)

        files_copied, err = SyncEngine._atomic_copy_to(
            source,
            dest,
            use_symlinks=False,
        )

        assert err is None
        assert dest.read_text() == "new"
        assert not os.path.lexists(backup)


# ---------------------------------------------------------------------------
# Push — additional edge cases
# ---------------------------------------------------------------------------


class TestPushEdgeCases:
    """Additional push tests for edge cases."""

    def test_push_multiple_items(
        self,
        target_manager: TargetManager,
        fake_home: SimpleNamespace,
        tmp_path: Path,
    ) -> None:
        """Push multiple items from different types in one call."""
        agent_dir = fake_home.opencode / "agent"
        agent_dir.mkdir(parents=True, exist_ok=True)
        (agent_dir / "agent-a.md").write_text("Agent A")
        (agent_dir / "agent-b.md").write_text("Agent B")

        item_a = Item(
            item_type=ItemType.AGENT,
            name="agent-a",
            source_path=agent_dir / "agent-a.md",
        )
        item_b = Item(
            item_type=ItemType.AGENT,
            name="agent-b",
            source_path=agent_dir / "agent-b.md",
        )

        source_dir = tmp_path / "source"
        source_dir.mkdir()

        engine = SyncEngine(target_manager)
        report = engine.push(
            [item_a, item_b],
            source_dir=source_dir,
        )

        assert report.is_success
        assert len(report.updated) == 2
        assert (source_dir / "agents" / "agent-a" / "agent-a.md").exists()
        assert (source_dir / "agents" / "agent-b" / "agent-b.md").exists()

    def test_push_skips_when_target_dir_is_none(
        self,
        tmp_path: Path,
    ) -> None:
        """Push with a mock target manager returning None skips items gracefully."""
        mock_target = mock.Mock(spec=SyncTarget)
        mock_target.get_target_dir.return_value = None
        item = Item(
            item_type=ItemType.COMMAND,
            name="my-cmd",
            source_path=Path("/src/my-cmd.md"),
        )

        source_dir = tmp_path / "source"
        source_dir.mkdir()

        engine = SyncEngine(mock_target)
        report = engine.push(
            [item],
            source_dir=source_dir,
        )

        assert report.is_success
        assert report.summary() == "No operations performed"

    def test_push_with_no_target_dir_logs_warning(
        self,
        target_manager: TargetManager,
        tmp_path: Path,
    ) -> None:
        """When platform is unsupported, push logs a warning and skips."""
        mock_target = mock.Mock(spec=SyncTarget)
        mock_target.get_target_dir.return_value = None
        item = Item(
            item_type=ItemType.AGENT,
            name="ghost",
            source_path=Path("/src/ghost.md"),
        )

        engine = SyncEngine(mock_target)
        with mock.patch("agentfiles.engine.logger") as mock_logger:
            report = engine.push(
                [item],
                source_dir=tmp_path,
            )

        mock_logger.warning.assert_called()
        assert report.is_success


# ---------------------------------------------------------------------------
# Parametrized tests — item types
# ---------------------------------------------------------------------------


class TestParametrizedItemTypes:
    """Parametrized tests that verify consistent behavior across item types."""

    @pytest.mark.parametrize(
        ("item_type", "item_factory"),
        [
            (ItemType.AGENT, _make_file_item),
            (ItemType.SKILL, _make_dir_item),
            (ItemType.COMMAND, _make_file_item),
            (ItemType.PLUGIN, _make_dir_item),
        ],
        ids=["agent", "skill", "command", "plugin"],
    )
    def test_plan_install_for_each_type(
        self,
        target_manager: TargetManager,
        item_type: ItemType,
        item_factory: Callable[[str], Item],
    ) -> None:
        """Each item type can be planned for installation on OpenCode."""
        item_name = f"test-{item_type.value}"
        item = item_factory(item_name)
        # Override type for non-default factories.
        if item_type in (ItemType.COMMAND, ItemType.PLUGIN):
            item = Item(
                item_type=item_type,
                name=item_name,
                source_path=item.source_path,
                files=item.files,
            )

        engine = SyncEngine(target_manager)
        plans = engine.plan_sync([item])

        # All types have a valid target dir on OpenCode.
        assert len(plans) == 1
        assert plans[0].action == SyncAction.INSTALL

    @pytest.mark.parametrize(
        "use_symlinks",
        [False, True],
        ids=["copy", "symlink"],
    )
    def test_install_with_symlink_flag(
        self,
        target_manager: TargetManager,
        tmp_path: Path,
        use_symlinks: bool,
    ) -> None:
        """Install produces symlinks when flag is True, copies otherwise."""
        src = tmp_path / "agent.md"
        src.write_text("# Agent Content")

        item = Item(
            item_type=ItemType.AGENT,
            name="test-agent",
            source_path=src,
            files=("agent.md",),
        )
        target_dir = target_manager.get_target_dir(ItemType.AGENT)
        assert target_dir is not None

        plan = SyncPlan(
            item=item,
            action=SyncAction.INSTALL,
            target_dir=target_dir,
            reason="not installed",
        )
        engine = SyncEngine(target_manager, use_symlinks=use_symlinks)
        results = engine.execute_plan([plan])

        assert results[0].is_success
        dest = target_dir / "agent.md"
        assert dest.exists()
        assert dest.is_symlink() == use_symlinks


# ---------------------------------------------------------------------------
# SyncReport — additional edge cases
# ---------------------------------------------------------------------------


class TestSyncReportEdgeCases:
    """Additional SyncReport edge cases."""

    def test_summary_with_files_copied(self) -> None:
        result = SyncResult(
            plan=mock.Mock(action=SyncAction.INSTALL),
            is_success=True,
            files_copied=5,
        )
        report = SyncReport(installed=[result])
        summary = report.summary()
        assert "Installed 1" in summary
        assert "Files copied: 5" in summary

    def test_summary_with_zero_files_copied(self) -> None:
        result = SyncResult(
            plan=mock.Mock(action=SyncAction.INSTALL),
            is_success=True,
            files_copied=0,
        )
        report = SyncReport(installed=[result])
        summary = report.summary()
        assert "Files copied" not in summary

    def test_success_count_excludes_failures(self) -> None:
        report = SyncReport(
            installed=[mock.Mock()],
            failed=[mock.Mock(), mock.Mock()],
        )
        assert report.success_count == 1
        assert report.failure_count == 2

    def test_aggregate_unknown_action_goes_to_skipped(self) -> None:
        """Results with unknown SyncAction are classified as skipped."""
        result = SyncResult(
            plan=mock.Mock(action=mock.Mock(value="unknown")),
            is_success=True,
            files_copied=0,
        )
        report = SyncEngine.aggregate([result])
        assert len(report.skipped) == 1


# ---------------------------------------------------------------------------
# compute_sync_plan — platform with no state
# ---------------------------------------------------------------------------


class TestComputeSyncPlanEdgeCases:
    """Additional edge cases for compute_sync_plan."""

    def test_platform_not_in_state(
        self,
        target_manager: TargetManager,
        tmp_path: Path,
    ) -> None:
        """When platform has no entry in state, plan should be 'pull'."""
        item = Item(
            item_type=ItemType.AGENT,
            name="new-agent",
            source_path=Path("/src/new-agent.md"),
        )
        # Empty state — no platform info at all.
        state = SyncState()

        engine = SyncEngine(target_manager)
        plan = engine.compute_sync_plan(
            [item],
            state,
            tmp_path,
        )

        assert len(plan) == 1
        assert plan[0][1] == "pull"

    def test_item_not_in_platform_state(
        self,
        target_manager: TargetManager,
        tmp_path: Path,
    ) -> None:
        """When item has no entry in platform state, plan should be 'pull'."""
        item = Item(
            item_type=ItemType.AGENT,
            name="missing-agent",
            source_path=Path("/src/missing-agent.md"),
        )
        # State exists but item does not.
        state = SyncState()

        engine = SyncEngine(target_manager)
        plan = engine.compute_sync_plan(
            [item],
            state,
            tmp_path,
        )

        assert len(plan) == 1
        assert plan[0][1] == "pull"

    def test_existing_target_dir_produces_pull(
        self,
        target_manager: TargetManager,
        tmp_path: Path,
    ) -> None:
        """Item whose type has a target dir on the platform produces a pull plan."""
        item = Item(
            item_type=ItemType.COMMAND,
            name="my-cmd",
            source_path=Path("/src/my-cmd.md"),
        )
        state = SyncState()

        engine = SyncEngine(target_manager)
        plan = engine.compute_sync_plan(
            [item],
            state,
            tmp_path,
        )

        assert len(plan) == 1
        assert plan[0][1] == "pull"


# ---------------------------------------------------------------------------
# _update_sync_state — state persistence after pull
# ---------------------------------------------------------------------------


class TestUpdateSyncState:
    """Tests for _update_sync_state — ensuring pull operations update state."""

    def test_sync_with_source_dir_updates_state(
        self,
        target_manager: TargetManager,
        tmp_path: Path,
    ) -> None:
        """engine.sync() with source_dir persists sync timestamps to state file."""
        from agentfiles.config import load_sync_state

        src_dir = tmp_path / "skill_src"
        src_dir.mkdir()
        (src_dir / "SKILL.md").write_text("# My Skill")

        item = Item(
            item_type=ItemType.SKILL,
            name="my-skill",
            source_path=src_dir,
            files=("SKILL.md",),
        )

        source_dir = tmp_path / "source"
        source_dir.mkdir()

        engine = SyncEngine(target_manager)
        report = engine.sync(
            [item],
            source_dir=source_dir,
        )

        assert report.is_success
        assert len(report.installed) >= 1

        # State file should now exist with sync timestamps.
        state = load_sync_state(source_dir)
        assert state.last_sync != ""

        item_state = state.items.get("skill/my-skill")
        assert item_state is not None
        assert item_state.synced_at != ""

    def test_sync_without_source_dir_skips_state_update(
        self,
        target_manager: TargetManager,
        tmp_path: Path,
    ) -> None:
        """engine.sync() without source_dir does not create a state file."""
        from agentfiles.config import get_state_path

        src_dir = tmp_path / "skill_src"
        src_dir.mkdir()
        (src_dir / "SKILL.md").write_text("# Skill")

        item = Item(
            item_type=ItemType.SKILL,
            name="no-state-skill",
            source_path=src_dir,
            files=("SKILL.md",),
        )

        engine = SyncEngine(target_manager)
        report = engine.sync([item])

        assert report.is_success
        # No state file should be created when source_dir is not provided.
        assert not get_state_path(tmp_path).exists()

    def test_sync_dry_run_skips_state_update(
        self,
        target_manager: TargetManager,
        tmp_path: Path,
    ) -> None:
        """engine.sync() in dry-run mode does not update state."""
        from agentfiles.config import get_state_path

        src_dir = tmp_path / "skill_src"
        src_dir.mkdir()
        (src_dir / "SKILL.md").write_text("# Skill")

        item = Item(
            item_type=ItemType.SKILL,
            name="dry-skill",
            source_path=src_dir,
            files=("SKILL.md",),
        )

        source_dir = tmp_path / "source"
        source_dir.mkdir()

        engine = SyncEngine(target_manager, dry_run=True)
        report = engine.sync(
            [item],
            source_dir=source_dir,
        )

        assert report.is_success
        # Dry-run should not create state file.
        assert not get_state_path(source_dir).exists()

    def test_sync_state_failure_does_not_fail_sync(
        self,
        target_manager: TargetManager,
        tmp_path: Path,
    ) -> None:
        """If state save fails, sync still succeeds (graceful degradation)."""
        src_dir = tmp_path / "skill_src"
        src_dir.mkdir()
        (src_dir / "SKILL.md").write_text("# Skill")

        item = Item(
            item_type=ItemType.SKILL,
            name="graceful-skill",
            source_path=src_dir,
            files=("SKILL.md",),
        )

        source_dir = tmp_path / "source"
        source_dir.mkdir()

        engine = SyncEngine(target_manager)

        with mock.patch("agentfiles.engine.save_sync_state", side_effect=OSError("disk full")):
            report = engine.sync(
                [item],
                source_dir=source_dir,
            )

        # Sync itself must succeed even though state save failed.
        assert report.is_success
        assert len(report.installed) >= 1

    def test_sync_state_records_platform(
        self,
        target_manager: TargetManager,
        tmp_path: Path,
    ) -> None:
        """Syncing records state for the platform."""
        from agentfiles.config import load_sync_state

        src_dir = tmp_path / "skill_src"
        src_dir.mkdir()
        (src_dir / "SKILL.md").write_text("# Multi")

        item = Item(
            item_type=ItemType.SKILL,
            name="multi-skill",
            source_path=src_dir,
            files=("SKILL.md",),
        )

        source_dir = tmp_path / "source"
        source_dir.mkdir()

        engine = SyncEngine(target_manager)
        report = engine.sync(
            [item],
            source_dir=source_dir,
        )

        assert report.is_success

        state = load_sync_state(source_dir)
        assert "skill/multi-skill" in state.items

    def test_sync_state_skipped_items_still_recorded(
        self,
        target_manager: TargetManager,
        fake_home: SimpleNamespace,
        tmp_path: Path,
    ) -> None:
        """Skipped items (already up-to-date) are recorded in state."""
        from agentfiles.config import load_sync_state

        skill_dir = fake_home.opencode / "skill" / "existing"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("content")

        item = Item(
            item_type=ItemType.SKILL,
            name="existing",
            source_path=skill_dir,
            files=("SKILL.md",),
        )

        source_dir = tmp_path / "source"
        source_dir.mkdir()

        engine = SyncEngine(target_manager)
        report = engine.sync(
            [item],
            source_dir=source_dir,
        )

        assert report.is_success
        assert len(report.skipped) >= 1

        # Even skipped items should be recorded in state.
        state = load_sync_state(source_dir)
        assert "skill/existing" in state.items

    def test_sync_state_load_failure_graceful(
        self,
        target_manager: TargetManager,
        tmp_path: Path,
    ) -> None:
        """If state load fails, sync still succeeds and state is recreated."""
        from agentfiles.config import get_state_path

        src_dir = tmp_path / "skill_src"
        src_dir.mkdir()
        (src_dir / "SKILL.md").write_text("# Skill")

        item = Item(
            item_type=ItemType.SKILL,
            name="recover-skill",
            source_path=src_dir,
            files=("SKILL.md",),
        )

        source_dir = tmp_path / "source"
        source_dir.mkdir()

        # Create a corrupted state file.
        state_file = get_state_path(source_dir)
        state_file.write_text("{{invalid yaml::")

        engine = SyncEngine(target_manager)
        with mock.patch("agentfiles.engine.logger"):
            report = engine.sync(
                [item],
                source_dir=source_dir,
            )

        assert report.is_success


# ---------------------------------------------------------------------------
# execute_plan — error isolation
# ---------------------------------------------------------------------------


class TestExecutePlanErrorIsolation:
    """Tests for try/except isolation in execute_plan."""

    def test_unhandled_exception_in_handler_returns_failed_result(
        self,
        target_manager: TargetManager,
        tmp_path: Path,
    ) -> None:
        """An unhandled exception in _execute_single returns a failed SyncResult."""
        src = tmp_path / "agent.md"
        src.write_text("# Agent")

        item = Item(
            item_type=ItemType.AGENT,
            name="crash-agent",
            source_path=src,
            files=("agent.md",),
        )
        plan = SyncPlan(
            item=item,
            action=SyncAction.INSTALL,
            target_dir=tmp_path / "target",
            reason="test",
        )

        engine = SyncEngine(target_manager)

        # NOTE: This test mocks _execute_single (private method) to simulate
        # an unhandled exception. If _execute_single is renamed/removed,
        # this test needs updating.
        with mock.patch.object(engine, "_execute_single", side_effect=RuntimeError("boom")):
            results = engine.execute_plan([plan])

        assert len(results) == 1
        assert not results[0].is_success
        # Verify the error message contains the original exception text
        assert "boom" in results[0].message

    def test_one_failure_does_not_abort_batch(
        self,
        target_manager: TargetManager,
        tmp_path: Path,
    ) -> None:
        """A crashing plan does not prevent subsequent plans from executing."""
        src = tmp_path / "agent.md"
        src.write_text("# Agent")

        item = Item(
            item_type=ItemType.AGENT,
            name="good-agent",
            source_path=src,
            files=("agent.md",),
        )

        good_plan = SyncPlan(
            item=item,
            action=SyncAction.INSTALL,
            target_dir=tmp_path / "target",
            reason="test",
        )
        bad_plan = SyncPlan(
            item=item,
            action=SyncAction.INSTALL,
            target_dir=tmp_path / "target2",
            reason="test",
        )

        engine = SyncEngine(target_manager)

        # NOTE: This test mocks _execute_single (private method) to selectively
        # crash on one plan. If _execute_single is renamed/removed, this test
        # needs updating.
        original_execute = engine._execute_single

        def selective_crash(plan: SyncPlan) -> SyncResult:
            # Crash only on bad_plan (identified by reference), let good_plan through
            if plan is bad_plan:
                raise RuntimeError("crash")
            return original_execute(plan)

        with mock.patch.object(engine, "_execute_single", side_effect=selective_crash):
            results = engine.execute_plan([bad_plan, good_plan])

        assert len(results) == 2
        assert not results[0].is_success
        # Verify the error message contains the original exception text
        assert "crash" in results[0].message
        assert results[1].is_success
