#compdef ccb-cli ccb

# Zsh completion for ccb-cli
# Install: source ~/.local/share/codex-dual/bin/ccb-cli-completion.zsh
# Or add to ~/.zshrc: source ~/.local/share/codex-dual/bin/ccb-cli-completion.zsh

_ccb_cli() {
    local -a providers agents options
    local -a codex_models gemini_models opencode_models kimi_models iflow_models

    # Providers
    providers=(
        'kimi:Fast Chinese AI with 128k context'
        'qwen:Multi-language code specialist'
        'iflow:Workflow automation'
        'opencode:Multi-model switching'
        'codex:OpenAI models (o3, o4-mini, gpt-4o)'
        'gemini:Google frontend specialist'
        'claude:Anthropic Claude'
        'qoder:Agentic code assistant'
        'auto:Auto-route based on task'
    )

    # Agent roles
    agents=(
        'sisyphus:Persistent improvement and bug fixing'
        'oracle:Prediction and trend analysis'
        'librarian:Documentation and knowledge organization'
        'explorer:Exploration and research'
        'frontend:Frontend development'
        'reviewer:Code review'
    )

    # Model shortcuts
    codex_models=('o3:Deep reasoning' 'o4-mini:Fast responses' 'gpt-4o:Multimodal' 'o1-pro:Professional')
    gemini_models=('3f:Gemini 3 Fast' '3p:Gemini 3 Pro' '2.5f:Gemini 2.5 Fast' '2.5p:Gemini 2.5 Pro')
    opencode_models=('mm:MiniMax' 'kimi:Kimi' 'glm:GLM')
    kimi_models=('thinking:Chain of thought' 'normal:Normal mode')
    iflow_models=('thinking:Chain of thought' 'normal:Normal mode')

    # Options
    options=(
        '-a[Agent role]:agent:->agents'
        '--agent[Agent role]:agent:->agents'
        '-t[Timeout in seconds]:timeout:'
        '--timeout[Timeout in seconds]:timeout:'
        '-h[Show help]'
        '--help[Show help]'
    )

    _arguments -C \
        '1:provider:->providers' \
        '2:model_or_prompt:->models' \
        '*:prompt:' \
        $options

    case $state in
        providers)
            _describe -t providers 'provider' providers
            ;;
        agents)
            _describe -t agents 'agent role' agents
            ;;
        models)
            local provider=${words[2]}
            case $provider in
                codex)
                    _describe -t models 'model' codex_models
                    ;;
                gemini)
                    _describe -t models 'model' gemini_models
                    ;;
                opencode)
                    _describe -t models 'model' opencode_models
                    ;;
                kimi)
                    _describe -t models 'model' kimi_models
                    ;;
                iflow)
                    _describe -t models 'model' iflow_models
                    ;;
            esac
            ;;
    esac
}

# Register completion
compdef _ccb_cli ccb-cli
compdef _ccb_cli ccb
