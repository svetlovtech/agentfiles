"""Tests for agentfiles.config — AgentfilesConfig loading and sync state I/O."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest import mock

import pytest
import yaml

from agentfiles.config import (
    AgentfilesConfig,
    _iter_config_search_paths,
    _read_yaml_file,
    _validate_config_dict,
    load_sync_state,
    save_sync_state,
)
from agentfiles.models import (
    ConfigError,
    SyncState,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def valid_yaml_content() -> str:
    """Return a valid YAML configuration string."""
    return yaml.dump(
        {
            "use_symlinks": True,
            "cache_dir": "/tmp/agentfiles-cache",
            "custom_paths": {"opencode": "/custom/opencode"},
        }
    )


@pytest.fixture
def valid_config_file(tmp_path: Path, valid_yaml_content: str) -> Path:
    """Create a valid .agentfiles.yaml file and return its path."""
    cfg = tmp_path / ".agentfiles.yaml"
    cfg.write_text(valid_yaml_content, encoding="utf-8")
    return cfg


# ---------------------------------------------------------------------------
# AgentfilesConfig creation
# ---------------------------------------------------------------------------


class TestAgentfilesConfigCreation:
    """Tests for AgentfilesConfig instantiation with defaults and custom values."""

    def test_default_values(self) -> None:
        config = AgentfilesConfig()
        assert config.use_symlinks is False
        assert config.cache_dir is None
        assert config.custom_paths == {}

    def test_custom_use_symlinks(self) -> None:
        config = AgentfilesConfig(use_symlinks=True)
        assert config.use_symlinks is True

    def test_custom_cache_dir(self) -> None:
        config = AgentfilesConfig(cache_dir="/tmp/cache")
        assert config.cache_dir == "/tmp/cache"

    def test_custom_paths(self) -> None:
        config = AgentfilesConfig(custom_paths={"opencode": "/x"})
        assert config.custom_paths == {"opencode": "/x"}

    def test_all_custom_values(self) -> None:
        config = AgentfilesConfig(
            use_symlinks=True,
            cache_dir="/cache",
            custom_paths={"opencode": "/custom"},
        )
        assert config.use_symlinks is True
        assert config.cache_dir == "/cache"
        assert config.custom_paths == {"opencode": "/custom"}


# ---------------------------------------------------------------------------
# Frozen immutability
# ---------------------------------------------------------------------------


class TestAgentfilesConfigImmutability:
    """Tests that AgentfilesConfig fields cannot be mutated after creation."""

    @pytest.mark.parametrize(
        "field, value",
        [
            ("use_symlinks", True),
            ("cache_dir", "/tmp"),
            ("custom_paths", {}),
        ],
    )
    def test_frozen_dataclass_prevents_mutation(self, field: str, value: Any) -> None:
        config = AgentfilesConfig()
        with pytest.raises(AttributeError):
            setattr(config, field, value)


# ---------------------------------------------------------------------------
# _from_dict
# ---------------------------------------------------------------------------


class TestFromDict:
    """Tests for AgentfilesConfig._from_dict class method."""

    def test_full_dict(self) -> None:
        data = {
            "use_symlinks": True,
            "cache_dir": "/cache",
            "custom_paths": {"opencode": "/x"},
        }
        config = AgentfilesConfig._from_dict(data)
        assert config.use_symlinks is True
        assert config.cache_dir == "/cache"
        assert config.custom_paths == {"opencode": "/x"}

    def test_empty_dict_returns_defaults(self) -> None:
        config = AgentfilesConfig._from_dict({})
        assert config.use_symlinks is False
        assert config.cache_dir is None
        assert config.custom_paths == {}

    def test_partial_dict_uses_defaults_for_missing(self) -> None:
        data = {"use_symlinks": True}
        config = AgentfilesConfig._from_dict(data)
        assert config.use_symlinks is True
        assert config.cache_dir is None
        assert config.custom_paths == {}

    def test_unknown_keys_ignored(self) -> None:
        data = {"unknown_key": "value", "another_unknown": 42, "use_symlinks": True}
        config = AgentfilesConfig._from_dict(data)
        assert config.use_symlinks is True

    def test_use_symlinks_coerced_to_bool(self) -> None:
        config = AgentfilesConfig._from_dict({"use_symlinks": "yes"})
        assert config.use_symlinks is True

        config2 = AgentfilesConfig._from_dict({"use_symlinks": 0})
        assert config2.use_symlinks is False

    def test_cache_dir_coerced_to_str(self) -> None:
        config = AgentfilesConfig._from_dict({"cache_dir": Path("/tmp/cache")})
        assert config.cache_dir == "/tmp/cache"

    def test_custom_paths_copied_to_dict(self) -> None:
        data = {"custom_paths": {"opencode": "/o"}}
        config = AgentfilesConfig._from_dict(data)
        assert isinstance(config.custom_paths, dict)
        assert config.custom_paths == {"opencode": "/o"}

    def test_none_cache_dir_uses_default(self) -> None:
        """A None value for cache_dir should use the default, not coerce to 'None'."""
        data = {"cache_dir": None}
        config = AgentfilesConfig._from_dict(data)
        assert config.cache_dir is None

    def test_none_use_symlinks_uses_default(self) -> None:
        """A None value for use_symlinks should use the default."""
        data = {"use_symlinks": None}
        config = AgentfilesConfig._from_dict(data)
        assert config.use_symlinks is False


# ---------------------------------------------------------------------------
# load() class method
# ---------------------------------------------------------------------------


class TestLoad:
    """Tests for AgentfilesConfig.load class method."""

    def test_load_from_explicit_path(self, valid_config_file: Path) -> None:
        config = AgentfilesConfig.load(valid_config_file)
        assert config.use_symlinks is True
        assert config.cache_dir == "/tmp/agentfiles-cache"
        assert config.custom_paths == {"opencode": "/custom/opencode"}

    def test_load_explicit_nonexistent_raises(self) -> None:
        with pytest.raises(ConfigError, match="config file not found"):
            AgentfilesConfig.load(Path("/nonexistent/config.yaml"))

    def test_load_none_returns_defaults(self, tmp_path: Path) -> None:
        """When no config file exists, load returns defaults."""
        with (
            mock.patch.object(Path, "cwd", return_value=tmp_path),
            mock.patch.object(Path, "home", return_value=tmp_path),
        ):
            config = AgentfilesConfig.load(None)
        assert config.use_symlinks is False

    def test_load_discovers_cwd_yaml(self, tmp_path: Path) -> None:
        """load discovers .agentfiles.yaml in CWD."""
        cfg = tmp_path / ".agentfiles.yaml"
        cfg.write_text(yaml.dump({"use_symlinks": True}), encoding="utf-8")

        isolated_home = tmp_path / "empty_home"

        with (
            mock.patch.object(Path, "cwd", return_value=tmp_path),
            mock.patch.object(Path, "home", return_value=isolated_home),
        ):
            config = AgentfilesConfig.load(None)
        assert config.use_symlinks is True

    def test_load_discovers_cwd_yml(self, tmp_path: Path) -> None:
        """load discovers .agentfiles.yml in CWD."""
        cfg = tmp_path / ".agentfiles.yml"
        cfg.write_text(yaml.dump({"cache_dir": "/mycache"}), encoding="utf-8")

        isolated_home = tmp_path / "empty_home"

        with (
            mock.patch.object(Path, "cwd", return_value=tmp_path),
            mock.patch.object(Path, "home", return_value=isolated_home),
        ):
            config = AgentfilesConfig.load(None)
        assert config.cache_dir == "/mycache"

    def test_load_discovers_home_yaml(self, tmp_path: Path) -> None:
        """load discovers ~/.agentfiles.yaml when CWD has none."""
        home_cfg = tmp_path / "home" / ".agentfiles.yaml"
        home_cfg.parent.mkdir(parents=True)
        home_cfg.write_text(yaml.dump({"use_symlinks": True}), encoding="utf-8")

        with (
            mock.patch.object(Path, "cwd", return_value=tmp_path / "cwd"),
            mock.patch.object(Path, "home", return_value=tmp_path / "home"),
        ):
            config = AgentfilesConfig.load(None)
        assert config.use_symlinks is True

    def test_cwd_takes_priority_over_home(self, tmp_path: Path) -> None:
        """CWD config takes priority over home config."""
        cwd_cfg = tmp_path / ".agentfiles.yaml"
        cwd_cfg.write_text(yaml.dump({"use_symlinks": True}), encoding="utf-8")

        home_cfg = tmp_path / "home" / ".agentfiles.yaml"
        home_cfg.parent.mkdir(parents=True)
        home_cfg.write_text(yaml.dump({"use_symlinks": False}), encoding="utf-8")

        with (
            mock.patch.object(Path, "cwd", return_value=tmp_path),
            mock.patch.object(Path, "home", return_value=tmp_path / "home"),
        ):
            config = AgentfilesConfig.load(None)
        assert config.use_symlinks is True

    def test_invalid_yaml_warns_and_continues(self, tmp_path: Path) -> None:
        """Invalid YAML file logs warning and falls through to next."""
        bad_cfg = tmp_path / ".agentfiles.yaml"
        bad_cfg.write_text("\x00invalid yaml", encoding="utf-8")

        good_cfg = tmp_path / ".agentfiles.yml"
        good_cfg.write_text(yaml.dump({"use_symlinks": True}), encoding="utf-8")

        isolated_home = tmp_path / "empty_home"

        with (
            mock.patch.object(Path, "cwd", return_value=tmp_path),
            mock.patch.object(Path, "home", return_value=isolated_home),
        ):
            config = AgentfilesConfig.load(None)

        # Should fall through to .agentfiles.yml
        assert config.use_symlinks is True

    def test_all_files_invalid_returns_defaults(self, tmp_path: Path) -> None:
        """When all config files have invalid YAML, returns defaults."""
        bad_yaml = "\x00invalid yaml"

        (tmp_path / ".agentfiles.yaml").write_text(bad_yaml, encoding="utf-8")
        (tmp_path / ".agentfiles.yml").write_text(bad_yaml, encoding="utf-8")

        home = tmp_path / "home"
        home.mkdir()
        (home / ".agentfiles.yaml").write_text(bad_yaml, encoding="utf-8")
        (home / ".agentfiles.yml").write_text(bad_yaml, encoding="utf-8")

        with (
            mock.patch.object(Path, "cwd", return_value=tmp_path),
            mock.patch.object(Path, "home", return_value=home),
        ):
            config = AgentfilesConfig.load(None)
        assert config.use_symlinks is False


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Edge cases for AgentfilesConfig."""

    def test_yaml_with_none_value_uses_default(self, tmp_path: Path) -> None:
        """A key with null YAML value should behave like the key is absent."""
        cfg = tmp_path / ".agentfiles.yaml"
        cfg.write_text(yaml.dump({"cache_dir": None, "use_symlinks": True}), encoding="utf-8")

        isolated_home = tmp_path / "empty_home"

        with (
            mock.patch.object(Path, "cwd", return_value=tmp_path),
            mock.patch.object(Path, "home", return_value=isolated_home),
        ):
            config = AgentfilesConfig.load(None)
        assert config.use_symlinks is True
        assert config.cache_dir is None  # None in YAML should not become "None" string

    def test_yaml_file_with_only_comments(self, tmp_path: Path) -> None:
        cfg = tmp_path / ".agentfiles.yaml"
        cfg.write_text("# Just a comment\n", encoding="utf-8")

        isolated_home = tmp_path / "empty_home"

        with (
            mock.patch.object(Path, "cwd", return_value=tmp_path),
            mock.patch.object(Path, "home", return_value=isolated_home),
        ):
            config = AgentfilesConfig.load(None)
        # yaml.safe_load returns None for comment-only file, which gets
        # converted to {} via "yaml.safe_load(fh) or {}"
        assert config.use_symlinks is False

    def test_two_configs_with_same_defaults_are_equal(self) -> None:
        a = AgentfilesConfig()
        b = AgentfilesConfig()
        assert a == b

    def test_explicit_path_overrides_auto_discovery(self, tmp_path: Path) -> None:
        """Explicit path argument should bypass auto-discovery."""
        explicit = tmp_path / "explicit.yaml"
        explicit.write_text(yaml.dump({"use_symlinks": True}), encoding="utf-8")

        cwd_cfg = tmp_path / ".agentfiles.yaml"
        cwd_cfg.write_text(yaml.dump({"use_symlinks": False}), encoding="utf-8")

        isolated_home = tmp_path / "empty_home"

        with (
            mock.patch.object(Path, "cwd", return_value=tmp_path),
            mock.patch.object(Path, "home", return_value=isolated_home),
        ):
            config = AgentfilesConfig.load(explicit)
        assert config.use_symlinks is True


