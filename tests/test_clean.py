"""Tests for agentfiles clean — removing orphaned installed items."""

from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import pytest

from agentfiles.engine import SyncEngine
from agentfiles.models import ItemType
from agentfiles.target import TargetDiscovery, TargetManager
from tests.conftest import make_item

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def fake_home(tmp_path: Path) -> SimpleNamespace:
    """Create a fake home with platform config directories."""
    home = tmp_path / "home"
    home.mkdir()

    oc_dir = home / ".config" / "opencode"
    (oc_dir / "agent").mkdir(parents=True)
    (oc_dir / "skill").mkdir(parents=True)
    (oc_dir / "command").mkdir(parents=True)
    (oc_dir / "plugin").mkdir(parents=True)

    cc_dir = home / ".claude"
    (cc_dir / "agents").mkdir(parents=True)
    (cc_dir / "skills").mkdir(parents=True)
    (cc_dir / "plugins").mkdir(parents=True)
    (cc_dir / "commands").mkdir(parents=True)

    return SimpleNamespace(home=home, opencode=oc_dir, claude=cc_dir)


@pytest.fixture
def source_repo(tmp_path: Path) -> Path:
    """Create a minimal source repository with one agent and one skill."""
    repo = tmp_path / "repo"
    repo.mkdir()

    # One agent present in source.
    agents_dir = repo / "agents"
    agents_dir.mkdir()
    (agents_dir / "coder.md").write_text(
        "---\nname: coder\n---\n# Coder Agent\n",
    )

    # One skill present in source.
    skills_dir = repo / "skills"
    skills_dir.mkdir()
    active_skill = skills_dir / "active-skill"
    active_skill.mkdir()
    (active_skill / "SKILL.md").write_text("---\nname: active-skill\n---\n# Active Skill\n")

    # Config file so agentfiles clean can load it.
    (repo / ".agentfiles.yaml").write_text(
        "version: '1.0'\ndefault_platforms:\n  - opencode\n  - claude_code\n",
    )

    return repo


@pytest.fixture
def target_manager(fake_home: SimpleNamespace) -> TargetManager:
    """Return a TargetManager backed by fake_home."""
    with (
        mock.patch.object(Path, "home", return_value=fake_home.home),
        mock.patch.dict(os.environ, {}, clear=True),
    ):
        targets = TargetDiscovery().discover_all()
        return TargetManager(targets)


def _install_agent(fake_home: SimpleNamespace, name: str, content: str = "# Agent\n") -> None:
    """Create an agent file on the OpenCode target."""
    agent_file = fake_home.opencode / "agent" / f"{name}.md"
    agent_file.write_text(content)


def _install_skill(fake_home: SimpleNamespace, name: str, content: str = "# Skill\n") -> None:
    """Create a skill directory on the OpenCode target."""
    skill_dir = fake_home.opencode / "skill" / name
    skill_dir.mkdir(exist_ok=True)
    (skill_dir / "SKILL.md").write_text(content)


# ---------------------------------------------------------------------------
# Test: SyncEngine.uninstall used by clean
# ---------------------------------------------------------------------------


class TestCleanEngineUninstall:
    """Verify that the engine uninstall works correctly for orphan removal."""

    def test_uninstall_orphan_agent(
        self,
        target_manager: TargetManager,
        fake_home: SimpleNamespace,
    ) -> None:
        """An orphaned agent is removed from the target."""
        _install_agent(fake_home, "old-reviewer", "# Old Reviewer\n")
        orphan = make_item("old-reviewer", ItemType.AGENT)

        engine = SyncEngine(target_manager)
        report = engine.uninstall([orphan])

        assert report.is_success
        assert len(report.uninstalled) >= 1
        assert not (fake_home.opencode / "agent" / "old-reviewer.md").exists()

    def test_uninstall_orphan_skill(
        self,
        target_manager: TargetManager,
        fake_home: SimpleNamespace,
    ) -> None:
        """An orphaned skill directory is removed from the target."""
        _install_skill(fake_home, "deprecated-skill", "# Deprecated\n")
        orphan = make_item("deprecated-skill", ItemType.SKILL)

        engine = SyncEngine(target_manager)
        report = engine.uninstall([orphan])

        assert report.is_success
        assert len(report.uninstalled) >= 1
        assert not (fake_home.opencode / "skill" / "deprecated-skill").exists()

    def test_uninstall_multiple_orphans(
        self,
        target_manager: TargetManager,
        fake_home: SimpleNamespace,
    ) -> None:
        """Multiple orphaned items are all removed."""
        _install_agent(fake_home, "old-agent-1")
        _install_agent(fake_home, "old-agent-2")
        _install_skill(fake_home, "old-skill-1")

        orphans = [
            make_item("old-agent-1", ItemType.AGENT),
            make_item("old-agent-2", ItemType.AGENT),
            make_item("old-skill-1", ItemType.SKILL),
        ]

        engine = SyncEngine(target_manager)
        report = engine.uninstall(orphans)

        assert report.is_success
        assert len(report.uninstalled) >= 3

    def test_uninstall_preserves_existing_items(
        self,
        target_manager: TargetManager,
        fake_home: SimpleNamespace,
    ) -> None:
        """Removing orphans does not affect items that still exist."""
        _install_agent(fake_home, "coder", "# Coder\n")
        _install_agent(fake_home, "orphan-agent", "# Orphan\n")

        # Only remove the orphan.
        orphan = make_item("orphan-agent", ItemType.AGENT)
        engine = SyncEngine(target_manager)
        engine.uninstall([orphan])

        # Coder should still exist.
        assert (fake_home.opencode / "agent" / "coder.md").exists()
        assert not (fake_home.opencode / "agent" / "orphan-agent.md").exists()


