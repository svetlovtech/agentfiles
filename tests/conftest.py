"""Shared test fixtures and helpers for agentfiles tests."""

from __future__ import annotations

import os
from collections.abc import Generator
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import pytest

from agentfiles.models import Item, ItemType
from agentfiles.target import TargetDiscovery, TargetManager

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

    Additional Item fields (``version``, ``files``, ``scope``, ``meta``) can be
    passed via ``**overrides``.
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
    )
    defaults.update(overrides)
    return Item(**defaults)


def make_items() -> list[Item]:
    """Create a standard set of test items spanning multiple types."""
    return [
        make_item("coder", ItemType.AGENT),
        make_item("debugger", ItemType.AGENT),
        make_item("solid-principles", ItemType.SKILL),
        make_item("dry-principle", ItemType.SKILL),
        make_item("autopilot", ItemType.COMMAND),
    ]


def make_args(*, command: str, **overrides) -> SimpleNamespace:
    """Create a test args namespace with sensible defaults."""
    defaults = dict(
        command=command,
        source=None,
        config=None,
        cache_dir=None,
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
    """Create a fake home directory with OpenCode config directories.

    Creates all standard subdirectories (agents, skills, commands, plugins) under
    the OpenCode config dir so that TargetDiscovery and TargetManager work
    correctly without touching the real filesystem.

    Returns a namespace with ``.home`` (the fake home root) and
    ``.opencode`` (the OpenCode config directory) attributes.
    """
    home = tmp_path / "home"
    home.mkdir()

    oc_dir = home / ".config" / "opencode"
    (oc_dir / "agents").mkdir(parents=True)
    (oc_dir / "skills").mkdir(parents=True)
    (oc_dir / "commands").mkdir(parents=True)
    (oc_dir / "plugins").mkdir(parents=True)

    return SimpleNamespace(
        home=home,
        opencode=oc_dir,
    )


@pytest.fixture
def target_manager(fake_home: SimpleNamespace) -> Generator[TargetManager, None, None]:
    """Return a TargetManager backed by the ``fake_home`` fixture.

    Patches ``Path.home`` and clears ``os.environ`` for the full test
    lifetime so that no code path can accidentally touch the real home
    directory or read stale env vars.
    """
    with (
        mock.patch.object(Path, "home", return_value=fake_home.home),
        mock.patch.dict(os.environ, {}, clear=True),
    ):
        targets = TargetDiscovery().discover_all()
        yield TargetManager(targets)


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
