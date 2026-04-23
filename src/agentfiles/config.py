"""Configuration and sync-state management for agentfiles.

This module handles three clearly separated concerns:

1. **Configuration data class** — :class:`AgentfilesConfig` defines runtime
   settings (symlinks, cache directory, custom paths, etc.).
2. **Configuration file I/O** — Locating and loading YAML config from
   standard search locations (explicit path, CWD, home directory).
3. **Sync state I/O** — Persisting and loading sync state to/from
   ``.agentfiles.state.yaml`` in the repository root.
"""

from __future__ import annotations

import logging
import tempfile
from collections.abc import Iterator
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from agentfiles.models import (
    AgentfilesError,
    ConfigError,
    ItemState,
    SyncState,
)

logger = logging.getLogger(__name__)

# Config file names searched in CWD and home directory.
_CONFIG_FILENAMES: tuple[str, ...] = (".agentfiles.yaml", ".agentfiles.yml")

# State file name stored in the repository root.
_STATE_FILENAME: str = ".agentfiles.state.yaml"

# Mapping of YAML config keys to their type coercers.
# Used by AgentfilesConfig._from_dict to declaratively convert parsed values.
_FIELD_COERCERS: dict[str, type] = {
    "use_symlinks": bool,
    "cache_dir": str,
    "custom_paths": dict,
}


# ---------------------------------------------------------------------------
# Shared YAML I/O utilities
# ---------------------------------------------------------------------------


