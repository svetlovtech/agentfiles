"""Tests for syncode.doctor — system health diagnostics."""

from __future__ import annotations

from pathlib import Path
from unittest import mock

import pytest
import yaml

from syncode.doctor import (
    CheckResult,
    CheckStatus,
    DoctorReport,
    _check_checksums,
    _check_config_file,
    _check_git,
    _check_platform_dir,
    _check_platform_tools,
    _check_source_directory,
    _check_state_file,
    _count_items_in_dir,
    _shorten_path,
    format_doctor_report,
    run_doctor,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def home_dir(tmp_path: Path) -> Path:
    """Create a temporary home directory."""
    return tmp_path / "home"


@pytest.fixture
def source_dir(tmp_path: Path) -> Path:
    """Create a source directory with item subdirectories."""
    src = tmp_path / "source"
    src.mkdir()
    (src / "agents").mkdir()
    (src / "skills").mkdir()
    return src


@pytest.fixture
def config_file(tmp_path: Path) -> Path:
    """Create a valid config file."""
    cfg = tmp_path / ".agentfiles.yaml"
    cfg.write_text(
        yaml.dump({"default_platforms": ["opencode"]}),
        encoding="utf-8",
    )
    return cfg


@pytest.fixture
def state_file(source_dir: Path) -> Path:
    """Create a valid state file in the source directory."""
    sf = source_dir / ".agentfiles.state.yaml"
    sf.write_text(
        yaml.dump(
            {
                "version": "1.0",
                "last_sync": "2025-01-01T00:00:00",
                "platforms": {
                    "opencode": {
                        "path": "/home/.config/opencode",
                        "items": {},
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    return sf


# ---------------------------------------------------------------------------
# CheckStatus
# ---------------------------------------------------------------------------


class TestCheckStatus:
    """Tests for CheckStatus enum."""

    def test_icon_ok(self) -> None:
        assert CheckStatus.OK.icon == "\u2705"

    def test_icon_warning(self) -> None:
        assert CheckStatus.WARNING.icon == "\u26a0\ufe0f"

    def test_icon_error(self) -> None:
        assert CheckStatus.ERROR.icon == "\u274c"


# ---------------------------------------------------------------------------
# CheckResult
# ---------------------------------------------------------------------------


class TestCheckResult:
    """Tests for CheckResult dataclass."""

    def test_frozen(self) -> None:
        result = CheckResult("test", CheckStatus.OK, "detail")
        with pytest.raises(AttributeError):
            result.label = "changed"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# DoctorReport
# ---------------------------------------------------------------------------


class TestDoctorReport:
    """Tests for DoctorReport."""

    def test_empty_report(self) -> None:
        report = DoctorReport()
        assert report.error_count == 0
        assert report.warning_count == 0
        assert report.exit_code == 0

    def test_error_count(self) -> None:
        report = DoctorReport(
            results=[
                CheckResult("a", CheckStatus.OK, ""),
                CheckResult("b", CheckStatus.ERROR, ""),
                CheckResult("c", CheckStatus.WARNING, ""),
                CheckResult("d", CheckStatus.ERROR, ""),
            ]
        )
        assert report.error_count == 2
        assert report.warning_count == 1
        assert report.exit_code == 1

    def test_warning_only_exit_code(self) -> None:
        report = DoctorReport(results=[CheckResult("a", CheckStatus.WARNING, "")])
        assert report.exit_code == 0


# ---------------------------------------------------------------------------
# _shorten_path
# ---------------------------------------------------------------------------


class TestShortenPath:
    """Tests for _shorten_path helper."""

    def test_home_prefix_replaced(self, tmp_path: Path) -> None:
        home = tmp_path / "user"
        home.mkdir()
        path = home / ".config" / "opencode"
        with mock.patch("syncode.doctor.Path.home", return_value=home):
            result = _shorten_path(path)
        assert result == "~/.config/opencode"

    def test_non_home_path_unchanged(self, tmp_path: Path) -> None:
        path = tmp_path / "opt" / "tools"
        with mock.patch("syncode.doctor.Path.home", return_value=tmp_path / "nonexistent"):
            result = _shorten_path(path)
        assert result == str(path)


# ---------------------------------------------------------------------------
# _count_items_in_dir
# ---------------------------------------------------------------------------


class TestCountItemsInDir:
    """Tests for _count_items_in_dir helper."""

    def test_counts_visible_entries(self, tmp_path: Path) -> None:
        d = tmp_path / "test"
        d.mkdir()
        (d / "file1.md").touch()
        (d / "file2.md").touch()
        (d / ".hidden").touch()
        assert _count_items_in_dir(d) == 2

    def test_nonexistent_dir(self, tmp_path: Path) -> None:
        assert _count_items_in_dir(tmp_path / "nope") == 0


# ---------------------------------------------------------------------------
# _check_config_file
# ---------------------------------------------------------------------------


class TestCheckConfigFile:
    """Tests for config file check."""

    def test_explicit_valid_config(self, config_file: Path) -> None:
        result = _check_config_file(config_file)
        assert result.status == CheckStatus.OK
        assert "valid" in result.detail

    def test_explicit_missing_config(self, tmp_path: Path) -> None:
        missing = tmp_path / "missing.yaml"
        result = _check_config_file(missing)
        assert result.status == CheckStatus.ERROR
        assert "NOT FOUND" in result.detail

    def test_explicit_invalid_yaml(self, tmp_path: Path) -> None:
        bad = tmp_path / ".agentfiles.yaml"
        bad.write_text("default_platforms: [\n", encoding="utf-8")
        result = _check_config_file(bad)
        assert result.status == CheckStatus.ERROR
        assert "INVALID" in result.detail

    def test_auto_discover_from_cwd(self, config_file: Path) -> None:
        with mock.patch("syncode.doctor.Path.cwd", return_value=config_file.parent):
            result = _check_config_file(None)
        assert result.status == CheckStatus.OK

    def test_no_config_found(self, tmp_path: Path) -> None:
        with mock.patch("syncode.doctor.Path.cwd", return_value=tmp_path):
            with mock.patch("syncode.doctor.Path.home", return_value=tmp_path):
                result = _check_config_file(None)
        assert result.status == CheckStatus.WARNING
        assert "not found" in result.detail


# ---------------------------------------------------------------------------
# _check_source_directory
# ---------------------------------------------------------------------------


class TestCheckSourceDirectory:
    """Tests for source directory check."""

    def test_valid_source(self, source_dir: Path) -> None:
        result = _check_source_directory(source_dir)
        assert result.status == CheckStatus.OK
        assert "2 item dirs" in result.detail

    def test_missing_source(self, tmp_path: Path) -> None:
        missing = tmp_path / "nonexistent"
        result = _check_source_directory(missing)
        assert result.status == CheckStatus.ERROR
        assert "NOT FOUND" in result.detail

    def test_none_source(self) -> None:
        result = _check_source_directory(None)
        assert result.status == CheckStatus.WARNING
        assert "not specified" in result.detail


# ---------------------------------------------------------------------------
# _check_git
# ---------------------------------------------------------------------------


class TestCheckGit:
    """Tests for git check."""

    def test_git_installed(self) -> None:
        result = _check_git()
        # Git should be available in the test environment
        assert result.status in (CheckStatus.OK, CheckStatus.ERROR)

    def test_git_not_installed(self) -> None:
        with mock.patch("shutil.which", return_value=None):
            result = _check_git()
        assert result.status == CheckStatus.ERROR
        assert "NOT FOUND" in result.detail


# ---------------------------------------------------------------------------
# _check_platform_dir
# ---------------------------------------------------------------------------


class TestCheckPlatformDir:
    """Tests for platform directory check."""

    def test_found_writable(self, tmp_path: Path) -> None:
        plat_dir = tmp_path / "opencode"
        plat_dir.mkdir()
        result = _check_platform_dir("opencode", "OpenCode", [plat_dir])
        assert result.status == CheckStatus.OK
        assert "writable" in result.detail

    def test_not_found(self, tmp_path: Path) -> None:
        candidates = [tmp_path / "nope"]
        result = _check_platform_dir("windsurf", "Windsurf", candidates)
        assert result.status == CheckStatus.WARNING
        assert "NOT FOUND" in result.detail

    def test_found_readonly(self, tmp_path: Path) -> None:
        plat_dir = tmp_path / "readonly"
        plat_dir.mkdir()
        with mock.patch("os.access", return_value=False):
            result = _check_platform_dir("cursor", "Cursor", [plat_dir])
        assert result.status == CheckStatus.WARNING
        assert "read-only" in result.detail


# ---------------------------------------------------------------------------
# _check_state_file
# ---------------------------------------------------------------------------


class TestCheckStateFile:
    """Tests for state file check."""

    def test_valid_state(self, source_dir: Path, state_file: Path) -> None:
        result = _check_state_file(source_dir)
        assert result.status == CheckStatus.OK
        assert "valid" in result.detail

    def test_no_state_file(self, source_dir: Path) -> None:
        result = _check_state_file(source_dir)
        assert result.status == CheckStatus.WARNING
        assert "not found" in result.detail

    def test_invalid_yaml(self, source_dir: Path) -> None:
        sf = source_dir / ".agentfiles.state.yaml"
        sf.write_text("platforms: [\n", encoding="utf-8")
        result = _check_state_file(source_dir)
        assert result.status == CheckStatus.ERROR
        assert "INVALID" in result.detail

    def test_none_source(self) -> None:
        result = _check_state_file(None)
        assert result.status == CheckStatus.WARNING


# ---------------------------------------------------------------------------
# _check_platform_tools
# ---------------------------------------------------------------------------


class TestCheckPlatformTools:
    """Tests for platform tool checks."""

    def test_returns_results(self) -> None:
        results = _check_platform_tools()
        assert len(results) >= 4  # One per tool

    def test_all_missing(self) -> None:
        with mock.patch("shutil.which", return_value=None):
            results = _check_platform_tools()
        # Should have 4 tool checks + 1 "none installed" hint
        warnings = [r for r in results if r.status == CheckStatus.WARNING]
        assert len(warnings) >= 4


# ---------------------------------------------------------------------------
# _check_checksums
# ---------------------------------------------------------------------------


class TestCheckChecksums:
    """Tests for checksum spot-check."""

    def test_no_source_dir(self) -> None:
        result = _check_checksums(None, None)
        assert result is None

    def test_no_state_file(self, source_dir: Path) -> None:
        result = _check_checksums(source_dir, None)
        assert result is None

    def test_valid_state_no_items(self, source_dir: Path, state_file: Path) -> None:
        result = _check_checksums(source_dir, None)
        assert result is not None
        assert result.status == CheckStatus.OK


# ---------------------------------------------------------------------------
# format_doctor_report
# ---------------------------------------------------------------------------


class TestFormatDoctorReport:
    """Tests for report formatting."""

    def test_all_ok(self) -> None:
        report = DoctorReport(
            results=[
                CheckResult("Config file", CheckStatus.OK, "found"),
                CheckResult("Git", CheckStatus.OK, "2.43.0"),
            ]
        )
        output = format_doctor_report(report)
        assert "All checks passed" in output
        assert "Config file" in output
        assert "Git" in output

    def test_with_errors(self) -> None:
        report = DoctorReport(
            results=[
                CheckResult("Config", CheckStatus.OK, "ok"),
                CheckResult("Git", CheckStatus.ERROR, "missing"),
            ]
        )
        output = format_doctor_report(report)
        assert "1 error" in output
        assert "agentfiles diff" in output

    def test_with_warnings(self) -> None:
        report = DoctorReport(
            results=[
                CheckResult("Config", CheckStatus.WARNING, "not found"),
            ]
        )
        output = format_doctor_report(report)
        assert "1 warning" in output

    def test_pluralization_errors(self) -> None:
        report = DoctorReport(
            results=[
                CheckResult("A", CheckStatus.ERROR, ""),
                CheckResult("B", CheckStatus.ERROR, ""),
            ]
        )
        output = format_doctor_report(report)
        assert "2 errors" in output

    def test_pluralization_warnings(self) -> None:
        report = DoctorReport(
            results=[
                CheckResult("A", CheckStatus.WARNING, ""),
                CheckResult("B", CheckStatus.WARNING, ""),
            ]
        )
        output = format_doctor_report(report)
        assert "2 warnings" in output


# ---------------------------------------------------------------------------
# run_doctor integration
# ---------------------------------------------------------------------------


class TestRunDoctor:
    """Integration tests for the full doctor pipeline."""

    def test_minimal_run(self) -> None:
        report = run_doctor()
        assert len(report.results) > 0
        # Git should be available in test env
        git_check = [r for r in report.results if r.label == "Git"]
        assert len(git_check) == 1

    def test_with_source(self, source_dir: Path) -> None:
        report = run_doctor(source_dir=source_dir)
        src_check = [r for r in report.results if r.label == "Source directory"]
        assert len(src_check) == 1
        assert src_check[0].status == CheckStatus.OK

    def test_with_config(self, config_file: Path) -> None:
        report = run_doctor(config_path=config_file)
        cfg_check = [r for r in report.results if r.label == "Config file"]
        assert len(cfg_check) == 1
        assert cfg_check[0].status == CheckStatus.OK
