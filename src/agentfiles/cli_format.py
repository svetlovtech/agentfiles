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
    """Format items as a JSON object and print to stdout.

    Token estimates are computed only for agents and skills.  The output
    is an object with ``items`` (array) and optionally ``token_summary``
    (aggregate totals for agents and skills).

    Args:
        items: Items to display.
        show_tokens: If ``True``, include a ``token_estimate`` block per
            agent/skill item and an aggregate ``token_summary``.

    Returns:
        Exit code (always ``0``).
    """
    from agentfiles.models import ItemType
    from agentfiles.tokens import estimate_name_description_tokens, token_estimate

    data: list[dict[str, Any]] = []
    token_items: list[dict[str, Any]] = []
    for item in sorted(items, key=lambda i: i.sort_key):
        entry: dict[str, Any] = {
            "name": item.name,
            "type": item.item_type.value,
            "version": item.version,
            "files": len(item.files),
        }
        if show_tokens and item.item_type in (ItemType.AGENT, ItemType.SKILL):
            est = token_estimate(item)
            nd_tokens = estimate_name_description_tokens(item)
            entry["token_estimate"] = {
                "content_tokens": est.content_tokens,
                "overhead_tokens": est.overhead_tokens,
                "total_tokens": est.total_tokens,
                "source_size_bytes": est.source_size_bytes,
                "name_desc_tokens": nd_tokens,
            }
            token_items.append(entry["token_estimate"])
        data.append(entry)

    output: dict[str, Any] = {"items": data}
    if show_tokens and token_items:
        output["token_summary"] = {
            "items": len(token_items),
            "content_tokens": sum(t["content_tokens"] for t in token_items),
            "overhead_tokens": sum(t["overhead_tokens"] for t in token_items),
            "total_tokens": sum(t["total_tokens"] for t in token_items),
            "name_desc_tokens": sum(t["name_desc_tokens"] for t in token_items),
        }

    print(json.dumps(output, indent=2))
    return 0


def _format_status_json(
    target_manager: Any,
    summary: dict[str, int],
) -> int:
    """Format status output as JSON and print to stdout.

    Args:
        target_manager: Provides access to the discovered target platform.
        summary: Item counts from ``platform_summary()``.

    Returns:
        Exit code (always ``0``).
    """
    if target_manager.targets is None:
        print(
            json.dumps(
                {"agents": 0, "skills": 0, "commands": 0, "plugins": 0, "total_items": 0}, indent=2
            )
        )
        return 0

    agents = summary.get("agents", 0)
    skills = summary.get("skills", 0)
    commands = summary.get("commands", 0)
    plugins = summary.get("plugins", 0)
    total_items = agents + skills + commands + plugins

    output = {
        "agents": agents,
        "skills": skills,
        "commands": commands,
        "plugins": plugins,
        "total_items": total_items,
    }
    print(json.dumps(output, indent=2))
    return 0


def _format_plan_json(
    plans: list[SyncPlan],
    _target_manager: Any,
    *,
    dry_run: bool,
) -> int:
    """Format sync plans as JSON and print to stdout.

    Args:
        plans: Planned sync operations from the engine.
        _target_manager: Unused.  Kept for call-site compatibility.
        dry_run: Whether this is a dry-run preview.

    Returns:
        Exit code (always ``0``).
    """
    from agentfiles.models import SyncAction

    plan_list: list[dict[str, Any]] = []
    for plan in plans:
        if plan.action == SyncAction.SKIP:
            continue
        plan_list.append(
            {
                "item": plan.item.item_key,
                "action": plan.action.value.upper(),
                "reason": plan.reason,
            }
        )

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
    result_entries = []
    for r in results:
        entry: dict[str, Any] = {
            "item": r.plan.item.item_key,
            "action": r.plan.action.value,
            "status": "success" if r.is_success else "failed",
            "message": r.message,
            "files_copied": r.files_copied,
        }
        if r.push_status:
            entry["push_status"] = r.push_status
        if r.push_detail:
            entry["push_detail"] = r.push_detail
        result_entries.append(entry)
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