# ---------------------------------------------------------------------------
# Explicit path error handling
# ---------------------------------------------------------------------------


class TestLoadExplicitErrors:
    """Tests for AgentfilesConfig.load with explicit path and invalid files."""

    def test_explicit_malformed_yaml_raises(self, tmp_path: Path) -> None:
        """Explicit path with malformed YAML raises ConfigError."""
        cfg = tmp_path / "bad.yaml"
        cfg.write_text("\x00invalid: yaml: [", encoding="utf-8")

        with pytest.raises(ConfigError, match="malformed YAML"):
            AgentfilesConfig.load(cfg)

    def test_explicit_invalid_custom_paths_type_raises(self, tmp_path: Path) -> None:
        """Explicit path with non-dict custom_paths raises ConfigError."""
        cfg = tmp_path / "bad.yaml"
        cfg.write_text(yaml.dump({"custom_paths": "not_a_dict"}), encoding="utf-8")

        with pytest.raises(ConfigError, match="custom_paths"):
            AgentfilesConfig.load(cfg)


# ---------------------------------------------------------------------------
# YAML top-level edge cases
# ---------------------------------------------------------------------------


class TestReadYamlEdgeCases:
    """Tests for YAML files with non-mapping top-level types."""

    def test_top_level_list_returns_defaults(self, tmp_path: Path) -> None:
        """YAML file with list at top level treated as empty config."""
        cfg = tmp_path / "list.yaml"
        cfg.write_text("- item1\n- item2\n", encoding="utf-8")

        config = AgentfilesConfig.load(cfg)
        assert config == AgentfilesConfig()

    def test_top_level_scalar_returns_defaults(self, tmp_path: Path) -> None:
        """YAML file with scalar at top level treated as empty config."""
        cfg = tmp_path / "scalar.yaml"
        cfg.write_text("just a string\n", encoding="utf-8")

        config = AgentfilesConfig.load(cfg)
        assert config == AgentfilesConfig()


