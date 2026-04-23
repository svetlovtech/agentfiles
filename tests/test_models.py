"""Tests for agentfiles.models — data models, enumerations, and helper utilities."""

from __future__ import annotations

from pathlib import Path

import pytest

from agentfiles.frontmatter import (
    _is_quoted,
    _quote_colon_values,
    _validate_field_type,
)
from agentfiles.models import (
    CHARS_PER_TOKEN,
    TARGET_PLATFORM,
    TARGET_PLATFORM_DISPLAY,
    AgentfilesError,
    ConfigError,
    DiffEntry,
    DiffStatus,
    Item,
    ItemMeta,
    ItemState,
    ItemType,
    SourceError,
    SourceInfo,
    SourceType,
    SyncAction,
    SyncPlan,
    SyncResult,
    SyncState,
    TargetError,
    TargetPaths,
    _build_item,
    _collect_relative_files,
    _find_main_md,
    _meta_from_frontmatter,
    _parse_item_meta,
    estimate_tokens_from_content,
    item_from_directory,
    item_from_file,
    parse_frontmatter,
    resolve_target_name,
)
from agentfiles.scanner import GitIgnoreMatcher, parse_gitignore

# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class TestExceptions:
    """Tests for the custom exception hierarchy."""

    @pytest.mark.parametrize(
        "exc_class, parent_class",
        [
            (AgentfilesError, Exception),
            (SourceError, AgentfilesError),
            (TargetError, AgentfilesError),
            (ConfigError, AgentfilesError),
        ],
        ids=["agentfiles-base", "source", "target", "config"],
    )
    def test_inheritance(self, exc_class: type, parent_class: type) -> None:
        assert issubclass(exc_class, parent_class)

    @pytest.mark.parametrize(
        "exc_class, message",
        [
            (ConfigError, "config file not found: 'foo.yaml'"),
            (SourceError, "bad path"),
            (TargetError, "not found"),
        ],
        ids=["config", "source", "target"],
    )
    def test_message_preserved(self, exc_class: type, message: str) -> None:
        exc = exc_class(message)
        assert message in str(exc)


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class TestSourceType:
    """Tests for SourceType enum."""

    def test_values(self) -> None:
        assert SourceType.LOCAL_DIR.value == "local_dir"
        assert SourceType.GIT_URL.value == "git_url"
        assert SourceType.GIT_DIR.value == "git_dir"

    def test_member_count(self) -> None:
        assert len(SourceType) == 3


class TestItemType:
    """Tests for ItemType enum."""

    def test_values(self) -> None:
        assert ItemType.AGENT.value == "agent"
        assert ItemType.SKILL.value == "skill"
        assert ItemType.COMMAND.value == "command"
        assert ItemType.PLUGIN.value == "plugin"
        assert ItemType.CONFIG.value == "config"

    def test_plural_property(self) -> None:
        assert ItemType.AGENT.plural == "agents"
        assert ItemType.SKILL.plural == "skills"
        assert ItemType.COMMAND.plural == "commands"
        assert ItemType.PLUGIN.plural == "plugins"
        assert ItemType.CONFIG.plural == "configs"

    def test_is_file_based_true_for_agents_and_commands(self) -> None:
        assert ItemType.AGENT.is_file_based is True
        assert ItemType.COMMAND.is_file_based is True

    def test_is_file_based_true_for_plugins_and_configs(self) -> None:
        assert ItemType.PLUGIN.is_file_based is True
        assert ItemType.CONFIG.is_file_based is True

    def test_is_file_based_false_only_for_skills(self) -> None:
        assert ItemType.SKILL.is_file_based is False

    def test_member_count(self) -> None:
        assert len(ItemType) == 6


class TestPlatformConstants:
    """Tests for platform string constants."""

    def test_target_platform_value(self) -> None:
        assert TARGET_PLATFORM == "opencode"

    def test_target_platform_display_value(self) -> None:
        assert TARGET_PLATFORM_DISPLAY == "OpenCode"


class TestSyncAction:
    """Tests for SyncAction enum."""

    def test_values(self) -> None:
        assert SyncAction.INSTALL.value == "install"
        assert SyncAction.UPDATE.value == "update"
        assert SyncAction.UNINSTALL.value == "uninstall"
        assert SyncAction.SKIP.value == "skip"

    def test_member_count(self) -> None:
        assert len(SyncAction) == 4


class TestDiffStatus:
    """Tests for DiffStatus enum."""

    def test_values(self) -> None:
        assert DiffStatus.NEW.value == "new"
        assert DiffStatus.UPDATED.value == "updated"
        assert DiffStatus.UNCHANGED.value == "unchanged"

    def test_member_count(self) -> None:
        assert len(DiffStatus) == 3


# ---------------------------------------------------------------------------
# Frozen data classes
# ---------------------------------------------------------------------------


class TestSourceInfo:
    """Tests for SourceInfo data class."""

    def test_creation_with_required_fields(self) -> None:
        info = SourceInfo(
            source_type=SourceType.LOCAL_DIR,
            path=Path("/some/path"),
            original_input="some/path",
            is_git_repo=False,
        )
        assert info.source_type == SourceType.LOCAL_DIR
        assert info.path == Path("/some/path")
        assert info.original_input == "some/path"
        assert info.is_git_repo is False

    def test_frozen_immutability(self) -> None:
        info = SourceInfo(
            source_type=SourceType.GIT_URL,
            path=Path("/repo"),
            original_input="https://github.com/repo",
            is_git_repo=True,
        )
        with pytest.raises(AttributeError):
            info.source_type = SourceType.LOCAL_DIR  # type: ignore[misc]

    def test_equality(self) -> None:
        p = Path("/x")
        a = SourceInfo(SourceType.LOCAL_DIR, p, "x", False)
        b = SourceInfo(SourceType.LOCAL_DIR, p, "x", False)
        assert a == b


