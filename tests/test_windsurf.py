"""Tests for Windsurf platform support.

Validates that the Windsurf platform (Codeium AI IDE) is correctly integrated
across models, target discovery, scanner, and CLI modules.
"""

from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import pytest

from agentfiles.models import Item, ItemType, Platform
from agentfiles.scanner import _SCANNER_REGISTRY
from agentfiles.target import TargetDiscovery, TargetManager, build_target_manager

# ---------------------------------------------------------------------------
# Platform enum
# ---------------------------------------------------------------------------


class TestWindsurfPlatformEnum:
    """Test Windsurf platform enum value and display name."""

    def test_windsurf_enum_exists(self) -> None:
        """Platform.WINDSURF should be defined."""
        assert hasattr(Platform, "WINDSURF")

    def test_windsurf_enum_value(self) -> None:
        assert Platform.WINDSURF.value == "windsurf"

    def test_windsurf_display_name(self) -> None:
        assert Platform.WINDSURF.display_name == "Windsurf"

    def test_platform_constructable_from_value(self) -> None:
        assert Platform("windsurf") is Platform.WINDSURF


# ---------------------------------------------------------------------------
# Target discovery
# ---------------------------------------------------------------------------


class TestWindsurfTargetDiscovery:
    """Test Windsurf directory discovery."""

    def test_discover_windsurf_global_dir(self, tmp_path: Path) -> None:
        """Discover ~/.codeium/windsurf/skills/ as the Windsurf config dir."""
        fake_home = tmp_path / "home"
        fake_home.mkdir()
        skills_dir = fake_home / ".codeium" / "windsurf" / "skills"
        skills_dir.mkdir(parents=True)

        with (
            mock.patch.object(Path, "home", return_value=fake_home),
            mock.patch.dict(os.environ, {}, clear=True),
        ):
            result = TargetDiscovery().discover(Platform.WINDSURF)

        assert result is not None
        assert result.platform == Platform.WINDSURF
        assert result.is_valid
        assert result.config_dir == skills_dir.resolve()

    def test_discover_windsurf_subdirs_only_skills(self, tmp_path: Path) -> None:
        """Windsurf subdirs should only contain 'skills', not agents/commands/plugins."""
        fake_home = tmp_path / "home"
        fake_home.mkdir()
        skills_dir = fake_home / ".codeium" / "windsurf" / "skills"
        skills_dir.mkdir(parents=True)

        with (
            mock.patch.object(Path, "home", return_value=fake_home),
            mock.patch.dict(os.environ, {}, clear=True),
        ):
            result = TargetDiscovery().discover(Platform.WINDSURF)

        assert result is not None
        assert "skills" in result.subdirs
        assert "agents" not in result.subdirs
        assert "commands" not in result.subdirs
        assert "plugins" not in result.subdirs

    def test_discover_windsurf_not_found(self, tmp_path: Path) -> None:
        """Discovery returns None when no Windsurf directories exist."""
        fake_home = tmp_path / "empty_home"
        fake_home.mkdir()

        with (
            mock.patch.object(Path, "home", return_value=fake_home),
            mock.patch.dict(os.environ, {}, clear=True),
        ):
            result = TargetDiscovery().discover(Platform.WINDSURF)

        assert result is None

    def test_discover_windsurf_legacy_path(self, tmp_path: Path) -> None:
        """Fallback to ~/.windsurf when the primary path is absent."""
        fake_home = tmp_path / "home"
        fake_home.mkdir()
        legacy_dir = fake_home / ".windsurf"
        legacy_dir.mkdir(parents=True)

        with (
            mock.patch.object(Path, "home", return_value=fake_home),
            mock.patch.dict(os.environ, {}, clear=True),
        ):
            result = TargetDiscovery().discover(Platform.WINDSURF)

        assert result is not None
        assert result.config_dir == legacy_dir.resolve()

    def test_discover_all_includes_windsurf(self, tmp_path: Path) -> None:
        """discover_all() picks up Windsurf alongside OpenCode and Claude Code."""
        fake_home = tmp_path / "home"
        fake_home.mkdir()

        # OpenCode
        oc_dir = fake_home / ".config" / "opencode"
        (oc_dir / "agent").mkdir(parents=True)

        # Claude Code
        cc_dir = fake_home / ".claude"
        (cc_dir / "agents").mkdir(parents=True)

        # Windsurf
        ws_dir = fake_home / ".codeium" / "windsurf" / "skills"
        ws_dir.mkdir(parents=True)

        with (
            mock.patch.object(Path, "home", return_value=fake_home),
            mock.patch.object(Path, "cwd", return_value=tmp_path),
            mock.patch.dict(os.environ, {}, clear=True),
        ):
            targets = TargetDiscovery().discover_all()

        assert Platform.WINDSURF in targets
        assert Platform.OPENCODE in targets
        assert Platform.CLAUDE_CODE in targets
        assert len(targets) == 3


