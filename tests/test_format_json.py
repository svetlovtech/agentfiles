"""Tests for --format json support across CLI commands.

Covers JSON output for: status, pull (dry-run), push (dry-run).
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from agentfiles.cli import (
    _format_plan_json,
    _format_results_json,
    _format_status_json,
)
from agentfiles.engine import SyncReport
from agentfiles.models import (
    Item,
    ItemType,
    TARGET_PLATFORM,
    SyncAction,
    SyncPlan,
    SyncResult,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_item(
    name: str = "test-agent",
    item_type: ItemType = ItemType.AGENT,
) -> Item:
    """Create a minimal Item for testing."""
    return Item(
        item_type=item_type,
        name=name,
        source_path=Path(f"/fake/{item_type.plural}/{name}.md"),
        version="1.0.0",
        files=("file.md",),
    )


def _make_plan(
    item: Item | None = None,
    action: SyncAction = SyncAction.INSTALL,
    reason: str = "not installed",
) -> SyncPlan:
    """Create a minimal SyncPlan for testing."""
    if item is None:
        item = _make_item()
    return SyncPlan(
        item=item,
        action=action,
        target_dir=Path("/fake/target/agents"),
        reason=reason,
    )


def _make_result(
    plan: SyncPlan | None = None,
    is_success: bool = True,
    message: str = "Installed test-agent",
) -> SyncResult:
    """Create a minimal SyncResult for testing."""
    if plan is None:
        plan = _make_plan()
    return SyncResult(
        plan=plan,
        is_success=is_success,
        message=message,
        files_copied=1,
    )


# ---------------------------------------------------------------------------
# _format_status_json
# ---------------------------------------------------------------------------


class TestFormatStatusJson:
    """Tests for _format_status_json."""

    def test_basic_output_structure(self, capsys: pytest.CaptureFixture[str]) -> None:
        """JSON output has item type counts and total_items."""
        target_manager = MagicMock()
        target_manager.targets = MagicMock(
            platform=TARGET_PLATFORM,
            config_dir=Path("/oc"),
        )
        summary = {"agents": 3, "skills": 5, "commands": 2, "plugins": 1}

        result = _format_status_json(target_manager, summary)
        assert result == 0

        output = json.loads(capsys.readouterr().out)
        assert "total_items" in output
        assert isinstance(output["total_items"], int)
        assert "agents" in output
        assert "skills" in output

    def test_item_counts(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Output has agents, skills, commands, plugins, and total."""
        target_manager = MagicMock()
        target_manager.targets = MagicMock(
            platform=TARGET_PLATFORM,
            config_dir=Path("/oc"),
        )
        summary = {"agents": 3, "skills": 5, "commands": 2, "plugins": 1}

        _format_status_json(target_manager, summary)

        output = json.loads(capsys.readouterr().out)
        assert output["agents"] == 3
        assert output["skills"] == 5
        assert output["commands"] == 2
        assert output["plugins"] == 1
        assert output["total_items"] == 11

    def test_missing_count_defaults_to_zero(
        self,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Missing item types default to 0 in the output."""
        target_manager = MagicMock()
        target_manager.targets = MagicMock(
            platform=TARGET_PLATFORM,
            config_dir=Path("/oc"),
        )
        summary = {}

        _format_status_json(target_manager, summary)

        output = json.loads(capsys.readouterr().out)
        assert output["agents"] == 0
        assert output["skills"] == 0
        assert output["commands"] == 0
        assert output["plugins"] == 0
        assert output["total_items"] == 0

    def test_snake_case_keys(self, capsys: pytest.CaptureFixture[str]) -> None:
        """All JSON keys use snake_case convention."""
        target_manager = MagicMock()
        target_manager.targets = None
        summary = {}

        _format_status_json(target_manager, summary)

        output = json.loads(capsys.readouterr().out)
        # Verify no camelCase or hyphenated keys
        assert set(output.keys()) == {"agents", "skills", "commands", "plugins", "total_items"}


# ---------------------------------------------------------------------------
# _format_plan_json
# ---------------------------------------------------------------------------


class TestFormatPlanJson:
    """Tests for _format_plan_json."""

    def test_dry_run_output_structure(
        self,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """JSON output has plans list, total count, and dry_run flag."""
        item = _make_item("coder", ItemType.AGENT)
        plan = _make_plan(item, SyncAction.INSTALL, "not installed")

        target_manager = MagicMock()
        target_manager.owns_target_dir.return_value = True

        result = _format_plan_json([plan], target_manager, dry_run=True)
        assert result == 0

        output = json.loads(capsys.readouterr().out)
        assert "plans" in output
        assert "total" in output
        assert output["dry_run"] is True
        assert output["total"] == 1

    def test_plan_entry_fields(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Each plan entry has item, action, and reason."""
        item = _make_item("coder", ItemType.AGENT)
        plan = _make_plan(item, SyncAction.INSTALL, "not installed")

        target_manager = MagicMock()
        target_manager.owns_target_dir.return_value = True

        _format_plan_json([plan], target_manager, dry_run=True)

        output = json.loads(capsys.readouterr().out)
        entry = output["plans"][0]
        assert entry["item"] == "agent/coder"
        assert entry["action"] == "INSTALL"
        assert entry["reason"] == "not installed"

    def test_action_uppercase(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Actions are always uppercase in JSON output."""
        item = _make_item("old-agent", ItemType.AGENT)
        plan = _make_plan(item, SyncAction.UPDATE, "content differs")

        target_manager = MagicMock()
        target_manager.owns_target_dir.return_value = True

        _format_plan_json([plan], target_manager, dry_run=False)

        output = json.loads(capsys.readouterr().out)
        assert output["plans"][0]["action"] == "UPDATE"
        assert output["dry_run"] is False

    def test_skip_actions_excluded(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Plans with SKIP action are excluded from JSON output."""
        install_plan = _make_plan(
            _make_item("new-agent"),
            SyncAction.INSTALL,
            "not installed",
        )
        skip_plan = _make_plan(
            _make_item("up-to-date-agent"),
            SyncAction.SKIP,
            "already up-to-date",
        )

        target_manager = MagicMock()
        target_manager.owns_target_dir.return_value = True

        _format_plan_json([install_plan, skip_plan], target_manager, dry_run=True)

        output = json.loads(capsys.readouterr().out)
        assert output["total"] == 1
        assert output["plans"][0]["item"] == "agent/new-agent"

    def test_single_platform_plan(
        self,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Plans for the same item+action are recorded."""
        item = _make_item("shared-agent")
        plan1 = SyncPlan(
            item=item,
            action=SyncAction.INSTALL,
            target_dir=Path("/fake/oc/agents"),
            reason="not installed",
        )

        target_manager = MagicMock()
        target_manager.owns_target_dir.return_value = True

        _format_plan_json([plan1], target_manager, dry_run=True)

        output = json.loads(capsys.readouterr().out)
        assert output["total"] == 1
        assert output["plans"][0]["item"] == "agent/shared-agent"

    def test_empty_plans(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Empty plan list produces valid JSON with total 0."""
        target_manager = MagicMock()

        _format_plan_json([], target_manager, dry_run=True)

        output = json.loads(capsys.readouterr().out)
        assert output["plans"] == []
        assert output["total"] == 0
        assert output["dry_run"] is True


# ---------------------------------------------------------------------------
# _format_results_json
# ---------------------------------------------------------------------------


class TestFormatResultsJson:
    """Tests for _format_results_json."""

    def test_basic_output_structure(
        self,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """JSON output has results list, summary, and dry_run flag."""
        plan = _make_plan()
        result = _make_result(plan)
        report = SyncReport(installed=[result])

        exit_code = _format_results_json([result], report, dry_run=False)
        assert exit_code == 0

        output = json.loads(capsys.readouterr().out)
        assert "results" in output
        assert "summary" in output
        assert output["dry_run"] is False

    def test_result_entry_fields(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Each result entry has item, action, status, message, files_copied."""
        plan = _make_plan()
        result = _make_result(plan, is_success=True, message="Installed test-agent")
        report = SyncReport(installed=[result])

        _format_results_json([result], report, dry_run=False)

        output = json.loads(capsys.readouterr().out)
        entry = output["results"][0]
        assert entry["item"] == "agent/test-agent"
        assert entry["action"] == "install"
        assert entry["status"] == "success"
        assert entry["message"] == "Installed test-agent"
        assert entry["files_copied"] == 1

    def test_summary_counts(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Summary correctly counts installed, updated, skipped, failed."""
        plan1 = _make_plan(_make_item("a"))
        plan2 = _make_plan(_make_item("b"))
        result1 = _make_result(plan1, is_success=True)
        result2 = _make_result(plan2, is_success=False, message="Permission denied")

        report = SyncReport(installed=[result1], failed=[result2])

        _format_results_json([result1, result2], report, dry_run=True)

        output = json.loads(capsys.readouterr().out)
        summary = output["summary"]
        assert summary["installed"] == 1
        assert summary["updated"] == 0
        assert summary["skipped"] == 0
        assert summary["failed"] == 1

    def test_failed_result_exit_code(
        self,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Exit code is 1 when there are failures."""
        plan = _make_plan()
        result = _make_result(plan, is_success=False, message="Error")
        report = SyncReport(failed=[result])

        exit_code = _format_results_json([result], report, dry_run=False)
        assert exit_code == 1

    def test_failed_result_status_field(
        self,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Failed results have status 'failed'."""
        plan = _make_plan()
        result = _make_result(plan, is_success=False, message="OSError")
        report = SyncReport(failed=[result])

        _format_results_json([result], report, dry_run=False)

        output = json.loads(capsys.readouterr().out)
        assert output["results"][0]["status"] == "failed"

    def test_empty_results(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Empty results produce valid JSON."""
        report = SyncReport()

        exit_code = _format_results_json([], report, dry_run=False)
        assert exit_code == 0

        output = json.loads(capsys.readouterr().out)
        assert output["results"] == []
        assert output["summary"]["installed"] == 0


# ---------------------------------------------------------------------------
# JSON validity checks (all helpers produce parseable JSON)
# ---------------------------------------------------------------------------


class TestJsonValidity:
    """Ensure all JSON helpers produce valid, parseable output."""

    def test_status_json_no_trailing_comma(
        self,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Status JSON has no trailing commas."""
        target_manager = MagicMock()
        target_manager.targets = MagicMock(
            platform=TARGET_PLATFORM,
            config_dir=Path("/oc"),
        )
        summary = {"agents": 1}

        _format_status_json(target_manager, summary)

        raw = capsys.readouterr().out
        assert ",]" not in raw
        assert ",}" not in raw.replace("{}", "")
        # Verify it parses cleanly
        json.loads(raw)

    def test_plan_json_no_trailing_comma(
        self,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Plan JSON has no trailing commas."""
        target_manager = MagicMock()
        target_manager.owns_target_dir.return_value = True

        plan = _make_plan()
        _format_plan_json([plan], target_manager, dry_run=True)

        raw = capsys.readouterr().out
        json.loads(raw)  # Will fail if trailing commas present

    def test_results_json_no_trailing_comma(
        self,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Results JSON has no trailing commas."""
        plan = _make_plan()
        result = _make_result(plan)
        report = SyncReport(installed=[result])

        _format_results_json([result], report, dry_run=False)

        raw = capsys.readouterr().out
        json.loads(raw)
