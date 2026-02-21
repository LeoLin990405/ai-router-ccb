#!/bin/bash
# scan-cli-models.sh - 从各 CLI 动态扫描可用模型
# Scans available models from each CLI's binary/config
# Output: JSON array of { id, displayName, description, isDefault }

set -e

PROVIDER="$1"
if [ -z "$PROVIDER" ]; then
  echo "Usage: $0 <provider>"
  exit 1
fi

# Helper: output JSON array
json_model() {
  local id="$1" name="$2" desc="$3" default="$4"
  printf '{"id":"%s","displayName":"%s","description":"%s","isDefault":%s}' \
    "$id" "$name" "$desc" "${default:-false}"
}

case "$PROVIDER" in

  codex)
    # Extract model data from Codex binary
    CODEX_BIN=$(which codex 2>/dev/null)
    if [ -z "$CODEX_BIN" ]; then echo "[]"; exit 0; fi

    # Get current default from config
    DEFAULT_MODEL=""
    if [ -f "$HOME/.codex/config.toml" ]; then
      DEFAULT_MODEL=$(grep '^model = ' "$HOME/.codex/config.toml" | sed 's/model = "\(.*\)"/\1/' | head -1)
    fi

    # Extract slug + description pairs from binary
    MODELS=$(strings "$CODEX_BIN" | awk '
      /"slug":/ { gsub(/.*"slug": "/, ""); gsub(/".*/, ""); slug=$0 }
      /"description":/ && slug != "" {
        gsub(/.*"description": "/, ""); gsub(/".*/, "");
        print slug "|" $0; slug=""
      }
    ' | sort -u)

    # Build JSON array
    printf '['
    first=true
    while IFS='|' read -r slug desc; do
      [ -z "$slug" ] && continue
      # Skip legacy/duplicate models
      case "$slug" in gpt-5-codex|gpt-5-codex-mini|gpt-5.1|gpt-5) continue ;; esac
      $first || printf ','
      first=false
      is_default="false"
      [ "$slug" = "$DEFAULT_MODEL" ] && is_default="true"
      json_model "$slug" "$slug" "$desc" "$is_default"
    done <<< "$MODELS"
    printf ']'
    ;;

  claude)
    # Extract model selection options from Claude binary
    CLAUDE_BIN=$(which claude 2>/dev/null)
    if [ -z "$CLAUDE_BIN" ]; then
      # Try brew location
      CLAUDE_BIN="/opt/homebrew/bin/claude"
    fi
    [ ! -f "$CLAUDE_BIN" ] && { echo "[]"; exit 0; }

    # Resolve symlink
    CLAUDE_REAL=$(readlink "$CLAUDE_BIN" 2>/dev/null || echo "$CLAUDE_BIN")
    [ ! -f "$CLAUDE_REAL" ] && CLAUDE_REAL="$CLAUDE_BIN"

    # Extract model IDs from the binary's model config
    # Look for the UgA object that maps model names to IDs
    SONNET_ID=$(strings "$CLAUDE_REAL" | grep -oE "claude-sonnet-[0-9]+-[0-9]+-[0-9]+" | sort -u | tail -1)
    OPUS_ID=$(strings "$CLAUDE_REAL" | grep -oE "claude-opus-[0-9]+-[0-9]+-[0-9]+" | grep -v "4-1" | sort -u | tail -1)
    OPUS_1M_ID=$(strings "$CLAUDE_REAL" | grep -oE "claude-opus-[0-9]+-[0-9]+-[0-9]+" | sort -u | tail -1)
    HAIKU_ID=$(strings "$CLAUDE_REAL" | grep -oE "claude-haiku-[0-9]+-[0-9]+-[0-9]+" | sort -u | tail -1)

    # Fallbacks
    [ -z "$SONNET_ID" ] && SONNET_ID="claude-sonnet-4-5-20250929"
    [ -z "$OPUS_ID" ] && OPUS_ID="claude-opus-4-6-20250918"
    [ -z "$HAIKU_ID" ] && HAIKU_ID="claude-haiku-4-5-20251001"

    printf '['
    json_model "$SONNET_ID" "Sonnet 4.5 (Default)" "\$3/\$15 per Mtok" "true"
    printf ','
    json_model "$OPUS_ID" "Opus 4.6" "Most capable · \$5/\$25 per Mtok" "false"
    printf ','
    json_model "${OPUS_ID}-1m" "Opus 4.6 (1M context)" "Long sessions · \$10/\$37.50 per Mtok" "false"
    printf ','
    json_model "$HAIKU_ID" "Haiku 4.5" "Fastest · \$1/\$5 per Mtok" "false"
    printf ']'
    ;;

  opencode)
    # Run opencode models command
    MODELS=$(timeout 10 opencode models 2>/dev/null)
    if [ -z "$MODELS" ]; then echo "[]"; exit 0; fi

    # Get current default
    DEFAULT_MODEL=""
    if [ -f "$HOME/.opencode/config.yaml" ]; then
      DEFAULT_MODEL=$(grep '^model:' "$HOME/.opencode/config.yaml" | sed 's/model:\s*//' | tr -d ' ')
    fi

    # Filter to relevant providers only
    printf '['
    first=true
    echo "$MODELS" | grep -E "^(opencode/|minimax-cn-coding-plan/)" | while read -r model; do
      [ -z "$model" ] && continue
      $first || printf ','
      first=false
      is_default="false"
      [ "$model" = "$DEFAULT_MODEL" ] && is_default="true"
      # Generate display name from model ID
      name=$(echo "$model" | sed 's|.*/||')
      provider=$(echo "$model" | sed 's|/.*||')
      desc=""
      [ "$provider" != "opencode" ] && desc="via $provider"
      json_model "$model" "$name" "$desc" "$is_default"
    done
    printf ']'
    ;;

  qwen)
    # Read from ~/.qwen/settings.json
    SETTINGS="$HOME/.qwen/settings.json"
    [ ! -f "$SETTINGS" ] && { echo "[]"; exit 0; }

    python3 -c "
