"""Shell completion scripts for agentfiles.

Provides static completion scripts for bash, zsh, and fish shells.
No external dependencies are required.
"""

from __future__ import annotations

BASH_COMPLETION = r"""# agentfiles bash completion
_agentfiles_completion() {
    local cur prev commands
    COMPREPLY=()
    cur="${COMP_WORDS[COMP_CWORD]}"
    prev="${COMP_WORDS[COMP_CWORD-1]}"
    commands="pull push status clean init doctor verify completion"

    # Complete subcommand names
    if [[ ${COMP_CWORD} -eq 1 ]]; then
        COMPREPLY=( $(compgen -W "${commands}" -- "${cur}") )
        return
    fi

    local subcmd="${COMP_WORDS[1]}"

    # Complete flag values
    case "${prev}" in
        --type)
            COMPREPLY=( $(compgen -W "agent skill command plugin config all" -- "${cur}") )
            return
            ;;
        --color)
            COMPREPLY=( $(compgen -W "always auto never" -- "${cur}") )
            return
            ;;
        --format)
            COMPREPLY=( $(compgen -W "json" -- "${cur}") )
            return
            ;;
    esac

    # Complete flags per subcommand
    case "${subcmd}" in
        pull)
            COMPREPLY=( $(compgen -W "--source --config --type --only --except --dry-run --yes --update --verbose --quiet --color" -- "${cur}") )
            ;;
        push)
            COMPREPLY=( $(compgen -W "--source --config --type --only --except --dry-run --yes --verbose --quiet --color" -- "${cur}") )
            ;;
        status)
            COMPREPLY=( $(compgen -W "--source --config --type --only --except --list --diff --tokens --format --verbose --quiet --color" -- "${cur}") )
            ;;
        clean)
            COMPREPLY=( $(compgen -W "--source --config --type --only --except --dry-run --yes --verbose --quiet --color" -- "${cur}") )
            ;;
        init)
            COMPREPLY=( $(compgen -W "--verbose --quiet --color" -- "${cur}") )
            ;;
        doctor)
            COMPREPLY=( $(compgen -W "--source --config --verbose --quiet --color" -- "${cur}") )
            ;;
        verify)
            COMPREPLY=( $(compgen -W "--source --config --type --only --except --verbose --quiet --color" -- "${cur}") )
            ;;
        completion)
            COMPREPLY=( $(compgen -W "bash zsh fish" -- "${cur}") )
            ;;
    esac
}
complete -F _agentfiles_completion agentfiles
"""

ZSH_COMPLETION = r"""#compdef agentfiles
# agentfiles zsh completion

_agentfiles() {
    local -a commands
    commands=(
        'pull:Install/update items from source repository'
        'push:Push local items back to source repository'
        'status:Show installed-item counts per platform'
        'clean:Remove orphaned items'
        'init:Scaffold a new agentfiles repository'
        'doctor:Run environment diagnostics'
        'verify:Verify installed items match source'
        'completion:Generate shell completion scripts'
    )

    local -a types=(agent skill command plugin config all)
    local -a shells=(bash zsh fish)

    _arguments -C \
        '--version[Show version]' \
        '--verbose[Verbose output]' \
        '-v[Verbose output]' \
        '--quiet[Quiet mode]' \
        '-q[Quiet mode]' \
        '--color[Color mode]:mode:(always auto never)' \
        '1:command:->cmd' \
        '*::arg:->args'

    case "$state" in
        cmd)
            _describe -t commands 'agentfiles command' commands
            ;;
        args)
            case "${words[1]}" in
                pull)
                    _arguments \
                        '1:source:_files -/' \
                        '--config[Config file]:file:_files' \
                        '--type[Item type]:type:('"${types[*]}"')' \
                        '--only[Include only these items]:name:' \
                        '--except[Exclude these items]:name:' \
                        '--dry-run[Preview changes]' \
                        '--yes[Non-interactive mode]' \
                        '--update[Git pull source first]' \
                        '--verbose[Verbose output]' \
                        '--quiet[Quiet mode]' \
                        '--color[Color mode]:mode:(always auto never)'
                    ;;
                push)
                    _arguments \
                        '1:source:_files -/' \
                        '--config[Config file]:file:_files' \
                        '--type[Item type]:type:('"${types[*]}"')' \
                        '--only[Include only these items]:name:' \
                        '--except[Exclude these items]:name:' \
                        '--dry-run[Preview changes]' \
                        '--yes[Non-interactive mode]' \
                        '--verbose[Verbose output]' \
                        '--quiet[Quiet mode]' \
                        '--color[Color mode]:mode:(always auto never)'
                    ;;
                status)
                    _arguments \
                        '1:source:_files -/' \
                        '--config[Config file]:file:_files' \
                        '--type[Item type]:type:('"${types[*]}"')' \
                        '--only[Include only these items]:name:' \
                        '--except[Exclude these items]:name:' \
                        '--list[List source items]' \
                        '--diff[Compare source vs installed]' \
                        '--tokens[Show token estimates]' \
                        '--format[Output format]:format:(json)' \
                        '--verbose[Verbose output]' \
                        '--quiet[Quiet mode]' \
                        '--color[Color mode]:mode:(always auto never)'
                    ;;
                clean)
                    _arguments \
                        '1:source:_files -/' \
                        '--config[Config file]:file:_files' \
                        '--type[Item type]:type:('"${types[*]}"')' \
                        '--only[Include only these items]:name:' \
                        '--except[Exclude these items]:name:' \
                        '--dry-run[Preview changes]' \
                        '--yes[Non-interactive mode]' \
                        '--verbose[Verbose output]' \
                        '--quiet[Quiet mode]' \
                        '--color[Color mode]:mode:(always auto never)'
                    ;;
                init)
                    _arguments \
                        '--verbose[Verbose output]' \
                        '--quiet[Quiet mode]' \
                        '--color[Color mode]:mode:(always auto never)'
                    ;;
                doctor)
                    _arguments \
                        '1:source:_files -/' \
                        '--config[Config file]:file:_files' \
                        '--verbose[Verbose output]' \
                        '--quiet[Quiet mode]' \
                        '--color[Color mode]:mode:(always auto never)'
                    ;;
                verify)
                    _arguments \
                        '1:source:_files -/' \
                        '--config[Config file]:file:_files' \
                        '--type[Item type]:type:('"${types[*]}"')' \
                        '--only[Include only these items]:name:' \
                        '--except[Exclude these items]:name:' \
                        '--verbose[Verbose output]' \
                        '--quiet[Quiet mode]' \
                        '--color[Color mode]:mode:(always auto never)'
                    ;;
                completion)
                    _arguments '1:shell:('"${shells[*]}"')'
                    ;;
            esac
            ;;
    esac
}

_agentfiles "$@"
"""

