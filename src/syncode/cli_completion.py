"""Shell completion script generation for the ``agentfiles`` CLI.

Extracted from :mod:`syncode.cli` to reduce file size and Contains:
- ``_SUBCOMMAND_INFO`` — single source of truth for subcommand names and descriptions
- ``_SUBCOMMANDS`` — derived list of subcommand names
- ``_PLATFORM_CHOICES``, ``_TYPE_CHOICES`` — completion option lists
- ``_print_bash_completion``, ``_print_zsh_completion``, ``_print_fish_completion``
- ``cmd_completion`` — CLI command handler

All completion scripts derive their subcommand lists from ``_SUBCOMMAND_INFO``
so so avoid duplication.
"""

from __future__ import annotations

import argparse
import sys

# ---------------------------------------------------------------------------
# Subcommand registry (single source of truth)
# ---------------------------------------------------------------------------

_SUBCOMMAND_INFO: list[tuple[str, str]] = [
    ("pull", "Pull items from repository to local configs"),
    ("push", "Push items from local configs back to the source"),
    ("sync", "Bidirectional sync"),
    ("list", "List items in source repository"),
    ("diff", "Show differences between source and targets"),
    ("status", "Show installed items per platform"),
    ("show", "Show item content"),
    ("init", "Initialize a new agentfiles repository"),
    ("uninstall", "Remove items from target platforms"),
    ("update", "Git pull + sync in one step"),
    ("clean", "Remove orphaned items from targets"),
    ("verify", "CI-friendly drift detection"),
    ("doctor", "Diagnose common issues"),
    ("branch", "List or switch git branches"),
    ("adopt", "Adopt items from target platforms into source"),
    ("completion", "Generate shell completion scripts"),
]

_SUBCOMMANDS: list[str] = [cmd for cmd, _ in _SUBCOMMAND_INFO]

# Shell names used as ``--target`` choices.
_PLATFORM_CHOICES: list[str] = sorted(
    ["opencode", "claude_code", "windsurf", "cursor", "all"],
)

# Item type names used as ``--type`` choices.
_TYPE_CHOICES: list[str] = ["agent", "skill", "command", "plugin", "all"]


# ---------------------------------------------------------------------------
# Completion script generators
# ---------------------------------------------------------------------------