# ---------------------------------------------------------------------------
# Test: cmd_clean integration via CLI
# ---------------------------------------------------------------------------


class TestCmdCleanCLI:
    """Integration tests for cmd_clean via build_parser."""

    def _run_clean(
        self,
        source_repo: Path,
        fake_home: SimpleNamespace,
        *,
        extra_args: list[str] | None = None,
        stdin_response: str = "y\n",
    ) -> int:
        """Run agentfiles clean with the given arguments."""
        from agentfiles.cli import build_parser

        args_list = ["clean", "--yes", "--config", str(source_repo / ".agentfiles.yaml")]
        if extra_args:
            args_list.extend(extra_args)

        parser = build_parser()
        args = parser.parse_args(args_list)
        args.source = str(source_repo)

        with (
            mock.patch.object(Path, "home", return_value=fake_home.home),
            mock.patch.dict(os.environ, {}, clear=True),
        ):
            from agentfiles.cli import cmd_clean

            return cmd_clean(args)

    def test_clean_no_orphans(
        self,
        source_repo: Path,
        fake_home: SimpleNamespace,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """When all installed items exist in source, nothing is removed."""
        # Install the same agent that exists in source.
        _install_agent(
            fake_home,
            "coder",
            "---\nname: coder\n---\n# Coder Agent\n",
        )

        code = self._run_clean(source_repo, fake_home)
        assert code == 0

        output = capsys.readouterr().out
        assert "No orphaned items found" in output

    def test_clean_detects_orphaned_agent(
        self,
        source_repo: Path,
        fake_home: SimpleNamespace,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """An orphaned agent is detected and removed."""
        _install_agent(fake_home, "old-reviewer", "# Old Reviewer\n")
        _install_agent(fake_home, "coder", "# Coder\n")

        code = self._run_clean(source_repo, fake_home)
        assert code == 0

        output = capsys.readouterr().out
        assert "Found 1 orphaned items" in output
        assert "agent/old-reviewer" in output
        assert "Removed 1 items" in output

        # Verify the orphan was actually removed.
        assert not (fake_home.opencode / "agent" / "old-reviewer.md").exists()
        # But coder should still be there.
        assert (fake_home.opencode / "agent" / "coder.md").exists()

    def test_clean_detects_orphaned_skill(
        self,
        source_repo: Path,
        fake_home: SimpleNamespace,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """An orphaned skill is detected and removed."""
        _install_skill(fake_home, "deprecated-skill", "# Deprecated\n")

        code = self._run_clean(source_repo, fake_home)
        assert code == 0

        output = capsys.readouterr().out
        assert "Found 1 orphaned items" in output
        assert "skill/deprecated-skill" in output

    def test_clean_dry_run(
        self,
        source_repo: Path,
        fake_home: SimpleNamespace,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Dry-run lists orphans but does not remove them."""
        _install_agent(fake_home, "phantom-agent", "# Phantom\n")

        code = self._run_clean(
            source_repo,
            fake_home,
            extra_args=["--dry-run"],
        )
        assert code == 0

        output = capsys.readouterr().out
        assert "Found 1 orphaned items" in output
        assert "Dry-run mode" in output

        # File should still exist after dry-run.
        assert (fake_home.opencode / "agent" / "phantom-agent.md").exists()

    def test_clean_type_filter(
        self,
        source_repo: Path,
        fake_home: SimpleNamespace,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """--type skill filters out orphaned agents."""
        _install_agent(fake_home, "orphan-agent", "# Orphan Agent\n")
        _install_skill(fake_home, "orphan-skill", "# Orphan Skill\n")

        code = self._run_clean(
            source_repo,
            fake_home,
            extra_args=["--type", "skill"],
        )
        assert code == 0

        output = capsys.readouterr().out
        assert "Found 1 orphaned items" in output
        assert "skill/orphan-skill" in output
        # Agent should NOT be in the output.
        assert "agent/orphan-agent" not in output

    def test_clean_no_installed_items(
        self,
        source_repo: Path,
        fake_home: SimpleNamespace,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """When nothing is installed, clean reports no items."""
        code = self._run_clean(source_repo, fake_home)
        assert code == 0

        output = capsys.readouterr().out
        assert "No installed items found" in output

    def test_clean_multiple_orphans_across_types(
        self,
        source_repo: Path,
        fake_home: SimpleNamespace,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Multiple orphaned items of different types are all found."""
        _install_agent(fake_home, "old-reviewer", "# Old\n")
        _install_skill(fake_home, "deprecated-skill", "# Deprecated\n")

        code = self._run_clean(source_repo, fake_home)
        assert code == 0

        output = capsys.readouterr().out
        assert "Found 2 orphaned items" in output
        assert "agent/old-reviewer" in output
        assert "skill/deprecated-skill" in output

    def test_clean_subparser_registered(self) -> None:
        """The 'clean' subcommand is registered in the parser."""
        from agentfiles.cli import _COMMAND_MAP

        assert "clean" in _COMMAND_MAP
