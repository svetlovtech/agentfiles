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
    ItemState,
    ItemType,
    Platform,
    PlatformState,
    SyncAction,
    SyncPlan,
    SyncResult,
    SyncState,
    resolve_target_name,
)
from agentfiles.target import TargetDiscovery, TargetManager

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def fake_home(tmp_path: Path) -> SimpleNamespace:
    """Create a fake home with platform config directories."""
    home = tmp_path / "home"
    home.mkdir()

    oc_dir = home / ".config" / "opencode"
    (oc_dir / "agent").mkdir(parents=True)
    (oc_dir / "skill").mkdir(parents=True)
    (oc_dir / "command").mkdir(parents=True)
    (oc_dir / "plugin").mkdir(parents=True)

    cc_dir = home / ".claude"
    (cc_dir / "agents").mkdir(parents=True)
    (cc_dir / "skills").mkdir(parents=True)
    (cc_dir / "plugins").mkdir(parents=True)
    (cc_dir / "commands").mkdir(parents=True)

    ws_dir = home / ".codeium" / "windsurf" / "skills"
    ws_dir.mkdir(parents=True)

    return SimpleNamespace(home=home, opencode=oc_dir, claude=cc_dir, windsurf=ws_dir)


@pytest.fixture
def target_manager(fake_home: SimpleNamespace) -> Generator[TargetManager, None, None]:
    """Return a TargetManager backed by fake_home.

    Patches ``Path.home`` and clears ``os.environ`` for the full test
    lifetime so that no code path can accidentally touch the real home
    directory or read stale env vars.
    """
    with (
        mock.patch.object(Path, "home", return_value=fake_home.home),
        mock.patch.dict(os.environ, {}, clear=True),
    ):
        targets = TargetDiscovery().discover_all()
        yield TargetManager(targets)


def _make_dir_item(
    name: str,
    item_type: ItemType = ItemType.SKILL,
    source_dir: Path | None = None,
    platforms: tuple[Platform, ...] = (Platform.OPENCODE, Platform.CLAUDE_CODE),
) -> Item:
    """Create a directory-based Item for testing."""
    src = source_dir or Path(f"/src/{item_type.plural}/{name}")
    return Item(
        item_type=item_type,
        name=name,
        source_path=src,
        files=("SKILL.md",) if item_type == ItemType.SKILL else (),
        supported_platforms=platforms,
    )


