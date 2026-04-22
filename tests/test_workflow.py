"""Tests for WORKFLOW ItemType — models, scanner, and target integration."""

from __future__ import annotations

from pathlib import Path

import pytest

from agentfiles.models import ItemType, Platform
from agentfiles.scanner import (
    _SCANNER_REGISTRY,
    SourceScanner,
    _scan_workflows_dir,
)

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

_VALID_WORKFLOW_MD = """\
---
name: my-workflow
description: A test workflow pipeline
---

# My Workflow

Workflow body.
"""


def _make_workflow_dir(base: Path, name: str, content: str | None = None) -> Path:
    """Create a workflow subdirectory with a main markdown file."""
    if content is None:
        content = f"---\nname: {name}\ndescription: A test workflow\n---\n\n# {name}\n"
    workflow_dir = base / name
    workflow_dir.mkdir(parents=True, exist_ok=True)
    md = workflow_dir / f"{name}.md"
    md.write_text(content, encoding="utf-8")
    return workflow_dir


# ---------------------------------------------------------------------------
# Unit tests — models
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_workflow_enum_value() -> None:
    """ItemType.WORKFLOW exists with value 'workflow'."""
    assert ItemType.WORKFLOW.value == "workflow"


@pytest.mark.unit
def test_workflow_plural() -> None:
    """ItemType.WORKFLOW.plural returns 'workflows'."""
    assert ItemType.WORKFLOW.plural == "workflows"


@pytest.mark.unit
def test_workflow_is_not_file_based() -> None:
    """WORKFLOW is directory-based, not file-based."""
    assert ItemType.WORKFLOW.is_file_based is False


@pytest.mark.unit
def test_workflow_in_item_type_enum() -> None:
    """WORKFLOW is accessible via ItemType enum iteration."""
    assert ItemType.WORKFLOW in list(ItemType)


# ---------------------------------------------------------------------------
# Unit tests — scanner registry
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_workflow_scanner_registered() -> None:
    """WORKFLOW has a registered scanner function."""
    assert ItemType.WORKFLOW in _SCANNER_REGISTRY


@pytest.mark.unit
def test_workflow_scanner_is_callable() -> None:
    """WORKFLOW scanner is registered as a callable function."""
    entry = _SCANNER_REGISTRY[ItemType.WORKFLOW]
    assert callable(entry)


# ---------------------------------------------------------------------------
# Integration tests — scanner discovers workflow directories
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_scan_workflows_dir_discovers_items(tmp_path: Path) -> None:
    """_scan_workflows_dir finds a valid workflow directory."""
    workflows_dir = tmp_path / "workflows"
    workflows_dir.mkdir()
    _make_workflow_dir(workflows_dir, "data-pipeline")

    items = _scan_workflows_dir(workflows_dir)

    assert len(items) == 1
    assert items[0].name == "data-pipeline"
    assert items[0].item_type == ItemType.WORKFLOW


@pytest.mark.integration
def test_scan_workflows_dir_multiple(tmp_path: Path) -> None:
    """_scan_workflows_dir discovers multiple workflow directories."""
    workflows_dir = tmp_path / "workflows"
    workflows_dir.mkdir()
    _make_workflow_dir(workflows_dir, "pipeline-a")
    _make_workflow_dir(workflows_dir, "pipeline-b")

    items = _scan_workflows_dir(workflows_dir)

    names = {item.name for item in items}
    assert names == {"pipeline-a", "pipeline-b"}


@pytest.mark.integration
def test_scan_workflows_dir_skips_flat_files(tmp_path: Path) -> None:
    """_scan_workflows_dir ignores flat .md files at the top level."""
    workflows_dir = tmp_path / "workflows"
    workflows_dir.mkdir()
    # Flat file — should be ignored
    (workflows_dir / "flat.md").write_text("# Flat\n", encoding="utf-8")
    # Valid workflow directory
    _make_workflow_dir(workflows_dir, "real-workflow")

    items = _scan_workflows_dir(workflows_dir)

    assert len(items) == 1
    assert items[0].name == "real-workflow"


@pytest.mark.integration
def test_source_scanner_discovers_workflows(tmp_path: Path) -> None:
    """SourceScanner.scan() finds workflows in a 'workflows/' subdirectory."""
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    workflows_dir = source_dir / "workflows"
    workflows_dir.mkdir()
    _make_workflow_dir(workflows_dir, "etl-pipeline")

    scanner = SourceScanner(source_dir)
    items = scanner.scan()

    workflow_items = [i for i in items if i.item_type == ItemType.WORKFLOW]
    assert len(workflow_items) == 1
    assert workflow_items[0].name == "etl-pipeline"


@pytest.mark.integration
def test_source_scanner_workflow_platforms(tmp_path: Path) -> None:
    """Discovered workflow items carry all four supported platforms."""
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    workflows_dir = source_dir / "workflows"
    workflows_dir.mkdir()
    _make_workflow_dir(workflows_dir, "my-workflow")

    scanner = SourceScanner(source_dir)
    items = scanner.scan()

    workflow_items = [i for i in items if i.item_type == ItemType.WORKFLOW]
    assert len(workflow_items) == 1
    platforms = set(workflow_items[0].supported_platforms)
    expected = {Platform.OPENCODE}
    assert platforms == expected