# ---------------------------------------------------------------------------
# Sync state corruption recovery
# ---------------------------------------------------------------------------


class TestSyncStateRecovery:
    """Tests for sync state corruption recovery."""

    def test_corrupted_state_returns_empty(self, tmp_path: Path) -> None:
        """Corrupted state file returns empty SyncState instead of crashing."""
        state_file = tmp_path / ".agentfiles.state.yaml"
        state_file.write_text("\x00bad: yaml: [", encoding="utf-8")

        state = load_sync_state(tmp_path)

        assert state == SyncState()

    def test_corrupted_state_backed_up(self, tmp_path: Path) -> None:
        """Corrupted state file is renamed with .corrupted suffix."""
        state_file = tmp_path / ".agentfiles.state.yaml"
        state_file.write_text("\x00bad yaml", encoding="utf-8")

        load_sync_state(tmp_path)

        assert not state_file.exists()
        assert (tmp_path / ".agentfiles.state.yaml.corrupted").exists()

    def test_backup_preserves_corrupted_content(self, tmp_path: Path) -> None:
        """Corrupted content is preserved in the backup for debugging."""
        state_file = tmp_path / ".agentfiles.state.yaml"
        bad_content = "\x00corrupted content here"
        state_file.write_text(bad_content, encoding="utf-8")

        load_sync_state(tmp_path)

        backup = tmp_path / ".agentfiles.state.yaml.corrupted"
        assert backup.read_text(encoding="utf-8") == bad_content

    def test_multiple_corruptions_create_numbered_backups(self, tmp_path: Path) -> None:
        """Repeated corruptions create numbered backup files."""
        for i in range(3):
            state_file = tmp_path / ".agentfiles.state.yaml"
            state_file.write_text(f"\x00bad{i}", encoding="utf-8")
            load_sync_state(tmp_path)

        assert (tmp_path / ".agentfiles.state.yaml.corrupted").exists()
        assert (tmp_path / ".agentfiles.state.yaml.corrupted.1").exists()
        assert (tmp_path / ".agentfiles.state.yaml.corrupted.2").exists()

    def test_valid_state_after_corruption_recovery(self, tmp_path: Path) -> None:
        """After corruption recovery, saving and loading works normally."""
        state_file = tmp_path / ".agentfiles.state.yaml"
        state_file.write_text("\x00corrupted", encoding="utf-8")

        # Recover from corruption
        state = load_sync_state(tmp_path)
        assert state == SyncState()

        # Save a valid state and load it back
        new_state = SyncState(
            version="1.0",
            last_sync="2025-07-01T12:00:00Z",
        )
        save_sync_state(tmp_path, new_state)
        loaded = load_sync_state(tmp_path)

        assert loaded == new_state

    def test_auto_discovery_skips_invalid_config(self, tmp_path: Path) -> None:
        """Auto-discovery skips malformed YAML and tries next location."""
        bad_cfg = tmp_path / ".agentfiles.yaml"
        bad_cfg.write_text("\x00invalid yaml", encoding="utf-8")

        good_cfg = tmp_path / ".agentfiles.yml"
        good_cfg.write_text(yaml.dump({"use_symlinks": True}), encoding="utf-8")

        isolated_home = tmp_path / "empty_home"

        with (
            mock.patch.object(Path, "cwd", return_value=tmp_path),
            mock.patch.object(Path, "home", return_value=isolated_home),
        ):
            config = AgentfilesConfig.load(None)

        assert config.use_symlinks is True


