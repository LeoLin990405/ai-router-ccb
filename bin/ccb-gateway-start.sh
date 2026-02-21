#!/bin/bash
# Gateway启动脚本，确保环境变量正确传递

cd ~/.local/share/codex-dual

# Load environment from shell config
if [[ -f "$HOME/.zshrc" ]]; then
    source "$HOME/.zshrc" 2>/dev/null || true
elif [[ -f "$HOME/.bashrc" ]]; then
    source "$HOME/.bashrc" 2>/dev/null || true
fi

# If OPENAI_API_KEY not set, try to load from Codex auth.json (for OpenAI-compatible CLIs like Qwen)
if [[ -z "${OPENAI_API_KEY:-}" && -f "$HOME/.codex/auth.json" ]]; then
    OPENAI_API_KEY="$(python3 - <<'PY'
import json
from pathlib import Path
path = Path.home() / ".codex" / "auth.json"
try:
    data = json.loads(path.read_text())
    print(data.get("OPENAI_API_KEY", "") or "")
except Exception:
    print("")
PY
    )"
    if [[ -n "$OPENAI_API_KEY" ]]; then
        export OPENAI_API_KEY
    fi
fi

# Fallback values if not set
export ANTIGRAVITY_API_KEY="${ANTIGRAVITY_API_KEY:-sk-89f5748589e74b55926fb869d53e01e6}"
export ANTIGRAVITY_BASE_URL="${ANTIGRAVITY_BASE_URL:-http://127.0.0.1:8045}"

# Start Gateway
exec python3 -m lib.gateway.gateway_server --port 8765
