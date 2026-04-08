"""Tests for GitHub Copilot, Aider, and Continue.dev platform support."""

from __future__ import annotations

from pathlib import Path

import pytest

from agentfiles.models import Platform, resolve_platform
from agentfiles.target import (
    _PLATFORM_CANDIDATE_RESOLVERS,
    _PLATFORM_SUBDIR_RESOLVERS,
    _aider_candidates,
    _aider_subdirs,
    _continue_candidates,
    _continue_subdirs,
    _copilot_candidates,
    _copilot_subdirs,
)

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Enum values
# ---------------------------------------------------------------------------


class TestPlatformEnum:
    def test_copilot_value(self) -> None:
        assert Platform.COPILOT.value == "copilot"

    def test_aider_value(self) -> None:
        assert Platform.AIDER.value == "aider"

    def test_continue_value(self) -> None:
        assert Platform.CONTINUE.value == "continue"


# ---------------------------------------------------------------------------
# Display names
# ---------------------------------------------------------------------------


class TestDisplayNames:
    def test_copilot_display_name(self) -> None:
        assert Platform.COPILOT.display_name == "GitHub Copilot"

    def test_aider_display_name(self) -> None:
        assert Platform.AIDER.display_name == "Aider"

    def test_continue_display_name(self) -> None:
        assert Platform.CONTINUE.display_name == "Continue.dev"


# ---------------------------------------------------------------------------
# Aliases
# ---------------------------------------------------------------------------


class TestAliases:
    def test_copilot_aliases(self) -> None:
        assert resolve_platform("copilot") == "copilot"
        assert resolve_platform("cp") == "copilot"
        assert resolve_platform("github-copilot") == "copilot"

    def test_aider_aliases(self) -> None:
        assert resolve_platform("aider") == "aider"

    def test_continue_aliases(self) -> None:
        assert resolve_platform("continue") == "continue"
        assert resolve_platform("cont") == "continue"
        assert resolve_platform("continue.dev") == "continue"

    def test_aliases_case_insensitive(self) -> None:
        assert resolve_platform("COPILOT") == "copilot"
        assert resolve_platform("Aider") == "aider"
        assert resolve_platform("CONTINUE") == "continue"


# ---------------------------------------------------------------------------
# Candidate resolvers
# ---------------------------------------------------------------------------


class TestCandidateResolvers:
    def test_copilot_candidates(self) -> None:
        home = Path("/home/test")
        candidates = _copilot_candidates(home)
        assert any(".github" in str(c) for c in candidates)
        assert any(".config/github-copilot" in str(c) for c in candidates)

    def test_aider_candidates(self) -> None:
        home = Path("/home/test")
        candidates = _aider_candidates(home)
        assert any(".aider" in str(c) for c in candidates)

    def test_continue_candidates(self) -> None:
        home = Path("/home/test")
        candidates = _continue_candidates(home)
        assert any(".continue" in str(c) for c in candidates)
        assert len(candidates) == 2  # project + global

    def test_dispatch_table_has_new_platforms(self) -> None:
        assert Platform.COPILOT in _PLATFORM_CANDIDATE_RESOLVERS
        assert Platform.AIDER in _PLATFORM_CANDIDATE_RESOLVERS
        assert Platform.CONTINUE in _PLATFORM_CANDIDATE_RESOLVERS


# ---------------------------------------------------------------------------
# Subdir resolvers
# ---------------------------------------------------------------------------


class TestSubdirResolvers:
    def test_copilot_subdirs(self) -> None:
        root = Path("/project/.github")
        subdirs = _copilot_subdirs(root)
        assert subdirs["agents"] == root / "copilot"
        assert subdirs["configs"] == root

    def test_aider_subdirs(self) -> None:
        root = Path("/project/.aider")
        subdirs = _aider_subdirs(root)
        assert subdirs["agents"] == root / "prompts"
        assert subdirs["configs"] == root

    def test_continue_subdirs(self) -> None:
        root = Path("/project/.continue")
        subdirs = _continue_subdirs(root)
        assert subdirs["agents"] == root / "prompts"
        assert subdirs["commands"] == root / "prompts"
        assert subdirs["configs"] == root

    def test_dispatch_table_has_new_platforms(self) -> None:
        assert Platform.COPILOT in _PLATFORM_SUBDIR_RESOLVERS
        assert Platform.AIDER in _PLATFORM_SUBDIR_RESOLVERS
        assert Platform.CONTINUE in _PLATFORM_SUBDIR_RESOLVERS


# ---------------------------------------------------------------------------
# Not in default platforms (engine.py)
# ---------------------------------------------------------------------------


class TestNotInDefaults:
    def test_new_platforms_not_in_default_tuple(self) -> None:
        from agentfiles.engine import _DEFAULT_PLATFORMS

        assert Platform.COPILOT not in _DEFAULT_PLATFORMS
        assert Platform.AIDER not in _DEFAULT_PLATFORMS
        assert Platform.CONTINUE not in _DEFAULT_PLATFORMS
