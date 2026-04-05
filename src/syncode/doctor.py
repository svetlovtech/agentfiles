"""System health diagnostics for the agentfiles CLI.

Provides the ``run_doctor()`` function that checks the local environment
for common issues — missing config files, inaccessible platform directories,
stale checksums, and absent tool binaries.

Each check produces a :class:`CheckResult` with a status level:

- ``OK``      — check passed
- ``WARNING`` — non-critical issue (e.g. optional tool not installed)
- ``ERROR``   — critical issue that will prevent normal operation

The module is importable independently (no heavy transitive imports) so
that it can be tested in isolation and executed quickly from the CLI.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

import yaml

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
            CheckStatus.OK: "\u2705",  # ✅
            CheckStatus.WARNING: "\u26a0\ufe0f",  # ⚠️
            CheckStatus.ERROR: "\u274c",  # ❌
        }
        return _icons[self]


@dataclass(frozen=True)
class CheckResult:
    """Outcome of a single diagnostic check.

    Attributes:
        label: Human-readable check name (e.g. ``"Config file"``).
        status: Whether the check passed, warned, or errored.
        detail: Additional context (path, version, reason).
    """

    label: str
    status: CheckStatus
    detail: str


@dataclass
class DoctorReport:
    """Aggregated results of all doctor checks.

    Attributes:
        results: Ordered list of individual check results.
    """

    results: list[CheckResult] = field(default_factory=list)

    @property
    def error_count(self) -> int:
        """Number of checks with ERROR status."""
        return sum(1 for r in self.results if r.status == CheckStatus.ERROR)

    @property
    def warning_count(self) -> int:
        """Number of checks with WARNING status."""
        return sum(1 for r in self.results if r.status == CheckStatus.WARNING)

    @property
    def exit_code(self) -> int:
        """Recommended exit code based on results.

        Returns:
            ``0`` if all OK, ``1`` if any ERROR, ``2`` if cannot run.
        """
        if self.error_count > 0:
            return 1
        return 0


# ---------------------------------------------------------------------------
# Individual check functions
# ---------------------------------------------------------------------------


def _check_config_file(config_path: Path | None) -> CheckResult:
    """Check that the agentfiles config file exists and is valid YAML."""
    from syncode.config import _CONFIG_FILENAMES, _read_yaml_file
    from syncode.models import ConfigError

    label = "Config file"

    if config_path is not None:
        explicit = Path(config_path)
        if not explicit.is_file():
            return CheckResult(label, CheckStatus.ERROR, f"{explicit} (NOT FOUND)")
        try:
            _read_yaml_file(explicit)
            return CheckResult(label, CheckStatus.OK, f"{explicit} (found, valid)")
        except (OSError, ValueError, ConfigError) as exc:
            return CheckResult(label, CheckStatus.ERROR, f"{explicit} (found, INVALID: {exc})")

    # Auto-discover from CWD and home
    for base in (Path.cwd(), Path.home()):
        for filename in _CONFIG_FILENAMES:
            candidate = base / filename
            if candidate.is_file():
                try:
                    _read_yaml_file(candidate)
                    short = _shorten_path(candidate)
                    return CheckResult(label, CheckStatus.OK, f"{short} (found, valid)")
                except (OSError, ValueError, ConfigError) as exc:
                    short = _shorten_path(candidate)
                    return CheckResult(label, CheckStatus.ERROR, f"{short} (found, INVALID: {exc})")

    return CheckResult(label, CheckStatus.WARNING, "not found (using defaults)")


def _check_source_directory(source_dir: Path | None) -> CheckResult:
    """Check that the source directory exists and contains items."""
    if source_dir is None:
        return CheckResult("Source directory", CheckStatus.WARNING, "not specified")

    if not source_dir.is_dir():
        short = _shorten_path(source_dir)
        return CheckResult("Source directory", CheckStatus.ERROR, f"{short} (NOT FOUND)")

    # Count item directories
    item_dirs = [
        source_dir / "agents",
        source_dir / "skills",
        source_dir / "commands",
        source_dir / "plugins",
    ]
    found = [d for d in item_dirs if d.is_dir()]
    short = _shorten_path(source_dir)
    return CheckResult(
        "Source directory",
        CheckStatus.OK,
        f"{short} (found, {len(found)} item dirs)",
    )


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


def _check_platform_dir(
    platform_name: str,
    display_name: str,
    candidates: list[Path],
) -> CheckResult:
    """Check a single platform directory for existence and writability."""
    label = f"Platform: {display_name}"

    existing = None
    for candidate in candidates:
        try:
            if candidate.is_dir():
                existing = candidate
                break
        except OSError:
            continue

    if existing is None:
        paths_str = ", ".join(_shorten_path(c) for c in candidates)
        return CheckResult(label, CheckStatus.WARNING, f"({paths_str}) NOT FOUND")

    short = _shorten_path(existing)

    # Check writability
    writable = os.access(existing, os.W_OK)
    if writable:
        # Count installed items
        item_count = _count_items_in_dir(existing)
        count_info = f", {item_count} items" if item_count > 0 else ""
        return CheckResult(label, CheckStatus.OK, f"{short} (found, writable{count_info})")

    return CheckResult(label, CheckStatus.WARNING, f"{short} (found, read-only)")


def _check_state_file(source_dir: Path | None) -> CheckResult:
    """Check the sync state file for existence and validity."""
    from syncode.config import _read_yaml_file
    from syncode.models import ConfigError

    label = "State file"

    if source_dir is None:
        return CheckResult(label, CheckStatus.WARNING, "no source directory")

    state_path = source_dir / ".agentfiles.state.yaml"
    short = _shorten_path(state_path)

    if not state_path.is_file():
        return CheckResult(
            label, CheckStatus.WARNING, f"{short} (not found — run 'agentfiles pull')"
        )

    try:
        data = _read_yaml_file(state_path)
        if "version" in data or "platforms" in data:
            return CheckResult(label, CheckStatus.OK, f"{short} (found, valid)")
        return CheckResult(label, CheckStatus.WARNING, f"{short} (found, missing expected keys)")
    except (OSError, ValueError, yaml.YAMLError, ConfigError) as exc:
        return CheckResult(label, CheckStatus.ERROR, f"{short} (found, INVALID: {exc})")


def _check_platform_tools() -> list[CheckResult]:
    """Check which AI platform binaries are installed."""
    tools = [
        ("opencode", "OpenCode CLI"),
        ("claude", "Claude Code CLI"),
        ("cursor", "Cursor CLI"),
        ("windsurf", "Windsurf CLI"),
    ]
    results: list[CheckResult] = []
    found_any = False

    for binary, display in tools:
        path = shutil.which(binary)
        if path is not None:
            found_any = True
            results.append(CheckResult(f"Tool: {display}", CheckStatus.OK, f"found ({path})"))
        else:
            results.append(CheckResult(f"Tool: {display}", CheckStatus.WARNING, "not found"))

    if not found_any:
        # Upgrade the last result to an error-level hint
        results.append(
            CheckResult(
                "Platform tools",
                CheckStatus.WARNING,
                "none installed — install at least one AI coding tool",
            )
        )

    return results


# Maximum number of items to spot-check in _check_checksums.
_CHECKSUM_SPOT_CHECK_LIMIT = 10


def _check_checksums(
    source_dir: Path | None,
    config_path: Path | None,
) -> CheckResult | None:
    """Spot-check that installed items match source checksums.

    Returns None if there is no source directory or no state file to check.
    """
    from syncode.checksum import compute_checksum

    label = "Checksums"

    if source_dir is None or not source_dir.is_dir():
        return None

    state_path = source_dir / ".agentfiles.state.yaml"
    if not state_path.is_file():
        return None

    try:
        with open(state_path, encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
        if not isinstance(data, dict):
            return None
    except (OSError, yaml.YAMLError, ValueError):
        return None

    platforms_data = data.get("platforms") or {}
    total_checked = 0
    mismatches = 0

    for _platform_name, platform_info in platforms_data.items():
        if not isinstance(platform_info, dict):
            continue
        items = platform_info.get("items") or {}
        for item_key, item_state in items.items():
            if not isinstance(item_state, dict):
                continue
            source_hash = item_state.get("source_hash", "")
            if not source_hash:
                continue

            # Build the source path from item_key (e.g. "agent/coder")
            parts = item_key.split("/", 1)
            if len(parts) != 2:
                continue

            item_type_name, item_name = parts
            # Construct the expected source path
            type_plural_map = {
                "agent": "agents",
                "skill": "skills",
                "command": "commands",
                "plugin": "plugins",
            }
            plural = type_plural_map.get(item_type_name, f"{item_type_name}s")
            source_item_dir = source_dir / plural / item_name
            if not source_item_dir.exists():
                continue

            try:
                actual_hash = compute_checksum(source_item_dir)
                total_checked += 1
                if actual_hash != source_hash:
                    mismatches += 1
            except (OSError, ValueError):
                total_checked += 1

            # Only spot-check up to _CHECKSUM_SPOT_CHECK_LIMIT items
            if total_checked >= _CHECKSUM_SPOT_CHECK_LIMIT:
                break
        if total_checked >= _CHECKSUM_SPOT_CHECK_LIMIT:
            break

    if total_checked == 0:
        return CheckResult(label, CheckStatus.OK, "no items in state to verify")

    if mismatches > 0:
        return CheckResult(
            label,
            CheckStatus.WARNING,
            f"{mismatches}/{total_checked} items differ from recorded checksums",
        )

    return CheckResult(label, CheckStatus.OK, f"{total_checked} items verified")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _shorten_path(path: Path) -> str:
    """Replace home directory prefix with ``~`` for display."""
    home = str(Path.home())
    full = str(path)
    if full.startswith(home + "/"):
        return "~" + full[len(home) :]
    if full == home:
        return "~"
    return full


def _count_items_in_dir(directory: Path) -> int:
    """Count non-hidden files and directories inside *directory*."""
    try:
        return sum(1 for entry in os.scandir(directory) if not entry.name.startswith("."))
    except OSError:
        return 0


def _get_platform_candidates() -> list[tuple[str, str, list[Path]]]:
    """Return (internal_name, display_name, candidate_paths) for all platforms."""
    home = Path.home()
    xdg = os.environ.get("XDG_CONFIG_HOME")

    opencode_candidates: list[Path] = []
    if xdg:
        opencode_candidates.append(Path(xdg).expanduser() / "opencode")
    opencode_candidates.append(home / ".config" / "opencode")

    return [
        ("opencode", "OpenCode", opencode_candidates),
        ("claude_code", "Claude Code", [home / ".claude"]),
        ("windsurf", "Windsurf", [home / ".codeium" / "windsurf" / "skills"]),
        ("cursor", "Cursor", [home / ".cursor" / "skills"]),
    ]


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

    Returns:
        A :class:`DoctorReport` with individual check results and
        summary counts.
    """
    report = DoctorReport()

    # 1. Config file
    report.results.append(_check_config_file(config_path))

    # 2. Source directory
    report.results.append(_check_source_directory(source_dir))

    # 3. Git
    report.results.append(_check_git())

    # 4. Platform directories
    for _name, display_name, candidates in _get_platform_candidates():
        report.results.append(_check_platform_dir(display_name, display_name, candidates))

    # 5. State file
    report.results.append(_check_state_file(source_dir))

    # 6. Platform tools
    report.results.extend(_check_platform_tools())

    # 7. Checksums (spot-check)
    checksum_result = _check_checksums(source_dir, config_path)
    if checksum_result is not None:
        report.results.append(checksum_result)

    return report


def format_doctor_report(report: DoctorReport) -> str:
    """Format a doctor report as a human-readable string.

    Args:
        report: The report to format.

    Returns:
        Multi-line string with check results and a summary.
    """
    lines: list[str] = []
    lines.append("Checking agentfiles environment...")
    lines.append("")

    label_width = max(len(r.label) for r in report.results) + 2

    for result in report.results:
        padded = result.label.ljust(label_width)
        lines.append(f"  {result.status.icon} {padded}{result.detail}")

    # Summary line
    lines.append("")
    parts: list[str] = []
    if report.error_count > 0:
        parts.append(f"{report.error_count} error{'s' if report.error_count != 1 else ''}")
    if report.warning_count > 0:
        parts.append(f"{report.warning_count} warning{'s' if report.warning_count != 1 else ''}")
    if not parts:
        lines.append("All checks passed.")
    else:
        summary = ", ".join(parts) + "."
        lines.append(summary)

    if report.error_count > 0 or report.warning_count > 0:
        lines.append("Run 'agentfiles diff' for a detailed drift check.")

    return "\n".join(lines)