FISH_COMPLETION = r"""# agentfiles fish completion

# Disable file completions by default
complete -c agentfiles -f

# Subcommands
complete -c agentfiles -n '__fish_use_subcommand' -a pull -d 'Install/update items from source repository'
complete -c agentfiles -n '__fish_use_subcommand' -a push -d 'Push local items back to source repository'
complete -c agentfiles -n '__fish_use_subcommand' -a status -d 'Show installed-item counts per platform'
complete -c agentfiles -n '__fish_use_subcommand' -a clean -d 'Remove orphaned items'
complete -c agentfiles -n '__fish_use_subcommand' -a init -d 'Scaffold a new agentfiles repository'
complete -c agentfiles -n '__fish_use_subcommand' -a doctor -d 'Run environment diagnostics'
complete -c agentfiles -n '__fish_use_subcommand' -a verify -d 'Verify installed items match source'
complete -c agentfiles -n '__fish_use_subcommand' -a completion -d 'Generate shell completion scripts'

# Global flags
complete -c agentfiles -l version -d 'Show version'
complete -c agentfiles -l verbose -s v -d 'Verbose output'
complete -c agentfiles -l quiet -s q -d 'Quiet mode'
complete -c agentfiles -l color -xa 'always auto never' -d 'Color mode'

# Common flags for pull/push/status/clean
for cmd in pull push status clean verify
    complete -c agentfiles -n "__fish_seen_subcommand_from $cmd" -l source -d 'Source repository path'
    complete -c agentfiles -n "__fish_seen_subcommand_from $cmd" -l config -s c -d 'Config file path'
    complete -c agentfiles -n "__fish_seen_subcommand_from $cmd" -l type -xa 'agent skill command plugin config all' -d 'Item type'
    complete -c agentfiles -n "__fish_seen_subcommand_from $cmd" -l only -d 'Include only these items'
    complete -c agentfiles -n "__fish_seen_subcommand_from $cmd" -l except -d 'Exclude these items'
end

# pull-specific
complete -c agentfiles -n '__fish_seen_subcommand_from pull' -l dry-run -d 'Preview changes'
complete -c agentfiles -n '__fish_seen_subcommand_from pull' -l yes -s y -d 'Non-interactive mode'
complete -c agentfiles -n '__fish_seen_subcommand_from pull' -l update -d 'Git pull source first'

# push-specific
complete -c agentfiles -n '__fish_seen_subcommand_from push' -l dry-run -d 'Preview changes'
complete -c agentfiles -n '__fish_seen_subcommand_from push' -l yes -s y -d 'Non-interactive mode'

# status-specific
complete -c agentfiles -n '__fish_seen_subcommand_from status' -l list -d 'List source items'
complete -c agentfiles -n '__fish_seen_subcommand_from status' -l diff -d 'Compare source vs installed'
complete -c agentfiles -n '__fish_seen_subcommand_from status' -l tokens -d 'Show token estimates'
complete -c agentfiles -n '__fish_seen_subcommand_from status' -l format -xa 'json' -d 'Output format'

# clean-specific
complete -c agentfiles -n '__fish_seen_subcommand_from clean' -l dry-run -d 'Preview changes'
complete -c agentfiles -n '__fish_seen_subcommand_from clean' -l yes -s y -d 'Non-interactive mode'

# doctor
complete -c agentfiles -n '__fish_seen_subcommand_from doctor' -l config -s c -d 'Config file path'

# completion
complete -c agentfiles -n '__fish_seen_subcommand_from completion' -xa 'bash zsh fish' -d 'Shell type'
"""


def get_completion_script(shell: str) -> str:
    """Return the completion script for the given shell.

    Args:
        shell: One of ``"bash"``, ``"zsh"``, or ``"fish"``.

    Returns:
        The completion script as a string.

    Raises:
        ValueError: If *shell* is not a recognised shell name.
    """
    scripts = {
        "bash": BASH_COMPLETION,
        "zsh": ZSH_COMPLETION,
        "fish": FISH_COMPLETION,
    }
    if shell not in scripts:
        msg = f"Unsupported shell: {shell!r}. Choose from: bash, zsh, fish."
        raise ValueError(msg)
    return scripts[shell]
