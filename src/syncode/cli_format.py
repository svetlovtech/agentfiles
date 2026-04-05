"""JSON formatting helpers for CLI output.

Extracted from :mod:`syncode.cli` to reduce file size.  Contains:
- ``_format_list_json`` — JSON output for ``list`` command
- ``_format_status_json`` — JSON output for ``status`` command
- ``_format_plan_json`` — JSON output for ``pull``/``push`` dry-run plans
- ``_format_results_json`` — JSON output for ``pull``/``push`` execution results
- ``_format_show_json`` — JSON output for ``show`` command
- ``_build_verify_items`` — Build verification records from diff results
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

from syncode.models import DiffStatus

if TYPE_CHECKING:  # pragma: no cover
    from syncode.models import (
        DiffEntry,
        DiffStatus,
        Item,
        Platform,
        SyncPlan,
        SyncResult,
    )

# Short hash length for verify output (matches typical git abbreviation).
_SHORT_HASH_LEN = 8


def _format_list_json(items: list[Item], show_tokens: bool) -> int:
    """Format items as a JSON array and print to stdout.

    Args:
        items: Items to display.
        show_tokens: If ``True``, include a ``token_estimate`` block per item.

    Returns:
        Exit code (always ``0``).
    """
    from syncode.tokens import token_estimate

    data: list[dict[str, Any]] = []
    for item in sorted(items, key=lambda i: i.sort_key):
        entry: dict[str, Any] = {
            "name": item.name,
            "type": item.item_type.value,
            "version": item.version,
            "files": len(item.files),
            "platforms": item.platform_values,
        }
        if show_tokens:
            est = token_estimate(item)
            entry["token_estimate"] = {
                "content_tokens": est.content_tokens,
                "overhead_tokens": est.overhead_tokens,
                "total_tokens": est.total_tokens,
                "source_size_bytes": est.source_size_bytes,
            }
        data.append(entry)
    print(json.dumps(data, indent=2))
    return 0


def _format_status_json(
    target_manager: Any,
    summary: dict[Any, dict[str, int]],
) -> int:
    """Format status output as JSON and print to stdout.

    Args:
        target_manager: Provides access to discovered platform paths.
        summary: Per-platform item counts from ``platform_summary()``.

    Returns:
        Exit code (always ``0``).
    """
    platforms_data: dict[str, Any] = {}
    total_items = 0
    for platform in target_manager.targets:
        counts = summary.get(platform, {})
        agents = counts.get("agents", 0)
        skills = counts.get("skills", 0)
        commands = counts.get("commands", 0)
        plugins = counts.get("plugins", 0)
        platform_total = agents + skills + commands + plugins
        platforms_data[platform.value] = {
            "agents": agents,
            "skills": skills,
            "commands": commands,
            "plugins": plugins,
            "total": platform_total,
        }
        total_items += platform_total
    output = {
        "platforms": platforms_data,
        "total_items": total_items,
    }
    print(json.dumps(output, indent=2))
    return 0


def _format_show_json(item: Item, content: str, file_path: Path) -> int:
    """Format item content as JSON and print to stdout.

    Args:
        item: The :class:`Item` whose content is displayed.
        content: Text content of the item's primary file.
        file_path: Path to the content file on disk.

    Returns:
        Exit code (always ``0``).
    """
    output = {
        "name": item.name,
        "type": item.item_type.value,
        "content": content,
        "source_path": str(file_path),
        "platforms": item.platform_values,
    }
    print(json.dumps(output, indent=2))
    return 0


def _format_plan_json(
    plans: list[SyncPlan],
    target_manager: Any,
    *,
    dry_run: bool,
) -> int:
    """Format sync plans as JSON and print to stdout.

    Groups plans by ``(item_key, action)`` to collect platform names.

    Args:
        plans: Planned sync operations from the engine.
        target_manager: Used to resolve platforms from target directories.
        dry_run: Whether this is a dry-run preview.

    Returns:
        Exit code (always ``0``).
    """
    from syncode.models import SyncAction

    # Group by (item_key, action) to merge per-platform entries.
    grouped: dict[tuple[str, str], dict[str, Any]] = {}
    for plan in plans:
        if plan.action == SyncAction.SKIP:
            continue
        item_key = plan.item.item_key
        action_label = plan.action.value.upper()
        group_key = (item_key, action_label)

        platform = target_manager.resolve_platform_for(
            plan.item.item_type,
            plan.target_dir,
        )
        platform_name = platform.value if platform else "unknown"

        if group_key not in grouped:
            grouped[group_key] = {
                "item": item_key,
                "action": action_label,
                "platforms": [platform_name],
                "reason": plan.reason,
            }
        else:
            grouped[group_key]["platforms"].append(platform_name)

    plan_list = list(grouped.values())
    output = {
        "plans": plan_list,
        "total": len(plan_list),
        "dry_run": dry_run,
    }
    print(json.dumps(output, indent=2))
    return 0


def _format_results_json(
    results: list[SyncResult],
    report: Any,
    *,
    dry_run: bool,
) -> int:
    """Format sync execution results as JSON and print to stdout.

    Args:
        results: Per-plan execution results from the engine.
        report: Aggregated report with installed/updated/skipped/failed counts.
        dry_run: Whether this was a dry-run operation.

    Returns:
        ``0`` when all operations succeeded, ``1`` otherwise.
    """
    result_entries = [
        {
            "item": r.plan.item.item_key,
            "action": r.plan.action.value,
            "status": "success" if r.is_success else "failed",
            "message": r.message,
            "files_copied": r.files_copied,
        }
        for r in results
    ]
    output = {
        "results": result_entries,
        "summary": {
            "installed": len(report.installed),
            "updated": len(report.updated),
            "skipped": len(report.skipped),
            "failed": len(report.failed),
        },
        "dry_run": dry_run,
    }
    print(json.dumps(output, indent=2))
    return 0 if report.is_success else 1


def _build_verify_items(
    diff_results: dict[Platform, list[DiffEntry]],
) -> list[dict[str, Any]]:
    """Convert diff results into flat verify-item records.

    Each record has ``key``, ``status``, and ``platforms`` fields.
    Drift records also include ``source_hash`` and ``target_hash``
    (abbreviated to :data:`_SHORT_HASH_LEN` characters).

    Args:
        diff_results: Mapping of Platform to list of DiffEntry.

    Returns:
        Sorted list of verification record dicts.
    """
    verify_items: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()

    for platform, entries in diff_results.items():
        for entry in entries:
            item_key = entry.item.item_key
            platform_key = platform.value
            if (item_key, platform_key) in seen:
                continue
            seen.add((item_key, platform_key))

            if entry.status == DiffStatus.UNCHANGED:
                status = "matching"
            elif entry.status == DiffStatus.NEW:
                status = "missing"
            else:
                status = "drift"

            record: dict[str, Any] = {
                "key": item_key,
                "status": status,
                "platforms": [platform_key],
            }
            if status == "drift" and entry.source_checksum:
                record["source_hash"] = entry.source_checksum[:_SHORT_HASH_LEN]
                if entry.target_checksum:
                    record["target_hash"] = entry.target_checksum[:_SHORT_HASH_LEN]
            verify_items.append(record)

    verify_items.sort(key=lambda r: r["key"])
    return verify_items


def _print_verify_text(
    verify_items: list[dict[str, Any]],
    matching_count: int,
    drift_count: int,
    missing_count: int,
) -> None:
    """Print human-readable verify output with colour-coded status lines."""
    from syncode.cli import _use_colors_output
    from syncode.output import Colors, colorize

    use_col = _use_colors_output()

    print("\nagentfiles verify\n")
    for record in verify_items:
        key = record["key"]
        status = record["status"]
        platform_names = record["platforms"]

        if status == "matching":
            symbol = colorize("\u2705", Colors.GREEN) if use_col else "\u2705"
            detail = "checksums match"
        elif status == "drift":
            symbol = colorize("~", Colors.YELLOW) if use_col else "~"
            src = record.get("source_hash", "???")
            tgt = record.get("target_hash", "???")
            detail = f"DRIFT DETECTED (source: {src}, installed: {tgt})"
        else:
            symbol = colorize("\u274c", Colors.RED) if use_col else "\u274c"
            detail = "NOT INSTALLED"

        print(f"{symbol} {key:<30s} {platform_names} — {detail}")

    print()
    print(f"{matching_count} items verified, {drift_count} drift, {missing_count} missing.")
    exit_code = 1 if (drift_count > 0 or missing_count > 0) else 0
    print(f"Exit code: {exit_code}")