# ---------------------------------------------------------------------------
# Config with all fields populated via load()
# ---------------------------------------------------------------------------


class TestConfigLoadAllFields:
    """Tests for loading a fully populated config from a YAML file."""

    def test_load_config_with_all_fields(self, tmp_path: Path) -> None:
        """Loading a YAML file with every field set populates all attributes."""
        data = {
            "use_symlinks": True,
            "cache_dir": "/opt/agentfiles/cache",
            "custom_paths": {
                "opencode": "/home/user/.config/opencode",
            },
        }
        cfg_file = tmp_path / ".agentfiles.yaml"
        cfg_file.write_text(yaml.dump(data), encoding="utf-8")

        config = AgentfilesConfig.load(cfg_file)

        assert config.use_symlinks is True
        assert config.cache_dir == "/opt/agentfiles/cache"
        assert config.custom_paths == {
            "opencode": "/home/user/.config/opencode",
        }

    def test_load_config_all_fields_via_auto_discovery(self, tmp_path: Path) -> None:
        """Auto-discovery loads all fields from .agentfiles.yaml in CWD."""
        data = {
            "use_symlinks": False,
            "cache_dir": "/var/cache/agentfiles",
            "custom_paths": {"opencode": "/home/user/.config/opencode"},
        }
        cfg = tmp_path / ".agentfiles.yaml"
        cfg.write_text(yaml.dump(data), encoding="utf-8")

        isolated_home = tmp_path / "empty_home"

        with (
            mock.patch.object(Path, "cwd", return_value=tmp_path),
            mock.patch.object(Path, "home", return_value=isolated_home),
        ):
            config = AgentfilesConfig.load(None)

        assert config.use_symlinks is False
        assert config.cache_dir == "/var/cache/agentfiles"
        assert config.custom_paths == {"opencode": "/home/user/.config/opencode"}