class TestItemMeta:
    """Tests for ItemMeta data class."""

    def test_defaults(self) -> None:
        meta = ItemMeta(name="test")
        assert meta.name == "test"
        assert meta.description == ""
        assert meta.version == "1.0.0"
        assert meta.priority is None
        assert meta.tools == {}
        assert meta.extra == {}

    def test_custom_values(self) -> None:
        meta = ItemMeta(
            name="my-agent",
            description="Does stuff",
            version="2.1.0",
            priority="critical",
            tools={"bash": True, "read": False},
            extra={"author": "dev"},
        )
        assert meta.name == "my-agent"
        assert meta.description == "Does stuff"
        assert meta.version == "2.1.0"
        assert meta.priority == "critical"
        assert meta.tools == {"bash": True, "read": False}
        assert meta.extra == {"author": "dev"}

    def test_frozen_immutability(self) -> None:
        meta = ItemMeta(name="frozen")
        with pytest.raises(AttributeError):
            meta.name = "changed"  # type: ignore[misc]


class TestItem:
    """Tests for Item data class."""

    def test_minimal_creation(self) -> None:
        item = Item(item_type=ItemType.AGENT, name="test", source_path=Path("/a"))
        assert item.item_type == ItemType.AGENT
        assert item.name == "test"
        assert item.source_path == Path("/a")
        assert item.meta is None
        assert item.version == "1.0.0"
        assert item.files == ()

    def test_full_creation(self) -> None:
        meta = ItemMeta(name="full", version="3.0.0")
        item = Item(
            item_type=ItemType.SKILL,
            name="full-skill",
            source_path=Path("/skills/full-skill"),
            meta=meta,
            version="3.0.0",
            files=("SKILL.md", "refs.yaml"),
        )
        assert item.item_type == ItemType.SKILL
        assert item.meta is meta
        assert item.version == "3.0.0"
        assert item.files == ("SKILL.md", "refs.yaml")

    def test_frozen_immutability(self) -> None:
        item = Item(item_type=ItemType.AGENT, name="x", source_path=Path("/x"))
        with pytest.raises(AttributeError):
            item.name = "y"  # type: ignore[misc]

    def test_item_key_property(self) -> None:
        item = Item(item_type=ItemType.AGENT, name="coder", source_path=Path("/a"))
        assert item.item_key == "agent/coder"

    def test_item_key_for_skill(self) -> None:
        item = Item(item_type=ItemType.SKILL, name="python-reviewer", source_path=Path("/s"))
        assert item.item_key == "skill/python-reviewer"

    def test_sort_key_property(self) -> None:
        agent = Item(item_type=ItemType.AGENT, name="z-agent", source_path=Path("/a"))
        skill = Item(item_type=ItemType.SKILL, name="a-skill", source_path=Path("/s"))
        items = [agent, skill]
        items.sort(key=lambda i: i.sort_key)
        assert items[0].item_type == ItemType.AGENT  # "agent" < "skill"
        assert items[1].item_type == ItemType.SKILL


class TestTargetPaths:
    """Tests for TargetPaths data class."""

    def test_defaults(self) -> None:
        tp = TargetPaths(config_dir=Path("/cfg"))
        assert tp.platform == TARGET_PLATFORM
        assert tp.config_dir == Path("/cfg")
        assert tp.subdirs == {}
        assert tp.config_file is None

    def test_subdir_for_known_key(self, tmp_path: Path) -> None:
        tp = TargetPaths(
            config_dir=tmp_path,
            subdirs={"agents": tmp_path / "agent"},
        )
        result = tp.subdir_for(ItemType.AGENT)
        assert result == tmp_path / "agent"

    def test_subdir_for_unknown_key_falls_back(self, tmp_path: Path) -> None:
        tp = TargetPaths(config_dir=tmp_path)
        result = tp.subdir_for(ItemType.AGENT)
        assert result == tmp_path / "agents"

    def test_frozen_immutability(self) -> None:
        tp = TargetPaths(config_dir=Path("/cfg"))
        with pytest.raises(AttributeError):
            tp.config_dir = Path("/other")  # type: ignore[misc]


class TestSyncPlan:
    """Tests for SyncPlan data class."""

    def test_creation(self) -> None:
        item = Item(item_type=ItemType.AGENT, name="x", source_path=Path("/x"))
        plan = SyncPlan(
            item=item,
            action=SyncAction.INSTALL,
            target_dir=Path("/t"),
            reason="test",
        )
        assert plan.item is item
        assert plan.action == SyncAction.INSTALL
        assert plan.target_dir == Path("/t")
        assert plan.reason == "test"

    def test_frozen_immutability(self) -> None:
        item = Item(item_type=ItemType.AGENT, name="x", source_path=Path("/x"))
        plan = SyncPlan(
            item=item,
            action=SyncAction.INSTALL,
            target_dir=Path("/t"),
            reason="test",
        )
        with pytest.raises(AttributeError):
            plan.action = SyncAction.UPDATE  # type: ignore[misc]


class TestSyncResult:
    """Tests for SyncResult data class (mutable)."""

    def test_defaults(self) -> None:
        item = Item(item_type=ItemType.AGENT, name="x", source_path=Path("/x"))
        plan = SyncPlan(item=item, action=SyncAction.INSTALL, target_dir=Path("/t"), reason="r")
        result = SyncResult(plan=plan, is_success=True)
        assert result.plan is plan
        assert result.is_success is True
        assert result.message == ""
        assert result.files_copied == 0

    def test_mutable_fields(self) -> None:
        item = Item(item_type=ItemType.AGENT, name="x", source_path=Path("/x"))
        plan = SyncPlan(item=item, action=SyncAction.INSTALL, target_dir=Path("/t"), reason="r")
        result = SyncResult(plan=plan, is_success=False, message="error")
        result.is_success = True
        result.message = "fixed"
        result.files_copied = 5
        assert result.is_success is True
        assert result.message == "fixed"
        assert result.files_copied == 5


class TestDiffEntry:
    """Tests for DiffEntry data class."""

    def test_defaults(self) -> None:
        item = Item(item_type=ItemType.AGENT, name="x", source_path=Path("/x"))
        entry = DiffEntry(item=item, status=DiffStatus.NEW)
        assert entry.item is item
        assert entry.status == DiffStatus.NEW
        assert entry.details == ""

    def test_full_creation(self) -> None:
        item = Item(item_type=ItemType.SKILL, name="y", source_path=Path("/y"))
        entry = DiffEntry(
            item=item,
            status=DiffStatus.UPDATED,
            details="content changed",
        )
        assert entry.details == "content changed"

    def test_frozen_immutability(self) -> None:
        item = Item(item_type=ItemType.AGENT, name="x", source_path=Path("/x"))
        entry = DiffEntry(item=item, status=DiffStatus.NEW)
        with pytest.raises(AttributeError):
            entry.status = DiffStatus.UNCHANGED  # type: ignore[misc]


