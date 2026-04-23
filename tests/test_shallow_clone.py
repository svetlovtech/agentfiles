"""Tests for shallow clone and sparse checkout optimisation.

Covers:
- ``shallow_clone`` helper in ``git.py``
- ``sparse_checkout_init`` helper in ``git.py``
- ``SourceResolver`` uses shallow clone + sparse checkout by default
- ``--full-clone`` flag disables sparse checkout
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from agentfiles.git import shallow_clone, sparse_checkout_init
from agentfiles.models import ItemType, SourceError, SourceInfo, SourceType
from agentfiles.source import (
    _SPARSE_CHECKOUT_DIRS,
    SourceResolver,
    SubprocessGitBackend,
)

# ---------------------------------------------------------------------------
# Markers
# ---------------------------------------------------------------------------

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# shallow_clone
# ---------------------------------------------------------------------------


class TestShallowClone:
    """Tests for ``agentfiles.git.shallow_clone``."""

    @patch("agentfiles.git.run_git")
    def test_default_depth(self, mock_run: MagicMock, tmp_path: Path) -> None:
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr=""
        )
        shallow_clone("https://example.com/repo.git", tmp_path / "dest")
        mock_run.assert_called_once_with(
            "clone",
            "--depth",
            "1",
            "https://example.com/repo.git",
            str(tmp_path / "dest"),
            timeout=120,
        )

    @patch("agentfiles.git.run_git")
    def test_custom_branch_and_depth(self, mock_run: MagicMock, tmp_path: Path) -> None:
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr=""
        )
        shallow_clone(
            "https://example.com/repo.git",
            tmp_path / "dest",
            branch="develop",
            depth=3,
        )
        mock_run.assert_called_once_with(
            "clone",
            "--depth",
            "3",
            "--branch",
            "develop",
            "https://example.com/repo.git",
            str(tmp_path / "dest"),
            timeout=120,
        )

    @patch("agentfiles.git.run_git")
    def test_no_branch(self, mock_run: MagicMock, tmp_path: Path) -> None:
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr=""
        )
        shallow_clone("https://example.com/repo.git", tmp_path / "dest")
        args_passed = mock_run.call_args[0]
        assert "--branch" not in args_passed


# ---------------------------------------------------------------------------
# sparse_checkout_init
# ---------------------------------------------------------------------------


class TestSparseCheckoutInit:
    """Tests for ``agentfiles.git.sparse_checkout_init``."""

    @patch("agentfiles.git.run_git")
    def test_calls_init_and_set(self, mock_run: MagicMock, tmp_path: Path) -> None:
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr=""
        )
        sparse_checkout_init(tmp_path, ["agents", "skills", "commands"])
        assert mock_run.call_count == 2
        mock_run.assert_any_call(
            "sparse-checkout",
            "init",
            "--cone",
            cwd=str(tmp_path),
            timeout=30,
        )
        mock_run.assert_any_call(
            "sparse-checkout",
            "set",
            "agents",
            "skills",
            "commands",
            cwd=str(tmp_path),
            timeout=30,
        )

    @patch("agentfiles.git.run_git")
    def test_skips_set_when_init_fails(self, mock_run: MagicMock, tmp_path: Path) -> None:
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=1, stdout="", stderr="error"
        )
        sparse_checkout_init(tmp_path, ["agents"])
        # Only init is called; set is skipped because init failed
        assert mock_run.call_count == 1


# ---------------------------------------------------------------------------
# SubprocessGitBackend.clone with sparse checkout
# ---------------------------------------------------------------------------


class TestSubprocessGitBackendClone:
    """Tests for ``SubprocessGitBackend.clone`` sparse checkout integration."""

    @patch("agentfiles.source.sparse_checkout_init")
    @patch("agentfiles.source.run_git")
    def test_default_clone_uses_sparse(
        self,
        mock_run_git: MagicMock,
        mock_sparse: MagicMock,
        tmp_path: Path,
    ) -> None:
        mock_run_git.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr=""
        )
        backend = SubprocessGitBackend()
        target = tmp_path / "repo"
        backend.clone("https://example.com/repo.git", target)
        mock_run_git.assert_called_once()
        mock_sparse.assert_called_once_with(target, _SPARSE_CHECKOUT_DIRS)

    @patch("agentfiles.source.sparse_checkout_init")
    @patch("agentfiles.source.run_git")
    def test_full_clone_skips_sparse(
        self,
        mock_run_git: MagicMock,
        mock_sparse: MagicMock,
        tmp_path: Path,
    ) -> None:
        mock_run_git.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr=""
        )
        backend = SubprocessGitBackend()
        target = tmp_path / "repo"
        backend.clone("https://example.com/repo.git", target, full_clone=True)
        mock_run_git.assert_called_once()
        mock_sparse.assert_not_called()

    @patch("agentfiles.source.run_git")
    def test_clone_failure_raises_source_error(
        self,
        mock_run_git: MagicMock,
        tmp_path: Path,
    ) -> None:
        mock_run_git.return_value = subprocess.CompletedProcess(
            args=[], returncode=128, stdout="", stderr="repository not found"
        )
        backend = SubprocessGitBackend()
        with pytest.raises(SourceError, match="clone failed"):
            backend.clone("https://example.com/repo.git", tmp_path / "repo")


# ---------------------------------------------------------------------------
# SourceResolver uses shallow clone by default
# ---------------------------------------------------------------------------


class TestSourceResolverShallowClone:
    """Test that SourceResolver passes full_clone flag correctly."""

    def test_default_resolver_passes_full_clone_false(self, tmp_path: Path) -> None:
        mock_backend = MagicMock()
        mock_backend.is_git_repo.return_value = False
        resolver = SourceResolver(git_backend=mock_backend)

        source_info = SourceInfo(
            source_type=SourceType.GIT_URL,
            path=Path("https://example.com/user/repo.git"),
            original_input="https://example.com/user/repo.git",
            is_git_repo=False,
        )
        resolver.resolve(source_info, cache_dir=tmp_path)
        mock_backend.clone.assert_called_once()
        _, kwargs = mock_backend.clone.call_args
        assert kwargs.get("full_clone") is False

    def test_full_clone_resolver_passes_full_clone_true(self, tmp_path: Path) -> None:
        mock_backend = MagicMock()
        mock_backend.is_git_repo.return_value = False
        resolver = SourceResolver(git_backend=mock_backend, full_clone=True)

        source_info = SourceInfo(
            source_type=SourceType.GIT_URL,
            path=Path("https://example.com/user/repo.git"),
            original_input="https://example.com/user/repo.git",
            is_git_repo=False,
        )
        resolver.resolve(source_info, cache_dir=tmp_path)
        mock_backend.clone.assert_called_once()
        _, kwargs = mock_backend.clone.call_args
        assert kwargs.get("full_clone") is True

    def test_existing_clone_not_affected(self, tmp_path: Path) -> None:
        """Existing cloned repos are updated via pull, not re-cloned."""
        target = tmp_path / "repo"
        target.mkdir()

        mock_backend = MagicMock()
        mock_backend.is_git_repo.return_value = True
        resolver = SourceResolver(git_backend=mock_backend)

        source_info = SourceInfo(
            source_type=SourceType.GIT_URL,
            path=Path("https://example.com/user/repo.git"),
            original_input="https://example.com/user/repo.git",
            is_git_repo=False,
        )
        resolver.resolve(source_info, cache_dir=tmp_path)
        mock_backend.pull.assert_called_once_with(target)
        mock_backend.clone.assert_not_called()


# ---------------------------------------------------------------------------
# --full-clone CLI flag
# ---------------------------------------------------------------------------


class TestFullCloneCLIFlag:
    """Test that --full-clone flag is wired through to SourceResolver."""

    def test_full_clone_flag_parsed(self) -> None:
        from agentfiles.cli import build_parser

        parser = build_parser()
        args = parser.parse_args(["pull", "--full-clone"])
        assert args.full_clone is True

    def test_default_no_full_clone(self) -> None:
        from agentfiles.cli import build_parser

        parser = build_parser()
        args = parser.parse_args(["pull"])
        assert args.full_clone is False


# ---------------------------------------------------------------------------
# _SPARSE_CHECKOUT_DIRS covers all ItemTypes
# ---------------------------------------------------------------------------


class TestSparseCheckoutDirs:
    """Verify the sparse checkout directory list stays in sync with ItemType."""

    def test_covers_all_item_types(self) -> None:
        expected = {t.plural for t in ItemType}
        actual = set(_SPARSE_CHECKOUT_DIRS)
        assert actual == expected
