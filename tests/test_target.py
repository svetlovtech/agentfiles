"""Tests for agentfiles.target — platform discovery and management."""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import pytest

from agentfiles.models import Item, ItemType, Platform, Scope, TargetError, TargetPaths
from agentfiles.target import (
    TargetDiscovery,
    TargetManager,
    _opencode_project_candidates,
    build_target_manager,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def fake_home(tmp_path: Path) -> SimpleNamespace:
    """Create a fake home directory with platform configs."""
    home = tmp_path / "home"
    home.mkdir()

    # OpenCode layout (singular dir names).
    oc_dir = home / ".config" / "opencode"
    (oc_dir / "agent").mkdir(parents=True)
    (oc_dir / "skill").mkdir(parents=True)
    (oc_dir / "command").mkdir(parents=True)
    (oc_dir / "plugin").mkdir(parents=True)

    return SimpleNamespace(home=home, opencode=oc_dir)


# ---------------------------------------------------------------------------
# TargetDiscovery — discover
# ---------------------------------------------------------------------------


class TestTargetDiscoveryDiscover:
    """Tests for the discover methods."""

    def test_discover_opencode_finds_xdg(self, fake_home: SimpleNamespace) -> None:
        with (
            mock.patch.object(Path, "home", return_value=fake_home.home),
            mock.patch.dict(os.environ, {}, clear=True),
        ):
            result = TargetDiscovery().discover()

        assert result is not None
        assert result.platform == Platform.OPENCODE
        assert result.is_valid
        assert result.config_dir == fake_home.opencode.resolve()

    def test_discover_returns_none_when_missing(self, tmp_path: Path) -> None:
        with (
            mock.patch.object(Path, "home", return_value=tmp_path / "nonexistent"),
            mock.patch.dict(os.environ, {}, clear=True),
        ):
            result = TargetDiscovery().discover()

        assert result is None

    def test_discover_all_returns_discovered_platforms(self, fake_home: SimpleNamespace) -> None:
        with (
            mock.patch.object(Path, "home", return_value=fake_home.home),
            mock.patch.object(Path, "cwd", return_value=fake_home.home / "project"),
            mock.patch.dict(os.environ, {}, clear=True),
        ):
            targets = TargetDiscovery().discover_all()

        assert targets is not None
        assert targets.platform == Platform.OPENCODE

    def test_discover_all_skips_missing(self, tmp_path: Path) -> None:
        with (
            mock.patch.object(Path, "home", return_value=tmp_path / "empty"),
            mock.patch.object(Path, "cwd", return_value=tmp_path / "empty" / "project"),
            mock.patch.dict(os.environ, {}, clear=True),
        ):
            targets = TargetDiscovery().discover_all()

        assert targets is None

    def test_discover_xdg_config_home_preferred(self, fake_home: SimpleNamespace) -> None:
        xdg_dir = fake_home.home / "xdg" / "opencode"
        xdg_dir.mkdir(parents=True)

        with (
            mock.patch.object(Path, "home", return_value=fake_home.home),
            mock.patch.dict(
                os.environ,
                {"XDG_CONFIG_HOME": str(fake_home.home / "xdg")},
                clear=True,
            ),
        ):
            result = TargetDiscovery().discover()

        assert result is not None
        assert result.config_dir == xdg_dir.resolve()

    def test_discover_macos_fallback(self, fake_home: SimpleNamespace) -> None:
        macos_dir = fake_home.home / "Library" / "Application Support" / "opencode"
        macos_dir.mkdir(parents=True)

        with (
            mock.patch.object(Path, "home", return_value=fake_home.home),
            mock.patch.dict(os.environ, {}, clear=True),
            mock.patch("sys.platform", "darwin"),
        ):
            linux_dir = fake_home.home / ".config" / "opencode"
            if linux_dir.exists():
                shutil.rmtree(linux_dir, ignore_errors=True)
            result = TargetDiscovery().discover()

        assert result is not None
        assert result.config_dir == macos_dir.resolve()


# ---------------------------------------------------------------------------
# Subdirectory resolution
# ---------------------------------------------------------------------------


class TestSubdirectoryResolution:
    """Tests for platform-specific subdirectory layouts."""

    def test_opencode_subdirs_are_singular(self, fake_home: SimpleNamespace) -> None:
        with (
            mock.patch.object(Path, "home", return_value=fake_home.home),
            mock.patch.dict(os.environ, {}, clear=True),
        ):
            result = TargetDiscovery().discover()

        assert result is not None
        assert result.subdirs["agents"] == fake_home.opencode / "agent"
        assert result.subdirs["skills"] == fake_home.opencode / "skill"
        assert result.subdirs["commands"] == fake_home.opencode / "command"
        assert result.subdirs["plugins"] == fake_home.opencode / "plugin"

    def test_opencode_subdir_for_returns_existing(self, fake_home: SimpleNamespace) -> None:
        with (
            mock.patch.object(Path, "home", return_value=fake_home.home),
            mock.patch.dict(os.environ, {}, clear=True),
        ):
            result = TargetDiscovery().discover()

        assert result is not None
        path = result.subdir_for(ItemType.AGENT)
        assert path == fake_home.opencode / "agent"


# ---------------------------------------------------------------------------
# TargetManager
# ---------------------------------------------------------------------------


def _make_item(
    item_type: ItemType,
    name: str,
) -> Item:
    """Create a minimal Item for testing."""
    ext = ".md" if item_type.is_file_based else ""
    return Item(
        item_type=item_type,
        name=name,
        source_path=Path("/src") / f"{name}{ext}",
            )


class TestTargetManager:
    """Tests for the TargetManager class."""

    def test_get_target_dir_returns_path(self, fake_home: SimpleNamespace) -> None:
        with (
            mock.patch.object(Path, "home", return_value=fake_home.home),
            mock.patch.dict(os.environ, {}, clear=True),
        ):
            targets = TargetDiscovery().discover_all()

        manager = TargetManager(targets)
        result = manager.get_target_dir(ItemType.AGENT)

        assert result is not None
        assert result == fake_home.opencode / "agent"

    def test_get_target_dir_raises_for_missing_platform(self) -> None:
        manager = TargetManager(None)

        with pytest.raises(TargetError, match="OpenCode has not been discovered"):
            manager.get_target_dir(ItemType.AGENT)

    def test_is_item_installed_true(self, fake_home: SimpleNamespace) -> None:
        (fake_home.opencode / "agent" / "python-reviewer.md").write_text("# agent")

        with (
            mock.patch.object(Path, "home", return_value=fake_home.home),
            mock.patch.dict(os.environ, {}, clear=True),
        ):
            targets = TargetDiscovery().discover_all()

        manager = TargetManager(targets)
        item = _make_item(ItemType.AGENT, "python-reviewer")

        assert manager.is_item_installed(item) is True

    def test_is_item_installed_false(self, fake_home: SimpleNamespace) -> None:
        with (
            mock.patch.object(Path, "home", return_value=fake_home.home),
            mock.patch.dict(os.environ, {}, clear=True),
        ):
            targets = TargetDiscovery().discover_all()

        manager = TargetManager(targets)
        item = _make_item(ItemType.AGENT, "nonexistent")

        assert manager.is_item_installed(item) is False

    def test_is_item_installed_false_for_missing_platform(self) -> None:
        manager = TargetManager(None)
        item = _make_item(ItemType.AGENT, "anything")

        assert manager.is_item_installed(item) is False

    def test_get_installed_items(self, fake_home: SimpleNamespace) -> None:
        (fake_home.opencode / "agent" / "reviewer.md").write_text("# agent")
        (fake_home.opencode / "agent" / "orchestrator.md").write_text("# agent")
        (fake_home.opencode / "skill" / "python-stylist").mkdir()

        with (
            mock.patch.object(Path, "home", return_value=fake_home.home),
            mock.patch.dict(os.environ, {}, clear=True),
        ):
            targets = TargetDiscovery().discover_all()

        manager = TargetManager(targets)
        items = manager.get_installed_items()

        types_and_names = [(t, n) for t, n in items]
        assert (ItemType.AGENT, "orchestrator") in types_and_names
        assert (ItemType.AGENT, "reviewer") in types_and_names
        assert (ItemType.SKILL, "python-stylist") in types_and_names

    def test_get_installed_items_raises_for_missing_platform(self) -> None:
        manager = TargetManager(None)

        with pytest.raises(TargetError, match="OpenCode has not been discovered"):
            manager.get_installed_items()

    def test_get_installed_items_skips_hidden(self, fake_home: SimpleNamespace) -> None:
        (fake_home.opencode / "agent" / "visible.md").write_text("# agent")
        (fake_home.opencode / "agent" / ".hidden.md").write_text("# agent")

        with (
            mock.patch.object(Path, "home", return_value=fake_home.home),
            mock.patch.dict(os.environ, {}, clear=True),
        ):
            targets = TargetDiscovery().discover_all()

        manager = TargetManager(targets)
        items = manager.get_installed_items()

        names = [n for _, n in items]
        assert "visible" in names
        assert ".hidden" not in names

    def test_platform_summary(self, fake_home: SimpleNamespace) -> None:
        (fake_home.opencode / "agent" / "a1.md").write_text("# agent")
        (fake_home.opencode / "agent" / "a2.md").write_text("# agent")
        (fake_home.opencode / "skill" / "s1").mkdir()

        with (
            mock.patch.object(Path, "home", return_value=fake_home.home),
            mock.patch.dict(os.environ, {}, clear=True),
        ):
            targets = TargetDiscovery().discover_all()

        manager = TargetManager(targets)
        summary = manager.platform_summary()

        assert summary["agents"] == 2
        assert summary["skills"] == 1

    def test_platform_summary_empty(self) -> None:
        manager = TargetManager(None)
        assert manager.platform_summary() == {}


# ---------------------------------------------------------------------------
# build_target_manager
# ---------------------------------------------------------------------------


class TestBuildTargetManager:
    """Tests for the build_target_manager convenience factory."""

    def test_discovers_platforms(self, fake_home: SimpleNamespace) -> None:
        """Discovers platforms just like TargetDiscovery.discover_all."""
        with (
            mock.patch.object(Path, "home", return_value=fake_home.home),
            mock.patch.dict(os.environ, {}, clear=True),
        ):
            manager = build_target_manager()

        assert manager.targets is not None
        assert manager.targets.platform == Platform.OPENCODE

    def test_applies_custom_paths(self, fake_home: SimpleNamespace) -> None:
        """Custom paths override discovered platform directories."""
        custom_dir = fake_home.home / "custom_oc"
        custom_dir.mkdir()

        with (
            mock.patch.object(Path, "home", return_value=fake_home.home),
            mock.patch.dict(os.environ, {}, clear=True),
        ):
            manager = build_target_manager(
                custom_paths={"opencode": str(custom_dir)},
            )

        assert manager.targets is not None
        assert manager.targets.config_dir == custom_dir.resolve()

    def test_skips_unknown_platform_in_custom_paths(
        self,
        fake_home: SimpleNamespace,
    ) -> None:
        """Unknown platform names in custom_paths are silently skipped."""
        with (
            mock.patch.object(Path, "home", return_value=fake_home.home),
            mock.patch.dict(os.environ, {}, clear=True),
        ):
            manager = build_target_manager(
                custom_paths={"unknown_platform": "/tmp/whatever"},
            )

        # Auto-discovered opencode should still be present
        assert manager.targets is not None
        assert manager.targets.platform == Platform.OPENCODE

    def test_skips_nonexistent_custom_path(
        self,
        fake_home: SimpleNamespace,
    ) -> None:
        """Non-existent custom paths are silently skipped."""
        with (
            mock.patch.object(Path, "home", return_value=fake_home.home),
            mock.patch.dict(os.environ, {}, clear=True),
        ):
            manager = build_target_manager(
                custom_paths={"opencode": "/nonexistent/path"},
            )

        # Should still have the auto-discovered path
        assert manager.targets is not None
        assert manager.targets.config_dir == fake_home.opencode.resolve()

    def test_returns_empty_manager_when_no_platforms(self, tmp_path: Path) -> None:
        """Returns a manager with no targets when nothing is found."""
        with (
            mock.patch.object(Path, "home", return_value=tmp_path / "empty"),
            mock.patch.object(Path, "cwd", return_value=tmp_path / "empty" / "project"),
            mock.patch.dict(os.environ, {}, clear=True),
        ):
            manager = build_target_manager()

        assert manager.targets is None

    def test_none_custom_paths_same_as_empty(
        self,
        fake_home: SimpleNamespace,
    ) -> None:
        """Passing None for custom_paths behaves like an empty mapping."""
        with (
            mock.patch.object(Path, "home", return_value=fake_home.home),
            mock.patch.dict(os.environ, {}, clear=True),
        ):
            manager_default = build_target_manager()
            manager_none = build_target_manager(custom_paths=None)

        assert manager_default.targets is not None
        assert manager_none.targets is not None
        assert manager_default.targets.config_dir == manager_none.targets.config_dir


# ---------------------------------------------------------------------------
# Error handling — permission / OS errors
# ---------------------------------------------------------------------------


class TestPermissionErrorHandling:
    """Verify graceful degradation on permission and OS errors."""

    def test_find_existing_skips_permission_denied(
        self,
        fake_home: SimpleNamespace,
    ) -> None:
        """_find_existing skips candidates that raise PermissionError."""
        from agentfiles.target import _find_existing

        inaccessible = fake_home.home / ".config" / "opencode"
        # Make is_dir raise PermissionError on the first call.
        with mock.patch.object(
            Path,
            "is_dir",
            side_effect=PermissionError("denied"),
        ):
            result = _find_existing([inaccessible])

        assert result is None

    def test_find_existing_skips_oserror(self, fake_home: SimpleNamespace) -> None:
        """_find_existing skips candidates that raise OSError."""
        from agentfiles.target import _find_existing

        inaccessible = fake_home.home / ".config" / "opencode"
        with mock.patch.object(
            Path,
            "is_dir",
            side_effect=OSError("broken symlink"),
        ):
            result = _find_existing([inaccessible])

        assert result is None

    def test_find_existing_returns_valid_after_error(
        self,
        fake_home: SimpleNamespace,
    ) -> None:
        """_find_existing continues past errors and returns a valid candidate."""
        from agentfiles.target import _find_existing

        bad_dir = fake_home.home / "bad"
        good_dir = fake_home.opencode

        original_is_dir = Path.is_dir
        call_count = 0

        def _flaky_is_dir(self: Path) -> bool:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise PermissionError("nope")
            return original_is_dir(self)

        with mock.patch.object(Path, "is_dir", _flaky_is_dir):
            result = _find_existing([bad_dir, good_dir])

        assert result is not None

    def test_discover_returns_none_on_candidate_scan_error(
        self,
        fake_home: SimpleNamespace,
    ) -> None:
        """discover() returns None when candidate scanning fails unexpectedly."""
        with (
            mock.patch.object(Path, "home", return_value=fake_home.home),
            mock.patch.dict(os.environ, {}, clear=True),
            mock.patch(
                "agentfiles.target._find_existing",
                side_effect=RuntimeError("surprise"),
            ),
        ):
            result = TargetDiscovery().discover()

        assert result is None

    def test_discover_returns_empty_subdirs_on_resolve_error(
        self,
        fake_home: SimpleNamespace,
    ) -> None:
        """discover() returns TargetPaths with empty subdirs when resolution fails."""
        with (
            mock.patch.object(Path, "home", return_value=fake_home.home),
            mock.patch.dict(os.environ, {}, clear=True),
            mock.patch(
                "agentfiles.target._opencode_subdirs",
                side_effect=RuntimeError("boom"),
            ),
        ):
            result = TargetDiscovery().discover()

        assert result is not None
        assert result.subdirs == {}

    def test_is_item_installed_returns_false_on_permission_error(
        self,
        fake_home: SimpleNamespace,
    ) -> None:
        """is_item_installed returns False (never raises) on PermissionError."""
        with (
            mock.patch.object(Path, "home", return_value=fake_home.home),
            mock.patch.dict(os.environ, {}, clear=True),
        ):
            targets = TargetDiscovery().discover_all()

        manager = TargetManager(targets)
        item = _make_item(ItemType.AGENT, "test-agent")

        with mock.patch.object(
            Path,
            "exists",
            side_effect=PermissionError("denied"),
        ):
            assert manager.is_item_installed(item) is False

    def test_is_item_installed_returns_false_on_oserror(
        self,
        fake_home: SimpleNamespace,
    ) -> None:
        """is_item_installed returns False on OSError."""
        with (
            mock.patch.object(Path, "home", return_value=fake_home.home),
            mock.patch.dict(os.environ, {}, clear=True),
        ):
            targets = TargetDiscovery().discover_all()

        manager = TargetManager(targets)
        item = _make_item(ItemType.AGENT, "test-agent")

        with mock.patch.object(
            Path,
            "exists",
            side_effect=OSError("stale handle"),
        ):
            assert manager.is_item_installed(item) is False

    def test_get_installed_items_skips_unreadable_subdir(
        self,
        fake_home: SimpleNamespace,
    ) -> None:
        """get_installed_items skips subdirs that raise PermissionError on iterdir."""
        (fake_home.opencode / "agent" / "visible-agent.md").write_text("# agent")

        with (
            mock.patch.object(Path, "home", return_value=fake_home.home),
            mock.patch.dict(os.environ, {}, clear=True),
        ):
            targets = TargetDiscovery().discover_all()

        manager = TargetManager(targets)

        original_is_dir = Path.is_dir

        def _patched_is_dir(self: Path) -> bool:
            # The skill subdir raises PermissionError on is_dir
            if self.name == "skill":
                raise PermissionError("denied")
            return original_is_dir(self)

        with mock.patch.object(Path, "is_dir", _patched_is_dir):
            items = manager.get_installed_items()

        # Only the agent entry is returned; skill is skipped.
        names = [n for _, n in items]
        assert "visible-agent" in names

    def test_get_installed_items_skips_iterdir_error(
        self,
        fake_home: SimpleNamespace,
    ) -> None:
        """get_installed_items skips subdirs that raise OSError on iterdir."""
        (fake_home.opencode / "agent" / "a1.md").write_text("# agent")

        with (
            mock.patch.object(Path, "home", return_value=fake_home.home),
            mock.patch.dict(os.environ, {}, clear=True),
        ):
            targets = TargetDiscovery().discover_all()

        manager = TargetManager(targets)

        # Patch iterdir on the agents subdir to raise OSError.
        agent_dir = fake_home.opencode / "agent"
        original_iterdir = Path.iterdir

        def _patched_iterdir(self: Path) -> object:
            if self == agent_dir:
                raise OSError("io error")
            return original_iterdir(self)

        with mock.patch.object(Path, "iterdir", _patched_iterdir):
            items = manager.get_installed_items()

        # agents subdir failed, so only items from other subdirs (if any)
        # are returned.  No crash.
        assert isinstance(items, list)

    def test_get_installed_items_skips_entry_stat_error(
        self,
        fake_home: SimpleNamespace,
    ) -> None:
        """get_installed_items skips entries that raise OSError on is_file."""
        (fake_home.opencode / "agent" / "good-agent.md").write_text("# agent")
        (fake_home.opencode / "agent" / "broken-agent.md").write_text("# agent")

        with (
            mock.patch.object(Path, "home", return_value=fake_home.home),
            mock.patch.dict(os.environ, {}, clear=True),
        ):
            targets = TargetDiscovery().discover_all()

        manager = TargetManager(targets)

        original_is_file = Path.is_file

        def _patched_is_file(self: Path) -> bool:
            if self.name == "broken-agent.md":
                raise OSError("stale NFS handle")
            return original_is_file(self)

        with mock.patch.object(Path, "is_file", _patched_is_file):
            items = manager.get_installed_items()

        names = [n for _, n in items]
        assert "good-agent" in names
        assert "broken-agent" not in names

    def test_build_target_manager_skips_custom_path_realpath_error(
        self,
        fake_home: SimpleNamespace,
    ) -> None:
        """build_target_manager skips custom paths when realpath fails."""
        custom_dir = fake_home.home / "custom_oc"
        custom_dir.mkdir()

        original_realpath = os.path.realpath

        def _selective_realpath(path: str | os.PathLike[str]) -> str:
            path_str = os.fspath(path)
            if "custom_oc" in path_str:
                raise OSError("broken mount")
            return original_realpath(path)

        with (
            mock.patch.object(Path, "home", return_value=fake_home.home),
            mock.patch.dict(os.environ, {}, clear=True),
            mock.patch("os.path.realpath", side_effect=_selective_realpath),
        ):
            manager = build_target_manager(
                custom_paths={"opencode": str(custom_dir)},
            )

        # Custom path was skipped, but auto-discovered path should remain.
        assert manager.targets is not None
        assert manager.targets.config_dir == fake_home.opencode.resolve()


# ---------------------------------------------------------------------------
# Custom path handling — expanded coverage
# ---------------------------------------------------------------------------


class TestCustomPathHandling:
    """Tests for custom path overrides in build_target_manager."""

    def test_custom_path_with_tilde_expansion(
        self,
        fake_home: SimpleNamespace,
    ) -> None:
        """Custom paths using ~ should be expanded via expanduser."""
        custom_dir = fake_home.home / "my_custom_opencode"
        custom_dir.mkdir()

        original_expanduser = Path.expanduser

        def _fake_expanduser(self: Path) -> Path:
            """Map ~/... to fake_home/... for testing."""
            s = str(self)
            if s.startswith("~/"):
                return fake_home.home / s[2:]
            return original_expanduser(self)

        with (
            mock.patch.object(Path, "home", return_value=fake_home.home),
            mock.patch.object(Path, "expanduser", _fake_expanduser),
            mock.patch.dict(os.environ, {}, clear=True),
        ):
            manager = build_target_manager(
                custom_paths={"opencode": "~/my_custom_opencode"},
            )

        assert manager.targets is not None
        assert manager.targets.config_dir == custom_dir.resolve()

    def test_custom_path_for_undiscovered_platform(self, tmp_path: Path) -> None:
        """Custom path can enable a platform that was not auto-discovered."""
        empty_home = tmp_path / "empty"
        empty_home.mkdir()

        # Create the custom dir outside of the home so nothing is auto-discovered.
        custom_oc = tmp_path / "manual_opencode"
        custom_oc.mkdir()

        with (
            mock.patch.object(Path, "home", return_value=empty_home),
            mock.patch.dict(os.environ, {}, clear=True),
        ):
            manager = build_target_manager(
                custom_paths={"opencode": str(custom_oc)},
            )

        assert manager.targets is not None
        assert manager.targets.config_dir == custom_oc.resolve()

    def test_custom_path_file_not_directory(
        self,
        fake_home: SimpleNamespace,
    ) -> None:
        """Custom paths pointing to a file (not a directory) are skipped."""
        file_path = fake_home.home / "not_a_dir"
        file_path.write_text("I am a file")

        with (
            mock.patch.object(Path, "home", return_value=fake_home.home),
            mock.patch.dict(os.environ, {}, clear=True),
        ):
            manager = build_target_manager(
                custom_paths={"opencode": str(file_path)},
            )

        # Should fall back to auto-discovered path.
        assert manager.targets is not None
        assert manager.targets.config_dir == fake_home.opencode.resolve()


# ---------------------------------------------------------------------------
# Platform subdir resolvers — direct unit tests
# ---------------------------------------------------------------------------


class TestPlatformSubdirResolvers:
    """Direct unit tests for the platform-specific subdir resolver functions."""

    def test_opencode_subdirs_maps_all_item_types(self) -> None:
        """OpenCode subdirs covers agents, skills, commands, and plugins."""
        from agentfiles.target import _opencode_subdirs

        config_dir = Path("/fake/opencode")
        subdirs = _opencode_subdirs(config_dir)

        assert subdirs == {
            "agents": config_dir / "agent",
            "skills": config_dir / "skill",
            "commands": config_dir / "command",
            "plugins": config_dir / "plugin",
            "workflows": config_dir / "workflow",
        }


# ---------------------------------------------------------------------------
# Installed items scanning — edge cases
# ---------------------------------------------------------------------------


class TestInstalledItemsEdgeCases:
    """Edge-case tests for get_installed_items and is_item_installed."""

    def test_file_based_item_uses_stem(self, fake_home: SimpleNamespace) -> None:
        """File-based items (agents) report stem without extension."""
        agent_dir = fake_home.opencode / "agent"
        (agent_dir / "my-agent.md").write_text("# agent")

        with (
            mock.patch.object(Path, "home", return_value=fake_home.home),
            mock.patch.dict(os.environ, {}, clear=True),
        ):
            targets = TargetDiscovery().discover_all()

        manager = TargetManager(targets)
        items = manager.get_installed_items()

        names = [n for t, n in items if t == ItemType.AGENT]
        assert "my-agent" in names

    def test_empty_subdir_yields_no_items(self, fake_home: SimpleNamespace) -> None:
        """An empty subdirectory contributes no items."""
        # agent dir exists but is empty.
        with (
            mock.patch.object(Path, "home", return_value=fake_home.home),
            mock.patch.dict(os.environ, {}, clear=True),
        ):
            targets = TargetDiscovery().discover_all()

        manager = TargetManager(targets)
        items = manager.get_installed_items()

        assert items == []

    def test_nonexistent_subdir_path_skipped(self, fake_home: SimpleNamespace) -> None:
        """Subdirectory paths that don't exist on disk are skipped."""
        # Only create the opencode config_dir, no subdirs inside.
        bare_oc = fake_home.home / "bare_opencode"
        bare_oc.mkdir()

        targets = TargetPaths(
            platform=Platform.OPENCODE,
            config_dir=bare_oc,
            subdirs={
                "agents": bare_oc / "agent",  # does not exist
            },
        )
        manager = TargetManager(targets)
        items = manager.get_installed_items()

        assert items == []

    def test_is_item_installed_with_no_subdir_mapping(self) -> None:
        """is_item_installed returns False when item type has no subdirectory."""
        from agentfiles.models import TargetPaths

        targets = TargetPaths(
            platform=Platform.OPENCODE,
            config_dir=Path("/fake"),
            subdirs={"skills": Path("/fake/skill")},
        )
        manager = TargetManager(targets)
        item = _make_item(ItemType.AGENT, "test")

        # No "agents" in subdirs, so get_target_dir returns None.
        assert manager.is_item_installed(item) is False

    def test_mixed_files_and_dirs_in_subdir(
        self,
        fake_home: SimpleNamespace,
    ) -> None:
        """get_installed_items only picks up files for file-based types."""
        agent_dir = fake_home.opencode / "agent"
        # A file-based agent — should be discovered.
        (agent_dir / "file-agent.md").write_text("# file agent")
        # A directory-based agent — should NOT be discovered (agents are file-based).
        (agent_dir / "dir-agent").mkdir()

        with (
            mock.patch.object(Path, "home", return_value=fake_home.home),
            mock.patch.dict(os.environ, {}, clear=True),
        ):
            targets = TargetDiscovery().discover_all()

        manager = TargetManager(targets)
        items = manager.get_installed_items()

        names = [n for t, n in items if t == ItemType.AGENT]
        assert "file-agent" in names
        assert "dir-agent" not in names


# ---------------------------------------------------------------------------
# _find_existing and _get_candidates — edge cases
# ---------------------------------------------------------------------------


class TestFindExistingEdgeCases:
    """Edge-case tests for _find_existing and candidate resolution."""

    def test_find_existing_empty_candidates(self) -> None:
        """_find_existing returns None when candidates list is empty."""
        from agentfiles.target import _find_existing

        result = _find_existing([])
        assert result is None

    def test_is_dir_oserror_on_subdir_is_dir_check(
        self,
        fake_home: SimpleNamespace,
    ) -> None:
        """get_installed_items skips subdirs where is_dir() raises OSError."""
        (fake_home.opencode / "agent" / "a1.md").write_text("# agent")

        with (
            mock.patch.object(Path, "home", return_value=fake_home.home),
            mock.patch.dict(os.environ, {}, clear=True),
        ):
            targets = TargetDiscovery().discover_all()

        manager = TargetManager(targets)

        original_is_dir = Path.is_dir

        def _flaky_is_dir(self: Path) -> bool:
            if self.name == "skill":
                raise OSError("I/O error")
            return original_is_dir(self)

        with mock.patch.object(Path, "is_dir", _flaky_is_dir):
            items = manager.get_installed_items()

        names = [n for _, n in items]
        assert "a1" in names

    def test_item_type_from_plural_unknown_key(self) -> None:
        """_item_type_from_plural returns None for unrecognised keys."""
        result = TargetManager._item_type_from_plural("unknown_type")
        assert result is None


# ---------------------------------------------------------------------------
# Project candidate resolvers
# ---------------------------------------------------------------------------


class TestProjectCandidateResolvers:
    """Direct unit tests for project-level candidate resolver functions."""

    def test_opencode_project_candidates(self) -> None:
        """OpenCode project candidate points to <project>/.opencode."""
        project_dir = Path("/my/project")
        candidates = _opencode_project_candidates(project_dir)
        assert candidates == [project_dir / ".opencode"]


# ---------------------------------------------------------------------------
# TargetManager — get_target_dir_for_scope
# ---------------------------------------------------------------------------


class TestGetTargetDirForScope:
    """Tests for the get_target_dir_for_scope method."""

    def test_global_scope_uses_discovered_targets(
        self,
        fake_home: SimpleNamespace,
    ) -> None:
        """GLOBAL scope delegates to existing get_target_dir."""
        with (
            mock.patch.object(Path, "home", return_value=fake_home.home),
            mock.patch.dict(os.environ, {}, clear=True),
        ):
            targets = TargetDiscovery().discover_all()

        manager = TargetManager(targets)
        result = manager.get_target_dir_for_scope(ItemType.AGENT,
            Scope.GLOBAL,
        )

        assert result is not None
        assert result == fake_home.opencode / "agent"

    def test_global_scope_raises_for_missing_platform(self) -> None:
        """GLOBAL scope raises TargetError when platform not discovered."""
        manager = TargetManager(None)

        with pytest.raises(TargetError, match="OpenCode has not been discovered"):
            manager.get_target_dir_for_scope(ItemType.AGENT,
                Scope.GLOBAL,
            )

    def test_project_scope_resolves_path(self, tmp_path: Path) -> None:
        """PROJECT scope resolves path relative to project_dir."""
        project_dir = tmp_path / "myproject"
        manager = TargetManager(None)  # No global targets is fine.

        result = manager.get_target_dir_for_scope(ItemType.AGENT,
            Scope.PROJECT,
            project_dir=project_dir,
        )

        assert result == project_dir / ".opencode" / "agent"

    def test_local_scope_resolves_same_path_as_project(
        self,
        tmp_path: Path,
    ) -> None:
        """LOCAL scope resolves the same filesystem path as PROJECT."""
        project_dir = tmp_path / "myproject"
        manager = TargetManager(None)

        project_result = manager.get_target_dir_for_scope(ItemType.SKILL,
            Scope.PROJECT,
            project_dir=project_dir,
        )
        local_result = manager.get_target_dir_for_scope(ItemType.SKILL,
            Scope.LOCAL,
            project_dir=project_dir,
        )

        assert project_result == project_dir / ".opencode" / "skill"
        assert local_result == project_result

    def test_project_scope_does_not_require_existing_dir(
        self,
        tmp_path: Path,
    ) -> None:
        """PROJECT scope returns a path even when the dir doesn't exist."""
        project_dir = tmp_path / "nonexistent_project"
        # Don't create any directories.
        manager = TargetManager(None)

        result = manager.get_target_dir_for_scope(ItemType.SKILL,
            Scope.PROJECT,
            project_dir=project_dir,
        )

        assert result is not None
        assert result == project_dir / ".opencode" / "skill"

    def test_project_scope_returns_none_without_project_dir(self) -> None:
        """PROJECT scope returns None when project_dir is not provided."""
        manager = TargetManager(None)

        result = manager.get_target_dir_for_scope(ItemType.SKILL,
            Scope.PROJECT,
            project_dir=None,
        )

        assert result is None

    def test_project_scope_config_type_returns_config_dir(
        self,
        tmp_path: Path,
    ) -> None:
        """PROJECT scope returns config_dir root for CONFIG item type."""
        project_dir = tmp_path / "myproject"
        manager = TargetManager(None)

        result = manager.get_target_dir_for_scope(ItemType.CONFIG,
            Scope.PROJECT,
            project_dir=project_dir,
        )

        assert result == project_dir / ".opencode"

    def test_project_scope_opencode_resolves(
        self,
        tmp_path: Path,
    ) -> None:
        """PROJECT scope resolves correctly for OpenCode."""
        project_dir = tmp_path / "project"
        manager = TargetManager(None)

        assert (
            manager.get_target_dir_for_scope(ItemType.AGENT, Scope.PROJECT, project_dir=project_dir
            )
            == project_dir / ".opencode" / "agent"
        )
        assert (
            manager.get_target_dir_for_scope(ItemType.SKILL, Scope.PROJECT, project_dir=project_dir
            )
            == project_dir / ".opencode" / "skill"
        )