# ---------------------------------------------------------------------------
# parse_frontmatter
# ---------------------------------------------------------------------------


class TestParseFrontmatter:
    """Tests for parse_frontmatter function."""

    def test_empty_string(self) -> None:
        assert parse_frontmatter("") == {}

    def test_whitespace_only(self) -> None:
        assert parse_frontmatter("   \n  \n") == {}

    def test_no_delimiter(self) -> None:
        assert parse_frontmatter("# Hello\nSome text") == {}

    def test_single_delimiter(self) -> None:
        assert parse_frontmatter("---\nname: test\n") == {}

    def test_valid_frontmatter(self) -> None:
        content = "---\nname: my-agent\ndescription: A test agent\n---\n# Body"
        result = parse_frontmatter(content)
        assert result == {"name": "my-agent", "description": "A test agent"}

    def test_empty_yaml_block(self) -> None:
        content = "---\n---\n# Body"
        assert parse_frontmatter(content) == {}

    def test_whitespace_only_yaml_block(self) -> None:
        content = "---\n   \n---\n# Body"
        assert parse_frontmatter(content) == {}

    def test_non_mapping_yaml_raises(self) -> None:
        content = "---\n- item1\n- item2\n---"
        with pytest.raises(AgentfilesError, match="must be a YAML mapping"):
            parse_frontmatter(content)

    def test_non_mapping_yaml_error_suggests_fix(self) -> None:
        content = "---\n- item1\n- item2\n---"
        with pytest.raises(AgentfilesError, match="Fix: use 'key: value' syntax"):
            parse_frontmatter(content)

    def test_malformed_yaml_raises(self) -> None:
        content = "---\nname: [unclosed\n---"
        with pytest.raises(AgentfilesError, match="malformed YAML frontmatter"):
            parse_frontmatter(content)

    def test_malformed_yaml_error_suggests_fix(self) -> None:
        content = "---\nname: [unclosed\n---"
        with pytest.raises(AgentfilesError, match="Fix: check for unquoted"):
            parse_frontmatter(content)

    def test_colon_in_value_automatically_quoted(self) -> None:
        content = "---\nname: Architecture: Design Patterns\n---"
        result = parse_frontmatter(content)
        assert result["name"] == "Architecture: Design Patterns"

    def test_block_scalar_unchanged(self) -> None:
        content = "---\nname: test\ndescription: |\n  Multi-line\n  description\n---"
        result = parse_frontmatter(content)
        assert result["description"].startswith("Multi-line")

    def test_extra_frontmatter_keys(self) -> None:
        content = "---\nname: x\nauthor: dev\nlicense: MIT\n---"
        result = parse_frontmatter(content)
        assert "author" in result
        assert "license" in result


# ---------------------------------------------------------------------------
# _quote_colon_values
# ---------------------------------------------------------------------------


class TestQuoteColonValues:
    """Tests for the _quote_colon_values helper."""

    @pytest.mark.parametrize(
        "input_line, expected",
        [
            ("name: Architecture: Design Patterns", 'name: "Architecture: Design Patterns"'),
            ("description: |", "description: |"),
            ("name:", "name:"),
            ('name: "already quoted"', 'name: "already quoted"'),
            ("name: 'already quoted'", "name: 'already quoted'"),
            ("version: 1.0.0", "version: 1.0.0"),
        ],
        ids=[
            "colon-in-value",
            "block-scalar",
            "empty-value",
            "double-quoted",
            "single-quoted",
            "plain-value",
        ],
    )
    def test_quote_behavior(self, input_line: str, expected: str) -> None:
        assert _quote_colon_values(input_line) == expected

    def test_multiple_lines(self) -> None:
        inp = "name: A: B\nversion: 1.0.0"
        result = _quote_colon_values(inp)
        assert 'name: "A: B"' in result
        assert "version: 1.0.0" in result


# ---------------------------------------------------------------------------
# _meta_from_frontmatter
# ---------------------------------------------------------------------------


class TestMetaFromFrontmatter:
    """Tests for _meta_from_frontmatter helper."""

    def test_basic_frontmatter(self) -> None:
        raw = {"name": "agent-x", "description": "Test agent", "version": "2.0.0"}
        meta = _meta_from_frontmatter(raw)
        assert meta.name == "agent-x"
        assert meta.description == "Test agent"
        assert meta.version == "2.0.0"

    def test_missing_name_defaults_empty(self) -> None:
        meta = _meta_from_frontmatter({"description": "No name"})
        assert meta.name == ""

    def test_missing_version_defaults(self) -> None:
        meta = _meta_from_frontmatter({"name": "x"})
        assert meta.version == "1.0.0"

    def test_tools_dict_converted(self) -> None:
        raw = {"name": "x", "tools": {"bash": True, "read": "yes", "write": 0}}
        meta = _meta_from_frontmatter(raw)
        assert meta.tools == {"bash": True, "read": True, "write": False}

    def test_tools_non_dict_raises(self) -> None:
        raw = {"name": "x", "tools": "invalid"}
        with pytest.raises(AgentfilesError, match="frontmatter field 'tools' must be dict"):
            _meta_from_frontmatter(raw)

    def test_unknown_keys_go_to_extra(self) -> None:
        raw = {"name": "x", "author": "dev", "license": "MIT"}
        meta = _meta_from_frontmatter(raw)
        assert meta.extra == {"author": "dev", "license": "MIT"}

    def test_priority_preserved(self) -> None:
        raw = {"name": "x", "priority": "critical"}
        meta = _meta_from_frontmatter(raw)
        assert meta.priority == "critical"

    def test_known_keys_not_in_extra(self) -> None:
        raw = {"name": "x", "description": "d", "version": "1.0", "priority": "high", "tools": {}}
        meta = _meta_from_frontmatter(raw)
        assert meta.extra == {}

    def test_name_non_string_raises(self) -> None:
        raw = {"name": 123}
        with pytest.raises(AgentfilesError, match="frontmatter field 'name' must be str"):
            _meta_from_frontmatter(raw)

    def test_name_list_raises(self) -> None:
        raw = {"name": ["a", "b"]}
        with pytest.raises(AgentfilesError, match="frontmatter field 'name' must be str"):
            _meta_from_frontmatter(raw)

    def test_description_non_string_raises(self) -> None:
        raw = {"name": "x", "description": ["list", "of", "strings"]}
        with pytest.raises(AgentfilesError, match="frontmatter field 'description' must be str"):
            _meta_from_frontmatter(raw)

    def test_version_non_string_raises(self) -> None:
        raw = {"name": "x", "version": 2.0}
        with pytest.raises(AgentfilesError, match="frontmatter field 'version' must be str"):
            _meta_from_frontmatter(raw)

    def test_priority_non_string_raises(self) -> None:
        raw = {"name": "x", "priority": 42}
        with pytest.raises(AgentfilesError, match="frontmatter field 'priority' must be str"):
            _meta_from_frontmatter(raw)

    def test_validation_error_includes_fix_guidance(self) -> None:
        raw = {"name": True}
        with pytest.raises(AgentfilesError, match="Fix: set 'name' to a str value or remove it"):
            _meta_from_frontmatter(raw)

    def test_none_values_are_allowed(self) -> None:
        raw: dict[str, object] = {"name": None, "description": None}
        meta = _meta_from_frontmatter(raw)
        assert meta.name == "None"  # str(None)
        assert meta.description == "None"

    def test_tools_with_list_raises(self) -> None:
        raw = {"name": "x", "tools": ["bash", "read"]}
        with pytest.raises(AgentfilesError, match="frontmatter field 'tools' must be dict"):
            _meta_from_frontmatter(raw)


