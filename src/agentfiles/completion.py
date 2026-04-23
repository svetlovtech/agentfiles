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
        --scope)
            COMPREPLY=( $(compgen -W "global project local all" -- "${cur}") )
            return
            ;;
        --color)
            COMPREPLY=( $(compgen -W "always auto never" -- "${cur}") )
            return
            ;;
        --format)
            COMPREPLY=( $(compgen -W "text json" -- "${cur}") )
            return
            ;;
    esac

    # Complete flags per subcommand
    case "${subcmd}" in
        pull)
            COMPREPLY=( $(compgen -W "--config --cache-dir --project-dir --scope --type --only --except --item --dry-run --yes --symlinks --update --full-clone --format --verbose --quiet --color" -- "${cur}") )
            ;;
        push)
            COMPREPLY=( $(compgen -W "--config --cache-dir --project-dir --scope --type --only --except --item --dry-run --yes --symlinks --create-pr --pr-title --pr-branch --format --verbose --quiet --color" -- "${cur}") )
            ;;
        status)
            COMPREPLY=( $(compgen -W "--source --config --cache-dir --type --list --diff --tokens --scope --format --verbose --quiet --color" -- "${cur}") )
            ;;
        clean)
            COMPREPLY=( $(compgen -W "--config --cache-dir --project-dir --scope --type --only --except --item --dry-run --yes --verbose --quiet --color" -- "${cur}") )
            ;;
        init)
            COMPREPLY=( $(compgen -W "--yes --verbose --quiet --color" -- "${cur}") )
            ;;
        doctor)
            COMPREPLY=( $(compgen -W "--config --verbose --quiet --color" -- "${cur}") )
            ;;
        verify)
            COMPREPLY=( $(compgen -W "--config --cache-dir --project-dir --scope --type --only --except --item --format --verbose --quiet --color" -- "${cur}") )
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
    local -a scopes=(global project local all)
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
                        '--cache-dir[Cache directory]:dir:_files -/' \
                        '--project-dir[Project directory]:dir:_files -/' \
                        '--scope[Filter by scope]:scope:('"${scopes[*]}"')' \
                        '--type[Item type]:type:('"${types[*]}"')' \
                        '--only[Include only these items]:name:' \
                        '--except[Exclude these items]:name:' \
                        '--item[Select specific items by key]:key:' \
                        '--dry-run[Preview changes]' \
                        '--yes[Non-interactive mode]' \
                        '--symlinks[Use symlinks instead of copying]' \
                        '--update[Git pull source first]' \
                        '--full-clone[Disable shallow clone]' \
                        '--format[Output format]:format:(text json)' \
                        '--verbose[Verbose output]' \
                        '--quiet[Quiet mode]' \
                        '--color[Color mode]:mode:(always auto never)'
                    ;;
                push)
                    _arguments \
                        '1:source:_files -/' \
                        '--config[Config file]:file:_files' \
                        '--cache-dir[Cache directory]:dir:_files -/' \
                        '--project-dir[Project directory]:dir:_files -/' \
                        '--scope[Filter by scope]:scope:('"${scopes[*]}"')' \
                        '--type[Item type]:type:('"${types[*]}"')' \
                        '--only[Include only these items]:name:' \
                        '--except[Exclude these items]:name:' \
                        '--item[Select specific items by key]:key:' \
                        '--dry-run[Preview changes]' \
                        '--yes[Non-interactive mode]' \
                        '--symlinks[Use symlinks instead of copying]' \
                        '--create-pr[Create a pull request]' \
                        '--pr-title[PR title]:title:' \
                        '--pr-branch[PR branch name]:branch:' \
                        '--format[Output format]:format:(text json)' \
                        '--verbose[Verbose output]' \
                        '--quiet[Quiet mode]' \
                        '--color[Color mode]:mode:(always auto never)'
                    ;;
                status)
                    _arguments \
                        '--source[Source repository path]:dir:_files -/' \
                        '--config[Config file]:file:_files' \
                        '--cache-dir[Cache directory]:dir:_files -/' \
                        '--type[Item type]:type:('"${types[*]}"')' \
                        '--list[List source items]' \
                        '--diff[Compare source vs installed]' \
                        '--tokens[Show token estimates]' \
                        '--scope[Filter by scope]:scope:('"${scopes[*]}"')' \
                        '--format[Output format]:format:(text json)' \
                        '--verbose[Show content-level diffs]' \
                        '--quiet[Quiet mode]' \
                        '--color[Color mode]:mode:(always auto never)'
                    ;;
                clean)
                    _arguments \
                        '1:source:_files -/' \
                        '--config[Config file]:file:_files' \
                        '--cache-dir[Cache directory]:dir:_files -/' \
                        '--project-dir[Project directory]:dir:_files -/' \
                        '--scope[Filter by scope]:scope:('"${scopes[*]}"')' \
                        '--type[Item type]:type:('"${types[*]}"')' \
                        '--only[Include only these items]:name:' \
                        '--except[Exclude these items]:name:' \
                        '--item[Select specific items by key]:key:' \
                        '--dry-run[Preview changes]' \
                        '--yes[Non-interactive mode]' \
                        '--verbose[Verbose output]' \
                        '--quiet[Quiet mode]' \
                        '--color[Color mode]:mode:(always auto never)'
                    ;;
                init)
                    _arguments \
                        '1:path:_files -/' \
                        '--yes[Non-interactive mode]' \
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
                        '--cache-dir[Cache directory]:dir:_files -/' \
                        '--project-dir[Project directory]:dir:_files -/' \
                        '--scope[Filter by scope]:scope:('"${scopes[*]}"')' \
                        '--type[Item type]:type:('"${types[*]}"')' \
                        '--only[Include only these items]:name:' \
                        '--except[Exclude these items]:name:' \
                        '--item[Select specific items by key]:key:' \
                        '--format[Output format]:format:(text json)' \
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

