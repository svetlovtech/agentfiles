"""Tests for agentfiles.doctor — environment diagnostics."""

from __future__ import annotations

from pathlib import Path
from unittest import mock

from agentfiles.doctor import (
    CheckResult,
    CheckStatus,
    DoctorReport,
    _check_config_file,
    _check_git,
    _check_platform_dir,
    _check_platform_tools,
    _check_source_directory,
    _check_state_file,
    _count_items,
    _short,
    format_doctor_report,
    run_doctor,
)

# ---------------------------------------------------------------------------
# CheckStatus / CheckResult / DoctorReport
# ---------------------------------------------------------------------------


class TestCheckStatus:
    def test_icon_ok(self) -> None:
        assert CheckStatus.OK.icon == "\u2705"

    def test_icon_warning(self) -> None:
        assert CheckStatus.WARNING.icon == "\u26a0\ufe0f"

    def test_icon_error(self) -> None:
        assert CheckStatus.ERROR.icon == "\u274c"


class TestDoctorReport:
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
                CheckResult("c", CheckStatus.ERROR, ""),
            ]
        )
        assert report.error_count == 2
        assert report.exit_code == 1

    def test_warning_count(self) -> None:
        report = DoctorReport(
            results=[
                CheckResult("a", CheckStatus.WARNING, ""),
                CheckResult("b", CheckStatus.OK, ""),
            ]
        )
        assert report.warning_count == 1
        assert report.exit_code == 0


# ---------------------------------------------------------------------------
# _check_config_file
# ---------------------------------------------------------------------------


class TestCheckConfigFile:
    def test_explicit_path_valid(self, tmp_path: Path) -> None:
        cfg = tmp_path / ".agentfiles.yaml"
        cfg.write_text("source: .")
        result = _check_config_file(cfg)
        assert result.status == CheckStatus.OK

    def test_explicit_path_missing(self, tmp_path: Path) -> None:
        result = _check_config_file(tmp_path / "nonexistent.yaml")
        assert result.status == CheckStatus.ERROR
        assert "NOT FOUND" in result.detail

    def test_explicit_path_invalid_yaml(self, tmp_path: Path) -> None:
        cfg = tmp_path / ".agentfiles.yaml"
        cfg.write_text("{{invalid")
        result = _check_config_file(cfg)
        assert result.status == CheckStatus.ERROR
        assert "INVALID" in result.detail

    def test_auto_discover_none(self) -> None:
        with (
            mock.patch("agentfiles.doctor.Path.cwd", return_value=Path("/nonexistent")),
            mock.patch("agentfiles.doctor.Path.home", return_value=Path("/nonexistent2")),
        ):
            result = _check_config_file(None)
        assert result.status == CheckStatus.WARNING
        assert "using defaults" in result.detail


# ---------------------------------------------------------------------------
# _check_source_directory
# ---------------------------------------------------------------------------


class TestCheckSourceDirectory:
    def test_none(self) -> None:
        result = _check_source_directory(None)
        assert result.status == CheckStatus.WARNING

    def test_missing(self) -> None:
        result = _check_source_directory(Path("/nonexistent"))
        assert result.status == CheckStatus.ERROR

    def test_exists_with_items(self, tmp_path: Path) -> None:
        (tmp_path / "agents").mkdir()
        (tmp_path / "skills").mkdir()
        result = _check_source_directory(tmp_path)
        assert result.status == CheckStatus.OK
        assert "2 item dirs" in result.detail

    def test_exists_empty(self, tmp_path: Path) -> None:
        result = _check_source_directory(tmp_path)
        assert result.status == CheckStatus.OK
        assert "0 item dirs" in result.detail


# ---------------------------------------------------------------------------
# _check_git
# ---------------------------------------------------------------------------


class TestCheckGit:
    def test_git_found(self) -> None:
        result = _check_git()
        # git is installed in CI and dev environments
        assert result.status == CheckStatus.OK

    def test_git_not_found(self) -> None:
        with mock.patch("shutil.which", return_value=None):
            result = _check_git()
        assert result.status == CheckStatus.ERROR
        assert "NOT FOUND" in result.detail

    def test_git_timeout(self) -> None:
        import subprocess

        with (
            mock.patch("shutil.which", return_value="/usr/bin/git"),
            mock.patch("subprocess.run", side_effect=subprocess.TimeoutExpired("git", 5)),
        ):
            result = _check_git()
        assert result.status == CheckStatus.ERROR


# ---------------------------------------------------------------------------
# _check_platform_dir
# ---------------------------------------------------------------------------