# ---------------------------------------------------------------------------
# _collect_relative_files
# ---------------------------------------------------------------------------


class TestCollectRelativeFiles:
    """Tests for _collect_relative_files helper."""

    def test_returns_files(self, tmp_path: Path) -> None:
        (tmp_path / "a.txt").write_text("a")
        (tmp_path / "b.txt").write_text("b")
        result = _collect_relative_files(tmp_path)
        assert sorted(result) == ["a.txt", "b.txt"]

    def test_excludes_hidden_files(self, tmp_path: Path) -> None:
        (tmp_path / "visible.txt").write_text("v")
        (tmp_path / ".hidden").write_text("h")
        result = _collect_relative_files(tmp_path)
        assert result == ["visible.txt"]

    def test_excludes_pycache(self, tmp_path: Path) -> None:
        (tmp_path / "normal.py").write_text("n")
        pyc = tmp_path / "__pycache__"
        pyc.mkdir()
        (pyc / "cached.pyc").write_bytes(b"\x00")
        result = _collect_relative_files(tmp_path)
        assert "__pycache__" not in str(result)
        assert result == ["normal.py"]

    def test_recursive_files(self, tmp_path: Path) -> None:
        sub = tmp_path / "sub"
        sub.mkdir()
        (sub / "deep.txt").write_text("d")
        (tmp_path / "top.txt").write_text("t")
        result = _collect_relative_files(tmp_path)
        expected = [str(Path("sub") / "deep.txt"), "top.txt"]
        assert sorted(result) == sorted(expected)

    def test_hidden_directory_ignored(self, tmp_path: Path) -> None:
        hidden_dir = tmp_path / ".git"
        hidden_dir.mkdir()
        (hidden_dir / "config").write_text("g")
        (tmp_path / "visible.txt").write_text("v")
        result = _collect_relative_files(tmp_path)
        assert ".git" not in str(result)
        assert result == ["visible.txt"]


# ---------------------------------------------------------------------------
# _find_main_md
# ---------------------------------------------------------------------------


class TestFindMainMd:
    """Tests for _find_main_md helper."""

    def test_skill_returns_skill_md(self, tmp_path: Path) -> None:
        (tmp_path / "SKILL.md").write_text("---\nname: s\n---")
        result = _find_main_md(tmp_path, ItemType.SKILL)
        assert result is not None
        assert result.name == "SKILL.md"

    def test_skill_without_skill_md_falls_back_to_first_md(self, tmp_path: Path) -> None:
        (tmp_path / "other.md").write_text("x")
        # Skill without SKILL.md falls back to first .md
        result = _find_main_md(tmp_path, ItemType.SKILL)
        assert result is not None
        assert result.name == "other.md"

    def test_agent_returns_dirname_md(self, tmp_path: Path) -> None:
        (tmp_path / f"{tmp_path.name}.md").write_text("---\nname: a\n---")
        result = _find_main_md(tmp_path, ItemType.AGENT)
        assert result is not None
        assert result.name == f"{tmp_path.name}.md"

    def test_command_returns_dirname_md(self, tmp_path: Path) -> None:
        (tmp_path / f"{tmp_path.name}.md").write_text("---\nname: c\n---")
        result = _find_main_md(tmp_path, ItemType.COMMAND)
        assert result is not None
        assert result.name == f"{tmp_path.name}.md"

    def test_fallback_first_md_alphabetically(self, tmp_path: Path) -> None:
        (tmp_path / "z-last.md").write_text("z")
        (tmp_path / "a-first.md").write_text("a")
        result = _find_main_md(tmp_path, ItemType.AGENT)
        assert result is not None
        assert result.name == "a-first.md"

    def test_plugin_no_md_returns_none(self, tmp_path: Path) -> None:
        (tmp_path / "index.ts").write_text("x")
        result = _find_main_md(tmp_path, ItemType.PLUGIN)
        assert result is None

    def test_plugin_with_md_returns_first_md(self, tmp_path: Path) -> None:
        """Plugin type still falls through to the .md fallback scan."""
        (tmp_path / "anything.md").write_text("x")
        result = _find_main_md(tmp_path, ItemType.PLUGIN)
        assert result is not None
        assert result.name == "anything.md"

    def test_empty_directory_returns_none(self, tmp_path: Path) -> None:
        result = _find_main_md(tmp_path, ItemType.AGENT)
        assert result is None


# ---------------------------------------------------------------------------
# _parse_item_meta
# ---------------------------------------------------------------------------