# Common flags for pull/push/clean/verify (use _add_common_args in CLI)
for cmd in pull push clean verify
    complete -c agentfiles -n "__fish_seen_subcommand_from $cmd" -l config -d 'Config file path'
    complete -c agentfiles -n "__fish_seen_subcommand_from $cmd" -l cache-dir -d 'Cache directory for git clones'
    complete -c agentfiles -n "__fish_seen_subcommand_from $cmd" -l project-dir -d 'Project directory for project/local scope'
    complete -c agentfiles -n "__fish_seen_subcommand_from $cmd" -l scope -xa 'global project local all' -d 'Filter by scope'
    complete -c agentfiles -n "__fish_seen_subcommand_from $cmd" -l type -xa 'agent skill command plugin config all' -d 'Item type'
    complete -c agentfiles -n "__fish_seen_subcommand_from $cmd" -l only -d 'Include only these items'
    complete -c agentfiles -n "__fish_seen_subcommand_from $cmd" -l except -d 'Exclude these items'
    complete -c agentfiles -n "__fish_seen_subcommand_from $cmd" -l item -d 'Select specific items by key'
    complete -c agentfiles -n "__fish_seen_subcommand_from $cmd" -l dry-run -s n -d 'Preview changes'
    complete -c agentfiles -n "__fish_seen_subcommand_from $cmd" -l yes -s y -d 'Non-interactive mode'
end

# pull-specific
complete -c agentfiles -n '__fish_seen_subcommand_from pull' -l symlinks -d 'Use symlinks instead of copying'
complete -c agentfiles -n '__fish_seen_subcommand_from pull' -l update -s u -d 'Git pull source first'
complete -c agentfiles -n '__fish_seen_subcommand_from pull' -l full-clone -d 'Disable shallow clone'
complete -c agentfiles -n '__fish_seen_subcommand_from pull' -l format -xa 'text json' -d 'Output format'

# push-specific
complete -c agentfiles -n '__fish_seen_subcommand_from push' -l symlinks -d 'Use symlinks instead of copying'
complete -c agentfiles -n '__fish_seen_subcommand_from push' -l create-pr -d 'Create a pull request after pushing'
complete -c agentfiles -n '__fish_seen_subcommand_from push' -l pr-title -d 'Title for the pull request'
complete -c agentfiles -n '__fish_seen_subcommand_from push' -l pr-branch -d 'Branch name for the pull request'
complete -c agentfiles -n '__fish_seen_subcommand_from push' -l format -xa 'text json' -d 'Output format'

# status-specific (does NOT use _add_common_args; has its own flag set)
complete -c agentfiles -n '__fish_seen_subcommand_from status' -l source -d 'Source repository path'
complete -c agentfiles -n '__fish_seen_subcommand_from status' -l config -d 'Config file path'
complete -c agentfiles -n '__fish_seen_subcommand_from status' -l cache-dir -d 'Cache directory for git clones'
complete -c agentfiles -n '__fish_seen_subcommand_from status' -l type -xa 'agent skill command plugin config all' -d 'Item type'
complete -c agentfiles -n '__fish_seen_subcommand_from status' -l list -d 'List source items'
complete -c agentfiles -n '__fish_seen_subcommand_from status' -l diff -d 'Compare source vs installed'
complete -c agentfiles -n '__fish_seen_subcommand_from status' -l tokens -d 'Show token estimates'
complete -c agentfiles -n '__fish_seen_subcommand_from status' -l scope -xa 'global project local all' -d 'Filter by scope'
complete -c agentfiles -n '__fish_seen_subcommand_from status' -l format -xa 'text json' -d 'Output format'

# init-specific
complete -c agentfiles -n '__fish_seen_subcommand_from init' -l yes -s y -d 'Non-interactive mode'

# doctor-specific
complete -c agentfiles -n '__fish_seen_subcommand_from doctor' -l config -s c -d 'Config file path'

# verify-specific
complete -c agentfiles -n '__fish_seen_subcommand_from verify' -l format -xa 'text json' -d 'Output format'

# completion
complete -c agentfiles -n '__fish_seen_subcommand_from completion' -xa 'bash zsh fish' -d 'Shell type'
"""

_SHELL_SCRIPTS: dict[str, str] = {
    "bash": BASH_COMPLETION,
    "zsh": ZSH_COMPLETION,
    "fish": FISH_COMPLETION,
}
_SUPPORTED_SHELLS = ", ".join(_SHELL_SCRIPTS)


def get_completion_script(shell: str) -> str:
    """Return the completion script for the given shell.

    Args:
        shell: One of ``"bash"``, ``"zsh"``, or ``"fish"``.

    Returns:
        The completion script as a string.

    Raises:
        ValueError: If *shell* is not a recognised shell name.
    """
    script = _SHELL_SCRIPTS.get(shell)
    if script is None:
        msg = f"Unsupported shell: {shell!r}. Choose from: {_SUPPORTED_SHELLS}."
        raise ValueError(msg)
    return script
