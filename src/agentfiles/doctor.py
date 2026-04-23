"""System health diagnostics for the agentfiles CLI.

Provides :func:`run_doctor` which checks the local environment for common
issues — missing config files, inaccessible platform directories, and
absent tool binaries.

Each check produces a :class:`CheckResult` with a status level (OK,
WARNING, ERROR).  Results are aggregated into a :class:`DoctorReport`.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from agentfiles.config import _iter_config_search_paths, _read_yaml_file, get_state_path
from agentfiles.models import TARGET_PLATFORM_DISPLAY, ConfigError, ItemType

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


class CheckStatus(str, Enum):
    """Status level for a single doctor check."""

    OK = "ok"
    WARNING = "warning"
    ERROR = "error"

    @property
    def icon(self) -> str:
        """Terminal icon for this status level."""
        _icons: dict[CheckStatus, str] = {
            CheckStatus.OK: "\u2705",
            CheckStatus.WARNING: "\u26a0\ufe0f",
            CheckStatus.ERROR: "\u274c",
        }
        return _icons[self]


@dataclass(frozen=True)
class CheckResult:
    """Outcome of a single diagnostic check."""

    label: str
    status: CheckStatus
    detail: str


@dataclass
class DoctorReport:
    """Aggregated results of all doctor checks."""

    results: list[CheckResult] = field(default_factory=list)

    @property
    def error_count(self) -> int:
        return sum(1 for r in self.results if r.status == CheckStatus.ERROR)

    @property
    def warning_count(self) -> int:
        return sum(1 for r in self.results if r.status == CheckStatus.WARNING)

    @property
    def exit_code(self) -> int:
        """``0`` if all OK, ``1`` if any ERROR."""
        return 1 if self.error_count > 0 else 0


# ---------------------------------------------------------------------------
# Individual checks
# ---------------------------------------------------------------------------


def _check_config_file(config_path: Path | None) -> CheckResult:
    """Check that the agentfiles config file exists and is valid YAML."""
    label = "Config file"

    try:
        for path in _iter_config_search_paths(config_path):
            if path.is_file():
                try:
                    _read_yaml_file(path)
                    return CheckResult(label, CheckStatus.OK, f"{_short(path)} (found, valid)")
                except ConfigError as exc:
                    return CheckResult(label, CheckStatus.ERROR, f"{_short(path)} (INVALID: {exc})")
    except ConfigError:
        return CheckResult(label, CheckStatus.ERROR, f"{config_path} (NOT FOUND)")

    return CheckResult(label, CheckStatus.WARNING, "not found (using defaults)")


def _check_source_directory(source_dir: Path | None) -> CheckResult:
    """Check that the source directory exists and contains item dirs."""
    label = "Source directory"
    if source_dir is None:
        return CheckResult(label, CheckStatus.WARNING, "not specified")

    if not source_dir.is_dir():
        return CheckResult(label, CheckStatus.ERROR, f"{_short(source_dir)} (NOT FOUND)")

    # Derive expected directory names from ItemType so new types are never missed.
    item_dirs = [t.plural for t in ItemType]
    found = sum(1 for d in item_dirs if (source_dir / d).is_dir())
    return CheckResult(label, CheckStatus.OK, f"{_short(source_dir)} ({found} item dirs)")


def _check_git() -> CheckResult:
    """Check that git is installed and accessible."""
    git_path = shutil.which("git")
    if git_path is None:
        return CheckResult("Git", CheckStatus.ERROR, "NOT FOUND (install git)")

    try:
        result = subprocess.run(
            [git_path, "--version"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        version = result.stdout.strip().replace("git version ", "")
        return CheckResult("Git", CheckStatus.OK, f"{version} ({git_path})")
    except (subprocess.TimeoutExpired, OSError) as exc:
        return CheckResult("Git", CheckStatus.ERROR, f"{git_path} (error: {exc})")


def _check_platform_dir(display_name: str, config_dir: Path) -> CheckResult:
    """Check a discovered platform directory for writability."""
    label = f"Platform: {display_name}"
    short = _short(config_dir)

    if not os.access(config_dir, os.W_OK):
        return CheckResult(label, CheckStatus.WARNING, f"{short} (found, read-only)")

    item_count = _count_items(config_dir)
    suffix = f", {item_count} items" if item_count > 0 else ""
    return CheckResult(label, CheckStatus.OK, f"{short} (found, writable{suffix})")


def _check_state_file(source_dir: Path | None) -> CheckResult:
    """Check the sync state file for existence and validity."""
    label = "State file"
    if source_dir is None:
        return CheckResult(label, CheckStatus.WARNING, "no source directory")

    state_path = get_state_path(source_dir)
    short = _short(state_path)

    if not state_path.is_file():
        return CheckResult(
            label, CheckStatus.WARNING, f"{short} (not found — run 'agentfiles pull')"
        )

    try:
        data = _read_yaml_file(state_path)
        if "version" in data or "items" in data:
            return CheckResult(label, CheckStatus.OK, f"{short} (found, valid)")
        return CheckResult(label, CheckStatus.WARNING, f"{short} (found, missing expected keys)")
    except ConfigError as exc:
        return CheckResult(label, CheckStatus.ERROR, f"{short} (INVALID: {exc})")


def _check_platform_tools() -> list[CheckResult]:
    """Check which AI platform CLI binaries are installed."""
    path = shutil.which("opencode")
    if path is not None:
        return [CheckResult("Tool: OpenCode CLI", CheckStatus.OK, f"found ({path})")]
    return [CheckResult("Tool: OpenCode CLI", CheckStatus.WARNING, "not found")]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _short(path: Path) -> str:
    """Replace home directory prefix with ``~`` for display."""
    home = str(Path.home())
    full = str(path)
    if full.startswith(home + "/"):
        return "~" + full[len(home) :]
    return full


def _count_items(directory: Path) -> int:
    """Count non-hidden entries inside *directory*."""
    try:
        return sum(1 for e in os.scandir(directory) if not e.name.startswith("."))
    except OSError:
        return 0


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def run_doctor(
    config_path: Path | None = None,
    source_dir: Path | None = None,
) -> DoctorReport:
    """Run all diagnostic checks and return an aggregated report.

    Args:
        config_path: Explicit path to the config file, or ``None`` for
            auto-discovery.
        source_dir: Path to the source repository, or ``None`` if not
            available.
    """
    from agentfiles.target import TargetDiscovery

    report = DoctorReport()

    report.results.append(_check_config_file(config_path))
    report.results.append(_check_source_directory(source_dir))
    report.results.append(_check_git())

    # Use TargetDiscovery to find the target platform directory.
    discovery = TargetDiscovery()
    discovered = discovery.discover_all()
    if discovered is not None:
        report.results.append(
            _check_platform_dir(
                TARGET_PLATFORM_DISPLAY,
                discovered.config_dir,
            )
        )
    else:
        report.results.append(
            CheckResult("Platform", CheckStatus.WARNING, "no platform directory found")
        )

    report.results.append(_check_state_file(source_dir))
    report.results.extend(_check_platform_tools())

    return report


def format_doctor_report(report: DoctorReport) -> str:
    """Format a doctor report as a human-readable string."""
    lines: list[str] = ["Checking agentfiles environment...", ""]

    label_width = max((len(r.label) for r in report.results), default=0) + 2

    for result in report.results:
        padded = result.label.ljust(label_width)
        lines.append(f"  {result.status.icon} {padded}{result.detail}")

    lines.append("")
    parts: list[str] = []
    if report.error_count > 0:
        parts.append(f"{report.error_count} error{'s' if report.error_count != 1 else ''}")
    if report.warning_count > 0:
        parts.append(f"{report.warning_count} warning{'s' if report.warning_count != 1 else ''}")
    if not parts:
        lines.append("All checks passed.")
    else:
        lines.append(", ".join(parts) + ".")

    return "\n".join(lines)