def _make_file_item(
    name: str,
    item_type: ItemType = ItemType.AGENT,
    source_path: Path | None = None,
    platforms: tuple[Platform, ...] = (Platform.OPENCODE, Platform.CLAUDE_CODE),
) -> Item:
    """Create a file-based Item for testing."""
    src = source_path or Path(f"/src/{item_type.plural}/{name}.md")
    return Item(
        item_type=item_type,
        name=name,
        source_path=src,
        files=(f"{name}.md",),
        supported_platforms=platforms,
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
            (Platform.OPENCODE,),
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
            (Platform.OPENCODE,),
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
            (Platform.OPENCODE,),
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
            (Platform.OPENCODE,),
            action=SyncAction.UNINSTALL,
        )

        assert len(plans) == 1
        assert plans[0].action == SyncAction.UNINSTALL

    def test_plan_uninstall_not_installed_skipped(self, target_manager: TargetManager) -> None:
        engine = SyncEngine(target_manager)
        item = _make_dir_item("ghost")

        plans = engine.plan_sync(
            [item],
            (Platform.OPENCODE,),
            action=SyncAction.UNINSTALL,
        )

        assert len(plans) == 1
        assert plans[0].action == SyncAction.SKIP

    def test_plan_filters_by_platform(self, target_manager: TargetManager) -> None:
        item = _make_dir_item("multi", platforms=(Platform.OPENCODE, Platform.CLAUDE_CODE))
        engine = SyncEngine(target_manager)

        plans = engine.plan_sync([item], (Platform.OPENCODE,))

        assert len(plans) == 1
        assert plans[0].target_dir is not None

    def test_plan_multiple_platforms(self, target_manager: TargetManager) -> None:
        item = _make_dir_item("multi")
        engine = SyncEngine(target_manager)

        plans = engine.plan_sync(
            [item],
            (Platform.OPENCODE, Platform.CLAUDE_CODE),
        )

        assert len(plans) == 2
        actions = {p.action for p in plans}
        assert actions == {SyncAction.INSTALL}

    def test_plan_skips_missing_target_dir(self, target_manager: TargetManager) -> None:
        """Windsurf does not support commands — plan should skip."""
        item = _make_file_item(
            "my-cmd",
            item_type=ItemType.COMMAND,
            platforms=(Platform.WINDSURF,),
        )
        engine = SyncEngine(target_manager)

        plans = engine.plan_sync([item], (Platform.WINDSURF,))

        assert len(plans) == 0

    def test_plan_multiple_items(self, target_manager: TargetManager) -> None:
        items = [
            _make_dir_item("skill-a"),
            _make_dir_item("skill-b"),
            _make_file_item("agent-a"),
        ]
        engine = SyncEngine(target_manager)

        plans = engine.plan_sync(items, (Platform.OPENCODE,))

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
            supported_platforms=(Platform.OPENCODE,),
        )
        target_dir = target_manager.get_target_dir(Platform.OPENCODE, ItemType.SKILL)
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
        target_dir = target_manager.get_target_dir(Platform.OPENCODE, ItemType.SKILL)
        assert target_dir is not None
        installed = target_dir / "old-skill"
        installed.mkdir()
        (installed / "SKILL.md").write_text("old")

        item = Item(
            item_type=ItemType.SKILL,
            name="old-skill",
            source_path=tmp_path / "src",
            supported_platforms=(Platform.OPENCODE,),
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
            supported_platforms=(Platform.OPENCODE,),
        )
        target_dir = target_manager.get_target_dir(Platform.OPENCODE, ItemType.SKILL)
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

        target_dir = target_manager.get_target_dir(Platform.OPENCODE, ItemType.SKILL)
        assert target_dir is not None

        good_plan = SyncPlan(
            item=Item(
                item_type=ItemType.SKILL,
                name="good-skill",
                source_path=good_src,
                files=("SKILL.md",),
                supported_platforms=(Platform.OPENCODE,),
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
                supported_platforms=(Platform.OPENCODE,),
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

    def test_execute_update_removes_old_first(
        self,
        target_manager: TargetManager,
        tmp_path: Path,
    ) -> None:
        target_dir = target_manager.get_target_dir(Platform.OPENCODE, ItemType.SKILL)
        assert target_dir is not None
        old_dest = target_dir / "update-skill"
        old_dest.mkdir()
        (old_dest / "old.txt").write_text("stale")

        new_src = tmp_path / "new_src"
        new_src.mkdir()
        (new_src / "SKILL.md").write_text("fresh")

        plan = SyncPlan(
            item=Item(
                item_type=ItemType.SKILL,
                name="update-skill",
                source_path=new_src,
                files=("SKILL.md",),
                supported_platforms=(Platform.OPENCODE,),
            ),
            action=SyncAction.UPDATE,
            target_dir=target_dir,
            reason="content differs",
        )


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
            supported_platforms=(Platform.OPENCODE,),
        )
        engine = SyncEngine(target_manager)
        report = engine.sync([item], (Platform.OPENCODE,))

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
            supported_platforms=(Platform.OPENCODE,),
        )
        engine = SyncEngine(target_manager, dry_run=True)
        report = engine.sync([item], (Platform.OPENCODE,))

        assert report.is_success
        # Nothing should be physically installed.
        target_dir = target_manager.get_target_dir(Platform.OPENCODE, ItemType.SKILL)
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
        report = engine.uninstall([item], (Platform.OPENCODE,))

        assert report.is_success
        assert len(report.uninstalled) >= 1
        assert not skill_dir.exists()

    def test_uninstall_nonexistent_reports_skip(
        self,
        target_manager: TargetManager,
    ) -> None:
        item = _make_dir_item("ghost")
        engine = SyncEngine(target_manager)
        report = engine.uninstall([item], (Platform.OPENCODE,))

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
            supported_platforms=(Platform.OPENCODE,),
        )

        source_dir = tmp_path / "source"
        source_dir.mkdir()

        engine = SyncEngine(target_manager)
        report = engine.push(
            [item],
            [Platform.OPENCODE],
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
            supported_platforms=(Platform.OPENCODE,),
        )

        source_dir = tmp_path / "source"
        source_dir.mkdir()

        engine = SyncEngine(target_manager)
        report = engine.push(
            [item],
            [Platform.OPENCODE],
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
            supported_platforms=(Platform.OPENCODE,),
        )

        engine = SyncEngine(target_manager)
        report = engine.push(
            [item],
            [Platform.OPENCODE],
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
            supported_platforms=(Platform.OPENCODE,),
        )

        engine = SyncEngine(target_manager, dry_run=True)
        report = engine.push(
            [item],
            [Platform.OPENCODE],
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
            supported_platforms=(Platform.OPENCODE,),
        )

        source_dir = tmp_path / "source"
        source_dir.mkdir()

        engine = SyncEngine(target_manager)
        report = engine.push(
            [item],
            [Platform.OPENCODE],
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
            supported_platforms=(Platform.OPENCODE,),
        )
        state = SyncState()

        engine = SyncEngine(target_manager)
        plan = engine.compute_sync_plan(
            [item],
            [Platform.OPENCODE],
            state,
            tmp_path / "src",
        )

        assert len(plan) == 1
        assert plan[0][2] == "pull"

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
            supported_platforms=(Platform.OPENCODE,),
        )

        state = SyncState()

        engine = SyncEngine(target_manager)
        plan = engine.compute_sync_plan(
            [item],
            [Platform.OPENCODE],
            state,
            tmp_path / "src",
        )

        assert len(plan) == 1
        assert plan[0][2] == "skip"


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
        assert "back up" in err.lower() or "backup" in err.lower()
        tmp_dest = dest.with_suffix(dest.suffix + ".agentfiles_tmp")
        assert not os.path.lexists(tmp_dest)
        # Original dest must still exist.
        assert dest.exists()
        assert dest.read_text() == "original content"

    def test_rename_failure_restores_backup(self, tmp_path: Path) -> None:
        """If tmp -> dest rename fails, backup is restored to dest."""
        source = tmp_path / "source.txt"
        source.write_text("new content")
        dest = tmp_path / "dest.txt"
        dest.write_text("original content")

        call_count = 0
        original_rename = Path.rename

        def selective_rename(self_path: Path, target: Path) -> Path:
            nonlocal call_count
            call_count += 1
            # Allow dest -> backup rename (first call),
            # fail tmp -> dest rename (second call),
            # allow backup -> dest restore (third call).
            if call_count == 2:
                raise OSError("rename failed")
            return original_rename(self_path, target)

        with mock.patch.object(Path, "rename", selective_rename):
            files_copied, err = SyncEngine._atomic_copy_to(source, dest, use_symlinks=False)

        assert err is not None
        assert "rename failed" in err.lower()
        # Backup must have been restored.
        assert dest.exists()
        assert dest.read_text() == "original content"
        # Backup must be gone (restored).
        backup = dest.with_suffix(dest.suffix + ".bak")
        assert not os.path.lexists(backup)

    def test_rename_and_restore_failure_logs_critical(self, tmp_path: Path) -> None:
        """If both rename and backup restore fail, log CRITICAL."""
        source = tmp_path / "source.txt"
        source.write_text("new content")
        dest = tmp_path / "dest.txt"
        dest.write_text("original content")

        call_count = 0
        original_rename = Path.rename

        def selective_rename(self_path: Path, target: Path) -> Path:
            nonlocal call_count
            call_count += 1
            if call_count >= 2:
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
        assert "stale" in result.message.lower()

    def test_install_fails_when_target_dir_creation_fails(self, tmp_path: Path) -> None:
        """If target directory cannot be created, install should fail."""
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
        assert "denied" in result.message