class TestParseItemMeta:
    """Tests for _parse_item_meta helper."""

    def test_none_main_md_returns_none(self, tmp_path: Path) -> None:
        meta, name = _parse_item_meta(None, tmp_path)
        assert meta is None
        assert name == tmp_path.name

    def test_md_without_frontmatter_returns_none(self, tmp_path: Path) -> None:
        md_file = tmp_path / "SKILL.md"
        md_file.write_text("Just body text")
        meta, name = _parse_item_meta(md_file, tmp_path)
        assert meta is None
        assert name == tmp_path.name

    def test_md_with_frontmatter(self, tmp_path: Path) -> None:
        md_file = tmp_path / "SKILL.md"
        md_file.write_text("---\nname: my-skill\nversion: 2.0.0\n---\n# Body")
        meta, name = _parse_item_meta(md_file, tmp_path)
        assert meta is not None
        assert meta.name == "my-skill"
        assert meta.version == "2.0.0"
        assert name == "my-skill"

    def test_name_fallback_to_dir_name(self, tmp_path: Path) -> None:
        md_file = tmp_path / "SKILL.md"
        md_file.write_text("---\nversion: 1.0.0\n---")
        meta, name = _parse_item_meta(md_file, tmp_path)
        assert name == tmp_path.name


# ---------------------------------------------------------------------------
# _build_item
# ---------------------------------------------------------------------------


class TestBuildItem:
    """Tests for _build_item helper."""

    def test_with_meta(self, tmp_path: Path) -> None:
        meta = ItemMeta(name="built", version="2.0.0")
        (tmp_path / "file.txt").write_text("content")
        item = _build_item(ItemType.SKILL, tmp_path, meta, "built", ("file.txt",))
        assert item.name == "built"
        assert item.version == "2.0.0"
        assert item.files == ("file.txt",)
        assert item.meta is meta

    def test_without_meta_uses_default_version(self, tmp_path: Path) -> None:
        (tmp_path / "file.txt").write_text("content")
        item = _build_item(ItemType.AGENT, tmp_path, None, "agent-x", ("file.txt",))
        assert item.version == "1.0.0"
        assert item.meta is None


# ---------------------------------------------------------------------------
# item_from_file
# ---------------------------------------------------------------------------


class TestItemFromFile:
    """Tests for item_from_file function."""

    def test_file_with_frontmatter(self, tmp_path: Path) -> None:
        f = tmp_path / "python-reviewer.md"
        f.write_text("---\nname: python-reviewer\ndescription: Review code\n---\n# Review")
        item = item_from_file(f, ItemType.AGENT)
        assert item.item_type == ItemType.AGENT
        assert item.name == "python-reviewer"
        assert item.files == (f.name,)

    def test_file_without_frontmatter_uses_stem(self, tmp_path: Path) -> None:
        f = tmp_path / "my-command.md"
        f.write_text("Just content")
        item = item_from_file(f, ItemType.COMMAND)
        assert item.name == "my-command"
        assert item.version == "1.0.0"
        assert item.meta is None

    def test_nonexistent_file_raises(self) -> None:
        with pytest.raises(SourceError, match="not a file"):
            item_from_file(Path("/nonexistent.md"), ItemType.AGENT)

    def test_directory_instead_of_file_raises(self, tmp_path: Path) -> None:
        d = tmp_path / "not_a_file"
        d.mkdir()
        with pytest.raises(SourceError, match="not a file"):
            item_from_file(d, ItemType.AGENT)


# ---------------------------------------------------------------------------
# item_from_directory
# ---------------------------------------------------------------------------


class TestItemFromDirectory:
    """Tests for item_from_directory function."""

    def test_skill_directory_with_skill_md(self, tmp_path: Path) -> None:
        skill_dir = tmp_path / "python-stylist"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(
            "---\nname: python-stylist\nversion: 1.5.0\n---\n# Styling"
        )
        item = item_from_directory(skill_dir, ItemType.SKILL)
        assert item.item_type == ItemType.SKILL
        assert item.name == "python-stylist"
        assert item.version == "1.5.0"
        assert len(item.files) >= 1
        assert item.meta is not None

    def test_agent_directory_with_dirname_md(self, tmp_path: Path) -> None:
        agent_dir = tmp_path / "reviewer"
        agent_dir.mkdir()
        (agent_dir / "reviewer.md").write_text(
            "---\nname: reviewer\ndescription: Reviews\n---\n# Reviewer"
        )
        item = item_from_directory(agent_dir, ItemType.AGENT)
        assert item.name == "reviewer"

    def test_plugin_directory_no_md_required(self, tmp_path: Path) -> None:
        plugin_dir = tmp_path / "my-plugin"
        plugin_dir.mkdir()
        (plugin_dir / "index.ts").write_text("export default {}")
        item = item_from_directory(plugin_dir, ItemType.PLUGIN)
        assert item.item_type == ItemType.PLUGIN
        assert item.name == "my-plugin"
        assert item.meta is None

    def test_nonexistent_directory_raises(self) -> None:
        with pytest.raises(SourceError, match="path does not exist"):
            item_from_directory(Path("/nonexistent"), ItemType.AGENT)

    def test_file_instead_of_directory_raises(self, tmp_path: Path) -> None:
        f = tmp_path / "not_a_dir.md"
        f.write_text("content")
        with pytest.raises(SourceError, match="expected a directory"):
            item_from_directory(f, ItemType.AGENT)

    def test_agent_without_md_raises(self, tmp_path: Path) -> None:
        agent_dir = tmp_path / "empty-agent"
        agent_dir.mkdir()
        (agent_dir / "notes.txt").write_text("not md")
        with pytest.raises(SourceError, match="cannot find main markdown file for agent"):
            item_from_directory(agent_dir, ItemType.AGENT)

    def test_skill_without_md_error_mentions_skill_md(self, tmp_path: Path) -> None:
        skill_dir = tmp_path / "empty-skill"
        skill_dir.mkdir()
        (skill_dir / "readme.txt").write_text("not md")
        with pytest.raises(SourceError, match="Expected 'SKILL.md'"):
            item_from_directory(skill_dir, ItemType.SKILL)

    def test_agent_without_md_error_suggests_filename(self, tmp_path: Path) -> None:
        agent_dir = tmp_path / "my-agent"
        agent_dir.mkdir()
        (agent_dir / "notes.txt").write_text("not md")
        with pytest.raises(SourceError, match="Expected 'my-agent.md'"):
            item_from_directory(agent_dir, ItemType.AGENT)

    def test_skill_without_md_raises(self, tmp_path: Path) -> None:
        skill_dir = tmp_path / "empty-skill"
        skill_dir.mkdir()
        (skill_dir / "readme.txt").write_text("not md")
        with pytest.raises(SourceError, match="cannot find main markdown file for skill"):
            item_from_directory(skill_dir, ItemType.SKILL)

    def test_empty_directory_raises(self, tmp_path: Path) -> None:
        plugin_dir = tmp_path / "empty-plugin"
        plugin_dir.mkdir()
        with pytest.raises(SourceError, match="directory is empty"):
            item_from_directory(plugin_dir, ItemType.PLUGIN)

    def test_recursive_file_collection(self, tmp_path: Path) -> None:
        skill_dir = tmp_path / "deep-skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("---\nname: deep-skill\n---")
        sub = skill_dir / "refs"
        sub.mkdir()
        (sub / "guide.md").write_text("ref")
        item = item_from_directory(skill_dir, ItemType.SKILL)
        assert len(item.files) >= 2

    def test_hidden_files_excluded(self, tmp_path: Path) -> None:
        skill_dir = tmp_path / "hidden-skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("---\nname: hidden-skill\n---")
        (skill_dir / ".hidden").write_text("h")
        item = item_from_directory(skill_dir, ItemType.SKILL)
        assert ".hidden" not in item.files


