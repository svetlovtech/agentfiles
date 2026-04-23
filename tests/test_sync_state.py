"""Tests for sync state models and I/O — SyncState load/save.

Note: ItemState dataclass tests are in test_models.py alongside other model
tests. This file focuses on SyncState I/O (load/save) and round-trip behavior.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from agentfiles.config import load_sync_state, save_sync_state
from agentfiles.models import ItemState, SyncState

# ---------------------------------------------------------------------------
# SyncState
# ---------------------------------------------------------------------------


class TestSyncState:
    """Tests for SyncState dataclass."""

    def test_default_values(self) -> None:
        state = SyncState()
        assert state.version == "1.0"
        assert state.last_sync == ""
        assert state.items == {}

    def test_mutable(self) -> None:
        """SyncState must be mutable for updates during sync."""
        state = SyncState()
        state.version = "2.0"
        state.last_sync = "2025-06-01T12:00:00Z"
        state.items["agent/coder"] = ItemState(synced_at="2025-01-01T00:00:00Z")
        assert state.version == "2.0"
        assert state.last_sync == "2025-06-01T12:00:00Z"
        assert "agent/coder" in state.items

    def test_default_factory_isolation(self) -> None:
        """Each instance gets its own items dict."""
        a = SyncState()
        b = SyncState()
        a.items["test"] = ItemState()
        assert "test" not in b.items

    def test_with_items(self) -> None:
        items = {
            "skill/reviewer": ItemState(synced_at="2025-01-01T00:00:00Z"),
            "agent/coder": ItemState(synced_at="2025-01-02T00:00:00Z"),
        }
        state = SyncState(version="1.0", items=items)
        assert "skill/reviewer" in state.items
        assert "agent/coder" in state.items


# ---------------------------------------------------------------------------
# load_sync_state
# ---------------------------------------------------------------------------


class TestLoadSyncState:
    """Tests for load_sync_state function."""

    def test_returns_empty_state_when_no_file(self, tmp_path: Path) -> None:
        state = load_sync_state(tmp_path)
        assert state.version == "1.0"
        assert state.last_sync == ""
        assert state.items == {}

    def test_loads_valid_state_file(self, tmp_path: Path) -> None:
        state_data = {
            "version": "1.0",
            "last_sync": "2025-06-01T12:00:00Z",
            "items": {
                "agent/coder": {
                    "synced_at": "2025-06-01T11:00:00Z",
                },
            },
        }
        state_file = tmp_path / ".agentfiles.state.yaml"
        state_file.write_text(yaml.dump(state_data), encoding="utf-8")

        state = load_sync_state(tmp_path)
        assert state.version == "1.0"
        assert state.last_sync == "2025-06-01T12:00:00Z"
        assert "agent/coder" in state.items

        item = state.items["agent/coder"]
        assert item.synced_at == "2025-06-01T11:00:00Z"

    def test_loads_empty_state_file(self, tmp_path: Path) -> None:
        state_file = tmp_path / ".agentfiles.state.yaml"
        state_file.write_text("# empty\n", encoding="utf-8")

        state = load_sync_state(tmp_path)
        assert state.version == "1.0"
        assert state.items == {}

    def test_loads_state_with_empty_items(self, tmp_path: Path) -> None:
        state_data = {
            "version": "1.0",
            "items": {},
        }
        state_file = tmp_path / ".agentfiles.state.yaml"
        state_file.write_text(yaml.dump(state_data), encoding="utf-8")

        state = load_sync_state(tmp_path)
        assert state.items == {}

    def test_skips_non_dict_item_data(self, tmp_path: Path) -> None:
        state_data = {
            "version": "1.0",
            "items": {"agent/bad": "not_a_dict"},
        }
        state_file = tmp_path / ".agentfiles.state.yaml"
        state_file.write_text(yaml.dump(state_data), encoding="utf-8")

        state = load_sync_state(tmp_path)
        assert "agent/bad" not in state.items

    def test_handles_missing_item_fields(self, tmp_path: Path) -> None:
        state_data = {
            "version": "1.0",
            "items": {"agent/minimal": {}},
        }
        state_file = tmp_path / ".agentfiles.state.yaml"
        state_file.write_text(yaml.dump(state_data), encoding="utf-8")

        state = load_sync_state(tmp_path)
        item = state.items["agent/minimal"]
        assert item.synced_at == ""

    def test_loads_legacy_platforms_format(self, tmp_path: Path) -> None:
        """Legacy state files with 'platforms' key are migrated to flat 'items'."""
        state_data = {
            "version": "1.0",
            "last_sync": "2025-06-01T12:00:00Z",
            "platforms": {
                "opencode": {
                    "path": "/home/user/.config/opencode",
                    "items": {
                        "agent/coder": {
                            "synced_at": "2025-06-01T11:00:00Z",
                        },
                    },
                },
            },
        }
        state_file = tmp_path / ".agentfiles.state.yaml"
        state_file.write_text(yaml.dump(state_data), encoding="utf-8")

        state = load_sync_state(tmp_path)
        assert state.version == "1.0"
        assert "agent/coder" in state.items
        assert state.items["agent/coder"].synced_at == "2025-06-01T11:00:00Z"


# ---------------------------------------------------------------------------
# save_sync_state
# ---------------------------------------------------------------------------


class TestSaveSyncState:
    """Tests for save_sync_state function."""

    def test_creates_state_file(self, tmp_path: Path) -> None:
        state = SyncState()
        save_sync_state(tmp_path, state)

        state_file = tmp_path / ".agentfiles.state.yaml"
        assert state_file.is_file()

    def test_file_has_header_comments(self, tmp_path: Path) -> None:
        state = SyncState()
        save_sync_state(tmp_path, state)

        content = (tmp_path / ".agentfiles.state.yaml").read_text(encoding="utf-8")
        assert "auto-generated" in content
        assert "agentfiles pull" in content

    def test_saves_empty_state(self, tmp_path: Path) -> None:
        state = SyncState()
        save_sync_state(tmp_path, state)

        content = (tmp_path / ".agentfiles.state.yaml").read_text(encoding="utf-8")
        loaded = yaml.safe_load(content)
        assert loaded["version"] == "1.0"
        assert loaded["last_sync"] == ""

    def test_saves_full_state(self, tmp_path: Path) -> None:
        state = SyncState(
            version="1.0",
            last_sync="2025-06-01T12:00:00Z",
            items={
                "agent/coder": ItemState(
                    synced_at="2025-06-01T11:00:00Z",
                ),
            },
        )
        save_sync_state(tmp_path, state)

        content = (tmp_path / ".agentfiles.state.yaml").read_text(encoding="utf-8")
        loaded = yaml.safe_load(content)
        assert loaded["version"] == "1.0"
        assert loaded["last_sync"] == "2025-06-01T12:00:00Z"
        assert "items" in loaded

        item = loaded["items"]["agent/coder"]
        assert item["synced_at"] == "2025-06-01T11:00:00Z"


# ---------------------------------------------------------------------------
# Round-trip (save → load)
# ---------------------------------------------------------------------------


class TestSyncStateRoundTrip:
    """Tests for save then load round-trip consistency."""

    def test_round_trip_empty_state(self, tmp_path: Path) -> None:
        original = SyncState()
        save_sync_state(tmp_path, original)
        loaded = load_sync_state(tmp_path)

        assert loaded.version == original.version
        assert loaded.last_sync == original.last_sync
        assert loaded.items == original.items

    def test_round_trip_full_state(self, tmp_path: Path) -> None:
        original = SyncState(
            version="1.0",
            last_sync="2025-06-01T12:00:00Z",
            items={
                "agent/coder": ItemState(
                    synced_at="2025-06-01T11:00:00Z",
                ),
                "skill/reviewer": ItemState(
                    synced_at="2025-06-01T10:00:00Z",
                ),
            },
        )
        save_sync_state(tmp_path, original)
        loaded = load_sync_state(tmp_path)

        assert loaded.version == original.version
        assert loaded.last_sync == original.last_sync
        assert set(loaded.items.keys()) == {"agent/coder", "skill/reviewer"}

        item = loaded.items["agent/coder"]
        assert item.synced_at == "2025-06-01T11:00:00Z"

    def test_round_trip_preserves_multiple_items(self, tmp_path: Path) -> None:
        """Round-trip preserves all items with their timestamps."""
        original = SyncState(
            version="1.0",
            last_sync="2025-09-01T08:00:00Z",
            items={
                "agent/coder": ItemState(
                    synced_at="2025-09-01T08:00:00Z",
                ),
                "skill/reviewer": ItemState(
                    synced_at="2025-09-01T07:00:00Z",
                ),
                "command/build": ItemState(
                    synced_at="2025-09-01T06:00:00Z",
                ),
            },
        )
        save_sync_state(tmp_path, original)
        loaded = load_sync_state(tmp_path)

        assert loaded == original

    def test_round_trip_with_empty_items(self, tmp_path: Path) -> None:
        """Round-trip preserves state with empty items dict."""
        original = SyncState(items={})
        save_sync_state(tmp_path, original)
        loaded = load_sync_state(tmp_path)

        assert loaded.items == {}


# ---------------------------------------------------------------------------
# Sync state save/load roundtrip — edge cases
# ---------------------------------------------------------------------------


class TestSyncStateRoundTripEdgeCases:
    """Edge cases for sync state save/load roundtrips."""

    def test_roundtrip_with_special_characters_in_hashes(self, tmp_path: Path) -> None:
        """Long synced_at values survive save/load roundtrip."""
        long_ts = "2025-12-31T23:59:59.123456Z"
        original = SyncState(
            items={
                "agent/special": ItemState(
                    synced_at=long_ts,
                ),
            },
        )
        save_sync_state(tmp_path, original)
        loaded = load_sync_state(tmp_path)

        assert loaded.items["agent/special"].synced_at == long_ts

    def test_roundtrip_with_slash_in_item_key(self, tmp_path: Path) -> None:
        """Item keys containing slashes survive roundtrip."""
        original = SyncState(
            items={
                "agent/coder": ItemState(synced_at="2025-01-01T00:00:00Z"),
                "skill/python-reviewer": ItemState(synced_at="2025-01-02T00:00:00Z"),
                "command/build": ItemState(synced_at="2025-01-03T00:00:00Z"),
            },
        )
        save_sync_state(tmp_path, original)
        loaded = load_sync_state(tmp_path)

        assert set(loaded.items.keys()) == {
            "agent/coder",
            "skill/python-reviewer",
            "command/build",
        }

    def test_overwrite_existing_state(self, tmp_path: Path) -> None:
        """Saving state overwrites an existing state file."""
        # Save initial state
        initial = SyncState(last_sync="2025-01-01T00:00:00Z")
        save_sync_state(tmp_path, initial)

        # Save updated state
        updated = SyncState(
            last_sync="2025-06-15T12:00:00Z",
            items={"agent/coder": ItemState(synced_at="2025-06-15T12:00:00Z")},
        )
        save_sync_state(tmp_path, updated)

        loaded = load_sync_state(tmp_path)
        assert loaded.last_sync == "2025-06-15T12:00:00Z"
        assert loaded.items["agent/coder"].synced_at == "2025-06-15T12:00:00Z"

    def test_state_file_is_valid_yaml(self, tmp_path: Path) -> None:
        """The saved state file is valid YAML that can be parsed externally."""
        original = SyncState(
            version="1.0",
            last_sync="2025-07-01T00:00:00Z",
            items={"agent/coder": ItemState(synced_at="2025-07-01T00:00:00Z")},
        )
        save_sync_state(tmp_path, original)

        content = (tmp_path / ".agentfiles.state.yaml").read_text(encoding="utf-8")
        parsed = yaml.safe_load(content)

        assert isinstance(parsed, dict)
        assert parsed["version"] == "1.0"
        assert parsed["last_sync"] == "2025-07-01T00:00:00Z"


# ---------------------------------------------------------------------------
# Corrupted state recovery — additional edge cases
# ---------------------------------------------------------------------------


class TestSyncStateRecoveryEdgeCases:
    """Additional edge cases for corrupted state recovery."""

    def test_load_state_after_save_delete_cycle(self, tmp_path: Path) -> None:
        """Loading state after the file is deleted returns empty SyncState."""
        state = SyncState(last_sync="2025-01-01T00:00:00Z")
        save_sync_state(tmp_path, state)

        # Delete the file manually
        state_file = tmp_path / ".agentfiles.state.yaml"
        assert state_file.exists()
        state_file.unlink()

        loaded = load_sync_state(tmp_path)
        assert loaded == SyncState()

    def test_save_after_corruption_recovery(self, tmp_path: Path) -> None:
        """Saving after corruption recovery works without errors."""
        state_file = tmp_path / ".agentfiles.state.yaml"
        state_file.write_text("\x00corrupted", encoding="utf-8")

        # Trigger recovery
        load_sync_state(tmp_path)

        # Now save a valid state
        new_state = SyncState(last_sync="2025-08-01T00:00:00Z")
        save_sync_state(tmp_path, new_state)

        loaded = load_sync_state(tmp_path)
        assert loaded.last_sync == "2025-08-01T00:00:00Z"

    def test_load_state_with_unexpected_yaml_structure(self, tmp_path: Path) -> None:
        """A state file with unexpected but valid YAML returns empty state."""
        state_data = {
            "items": {
                "agent/bad": ["not", "a", "dict"],
            },
        }
        state_file = tmp_path / ".agentfiles.state.yaml"
        state_file.write_text(yaml.dump(state_data), encoding="utf-8")

        state = load_sync_state(tmp_path)
        # Non-dict item data is skipped
        assert "agent/bad" not in state.items

    def test_load_state_with_null_items(self, tmp_path: Path) -> None:
        """A state file with null items returns empty items dict."""
        state_data = {"version": "1.0", "items": None}
        state_file = tmp_path / ".agentfiles.state.yaml"
        state_file.write_text(yaml.dump(state_data), encoding="utf-8")

        state = load_sync_state(tmp_path)
        assert state.items == {}