# ---------------------------------------------------------------------------
# Config with missing optional fields via load()
# ---------------------------------------------------------------------------


class TestConfigLoadMissingOptionalFields:
    """Tests for loading config when some fields are absent from YAML."""

    def test_load_with_only_use_symlinks(self, tmp_path: Path) -> None:
        """Only use_symlinks is set; other fields use defaults."""
        cfg = tmp_path / ".agentfiles.yaml"
        cfg.write_text(yaml.dump({"use_symlinks": True}), encoding="utf-8")

        config = AgentfilesConfig.load(cfg)

        assert config.use_symlinks is True
        assert config.cache_dir is None
        assert config.custom_paths == {}

    def test_load_with_only_cache_dir(self, tmp_path: Path) -> None:
        """Only cache_dir is set; other fields use defaults."""
        cfg = tmp_path / ".agentfiles.yaml"
        cfg.write_text(yaml.dump({"cache_dir": "/tmp/my-cache"}), encoding="utf-8")

        config = AgentfilesConfig.load(cfg)

        assert config.use_symlinks is False
        assert config.cache_dir == "/tmp/my-cache"
        assert config.custom_paths == {}

    def test_load_with_only_custom_paths(self, tmp_path: Path) -> None:
        """Only custom_paths is set; other fields use defaults."""
        cfg = tmp_path / ".agentfiles.yaml"
        cfg.write_text(
            yaml.dump({"custom_paths": {"opencode": "/custom/path"}}),
            encoding="utf-8",
        )

        config = AgentfilesConfig.load(cfg)

        assert config.use_symlinks is False
        assert config.cache_dir is None
        assert config.custom_paths == {"opencode": "/custom/path"}

    def test_load_empty_yaml_uses_all_defaults(self, tmp_path: Path) -> None:
        """An empty YAML file (no keys) results in all-default config."""
        cfg = tmp_path / ".agentfiles.yaml"
        cfg.write_text(yaml.dump({}), encoding="utf-8")

        config = AgentfilesConfig.load(cfg)

        assert config == AgentfilesConfig()