# ---------------------------------------------------------------------------
# Version resolution
# ---------------------------------------------------------------------------


class TestVersionResolution:
    """Tests for version fallback logic."""

    def test_meta_empty_name_item_uses_provided_name(self, tmp_path: Path) -> None:
        meta = ItemMeta(name="")
        (tmp_path / "f.txt").write_text("x")
        item = _build_item(ItemType.AGENT, tmp_path, meta, "from-dir", ("f.txt",))
        assert item.name == "from-dir"


# ---------------------------------------------------------------------------
# resolve_target_name
# ---------------------------------------------------------------------------


class TestResolveTargetName:
    """Tests for resolve_target_name helper."""

    def test_file_item_returns_filename(self) -> None:
        item = Item(item_type=ItemType.AGENT, name="coder", source_path=Path("/tmp/coder.md"))
        assert resolve_target_name(item) == "coder.md"

    def test_directory_item_returns_name(self) -> None:
        item = Item(
            item_type=ItemType.SKILL, name="python-style", source_path=Path("/tmp/python-style")
        )
        assert resolve_target_name(item) == "python-style"


# ---------------------------------------------------------------------------
# parse_gitignore
# ---------------------------------------------------------------------------


class TestParseGitignore:
    """Tests for parse_gitignore helper."""

    def test_comments_and_empty_lines_skipped(self, tmp_path: Path) -> None:
        gitignore = tmp_path / ".gitignore"
        gitignore.write_text("# comment\n\n*.pyc\n")
        patterns = parse_gitignore(gitignore)
        assert patterns == ["*.pyc"]

    def test_missing_file_raises(self) -> None:
        with pytest.raises(SourceError):
            parse_gitignore(Path("/nonexistent/.gitignore"))


# ---------------------------------------------------------------------------
# GitIgnoreMatcher
# ---------------------------------------------------------------------------


class TestGitIgnoreMatcher:
    """Tests for GitIgnoreMatcher class."""

    def test_matches_file_pattern(self, tmp_path: Path) -> None:
        matcher = GitIgnoreMatcher(root_dir=tmp_path, patterns=["*.pyc", "__pycache__"])
        assert matcher.is_ignored(tmp_path / "foo.pyc") is True
        assert matcher.is_ignored(tmp_path / "foo.py") is False

    def test_matches_directory_pattern(self, tmp_path: Path) -> None:
        matcher = GitIgnoreMatcher(root_dir=tmp_path, patterns=["build/"])
        assert matcher.is_ignored(tmp_path / "build" / "output.js") is True

    def test_from_directory(self, tmp_path: Path) -> None:
        gitignore = tmp_path / ".gitignore"
        gitignore.write_text("*.log\n")
        matcher = GitIgnoreMatcher.from_directory(tmp_path)
        assert matcher is not None
        assert matcher.is_ignored(tmp_path / "debug.log") is True

    def test_from_directory_returns_none_when_no_gitignore(self, tmp_path: Path) -> None:
        """When no .gitignore file exists, from_directory returns None."""
        matcher = GitIgnoreMatcher.from_directory(tmp_path)
        assert matcher is None

    def test_empty_patterns_nothing_ignored(self, tmp_path: Path) -> None:
        """Matcher with empty pattern list never reports paths as ignored."""
        matcher = GitIgnoreMatcher(root_dir=tmp_path, patterns=[])
        assert matcher.is_ignored(tmp_path / "any.file") is False

    def test_none_patterns_nothing_ignored(self, tmp_path: Path) -> None:
        """Matcher with None patterns behaves like empty list."""
        matcher = GitIgnoreMatcher(root_dir=tmp_path, patterns=None)
        assert matcher.is_ignored(tmp_path / "any.file") is False

    def test_negation_pattern_unignores(self, tmp_path: Path) -> None:
        """Negation pattern (!) overrides a previous ignore."""
        matcher = GitIgnoreMatcher(root_dir=tmp_path, patterns=["*.log", "!important.log"])
        assert matcher.is_ignored(tmp_path / "debug.log") is True
        assert matcher.is_ignored(tmp_path / "important.log") is False

    def test_path_outside_root_not_ignored(self, tmp_path: Path) -> None:
        """Paths outside the root directory are never ignored."""
        matcher = GitIgnoreMatcher(root_dir=tmp_path, patterns=["*.pyc"])
        outside = Path("/some/completely/other/path/file.pyc")
        assert matcher.is_ignored(outside) is False

    def test_exact_name_match(self, tmp_path: Path) -> None:
        """Exact name pattern (no glob, no trailing /) matches path parts."""
        matcher = GitIgnoreMatcher(root_dir=tmp_path, patterns=["thumbs.db"])
        assert matcher.is_ignored(tmp_path / "thumbs.db") is True
        assert matcher.is_ignored(tmp_path / "sub" / "thumbs.db") is True
        assert matcher.is_ignored(tmp_path / "readme.md") is False

    def test_glob_matches_nested_path(self, tmp_path: Path) -> None:
        """Glob pattern matches file in nested directory."""
        matcher = GitIgnoreMatcher(root_dir=tmp_path, patterns=["*.log"])
        nested = tmp_path / "sub" / "deep" / "trace.log"
        assert matcher.is_ignored(nested) is True

    def test_directory_pattern_matches_nested_file(self, tmp_path: Path) -> None:
        """Directory pattern with trailing slash matches nested files."""
        matcher = GitIgnoreMatcher(root_dir=tmp_path, patterns=["node_modules/"])
        assert matcher.is_ignored(tmp_path / "node_modules" / "pkg" / "index.js") is True
        assert matcher.is_ignored(tmp_path / "src" / "app.js") is False


