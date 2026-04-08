"""Tests for Cursor platform support."""

from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import pytest

from agentfiles.models import Item, ItemType, Platform
from agentfiles.target import TargetDiscovery, TargetManager, build_target_manager

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def fake_home_with_cursor(tmp_path: Path) -> SimpleNamespace:
    """Create a fake home directory with Cursor skills directory."""
    home = tmp_path / "home"
    home.mkdir()

    # Cursor layout — skills only.
    cursor_dir = home / ".cursor" / "skills"
    cursor_dir.mkdir(parents=True)

    return SimpleNamespace(home=home, cursor_skills=cursor_dir)


# ---------------------------------------------------------------------------
# Platform enum
# ---------------------------------------------------------------------------


class TestCursorPlatformEnum:
    """Test Cursor platform enum value and display name."""

    def test_cursor_enum_exists(self) -> None:
        """Platform must expose a CURSOR member."""
        assert hasattr(Platform, "CURSOR")

    def test_cursor_enum_value(self) -> None:
        """CURSOR enum value must be the string 'cursor'."""
        assert Platform.CURSOR.value == "cursor"

    def test_cursor_display_name(self) -> None:
        """display_name must return 'Cursor'."""
        assert Platform.CURSOR.display_name == "Cursor"


# ---------------------------------------------------------------------------
# TargetDiscovery — Cursor
# ---------------------------------------------------------------------------


class TestCursorDiscovery:
    """Tests for Cursor platform discovery."""

    def test_discover_cursor_finds_global_dir(
        self,
        fake_home_with_cursor: SimpleNamespace,
    ) -> None:
        """Test that Cursor discovers ~/.cursor/skills/."""
        with (
            mock.patch.object(Path, "home", return_value=fake_home_with_cursor.home),
            mock.patch.dict(os.environ, {}, clear=True),
        ):
            result = TargetDiscovery().discover(Platform.CURSOR)

        assert result is not None
        assert result.platform == Platform.CURSOR
        assert result.is_valid

    def test_discover_cursor_not_found(self, tmp_path: Path) -> None:
        """Test that discovery returns None when Cursor dir doesn't exist."""
        empty_home = tmp_path / "empty"
        empty_home.mkdir()

        with (
            mock.patch.object(Path, "home", return_value=empty_home),
            mock.patch.dict(os.environ, {}, clear=True),
        ):
            result = TargetDiscovery().discover(Platform.CURSOR)

        assert result is None

    def test_discover_cursor_subdirs_only_skills(
        self,
        fake_home_with_cursor: SimpleNamespace,
    ) -> None:
        """Cursor subdirs must only contain 'skills'."""
        with (
            mock.patch.object(Path, "home", return_value=fake_home_with_cursor.home),
            mock.patch.dict(os.environ, {}, clear=True),
        ):
            result = TargetDiscovery().discover(Platform.CURSOR)

        assert result is not None
        assert set(result.subdirs.keys()) == {"skills", "workflows"}

    def test_discover_all_includes_cursor(
        self,
        fake_home_with_cursor: SimpleNamespace,
        tmp_path: Path,
    ) -> None:
        """discover_all must include Cursor when the directory exists."""
        with (
            mock.patch.object(Path, "home", return_value=fake_home_with_cursor.home),
            mock.patch.object(Path, "cwd", return_value=tmp_path),
            mock.patch.dict(os.environ, {}, clear=True),
        ):
            targets = TargetDiscovery().discover_all()

        assert Platform.CURSOR in targets


# ---------------------------------------------------------------------------
# TargetManager — Cursor
# ---------------------------------------------------------------------------


