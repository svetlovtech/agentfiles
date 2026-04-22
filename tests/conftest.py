"""Shared test fixtures and helpers for agentfiles tests."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import pytest

from agentfiles.models import Item, ItemType, Platform

# ---------------------------------------------------------------------------
# Shared helper functions
# ---------------------------------------------------------------------------


def make_item(
    name: str = "coder",
    item_type: ItemType = ItemType.AGENT,
    source_path: Path | None = None,
    **overrides,
) -> Item:
    """Create a test Item with sensible defaults.

    File-based items (agents, commands, plugins, configs) automatically get a
    ``.md`` extension on their source_path so that target resolution works
    correctly in clean/uninstall tests.
    """
    if source_path is None:
        base = Path("/src") / item_type.plural / name
        if item_type.is_file_based:
            base = base.with_suffix(".md")
        source_path = base

    defaults = dict(
        item_type=item_type,
        name=name,
        source_path=source_path,
        supported_platforms=(Platform.OPENCODE,),
    )
    defaults.update(overrides)
    return Item(**defaults)


def make_args(*, command: str, **overrides) -> SimpleNamespace:
    """Create a test args namespace with sensible defaults."""
    defaults = dict(
        command=command,
        source=None,
        config=None,
        cache_dir=None,
        target=None,
        item_type=None,
        non_interactive=True,
        dry_run=False,
        symlinks=False,
        format="text",
        only=None,
        except_items=None,
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def fake_home(tmp_path: Path) -> SimpleNamespace:
    """Create a fake home directory with platform config directories."""
    home = tmp_path / "home"
    home.mkdir()

    # OpenCode
    oc_dir = home / ".config" / "opencode"
    oc_dir.mkdir(parents=True)

    return SimpleNamespace(
        root=home,
        oc_dir=oc_dir,
    )


@pytest.fixture
def sample_source(tmp_path: Path) -> Path:
    """Create a minimal source directory with agents and skills."""
    source = tmp_path / "source"
    agents_dir = source / "agents"
    agents_dir.mkdir(parents=True)
    skills_dir = source / "skills"
    skills_dir.mkdir(parents=True)

    # Create a sample agent
    agent_dir = agents_dir / "test-agent"
    agent_dir.mkdir()
    (agent_dir / "test-agent.md").write_text(
        "---\nname: test-agent\ndescription: Test agent\n---\nTest content\n",
        encoding="utf-8",
    )

    # Create a sample skill
    skill_dir = skills_dir / "test-skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        "---\nname: test-skill\ndescription: Test skill\n---\nSkill content\n",
        encoding="utf-8",
    )

    return source


# ---------------------------------------------------------------------------
# Shared mock-stack fixtures for push / pull integration tests
# ---------------------------------------------------------------------------


@pytest.fixture
def push_mocks(tmp_path: Path):
    """Pre-configured mock stack for cmd_push tests.

    Patches all internal helpers that cmd_push calls so tests only need to
    adjust return values on the yielded SimpleNamespace attributes.
    """
    with (
        mock.patch("agentfiles.config.AgentfilesConfig.load") as mock_config,
        mock.patch("agentfiles.cli._get_source") as mock_source,
        mock.patch("agentfiles.cli._create_sync_pipeline") as mock_pipeline,
        mock.patch(
            "agentfiles.cli._resolve_platforms",
            return_value=[Platform.OPENCODE],
        ) as mock_platforms,
        mock.patch(
            "agentfiles.cli._resolve_item_types",
            return_value=[ItemType.AGENT],
        ) as mock_types,
        mock.patch("agentfiles.cli._discover_installed_from_targets") as mock_discover,
        mock.patch("agentfiles.cli._resolve_item_filter") as mock_resolve_filter,
        mock.patch("agentfiles.cli._apply_item_filter") as mock_apply_filter,
    ):
        mock_config.return_value = mock.MagicMock(cache_dir=None)
        mock_source.return_value = tmp_path
        mock_pipeline.return_value = (mock.MagicMock(), mock.MagicMock(), mock.MagicMock())
        mock_resolve_filter.return_value = (None, None)
        mock_apply_filter.return_value = lambda items: items

        yield SimpleNamespace(
            config=mock_config,
            source=mock_source,
            pipeline=mock_pipeline,
            platforms=mock_platforms,
            types=mock_types,
            discover=mock_discover,
            resolve_filter=mock_resolve_filter,
            apply_filter=mock_apply_filter,
        )


@pytest.fixture
def pull_mocks(tmp_path: Path):
    """Pre-configured mock stack for cmd_pull tests.

    Patches the three internal helpers used by cmd_pull so tests only need
    to configure the context object returned by ``_build_context``.
    """
    with (
        mock.patch("agentfiles.cli._build_context") as mock_build_ctx,
        mock.patch("agentfiles.cli._display_update_indicators") as mock_display,
        mock.patch("agentfiles.cli._update_sync_state_from_results") as mock_state,
    ):
        yield SimpleNamespace(
            build_ctx=mock_build_ctx,
            display=mock_display,
            state=mock_state,
        )
