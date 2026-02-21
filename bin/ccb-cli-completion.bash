#!/bin/bash
# Bash completion for ccb-cli
# Install: source ~/.local/share/codex-dual/bin/ccb-cli-completion.bash
# Or add to ~/.bashrc: source ~/.local/share/codex-dual/bin/ccb-cli-completion.bash

_ccb_cli_completions() {
    local cur prev opts
    COMPREPLY=()
    cur="${COMP_WORDS[COMP_CWORD]}"
    prev="${COMP_WORDS[COMP_CWORD-1]}"

    # Providers
    local providers="kimi qwen iflow opencode codex gemini claude qoder auto"

    # Agent roles
    local agents="sisyphus oracle librarian explorer frontend reviewer"

    # Model shortcuts by provider
    local codex_models="o3 o4-mini gpt-4o o1-pro"
    local gemini_models="3f 3p 2.5f 2.5p"
    local opencode_models="mm kimi ds glm"
    local kimi_models="thinking normal"
    local iflow_models="thinking normal"

    # Options
    local options="-a --agent -t --timeout -h --help"

    # If completing provider (first positional arg or after option)
    if [[ ${COMP_CWORD} -eq 1 ]] || [[ ${prev} == -* && ${prev} != "-a" && ${prev} != "--agent" && ${prev} != "-t" && ${prev} != "--timeout" ]]; then
        COMPREPLY=( $(compgen -W "${providers}" -- ${cur}) )
        return 0
    fi

    # If completing after -a or --agent
    if [[ ${prev} == "-a" ]] || [[ ${prev} == "--agent" ]]; then
        COMPREPLY=( $(compgen -W "${agents}" -- ${cur}) )
        return 0
    fi

    # If completing model shortcut (second positional arg after provider)
    local first_word="${COMP_WORDS[1]}"
    if [[ ${COMP_CWORD} -eq 2 ]] || [[ ${COMP_CWORD} -eq 3 && ${COMP_WORDS[2]} == -* ]]; then
        case "${first_word}" in
            codex)
                COMPREPLY=( $(compgen -W "${codex_models} ${options}" -- ${cur}) )
                ;;
            gemini)
                COMPREPLY=( $(compgen -W "${gemini_models} ${options}" -- ${cur}) )
                ;;
            opencode)
                COMPREPLY=( $(compgen -W "${opencode_models} ${options}" -- ${cur}) )
                ;;
            kimi)
                COMPREPLY=( $(compgen -W "${kimi_models} ${options}" -- ${cur}) )
                ;;
            iflow)
                COMPREPLY=( $(compgen -W "${iflow_models} ${options}" -- ${cur}) )
                ;;
            *)
                COMPREPLY=( $(compgen -W "${options}" -- ${cur}) )
                ;;
        esac
        return 0
    fi

    # Default to options
    if [[ ${cur} == -* ]]; then
        COMPREPLY=( $(compgen -W "${options}" -- ${cur}) )
        return 0
    fi
}

# Register completion for ccb-cli
complete -F _ccb_cli_completions ccb-cli

# Also register for common aliases
complete -F _ccb_cli_completions ccb
