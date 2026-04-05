from __future__ import annotations

"""syncode — Sync AI tool configurations across platforms.

Architecture Overview
=====================
syncode keeps AI tool configurations (agents, skills, commands, plugins)
consistent across multiple target platforms (OpenCode, Claude Code,
Windsurf, Cursor) by treating a source repository as the single source
of truth and propagating changes through a three-stage pipeline::

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
    differ.py          Compares source vs installed → dict[Platform, list[DiffEntry]]
         │
         ▼
    engine.py          Plans actions (INSTALL/UPDATE/UNINSTALL/SKIP)
         │                  → executes filesystem operations
         │                  → collects list[SyncResult]
         ▼
    engine.py          Aggregates results → SyncReport

Key Modules
-----------
models    Data models, enums, exceptions (Item, DiffEntry, SyncPlan, Platform, ItemType)
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
Add a new platform:
    1. Add enum value to ``Platform`` in models.py.
    2. Add discovery logic in target.py (``_DISCOVERY_TABLE``).
    3. Add alias in ``PLATFORM_ALIASES`` (models.py).

Add a new item type:
    1. Add enum value to ``ItemType`` in models.py (set ``plural`` mapping).
    2. Write a scanner function ``(dir_path, *, gitignore) -> list[Item]``.
    3. Register it via ``_register_scanner()`` in scanner.py.
    4. Add handling in engine.py if the type needs special install logic.

No other modules need modification (Open/Closed Principle).
"""

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
# Replaced eager ``from syncode.xxx import ...`` with ``__getattr__``-based
# lazy loading so that ``import syncode`` (or ``from syncode import __version__``)
# no longer cascades through every submodule.  Each name is resolved on first
# access and then cached in ``globals()`` for O(1) subsequent lookups.
#
# This cuts package import time from ~150 ms to < 1 ms, which directly
# improves CLI startup latency for ``--version``, ``--help``, and every
# subcommand.
# ---------------------------------------------------------------------------

# name → (module_path, attribute_name) for O(1) lazy resolution.
_EXPORT_MAP: dict[str, tuple[str, str]] = {
    "SyncodeConfig": ("syncode.config", "SyncodeConfig"),
    "Differ": ("syncode.differ", "Differ"),
    "SyncEngine": ("syncode.engine", "SyncEngine"),
    "SyncReport": ("syncode.engine", "SyncReport"),
    "InteractiveSession": ("syncode.interactive", "InteractiveSession"),
    "DiffEntry": ("syncode.models", "DiffEntry"),
    "DiffStatus": ("syncode.models", "DiffStatus"),
    "Item": ("syncode.models", "Item"),
    "ItemMeta": ("syncode.models", "ItemMeta"),
    "ItemState": ("syncode.models", "ItemState"),
    "ItemType": ("syncode.models", "ItemType"),
    "Platform": ("syncode.models", "Platform"),
    "PlatformState": ("syncode.models", "PlatformState"),
    "SourceError": ("syncode.models", "SourceError"),
    "SourceInfo": ("syncode.models", "SourceInfo"),
    "SourceType": ("syncode.models", "SourceType"),
    "SyncAction": ("syncode.models", "SyncAction"),
    "SyncodeError": ("syncode.models", "SyncodeError"),
    "ConfigError": ("syncode.models", "ConfigError"),
    "SyncPlan": ("syncode.models", "SyncPlan"),
    "SyncResult": ("syncode.models", "SyncResult"),
    "SyncState": ("syncode.models", "SyncState"),
    "TargetError": ("syncode.models", "TargetError"),
    "TargetPaths": ("syncode.models", "TargetPaths"),
    "TokenEstimate": ("syncode.models", "TokenEstimate"),
    "resolve_platform": ("syncode.models", "resolve_platform"),
    "token_estimate": ("syncode.tokens", "token_estimate"),
    "SourceScanner": ("syncode.scanner", "SourceScanner"),
    "SourceResolver": ("syncode.source", "SourceResolver"),
    "TargetDiscovery": ("syncode.target", "TargetDiscovery"),
    "TargetManager": ("syncode.target", "TargetManager"),
    "build_target_manager": ("syncode.target", "build_target_manager"),
}


def __getattr__(name: str) -> object:
    """Lazy-load submodule exports on first access."""
    spec = _EXPORT_MAP.get(name)
    if spec is not None:
        module_path, attr_name = spec
        import importlib

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
    "SyncodeError",
    "TargetError",
    # Enums
    "DiffStatus",
    "ItemType",
    "Platform",
    "SourceType",
    "SyncAction",
    # Data models
    "DiffEntry",
    "Item",
    "ItemMeta",
    "ItemState",
    "PlatformState",
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
    "SyncodeConfig",
    "TargetDiscovery",
    "TargetManager",
    # Factories & helpers
    "build_target_manager",
    "resolve_platform",
    "token_estimate",
]