def _read_yaml_file(path: Path) -> dict[str, Any]:
    """Read and parse a YAML file. Returns empty dict for non-mapping top-level.

    Raises ConfigError on read failures, encoding errors, or malformed YAML.
    """
    try:
        with open(path, encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
    except yaml.YAMLError as exc:
        raise ConfigError(f"malformed YAML in '{path}': {exc}") from exc
    except UnicodeDecodeError as exc:
        raise ConfigError(f"invalid text encoding in '{path}': {exc}") from exc
    except OSError as exc:
        raise ConfigError(f"cannot read file '{path}': {exc}") from exc

    return data if isinstance(data, dict) else {}


# ---------------------------------------------------------------------------
# Configuration search path resolution
# ---------------------------------------------------------------------------


def _iter_config_search_paths(config_path: Path | None) -> Iterator[Path]:
    """Yield config file paths in priority order.

    Explicit path is validated for existence; otherwise standard locations
    (CWD, then home) are yielded lazily.

    Raises ConfigError when *config_path* is given but does not exist.
    """
    if config_path is not None:
        explicit = Path(config_path)
        if not explicit.is_file():
            raise ConfigError(
                f"config file not found at explicit path: '{explicit}'. "
                f"Verify the path is correct, or run 'agentfiles init' to create one"
            )
        yield explicit
        return

    for base in (Path.cwd(), Path.home()):
        for filename in _CONFIG_FILENAMES:
            yield base / filename


# ---------------------------------------------------------------------------
# Configuration data class
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AgentfilesConfig:
    """Runtime configuration for agentfiles.

    Loaded from YAML files with the following search order:

    1. Explicit path (via ``--config`` CLI flag)
    2. ``.agentfiles.yaml`` or ``.agentfiles.yml`` in the current directory
    3. ``~/.agentfiles.yaml`` or ``~/.agentfiles.yml``

    Attributes:
        use_symlinks: Create symlinks instead of copying files.
        cache_dir: Override the default cache directory for git clones.
        custom_paths: Mapping of platform name to config directory path.

    """

    use_symlinks: bool = False
    cache_dir: str | None = None
    custom_paths: dict[str, str] = field(default_factory=dict)

    @classmethod
    def load(cls, config_path: Path | None = None) -> AgentfilesConfig:
        """Load config from file, falling back to defaults.

        Searches for config files in the standard locations.  If a file
        is found but cannot be parsed, a warning is logged and the
        search continues.

        When *config_path* is provided explicitly and the file is
        malformed, a :class:`ConfigError` is raised so the caller
        knows their config is broken rather than silently falling back
        to defaults.

        Path resolution is delegated to :func:`_iter_config_search_paths`
        and file reading to the cached :func:`_load_config_from_file`,
        keeping this method focused on *iteration and fallback logic only*.

        Args:
            config_path: Explicit path to a config file, or ``None``
                for auto-discovery.

        Returns:
            A fully populated :class:`AgentfilesConfig` instance.

        Raises:
            ConfigError: When *config_path* is given and the file
                contains malformed YAML or invalid config values.

        """
        for path in _iter_config_search_paths(config_path):
            if path.is_file():
                logger.debug("Loading config from %s", path)
                try:
                    return _load_config_from_file(path)
                except AgentfilesError:
                    if config_path is not None:
                        raise
                    logger.warning(
                        "Skipping invalid config '%s'",
                        path,
                        exc_info=True,
                    )
                    continue

        return cls()

    @classmethod
    def _from_dict(cls, data: dict[str, Any]) -> AgentfilesConfig:
        """Construct a config from a parsed YAML dictionary.

        Uses :data:`_FIELD_COERCERS` to declaratively map YAML keys
        to their type coercers, avoiding repetitive if-blocks.
        """
        kwargs = {
            key: coercer(data[key])
            for key, coercer in _FIELD_COERCERS.items()
            if key in data and data[key] is not None
        }
        return cls(**kwargs)


# ---------------------------------------------------------------------------
# Config validation
# ---------------------------------------------------------------------------


def _validate_config_dict(data: dict[str, Any], path: Path) -> None:
    """Validate config value types before coercion.

    Raises ConfigError when a config value has an unexpected type.
    """
    if "custom_paths" in data:
        value = data["custom_paths"]
        if not isinstance(value, dict):
            raise ConfigError(
                f"invalid 'custom_paths' in '{path}': "
                f"expected a mapping, got {type(value).__name__}"
            )


# ---------------------------------------------------------------------------
# Config loading cache
# ---------------------------------------------------------------------------


@lru_cache(maxsize=8)
def _load_config_from_file(path: Path) -> AgentfilesConfig:
    """Load, validate, and parse a config file. Results are cached by path.

    Raises ConfigError on malformed YAML or invalid config values.
    """
    data = _read_yaml_file(path)
    _validate_config_dict(data, path)
    return AgentfilesConfig._from_dict(data)


def clear_config_cache() -> None:
    """Invalidate the config file loading cache (call after on-disk changes)."""
    _load_config_from_file.cache_clear()


# ---------------------------------------------------------------------------
# Sync State I/O
# ---------------------------------------------------------------------------


def load_sync_state(repo_path: Path) -> SyncState:
    """Load sync state from .agentfiles.state.yaml in the repo root.

    If the state file is corrupted (malformed YAML, bad encoding, or
    unparseable structure), it is backed up with a ``.corrupted`` suffix
    and an empty :class:`SyncState` is returned so the application can
    continue operating.

    Args:
        repo_path: Path to the source repository root.

    Returns:
        SyncState instance, or empty SyncState if file doesn't exist
        or is corrupted.

    """
    state_file = get_state_path(repo_path)
    if not state_file.is_file():
        return SyncState()

    try:
        data = _read_yaml_file(state_file)
        return _parse_sync_state(data)
    except AgentfilesError as exc:
        backup_path = _backup_corrupted_state(state_file)
        logger.warning(
            "Corrupted state file '%s': %s. "
            "Backed up to '%s'. Sync history has been reset — "
            "next pull will treat all items as new.",
            state_file,
            exc,
            backup_path,
        )
        return SyncState()


def save_sync_state(repo_path: Path, state: SyncState) -> None:
    """Save sync state to .agentfiles.state.yaml in the repo root.

    Args:
        repo_path: Path to the source repository root.
        state: SyncState instance to save.

    """
    state_file = get_state_path(repo_path)
    state_file.parent.mkdir(parents=True, exist_ok=True)
    data = _serialize_sync_state(state)

    fd, tmp_path = tempfile.mkstemp(dir=state_file.parent, suffix=".tmp", prefix=".state-")
    try:
        with open(fd, "w", encoding="utf-8") as f:
            f.write("# Sync state — auto-generated, do not edit manually\n")
            f.write("# Use 'agentfiles pull', 'agentfiles push', or 'agentfiles sync'\n")
            yaml.dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
        Path(tmp_path).replace(state_file)
    except BaseException:
        Path(tmp_path).unlink(missing_ok=True)
        raise


def _parse_item_state(raw: dict[str, Any]) -> ItemState:
    """Construct an ItemState from a raw parsed dictionary."""
    return ItemState(synced_at=str(raw.get("synced_at", "")))


def _parse_sync_state(data: dict[str, Any]) -> SyncState:
    """Construct a SyncState from a parsed YAML dictionary.

    Supports both the current flat ``items`` format and the legacy nested
    ``platforms`` format (auto-migrated on load).
    """
    # New flat format: items key present at top level.
    if "items" in data:
        raw_items = data["items"] or {}
        items = {
            key: _parse_item_state(item_data)
            for key, item_data in raw_items.items()
            if isinstance(item_data, dict)
        }
        return SyncState(
            version=str(data.get("version", "1.0")),
            last_sync=str(data.get("last_sync", "")),
            items=items,
        )

    # Legacy nested format: migrate platforms["opencode"]["items"] → items.
    raw_platforms = data.get("platforms") or {}
    legacy_items: dict[str, ItemState] = {}
    for _name, pd in raw_platforms.items():
        if not isinstance(pd, dict):
            continue
        raw_items = pd.get("items") or {}
        for key, item_data in raw_items.items():
            if isinstance(item_data, dict) and key not in legacy_items:
                legacy_items[key] = _parse_item_state(item_data)

    return SyncState(
        version=str(data.get("version", "1.0")),
        last_sync=str(data.get("last_sync", "")),
        items=legacy_items,
    )


def _serialize_item_state(item: ItemState) -> dict[str, str]:
    """Convert an ItemState to a YAML-serializable dictionary."""
    return {"synced_at": item.synced_at} if item.synced_at else {}


def _serialize_sync_state(state: SyncState) -> dict[str, Any]:
    """Convert a SyncState into a YAML-serializable dictionary."""
    items = {key: _serialize_item_state(item) for key, item in state.items.items()}

    return {
        "version": state.version,
        "last_sync": state.last_sync,
        "items": items,
    }


def _backup_corrupted_state(state_file: Path) -> Path:
    """Rename corrupted state file with ``.corrupted`` suffix (``.corrupted.1``, etc.).

    Preserves the broken file for debugging while allowing a fresh start.
    """
    backup = Path(f"{state_file}.corrupted")
    counter = 1
    while backup.exists():
        backup = Path(f"{state_file}.corrupted.{counter}")
        counter += 1

    try:
        state_file.rename(backup)
        logger.info("Corrupted state backed up to '%s'", backup)
    except OSError as exc:
        logger.error("Failed to backup corrupted state '%s': %s", state_file, exc)
    return backup


def get_state_path(repo_path: Path) -> Path:
    """Return the path to ``.agentfiles.state.yaml`` within *repo_path*."""
    return repo_path / _STATE_FILENAME