import json, sys
with open('$SETTINGS') as f:
    s = json.load(f)
providers = s.get('modelProviders', {}).get('openai', [])
current = s.get('model', {}).get('name', '')
models = []
for p in providers:
    mid = p.get('id') or p.get('name', 'unknown')
    models.append({
        'id': mid,
        'displayName': p.get('name', mid),
        'description': p.get('description', ''),
        'isDefault': mid == current
    })
print(json.dumps(models))
" 2>/dev/null || echo "[]"
    ;;

  kimi)
    # Read from ~/.kimi/config.toml
    CONFIG="$HOME/.kimi/config.toml"
    default_thinking="false"
    if [ -f "$CONFIG" ]; then
      grep -q "default_thinking = true" "$CONFIG" && default_thinking="true"
    fi
    printf '['
    if [ "$default_thinking" = "true" ]; then
      json_model "kimi-thinking" "Kimi 思考模式" "启用思考链" "true"
      printf ','
      json_model "kimi-normal" "Kimi 标准模式" "快速响应" "false"
    else
      json_model "kimi-normal" "Kimi 标准模式" "快速响应" "true"
      printf ','
      json_model "kimi-thinking" "Kimi 思考模式" "启用思考链" "false"
    fi
    printf ']'
    ;;

  iflow)
    # Read from ~/.iflow/settings.json
    SETTINGS="$HOME/.iflow/settings.json"
    MODEL_NAME="GLM-4.7"
    if [ -f "$SETTINGS" ]; then
      M=$(python3 -c "import json; print(json.load(open('$SETTINGS')).get('modelName','GLM-4.7'))" 2>/dev/null)
      [ -n "$M" ] && MODEL_NAME="$M"
    fi
    printf '['
    json_model "iflow-normal" "iFlow 标准 ($MODEL_NAME)" "工作流自动化" "true"
    printf ','
    json_model "iflow-thinking" "iFlow 思考 ($MODEL_NAME)" "启用思考链" "false"
    printf ']'
    ;;

  ollama)
    # Use ollama list command
    MODELS=$(timeout 5 ollama list 2>/dev/null | tail -n +2)
    if [ -z "$MODELS" ]; then echo "[]"; exit 0; fi
    printf '['
    first=true
    echo "$MODELS" | while read -r name rest; do
      [ -z "$name" ] && continue
      $first || printf ','
      first=false
      is_default="false"
      [ "$first_done" != "true" ] && is_default="true" && first_done="true"
      json_model "$name" "$name" "" "$is_default"
    done
    printf ']'
    ;;

  *)
    echo "[]"
    ;;
esac
