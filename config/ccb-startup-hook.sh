#!/bin/bash
# CCB Auto-Startup Hook for Claude Code
# This script checks CCB status and auto-starts providers in WezTerm using sidecar mode

# Configuration
CCB_RUN_DIR="$HOME/.ccb/run"
CCB_CONFIG="$HOME/.ccb/ccb.config"
AUTO_START="${CCB_AUTO_START:-true}"  # Enable auto-start by default

# Function to get ping command for provider
get_ping_cmd() {
    local provider=$1
    case "$provider" in
        opencode) echo "oping" ;;
        droid) echo "dping" ;;
        *) echo "${provider:0:1}ping" ;;
    esac
}

# Function to check provider health
check_provider() {
    local provider=$1
    local ping_cmd=$(get_ping_cmd "$provider")

    if command -v "$ping_cmd" &> /dev/null; then
        if $ping_cmd 2>/dev/null | grep -qi "ok\|healthy\|connection"; then
            return 0
        fi
    fi
    return 1
}

# Function to get configured providers from ccb.config
get_configured_providers() {
    if [ -f "$CCB_CONFIG" ]; then
        # Extract providers array from JSON config
        python3 -c "import json; print(' '.join(json.load(open('$CCB_CONFIG')).get('providers', [])))" 2>/dev/null
    fi
}

# Function to get current WezTerm pane ID
get_current_pane_id() {
    if command -v wezterm &> /dev/null; then
        wezterm cli list --format json 2>/dev/null | python3 -c "
import json, sys, os
try:
    panes = json.load(sys.stdin)
    # Find the pane with matching PID or current terminal
    for p in panes:
        print(p.get('pane_id', 0))
        break
except: pass
" 2>/dev/null
    fi
}

# Main logic
echo "🔍 CCB Status Check"
echo "━━━━━━━━━━━━━━━━━━━━"

# Check if CCB is installed
if ! command -v ccb &> /dev/null; then
    echo "⚠️ CCB not installed"
    exit 0
fi

# Check terminal environment
if [ "$TERM_PROGRAM" = "WezTerm" ]; then
    echo "✅ Running in WezTerm"
    IN_WEZTERM=true
else
    echo "📍 Terminal: ${TERM_PROGRAM:-unknown}"
    IN_WEZTERM=false
fi

# Get configured providers
CONFIGURED_PROVIDERS=$(get_configured_providers)
if [ -z "$CONFIGURED_PROVIDERS" ]; then
    CONFIGURED_PROVIDERS="kimi"  # Default fallback
fi

# Check status and collect inactive providers
echo ""
echo "Provider Status:"
INACTIVE_PROVIDERS=""
ACTIVE_COUNT=0

for provider in $CONFIGURED_PROVIDERS; do
    if check_provider "$provider"; then
        echo "  ✅ $provider"
        ((ACTIVE_COUNT++))
    else
        echo "  ⬜ $provider (inactive)"
        INACTIVE_PROVIDERS="$INACTIVE_PROVIDERS $provider"
    fi
done

# Status summary
echo ""
if [ "$ACTIVE_COUNT" -gt 0 ]; then
    echo "✅ CCB ready with $ACTIVE_COUNT provider(s)"
    echo "💡 Inactive providers will auto-start on demand (sidecar mode)"
elif [ "$IN_WEZTERM" = true ]; then
    echo "💡 CCB sidecar mode enabled - providers will auto-start on demand"
    echo "   Use: gask, cask, oask, kask, qask, etc. to invoke providers"
else
    echo "💡 To use CCB: open WezTerm for sidecar auto-start"
fi

exit 0
