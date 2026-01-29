# 单轮次优化 Claude Code Bridge (CCB)

> Optimized fork based on **bfly123/claude_code_bridge**. Thanks to the original author and community.

**English** | [中文说明](README_zh.md)

## What this fork focuses on
This version is built for a *single‑round, on‑demand* workflow: Claude acts as the main brain, and CCB opens/controls other CLIs only when needed, then closes them automatically. The goal is higher reliability with less manual pane management.

## Key optimizations (high‑impact)
- **Sidecar auto‑open/close**: when you call `ask <provider>`, the pane opens on demand and closes after completion.
- **WezTerm anchor override**: explicit pane targeting to avoid “no split / wrong window” issues.
- **Unified CLI delay**: consistent send delay across providers via `CCB_CLI_READY_WAIT_S`.
- **Gemini startup gating**: extra readiness checks to avoid “send before ready”.
- **DeepSeek reliability**: quick/headless mode to ensure Claude receives replies; optional sidecar preview window.
- **OpenCode stability**: wait for session file + minimum open time to prevent instant close.
- **Unified commands**: `ask/ping/pend` for all providers, including DeepSeek.

## Quick start
1. Install dependencies (WezTerm + provider CLIs)
2. Set environment variables (example below)
3. Run `claude`, then `ask gemini|opencode|deepseek ...`

### Example env (zsh)
```bash
export CCB_SIDECAR_AUTOSTART=1
export CCB_SIDECAR_DIRECTION=right
export CCB_CLI_READY_WAIT_S=20

# DeepSeek (stable reply + optional sidecar)
export CCB_DSKASKD_QUICK_MODE=1
export CCB_DSKASKD_ALLOW_NO_SESSION=1
export CCB_DSKASKD_FORCE_SIDECAR=1
export CCB_DSKASKD_SIDECAR_MIN_OPEN_S=5
export DEEPSEEK_BIN=/Users/leo/.npm-global/bin/deepseek

# OpenCode sidecar stability
export CCB_OASKD_SESSION_WAIT_S=12
export CCB_OASKD_SIDECAR_MIN_OPEN_S=5
```

## Usage
```bash
ask gemini "测试联网"
ask opencode "测试联网"
ask deepseek "测试联网"
```

## Notes
- If you **really want DeepSeek TUI**, set `CCB_DSKASKD_QUICK_MODE=0` (less stable).
- Sidecar auto‑close is driven by the request lifecycle; adjust `*_MIN_OPEN_S` if you want the pane to stay longer.

## Acknowledgements
This repository is an optimized fork of **bfly123/claude_code_bridge**. All credit to the original author and community.