# ---------------------------------------------------------------------------
# Scanner platform mapping
# ---------------------------------------------------------------------------


class TestWindsurfScannerMapping:
    """Test that Windsurf appears in the right scanner platform mapping."""

    def test_skill_supports_windsurf(self) -> None:
        assert Platform.WINDSURF in _SCANNER_REGISTRY[ItemType.SKILL].platforms

    def test_agent_does_not_support_windsurf(self) -> None:
        assert Platform.WINDSURF not in _SCANNER_REGISTRY[ItemType.AGENT].platforms

    def test_command_does_not_support_windsurf(self) -> None:
        assert Platform.WINDSURF not in _SCANNER_REGISTRY[ItemType.COMMAND].platforms

    def test_plugin_does_not_support_windsurf(self) -> None:
        assert Platform.WINDSURF not in _SCANNER_REGISTRY[ItemType.PLUGIN].platforms


# ---------------------------------------------------------------------------
# TargetManager with Windsurf
# ---------------------------------------------------------------------------


class TestWindsurfTargetManager:
    """Test TargetManager operations with the Windsurf platform."""

    @pytest.fixture
    def _windsurf_env(self, tmp_path: Path) -> SimpleNamespace:
        """Create a fake home with all three platforms."""
        home = tmp_path / "home"
        home.mkdir()

        # OpenCode
        oc_dir = home / ".config" / "opencode"
        (oc_dir / "agent").mkdir(parents=True)
        (oc_dir / "skill").mkdir(parents=True)

        # Claude Code
        cc_dir = home / ".claude"
        (cc_dir / "agents").mkdir(parents=True)
        (cc_dir / "skills").mkdir(parents=True)

        # Windsurf
        ws_dir = home / ".codeium" / "windsurf" / "skills"
        ws_dir.mkdir(parents=True)

        return SimpleNamespace(home=home, opencode=oc_dir, claude=cc_dir, windsurf=ws_dir)

    def test_get_target_dir_skill_for_windsurf(
        self, _windsurf_env: SimpleNamespace, tmp_path: Path
    ) -> None:
        """TargetManager resolves the skills directory for Windsurf."""
        with (
            mock.patch.object(Path, "home", return_value=_windsurf_env.home),
            mock.patch.object(Path, "cwd", return_value=tmp_path),
            mock.patch.dict(os.environ, {}, clear=True),
        ):
            targets = TargetDiscovery().discover_all()

        manager = TargetManager(targets)
        result = manager.get_target_dir(Platform.WINDSURF, ItemType.SKILL)

        assert result is not None
        assert result == _windsurf_env.windsurf

    def test_get_target_dir_agent_returns_none_for_windsurf(
        self, _windsurf_env: SimpleNamespace, tmp_path: Path
    ) -> None:
        """Windsurf has no agents subdirectory, so get_target_dir returns None."""
        with (
            mock.patch.object(Path, "home", return_value=_windsurf_env.home),
            mock.patch.object(Path, "cwd", return_value=tmp_path),
            mock.patch.dict(os.environ, {}, clear=True),
        ):
            targets = TargetDiscovery().discover_all()

        manager = TargetManager(targets)
        result = manager.get_target_dir(Platform.WINDSURF, ItemType.AGENT)

        assert result is None

    def test_windsurf_installed_skill_items(
        self, _windsurf_env: SimpleNamespace, tmp_path: Path
    ) -> None:
        """Installed items scan picks up skills from the Windsurf directory."""
        skill_dir = _windsurf_env.windsurf
        (skill_dir / "python-reviewer").mkdir()

        with (
            mock.patch.object(Path, "home", return_value=_windsurf_env.home),
            mock.patch.object(Path, "cwd", return_value=tmp_path),
            mock.patch.dict(os.environ, {}, clear=True),
        ):
            targets = TargetDiscovery().discover_all()

        manager = TargetManager(targets)
        items = manager.get_installed_items(Platform.WINDSURF)

        assert len(items) == 1
        assert items[0] == (ItemType.SKILL, "python-reviewer")

    def test_is_item_installed_on_windsurf(
        self, _windsurf_env: SimpleNamespace, tmp_path: Path
    ) -> None:
        """Check installation status of a skill on Windsurf."""
        skill_dir = _windsurf_env.windsurf
        (skill_dir / "my-skill").mkdir()

        with (
            mock.patch.object(Path, "home", return_value=_windsurf_env.home),
            mock.patch.object(Path, "cwd", return_value=tmp_path),
            mock.patch.dict(os.environ, {}, clear=True),
        ):
            targets = TargetDiscovery().discover_all()

        manager = TargetManager(targets)
        item = Item(
            item_type=ItemType.SKILL,
            name="my-skill",
            source_path=Path("/src/my-skill"),
            supported_platforms=(Platform.OPENCODE, Platform.CLAUDE_CODE, Platform.WINDSURF),
        )

        assert manager.is_item_installed(item, Platform.WINDSURF) is True

    def test_is_item_not_installed_on_windsurf(
        self, _windsurf_env: SimpleNamespace, tmp_path: Path
    ) -> None:
        """Missing skill should report as not installed."""
        with (
            mock.patch.object(Path, "home", return_value=_windsurf_env.home),
            mock.patch.object(Path, "cwd", return_value=tmp_path),
            mock.patch.dict(os.environ, {}, clear=True),
        ):
            targets = TargetDiscovery().discover_all()

        manager = TargetManager(targets)
        item = Item(
            item_type=ItemType.SKILL,
            name="missing-skill",
            source_path=Path("/src/missing-skill"),
            supported_platforms=(Platform.WINDSURF,),
        )

        assert manager.is_item_installed(item, Platform.WINDSURF) is False

    def test_windsurf_platform_summary(
        self, _windsurf_env: SimpleNamespace, tmp_path: Path
    ) -> None:
        """platform_summary includes Windsurf skill counts."""
        skill_dir = _windsurf_env.windsurf
        (skill_dir / "ws-skill-1").mkdir()
        (skill_dir / "ws-skill-2").mkdir()

        with (
            mock.patch.object(Path, "home", return_value=_windsurf_env.home),
            mock.patch.object(Path, "cwd", return_value=tmp_path),
            mock.patch.dict(os.environ, {}, clear=True),
        ):
            targets = TargetDiscovery().discover_all()

        manager = TargetManager(targets)
        summary = manager.platform_summary()

        assert Platform.WINDSURF in summary
        assert summary[Platform.WINDSURF] == {"skills": 2}

    def test_windsurf_primary_path_preferred_over_legacy(self, tmp_path: Path) -> None:
        """When both paths exist, primary ~/.codeium/windsurf/skills wins."""
        fake_home = tmp_path / "home"
        fake_home.mkdir()

        primary = fake_home / ".codeium" / "windsurf" / "skills"
        primary.mkdir(parents=True)

        legacy = fake_home / ".windsurf"
        legacy.mkdir(parents=True)

        with (
            mock.patch.object(Path, "home", return_value=fake_home),
            mock.patch.dict(os.environ, {}, clear=True),
        ):
            result = TargetDiscovery().discover(Platform.WINDSURF)

        assert result is not None
        assert result.config_dir == primary.resolve()


# ---------------------------------------------------------------------------
# Custom path override for Windsurf
# ---------------------------------------------------------------------------


class TestWindsurfCustomPath:
    """Test build_target_manager with Windsurf custom paths."""

    def test_custom_path_overrides_windsurf(self, tmp_path: Path) -> None:
        """Custom path for Windsurf overrides the auto-discovered directory."""
        fake_home = tmp_path / "home"
        fake_home.mkdir()

        # Auto-discovered path.
        auto_dir = fake_home / ".codeium" / "windsurf" / "skills"
        auto_dir.mkdir(parents=True)

        # Custom path.
        custom_dir = tmp_path / "custom_windsurf_skills"
        custom_dir.mkdir()

        with (
            mock.patch.object(Path, "home", return_value=fake_home),
            mock.patch.dict(os.environ, {}, clear=True),
        ):
            manager = build_target_manager(
                custom_paths={"windsurf": str(custom_dir)},
            )

        assert Platform.WINDSURF in manager.targets
        assert manager.targets[Platform.WINDSURF].config_dir == custom_dir.resolve()
