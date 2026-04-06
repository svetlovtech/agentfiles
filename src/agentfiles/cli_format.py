"""JSON formatting helpers for CLI output.

Extracted from :mod:`agentfiles.cli` to reduce file size.  Contains:
- ``_format_list_json`` — JSON output for ``list`` command
- ``_format_status_json`` — JSON output for ``status`` command
- ``_format_plan_json`` — JSON output for ``pull``/``push`` dry-run plans
- ``_format_results_json`` — JSON output for ``pull``/``push`` execution results
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover
    from agentfiles.models import (
        Item,
        SyncPlan,
        SyncResult,
    )


def _format_list_json(items: list[Item], show_tokens: bool) -> int:
    """Format items as a JSON array and print to stdout.

    Args:
        items: Items to display.
        show_tokens: If ``True``, include a ``token_estimate`` block per item.

    Returns:
        Exit code (always ``0``).
    """
    from agentfiles.tokens import token_estimate

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
    from agentfiles.models import SyncAction

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
