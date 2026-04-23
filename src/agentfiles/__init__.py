from __future__ import annotations

"""agentfiles — Sync AI tool configurations for OpenCode.

Architecture Overview
=====================
agentfiles keeps AI tool configurations (agents, skills, commands, plugins)
consistent for the OpenCode platform by treating a source repository as the
single source of truth and propagating changes through a three-stage pipeline::

    ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
    │  Source Resolution │─▶│     Scanner      │─▶│     Differ      │
    │   (source.py)     │   │  (scanner.py)    │   │  (differ.py)    │
    └─────────────────┘    └─────────────────┘    └─────────────────┘
                                                          │
                                                          ▼
                                                   ┌─────────────────┐
    ┌─────────────────┐    ┌─────────────────┐    │     Engine      │
    │   SyncReport    │◀── │  SyncResult[]   │◀── │  (engine.py)    │
    │  (engine.py)    │    │  (engine.py)    │    │  plan → execute │
    └─────────────────┘    └─────────────────┘    └─────────────────┘

Data flow::

    source.py          Resolves user input → local directory path
         │
         ▼
    scanner.py         Walks source dirs → list[Item]
         │
         ▼
    differ.py          Compares source vs installed → list[DiffEntry]
         │
         ▼
    engine.py          Plans actions (INSTALL/UPDATE/UNINSTALL/SKIP)
         │                  → executes filesystem operations
         │                  → collects list[SyncResult]
         ▼
    engine.py          Aggregates results → SyncReport

Key Modules
-----------
models    Data models, enums, exceptions (Item, DiffEntry, SyncPlan, ItemType)
source    Source detection and resolution (local dir, git URL, git repo)
scanner   Convention-based directory scanner with registry pattern for item types
differ    Three-stage comparison: existence → metadata → SHA-256 checksum
engine    Plan-execute-report pipeline with dry-run support
target    Target platform discovery and installed-item management
config    YAML configuration and sync-state persistence
paths     Centralised filesystem path construction helpers
cli       Argparse CLI with subcommands (pull, push, sync, diff, status, …)
interactive  Stdlib-only terminal prompts (menus, confirmations, diff review)
output    Console formatting, ANSI colours, logging setup, diff display
git       Lightweight git branch operations (subprocess-based)
tokens    LLM token estimation (~4 chars/token heuristic)

Extending the System
--------------------
Add a new item type:
    1. Add enum value to ``ItemType`` in models.py (set ``plural`` mapping).
    2. Write a scanner function ``(dir_path, *, gitignore) -> list[Item]``.
    3. Register it via ``_register_scanner()`` in scanner.py.
    4. Add handling in engine.py if the type needs special install logic.

No other modules need modification (Open/Closed Principle).
"""

import importlib

try:
    from importlib.metadata import PackageNotFoundError, version

    try:
        __version__ = version("agentfiles")
    except PackageNotFoundError:
        __version__ = "0.0.0-dev"
except ImportError:
    __version__ = "0.0.0-dev"

# ---------------------------------------------------------------------------
# Lazy submodule exports
# ---------------------------------------------------------------------------
# Replaced eager ``from agentfiles.xxx import ...`` with ``__getattr__``-based
# lazy loading so that ``import agentfiles`` (or ``from agentfiles import __version__``)
# no longer cascades through every submodule.  Each name is resolved on first
# access and then cached in ``globals()`` for O(1) subsequent lookups.
#
# This cuts package import time from ~150 ms to < 1 ms, which directly
# improves CLI startup latency for ``--version``, ``--help``, and every
# subcommand.
# ---------------------------------------------------------------------------

# name → (module_path, attribute_name) for O(1) lazy resolution.
_EXPORT_MAP: dict[str, tuple[str, str]] = {
    "AgentfilesConfig": ("agentfiles.config", "AgentfilesConfig"),
    "Differ": ("agentfiles.differ", "Differ"),
    "SyncEngine": ("agentfiles.engine", "SyncEngine"),
    "SyncReport": ("agentfiles.engine", "SyncReport"),
    "InteractiveSession": ("agentfiles.interactive", "InteractiveSession"),
    "DiffEntry": ("agentfiles.models", "DiffEntry"),
    "DiffStatus": ("agentfiles.models", "DiffStatus"),
    "Item": ("agentfiles.models", "Item"),
    "ItemMeta": ("agentfiles.models", "ItemMeta"),
    "ItemState": ("agentfiles.models", "ItemState"),
    "ItemType": ("agentfiles.models", "ItemType"),
    "TARGET_PLATFORM": ("agentfiles.models", "TARGET_PLATFORM"),
    "TARGET_PLATFORM_DISPLAY": ("agentfiles.models", "TARGET_PLATFORM_DISPLAY"),
    "SourceError": ("agentfiles.models", "SourceError"),
    "SourceInfo": ("agentfiles.models", "SourceInfo"),
    "SourceType": ("agentfiles.models", "SourceType"),
    "SyncAction": ("agentfiles.models", "SyncAction"),
    "AgentfilesError": ("agentfiles.models", "AgentfilesError"),
    "ConfigError": ("agentfiles.models", "ConfigError"),
    "SyncPlan": ("agentfiles.models", "SyncPlan"),
    "SyncResult": ("agentfiles.models", "SyncResult"),
    "SyncState": ("agentfiles.models", "SyncState"),
    "TargetError": ("agentfiles.models", "TargetError"),
    "TargetPaths": ("agentfiles.models", "TargetPaths"),
    "TokenEstimate": ("agentfiles.models", "TokenEstimate"),
    "resolve_platform": ("agentfiles.models", "resolve_platform"),
    "token_estimate": ("agentfiles.tokens", "token_estimate"),
    "SourceScanner": ("agentfiles.scanner", "SourceScanner"),
    "SourceResolver": ("agentfiles.source", "SourceResolver"),
    "TargetDiscovery": ("agentfiles.target", "TargetDiscovery"),
    "TargetManager": ("agentfiles.target", "TargetManager"),
    "build_target_manager": ("agentfiles.target", "build_target_manager"),
}


def __getattr__(name: str) -> object:
    """Lazy-load submodule exports on first access."""
    spec = _EXPORT_MAP.get(name)
    if spec is not None:
        module_path, attr_name = spec
        module = importlib.import_module(module_path)
        value = getattr(module, attr_name)
        # Cache in module globals so future access bypasses __getattr__.
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    """Include lazy exports in ``dir()`` output for IDE completion."""
    return list(globals()) + list(_EXPORT_MAP)


__all__ = [
    "__version__",
    # Exceptions
    "ConfigError",
    "SourceError",
    "AgentfilesError",
    "TargetError",
    # Enums
    "DiffStatus",
    "ItemType",
    "TARGET_PLATFORM",
    "TARGET_PLATFORM_DISPLAY",
    "SourceType",
    "SyncAction",
    # Data models
    "DiffEntry",
    "Item",
    "ItemMeta",
    "ItemState",
    "SourceInfo",
    "SyncPlan",
    "SyncResult",
    "SyncState",
    "TargetPaths",
    "TokenEstimate",
    # Core classes
    "Differ",
    "InteractiveSession",
    "SourceResolver",
    "SourceScanner",
    "SyncEngine",
    "SyncReport",
    "AgentfilesConfig",
    "TargetDiscovery",
    "TargetManager",
    # Factories & helpers
    "build_target_manager",
    "resolve_platform",
    "token_estimate",
]