# ---------------------------------------------------------------------------
# Additional frontmatter edge cases
# ---------------------------------------------------------------------------


class TestParseFrontmatterEdgeCases:
    """Additional edge-case tests for parse_frontmatter."""

    def test_leading_whitespace_before_delimiter_still_parsed(self) -> None:
        """Content with leading whitespace before --- is stripped, so frontmatter is parsed."""
        content = "  ---\nname: test\n---\n"
        result = parse_frontmatter(content)
        assert result == {"name": "test"}

    def test_text_before_delimiter_returns_empty(self) -> None:
        """Content with non-whitespace text before --- is not frontmatter."""
        content = "Some text\n---\nname: test\n---\n"
        assert parse_frontmatter(content) == {}

    def test_unicode_values(self) -> None:
        """Frontmatter with unicode characters is parsed correctly."""
        content = "---\nname: Агент\nauthor: 日本語\n---\n"
        result = parse_frontmatter(content)
        assert result["name"] == "Агент"
        assert result["author"] == "日本語"

    def test_multiple_colons_in_value(self) -> None:
        """Values with multiple colons are auto-quoted."""
        content = "---\nname: foo: bar: baz\n---\n"
        result = parse_frontmatter(content)
        assert result["name"] == "foo: bar: baz"

    def test_frontmatter_with_only_body_after(self) -> None:
        """Body content after second delimiter does not affect parsing."""
        content = "---\nname: test\n---\n# Heading\nSome body\nMore lines\n"
        result = parse_frontmatter(content)
        assert result == {"name": "test"}

    def test_delimiter_in_body_not_confused(self) -> None:
        """A third --- in body content does not confuse parsing."""
        content = "---\nname: test\n---\n---\nThis is body\n---\n"
        result = parse_frontmatter(content)
        assert result == {"name": "test"}

    def test_nested_yaml_mapping(self) -> None:
        """Frontmatter with nested mapping (still a dict) is parsed."""
        content = "---\nname: test\nmeta:\n  key: value\n---\n"
        result = parse_frontmatter(content)
        assert result["name"] == "test"
        assert result["meta"] == {"key": "value"}

    @pytest.mark.parametrize(
        "content",
        [
            "---\n---\n",
            "---\n   \n---\n",
            "---\n\t\n---\n",
        ],
        ids=["empty-block", "whitespace-block", "tab-block"],
    )
    def test_empty_or_whitespace_variants(self, content: str) -> None:
        """Various empty/whitespace YAML blocks return empty dict."""
        assert parse_frontmatter(content) == {}

    def test_large_frontmatter_content(self) -> None:
        """Large frontmatter block is parsed without issues."""
        lines = [f"key{i}: value{i}" for i in range(200)]
        content = "---\n" + "\n".join(lines) + "\n---\n"
        result = parse_frontmatter(content)
        assert len(result) == 200
        assert result["key0"] == "value0"
        assert result["key199"] == "value199"


# ---------------------------------------------------------------------------
# Platform resolution edge cases
# ---------------------------------------------------------------------------


class TestPlatformDisplayNames:
    """Tests for TARGET_PLATFORM_DISPLAY constant."""

    def test_display_name(self) -> None:
        assert TARGET_PLATFORM_DISPLAY == "OpenCode"


# ---------------------------------------------------------------------------
# _is_quoted helper
# ---------------------------------------------------------------------------


class TestIsQuoted:
    """Tests for the _is_quoted private helper."""

    def test_double_quoted(self) -> None:
        assert _is_quoted('"hello"') is True

    def test_single_quoted(self) -> None:
        assert _is_quoted("'hello'") is True

    def test_unquoted(self) -> None:
        assert _is_quoted("hello") is False

    def test_empty_string(self) -> None:
        assert _is_quoted("") is False

    def test_single_char(self) -> None:
        assert _is_quoted('"') is False

    def test_mismatched_quotes(self) -> None:
        assert _is_quoted("\"hello'") is False

    def test_two_chars_quotes(self) -> None:
        assert _is_quoted('""') is True

    def test_two_chars_single_quotes(self) -> None:
        assert _is_quoted("''") is True


# ---------------------------------------------------------------------------
# _quote_colon_values edge cases
# ---------------------------------------------------------------------------


class TestQuoteColonValuesEdgeCases:
    """Additional edge cases for _quote_colon_values."""

    def test_multiple_colons_in_value(self) -> None:
        result = _quote_colon_values("name: a: b: c")
        assert result == 'name: "a: b: c"'

    def test_non_key_line_preserved(self) -> None:
        """Lines that don't match the key: value pattern are preserved."""
        line = "  - list item"
        assert _quote_colon_values(line) == line

    def test_empty_input(self) -> None:
        assert _quote_colon_values("") == ""

    def test_key_with_underscore(self) -> None:
        result = _quote_colon_values("my_key: value: with: colons")
        assert result == 'my_key: "value: with: colons"'

    def test_key_with_dash(self) -> None:
        result = _quote_colon_values("my-key: val: ue")
        assert result == 'my-key: "val: ue"'


# ---------------------------------------------------------------------------
# _validate_field_type
# ---------------------------------------------------------------------------


class TestValidateFieldType:
    """Tests for _validate_field_type helper."""

    def test_missing_field_passes(self) -> None:
        """Missing field does not raise."""
        _validate_field_type({}, "name", str)

    def test_none_value_passes(self) -> None:
        """None value is treated as missing and passes."""
        _validate_field_type({"name": None}, "name", str)

    def test_correct_type_passes(self) -> None:
        """Field with correct type passes validation."""
        _validate_field_type({"name": "test"}, "name", str)

    def test_wrong_type_raises(self) -> None:
        """Field with wrong type raises AgentfilesError."""
        with pytest.raises(AgentfilesError, match="must be str"):
            _validate_field_type({"name": 123}, "name", str)

    def test_tuple_expected_type(self) -> None:
        """Validation with multiple allowed types."""
        _validate_field_type({"val": "text"}, "val", (str, int))
        _validate_field_type({"val": 42}, "val", (str, int))

    def test_tuple_expected_type_wrong_raises(self) -> None:
        """Wrong type with tuple expected raises with all type names."""
        with pytest.raises(AgentfilesError, match="must be str or int"):
            _validate_field_type({"val": [1, 2]}, "val", (str, int))


