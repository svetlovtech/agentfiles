"""Tests for bidirectional conflict detection during push."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from agentfiles.config import save_sync_state
from agentfiles.engine import (
    PushConflict,
    SyncTarget,
    detect_push_conflicts,
)
from agentfiles.models import (
    Item,
    ItemState,
    ItemType,
    Platform,
    PlatformState,
    SyncState,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_item(
    name: str = "coder",
    item_type: ItemType = ItemType.AGENT,
    source_path: Path | None = None,
) -> Item:
    return Item(
        item_type=item_type,
        name=name,
        source_path=source_path or Path("/tmp/agents") / f"{name}.md",
        files=(f"{name}.md",),
        supported_platforms=(Platform.OPENCODE,),
    )


def _make_target_manager(
    target_dir: Path,
) -> SyncTarget:
    mgr = MagicMock(spec=SyncTarget)
    mgr.get_target_dir.return_value = target_dir
    mgr.resolve_platform_for.return_value = Platform.OPENCODE
    return mgr


def _setup_push_scenario(
    tmp_path: Path,
    *,
    source_content: str = "source content",
    target_content: str = "target content",
    synced_at: str | None = None,
) -> tuple[list[Item], Path, Path, SyncTarget]:
    """Set up source repo, target dir, state file, and item for testing.

    Returns (items, source_dir, target_dir, target_manager).
    """
    source_dir = tmp_path / "source"
    agents_dir = source_dir / "agents" / "coder"
    agents_dir.mkdir(parents=True)
    source_file = agents_dir / "coder.md"
    source_file.write_text(source_content, encoding="utf-8")

    target_dir = tmp_path / "target" / "agents"
    target_dir.mkdir(parents=True)
    target_file = target_dir / "coder.md"
    target_file.write_text(target_content, encoding="utf-8")

    item = _make_item("coder", source_path=target_file)

    if synced_at is not None:
        state = SyncState(
            last_sync=synced_at,
            platforms={
                "opencode": PlatformState(
                    path=str(target_dir),
                    items={
                        "agent/coder": ItemState(synced_at=synced_at),
                    },
                ),
            },
        )
        save_sync_state(source_dir, state)

    target_manager = _make_target_manager(target_dir)
    return [item], source_dir, target_dir, target_manager


# ---------------------------------------------------------------------------
# Tests — conflict detection
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestDetectPushConflicts:
    """Tests for detect_push_conflicts()."""

    def test_no_state_file_returns_empty(self, tmp_path: Path) -> None:
        """When no state file exists, there are no conflicts."""
        source_dir = tmp_path / "source"
        source_dir.mkdir()
        target_dir = tmp_path / "target" / "agents"
        target_dir.mkdir(parents=True)

        item = _make_item("coder")
        mgr = _make_target_manager(target_dir)

        result = detect_push_conflicts(
            [item],
            (Platform.OPENCODE,),
            source_dir,
            mgr,
        )
        assert result == []

    def test_no_last_sync_returns_empty(self, tmp_path: Path) -> None:
        """When state has no last_sync, no conflicts are detected."""
        source_dir = tmp_path / "source"
        source_dir.mkdir()
        state = SyncState(last_sync="")
        save_sync_state(source_dir, state)

        item = _make_item("coder")
        target_dir = tmp_path / "target" / "agents"
        target_dir.mkdir(parents=True)
        mgr = _make_target_manager(target_dir)

        result = detect_push_conflicts(
            [item],
            (Platform.OPENCODE,),
            source_dir,
            mgr,
        )
        assert result == []

    def test_identical_files_no_conflict(self, tmp_path: Path) -> None:
        """When source and target are identical, no conflict."""
        synced_at = datetime.now(tz=timezone.utc).isoformat()
        items, source_dir, target_dir, mgr = _setup_push_scenario(
            tmp_path,
            source_content="same content",
            target_content="same content",
            synced_at=synced_at,
        )

        result = detect_push_conflicts(
            items,
            (Platform.OPENCODE,),
            source_dir,
            mgr,
        )
        assert result == []

    def test_source_unchanged_since_sync_no_conflict(self, tmp_path: Path) -> None:
        """When only target changed (source unchanged since sync), no conflict."""
        # Use a timestamp well in the future so source mtime is before it.
        future_sync = "2099-01-01T00:00:00+00:00"
        items, source_dir, target_dir, mgr = _setup_push_scenario(
            tmp_path,
            source_content="original",
            target_content="modified locally",
            synced_at=future_sync,
        )

        result = detect_push_conflicts(
            items,
            (Platform.OPENCODE,),
            source_dir,
            mgr,
        )
        assert result == []

    def test_both_changed_is_conflict(self, tmp_path: Path) -> None:
        """When both source and target changed since sync, conflict is detected."""
        # Set sync time well in the past.
        past_sync = "2000-01-01T00:00:00+00:00"
        items, source_dir, target_dir, mgr = _setup_push_scenario(
            tmp_path,
            source_content="changed in source",
            target_content="changed locally",
            synced_at=past_sync,
        )

        result = detect_push_conflicts(
            items,
            (Platform.OPENCODE,),
            source_dir,
            mgr,
        )
        assert len(result) == 1
        assert isinstance(result[0], PushConflict)
        assert result[0].item.name == "coder"
        assert result[0].platform == Platform.OPENCODE

    def test_source_not_exists_no_conflict(self, tmp_path: Path) -> None:
        """When source repo file does not exist, it's new — not a conflict."""
        source_dir = tmp_path / "source"
        source_dir.mkdir()
        # No agents dir in source.

        target_dir = tmp_path / "target" / "agents"
        target_dir.mkdir(parents=True)
        target_file = target_dir / "coder.md"
        target_file.write_text("local content", encoding="utf-8")

        item = _make_item("coder", source_path=target_file)
        mgr = _make_target_manager(target_dir)

        state = SyncState(
            last_sync="2000-01-01T00:00:00+00:00",
            platforms={
                "opencode": PlatformState(
                    path=str(target_dir),
                    items={"agent/coder": ItemState(synced_at="2000-01-01T00:00:00+00:00")},
                ),
            },
        )
        save_sync_state(source_dir, state)

        result = detect_push_conflicts(
            [item],
            (Platform.OPENCODE,),
            source_dir,
            mgr,
        )
        assert result == []

    def test_no_item_in_state_no_conflict(self, tmp_path: Path) -> None:
        """When item has no state entry, no conflict (never synced)."""
        past_sync = "2000-01-01T00:00:00+00:00"
        items, source_dir, target_dir, mgr = _setup_push_scenario(
            tmp_path,
            source_content="changed in source",
            target_content="changed locally",
            synced_at=None,  # Don't create state for item
        )

        # Create state without the item entry.
        state = SyncState(
            last_sync=past_sync,
            platforms={
                "opencode": PlatformState(
                    path=str(target_dir),
                    items={},
                ),
            },
        )
        save_sync_state(source_dir, state)

        result = detect_push_conflicts(
            items,
            (Platform.OPENCODE,),
            source_dir,
            mgr,
        )
        assert result == []