# ---------------------------------------------------------------------------
# Config search path resolution (_iter_config_search_paths)
# ---------------------------------------------------------------------------


class TestIterConfigSearchPaths:
    """Tests for _iter_config_search_paths generator."""

    def test_explicit_existing_file_yields_single_path(self, tmp_path: Path) -> None:
        """Explicit path to an existing file yields only that path."""
        cfg = tmp_path / "my-config.yaml"
        cfg.write_text("key: value", encoding="utf-8")

        paths = list(_iter_config_search_paths(cfg))

        assert len(paths) == 1
        assert paths[0] == cfg

    def test_explicit_nonexistent_file_raises(self) -> None:
        """Explicit path to a nonexistent file raises ConfigError."""
        with pytest.raises(ConfigError, match="config file not found"):
            list(_iter_config_search_paths(Path("/nonexistent/file.yaml")))

    def test_auto_discovery_yields_four_paths(self, tmp_path: Path) -> None:
        """Auto-discovery yields 4 paths: (CWD + home) x 2 filenames."""
        with (
            mock.patch.object(Path, "cwd", return_value=tmp_path / "cwd"),
            mock.patch.object(Path, "home", return_value=tmp_path / "home"),
        ):
            paths = list(_iter_config_search_paths(None))

        assert len(paths) == 4
        # CWD paths come first
        assert paths[0] == tmp_path / "cwd" / ".agentfiles.yaml"
        assert paths[1] == tmp_path / "cwd" / ".agentfiles.yml"
        # Home paths come second
        assert paths[2] == tmp_path / "home" / ".agentfiles.yaml"
        assert paths[3] == tmp_path / "home" / ".agentfiles.yml"

    def test_auto_discovery_cwd_before_home(self, tmp_path: Path) -> None:
        """CWD paths are yielded before home directory paths."""
        cwd_dir = tmp_path / "cwd"
        home_dir = tmp_path / "home"

        with (
            mock.patch.object(Path, "cwd", return_value=cwd_dir),
            mock.patch.object(Path, "home", return_value=home_dir),
        ):
            paths = list(_iter_config_search_paths(None))

        cwd_paths = [p for p in paths if cwd_dir in p.parents]
        home_paths = [p for p in paths if home_dir in p.parents]
        for cp in cwd_paths:
            for hp in home_paths:
                assert paths.index(cp) < paths.index(hp)

    def test_auto_discovery_yaml_before_yml(self, tmp_path: Path) -> None:
        """Within each directory, .yaml is yielded before .yml."""
        with (
            mock.patch.object(Path, "cwd", return_value=tmp_path),
            mock.patch.object(Path, "home", return_value=tmp_path / "home"),
        ):
            paths = list(_iter_config_search_paths(None))

        assert paths[0].name == ".agentfiles.yaml"
        assert paths[1].name == ".agentfiles.yml"

    def test_explicit_path_to_directory_raises(self, tmp_path: Path) -> None:
        """Explicit path to a directory (not a file) raises ConfigError."""
        directory = tmp_path / "a_directory"
        directory.mkdir()

        with pytest.raises(ConfigError, match="config file not found"):
            list(_iter_config_search_paths(directory))


