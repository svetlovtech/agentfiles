"""Shared test fixtures for agentfiles."""

from pathlib import Path
from types import SimpleNamespace

import pytest


@pytest.fixture
def fake_home(tmp_path: Path) -> SimpleNamespace:
    """Create a fake home directory with platform config directories."""
    home = tmp_path / "home"
    home.mkdir()

    # OpenCode
    oc_dir = home / ".config" / "opencode"
    oc_dir.mkdir(parents=True)

    # Claude Code
    cc_dir = home / ".claude"
    cc_dir.mkdir()

    # Windsurf
    ws_dir = home / ".codeium" / "windsurf"
    ws_dir.mkdir(parents=True)

    # Cursor
    cursor_dir = home / ".cursor"
    cursor_dir.mkdir()

    return SimpleNamespace(
        root=home,
        oc_dir=oc_dir,
        cc_dir=cc_dir,
        ws_dir=ws_dir,
        cursor_dir=cursor_dir,
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