# ---------------------------------------------------------------------------
# Tests — interactive conflict resolution
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestPromptPushConflicts:
    """Tests for InteractiveSession.prompt_push_conflicts()."""

    def test_empty_conflicts_returns_empty(self) -> None:
        from agentfiles.interactive import InteractiveSession

        session = InteractiveSession(use_colors=False)
        result = session.prompt_push_conflicts([])
        assert result == {}

    def test_keep_source_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from agentfiles.interactive import InteractiveSession

        session = InteractiveSession(use_colors=False)
        # Empty input -> default "s" -> keep-source
        inputs = iter([""])
        monkeypatch.setattr("builtins.input", lambda _: next(inputs))

        conflicts = [
            ("agent/coder", "agent", "OpenCode", Path("/src"), Path("/tgt")),
        ]
        result = session.prompt_push_conflicts(conflicts)
        assert result == {"agent/coder": "keep-source"}

    def test_keep_target_choice(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from agentfiles.interactive import InteractiveSession

        session = InteractiveSession(use_colors=False)
        inputs = iter(["t"])
        monkeypatch.setattr("builtins.input", lambda _: next(inputs))

        conflicts = [
            ("agent/coder", "agent", "OpenCode", Path("/src"), Path("/tgt")),
        ]
        result = session.prompt_push_conflicts(conflicts)
        assert result == {"agent/coder": "keep-target"}

    def test_apply_to_all(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from agentfiles.interactive import InteractiveSession

        session = InteractiveSession(use_colors=False)
        inputs = iter(["a", "t"])
        monkeypatch.setattr("builtins.input", lambda _: next(inputs))

        conflicts = [
            ("agent/coder", "agent", "OpenCode", Path("/src"), Path("/tgt")),
            ("agent/writer", "agent", "OpenCode", Path("/src2"), Path("/tgt2")),
        ]
        result = session.prompt_push_conflicts(conflicts)
        assert result == {
            "agent/coder": "keep-target",
            "agent/writer": "keep-target",
        }

    def test_show_diff_then_choose(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        from agentfiles.interactive import InteractiveSession

        session = InteractiveSession(use_colors=False)

        src = tmp_path / "src.md"
        tgt = tmp_path / "tgt.md"
        src.write_text("source line\n", encoding="utf-8")
        tgt.write_text("target line\n", encoding="utf-8")

        # First "d" to show diff, then "t" to keep target.
        inputs = iter(["d", "t"])
        monkeypatch.setattr("builtins.input", lambda _: next(inputs))

        conflicts = [
            ("agent/coder", "agent", "OpenCode", src, tgt),
        ]
        result = session.prompt_push_conflicts(conflicts)
        assert result == {"agent/coder": "keep-target"}


# ---------------------------------------------------------------------------
# Tests — cmd_push conflict integration
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestCmdPushConflictSkip:
    """Non-interactive push skips conflicts."""

    def test_non_interactive_skips_conflicts(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """In --yes mode, conflicts are skipped with a warning."""
        from agentfiles.engine import detect_push_conflicts

        past_sync = "2000-01-01T00:00:00+00:00"
        items, source_dir, target_dir, mgr = _setup_push_scenario(
            tmp_path,
            source_content="changed in source",
            target_content="changed locally",
            synced_at=past_sync,
        )

        conflicts = detect_push_conflicts(
            items,
            (Platform.OPENCODE,),
            source_dir,
            mgr,
        )
        assert len(conflicts) == 1

        # Simulate non-interactive filtering
        skip_keys = {c.item.item_key for c in conflicts}
        remaining = [i for i in items if i.item_key not in skip_keys]
        assert remaining == []