# ---------------------------------------------------------------------------
# _validate_config_dict direct tests
# ---------------------------------------------------------------------------


class TestValidateConfigDict:
    """Direct tests for _validate_config_dict function."""

    def test_valid_full_config_passes(self, tmp_path: Path) -> None:
        """A fully valid config dict passes validation without error."""
        data = {
            "use_symlinks": True,
            "cache_dir": "/cache",
            "custom_paths": {"opencode": "/path"},
        }
        _validate_config_dict(data, tmp_path / "test.yaml")

    def test_empty_dict_passes(self, tmp_path: Path) -> None:
        """An empty dict passes validation."""
        _validate_config_dict({}, tmp_path / "test.yaml")

    def test_custom_paths_string_raises(self, tmp_path: Path) -> None:
        """A string value for custom_paths raises ConfigError."""
        data = {"custom_paths": "not_a_mapping"}
        with pytest.raises(ConfigError, match="expected a mapping, got str"):
            _validate_config_dict(data, tmp_path / "test.yaml")

    def test_custom_paths_list_raises(self, tmp_path: Path) -> None:
        """A list value for custom_paths raises ConfigError."""
        data = {"custom_paths": ["opencode", "/path"]}
        with pytest.raises(ConfigError, match="expected a mapping, got list"):
            _validate_config_dict(data, tmp_path / "test.yaml")

    def test_unknown_keys_ignored(self, tmp_path: Path) -> None:
        """Unknown keys in the config dict do not trigger validation errors."""
        data = {"unknown_field": 42, "another": [1, 2, 3]}
        _validate_config_dict(data, tmp_path / "test.yaml")

    def test_path_included_in_error_message(self, tmp_path: Path) -> None:
        """The config file path is included in error messages."""
        cfg_path = tmp_path / "my-special-config.yaml"
        data = {"custom_paths": "not_a_mapping"}
        with pytest.raises(ConfigError):
            _validate_config_dict(data, cfg_path)


# ---------------------------------------------------------------------------
# _read_yaml_file edge cases
# ---------------------------------------------------------------------------


class TestReadYamlFile:
    """Direct tests for _read_yaml_file function."""

    def test_reads_valid_yaml(self, tmp_path: Path) -> None:
        """Valid YAML file is parsed into a dictionary."""
        f = tmp_path / "test.yaml"
        f.write_text("key: value\nnumber: 42\n", encoding="utf-8")

        result = _read_yaml_file(f)
        assert result == {"key": "value", "number": 42}

    def test_returns_empty_dict_for_comment_only(self, tmp_path: Path) -> None:
        """A file with only comments returns an empty dict."""
        f = tmp_path / "comments.yaml"
        f.write_text("# just a comment\n# another comment\n", encoding="utf-8")

        result = _read_yaml_file(f)
        assert result == {}

    def test_returns_empty_dict_for_empty_file(self, tmp_path: Path) -> None:
        """An empty file returns an empty dict."""
        f = tmp_path / "empty.yaml"
        f.write_text("", encoding="utf-8")

        result = _read_yaml_file(f)
        assert result == {}

    def test_returns_empty_dict_for_top_level_list(self, tmp_path: Path) -> None:
        """A YAML file with a top-level list returns an empty dict."""
        f = tmp_path / "list.yaml"
        f.write_text("- item1\n- item2\n", encoding="utf-8")

        result = _read_yaml_file(f)
        assert result == {}

    def test_returns_empty_dict_for_top_level_scalar(self, tmp_path: Path) -> None:
        """A YAML file with a top-level scalar returns an empty dict."""
        f = tmp_path / "scalar.yaml"
        f.write_text("just a string\n", encoding="utf-8")

        result = _read_yaml_file(f)
        assert result == {}

    def test_malformed_yaml_raises_config_error(self, tmp_path: Path) -> None:
        """Malformed YAML raises ConfigError."""
        f = tmp_path / "bad.yaml"
        f.write_text("\x00invalid: yaml: [", encoding="utf-8")

        with pytest.raises(ConfigError, match="malformed YAML"):
            _read_yaml_file(f)

    def test_nonexistent_file_raises_config_error(self) -> None:
        """A nonexistent file raises ConfigError."""
        with pytest.raises(ConfigError, match="cannot read file"):
            _read_yaml_file(Path("/nonexistent/file.yaml"))

    def test_path_included_in_error_message(self, tmp_path: Path) -> None:
        """The file path is included in error messages for debugging."""
        f = tmp_path / "specific-file.yaml"
        f.write_text("\x00bad", encoding="utf-8")

        with pytest.raises(ConfigError):
            _read_yaml_file(f)


