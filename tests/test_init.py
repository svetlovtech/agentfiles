"""Tests for agentfiles.cli — commands, helpers, and edge cases."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from agentfiles.cli import (
    _create_init_structure,
    _discover_installed_from_targets,
    _filter_items,
    _filter_items_by_installed,
    _format_list_json,
    _format_list_text,
    _print_token_summary,
    _resolve_item_types,
    build_parser,
    cmd_init,
)
from agentfiles.models import (
    AgentfilesError,
    Item,
    ItemType,
    TARGET_PLATFORM,
    TargetPaths,
    TokenEstimate,
)
from agentfiles.target import TargetManager

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_args(
    path: str = ".",
    non_interactive: bool = True,
) -> argparse.Namespace:
    """Build a minimal argparse.Namespace for cmd_init."""
    return argparse.Namespace(
        path=path,
        non_interactive=non_interactive,
    )


def _make_item(
    name: str = "test-item",
    item_type: ItemType = ItemType.AGENT,
    version: str = "1.0.0",
    files: tuple[str, ...] = ("test-item.md",),
    source_path: Path | None = None,
) -> Item:
    """Create a minimal Item for testing."""
    return Item(
        item_type=item_type,
        name=name,
        source_path=source_path or Path(f"/fake/{item_type.value}/{name}"),
        version=version,
        files=files,
    )


# ---------------------------------------------------------------------------
# cmd_init — Basic directory creation
# ---------------------------------------------------------------------------


class TestInitDirectories:
    """Tests for directory structure creation."""

    def test_creates_all_subdirs(self, tmp_path: Path) -> None:
        args = _make_args(str(tmp_path / "myrepo"))
        cmd_init(args)

        base = tmp_path / "myrepo"
        for subdir in ["agents", "skills", "commands", "plugins"]:
            assert (base / subdir).is_dir()
            assert (base / subdir / ".gitkeep").is_file()

    def test_creates_agentfiles_yaml(self, tmp_path: Path) -> None:
        args = _make_args(str(tmp_path / "myrepo"))
        cmd_init(args)

        config = tmp_path / "myrepo" / ".agentfiles.yaml"
        assert config.is_file()
        content = config.read_text()
        assert "default_platforms:" in content
        assert "opencode" in content

    def test_creates_state_yaml(self, tmp_path: Path) -> None:
        args = _make_args(str(tmp_path))
        cmd_init(args)
        state = tmp_path / ".agentfiles.state.yaml"
        assert state.is_file()
        content = state.read_text()
        assert "auto-generated" in content.lower() or "version" in content

    def test_creates_base_dir_if_not_exists(self, tmp_path: Path) -> None:
        new_dir = tmp_path / "nested" / "deep" / "repo"
        assert not new_dir.exists()

        args = _make_args(str(new_dir))
        cmd_init(args)

        assert new_dir.is_dir()
        assert (new_dir / "agents").is_dir()

    def test_uses_current_dir_when_path_omitted(self, tmp_path: Path) -> None:
        args = _make_args(str(tmp_path))
        cmd_init(args)

        assert (tmp_path / "agents").is_dir()
        assert (tmp_path / ".agentfiles.yaml").is_file()


# ---------------------------------------------------------------------------
# cmd_init — Idempotency / skip existing
# ---------------------------------------------------------------------------


class TestInitIdempotent:
    """Tests for handling already-existing directories and files."""

    def test_skips_existing_subdirs(self, tmp_path: Path) -> None:
        (tmp_path / "agents").mkdir()
        (tmp_path / "agents" / "existing.md").write_text("keep me")

        args = _make_args(str(tmp_path))
        cmd_init(args)

        # Existing file should be preserved
        assert (tmp_path / "agents" / "existing.md").read_text() == "keep me"
        # .gitkeep should NOT be created in existing dir
        assert not (tmp_path / "agents" / ".gitkeep").exists()
        # Other dirs should still be created
        assert (tmp_path / "skills").is_dir()
        assert (tmp_path / "skills" / ".gitkeep").is_file()

    def test_does_not_overwrite_agentfiles_yaml(self, tmp_path: Path) -> None:
        config = tmp_path / ".agentfiles.yaml"
        config.write_text("custom: true\n")

        args = _make_args(str(tmp_path))
        cmd_init(args)

        assert config.read_text() == "custom: true\n"

    def test_returns_zero_on_success(self, tmp_path: Path) -> None:
        args = _make_args(str(tmp_path))
        result = cmd_init(args)
        assert result == 0

    def test_returns_zero_when_already_initialized(self, tmp_path: Path) -> None:
        for subdir in ["agents", "skills", "commands", "plugins"]:
            (tmp_path / subdir).mkdir()
        (tmp_path / ".agentfiles.yaml").write_text("custom: true\n")

        args = _make_args(str(tmp_path))
        result = cmd_init(args)
        assert result == 0


# ---------------------------------------------------------------------------
# cmd_init — Interactive confirmation
# ---------------------------------------------------------------------------


class TestInitInteractive:
    """Tests for the interactive confirmation prompt."""

    def test_aborts_when_user_declines(self, tmp_path: Path) -> None:
        args = _make_args(str(tmp_path), non_interactive=False)

        with patch("builtins.input", return_value="n"):
            result = cmd_init(args)

        assert result == 0
        assert not (tmp_path / "agents").exists()

    def test_proceeds_when_user_confirms(self, tmp_path: Path) -> None:
        args = _make_args(str(tmp_path), non_interactive=False)

        with patch("builtins.input", return_value="y"):
            result = cmd_init(args)

        assert result == 0
        assert (tmp_path / "agents").is_dir()
        assert (tmp_path / ".agentfiles.yaml").is_file()

    def test_yes_flag_skips_confirmation(self, tmp_path: Path) -> None:
        args = _make_args(str(tmp_path), non_interactive=True)
        # Should not prompt at all
        result = cmd_init(args)
        assert result == 0
        assert (tmp_path / "agents").is_dir()


# ---------------------------------------------------------------------------
# cmd_init — Config file content
# ---------------------------------------------------------------------------


class TestInitConfigContent:
    """Tests for the .agentfiles.yaml file content."""

    def test_config_has_yaml_header_comment(self, tmp_path: Path) -> None:
        args = _make_args(str(tmp_path))
        cmd_init(args)

        content = (tmp_path / ".agentfiles.yaml").read_text()
        assert content.startswith("# agentfiles configuration")

    def test_does_not_overwrite_state_yaml(self, tmp_path: Path) -> None:
        """State file should be preserved when it already exists."""
        state = tmp_path / ".agentfiles.state.yaml"
        state.write_text("custom_state: true\n")

        args = _make_args(str(tmp_path))
        cmd_init(args)

        assert state.read_text() == "custom_state: true\n"


# ---------------------------------------------------------------------------
# cmd_init — Error paths
# ---------------------------------------------------------------------------


class TestInitErrorPaths:
    """Tests for error handling in cmd_init."""

    def test_raises_on_permission_denied_for_mkdir(self, tmp_path: Path) -> None:
        """AgentfilesError raised when base directory cannot be created."""
        args = _make_args(str(tmp_path))
        with (
            patch("pathlib.Path.mkdir", side_effect=OSError("Permission denied")),
            pytest.raises(AgentfilesError, match="Failed to create directory"),
        ):
            cmd_init(args)

    def test_raises_on_permission_denied_for_config_write(self, tmp_path: Path) -> None:
        """AgentfilesError raised when config file cannot be written."""
        args = _make_args(str(tmp_path))
        with (
            patch("pathlib.Path.write_text", side_effect=OSError("Read-only")),
            pytest.raises(AgentfilesError),
        ):
            cmd_init(args)


# ---------------------------------------------------------------------------
# _create_init_structure — direct tests
# ---------------------------------------------------------------------------


class TestCreateInitStructure:
    """Tests for the _create_init_structure helper."""

    def test_creates_all_item_type_dirs(self, tmp_path: Path) -> None:
        created, skipped = _create_init_structure(tmp_path)
        expected_names = {it.plural for it in ItemType}
        assert set(created) == expected_names
        assert skipped == []
        for name in expected_names:
            assert (tmp_path / name).is_dir()
            assert (tmp_path / name / ".gitkeep").is_file()

    def test_skips_existing_dirs(self, tmp_path: Path) -> None:
        (tmp_path / "agents").mkdir()
        (tmp_path / "skills").mkdir()

        created, skipped = _create_init_structure(tmp_path)

        assert "agents" in skipped
        assert "skills" in skipped
        assert "commands" in created
        assert "plugins" in created

    def test_raises_on_oserror(self, tmp_path: Path) -> None:
        with (
            patch("pathlib.Path.mkdir", side_effect=OSError("disk full")),
            pytest.raises(AgentfilesError, match="Failed to create directory"),
        ):
            _create_init_structure(tmp_path)

    def test_all_dirs_created_with_parents(self, tmp_path: Path) -> None:
        """Ensures parent directories are created automatically."""
        base = tmp_path / "new" / "nested"
        created, _ = _create_init_structure(base)
        assert len(created) == len(ItemType)
        assert base.is_dir()


# ---------------------------------------------------------------------------
# _resolve_item_types
# ---------------------------------------------------------------------------


class TestResolveItemTypes:
    """Tests for _resolve_item_types helper."""

    @pytest.mark.parametrize("flag", ["all", None])
    def test_all_or_none_returns_all_types(self, flag: str | None) -> None:
        result = _resolve_item_types(flag)
        assert set(result) == set(ItemType)

    def test_valid_type_returns_single(self) -> None:
        result = _resolve_item_types("agent")
        assert result == [ItemType.AGENT]

    @pytest.mark.parametrize("flag", ["skill", "command", "plugin"])
    def test_each_valid_type(self, flag: str) -> None:
        result = _resolve_item_types(flag)
        assert len(result) == 1
        assert result[0].value == flag

    def test_unknown_type_returns_all_with_warning(self) -> None:
        """Unknown type falls back to all item types."""
        result = _resolve_item_types("nonexistent")
        assert set(result) == set(ItemType)


# ---------------------------------------------------------------------------
# _filter_items
# ---------------------------------------------------------------------------


class TestFilterItems:
    """Tests for _filter_items helper."""

    def test_filters_by_single_type(self) -> None:
        items = [
            _make_item("agent-1", ItemType.AGENT),
            _make_item("skill-1", ItemType.SKILL),
            _make_item("command-1", ItemType.COMMAND),
        ]
        result = _filter_items(items, [ItemType.AGENT])
        assert len(result) == 1
        assert result[0].name == "agent-1"

    def test_filters_by_multiple_types(self) -> None:
        items = [
            _make_item("agent-1", ItemType.AGENT),
            _make_item("skill-1", ItemType.SKILL),
            _make_item("command-1", ItemType.COMMAND),
        ]
        result = _filter_items(items, [ItemType.AGENT, ItemType.COMMAND])
        assert len(result) == 2
        assert {i.name for i in result} == {"agent-1", "command-1"}

    def test_empty_items_returns_empty(self) -> None:
        result = _filter_items([], [ItemType.AGENT])
        assert result == []

    def test_no_matching_type_returns_empty(self) -> None:
        items = [_make_item("agent-1", ItemType.AGENT)]
        result = _filter_items(items, [ItemType.PLUGIN])
        assert result == []

    def test_all_types_returns_everything(self) -> None:
        items = [_make_item(f"item-{t.value}", t) for t in ItemType]
        result = _filter_items(items, list(ItemType))
        assert len(result) == len(ItemType)


# ---------------------------------------------------------------------------
# _filter_items_by_installed
# ---------------------------------------------------------------------------


class TestFilterItemsByInstalled:
    """Tests for _filter_items_by_installed helper."""

    def _make_mock_target_manager(
        self,
        installed_map: dict[str, bool] | None = None,
    ) -> MagicMock:
        """Create a mock target_manager with configurable is_item_installed."""
        manager = MagicMock()
        installed_map = installed_map or {}

        def is_installed(item: Any) -> bool:
            return installed_map.get(item.name, False)

        manager.is_item_installed.side_effect = is_installed
        return manager

    def test_returns_only_installed_items(self) -> None:
        items = [_make_item("installed"), _make_item("not-installed")]
        tm = self._make_mock_target_manager(
            {"installed": True, "not-installed": False},
        )
        result = _filter_items_by_installed(
            items,
            tm,
            [],
            installed=True,
        )
        assert len(result) == 1
        assert result[0].name == "installed"

    def test_returns_only_not_installed_items(self) -> None:
        items = [_make_item("installed"), _make_item("not-installed")]
        tm = self._make_mock_target_manager(
            {"installed": True, "not-installed": False},
        )
        result = _filter_items_by_installed(
            items,
            tm,
            [],
            installed=False,
        )
        assert len(result) == 1
        assert result[0].name == "not-installed"

    def test_empty_items_returns_empty(self) -> None:
        tm = self._make_mock_target_manager()
        result = _filter_items_by_installed([], tm, [], installed=True)
        assert result == []

    def test_all_installed_returns_all_when_filter_installed(self) -> None:
        items = [_make_item("a"), _make_item("b")]
        tm = self._make_mock_target_manager({"a": True, "b": True})
        result = _filter_items_by_installed(
            items,
            tm,
            [],
            installed=True,
        )
        assert len(result) == 2


# ---------------------------------------------------------------------------
# _format_list_json
# ---------------------------------------------------------------------------


class TestFormatListJson:
    """Tests for _format_list_json helper."""

    def test_outputs_valid_json(self, capsys: pytest.CaptureFixture[str]) -> None:
        items = [_make_item("my-agent")]
        result = _format_list_json(items, show_tokens=False)
        captured = capsys.readouterr()
        assert result == 0
        output = json.loads(captured.out)
        assert "items" in output
        assert len(output["items"]) == 1
        assert output["items"][0]["name"] == "my-agent"
        assert output["items"][0]["type"] == "agent"

    def test_json_includes_expected_fields(self, capsys: pytest.CaptureFixture[str]) -> None:
        items = [_make_item("my-skill", ItemType.SKILL, version="2.0.0")]
        _format_list_json(items, show_tokens=False)
        output = json.loads(capsys.readouterr().out)
        entry = output["items"][0]
        assert "name" in entry
        assert "type" in entry
        assert "version" in entry
        assert "files" in entry
        assert entry["version"] == "2.0.0"

    def test_json_without_tokens_has_no_estimate(self, capsys: pytest.CaptureFixture[str]) -> None:
        items = [_make_item()]
        _format_list_json(items, show_tokens=False)
        output = json.loads(capsys.readouterr().out)
        assert "token_estimate" not in output["items"][0]

    def test_json_with_tokens_includes_estimate(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Token estimation requires real files; mock token_estimate."""
        items = [_make_item()]
        estimate = TokenEstimate(
            name="test-item",
            item_type=ItemType.AGENT,
            files=("test-item.md",),
            source_size_bytes=100,
            content_tokens=50,
            overhead_tokens=10,
            total_tokens=60,
        )
        with (
            patch("agentfiles.tokens.token_estimate", return_value=estimate),
            patch("agentfiles.tokens.estimate_name_description_tokens", return_value=15),
        ):
            _format_list_json(items, show_tokens=True)
        output = json.loads(capsys.readouterr().out)
        assert "token_estimate" in output["items"][0]
        assert output["items"][0]["token_estimate"]["total_tokens"] == 60
        assert output["items"][0]["token_estimate"]["name_desc_tokens"] == 15

    def test_json_with_tokens_excludes_non_agent_skill(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Token estimates are only computed for agents and skills."""
        items = [_make_item("my-cmd", ItemType.COMMAND)]
        estimate = TokenEstimate(
            name="my-cmd",
            item_type=ItemType.COMMAND,
            files=("my-cmd.md",),
            source_size_bytes=50,
            content_tokens=25,
            overhead_tokens=5,
            total_tokens=30,
        )
        with patch("agentfiles.tokens.token_estimate", return_value=estimate):
            _format_list_json(items, show_tokens=True)
        output = json.loads(capsys.readouterr().out)
        assert "token_estimate" not in output["items"][0]

    def test_json_token_summary_aggregate(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Token summary aggregates across agents and skills."""
        items = [
            _make_item("a1", ItemType.AGENT),
            _make_item("s1", ItemType.SKILL),
        ]
        est_agent = TokenEstimate("a1", ItemType.AGENT, (), 100, 50, 10, 60)
        est_skill = TokenEstimate("s1", ItemType.SKILL, (), 200, 80, 20, 100)

        with (
            patch("agentfiles.tokens.token_estimate", side_effect=[est_agent, est_skill]),
            patch("agentfiles.tokens.estimate_name_description_tokens", return_value=5),
        ):
            _format_list_json(items, show_tokens=True)
        output = json.loads(capsys.readouterr().out)
        assert "token_summary" in output
        assert output["token_summary"]["items"] == 2
        assert output["token_summary"]["total_tokens"] == 160
        assert output["token_summary"]["name_desc_tokens"] == 10

    def test_empty_items_outputs_empty_object(self, capsys: pytest.CaptureFixture[str]) -> None:
        result = _format_list_json([], show_tokens=False)
        captured = capsys.readouterr()
        assert result == 0
        output = json.loads(captured.out)
        assert output == {"items": []}

    def test_items_sorted_by_type_then_name(self, capsys: pytest.CaptureFixture[str]) -> None:
        items = [
            _make_item("zebra", ItemType.SKILL),
            _make_item("alpha", ItemType.AGENT),
            _make_item("beta", ItemType.AGENT),
        ]
        _format_list_json(items, show_tokens=False)
        output = json.loads(capsys.readouterr().out)
        names = [d["name"] for d in output["items"]]
        # agent/alpha < agent/beta < skill/zebra
        assert names == ["alpha", "beta", "zebra"]


# ---------------------------------------------------------------------------
# _format_list_text
# ---------------------------------------------------------------------------


class TestFormatListText:
    """Tests for _format_list_text helper."""

    def test_outputs_item_names(self, capsys: pytest.CaptureFixture[str]) -> None:
        items = [_make_item("reviewer", ItemType.AGENT)]
        result = _format_list_text(items, show_tokens=False)
        captured = capsys.readouterr()
        assert result == 0
        assert "reviewer" in captured.out

    def test_groups_by_type(self, capsys: pytest.CaptureFixture[str]) -> None:
        items = [
            _make_item("a1", ItemType.AGENT),
            _make_item("s1", ItemType.SKILL),
        ]
        _format_list_text(items, show_tokens=False)
        output = capsys.readouterr().out
        # ItemType.plural returns lowercase names (e.g. "agents:", "skills:")
        assert "agents:" in output
        assert "skills:" in output

    def test_empty_items_returns_zero(self, capsys: pytest.CaptureFixture[str]) -> None:
        result = _format_list_text([], show_tokens=False)
        assert result == 0

    def test_with_tokens_shows_token_count(self, capsys: pytest.CaptureFixture[str]) -> None:
        items = [_make_item("agent-x")]
        estimate = TokenEstimate(
            name="agent-x",
            item_type=ItemType.AGENT,
            files=("agent-x.md",),
            source_size_bytes=200,
            content_tokens=100,
            overhead_tokens=20,
            total_tokens=120,
        )
        with (
            patch("agentfiles.tokens.token_estimate", return_value=estimate),
            patch("agentfiles.tokens.estimate_name_description_tokens", return_value=10),
        ):
            result = _format_list_text(items, show_tokens=True)
        output = capsys.readouterr().out
        assert result == 0
        assert "120" in output
        assert "Token Summary" in output
        assert "Name + Description tokens" in output

    def test_non_agent_skill_items_skip_tokens(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Commands and plugins never show per-item token counts."""
        items = [_make_item("build", ItemType.COMMAND)]
        estimate = TokenEstimate(
            name="build",
            item_type=ItemType.COMMAND,
            files=("build.md",),
            source_size_bytes=50,
            content_tokens=25,
            overhead_tokens=5,
            total_tokens=30,
        )
        with patch("agentfiles.tokens.token_estimate", return_value=estimate):
            result = _format_list_text(items, show_tokens=True)
        output = capsys.readouterr().out
        assert result == 0
        assert "30" not in output
        assert "Token Summary" not in output


# ---------------------------------------------------------------------------
# _print_token_summary
# ---------------------------------------------------------------------------


class TestPrintTokenSummary:
    """Tests for _print_token_summary helper."""

    def test_prints_summary(self, capsys: pytest.CaptureFixture[str]) -> None:
        estimates = [
            TokenEstimate("a", ItemType.AGENT, (), 100, 50, 10, 60),
            TokenEstimate("b", ItemType.SKILL, (), 200, 80, 20, 100),
        ]
        _print_token_summary(estimates)
        output = capsys.readouterr().out
        assert "Token Summary:" in output
        assert "Items: 2" in output
        assert "160" in output  # total tokens

    def test_empty_estimates_prints_summary(self, capsys: pytest.CaptureFixture[str]) -> None:
        _print_token_summary([])
        output = capsys.readouterr().out
        assert "Token Summary:" in output
        assert "Items: 0" in output


# ---------------------------------------------------------------------------
# _discover_installed_from_targets
# ---------------------------------------------------------------------------


class TestDiscoverInstalledFromTargets:
    """Tests for _discover_installed_from_targets helper."""

    def test_discovers_items_from_target(self, tmp_path: Path) -> None:
        """Discovers installed items by scanning target directories."""
        agent_dir = tmp_path / "agents"
        agent_dir.mkdir()
        (agent_dir / "coder.md").write_text("# coder")

        tm = MagicMock()
        tm.get_installed_items.return_value = [(ItemType.AGENT, "coder")]
        tm.get_target_dir.return_value = agent_dir

        items = _discover_installed_from_targets(
            tm,
            [],
            list(ItemType),
        )
        assert len(items) == 1
        assert items[0].name == "coder"
        assert items[0].item_type == ItemType.AGENT

    def test_skips_nonexistent_files(self, tmp_path: Path) -> None:
        """Items whose files do not exist on disk are excluded."""
        agent_dir = tmp_path / "agents"
        agent_dir.mkdir()

        tm = MagicMock()
        tm.get_installed_items.return_value = [(ItemType.AGENT, "ghost")]
        tm.get_target_dir.return_value = agent_dir

        items = _discover_installed_from_targets(
            tm,
            [],
            list(ItemType),
        )
        assert items == []

    def test_filters_by_item_type(self, tmp_path: Path) -> None:
        """Only items matching allowed types are returned."""
        agent_dir = tmp_path / "agents"
        agent_dir.mkdir()
        (agent_dir / "coder.md").write_text("# coder")

        skill_dir = tmp_path / "skills"
        skill_dir.mkdir()
        (skill_dir / "reviewer").mkdir()
        (skill_dir / "reviewer" / "SKILL.md").write_text("# reviewer")

        tm = MagicMock()

        def get_target_dir(item_type: Any) -> Path:
            if item_type == ItemType.AGENT:
                return agent_dir
            return skill_dir

        tm.get_installed_items.return_value = [
            (ItemType.AGENT, "coder"),
            (ItemType.SKILL, "reviewer"),
        ]
        tm.get_target_dir.side_effect = get_target_dir

        # Filter to only AGENT type
        items = _discover_installed_from_targets(
            tm,
            [],
            [ItemType.AGENT],
        )
        assert len(items) == 1
        assert items[0].item_type == ItemType.AGENT

    def test_skips_when_target_dir_is_none(self) -> None:
        """Items with no target directory are silently skipped."""
        tm = MagicMock()
        tm.get_installed_items.return_value = [(ItemType.AGENT, "orphan")]
        tm.get_target_dir.return_value = None

        items = _discover_installed_from_targets(
            tm,
            [],
            list(ItemType),
        )
        assert items == []

    def test_empty_installed_items_returns_empty(self) -> None:
        tm = MagicMock()
        tm.get_installed_items.return_value = []

        items = _discover_installed_from_targets(
            tm,
            [],
            list(ItemType),
        )
        assert items == []

    def test_deduplicates_across_platforms(self, tmp_path: Path) -> None:
        """Same item discovered multiple times is returned once."""
        agent_dir = tmp_path / "agents"
        agent_dir.mkdir()
        (agent_dir / "coder.md").write_text("# coder")

        tm = MagicMock()
        tm.get_installed_items.return_value = [
            (ItemType.AGENT, "coder"),
        ]
        tm.get_target_dir.return_value = agent_dir

        items = _discover_installed_from_targets(
            tm,
            [],
            list(ItemType),
        )
        # Single item
        assert len(items) == 1
        assert items[0].name == "coder"


# ---------------------------------------------------------------------------
# TargetManager.owns_target_dir
# ---------------------------------------------------------------------------


class TestResolvePlatformFor:
    """Tests for TargetManager.owns_target_dir method."""

    def _make_target_manager(
        self,
        targets: TargetPaths | None = None,
    ) -> TargetManager:
        """Create a TargetManager with the given targets."""
        return TargetManager(targets)

    def test_finds_matching_platform(self, tmp_path: Path) -> None:
        target_dir = tmp_path / "agent"
        target_dir.mkdir()
        tp = TargetPaths(config_dir=tmp_path, subdirs={"agents": target_dir})
        tm = self._make_target_manager(tp)

        result = tm.owns_target_dir(ItemType.AGENT, target_dir)
        assert result is True

    def test_returns_none_when_no_match(self, tmp_path: Path) -> None:
        other_dir = tmp_path / "other"
        other_dir.mkdir()
        tp = TargetPaths(config_dir=tmp_path, subdirs={"agents": other_dir})
        tm = self._make_target_manager(tp)

        result = tm.owns_target_dir(ItemType.AGENT, tmp_path / "agents")
        assert result is False

    def test_returns_none_when_no_targets(self) -> None:
        tm = self._make_target_manager()
        result = tm.owns_target_dir(ItemType.AGENT, Path("/some/dir"))
        assert result is False


# ---------------------------------------------------------------------------
# build_parser
# ---------------------------------------------------------------------------


class TestBuildParser:
    """Tests for the argument parser construction."""

    def test_has_version_flag(self) -> None:
        parser = build_parser()
        with pytest.raises(SystemExit) as exc_info:
            parser.parse_args(["--version"])
        assert exc_info.value.code == 0

    def test_has_all_subcommands(self) -> None:
        parser = build_parser()
        for cmd in [
            "pull",
            "push",
            "status",
            "clean",
            "init",
        ]:
            args = parser.parse_args([cmd])
            assert args.command == cmd

    def test_init_default_path_is_dot(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["init"])
        assert args.path == "."

    def test_init_with_custom_path(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["init", "/tmp/myrepo"])
        assert args.path == "/tmp/myrepo"

    def test_pull_has_dry_run_flag(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["pull", "--dry-run"])
        assert args.dry_run is True

    def test_verbose_and_quiet_flags(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["--verbose", "status"])
        assert args.verbose is True
        args = parser.parse_args(["--quiet", "status"])
        assert args.quiet is True

    def test_pull_with_symlinks(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["pull", "--symlinks"])
        assert args.symlinks is True

    def test_no_command_sets_command_to_none(self) -> None:
        parser = build_parser()
        args = parser.parse_args([])
        assert args.command is None

    @pytest.mark.parametrize("cmd", ["pull", "push", "clean"])
    def test_yes_flag_sets_non_interactive(self, cmd: str) -> None:
        parser = build_parser()
        args = parser.parse_args([cmd, "--yes"])
        assert args.non_interactive is True