class TestCursorTargetManager:
    """Tests for Cursor platform via TargetManager."""

    def test_get_target_dir_skills(
        self,
        fake_home_with_cursor: SimpleNamespace,
        tmp_path: Path,
    ) -> None:
        """Cursor target dir for skills should resolve."""
        with (
            mock.patch.object(Path, "home", return_value=fake_home_with_cursor.home),
            mock.patch.object(Path, "cwd", return_value=tmp_path),
            mock.patch.dict(os.environ, {}, clear=True),
        ):
            targets = TargetDiscovery().discover_all()

        manager = TargetManager(targets)
        skills_dir = manager.get_target_dir(Platform.CURSOR, ItemType.SKILL)

        assert skills_dir is not None

    def test_get_target_dir_returns_none_for_agents(
        self,
        fake_home_with_cursor: SimpleNamespace,
        tmp_path: Path,
    ) -> None:
        """Cursor does not support agents — should return None."""
        with (
            mock.patch.object(Path, "home", return_value=fake_home_with_cursor.home),
            mock.patch.object(Path, "cwd", return_value=tmp_path),
            mock.patch.dict(os.environ, {}, clear=True),
        ):
            targets = TargetDiscovery().discover_all()

        manager = TargetManager(targets)
        agents_dir = manager.get_target_dir(Platform.CURSOR, ItemType.AGENT)

        # Cursor subdirs only has 'skills', so agents should be None.
        assert agents_dir is None

    def test_get_installed_items_cursor(
        self,
        fake_home_with_cursor: SimpleNamespace,
        tmp_path: Path,
    ) -> None:
        """Installed items from Cursor show skills."""
        # Create a skill directory.
        (fake_home_with_cursor.cursor_skills / "my-skill").mkdir()

        with (
            mock.patch.object(Path, "home", return_value=fake_home_with_cursor.home),
            mock.patch.object(Path, "cwd", return_value=tmp_path),
            mock.patch.dict(os.environ, {}, clear=True),
        ):
            targets = TargetDiscovery().discover_all()

        manager = TargetManager(targets)
        items = manager.get_installed_items(Platform.CURSOR)

        assert len(items) == 1
        assert items[0] == (ItemType.SKILL, "my-skill")

    def test_get_installed_items_empty_skills(
        self,
        fake_home_with_cursor: SimpleNamespace,
        tmp_path: Path,
    ) -> None:
        """Empty skills directory should produce no installed items."""
        with (
            mock.patch.object(Path, "home", return_value=fake_home_with_cursor.home),
            mock.patch.object(Path, "cwd", return_value=tmp_path),
            mock.patch.dict(os.environ, {}, clear=True),
        ):
            targets = TargetDiscovery().discover_all()

        manager = TargetManager(targets)
        items = manager.get_installed_items(Platform.CURSOR)

        assert items == []

    def test_get_installed_items_skips_hidden(
        self,
        fake_home_with_cursor: SimpleNamespace,
        tmp_path: Path,
    ) -> None:
        """Hidden entries in the Cursor skills directory are skipped."""
        skill_dir = fake_home_with_cursor.cursor_skills
        (skill_dir / "visible-skill").mkdir()
        (skill_dir / ".hidden-skill").mkdir()

        with (
            mock.patch.object(Path, "home", return_value=fake_home_with_cursor.home),
            mock.patch.object(Path, "cwd", return_value=tmp_path),
            mock.patch.dict(os.environ, {}, clear=True),
        ):
            targets = TargetDiscovery().discover_all()

        manager = TargetManager(targets)
        items = manager.get_installed_items(Platform.CURSOR)

        names = [n for _, n in items]
        assert "visible-skill" in names
        assert ".hidden-skill" not in names

    def test_is_item_installed_true(
        self,
        fake_home_with_cursor: SimpleNamespace,
        tmp_path: Path,
    ) -> None:
        """is_item_installed returns True when a skill exists."""
        skill_dir = fake_home_with_cursor.cursor_skills
        (skill_dir / "existing-skill").mkdir()

        with (
            mock.patch.object(Path, "home", return_value=fake_home_with_cursor.home),
            mock.patch.object(Path, "cwd", return_value=tmp_path),
            mock.patch.dict(os.environ, {}, clear=True),
        ):
            targets = TargetDiscovery().discover_all()

        manager = TargetManager(targets)
        item = Item(
            item_type=ItemType.SKILL,
            name="existing-skill",
            source_path=Path("/src/existing-skill"),
            supported_platforms=(Platform.CURSOR,),
        )

        assert manager.is_item_installed(item, Platform.CURSOR) is True

    def test_is_item_installed_false(
        self,
        fake_home_with_cursor: SimpleNamespace,
        tmp_path: Path,
    ) -> None:
        """is_item_installed returns False when skill is missing."""
        with (
            mock.patch.object(Path, "home", return_value=fake_home_with_cursor.home),
            mock.patch.object(Path, "cwd", return_value=tmp_path),
            mock.patch.dict(os.environ, {}, clear=True),
        ):
            targets = TargetDiscovery().discover_all()

        manager = TargetManager(targets)
        item = Item(
            item_type=ItemType.SKILL,
            name="missing-skill",
            source_path=Path("/src/missing-skill"),
            supported_platforms=(Platform.CURSOR,),
        )

        assert manager.is_item_installed(item, Platform.CURSOR) is False

    def test_platform_summary_cursor(
        self,
        fake_home_with_cursor: SimpleNamespace,
        tmp_path: Path,
    ) -> None:
        """platform_summary includes Cursor skill counts."""
        skill_dir = fake_home_with_cursor.cursor_skills
        (skill_dir / "cr-skill-1").mkdir()
        (skill_dir / "cr-skill-2").mkdir()

        with (
            mock.patch.object(Path, "home", return_value=fake_home_with_cursor.home),
            mock.patch.object(Path, "cwd", return_value=tmp_path),
            mock.patch.dict(os.environ, {}, clear=True),
        ):
            targets = TargetDiscovery().discover_all()

        manager = TargetManager(targets)
        summary = manager.platform_summary()

        assert Platform.CURSOR in summary
        assert summary[Platform.CURSOR] == {"skills": 2}

    def test_cursor_only_platform_discovered(
        self,
        tmp_path: Path,
    ) -> None:
        """discover_all finds Cursor even when no other platforms exist."""
        home = tmp_path / "home"
        home.mkdir()

        cursor_dir = home / ".cursor" / "skills"
        cursor_dir.mkdir(parents=True)

        with (
            mock.patch.object(Path, "home", return_value=home),
            mock.patch.object(Path, "cwd", return_value=tmp_path),
            mock.patch.dict(os.environ, {}, clear=True),
        ):
            targets = TargetDiscovery().discover_all()

        assert Platform.CURSOR in targets
        assert len(targets) == 1


# ---------------------------------------------------------------------------
# Custom path override for Cursor
# ---------------------------------------------------------------------------


class TestCursorCustomPath:
    """Test build_target_manager with Cursor custom paths."""

    def test_custom_path_overrides_cursor(self, tmp_path: Path) -> None:
        """Custom path for Cursor overrides the auto-discovered directory."""
        fake_home = tmp_path / "home"
        fake_home.mkdir()

        auto_dir = fake_home / ".cursor" / "skills"
        auto_dir.mkdir(parents=True)

        custom_dir = tmp_path / "custom_cursor_skills"
        custom_dir.mkdir()

        with (
            mock.patch.object(Path, "home", return_value=fake_home),
            mock.patch.dict(os.environ, {}, clear=True),
        ):
            manager = build_target_manager(
                custom_paths={"cursor": str(custom_dir)},
            )

        assert Platform.CURSOR in manager.targets
        assert manager.targets[Platform.CURSOR].config_dir == custom_dir.resolve()