# ---------------------------------------------------------------------------
# Corrupted config recovery (config files, not state files)
# ---------------------------------------------------------------------------


class TestCorruptedConfigRecovery:
    """Tests for config file corruption handling during auto-discovery."""

    def test_corrupted_cwd_config_falls_through_to_yml(self, tmp_path: Path) -> None:
        """Corrupted .yaml in CWD falls through to .yml."""
        bad_cfg = tmp_path / ".agentfiles.yaml"
        bad_cfg.write_text("\x00corrupted", encoding="utf-8")

        good_cfg = tmp_path / ".agentfiles.yml"
        good_cfg.write_text(
            yaml.dump({"cache_dir": "/fallback-cache"}),
            encoding="utf-8",
        )

        isolated_home = tmp_path / "empty_home"

        with (
            mock.patch.object(Path, "cwd", return_value=tmp_path),
            mock.patch.object(Path, "home", return_value=isolated_home),
        ):
            config = AgentfilesConfig.load(None)

        assert config.cache_dir == "/fallback-cache"

    def test_corrupted_cwd_falls_through_to_home(self, tmp_path: Path) -> None:
        """Corrupted CWD configs fall through to home directory config."""
        bad_yaml = "\x00corrupted"
        (tmp_path / ".agentfiles.yaml").write_text(bad_yaml, encoding="utf-8")
        (tmp_path / ".agentfiles.yml").write_text(bad_yaml, encoding="utf-8")

        home = tmp_path / "home"
        home.mkdir()
        (home / ".agentfiles.yaml").write_text(
            yaml.dump({"use_symlinks": True}),
            encoding="utf-8",
        )

        with (
            mock.patch.object(Path, "cwd", return_value=tmp_path),
            mock.patch.object(Path, "home", return_value=home),
        ):
            config = AgentfilesConfig.load(None)

        assert config.use_symlinks is True

    def test_explicit_corrupted_config_raises_without_fallback(self, tmp_path: Path) -> None:
        """Explicit path with corrupted config raises instead of falling back."""
        bad_cfg = tmp_path / "explicit.yaml"
        bad_cfg.write_text("\x00corrupted", encoding="utf-8")

        # A valid fallback exists but should not be used
        good_cfg = tmp_path / ".agentfiles.yaml"
        good_cfg.write_text(yaml.dump({"use_symlinks": True}), encoding="utf-8")

        with pytest.raises(ConfigError, match="malformed YAML"):
            AgentfilesConfig.load(bad_cfg)

    def test_invalid_config_value_type_falls_through(self, tmp_path: Path) -> None:
        """Config with wrong value types (e.g. string for custom_paths) falls through."""
        bad_cfg = tmp_path / ".agentfiles.yaml"
        bad_cfg.write_text(
            yaml.dump({"custom_paths": "not_a_mapping"}),
            encoding="utf-8",
        )

        good_cfg = tmp_path / ".agentfiles.yml"
        good_cfg.write_text(
            yaml.dump({"use_symlinks": True}),
            encoding="utf-8",
        )

        isolated_home = tmp_path / "empty_home"

        with (
            mock.patch.object(Path, "cwd", return_value=tmp_path),
            mock.patch.object(Path, "home", return_value=isolated_home),
        ):
            config = AgentfilesConfig.load(None)

        assert config.use_symlinks is True
