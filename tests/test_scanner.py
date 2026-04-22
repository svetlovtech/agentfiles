"""Tests for agentfiles.scanner — source scanning for agents, skills, commands, plugins."""

from __future__ import annotations

from pathlib import Path

import pytest

from agentfiles.models import Item, ItemType, Platform, Scope
from agentfiles.scanner import (
    _SCANNER_REGISTRY,
    SourceScanner,
    _find_item_dirs,
    _is_in_scope_subdir,
    _register_scanner,
    _scan_agents_dir,
    _scan_commands_dir,
    _scan_plugins_dir,
    _scan_skills_dir,
    _should_skip,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_VALID_AGENT_MD = """\
---
name: my-agent
description: A test agent
version: 2.0.0
---

# My Agent

Some body text.
"""

_VALID_SKILL_MD = """\
---
name: my-skill
description: A test skill
---

# My Skill

Skill body.
"""

_VALID_COMMAND_MD = """\
---
name: my-command
description: A test command
---

# My Command

Command body.
"""


def _write_md(dir_path: Path, filename: str, content: str = _VALID_AGENT_MD) -> Path:
    """Write a .md file and return its path."""
    dir_path.mkdir(parents=True, exist_ok=True)
    p = dir_path / filename
    p.write_text(content, encoding="utf-8")
    return p


def _make_source_dir(
    base: Path,
    agents: list[str] | None = None,
    skills: list[str] | None = None,
    commands: list[str] | None = None,
    plugins: list[str] | None = None,
) -> Path:
    """Create a source directory tree with optional item subdirectories.

    *agents* / *skills* / *commands* are lists of .md filenames to create.
    *plugins* are filenames with their extensions (.ts, .yaml, .py).
    """
    if agents:
        agents_dir = base / "agents"
        agents_dir.mkdir(parents=True, exist_ok=True)
        for name in agents:
            _write_md(agents_dir, name, _VALID_AGENT_MD)

    if skills:
        skills_dir = base / "skills"
        skills_dir.mkdir(parents=True, exist_ok=True)
        for name in skills:
            skill_dir = skills_dir / name
            skill_dir.mkdir()
            (skill_dir / "SKILL.md").write_text(_VALID_SKILL_MD, encoding="utf-8")

    if commands:
        commands_dir = base / "commands"
        commands_dir.mkdir(parents=True, exist_ok=True)
        for name in commands:
            _write_md(commands_dir, name, _VALID_COMMAND_MD)

    if plugins:
        plugins_dir = base / "plugins"
        plugins_dir.mkdir(parents=True, exist_ok=True)
        for name in plugins:
            (plugins_dir / name).write_text("# plugin", encoding="utf-8")

    return base


# ---------------------------------------------------------------------------
# _should_skip
# ---------------------------------------------------------------------------


class TestShouldSkip:
    """Tests for _should_skip helper."""

    @pytest.mark.parametrize("name", [".hidden", ".git", ".env", ".DS_Store"])
    def test_skip_hidden_names(self, name: str) -> None:
        assert _should_skip(name) is True

    @pytest.mark.parametrize("name", ["__pycache__", "__init__.py"])
    def test_skip_internal_names(self, name: str) -> None:
        assert _should_skip(name) is True

    @pytest.mark.parametrize("name", ["agent.md", "SKILL.md", "plugin.ts", "my-dir"])
    def test_do_not_skip_normal_names(self, name: str) -> None:
        assert _should_skip(name) is False


# ---------------------------------------------------------------------------
# _find_item_dirs
# ---------------------------------------------------------------------------


class TestFindItemDirs:
    """Tests for _find_item_dirs helper."""

    def test_finds_plural_directory(self, tmp_path: Path) -> None:
        (tmp_path / "agents").mkdir()
        result = _find_item_dirs(tmp_path, ItemType.AGENT)
        assert len(result) == 1
        assert result[0][0].name == "agents"
        assert result[0][1] == Scope.GLOBAL

    def test_finds_singular_directory(self, tmp_path: Path) -> None:
        (tmp_path / "agent").mkdir()
        result = _find_item_dirs(tmp_path, ItemType.AGENT)
        assert len(result) == 1
        assert result[0][0].name == "agent"
        assert result[0][1] == Scope.GLOBAL

    def test_prefers_plural_over_singular(self, tmp_path: Path) -> None:
        (tmp_path / "agent").mkdir()
        (tmp_path / "agents").mkdir()
        result = _find_item_dirs(tmp_path, ItemType.AGENT)
        assert len(result) == 1
        assert result[0][0].name == "agents"

    def test_returns_empty_when_not_found(self, tmp_path: Path) -> None:
        result = _find_item_dirs(tmp_path, ItemType.AGENT)
        assert result == []

    @pytest.mark.parametrize("item_type", list(ItemType))
    def test_finds_all_item_types_plural(self, tmp_path: Path, item_type: ItemType) -> None:
        (tmp_path / item_type.plural).mkdir()
        result = _find_item_dirs(tmp_path, item_type)
        assert len(result) >= 1
        assert result[0][1] == Scope.GLOBAL

    def test_discovers_scope_subdirs(self, tmp_path: Path) -> None:
        """Scope subdirectories within content dir are discovered."""
        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()
        (agents_dir / "global").mkdir()
        (agents_dir / "project").mkdir()
        (agents_dir / "local").mkdir()

        result = _find_item_dirs(tmp_path, ItemType.AGENT)
        scopes = {scope for _, scope in result}
        assert Scope.GLOBAL in scopes
        assert Scope.PROJECT in scopes
        assert Scope.LOCAL in scopes

    def test_scope_filter_returns_only_requested_scope(self, tmp_path: Path) -> None:
        """When scope is specific, only that scope's directory is returned."""
        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()
        (agents_dir / "global").mkdir()
        (agents_dir / "project").mkdir()
        (agents_dir / "local").mkdir()

        result = _find_item_dirs(tmp_path, ItemType.AGENT, scope=Scope.PROJECT)
        assert len(result) == 1
        assert result[0][1] == Scope.PROJECT
        assert result[0][0].name == "project"

    def test_global_scope_filter_includes_base_dir(self, tmp_path: Path) -> None:
        """GLOBAL scope filter includes the base content dir."""
        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()

        result = _find_item_dirs(tmp_path, ItemType.AGENT, scope=Scope.GLOBAL)
        assert len(result) == 1
        assert result[0][0].name == "agents"
        assert result[0][1] == Scope.GLOBAL

    def test_global_scope_filter_includes_explicit_global_dir(self, tmp_path: Path) -> None:
        """GLOBAL scope filter includes explicit global/ subdirectory."""
        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()
        (agents_dir / "global").mkdir()

        result = _find_item_dirs(tmp_path, ItemType.AGENT, scope=Scope.GLOBAL)
        assert len(result) == 2
        dir_names = [p.name for p, _ in result]
        assert "agents" in dir_names
        assert "global" in dir_names

    def test_nonexistent_scope_dir_not_included(self, tmp_path: Path) -> None:
        """Scope subdirs that don't exist are not included."""
        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()

        result = _find_item_dirs(tmp_path, ItemType.AGENT, scope=Scope.PROJECT)
        assert result == []

    def test_base_dir_comes_first_for_dedup_priority(self, tmp_path: Path) -> None:
        """Base content dir is always the first entry for dedup priority."""
        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()
        (agents_dir / "project").mkdir()

        result = _find_item_dirs(tmp_path, ItemType.AGENT)
        assert result[0][0] == agents_dir
        assert result[0][1] == Scope.GLOBAL


# ---------------------------------------------------------------------------
# _scan_agents_dir
# ---------------------------------------------------------------------------


class TestScanAgentsDir:
    """Tests for _scan_agents_dir."""

    def test_delegates_to_file_based(self, tmp_path: Path) -> None:
        _write_md(tmp_path, "coder.md", _VALID_AGENT_MD)
        items = _scan_agents_dir(tmp_path)
        assert len(items) == 1
        assert items[0].item_type == ItemType.AGENT

    def test_discovers_nested_agent_directory(self, tmp_path: Path) -> None:
        """agents/coder/coder.md should be discovered as an agent."""
        coder_dir = tmp_path / "coder"
        coder_dir.mkdir()
        (coder_dir / "coder.md").write_text(_VALID_AGENT_MD, encoding="utf-8")

        items = _scan_agents_dir(tmp_path)
        assert len(items) == 1
        assert items[0].item_type == ItemType.AGENT
        assert items[0].name == "my-agent"

    def test_flat_file_takes_priority_over_directory(self, tmp_path: Path) -> None:
        """When both coder.md and coder/coder.md exist, only the flat file wins."""
        _write_md(tmp_path, "coder.md", _VALID_AGENT_MD)
        coder_dir = tmp_path / "coder"
        coder_dir.mkdir()
        (coder_dir / "coder.md").write_text("---\nname: nested-coder\n---\nbody", encoding="utf-8")

        items = _scan_agents_dir(tmp_path)
        assert len(items) == 1
        assert items[0].name == "my-agent"

    def test_mixed_flat_and_nested_agents(self, tmp_path: Path) -> None:
        """Flat files and directory-based agents coexist."""
        _write_md(tmp_path, "flat.md", "---\nname: flat-agent\n---\nbody")
        nested_dir = tmp_path / "nested"
        nested_dir.mkdir()
        (nested_dir / "nested.md").write_text(
            "---\nname: nested-agent\n---\nbody", encoding="utf-8"
        )

        items = _scan_agents_dir(tmp_path)
        assert len(items) == 2
        names = {it.name for it in items}
        assert names == {"flat-agent", "nested-agent"}

    def test_skips_hidden_nested_agent_dirs(self, tmp_path: Path) -> None:
        """Hidden subdirectories should be skipped."""
        hidden = tmp_path / ".hidden-agent"
        hidden.mkdir()
        (hidden / ".hidden-agent.md").write_text(_VALID_AGENT_MD, encoding="utf-8")

        items = _scan_agents_dir(tmp_path)
        assert items == []

    def test_skips_dir_without_matching_md(self, tmp_path: Path) -> None:
        """Directory without <dirname>.md should be skipped."""
        subdir = tmp_path / "myagent"
        subdir.mkdir()
        (subdir / "README.md").write_text("no matching md", encoding="utf-8")

        items = _scan_agents_dir(tmp_path)
        assert items == []


# ---------------------------------------------------------------------------
# _scan_commands_dir
# ---------------------------------------------------------------------------


class TestScanCommandsDir:
    """Tests for _scan_commands_dir."""

    def test_delegates_to_file_based(self, tmp_path: Path) -> None:
        _write_md(tmp_path, "deploy.md", _VALID_COMMAND_MD)
        items = _scan_commands_dir(tmp_path)
        assert len(items) == 1
        assert items[0].item_type == ItemType.COMMAND

    def test_discovers_nested_command_directory(self, tmp_path: Path) -> None:
        """commands/deploy/deploy.md should be discovered as a command."""
        deploy_dir = tmp_path / "deploy"
        deploy_dir.mkdir()
        (deploy_dir / "deploy.md").write_text(_VALID_COMMAND_MD, encoding="utf-8")

        items = _scan_commands_dir(tmp_path)
        assert len(items) == 1
        assert items[0].item_type == ItemType.COMMAND
        assert items[0].name == "my-command"

    def test_flat_file_takes_priority_over_directory(self, tmp_path: Path) -> None:
        """When both deploy.md and deploy/deploy.md exist, only the flat file wins."""
        _write_md(tmp_path, "deploy.md", _VALID_COMMAND_MD)
        deploy_dir = tmp_path / "deploy"
        deploy_dir.mkdir()
        (deploy_dir / "deploy.md").write_text(
            "---\nname: nested-deploy\n---\nbody", encoding="utf-8"
        )

        items = _scan_commands_dir(tmp_path)
        assert len(items) == 1
        assert items[0].name == "my-command"

    def test_mixed_flat_and_nested_commands(self, tmp_path: Path) -> None:
        """Flat files and directory-based commands coexist."""
        _write_md(tmp_path, "flat.md", "---\nname: flat-cmd\n---\nbody")
        nested_dir = tmp_path / "nested"
        nested_dir.mkdir()
        (nested_dir / "nested.md").write_text("---\nname: nested-cmd\n---\nbody", encoding="utf-8")

        items = _scan_commands_dir(tmp_path)
        assert len(items) == 2
        names = {it.name for it in items}
        assert names == {"flat-cmd", "nested-cmd"}


# ---------------------------------------------------------------------------
# _scan_skills_dir
# ---------------------------------------------------------------------------


class TestScanSkillsDir:
    """Tests for _scan_skills_dir."""

    def test_scans_skill_subdirectories(self, tmp_path: Path) -> None:
        skill_dir = tmp_path / "python-tdd"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(_VALID_SKILL_MD, encoding="utf-8")

        items = _scan_skills_dir(tmp_path)
        assert len(items) == 1
        assert items[0].item_type == ItemType.SKILL
        assert items[0].name == "my-skill"

    def test_skips_dirs_without_skill_md(self, tmp_path: Path) -> None:
        skill_dir = tmp_path / "empty-skill"
        skill_dir.mkdir()
        (skill_dir / "README.md").write_text("no SKILL.md here")

        items = _scan_skills_dir(tmp_path)
        assert items == []

    def test_skips_hidden_dirs(self, tmp_path: Path) -> None:
        hidden = tmp_path / ".hidden-skill"
        hidden.mkdir()
        (hidden / "SKILL.md").write_text(_VALID_SKILL_MD, encoding="utf-8")

        items = _scan_skills_dir(tmp_path)
        assert items == []

    def test_skips_pycache(self, tmp_path: Path) -> None:
        (tmp_path / "__pycache__").mkdir()
        items = _scan_skills_dir(tmp_path)
        assert items == []

    def test_multiple_skills(self, tmp_path: Path) -> None:
        for name in ["skill-a", "skill-b", "skill-c"]:
            d = tmp_path / name
            d.mkdir()
            (d / "SKILL.md").write_text(_VALID_SKILL_MD, encoding="utf-8")

        items = _scan_skills_dir(tmp_path)
        assert len(items) == 3

    def test_discovers_multiple_skills(self, tmp_path: Path) -> None:
        """Multiple skill directories with valid SKILL.md are all discovered."""
        good = tmp_path / "good-skill"
        good.mkdir()
        (good / "SKILL.md").write_text(_VALID_SKILL_MD, encoding="utf-8")

        other = tmp_path / "other-skill"
        other.mkdir()
        (other / "SKILL.md").write_text("---\nname: other\n---\nbody", encoding="utf-8")

        items = _scan_skills_dir(tmp_path)
        assert len(items) == 2
        names = {i.name for i in items}
        assert "my-skill" in names
        assert "other" in names


# ---------------------------------------------------------------------------
# _scan_plugins_dir
# ---------------------------------------------------------------------------


class TestScanPluginsDir:
    """Tests for _scan_plugins_dir."""

    def test_scans_plugin_files(self, tmp_path: Path) -> None:
        (tmp_path / "my-plugin.ts").write_text("export default {};", encoding="utf-8")
        items = _scan_plugins_dir(tmp_path)
        assert len(items) == 1
        assert items[0].item_type == ItemType.PLUGIN
        assert items[0].name == "my-plugin"

    def test_scans_yaml_plugin(self, tmp_path: Path) -> None:
        (tmp_path / "config.yaml").write_text("key: value", encoding="utf-8")
        items = _scan_plugins_dir(tmp_path)
        assert len(items) == 1

    def test_scans_python_plugin(self, tmp_path: Path) -> None:
        (tmp_path / "helper.py").write_text("def main(): pass", encoding="utf-8")
        items = _scan_plugins_dir(tmp_path)
        assert len(items) == 1

    def test_skips_unrecognised_extensions(self, tmp_path: Path) -> None:
        (tmp_path / "readme.md").write_text("# readme")
        (tmp_path / "data.json").write_text("{}")
        (tmp_path / "image.png").write_bytes(b"\x89PNG")
        items = _scan_plugins_dir(tmp_path)
        assert items == []

    def test_scans_plugin_directories(self, tmp_path: Path) -> None:
        plugin_dir = tmp_path / "my-plugin"
        plugin_dir.mkdir()
        (plugin_dir / "index.ts").write_text("export default {};", encoding="utf-8")
        (plugin_dir / "package.json").write_text('{"name": "my-plugin"}')

        items = _scan_plugins_dir(tmp_path)
        assert len(items) == 1
        assert items[0].item_type == ItemType.PLUGIN

    def test_skips_plugin_dirs_without_plugin_files(self, tmp_path: Path) -> None:
        plugin_dir = tmp_path / "not-a-plugin"
        plugin_dir.mkdir()
        (plugin_dir / "README.md").write_text("# readme")

        items = _scan_plugins_dir(tmp_path)
        assert items == []

    def test_skips_hidden_entries(self, tmp_path: Path) -> None:
        (tmp_path / ".hidden.ts").write_text("// hidden", encoding="utf-8")
        hidden_dir = tmp_path / ".hidden-plugin"
        hidden_dir.mkdir()
        (hidden_dir / "index.ts").write_text("// hidden plugin", encoding="utf-8")

        items = _scan_plugins_dir(tmp_path)
        assert items == []

    def test_skips_pycache(self, tmp_path: Path) -> None:
        (tmp_path / "__pycache__").mkdir()
        items = _scan_plugins_dir(tmp_path)
        assert items == []

    def test_mixed_files_and_dirs(self, tmp_path: Path) -> None:
        (tmp_path / "single.ts").write_text("export {};", encoding="utf-8")
        plugin_dir = tmp_path / "dir-plugin"
        plugin_dir.mkdir()
        (plugin_dir / "main.py").write_text("print('hello')", encoding="utf-8")

        items = _scan_plugins_dir(tmp_path)
        assert len(items) == 2


# ---------------------------------------------------------------------------
# SourceScanner
# ---------------------------------------------------------------------------


class TestSourceScannerScan:
    """Tests for SourceScanner.scan() and scan_type()."""

    def test_scan_finds_agents_and_skills(self, tmp_path: Path) -> None:
        _make_source_dir(tmp_path, agents=["coder.md"], skills=["python-tdd"])
        scanner = SourceScanner(tmp_path)
        items = scanner.scan()
        types = {i.item_type for i in items}
        assert ItemType.AGENT in types
        assert ItemType.SKILL in types

    def test_scan_finds_all_types(self, tmp_path: Path) -> None:
        _make_source_dir(
            tmp_path,
            agents=["a.md"],
            skills=["s"],
            commands=["c.md"],
            plugins=["p.ts"],
        )
        scanner = SourceScanner(tmp_path)
        items = scanner.scan()
        types = {i.item_type for i in items}
        assert types == {ItemType.AGENT, ItemType.SKILL, ItemType.COMMAND, ItemType.PLUGIN}

    def test_scan_returns_sorted_items(self, tmp_path: Path) -> None:
        _make_source_dir(
            tmp_path,
            agents=["z-agent.md", "a-agent.md"],
            commands=["b-cmd.md"],
        )
        # Give them distinct names so sorting is observable.
        (tmp_path / "agents" / "z-agent.md").write_text(
            "---\nname: zzz\n---\nbody", encoding="utf-8"
        )
        (tmp_path / "agents" / "a-agent.md").write_text(
            "---\nname: aaa\n---\nbody", encoding="utf-8"
        )

        scanner = SourceScanner(tmp_path)
        items = scanner.scan()

        # All items should be sorted by (item_type, name).
        for i in range(len(items) - 1):
            key_prev = (items[i].item_type.value, items[i].name)
            key_curr = (items[i + 1].item_type.value, items[i + 1].name)
            assert key_prev <= key_curr

    def test_scan_type_for_missing_directory(self, tmp_path: Path) -> None:
        scanner = SourceScanner(tmp_path)
        items = scanner.scan_type(ItemType.AGENT)
        assert items == []


# ---------------------------------------------------------------------------
# SourceScanner.get_summary
# ---------------------------------------------------------------------------


class TestSourceScannerSummary:
    """Tests for SourceScanner.get_summary()."""

    def test_summary_counts_all_types(self, tmp_path: Path) -> None:
        _make_source_dir(
            tmp_path,
            agents=["a.md", "b.md"],
            skills=["s1"],
            commands=["c.md"],
        )
        scanner = SourceScanner(tmp_path)
        summary = scanner.get_summary()
        assert summary[ItemType.AGENT] == 2
        assert summary[ItemType.SKILL] == 1
        assert summary[ItemType.COMMAND] == 1
        assert summary[ItemType.PLUGIN] == 0

    def test_summary_empty_source(self, tmp_path: Path) -> None:
        scanner = SourceScanner(tmp_path)
        summary = scanner.get_summary()
        assert all(v == 0 for v in summary.values())


# ---------------------------------------------------------------------------
# SourceScanner._count_by_type
# ---------------------------------------------------------------------------


class TestCountByType:
    """Tests for SourceScanner._count_by_type static method."""

    def test_counts_items(self, tmp_path: Path) -> None:
        items = [
            Item(item_type=ItemType.AGENT, name="a", source_path=tmp_path),
            Item(item_type=ItemType.AGENT, name="b", source_path=tmp_path),
            Item(item_type=ItemType.SKILL, name="s", source_path=tmp_path),
        ]
        counts = SourceScanner._count_by_type(items)
        assert counts[ItemType.AGENT] == 2
        assert counts[ItemType.SKILL] == 1
        assert ItemType.COMMAND not in counts

    def test_empty_list(self) -> None:
        assert SourceScanner._count_by_type([]) == {}


# ---------------------------------------------------------------------------
# Singular directory name support
# ---------------------------------------------------------------------------


class TestSingularDirectoryNames:
    """Verify scanners work with singular directory names (agent/, skill/, etc.)."""

    def test_scan_agents_with_singular_name(self, tmp_path: Path) -> None:
        """scanner should find 'agent/' when 'agents/' doesn't exist."""
        (tmp_path / "agent").mkdir()
        _write_md(tmp_path / "agent", "coder.md", _VALID_AGENT_MD)
        scanner = SourceScanner(tmp_path)
        items = scanner.scan_type(ItemType.AGENT)
        assert len(items) == 1
        assert items[0].item_type == ItemType.AGENT

    def test_plural_takes_priority_over_singular(self, tmp_path: Path) -> None:
        (tmp_path / "agent").mkdir()
        _write_md(tmp_path / "agent", "a.md", _VALID_AGENT_MD)
        (tmp_path / "agents").mkdir()
        _write_md(tmp_path / "agents", "b.md", _VALID_AGENT_MD)
        scanner = SourceScanner(tmp_path)
        items = scanner.scan_type(ItemType.AGENT)
        assert len(items) == 1
        assert items[0].name == "my-agent"


# ---------------------------------------------------------------------------
# Scanner registry (OCP)
# ---------------------------------------------------------------------------


class TestScannerRegistry:
    """Tests for the _SCANNER_REGISTRY registration mechanism (OCP)."""

    def test_all_item_types_registered(self) -> None:
        """Every ItemType enum member must have a registered scanner."""
        for item_type in ItemType:
            assert item_type in _SCANNER_REGISTRY, f"{item_type!r} missing from _SCANNER_REGISTRY"

    def test_registry_entries_are_callable(self) -> None:
        """Each registry entry must be a callable scanner function."""
        for item_type, scanner in _SCANNER_REGISTRY.items():
            assert callable(scanner), f"{item_type!r} scanner is not callable"

    def test_register_scanner_adds_entry(self) -> None:
        """_register_scanner should add a new entry to the registry."""
        # Save original state so we can restore it.
        original_len = len(_SCANNER_REGISTRY)

        def _dummy_scanner(
            dir_path: Path,
            gitignore: object = None,
        ) -> list[Item]:
            return []

        _register_scanner(
            ItemType.AGENT,  # Re-register an existing type for testing
            _dummy_scanner,
        )

        assert _SCANNER_REGISTRY[ItemType.AGENT] is _dummy_scanner

        # Restore original scanner.
        _register_scanner(
            ItemType.AGENT,
            _scan_agents_dir,
        )
        assert len(_SCANNER_REGISTRY) == original_len


# ---------------------------------------------------------------------------
# Error resilience tests
# ---------------------------------------------------------------------------


_CORRUPTED_YAML_MD = """\
---
- item1
- item2
---

Some body text.
"""

_UNREADABLE_CONTENT = "this is not parseable as frontmatter but readable"

_MALFORMED_FRONTMATTER_MD = """\
---
name: valid-name
description: desc
version: [
---

Body text.
"""


class TestCorruptedYAMLResilience:
    """Scanner must skip files with corrupted YAML frontmatter instead of crashing."""

    def test_corrupted_yaml_in_agents_is_skipped(self, tmp_path: Path) -> None:
        """A file with broken YAML should be skipped, not crash the scan."""
        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()
        _write_md(agents_dir, "good.md", _VALID_AGENT_MD)
        (agents_dir / "corrupt.md").write_text(_CORRUPTED_YAML_MD, encoding="utf-8")

        items = _scan_agents_dir(agents_dir)
        names = {i.name for i in items}
        assert "my-agent" in names
        assert len(items) == 1

    def test_corrupted_yaml_in_commands_is_skipped(self, tmp_path: Path) -> None:
        """Commands scanner must also tolerate corrupted YAML."""
        cmds_dir = tmp_path / "commands"
        cmds_dir.mkdir()
        _write_md(cmds_dir, "ok.md", _VALID_COMMAND_MD)
        (cmds_dir / "bad.md").write_text(_CORRUPTED_YAML_MD, encoding="utf-8")

        items = _scan_commands_dir(cmds_dir)
        assert len(items) == 1
        assert items[0].name == "my-command"

    def test_corrupted_yaml_in_plugins_is_skipped(self, tmp_path: Path) -> None:
        """Plugin scanner must tolerate corrupted YAML in .yaml files."""
        plugins_dir = tmp_path / "plugins"
        plugins_dir.mkdir()
        (plugins_dir / "good.yaml").write_text("name: my-plugin\ndescription: ok", encoding="utf-8")
        # Use frontmatter-wrapped list YAML that triggers agentfilesError""
        (plugins_dir / "broken.yaml").write_text(
            "---\n- item1\n- item2\n---\nbody", encoding="utf-8"
        )

        items = _scan_plugins_dir(plugins_dir)
        assert len(items) == 1
        assert items[0].name == "good"

    def test_multiple_corrupted_files_all_skipped(self, tmp_path: Path) -> None:
        """Multiple corrupted files should all be skipped gracefully."""
        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()
        _write_md(agents_dir, "good.md", _VALID_AGENT_MD)
        for i in range(5):
            (agents_dir / f"corrupt-{i}.md").write_text(_CORRUPTED_YAML_MD, encoding="utf-8")

        items = _scan_agents_dir(agents_dir)
        assert len(items) == 1
        assert items[0].name == "my-agent"


class TestPermissionErrorResilience:
    """Scanner must handle unreadable files gracefully."""

    def test_unreadable_agent_file_skipped(self, tmp_path: Path) -> None:
        """An unreadable file should be skipped with a warning."""
        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()
        _write_md(agents_dir, "readable.md", _VALID_AGENT_MD)
        unreadable = agents_dir / "unreadable.md"
        unreadable.write_text("---\nname: no-access\n---\nbody", encoding="utf-8")
        # Remove read permissions
        unreadable.chmod(0o000)

        try:
            items = _scan_agents_dir(agents_dir)
            names = {i.name for i in items}
            assert "my-agent" in names
            assert "no-access" not in names
        finally:
            # Restore permissions so tmp_path cleanup works
            unreadable.chmod(0o644)

    def test_unreadable_skill_directory_skipped(self, tmp_path: Path) -> None:
        """An unreadable skill directory should be skipped."""
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()

        # Good skill
        good = skills_dir / "good-skill"
        good.mkdir()
        (good / "SKILL.md").write_text(_VALID_SKILL_MD, encoding="utf-8")

        # Bad skill — make the directory unreadable
        bad = skills_dir / "bad-skill"
        bad.mkdir()
        (bad / "SKILL.md").write_text(_VALID_SKILL_MD, encoding="utf-8")
        bad.chmod(0o000)

        try:
            items = _scan_skills_dir(skills_dir)
            names = {i.name for i in items}
            assert "my-skill" in names
            assert len(items) == 1
        finally:
            bad.chmod(0o755)

    def test_unreadable_plugin_file_skipped(self, tmp_path: Path) -> None:
        """An unreadable plugin file should be skipped."""
        plugins_dir = tmp_path / "plugins"
        plugins_dir.mkdir()
        (plugins_dir / "good.ts").write_text("export {};", encoding="utf-8")
        unreadable = plugins_dir / "nope.ts"
        unreadable.write_text("export {};", encoding="utf-8")
        unreadable.chmod(0o000)

        try:
            items = _scan_plugins_dir(plugins_dir)
            assert len(items) == 1
            assert items[0].name == "good"
        finally:
            unreadable.chmod(0o644)


class TestScanResilience:
    """SourceScanner.scan() must continue even if one item type fails."""

    def test_scan_continues_after_one_type_fails(self, tmp_path: Path) -> None:
        """If agents dir causes an error, skills should still be scanned."""
        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()
        # Create a file that has corrupted YAML frontmatter
        (agents_dir / "broken.md").write_text(_CORRUPTED_YAML_MD, encoding="utf-8")

        # Create valid skills
        _make_source_dir(tmp_path, skills=["python-tdd"])

        scanner = SourceScanner(tmp_path)
        items = scanner.scan()

        # Skills should be found even though agents had issues
        types = {i.item_type for i in items}
        assert ItemType.SKILL in types

    def test_scan_with_mixed_good_and_bad_files(self, tmp_path: Path) -> None:
        """Mix of valid and corrupted files should return only valid items."""
        _make_source_dir(
            tmp_path,
            agents=["good.md"],
            skills=["good-skill"],
            commands=["good-cmd.md"],
        )
        # Add corrupted files
        agents_dir = tmp_path / "agents"
        (agents_dir / "bad.md").write_text(_CORRUPTED_YAML_MD, encoding="utf-8")

        scanner = SourceScanner(tmp_path)
        items = scanner.scan()
        types = {i.item_type for i in items}
        assert ItemType.AGENT in types
        assert ItemType.SKILL in types
        assert ItemType.COMMAND in types


class TestHasPluginFileDepthLimit:
    """_has_plugin_file must not recurse infinitely on deep nesting."""

    def test_deeply_nested_directory_stops(self, tmp_path: Path) -> None:
        """Directories deeper than max depth should not cause RecursionError."""
        from agentfiles.scanner import _has_plugin_file

        current = tmp_path
        for i in range(15):  # Exceed _PLUGIN_SCAN_MAX_DEPTH of 10
            current = current / f"level{i}"
        current.mkdir(parents=True)

        # Should return False (no plugin file found within depth limit)
        # and must NOT raise RecursionError
        result = _has_plugin_file(tmp_path)
        assert result is False

    def test_plugin_file_at_shallow_depth_found(self, tmp_path: Path) -> None:
        """Plugin files at shallow depth should still be found."""
        from agentfiles.scanner import _has_plugin_file

        shallow = tmp_path / "sub"
        shallow.mkdir()
        (shallow / "plugin.ts").write_text("export {};", encoding="utf-8")

        result = _has_plugin_file(tmp_path)
        assert result is True


# ---------------------------------------------------------------------------
# Empty directory tests
# ---------------------------------------------------------------------------


class TestEmptyDirectories:
    """All scanner functions must return [] for empty directories."""

    @pytest.mark.parametrize(
        ("scanner_fn", "item_type"),
        [
            (_scan_agents_dir, ItemType.AGENT),
            (_scan_commands_dir, ItemType.COMMAND),
            (_scan_skills_dir, ItemType.SKILL),
            (_scan_plugins_dir, ItemType.PLUGIN),
        ],
        ids=["agents", "commands", "skills", "plugins"],
    )
    def test_empty_dir_returns_empty_list(
        self,
        tmp_path: Path,
        scanner_fn: object,
        item_type: ItemType,
    ) -> None:
        items = scanner_fn(tmp_path)  # type: ignore[operator]
        assert items == []

    def test_scan_all_types_on_empty_source(self, tmp_path: Path) -> None:
        """SourceScanner.scan() on a completely empty source returns []."""
        scanner = SourceScanner(tmp_path)
        assert scanner.scan() == []

    @pytest.mark.parametrize(
        ("dir_name", "item_type"),
        [
            ("agents", ItemType.AGENT),
            ("skills", ItemType.SKILL),
            ("plugins", ItemType.PLUGIN),
        ],
        ids=["agents", "skills", "plugins"],
    )
    def test_empty_dir_in_source_tree(
        self,
        tmp_path: Path,
        dir_name: str,
        item_type: ItemType,
    ) -> None:
        """An existing but empty directory should yield no items."""
        (tmp_path / dir_name).mkdir()
        scanner = SourceScanner(tmp_path)
        assert scanner.scan_type(item_type) == []


# ---------------------------------------------------------------------------
# Directories with only hidden files
# ---------------------------------------------------------------------------


class TestOnlyHiddenFiles:
    """Directories containing only hidden/internal entries should yield no items."""

    @pytest.mark.parametrize(
        "hidden_name",
        [".hidden.md", ".env", ".gitkeep", ".DS_Store"],
        ids=["hidden-md", "env", "gitkeep", "ds-store"],
    )
    def test_agents_dir_with_single_hidden_file(
        self,
        tmp_path: Path,
        hidden_name: str,
    ) -> None:
        (tmp_path / hidden_name).write_text(_VALID_AGENT_MD, encoding="utf-8")
        items = _scan_agents_dir(tmp_path)
        assert items == []

    @pytest.mark.parametrize(
        "hidden_name",
        [".secret.md", ".env"],
        ids=["secret-md", "env"],
    )
    def test_commands_dir_with_single_hidden_file(
        self,
        tmp_path: Path,
        hidden_name: str,
    ) -> None:
        (tmp_path / hidden_name).write_text(_VALID_COMMAND_MD, encoding="utf-8")
        items = _scan_commands_dir(tmp_path)
        assert items == []

    def test_skills_dir_with_only_hidden_subdirs(self, tmp_path: Path) -> None:
        hidden = tmp_path / ".hidden-skill"
        hidden.mkdir()
        (hidden / "SKILL.md").write_text(_VALID_SKILL_MD, encoding="utf-8")
        items = _scan_skills_dir(tmp_path)
        assert items == []

    def test_plugins_dir_with_only_hidden_files(self, tmp_path: Path) -> None:
        (tmp_path / ".hidden.ts").write_text("export {};", encoding="utf-8")
        (tmp_path / ".secret.yaml").write_text("key: value", encoding="utf-8")
        items = _scan_plugins_dir(tmp_path)
        assert items == []

    def test_plugins_dir_with_only_hidden_dirs(self, tmp_path: Path) -> None:
        hidden_dir = tmp_path / ".hidden-plugin"
        hidden_dir.mkdir()
        (hidden_dir / "index.ts").write_text("export {};", encoding="utf-8")
        items = _scan_plugins_dir(tmp_path)
        assert items == []

    def test_agents_dir_with_only_pycache(self, tmp_path: Path) -> None:
        (tmp_path / "__pycache__").mkdir()
        items = _scan_agents_dir(tmp_path)
        assert items == []

    def test_source_scan_with_only_hidden_items(self, tmp_path: Path) -> None:
        """Full scan with only hidden items in all directories returns []."""
        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()
        (agents_dir / ".hidden.md").write_text(_VALID_AGENT_MD, encoding="utf-8")

        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        hidden_skill = skills_dir / ".hidden-skill"
        hidden_skill.mkdir()
        (hidden_skill / "SKILL.md").write_text(_VALID_SKILL_MD, encoding="utf-8")

        plugins_dir = tmp_path / "plugins"
        plugins_dir.mkdir()
        (plugins_dir / ".hidden.ts").write_text("export {};", encoding="utf-8")

        scanner = SourceScanner(tmp_path)
        assert scanner.scan() == []

    def test_mixed_hidden_and_init_produces_nothing(self, tmp_path: Path) -> None:
        """A directory with __init__.py, __pycache__, and .hidden files yields []."""
        (tmp_path / "__init__.py").write_text("", encoding="utf-8")
        (tmp_path / "__pycache__").mkdir()
        (tmp_path / ".hidden.md").write_text(_VALID_AGENT_MD, encoding="utf-8")
        items = _scan_agents_dir(tmp_path)
        assert items == []


# ---------------------------------------------------------------------------
# Mixed valid and invalid items
# ---------------------------------------------------------------------------


class TestMixedValidInvalidItems:
    """Scanners must correctly separate valid items from noise."""

    def test_agents_dir_with_non_md_and_valid_md(self, tmp_path: Path) -> None:
        _write_md(tmp_path, "valid.md", _VALID_AGENT_MD)
        (tmp_path / "readme.txt").write_text("text file", encoding="utf-8")
        (tmp_path / "data.json").write_text("{}", encoding="utf-8")
        (tmp_path / "image.png").write_bytes(b"\x89PNG")
        items = _scan_agents_dir(tmp_path)
        assert len(items) == 1
        assert items[0].name == "my-agent"

    def test_skills_dir_mixed_valid_empty_and_hidden(self, tmp_path: Path) -> None:
        valid = tmp_path / "valid-skill"
        valid.mkdir()
        (valid / "SKILL.md").write_text(_VALID_SKILL_MD, encoding="utf-8")

        empty = tmp_path / "empty-skill"
        empty.mkdir()
        # No SKILL.md in empty-skill

        hidden = tmp_path / ".hidden-skill"
        hidden.mkdir()
        (hidden / "SKILL.md").write_text(_VALID_SKILL_MD, encoding="utf-8")

        items = _scan_skills_dir(tmp_path)
        assert len(items) == 1
        assert items[0].name == "my-skill"

    def test_commands_dir_mixed_valid_and_corrupt(self, tmp_path: Path) -> None:
        _write_md(tmp_path, "ok.md", _VALID_COMMAND_MD)
        (tmp_path / "bad.md").write_text(_CORRUPTED_YAML_MD, encoding="utf-8")
        (tmp_path / ".hidden.md").write_text(_VALID_COMMAND_MD, encoding="utf-8")
        items = _scan_commands_dir(tmp_path)
        assert len(items) == 1
        assert items[0].name == "my-command"

    def test_plugins_dir_mixed_types_and_noise(self, tmp_path: Path) -> None:
        """Only recognized plugin extensions produce items."""
        (tmp_path / "good.ts").write_text("export {};", encoding="utf-8")
        (tmp_path / "config.yaml").write_text("name: cfg", encoding="utf-8")
        (tmp_path / "helper.py").write_text("pass", encoding="utf-8")
        # Noise files
        (tmp_path / "readme.md").write_text("# readme", encoding="utf-8")
        (tmp_path / "data.json").write_text("{}", encoding="utf-8")
        (tmp_path / ".hidden.ts").write_text("export {};", encoding="utf-8")
        items = _scan_plugins_dir(tmp_path)
        assert len(items) == 3
        names = {i.name for i in items}
        assert "good" in names
        assert "config" in names
        assert "helper" in names

    def test_source_scan_mixed_all_types_with_noise(self, tmp_path: Path) -> None:
        """Full scan with valid items plus noise files in each directory."""
        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()
        _write_md(agents_dir, "coder.md", _VALID_AGENT_MD)
        (agents_dir / "notes.txt").write_text("noise", encoding="utf-8")

        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        valid_skill = skills_dir / "python-tdd"
        valid_skill.mkdir()
        (valid_skill / "SKILL.md").write_text(_VALID_SKILL_MD, encoding="utf-8")
        empty_skill = skills_dir / "incomplete"
        empty_skill.mkdir()

        commands_dir = tmp_path / "commands"
        commands_dir.mkdir()
        _write_md(commands_dir, "deploy.md", _VALID_COMMAND_MD)
        (commands_dir / ".secret.md").write_text(_VALID_COMMAND_MD, encoding="utf-8")

        plugins_dir = tmp_path / "plugins"
        plugins_dir.mkdir()
        (plugins_dir / "tool.ts").write_text("export {};", encoding="utf-8")
        (plugins_dir / "readme.txt").write_text("noise", encoding="utf-8")

        scanner = SourceScanner(tmp_path)
        items = scanner.scan()
        types = {i.item_type for i in items}
        assert types == {ItemType.AGENT, ItemType.SKILL, ItemType.COMMAND, ItemType.PLUGIN}
        # Verify noise didn't create extra items
        assert len(items) == 4

    def test_agents_dir_mixed_flat_nested_and_invalid(self, tmp_path: Path) -> None:
        """Flat files, valid nested dirs, and invalid nested dirs coexist."""
        # Valid flat file
        _write_md(tmp_path, "flat.md", "---\nname: flat-agent\n---\nbody")
        # Valid nested dir
        nested = tmp_path / "nested"
        nested.mkdir()
        (nested / "nested.md").write_text(
            "---\nname: nested-agent\n---\nbody",
            encoding="utf-8",
        )
        # Nested dir without matching md (invalid)
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()
        (empty_dir / "README.md").write_text("no match", encoding="utf-8")
        # Hidden nested dir
        hidden = tmp_path / ".hidden"
        hidden.mkdir()
        (hidden / ".hidden.md").write_text(
            "---\nname: hidden-agent\n---\nbody",
            encoding="utf-8",
        )

        items = _scan_agents_dir(tmp_path)
        names = {it.name for it in items}
        assert names == {"flat-agent", "nested-agent"}


# ---------------------------------------------------------------------------
# Plugin scanning edge cases
# ---------------------------------------------------------------------------


class TestPluginEdgeCases:
    """Edge cases for plugin scanning."""

    def test_plugin_dir_with_nested_plugin_file_within_depth(
        self,
        tmp_path: Path,
    ) -> None:
        """Plugin file at depth 3 should be found."""
        from agentfiles.scanner import _has_plugin_file

        level1 = tmp_path / "src"
        level2 = level1 / "lib"
        level2.mkdir(parents=True)
        (level2 / "plugin.ts").write_text("export {};", encoding="utf-8")

        assert _has_plugin_file(tmp_path) is True

    def test_plugin_dir_with_non_plugin_files_only(self, tmp_path: Path) -> None:
        """Directory with only .md, .json, .txt files has no plugin file."""
        from agentfiles.scanner import _has_plugin_file

        (tmp_path / "readme.md").write_text("# readme", encoding="utf-8")
        (tmp_path / "package.json").write_text("{}", encoding="utf-8")
        (tmp_path / "notes.txt").write_text("notes", encoding="utf-8")

        assert _has_plugin_file(tmp_path) is False

    def test_plugin_dir_with_empty_subdirectories_only(self, tmp_path: Path) -> None:
        """Directory tree with only empty subdirs has no plugin file."""
        from agentfiles.scanner import _has_plugin_file

        (tmp_path / "empty1").mkdir()
        (tmp_path / "empty2").mkdir()
        sub = tmp_path / "sub" / "deep"
        sub.mkdir(parents=True)

        assert _has_plugin_file(tmp_path) is False

    @pytest.mark.parametrize(
        "ext",
        [".ts", ".yaml", ".py"],
        ids=["typescript", "yaml", "python"],
    )
    def test_plugin_single_file_all_extensions(
        self,
        tmp_path: Path,
        ext: str,
    ) -> None:
        """Each recognized plugin extension should be scannable."""
        (tmp_path / f"plugin{ext}").write_text("content", encoding="utf-8")
        items = _scan_plugins_dir(tmp_path)
        assert len(items) == 1
        assert items[0].item_type == ItemType.PLUGIN

    def test_plugin_dir_with_mixed_plugin_and_non_plugin_files(
        self,
        tmp_path: Path,
    ) -> None:
        """Plugin dir with both plugin and non-plugin files is recognized."""
        plugin_dir = tmp_path / "my-plugin"
        plugin_dir.mkdir()
        (plugin_dir / "index.ts").write_text("export {};", encoding="utf-8")
        (plugin_dir / "package.json").write_text('{"name": "p"}', encoding="utf-8")
        (plugin_dir / "README.md").write_text("# readme", encoding="utf-8")

        items = _scan_plugins_dir(tmp_path)
        assert len(items) == 1
        assert items[0].name == "my-plugin"

    def test_multiple_plugin_dirs_and_files(self, tmp_path: Path) -> None:
        """Mix of plugin files and plugin directories."""
        # File-based plugins
        (tmp_path / "standalone.ts").write_text("export {};", encoding="utf-8")
        (tmp_path / "config.yaml").write_text("name: cfg", encoding="utf-8")

        # Directory-based plugins
        dir_a = tmp_path / "plugin-a"
        dir_a.mkdir()
        (dir_a / "main.py").write_text("pass", encoding="utf-8")

        dir_b = tmp_path / "plugin-b"
        dir_b.mkdir()
        (dir_b / "index.ts").write_text("export {};", encoding="utf-8")

        # Non-plugin directory (no plugin files)
        non_plugin = tmp_path / "docs"
        non_plugin.mkdir()
        (non_plugin / "readme.txt").write_text("docs", encoding="utf-8")

        items = _scan_plugins_dir(tmp_path)
        assert len(items) == 4
        names = {i.name for i in items}
        assert names == {"standalone", "config", "plugin-a", "plugin-b"}

    def test_plugin_yaml_with_content(self, tmp_path: Path) -> None:
        """A .yaml plugin file is scanned as a plugin item with stem as name."""
        (tmp_path / "manifest.yaml").write_text(
            "name: manifest-plugin\ndescription: yaml plugin\n",
            encoding="utf-8",
        )
        items = _scan_plugins_dir(tmp_path)
        assert len(items) == 1
        # Plugin name is derived from the file stem, not YAML content.
        assert items[0].name == "manifest"

    def test_plugin_python_with_content(self, tmp_path: Path) -> None:
        """A .py plugin file is scanned as a plugin item."""
        (tmp_path / "helper.py").write_text(
            "def main():\n    print('hello')\n",
            encoding="utf-8",
        )
        items = _scan_plugins_dir(tmp_path)
        assert len(items) == 1

    def test_plugin_dir_at_exactly_max_depth(self, tmp_path: Path) -> None:
        """Plugin file at exactly _PLUGIN_SCAN_MAX_DEPTH is found."""
        from agentfiles.scanner import _PLUGIN_SCAN_MAX_DEPTH, _has_plugin_file

        current = tmp_path
        for i in range(_PLUGIN_SCAN_MAX_DEPTH):
            current = current / f"level{i}"
        current.mkdir(parents=True)
        (current / "plugin.ts").write_text("export {};", encoding="utf-8")

        # The file is at depth == _PLUGIN_SCAN_MAX_DEPTH from tmp_path.
        # _depth starts at 0 and stops when > _PLUGIN_SCAN_MAX_DEPTH.
        # So depth 10 means _depth goes 0,1,...,10 — exactly at limit.
        assert _has_plugin_file(tmp_path) is True


# ---------------------------------------------------------------------------
# Large number of items
# ---------------------------------------------------------------------------


class TestLargeNumberOfItems:
    """Tests for scanning directories with many items."""

    @pytest.mark.parametrize("count", [50, 100], ids=["fifty", "hundred"])
    def test_many_agents(self, tmp_path: Path, count: int) -> None:
        """Scanning many agent files should be correct and complete."""
        for i in range(count):
            content = f"---\nname: agent-{i:04d}\ndescription: Agent {i}\n---\nbody"
            _write_md(tmp_path, f"agent-{i:04d}.md", content)
        items = _scan_agents_dir(tmp_path)
        assert len(items) == count
        names = {it.name for it in items}
        assert f"agent-{0:04d}" in names
        assert f"agent-{count - 1:04d}" in names

    @pytest.mark.parametrize("count", [50, 100], ids=["fifty", "hundred"])
    def test_many_skills(self, tmp_path: Path, count: int) -> None:
        """Scanning many skill directories should be correct and complete."""
        for i in range(count):
            d = tmp_path / f"skill-{i:04d}"
            d.mkdir()
            content = f"---\nname: skill-{i:04d}\ndescription: Skill {i}\n---\nbody"
            (d / "SKILL.md").write_text(content, encoding="utf-8")
        items = _scan_skills_dir(tmp_path)
        assert len(items) == count

    @pytest.mark.parametrize("count", [50, 100], ids=["fifty", "hundred"])
    def test_many_commands(self, tmp_path: Path, count: int) -> None:
        """Scanning many command files should be correct and complete."""
        for i in range(count):
            content = f"---\nname: cmd-{i:04d}\ndescription: Cmd {i}\n---\nbody"
            _write_md(tmp_path, f"cmd-{i:04d}.md", content)
        items = _scan_commands_dir(tmp_path)
        assert len(items) == count

    @pytest.mark.parametrize("count", [50, 100], ids=["fifty", "hundred"])
    def test_many_plugins(self, tmp_path: Path, count: int) -> None:
        """Scanning many plugin files should be correct and complete."""
        for i in range(count):
            (tmp_path / f"plugin-{i:04d}.ts").write_text(
                "export {};",
                encoding="utf-8",
            )
        items = _scan_plugins_dir(tmp_path)
        assert len(items) == count

    def test_many_items_mixed_types_sorted(self, tmp_path: Path) -> None:
        """Many items across all types are returned sorted by (type, name)."""
        agent_content = "---\nname: agent-{i}\ndescription: d\n---\nbody"
        for i in range(20):
            _write_md(
                tmp_path / "agents",
                f"a-{i:03d}.md",
                agent_content.format(i=i),
            )

        cmd_content = "---\nname: cmd-{i}\ndescription: d\n---\nbody"
        for i in range(15):
            _write_md(
                tmp_path / "commands",
                f"c-{i:03d}.md",
                cmd_content.format(i=i),
            )

        for i in range(10):
            d = tmp_path / "skills" / f"s-{i:03d}"
            d.mkdir(parents=True, exist_ok=True)
            (d / "SKILL.md").write_text(
                f"---\nname: s-{i:03d}\ndescription: d\n---\nbody",
                encoding="utf-8",
            )

        for i in range(5):
            (tmp_path / "plugins" / f"p-{i:03d}.ts").parent.mkdir(
                parents=True,
                exist_ok=True,
            )
            (tmp_path / "plugins" / f"p-{i:03d}.ts").write_text(
                "export {};",
                encoding="utf-8",
            )

        scanner = SourceScanner(tmp_path)
        items = scanner.scan()

        assert len(items) == 50
        for idx in range(len(items) - 1):
            key_prev = (items[idx].item_type.value, items[idx].name)
            key_curr = (items[idx + 1].item_type.value, items[idx + 1].name)
            assert key_prev <= key_curr, f"Items not sorted at index {idx}: {key_prev} > {key_curr}"

    def test_large_source_get_summary_counts(self, tmp_path: Path) -> None:
        """get_summary() correctly counts many items across all types."""
        for i in range(30):
            _write_md(
                tmp_path / "agents",
                f"agent-{i}.md",
                f"---\nname: agent-{i}\n---\nbody",
            )
        for i in range(20):
            d = tmp_path / "skills" / f"skill-{i}"
            d.mkdir(parents=True, exist_ok=True)
            (d / "SKILL.md").write_text(
                f"---\nname: skill-{i}\n---\nbody",
                encoding="utf-8",
            )

        scanner = SourceScanner(tmp_path)
        summary = scanner.get_summary()
        assert summary[ItemType.AGENT] == 30
        assert summary[ItemType.SKILL] == 20
        assert summary[ItemType.COMMAND] == 0
        assert summary[ItemType.PLUGIN] == 0


# ---------------------------------------------------------------------------
# _scandir_sorted edge cases
# ---------------------------------------------------------------------------


class TestScandirSorted:
    """Tests for _scandir_sorted helper."""

    def test_returns_empty_for_nonexistent_dir(self, tmp_path: Path) -> None:
        from agentfiles.scanner import _scandir_sorted

        result = _scandir_sorted(tmp_path / "nonexistent")
        assert result == []

    def test_returns_sorted_entries(self, tmp_path: Path) -> None:
        from agentfiles.scanner import _scandir_sorted

        (tmp_path / "c.md").write_text("c", encoding="utf-8")
        (tmp_path / "a.md").write_text("a", encoding="utf-8")
        (tmp_path / "b.md").write_text("b", encoding="utf-8")

        entries = _scandir_sorted(tmp_path)
        names = [e.name for e in entries]
        assert names == ["a.md", "b.md", "c.md"]

    def test_returns_empty_for_empty_dir(self, tmp_path: Path) -> None:
        from agentfiles.scanner import _scandir_sorted

        entries = _scandir_sorted(tmp_path)
        assert entries == []


# ---------------------------------------------------------------------------
# Platform assignment
# ---------------------------------------------------------------------------


class TestPlatformAssignment:
    """Tests for platform assignment on discovered items."""

    def test_all_items_get_opencode_platform(self, tmp_path: Path) -> None:
        """All discovered items receive OPENCODE platform."""
        _make_source_dir(
            tmp_path,
            agents=["a.md"],
            skills=["s"],
            commands=["c.md"],
            plugins=["p.ts"],
        )
        scanner = SourceScanner(tmp_path)
        items = scanner.scan()
        for item in items:
            assert item.supported_platforms == (Platform.OPENCODE,), (
                f"{item.item_type!r} item '{item.name}' has wrong platforms"
            )


# ---------------------------------------------------------------------------
# Scope-aware scanning
# ---------------------------------------------------------------------------


class TestScopeAwareScanning:
    """Tests for scope-aware item discovery via SourceScanner."""

    def test_flat_files_get_global_scope(self, tmp_path: Path) -> None:
        """Items in the base content dir receive GLOBAL scope (backward compat)."""
        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()
        _write_md(agents_dir, "coder.md", _VALID_AGENT_MD)

        scanner = SourceScanner(tmp_path)
        items = scanner.scan_type(ItemType.AGENT)
        assert len(items) == 1
        assert items[0].scope == Scope.GLOBAL

    def test_project_scope_items(self, tmp_path: Path) -> None:
        """Items in agents/project/ receive PROJECT scope."""
        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()
        project_dir = agents_dir / "project"
        project_dir.mkdir()
        _write_md(project_dir, "local-agent.md", "---\nname: local-agent\n---\nbody")

        scanner = SourceScanner(tmp_path)
        items = scanner.scan_type(ItemType.AGENT)
        assert len(items) == 1
        assert items[0].scope == Scope.PROJECT
        assert items[0].name == "local-agent"

    def test_local_scope_items(self, tmp_path: Path) -> None:
        """Items in agents/local/ receive LOCAL scope."""
        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()
        local_dir = agents_dir / "local"
        local_dir.mkdir()
        _write_md(local_dir, "personal.md", "---\nname: personal\n---\nbody")

        scanner = SourceScanner(tmp_path)
        items = scanner.scan_type(ItemType.AGENT)
        assert len(items) == 1
        assert items[0].scope == Scope.LOCAL

    def test_explicit_global_scope(self, tmp_path: Path) -> None:
        """Items in agents/global/ receive GLOBAL scope."""
        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()
        global_dir = agents_dir / "global"
        global_dir.mkdir()
        _write_md(global_dir, "shared.md", "---\nname: shared\n---\nbody")

        scanner = SourceScanner(tmp_path)
        items = scanner.scan_type(ItemType.AGENT)
        assert len(items) == 1
        assert items[0].scope == Scope.GLOBAL
        assert items[0].name == "shared"

    def test_all_scopes_discovered(self, tmp_path: Path) -> None:
        """Items from all scopes are discovered when no scope filter is set."""
        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()
        _write_md(agents_dir, "base.md", "---\nname: base-agent\n---\nbody")

        for scope_dir_name, scope in [
            ("global", Scope.GLOBAL),
            ("project", Scope.PROJECT),
            ("local", Scope.LOCAL),
        ]:
            d = agents_dir / scope_dir_name
            d.mkdir()
            _write_md(d, f"{scope_dir_name}.md", f"---\nname: {scope_dir_name}-agent\n---\nbody")

        scanner = SourceScanner(tmp_path)
        items = scanner.scan_type(ItemType.AGENT)
        assert len(items) == 4

        scopes_by_name = {item.name: item.scope for item in items}
        assert scopes_by_name["base-agent"] == Scope.GLOBAL
        assert scopes_by_name["global-agent"] == Scope.GLOBAL
        assert scopes_by_name["project-agent"] == Scope.PROJECT
        assert scopes_by_name["local-agent"] == Scope.LOCAL

    def test_scope_filter_project(self, tmp_path: Path) -> None:
        """scope=Scope.PROJECT returns only project-scoped items."""
        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()
        _write_md(agents_dir, "base.md", "---\nname: base\n---\nbody")

        project_dir = agents_dir / "project"
        project_dir.mkdir()
        _write_md(project_dir, "proj.md", "---\nname: proj\n---\nbody")

        scanner = SourceScanner(tmp_path, scope=Scope.PROJECT)
        items = scanner.scan_type(ItemType.AGENT)
        assert len(items) == 1
        assert items[0].name == "proj"
        assert items[0].scope == Scope.PROJECT

    def test_scope_filter_local(self, tmp_path: Path) -> None:
        """scope=Scope.LOCAL returns only local-scoped items."""
        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()
        local_dir = agents_dir / "local"
        local_dir.mkdir()
        _write_md(local_dir, "me.md", "---\nname: me\n---\nbody")

        scanner = SourceScanner(tmp_path, scope=Scope.LOCAL)
        items = scanner.scan_type(ItemType.AGENT)
        assert len(items) == 1
        assert items[0].scope == Scope.LOCAL

    def test_scope_filter_global_includes_base(self, tmp_path: Path) -> None:
        """scope=Scope.GLOBAL includes items from base content dir."""
        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()
        _write_md(agents_dir, "base.md", "---\nname: base\n---\nbody")

        scanner = SourceScanner(tmp_path, scope=Scope.GLOBAL)
        items = scanner.scan_type(ItemType.AGENT)
        assert len(items) == 1
        assert items[0].scope == Scope.GLOBAL

    def test_scope_filter_excludes_other_scopes(self, tmp_path: Path) -> None:
        """scope=Scope.GLOBAL excludes project and local items."""
        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()

        for scope_dir_name in ("project", "local"):
            d = agents_dir / scope_dir_name
            d.mkdir()
            _write_md(d, f"{scope_dir_name}.md", f"---\nname: {scope_dir_name}\n---\nbody")

        scanner = SourceScanner(tmp_path, scope=Scope.GLOBAL)
        items = scanner.scan_type(ItemType.AGENT)
        assert items == []

    def test_dedup_base_over_global_dir(self, tmp_path: Path) -> None:
        """Base dir items take priority over explicit global/ items with same name."""
        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()
        _write_md(agents_dir, "coder.md", "---\nname: coder\nversion: '1.0'\n---\nbase")

        global_dir = agents_dir / "global"
        global_dir.mkdir()
        _write_md(global_dir, "coder.md", "---\nname: coder\nversion: '2.0'\n---\nglobal")

        scanner = SourceScanner(tmp_path)
        items = scanner.scan_type(ItemType.AGENT)
        assert len(items) == 1
        assert items[0].version == "1.0"
        assert items[0].scope == Scope.GLOBAL

    def test_same_name_different_scopes(self, tmp_path: Path) -> None:
        """Items with same name but different scopes are both kept."""
        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()
        _write_md(agents_dir, "coder.md", "---\nname: coder\n---\nglobal body")

        project_dir = agents_dir / "project"
        project_dir.mkdir()
        _write_md(project_dir, "coder.md", "---\nname: coder\n---\nproject body")

        scanner = SourceScanner(tmp_path)
        items = scanner.scan_type(ItemType.AGENT)
        assert len(items) == 2
        scopes = {item.scope for item in items}
        assert scopes == {Scope.GLOBAL, Scope.PROJECT}

    def test_skills_with_scopes(self, tmp_path: Path) -> None:
        """Skills in scope subdirectories get correct scope."""
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()

        # Base skill
        base_skill = skills_dir / "global-skill"
        base_skill.mkdir()
        (base_skill / "SKILL.md").write_text("---\nname: global-skill\n---\nbody", encoding="utf-8")

        # Project skill
        project_dir = skills_dir / "project"
        project_dir.mkdir()
        proj_skill = project_dir / "proj-skill"
        proj_skill.mkdir()
        (proj_skill / "SKILL.md").write_text("---\nname: proj-skill\n---\nbody", encoding="utf-8")

        scanner = SourceScanner(tmp_path)
        items = scanner.scan_type(ItemType.SKILL)
        assert len(items) == 2

        scopes_by_name = {item.name: item.scope for item in items}
        assert scopes_by_name["global-skill"] == Scope.GLOBAL
        assert scopes_by_name["proj-skill"] == Scope.PROJECT

    def test_backward_compat_no_scope_dirs(self, tmp_path: Path) -> None:
        """When no scope subdirs exist, behavior is identical to before."""
        _make_source_dir(
            tmp_path,
            agents=["a.md"],
            skills=["s"],
            commands=["c.md"],
            plugins=["p.ts"],
        )
        scanner = SourceScanner(tmp_path)
        items = scanner.scan()

        # All items should have GLOBAL scope
        for item in items:
            assert item.scope == Scope.GLOBAL

        types = {i.item_type for i in items}
        assert types == {ItemType.AGENT, ItemType.SKILL, ItemType.COMMAND, ItemType.PLUGIN}

    def test_scope_filter_with_project_scope(self, tmp_path: Path) -> None:
        """Scope filter correctly returns project-scoped items."""
        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()
        project_dir = agents_dir / "project"
        project_dir.mkdir()
        _write_md(project_dir, "coder.md", _VALID_AGENT_MD)

        scanner = SourceScanner(tmp_path, scope=Scope.PROJECT)
        items = scanner.scan_type(ItemType.AGENT)
        assert len(items) == 1
        assert items[0].scope == Scope.PROJECT

    def test_scope_filter_nonexistent_scope_dir(self, tmp_path: Path) -> None:
        """scope=Scope.PROJECT on a source without project/ returns empty."""
        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()
        _write_md(agents_dir, "coder.md", _VALID_AGENT_MD)

        scanner = SourceScanner(tmp_path, scope=Scope.PROJECT)
        items = scanner.scan_type(ItemType.AGENT)
        assert items == []


class TestIsInScopeSubdir:
    """Tests for _is_in_scope_subdir helper."""

    def test_path_in_global_subdir(self, tmp_path: Path) -> None:
        """Path inside global/ subdir is detected."""
        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()
        file_path = agents_dir / "global" / "coder.md"
        file_path.parent.mkdir(parents=True)

        assert _is_in_scope_subdir(file_path, agents_dir) is True

    def test_path_in_project_subdir(self, tmp_path: Path) -> None:
        """Path inside project/ subdir is detected."""
        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()
        file_path = agents_dir / "project" / "coder.md"
        file_path.parent.mkdir(parents=True)

        assert _is_in_scope_subdir(file_path, agents_dir) is True

    def test_path_in_base_dir(self, tmp_path: Path) -> None:
        """Path directly in base dir is NOT a scope subdir."""
        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()
        file_path = agents_dir / "coder.md"

        assert _is_in_scope_subdir(file_path, agents_dir) is False

    def test_path_in_regular_subdir(self, tmp_path: Path) -> None:
        """Path in a non-scope subdir is NOT detected as scope subdir."""
        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()
        file_path = agents_dir / "coder" / "coder.md"
        file_path.parent.mkdir(parents=True)

        assert _is_in_scope_subdir(file_path, agents_dir) is False

    def test_unrelated_path(self, tmp_path: Path) -> None:
        """Path outside the content dir returns False."""
        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()
        other_path = tmp_path / "other" / "file.md"

        assert _is_in_scope_subdir(other_path, agents_dir) is False