# ---------------------------------------------------------------------------
# Empty item lists — edge case
# ---------------------------------------------------------------------------


class TestEmptyItemList:
    """All public API methods should handle empty item lists gracefully."""

    def test_plan_sync_empty(self, target_manager: TargetManager) -> None:
        engine = SyncEngine(target_manager)
        plans = engine.plan_sync([], (Platform.OPENCODE,))
        assert plans == []

    def test_execute_plan_empty(self, target_manager: TargetManager) -> None:
        engine = SyncEngine(target_manager)
        results = engine.execute_plan([])
        assert results == []

    def test_sync_empty(self, target_manager: TargetManager) -> None:
        engine = SyncEngine(target_manager)
        report = engine.sync([], (Platform.OPENCODE,))
        assert report.is_success
        assert report.summary() == "No operations performed"

    def test_uninstall_empty(self, target_manager: TargetManager) -> None:
        engine = SyncEngine(target_manager)
        report = engine.uninstall([], (Platform.OPENCODE,))
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
            [Platform.OPENCODE],
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
            [Platform.OPENCODE],
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
            supported_platforms=(Platform.OPENCODE,),
        )

        # -- Item 2: SKIP (up-to-date item) --
        skip_item = Item(
            item_type=ItemType.SKILL,
            name="skip-me",
            source_path=Path("/src/skip-me"),
            supported_platforms=(Platform.OPENCODE,),
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
            supported_platforms=(Platform.OPENCODE,),
        )

        # -- Item 4: UNINSTALL (existing target to remove) --
        uninstall_dest = skill_dir / "remove-skill"
        uninstall_dest.mkdir()
        (uninstall_dest / "SKILL.md").write_text("# Remove Me")
        uninstall_item = Item(
            item_type=ItemType.SKILL,
            name="remove-skill",
            source_path=Path("/src/remove-skill"),
            supported_platforms=(Platform.OPENCODE,),
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
        target_dir = target_manager.get_target_dir(Platform.OPENCODE, ItemType.SKILL)
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
            supported_platforms=(Platform.OPENCODE,),
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
        target_dir = target_manager.get_target_dir(Platform.OPENCODE, ItemType.AGENT)
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
            supported_platforms=(Platform.OPENCODE,),
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
        target_dir = tmp_path / "target"
        target_dir.mkdir()
        item = Item(
            item_type=ItemType.SKILL,
            name="protected",
            source_path=Path("/src/protected"),
            supported_platforms=(Platform.OPENCODE,),
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
        assert "permission denied" in result.message


# ---------------------------------------------------------------------------
# plan_sync with UPDATE action
# ---------------------------------------------------------------------------


class TestPlanSyncUpdateAction:
    """Tests for plan_sync with action=UPDATE."""

    def test_update_action_skips_not_installed(self, target_manager: TargetManager) -> None:
        """Items not yet installed should return no plan when action=UPDATE."""
        item = _make_dir_item("brand-new")
        engine = SyncEngine(target_manager)
        plans = engine.plan_sync(
            [item],
            (Platform.OPENCODE,),
            action=SyncAction.UPDATE,
        )
        # Not installed → _plan_install_or_update returns None for UPDATE.
        assert len(plans) == 0

    def test_update_action_skips_installed(
        self,
        target_manager: TargetManager,
        fake_home: SimpleNamespace,
    ) -> None:
        """Installed items are always SKIP regardless of content."""
        skill_dir = fake_home.opencode / "skill" / "diff-skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("old")

        item = _make_dir_item("diff-skill")
        engine = SyncEngine(target_manager)
        plans = engine.plan_sync(
            [item],
            (Platform.OPENCODE,),
            action=SyncAction.UPDATE,
        )

        assert len(plans) == 1
        assert plans[0].action == SyncAction.SKIP

    def test_update_action_skips_up_to_date(
        self,
        target_manager: TargetManager,
        fake_home: SimpleNamespace,
    ) -> None:
        """Installed items are SKIP — engine only checks existence."""
        skill_dir = fake_home.opencode / "skill" / "same-skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("content")

        item = _make_dir_item("same-skill")
        engine = SyncEngine(target_manager)
        plans = engine.plan_sync(
            [item],
            (Platform.OPENCODE,),
            action=SyncAction.UPDATE,
        )

        assert len(plans) == 1
        assert plans[0].action == SyncAction.SKIP


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
            supported_platforms=(Platform.OPENCODE,),
        )
        item_b = Item(
            item_type=ItemType.AGENT,
            name="agent-b",
            source_path=agent_dir / "agent-b.md",
            supported_platforms=(Platform.OPENCODE,),
        )

        source_dir = tmp_path / "source"
        source_dir.mkdir()

        engine = SyncEngine(target_manager)
        report = engine.push(
            [item_a, item_b],
            [Platform.OPENCODE],
            source_dir=source_dir,
        )

        assert report.is_success
        assert len(report.updated) == 2
        assert (source_dir / "agents" / "agent-a" / "agent-a.md").exists()
        assert (source_dir / "agents" / "agent-b" / "agent-b.md").exists()

    def test_push_unsupported_platform_is_skipped(
        self,
        target_manager: TargetManager,
        tmp_path: Path,
    ) -> None:
        """Push skips items whose supported_platforms don't match the request."""
        item = Item(
            item_type=ItemType.AGENT,
            name="coder",
            source_path=Path("/src/coder.md"),
            supported_platforms=(Platform.OPENCODE,),
        )

        source_dir = tmp_path / "source"
        source_dir.mkdir()

        engine = SyncEngine(target_manager)
        report = engine.push(
            [item],
            [Platform.CLAUDE_CODE],  # item only supports OPENCODE
            source_dir=source_dir,
        )

        assert report.is_success
        assert report.summary() == "No operations performed"

    def test_push_skips_when_target_dir_is_none(
        self,
        target_manager: TargetManager,
        tmp_path: Path,
    ) -> None:
        """Push skips when get_target_dir returns None for a platform/type pair."""
        # COMMAND is not supported by Windsurf (skills-only) — target_dir will be None.
        item = Item(
            item_type=ItemType.COMMAND,
            name="my-cmd",
            source_path=Path("/src/my-cmd.md"),
            supported_platforms=(Platform.WINDSURF,),
        )

        source_dir = tmp_path / "source"
        source_dir.mkdir()

        engine = SyncEngine(target_manager)
        report = engine.push(
            [item],
            [Platform.WINDSURF],
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
            supported_platforms=(Platform.OPENCODE,),
        )

        engine = SyncEngine(mock_target)
        with mock.patch("agentfiles.engine.logger") as mock_logger:
            report = engine.push(
                [item],
                [Platform.OPENCODE],
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
                supported_platforms=(Platform.OPENCODE,),
            )

        engine = SyncEngine(target_manager)
        plans = engine.plan_sync([item], (Platform.OPENCODE,))

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
            supported_platforms=(Platform.OPENCODE,),
        )
        target_dir = target_manager.get_target_dir(Platform.OPENCODE, ItemType.AGENT)
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
            supported_platforms=(Platform.OPENCODE,),
        )
        # Empty state — no platform info at all.
        state = SyncState()

        engine = SyncEngine(target_manager)
        plan = engine.compute_sync_plan(
            [item],
            [Platform.OPENCODE],
            state,
            tmp_path,
        )

        assert len(plan) == 1
        assert plan[0][2] == "pull"

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
            supported_platforms=(Platform.OPENCODE,),
        )
        # Platform exists in state but item does not.
        state = SyncState(
            platforms={
                Platform.OPENCODE.value: PlatformState(path="/tmp"),
            },
        )

        engine = SyncEngine(target_manager)
        plan = engine.compute_sync_plan(
            [item],
            [Platform.OPENCODE],
            state,
            tmp_path,
        )

        assert len(plan) == 1
        assert plan[0][2] == "pull"

    def test_no_target_dir_skips_item(
        self,
        target_manager: TargetManager,
        tmp_path: Path,
    ) -> None:
        """Item whose type has no target dir on a platform is skipped."""
        item = Item(
            item_type=ItemType.COMMAND,
            name="my-cmd",
            source_path=Path("/src/my-cmd.md"),
            supported_platforms=(Platform.WINDSURF,),
        )
        state = SyncState()

        engine = SyncEngine(target_manager)
        plan = engine.compute_sync_plan(
            [item],
            [Platform.WINDSURF],
            state,
            tmp_path,
        )

        assert len(plan) == 1
        assert plan[0][2] == "skip"

    def test_unsupported_platform_filtered_out(
        self,
        target_manager: TargetManager,
        tmp_path: Path,
    ) -> None:
        """Items not supporting the requested platform are excluded."""
        item = Item(
            item_type=ItemType.AGENT,
            name="oc-only",
            source_path=Path("/src/oc-only.md"),
            supported_platforms=(Platform.OPENCODE,),
        )
        state = SyncState()

        engine = SyncEngine(target_manager)
        plan = engine.compute_sync_plan(
            [item],
            [Platform.CLAUDE_CODE],  # item doesn't support Claude Code
            state,
            tmp_path,
        )

        assert len(plan) == 0


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
            supported_platforms=(Platform.OPENCODE,),
        )

        source_dir = tmp_path / "source"
        source_dir.mkdir()

        engine = SyncEngine(target_manager)
        report = engine.sync(
            [item],
            (Platform.OPENCODE,),
            source_dir=source_dir,
        )

        assert report.is_success
        assert len(report.installed) >= 1

        # State file should now exist with sync timestamps.
        state = load_sync_state(source_dir)
        assert state.last_sync != ""

        oc_state = state.platforms.get(Platform.OPENCODE.value)
        assert oc_state is not None

        item_state = oc_state.items.get("skill/my-skill")
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
            supported_platforms=(Platform.OPENCODE,),
        )

        engine = SyncEngine(target_manager)
        report = engine.sync([item], (Platform.OPENCODE,))

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
            supported_platforms=(Platform.OPENCODE,),
        )

        source_dir = tmp_path / "source"
        source_dir.mkdir()

        engine = SyncEngine(target_manager, dry_run=True)
        report = engine.sync(
            [item],
            (Platform.OPENCODE,),
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
            supported_platforms=(Platform.OPENCODE,),
        )

        source_dir = tmp_path / "source"
        source_dir.mkdir()

        engine = SyncEngine(target_manager)

        with mock.patch("agentfiles.engine.save_sync_state", side_effect=OSError("disk full")):
            report = engine.sync(
                [item],
                (Platform.OPENCODE,),
                source_dir=source_dir,
            )

        # Sync itself must succeed even though state save failed.
        assert report.is_success
        assert len(report.installed) >= 1

    def test_sync_state_includes_multiple_platforms(
        self,
        target_manager: TargetManager,
        tmp_path: Path,
    ) -> None:
        """Syncing to multiple platforms records state for each."""
        from agentfiles.config import load_sync_state

        src_dir = tmp_path / "skill_src"
        src_dir.mkdir()
        (src_dir / "SKILL.md").write_text("# Multi")

        item = Item(
            item_type=ItemType.SKILL,
            name="multi-skill",
            source_path=src_dir,
            files=("SKILL.md",),
            supported_platforms=(Platform.OPENCODE, Platform.CLAUDE_CODE),
        )

        source_dir = tmp_path / "source"
        source_dir.mkdir()

        engine = SyncEngine(target_manager)
        report = engine.sync(
            [item],
            (Platform.OPENCODE, Platform.CLAUDE_CODE),
            source_dir=source_dir,
        )

        assert report.is_success

        state = load_sync_state(source_dir)
        oc_state = state.platforms.get(Platform.OPENCODE.value)
        cc_state = state.platforms.get(Platform.CLAUDE_CODE.value)
        assert oc_state is not None
        assert cc_state is not None
        assert "skill/multi-skill" in oc_state.items
        assert "skill/multi-skill" in cc_state.items

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
            supported_platforms=(Platform.OPENCODE,),
        )

        source_dir = tmp_path / "source"
        source_dir.mkdir()

        engine = SyncEngine(target_manager)
        report = engine.sync(
            [item],
            (Platform.OPENCODE,),
            source_dir=source_dir,
        )

        assert report.is_success
        assert len(report.skipped) >= 1

        # Even skipped items should be recorded in state.
        state = load_sync_state(source_dir)
        oc_state = state.platforms.get(Platform.OPENCODE.value)
        assert oc_state is not None
        assert "skill/existing" in oc_state.items

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
            supported_platforms=(Platform.OPENCODE,),
        )

        source_dir = tmp_path / "source"
        source_dir.mkdir()

        # Create a corrupted state file.
        state_file = get_state_path(source_dir)
        state_file.write_text("{{invalid yaml::")

        engine = SyncEngine(target_manager)
        with mock.patch("agentfiles.engine.logger") as mock_logger:
            report = engine.sync(
                [item],
                (Platform.OPENCODE,),
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
            supported_platforms=(Platform.OPENCODE,),
        )
        plan = SyncPlan(
            item=item,
            action=SyncAction.INSTALL,
            target_dir=tmp_path / "target",
            reason="test",
        )

        engine = SyncEngine(target_manager)

        with mock.patch.object(engine, "_execute_single", side_effect=RuntimeError("boom")):
            results = engine.execute_plan([plan])

        assert len(results) == 1
        assert not results[0].is_success
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
            supported_platforms=(Platform.OPENCODE,),
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

        call_count = 0
        original_execute = engine._execute_single

        def selective_crash(plan: SyncPlan) -> SyncResult:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("crash")
            return original_execute(plan)

        with mock.patch.object(engine, "_execute_single", side_effect=selective_crash):
            results = engine.execute_plan([bad_plan, good_plan])

        assert len(results) == 2
        assert not results[0].is_success
        assert "crash" in results[0].message
        assert results[1].is_success