def _print_bash_completion() -> None:
    """Print a bash completion script for ``agentfiles``."""
    script = (
        "#!/usr/bin/env bash\n"
        "# agentfiles bash completion\n"
        "\n"
        "_agentfiles() {\n"
        "  local cur prev commands subcommands\n"
        '  cur="${COMP_WORDS[COMP_CWORD]}"\n'
        '  prev="${COMP_WORDS[COMP_CWORD-1]}"\n'
        f'  commands="{" ".join(_SUBCOMMANDS)}"\n'
        "\n"
        "  # Complete subcommands\n"
        '  if [[ "$COMP_CWORD" -eq 1 ]]; then\n'
        '    COMPREPLY=($(compgen -W "$commands" -- "$cur"))\n'
        "    return 0\n"
        "  fi\n"
        "\n"
        "  # Global flags (any position)\n"
        '  case "$prev" in\n'
        "    --color)\n"
        '      COMPREPLY=($(compgen -W "always auto never" -- "$cur"))\n'
        "      return 0\n"
        "      ;;\n"
        "  esac\n"
        "\n"
        "  # Subcommand-specific flag completions\n"
        '  local subcmd="${COMP_WORDS[1]}"\n'
        '  case "$prev" in\n'
        "    --target)\n"
        f'      COMPREPLY=($(compgen -W "{" ".join(_PLATFORM_CHOICES)}" -- "$cur"))\n'
        "      return 0\n"
        "      ;;\n"
        "    --type)\n"
        f'      COMPREPLY=($(compgen -W "{" ".join(_TYPE_CHOICES)}" -- "$cur"))\n'
        "      return 0\n"
        "      ;;\n"
        "    --format)\n"
        '      COMPREPLY=($(compgen -W "text json" -- "$cur"))\n'
        "      return 0\n"
        "      ;;\n"
        "    --switch)\n"
        "      # Could list branches, but keep it simple\n"
        "      return 0\n"
        "      ;;\n"
        "  esac\n"
        "\n"
        "  # Offer flags relevant to the current subcommand\n"
        '  case "$subcmd" in\n'
        "    pull|push|sync|update)\n"
        "      COMPREPLY=($(compgen -W "
        '"--target --type --only --except --dry-run --yes '
        "--config --cache-dir --symlinks --format "
        '--color --verbose --quiet" -- "$cur"))\n'
        "      ;;\n"
        "    list|diff|verify)\n"
        "      COMPREPLY=($(compgen -W "
        '"--target --type --only --except --config '
        '--cache-dir --format --color --verbose --quiet" -- "$cur"))\n'
        "      ;;\n"
        "    uninstall)\n"
        "      COMPREPLY=($(compgen -W "
        '"--target --type --only --except --dry-run '
        "--yes --force --config --color --verbose "
        '--quiet" -- "$cur"))\n'
        "      ;;\n"
        "    clean)\n"
        "      COMPREPLY=($(compgen -W "
        '"--target --type --only --except --dry-run '
        "--yes --config --cache-dir --color "
        '--verbose --quiet" -- "$cur"))\n'
        "      ;;\n"
        "    status|doctor)\n"
        "      COMPREPLY=($(compgen -W "
        '"--config --format --color --verbose '
        '--quiet" -- "$cur"))\n'
        "      ;;\n"
        "    branch)\n"
        "      COMPREPLY=($(compgen -W "
        '"--switch --yes --config --cache-dir '
        '--color --verbose --quiet" -- "$cur"))\n'
        "      ;;\n"
        "    init)\n"
        "      COMPREPLY=($(compgen -W "
        '"--yes --color --verbose --quiet" -- '
        '"$cur"))\n'
        "      ;;\n"
        "    show)\n"
        "      COMPREPLY=($(compgen -W "
        '"--source --format --color --verbose '
        '--quiet" -- "$cur"))\n'
        "      ;;\n"
        "    completion)\n"
        "      COMPREPLY=($(compgen -W "
        '"bash zsh fish" -- "$cur"))\n'
        "      ;;\n"
        "  esac\n"
        "}\n"
        "\n"
        "complete -F _agentfiles agentfiles\n"
    )
    sys.stdout.write(script)