# ---------------------------------------------------------------------------
# parse_gitignore edge cases
# ---------------------------------------------------------------------------


class TestParseGitignoreEdgeCases:
    """Additional edge cases for parse_gitignore."""

    def test_empty_file_returns_empty_list(self, tmp_path: Path) -> None:
        gitignore = tmp_path / ".gitignore"
        gitignore.write_text("")
        assert parse_gitignore(gitignore) == []

    def test_only_comments_returns_empty(self, tmp_path: Path) -> None:
        gitignore = tmp_path / ".gitignore"
        gitignore.write_text("# comment 1\n# comment 2\n")
        assert parse_gitignore(gitignore) == []

    def test_only_blank_lines_returns_empty(self, tmp_path: Path) -> None:
        gitignore = tmp_path / ".gitignore"
        gitignore.write_text("\n\n  \n\n")
        assert parse_gitignore(gitignore) == []

    def test_inline_comment_not_special(self, tmp_path: Path) -> None:
        """Lines with # in the middle are NOT treated as comments."""
        gitignore = tmp_path / ".gitignore"
        gitignore.write_text("path/#with_hash\n")
        patterns = parse_gitignore(gitignore)
        assert patterns == ["path/#with_hash"]

    def test_whitespace_stripped(self, tmp_path: Path) -> None:
        gitignore = tmp_path / ".gitignore"
        gitignore.write_text("  *.pyc  \n  build/  \n")
        patterns = parse_gitignore(gitignore)
        assert patterns == ["*.pyc", "build/"]


# ---------------------------------------------------------------------------
# TargetPaths.is_valid
# ---------------------------------------------------------------------------


class TestTargetPathsIsValid:
    """Tests for TargetPaths.is_valid property."""

    def test_valid_when_dir_exists(self, tmp_path: Path) -> None:
        tp = TargetPaths(config_dir=tmp_path)
        assert tp.is_valid is True

    def test_invalid_when_dir_does_not_exist(self) -> None:
        tp = TargetPaths(config_dir=Path("/nonexistent/dir"))
        assert tp.is_valid is False


# ---------------------------------------------------------------------------
# Sync state data classes
# ---------------------------------------------------------------------------


class TestItemState:
    """Tests for ItemState frozen data class."""

    def test_defaults(self) -> None:
        state = ItemState()
        assert state.synced_at == ""

    def test_custom_values(self) -> None:
        state = ItemState(
            synced_at="2025-01-15T10:30:00Z",
        )
        assert state.synced_at == "2025-01-15T10:30:00Z"

    def test_frozen_immutability(self) -> None:
        state = ItemState(synced_at="abc")
        with pytest.raises(AttributeError):
            state.synced_at = "changed"  # type: ignore[misc]


class TestSyncState:
    """Tests for SyncState mutable data class."""

    def test_defaults(self) -> None:
        state = SyncState()
        assert state.version == "1.0"
        assert state.last_sync == ""
        assert state.items == {}

    def test_mutable_fields(self) -> None:
        state = SyncState()
        state.version = "2.0"
        state.last_sync = "2025-06-01T00:00:00Z"
        state.items["agent/coder"] = ItemState(synced_at="2025-01-01T00:00:00Z")
        assert state.version == "2.0"
        assert state.last_sync == "2025-06-01T00:00:00Z"
        assert "agent/coder" in state.items

    def test_not_frozen(self) -> None:
        """SyncState is mutable (not frozen)."""
        state = SyncState()
        state.version = "3.0"
        assert state.version == "3.0"


# ---------------------------------------------------------------------------
# CHARS_PER_TOKEN constant
# ---------------------------------------------------------------------------


class TestCharsPerToken:
    """Tests for CHARS_PER_TOKEN constant usage."""

    def test_value(self) -> None:
        assert CHARS_PER_TOKEN == 4

    def test_estimate_tokens_from_content_uses_constant(self) -> None:
        content = "a" * CHARS_PER_TOKEN
        assert estimate_tokens_from_content(content) == 1

    def test_estimate_tokens_less_than_one_char_per_token(self) -> None:
        # Function guarantees at least 1 token for any non-empty string.
        assert estimate_tokens_from_content("abc") == 1


# ---------------------------------------------------------------------------
# item_from_file — encoding edge case
# ---------------------------------------------------------------------------


class TestItemFromFileEdgeCases:
    """Additional edge cases for item_from_file."""

    def test_file_with_unicode_frontmatter(self, tmp_path: Path) -> None:
        f = tmp_path / "unicode-agent.md"
        f.write_text(
            "---\nname: тест-агент\ndescription: Описание\n---\n# Тело",
            encoding="utf-8",
        )
        item = item_from_file(f, ItemType.AGENT)
        assert item.name == "тест-агент"
        assert item.meta is not None
        assert item.meta.description == "Описание"

    def test_file_with_complex_tools(self, tmp_path: Path) -> None:
        f = tmp_path / "tools-agent.md"
        f.write_text(
            "---\nname: tooled\ntools:\n  bash: true\n  read: true\n  write: false\n---\n",
            encoding="utf-8",
        )
        item = item_from_file(f, ItemType.AGENT)
        assert item.meta is not None
        assert item.meta.tools == {"bash": True, "read": True, "write": False}


# ---------------------------------------------------------------------------
# item_from_directory — command type
# ---------------------------------------------------------------------------


class TestItemFromDirectoryCommand:
    """Tests for item_from_directory with ItemType.COMMAND."""

    def test_command_directory_with_dirname_md(self, tmp_path: Path) -> None:
        cmd_dir = tmp_path / "deploy"
        cmd_dir.mkdir()
        (cmd_dir / "deploy.md").write_text("---\nname: deploy\nversion: 1.0.0\n---\n# Deploy")
        item = item_from_directory(cmd_dir, ItemType.COMMAND)
        assert item.item_type == ItemType.COMMAND
        assert item.name == "deploy"
        assert item.item_key == "command/deploy"