class TestCheckPlatformDir:
    def test_writable(self, tmp_path: Path) -> None:
        result = _check_platform_dir("TestPlatform", tmp_path)
        assert result.status == CheckStatus.OK
        assert "writable" in result.detail

    def test_with_items(self, tmp_path: Path) -> None:
        (tmp_path / "agent.md").touch()
        (tmp_path / "skill.md").touch()
        result = _check_platform_dir("TestPlatform", tmp_path)
        assert "2 items" in result.detail

    def test_read_only(self, tmp_path: Path) -> None:
        with mock.patch("os.access", return_value=False):
            result = _check_platform_dir("TestPlatform", tmp_path)
        assert result.status == CheckStatus.WARNING
        assert "read-only" in result.detail


# ---------------------------------------------------------------------------
# _check_state_file
# ---------------------------------------------------------------------------


class TestCheckStateFile:
    def test_no_source(self) -> None:
        result = _check_state_file(None)
        assert result.status == CheckStatus.WARNING

    def test_missing(self, tmp_path: Path) -> None:
        result = _check_state_file(tmp_path)
        assert result.status == CheckStatus.WARNING
        assert "not found" in result.detail

    def test_valid(self, tmp_path: Path) -> None:
        state = tmp_path / ".agentfiles.state.yaml"
        state.write_text("version: 1\nplatforms: {}")
        result = _check_state_file(tmp_path)
        assert result.status == CheckStatus.OK

    def test_invalid_yaml(self, tmp_path: Path) -> None:
        state = tmp_path / ".agentfiles.state.yaml"
        state.write_text("{{broken")
        result = _check_state_file(tmp_path)
        assert result.status == CheckStatus.ERROR

    def test_missing_keys(self, tmp_path: Path) -> None:
        state = tmp_path / ".agentfiles.state.yaml"
        state.write_text("foo: bar")
        result = _check_state_file(tmp_path)
        assert result.status == CheckStatus.WARNING
        assert "missing expected keys" in result.detail


# ---------------------------------------------------------------------------
# _check_platform_tools
# ---------------------------------------------------------------------------


class TestCheckPlatformTools:
    def test_none_found(self) -> None:
        with mock.patch("shutil.which", return_value=None):
            results = _check_platform_tools()
        statuses = [r.status for r in results]
        assert all(s == CheckStatus.WARNING for s in statuses)

    def test_some_found(self) -> None:
        def mock_which(name: str) -> str | None:
            return "/usr/bin/opencode" if name == "opencode" else None

        with mock.patch("shutil.which", side_effect=mock_which):
            results = _check_platform_tools()
        ok_results = [r for r in results if r.status == CheckStatus.OK]
        assert len(ok_results) == 1
        assert "OpenCode" in ok_results[0].label


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class TestHelpers:
    def test_short_home(self) -> None:
        home = Path.home()
        assert _short(home / "foo" / "bar").startswith("~")

    def test_short_non_home(self) -> None:
        assert _short(Path("/tmp/foo")) == "/tmp/foo"

    def test_count_items_empty(self, tmp_path: Path) -> None:
        assert _count_items(tmp_path) == 0

    def test_count_items_skips_hidden(self, tmp_path: Path) -> None:
        (tmp_path / "visible.md").touch()
        (tmp_path / ".hidden").touch()
        assert _count_items(tmp_path) == 1

    def test_count_items_bad_dir(self) -> None:
        assert _count_items(Path("/nonexistent")) == 0


# ---------------------------------------------------------------------------
# format_doctor_report
# ---------------------------------------------------------------------------


class TestFormatDoctorReport:
    def test_all_ok(self) -> None:
        report = DoctorReport(results=[CheckResult("Git", CheckStatus.OK, "2.40")])
        output = format_doctor_report(report)
        assert "All checks passed." in output

    def test_with_errors(self) -> None:
        report = DoctorReport(results=[CheckResult("Config", CheckStatus.ERROR, "missing")])
        output = format_doctor_report(report)
        assert "1 error." in output

    def test_with_warnings(self) -> None:
        report = DoctorReport(results=[CheckResult("Tool", CheckStatus.WARNING, "not found")])
        output = format_doctor_report(report)
        assert "1 warning." in output

    def test_empty_report(self) -> None:
        output = format_doctor_report(DoctorReport())
        assert "All checks passed." in output


# ---------------------------------------------------------------------------
# run_doctor (integration)
# ---------------------------------------------------------------------------


class TestRunDoctor:
    def test_runs_without_args(self) -> None:
        report = run_doctor()
        assert isinstance(report, DoctorReport)
        assert len(report.results) > 0

    def test_with_source_dir(self, tmp_path: Path) -> None:
        (tmp_path / "agents").mkdir()
        report = run_doctor(source_dir=tmp_path)
        labels = [r.label for r in report.results]
        assert "Source directory" in labels
        assert "State file" in labels

    def test_with_config_path(self, tmp_path: Path) -> None:
        cfg = tmp_path / ".agentfiles.yaml"
        cfg.write_text("source: .")
        report = run_doctor(config_path=cfg)
        config_result = next(r for r in report.results if r.label == "Config file")
        assert config_result.status == CheckStatus.OK
