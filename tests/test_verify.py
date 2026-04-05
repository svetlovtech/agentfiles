"""Tests for agentfiles verify command — CI-friendly checksum verification."""

from __future__ import annotations

import json
import os
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import pytest

from syncode.cli import (
    _SHORT_HASH_LEN,
    _build_verify_items,
    _print_verify_text,
    cmd_verify,
)
from syncode.models import (
    DiffEntry,
    DiffStatus,
    Item,
    ItemType,
    Platform,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def fake_home(tmp_path: Path) -> SimpleNamespace:
    """Create a fake home directory with platform configs."""
    home = tmp_path / "home"
    home.mkdir()

    oc_dir = home / ".config" / "opencode"
    (oc_dir / "agents").mkdir(parents=True)
    (oc_dir / "skills").mkdir(parents=True)

    cc_dir = home / ".claude"
    (cc_dir / "agents").mkdir(parents=True)
    (cc_dir / "skills").mkdir(parents=True)

    return SimpleNamespace(home=home, opencode=oc_dir, claude=cc_dir)


def _make_item(
    item_type: ItemType = ItemType.AGENT,
    name: str = "test-item",
    platforms: tuple[Platform, ...] = (Platform.OPENCODE, Platform.CLAUDE_CODE),
    checksum: str = "",
    source_path: Path | None = None,
) -> Item:
    """Create a minimal Item for testing."""
    return Item(
        item_type=item_type,
        name=name,
        source_path=source_path or Path("/src") / item_type.plural / name,
        supported_platforms=platforms,
        checksum=checksum,
    )


def _make_diff_entry(
    status: DiffStatus,
    item: Item | None = None,
    source_checksum: str = "",
    target_checksum: str = "",
) -> DiffEntry:
    """Create a DiffEntry for testing."""
    return DiffEntry(
        item=item or _make_item(),
        status=status,
        source_checksum=source_checksum,
        target_checksum=target_checksum,
    )


# ---------------------------------------------------------------------------
# _build_verify_items
# ---------------------------------------------------------------------------


class TestBuildVerifyItems:
    """Tests for the _build_verify_items helper."""

    def test_empty_diff_results(self) -> None:
        """Empty diff results produce an empty list."""
        result = _build_verify_items({})
        assert result == []

    def test_matching_items_classified_correctly(self) -> None:
        """UNCHANGED entries become 'matching'."""
        item = _make_item(name="coder")
        diff_results = {
            Platform.OPENCODE: [
                _make_diff_entry(DiffStatus.UNCHANGED, item, source_checksum="a" * 64),
            ],
        }
        result = _build_verify_items(diff_results)
        assert len(result) == 1
        assert result[0]["status"] == "matching"
        assert result[0]["key"] == "agent/coder"
        assert result[0]["platforms"] == ["opencode"]

    def test_new_items_classified_as_missing(self) -> None:
        """NEW entries become 'missing'."""
        item = _make_item(name="missing-agent")
        diff_results = {
            Platform.OPENCODE: [
                _make_diff_entry(DiffStatus.NEW, item),
            ],
        }
        result = _build_verify_items(diff_results)
        assert len(result) == 1
        assert result[0]["status"] == "missing"

    def test_updated_items_classified_as_drift(self) -> None:
        """UPDATED entries become 'drift' with abbreviated hashes."""
        item = _make_item(name="drifted-agent")
        src_hash = "a1b2c3d4e5f6a7b8" + "0" * 48
        tgt_hash = "d4e5f6a7b8c9d0e1" + "0" * 48
        diff_results = {
            Platform.OPENCODE: [
                _make_diff_entry(
                    DiffStatus.UPDATED,
                    item,
                    source_checksum=src_hash,
                    target_checksum=tgt_hash,
                ),
            ],
        }
        result = _build_verify_items(diff_results)
        assert len(result) == 1
        assert result[0]["status"] == "drift"
        assert result[0]["source_hash"] == src_hash[:_SHORT_HASH_LEN]
        assert result[0]["target_hash"] == tgt_hash[:_SHORT_HASH_LEN]

    def test_deleted_items_classified_as_drift(self) -> None:
        """DELETED entries also become 'drift'."""
        item = _make_item(name="deleted-agent")
        diff_results = {
            Platform.OPENCODE: [
                _make_diff_entry(
                    DiffStatus.DELETED,
                    item,
                    source_checksum="x" * 64,
                ),
            ],
        }
        result = _build_verify_items(diff_results)
        assert len(result) == 1
        assert result[0]["status"] == "drift"

    def test_multi_platform_deduplication(self) -> None:
        """Same item on multiple platforms produces separate records."""
        item = _make_item(name="shared-agent")
        diff_results = {
            Platform.OPENCODE: [
                _make_diff_entry(DiffStatus.UNCHANGED, item),
            ],
            Platform.CLAUDE_CODE: [
                _make_diff_entry(DiffStatus.UNCHANGED, item),
            ],
        }
        result = _build_verify_items(diff_results)
        assert len(result) == 2
        assert result[0]["platforms"] == ["opencode"]
        assert result[1]["platforms"] == ["claude_code"]

    def test_results_sorted_by_key(self) -> None:
        """Output is sorted by key for deterministic ordering."""
        item_a = _make_item(name="alpha")
        item_z = _make_item(name="zeta")
        diff_results = {
            Platform.OPENCODE: [
                _make_diff_entry(DiffStatus.UNCHANGED, item_z),
                _make_diff_entry(DiffStatus.UNCHANGED, item_a),
            ],
        }
        result = _build_verify_items(diff_results)
        assert result[0]["key"] == "agent/alpha"
        assert result[1]["key"] == "agent/zeta"

    def test_drift_without_source_checksum(self) -> None:
        """Drift record with no source checksum omits hash fields."""
        item = _make_item(name="no-hash")
        diff_results = {
            Platform.OPENCODE: [
                _make_diff_entry(
                    DiffStatus.UPDATED,
                    item,
                    source_checksum="",
                    target_checksum="b" * 64,
                ),
            ],
        }
        result = _build_verify_items(diff_results)
        assert result[0]["status"] == "drift"
        assert "source_hash" not in result[0]
        assert "target_hash" not in result[0]


# ---------------------------------------------------------------------------
# _print_verify_text
# ---------------------------------------------------------------------------


class TestPrintVerifyText:
    """Tests for _print_verify_text output formatting."""

    def test_all_matching(self, capsys: pytest.CaptureFixture[str]) -> None:
        """All matching items produces clean summary."""
        items = [
            {"key": "agent/coder", "status": "matching", "platforms": ["opencode"]},
            {"key": "skill/reviewer", "status": "matching", "platforms": ["claude_code"]},
        ]
        with mock.patch.dict(os.environ, {"NO_COLOR": "1"}):
            _print_verify_text(items, 2, 0, 0)
        output = capsys.readouterr().out
        assert "agentfiles verify" in output
        assert "checksums match" in output
        assert "2 items verified, 0 drift, 0 missing" in output
        assert "Exit code: 0" in output

    def test_drift_and_missing(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Drift and missing items show correct details."""
        src_hash = "a1b2c3d4"
        tgt_hash = "d4e5f6a7"
        items = [
            {"key": "agent/coder", "status": "matching", "platforms": ["opencode"]},
            {
                "key": "agent/reviewer",
                "status": "drift",
                "platforms": ["claude_code"],
                "source_hash": src_hash,
                "target_hash": tgt_hash,
            },
            {"key": "skill/missing", "status": "missing", "platforms": ["opencode"]},
        ]
        with mock.patch.dict(os.environ, {"NO_COLOR": "1"}):
            _print_verify_text(items, 1, 1, 1)
        output = capsys.readouterr().out
        assert "DRIFT DETECTED" in output
        assert src_hash in output
        assert tgt_hash in output
        assert "NOT INSTALLED" in output
        assert "1 items verified, 1 drift, 1 missing" in output
        assert "Exit code: 1" in output


# ---------------------------------------------------------------------------
# _SHORT_HASH_LEN
# ---------------------------------------------------------------------------


class TestShortHashLen:
    """Verify the constant is sane."""

    def test_value(self) -> None:
        assert _SHORT_HASH_LEN == 8


# ---------------------------------------------------------------------------
# cmd_verify integration
# ---------------------------------------------------------------------------


class TestCmdVerifyIntegration:
    """Integration tests for the full cmd_verify pipeline.

    These tests mock out the heavy dependencies (scanner, differ, config)
    to test the verify command's control flow in isolation.

    Because the codebase uses deferred (function-scope) imports,
    we must patch at the source module (e.g. ``syncode.config.SyncodeConfig``)
    rather than ``syncode.cli.SyncodeConfig``.
    """

    def _make_args(
        self,
        *,
        quiet: bool = False,
        fmt: str = "text",
        source: str | None = None,
        target: str | None = None,
        item_type: str | None = None,
        config: Path | None = None,
        cache_dir: str | None = None,
    ) -> SimpleNamespace:
        """Create a mock argparse.Namespace for cmd_verify."""
        return SimpleNamespace(
            quiet=quiet,
            format=fmt,
            source=source,
            target=target,
            item_type=item_type,
            config=config,
            cache_dir=cache_dir,
        )

    @mock.patch("syncode.cli._discover_targets")
    @mock.patch("syncode.cli._resolve_platforms")
    @mock.patch("syncode.cli._scan_filtered")
    @mock.patch("syncode.cli._resolve_item_types")
    @mock.patch("syncode.cli._get_source")
    @mock.patch("syncode.config.SyncodeConfig.load")
    def test_quiet_mode_clean(
        self,
        mock_config_load: mock.MagicMock,
        mock_get_source: mock.MagicMock,
        mock_resolve_types: mock.MagicMock,
        mock_scan: mock.MagicMock,
        mock_resolve_platforms: mock.MagicMock,
        mock_discover: mock.MagicMock,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Quiet mode with no issues exits 0 and produces no output."""
        mock_config_load.return_value = mock.MagicMock(cache_dir=None)
        mock_get_source.return_value = tmp_path
        mock_resolve_types.return_value = [ItemType.AGENT]
        mock_scan.return_value = []

        args = self._make_args(quiet=True)
        result = cmd_verify(args)

        assert result == 0
        captured = capsys.readouterr()
        assert captured.out == ""

    @mock.patch("syncode.cli._discover_targets")
    @mock.patch("syncode.cli._resolve_platforms")
    @mock.patch("syncode.cli._scan_filtered")
    @mock.patch("syncode.cli._resolve_item_types")
    @mock.patch("syncode.cli._get_source")
    @mock.patch("syncode.config.SyncodeConfig.load")
    def test_quiet_mode_with_drift(
        self,
        mock_config_load: mock.MagicMock,
        mock_get_source: mock.MagicMock,
        mock_resolve_types: mock.MagicMock,
        mock_scan: mock.MagicMock,
        mock_resolve_platforms: mock.MagicMock,
        mock_discover: mock.MagicMock,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Quiet mode with drift exits 1 and produces no output."""
        mock_config_load.return_value = mock.MagicMock(cache_dir=None)
        mock_get_source.return_value = tmp_path
        mock_resolve_types.return_value = [ItemType.AGENT]
        item = _make_item(name="drifted")
        mock_scan.return_value = [item]
        mock_resolve_platforms.return_value = [Platform.OPENCODE]

        mock_discover.return_value = mock.MagicMock()

        diff_results = {
            Platform.OPENCODE: [
                _make_diff_entry(
                    DiffStatus.UPDATED,
                    item,
                    source_checksum="a" * 64,
                    target_checksum="b" * 64,
                ),
            ],
        }

        args = self._make_args(quiet=True)
        with mock.patch("syncode.differ.Differ") as mock_differ_cls:
            mock_differ_cls.return_value.diff.return_value = diff_results
            result = cmd_verify(args)

        assert result == 1
        captured = capsys.readouterr()
        assert captured.out == ""

    @mock.patch("syncode.cli._discover_targets")
    @mock.patch("syncode.cli._resolve_platforms")
    @mock.patch("syncode.cli._scan_filtered")
    @mock.patch("syncode.cli._resolve_item_types")
    @mock.patch("syncode.cli._get_source")
    @mock.patch("syncode.config.SyncodeConfig.load")
    def test_json_output_all_clean(
        self,
        mock_config_load: mock.MagicMock,
        mock_get_source: mock.MagicMock,
        mock_resolve_types: mock.MagicMock,
        mock_scan: mock.MagicMock,
        mock_resolve_platforms: mock.MagicMock,
        mock_discover: mock.MagicMock,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """JSON output with all matching items has correct structure."""
        mock_config_load.return_value = mock.MagicMock(cache_dir=None)
        mock_get_source.return_value = tmp_path
        mock_resolve_types.return_value = [ItemType.AGENT]
        item = _make_item(name="coder")
        mock_scan.return_value = [item]
        mock_resolve_platforms.return_value = [Platform.OPENCODE]
        mock_discover.return_value = mock.MagicMock()

        diff_results = {
            Platform.OPENCODE: [
                _make_diff_entry(
                    DiffStatus.UNCHANGED,
                    item,
                    source_checksum="c" * 64,
                ),
            ],
        }

        args = self._make_args(fmt="json")
        with mock.patch("syncode.differ.Differ") as mock_differ_cls:
            mock_differ_cls.return_value.diff.return_value = diff_results
            result = cmd_verify(args)

        assert result == 0
        captured = capsys.readouterr().out
        payload = json.loads(captured)

        assert payload["total"] == 1
        assert payload["matching"] == 1
        assert payload["drift"] == 0
        assert payload["missing"] == 0
        assert payload["items"][0]["key"] == "agent/coder"
        assert payload["items"][0]["status"] == "matching"

    @mock.patch("syncode.cli._discover_targets")
    @mock.patch("syncode.cli._resolve_platforms")
    @mock.patch("syncode.cli._scan_filtered")
    @mock.patch("syncode.cli._resolve_item_types")
    @mock.patch("syncode.cli._get_source")
    @mock.patch("syncode.config.SyncodeConfig.load")
    def test_json_output_mixed_statuses(
        self,
        mock_config_load: mock.MagicMock,
        mock_get_source: mock.MagicMock,
        mock_resolve_types: mock.MagicMock,
        mock_scan: mock.MagicMock,
        mock_resolve_platforms: mock.MagicMock,
        mock_discover: mock.MagicMock,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """JSON output with matching, drift, and missing items."""
        mock_config_load.return_value = mock.MagicMock(cache_dir=None)
        mock_get_source.return_value = tmp_path
        mock_resolve_types.return_value = [ItemType.AGENT]
        item_match = _make_item(name="coder")
        item_drift = _make_item(name="reviewer")
        item_miss = _make_item(name="missing")
        mock_scan.return_value = [item_match, item_drift, item_miss]
        mock_resolve_platforms.return_value = [Platform.OPENCODE]
        mock_discover.return_value = mock.MagicMock()

        diff_results = {
            Platform.OPENCODE: [
                _make_diff_entry(
                    DiffStatus.UNCHANGED,
                    item_match,
                    source_checksum="c" * 64,
                ),
                _make_diff_entry(
                    DiffStatus.UPDATED,
                    item_drift,
                    source_checksum="a1b2c3d4" + "0" * 56,
                    target_checksum="d4e5f6a7" + "0" * 56,
                ),
                _make_diff_entry(DiffStatus.NEW, item_miss),
            ],
        }

        args = self._make_args(fmt="json")
        with mock.patch("syncode.differ.Differ") as mock_differ_cls:
            mock_differ_cls.return_value.diff.return_value = diff_results
            result = cmd_verify(args)

        assert result == 1
        payload = json.loads(capsys.readouterr().out)

        assert payload["total"] == 3
        assert payload["matching"] == 1
        assert payload["drift"] == 1
        assert payload["missing"] == 1

        # Verify drift item has abbreviated hashes.
        drift_item = next(i for i in payload["items"] if i["status"] == "drift")
        assert drift_item["source_hash"] == "a1b2c3d4"
        assert drift_item["target_hash"] == "d4e5f6a7"

    @mock.patch("syncode.cli._discover_targets")
    @mock.patch("syncode.cli._resolve_platforms")
    @mock.patch("syncode.cli._scan_filtered")
    @mock.patch("syncode.cli._resolve_item_types")
    @mock.patch("syncode.cli._get_source")
    @mock.patch("syncode.config.SyncodeConfig.load")
    def test_text_output_all_clean(
        self,
        mock_config_load: mock.MagicMock,
        mock_get_source: mock.MagicMock,
        mock_resolve_types: mock.MagicMock,
        mock_scan: mock.MagicMock,
        mock_resolve_platforms: mock.MagicMock,
        mock_discover: mock.MagicMock,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Text output with all matching shows exit code 0."""
        mock_config_load.return_value = mock.MagicMock(cache_dir=None)
        mock_get_source.return_value = tmp_path
        mock_resolve_types.return_value = [ItemType.AGENT]
        item = _make_item(name="coder")
        mock_scan.return_value = [item]
        mock_resolve_platforms.return_value = [Platform.OPENCODE]
        mock_discover.return_value = mock.MagicMock()

        diff_results = {
            Platform.OPENCODE: [
                _make_diff_entry(
                    DiffStatus.UNCHANGED,
                    item,
                    source_checksum="x" * 64,
                ),
            ],
        }

        args = self._make_args(fmt="text")
        with (
            mock.patch("syncode.differ.Differ") as mock_differ_cls,
            mock.patch.dict(os.environ, {"NO_COLOR": "1"}),
        ):
            mock_differ_cls.return_value.diff.return_value = diff_results
            result = cmd_verify(args)

        assert result == 0
        output = capsys.readouterr().out
        assert "agent/coder" in output
        assert "checksums match" in output
        assert "Exit code: 0" in output

    @mock.patch("syncode.cli._discover_targets")
    @mock.patch("syncode.cli._resolve_platforms")
    @mock.patch("syncode.cli._scan_filtered")
    @mock.patch("syncode.cli._resolve_item_types")
    @mock.patch("syncode.cli._get_source")
    @mock.patch("syncode.config.SyncodeConfig.load")
    def test_text_output_with_drift(
        self,
        mock_config_load: mock.MagicMock,
        mock_get_source: mock.MagicMock,
        mock_resolve_types: mock.MagicMock,
        mock_scan: mock.MagicMock,
        mock_resolve_platforms: mock.MagicMock,
        mock_discover: mock.MagicMock,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Text output with drift shows exit code 1."""
        mock_config_load.return_value = mock.MagicMock(cache_dir=None)
        mock_get_source.return_value = tmp_path
        mock_resolve_types.return_value = [ItemType.AGENT]
        item = _make_item(name="reviewer")
        mock_scan.return_value = [item]
        mock_resolve_platforms.return_value = [Platform.OPENCODE]
        mock_discover.return_value = mock.MagicMock()

        diff_results = {
            Platform.OPENCODE: [
                _make_diff_entry(
                    DiffStatus.UPDATED,
                    item,
                    source_checksum="a1b2c3d4" + "0" * 56,
                    target_checksum="d4e5f6a7" + "0" * 56,
                ),
            ],
        }

        args = self._make_args(fmt="text")
        with (
            mock.patch("syncode.differ.Differ") as mock_differ_cls,
            mock.patch.dict(os.environ, {"NO_COLOR": "1"}),
        ):
            mock_differ_cls.return_value.diff.return_value = diff_results
            result = cmd_verify(args)

        assert result == 1
        output = capsys.readouterr().out
        assert "DRIFT DETECTED" in output
        assert "a1b2c3d4" in output
        assert "d4e5f6a7" in output
        assert "Exit code: 1" in output