def _print_zsh_completion() -> None:
    """Print a zsh completion script for ``agentfiles``."""
    subcommand_descriptions = dict(_SUBCOMMAND_INFO)

    subcmd_lines = "\n".join(
        f"        '{cmd}:{' ' + desc if desc else ''}'"
        for cmd, desc in subcommand_descriptions.items()
    )

    platforms_str = " ".join(_PLATFORM_CHOICES)
    types_str = " ".join(_TYPE_CHOICES)

    script = (
        "#compdef agentfiles\n"
        "# agentfiles zsh completion\n"
        "\n"
        "_agentfiles() {\n"
        "  local -a commands\n"
        "  commands=(\n"
        f"{subcmd_lines}\n"
        "  )\n"
        "\n"
        "  _arguments -C \\\n"
        "    '(--version)-1[Show version]' \\\n"
        "    '(--color)-c[When to use colors]:color:(always auto never)' \\\n"
        "    '(--verbose -v)-v[Verbose output]' \\\n"
        "    '(--quiet -q)-q[Quiet mode]' \\\n"
        "    '1:command:->command' \\\n"
        "    '*::arg:->args'\n"
        "\n"
        "  case $state in\n"
        "    command)\n"
        "      _describe 'command' commands\n"
        "      ;;\n"
        "    args)\n"
        "      case $words[1] in\n"
        "        pull|push|adopt|sync|update)\n"
        f"          _arguments '--target[Target platform]:target:({platforms_str})' \\\n"
        f"            '--type[Filter by item type]:type:({types_str})' \\\n"
        "            '--only[Only sync these items]:items' \\\n"
        "            '--except[Exclude these items]:items' \\\n"
        "            '--dry-run[Preview changes]' \\\n"
        "            '--yes[Non-interactive mode]' \\\n"
        "            '--config[Path to config file]:file:_files' \\\n"
        "            '--cache-dir[Cache directory]:dir:_directories' \\\n"
        "            '--symlinks[Use symlinks]' \\\n"
        "            '--format[Output format]:format:(text json)'\n"
        "          ;;\n"
        "        list|diff|verify)\n"
        f"          _arguments '--target[Target platform]:target:({platforms_str})' \\\n"
        f"            '--type[Filter by item type]:type:({types_str})' \\\n"
        "            '--only[Only sync these items]:items' \\\n"
        "            '--except[Exclude these items]:items' \\\n"
        "            '--config[Path to config file]:file:_files' \\\n"
        "            '--cache-dir[Cache directory]:dir:_directories' \\\n"
        "            '--format[Output format]:format:(text json)'\n"
        "          ;;\n"
        "        clean)\n"
        f"          _arguments '--target[Target platform]:target:({platforms_str})' \\\n"
        f"            '--type[Filter by item type]:type:({types_str})' \\\n"
        "            '--only[Only sync these items]:items' \\\n"
        "            '--except[Exclude these items]:items' \\\n"
        "            '--dry-run[Preview changes]' \\\n"
        "            '--yes[Non-interactive mode]' \\\n"
        "            '--config[Path to config file]:file:_files' \\\n"
        "            '--cache-dir[Cache directory]:dir:_directories'\n"
        "          ;;\n"
        "        uninstall)\n"
        f"          _arguments '--target[Target platform]:target:({platforms_str})' \\\n"
        f"            '--type[Filter by item type]:type:({types_str})' \\\n"
        "            '--only[Only sync these items]:items' \\\n"
        "            '--except[Exclude these items]:items' \\\n"
        "            '--dry-run[Preview changes]' \\\n"
        "            '--yes[Non-interactive mode]' \\\n"
        "            '--force[Skip confirmation]' \\\n"
        "            '--config[Path to config file]:file:_files'\n"
        "          ;;\n"
        "        status|doctor)\n"
        "          _arguments '--config[Path to config file]:file:_files' \\\n"
        "            '--format[Output format]:format:(text json)'\n"
        "          ;;\n"
        "        branch)\n"
        "          _arguments '--switch[Switch to branch]:branch' \\\n"
        "            '--yes[Non-interactive mode]' \\\n"
        "            '--config[Path to config file]:file:_files' \\\n"
        "            '--cache-dir[Cache directory]:dir:_directories'\n"
        "          ;;\n"
        "        init)\n"
        "          _arguments '--yes[Non-interactive mode]' \\\n"
        "            '1:path:_directories'\n"
        "          ;;\n"
        "        show)\n"
        "          _arguments '--source[Source repository path]:path:_directories' \\\n"
        "            '--format[Output format]:format:(text json)' \\\n"
        "            '1:item_name'\n"
        "          ;;\n"
        "        completion)\n"
        "          _arguments '1:shell:(bash zsh fish)'\n"
        "          ;;\n"
        "      esac\n"
        "      ;;\n"
        "  esac\n"
        "}\n"
        "\n"
        '_agentfiles "$@"\n'
    )
    sys.stdout.write(script)


