"""Tests for platform_groups feature — config parsing and CLI resolution."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from agentfiles.config import (
    AgentfilesConfig,
    _validate_config_dict,
    clear_config_cache,
)
from agentfiles.models import ConfigError, Platform

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_config(**kwargs: object) -> AgentfilesConfig:
    """Construct AgentfilesConfig with only the supplied fields overridden."""
    return AgentfilesConfig(**kwargs)  # type: ignore[arg-type]


def _resolve(target_flag: str | None, config: AgentfilesConfig) -> list[Platform]:
    """Call cli._resolve_platforms without importing the whole CLI module."""
    from agentfiles.cli import _resolve_platforms

    return _resolve_platforms(target_flag, config)


# ---------------------------------------------------------------------------
# Config parsing — platform_groups field
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestPlatformGroupsConfigParsing:
    def test_default_is_empty_dict(self) -> None:
        cfg = AgentfilesConfig()
        assert cfg.platform_groups == {}

    def test_platform_groups_parsed_from_yaml(self, tmp_path: Path) -> None:
        cfg_file = tmp_path / ".agentfiles.yaml"
        cfg_file.write_text(
            yaml.dump(
                {
                    "platform_groups": {
                        "dev": ["claude_code", "cursor"],
                        "ci": ["opencode"],
                    }
                }
            )
        )
        clear_config_cache()
        cfg = AgentfilesConfig.load(cfg_file)
        assert cfg.platform_groups == {
            "dev": ["claude_code", "cursor"],
            "ci": ["opencode"],
        }

    def test_platform_groups_accepts_aliases(self, tmp_path: Path) -> None:
        cfg_file = tmp_path / ".agentfiles.yaml"
        cfg_file.write_text(yaml.dump({"platform_groups": {"fast": ["cc", "cr"]}}))
        clear_config_cache()
        cfg = AgentfilesConfig.load(cfg_file)
        assert cfg.platform_groups == {"fast": ["cc", "cr"]}

    def test_platform_groups_empty_list_is_valid(self, tmp_path: Path) -> None:
        cfg_file = tmp_path / ".agentfiles.yaml"
        cfg_file.write_text(yaml.dump({"platform_groups": {"nothing": []}}))
        clear_config_cache()
        cfg = AgentfilesConfig.load(cfg_file)
        assert cfg.platform_groups == {"nothing": []}


# ---------------------------------------------------------------------------
# Config validation — _validate_config_dict
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestPlatformGroupsValidation:
    _path = Path("/fake/.agentfiles.yaml")

    def test_valid_group_passes(self) -> None:
        data = {"platform_groups": {"dev": ["claude_code", "cursor"]}}
        _validate_config_dict(data, self._path)  # no error

    def test_non_dict_platform_groups_raises(self) -> None:
        data = {"platform_groups": ["claude_code"]}
        with pytest.raises(ConfigError, match="expected a mapping"):
            _validate_config_dict(data, self._path)

    def test_non_list_group_members_raises(self) -> None:
        data = {"platform_groups": {"dev": "claude_code"}}
        with pytest.raises(ConfigError, match="expected a list"):
            _validate_config_dict(data, self._path)

    def test_non_string_member_raises(self) -> None:
        data = {"platform_groups": {"dev": [42]}}
        with pytest.raises(ConfigError, match="expected a string"):
            _validate_config_dict(data, self._path)

    def test_unknown_platform_in_group_raises(self) -> None:
        data = {"platform_groups": {"dev": ["unknown_tool"]}}
        with pytest.raises(ConfigError, match="invalid platform.*unknown_tool"):
            _validate_config_dict(data, self._path)


# ---------------------------------------------------------------------------
# CLI _resolve_platforms — group expansion
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestResolveWithGroups:
    def _cfg(self, groups: dict[str, list[str]]) -> AgentfilesConfig:
        return AgentfilesConfig(platform_groups=groups)

    def test_group_name_expands_to_members(self) -> None:
        cfg = self._cfg({"dev": ["claude_code", "cursor"]})
        result = _resolve("dev", cfg)
        assert result == [Platform.CLAUDE_CODE, Platform.CURSOR]

    def test_group_with_alias_expands_correctly(self) -> None:
        cfg = self._cfg({"fast": ["cc", "cr"]})
        result = _resolve("fast", cfg)
        assert result == [Platform.CLAUDE_CODE, Platform.CURSOR]

    def test_direct_platform_still_works(self) -> None:
        cfg = self._cfg({})
        result = _resolve("opencode", cfg)
        assert result == [Platform.OPENCODE]

    def test_all_returns_every_platform(self) -> None:
        cfg = self._cfg({})
        result = _resolve("all", cfg)
        assert set(result) == set(Platform)

    def test_unknown_name_raises_value_error(self) -> None:
        cfg = self._cfg({})
        with pytest.raises(ValueError, match="unknown platform"):
            _resolve("not_a_platform", cfg)

    def test_group_deduplicates_platforms(self) -> None:
        cfg = self._cfg({"both": ["claude_code", "claude_code"]})
        result = _resolve("both", cfg)
        assert result == [Platform.CLAUDE_CODE]

    def test_group_and_direct_platform_in_default_platforms(self) -> None:
        """default_platforms can mix group names and direct platform names."""
        cfg = AgentfilesConfig(
            default_platforms=["dev", "opencode"],
            platform_groups={"dev": ["claude_code", "cursor"]},
        )
        result = _resolve(None, cfg)
        assert Platform.CLAUDE_CODE in result
        assert Platform.CURSOR in result
        assert Platform.OPENCODE in result

    def test_none_target_with_no_groups_uses_default_platforms(self) -> None:
        cfg = AgentfilesConfig(default_platforms=["opencode", "windsurf"])
        result = _resolve(None, cfg)
        assert result == [Platform.OPENCODE, Platform.WINDSURF]