def _print_fish_completion() -> None:
    """Print a fish completion script for ``agentfiles``."""
    platforms_str = " ".join(_PLATFORM_CHOICES)
    types_str = " ".join(_TYPE_CHOICES)

    def _fc(
        condition: str,
        *opts: str,
        short: str = "",
        long: str = "",
        desc: str = "",
        req: bool = False,
        args: str = "",
        command: str = "",
    ) -> str:
        """Build a single fish ``complete`` line."""
        parts = ["complete -c agentfiles"]
        if condition:
            parts.append(f"-n '{condition}'")
        if short:
            parts.append(f"-s {short}")
        if long:
            parts.append(f"-l {long}")
        if desc:
            parts.append(f"-d '{desc}'")
        if req:
            parts.append("-r")
        if args:
            parts.append(f"-a '{args}'")
        if command:
            parts.append(f"-a '{command}'")
        return " ".join(parts)

    use_sub = "__fish_use_subcommand"

    lines: list[str] = [
        "# agentfiles fish completion",
        "",
        "# Disable file completions by default",
        "complete -c agentfiles -f",
        "",
        "# Global flags",
        _fc(use_sub, long="version", desc="Show version"),
        _fc(
            use_sub,
            long="color",
            desc="When to use colors",
            req=True,
            args="always auto never",
        ),
        _fc(use_sub, short="v", long="verbose", desc="Verbose output"),
        _fc(use_sub, short="q", long="quiet", desc="Quiet mode"),
        "",
    ]

    # Subcommands — derived from _SUBCOMMAND_INFO
    for cmd, desc in _SUBCOMMAND_INFO:
        lines.append(_fc(use_sub, command=cmd, desc=desc))

    lines.append("")

    # Common flags for subcommands that use _add_common_args
    common_subcmds = " ".join(
        ["pull", "push", "adopt", "sync", "list", "diff", "verify", "clean", "uninstall", "branch"]
    )
    common_condition = f"__fish_seen_subcommand_from {common_subcmds}"

    lines.extend(
        [
            _fc(
                common_condition,
                long="target",
                desc="Target platform",
                req=True,
                args=platforms_str,
            ),
            _fc(
                common_condition,
                long="type",
                desc="Filter by item type",
                req=True,
                args=types_str,
            ),
            _fc(common_condition, long="only", desc="Only sync these items", req=True),
            _fc(common_condition, long="except", desc="Exclude these items", req=True),
            _fc(common_condition, long="config", desc="Path to config file", req=True),
            _fc(
                common_condition,
                long="cache-dir",
                desc="Cache directory for git clones",
                req=True,
            ),
            _fc(
                common_condition,
                short="n",
                long="dry-run",
                desc="Preview changes without applying",
            ),
            _fc(common_condition, short="y", long="yes", desc="Non-interactive mode"),
            "",
        ]
    )

    # pull/push/sync/update specific
    sync_subcmds = "__fish_seen_subcommand_from pull push sync update"
    lines.extend(
        [
            _fc(sync_subcmds, long="symlinks", desc="Use symlinks instead of copying"),
            _fc(
                sync_subcmds,
                long="format",
                desc="Output format",
                req=True,
                args="text json",
            ),
            "",
        ]
    )

    # list/diff/verify specific
    fmt_subcmds = "__fish_seen_subcommand_from list diff verify"
    lines.append(
        _fc(fmt_subcmds, long="format", desc="Output format", req=True, args="text json"),
    )
    lines.append(
        "complete -c agentfiles -n '__fish_seen_subcommand_from list' "
        "-l tokens -d 'Show estimated token counts'",
    )
    lines.append("")

    # uninstall specific
    lines.append(
        "complete -c agentfiles -n '__fish_seen_subcommand_from uninstall' "
        "-s f -l force -d 'Skip confirmation prompt'",
    )
    lines.append("")

    # branch specific
    lines.append(
        "complete -c agentfiles -n '__fish_seen_subcommand_from branch' "
        "-s s -l switch -d 'Switch to branch' -r",
    )
    lines.append("")

    # show specific
    lines.extend(
        [
            "complete -c agentfiles -n '__fish_seen_subcommand_from show' "
            "-l source -d 'Source repository path' -r",
            "complete -c agentfiles -n '__fish_seen_subcommand_from show' "
            "-l format -d 'Output format' -r -a 'text json'",
            "",
        ]
    )

    # status/doctor
    lines.extend(
        [
            "complete -c agentfiles -n '__fish_seen_subcommand_from status' "
            "-l config -d 'Path to config file' -r",
            "complete -c agentfiles -n '__fish_seen_subcommand_from status' "
            "-l format -d 'Output format' -r -a 'text json'",
            "complete -c agentfiles -n '__fish_seen_subcommand_from doctor' "
            "-l config -d 'Path to config file' -r",
            "",
        ]
    )

    # init specific
    lines.append(
        "complete -c agentfiles -n '__fish_seen_subcommand_from init' "
        "-s y -l yes -d 'Non-interactive mode'",
    )
    lines.append("")

    # completion specific
    lines.append(
        "complete -c agentfiles -n '__fish_seen_subcommand_from completion' "
        "-a 'bash zsh fish' -d 'Shell'",
    )

    script = "\n".join(lines) + "\n"
    sys.stdout.write(script)


def cmd_completion(args: argparse.Namespace) -> int:
    """Generate shell completion scripts for bash, zsh, and fish.

    Prints the completion script to *stdout* so the user can redirect it
    to the appropriate location or ``eval`` it directly.

    Args:
        args: Parsed CLI namespace (reads ``shell``).

    Returns:
        ``0`` on success.
    """
    shell = args.shell
    if shell == "bash":
        _print_bash_completion()
    elif shell == "zsh":
        _print_zsh_completion()
    elif shell == "fish":
        _print_fish_completion()
    return 0
