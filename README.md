# CCB - Claude Code Bridge (Optimized Fork)

> **An optimized fork of [bfly123/claude_code_bridge](https://github.com/bfly123/claude_code_bridge)**
>
> Special thanks to the original author **bfly123** and the community for creating this amazing multi-AI collaboration framework.

**English** | [中文说明](README_zh.md)

---

## About This Fork

This repository is a **collaborative optimization project** by:
- **Leo** ([@LeoLin990405](https://github.com/LeoLin990405)) - Project lead & integration
- **Claude** (Anthropic Claude Opus 4.5) - Architecture design & code optimization
- **Codex** (OpenAI GPT-5.2 Codex) - Script development & debugging

We focused on improving **reliability**, **stability**, and **ease of use** for single-round, on-demand AI collaboration workflows.

---

## Key Optimizations & Changes

### 1. Extended Provider Support
| Provider | Original | This Fork |
|----------|----------|-----------|
| Claude | ✓ | ✓ |
| Codex | ✓ | ✓ |
| Gemini | ✓ | ✓ (enhanced) |
| OpenCode | ✓ | ✓ (enhanced) |
| iFlow | ✗ | ✓ **NEW** |
| Kimi | ✗ | ✓ **NEW** |
| Qwen | ✗ | ✓ **NEW** |
| DeepSeek | ✗ | ✓ **NEW** |
| Grok | ✗ | ✓ **NEW** |

### 2. Sidecar Auto-Management
- **Auto-open**: Panes open on-demand when you call `ask <provider>`
- **Auto-close**: Panes close automatically after task completion
- **Configurable timing**: `*_MIN_OPEN_S` variables control minimum open duration

### 3. WezTerm Integration Improvements
- **Explicit pane targeting**: Avoids "no split / wrong window" issues
- **Anchor override**: Reliable pane positioning with `CCB_SIDECAR_DIRECTION`
- **Border scripts**: Visual feedback for active AI sessions

### 4. Provider-Specific Stability Fixes

#### Gemini
- Extra readiness checks to prevent "send before ready" errors
- Improved startup gating with configurable delays

#### OpenCode
- Session file wait mechanism (`CCB_OASKD_SESSION_WAIT_S`)
- Minimum open time to prevent instant close

#### DeepSeek
- Quick/headless mode for reliable replies (`CCB_DSKASKD_QUICK_MODE`)
- Optional sidecar preview window
- Force sidecar option for debugging

#### Kimi / Qwen / iFlow
- Full command set: `*ask`, `*ping`, `*pend`
- Consistent behavior with other providers
- **Kimi**: CLI starts slowly, recommend `CCB_KASKD_STARTUP_WAIT_S=25`
- **iFlow (GLM)**: Model responds slowly, recommend `CCB_IASKD_STARTUP_WAIT_S=30`

### 5. Unified Command Interface
All providers now support the same command pattern:
```bash
# Ask a question (background, non-blocking)
<provider>ask "your question"

# Check connectivity
<provider>ping

# Get pending reply (explicit request only)
<provider>pend
```

### 6. Configuration Improvements
- Unified CLI delay via `CCB_CLI_READY_WAIT_S`
- Per-provider environment variables for fine-tuning
- Centralized config in `~/.ccb/ccb.config`

### 7. CLAUDE.md Integration
- Pre-configured collaboration rules for all providers
- Command map with prefixes and shortcuts
- Fast-path dispatch for minimal latency

### 8. Unified Router (Intelligent Task Routing) **NEW**
Inspired by [Nexus Router](https://github.com/grafbase/nexus), CCB now includes an intelligent routing engine that automatically selects the optimal AI provider based on task type:

```bash
# Smart routing - auto-selects best provider
ccb ask "添加 React 组件"        # → gemini (frontend)
ccb ask "设计 API 接口"          # → codex (backend)
ccb ask "分析这个算法的复杂度"    # → deepseek (reasoning)

# Show routing decision without executing
ccb route "帮我审查这段代码"

# Check all provider health status
ccb health
```

| Task Type | Keywords | Recommended Provider |
|-----------|----------|---------------------|
| Frontend | react, vue, component, 前端 | gemini |
| Backend | api, endpoint, 后端, 接口 | codex |
| Architecture | design, architect, 设计, 架构 | claude |
| Reasoning | analyze, reason, 分析, 推理 | deepseek |
| Code Review | review, check, 审查, 检查 | gemini |
| Quick Query | what, how, why, 什么, 怎么 | claude |

Configuration: `~/.ccb_config/unified-router.yaml`

---

## Quick Start

### Prerequisites
- [WezTerm](https://wezfurlong.org/wezterm/) (recommended) or tmux
- Provider CLIs installed:
  - `claude` (Anthropic)
  - `codex` (OpenAI)
  - `gemini` (Google)
  - `opencode` (OpenCode CLI)
  - `deepseek` (DeepSeek CLI)
  - Others as needed

### Installation
```bash
# Clone this repository
git clone https://github.com/LeoLin990405/-Claude-Code-Bridge.git ~/.local/share/codex-dual

# Run installer
cd ~/.local/share/codex-dual
./install.sh
```

### Environment Variables (Example)
Add to your `~/.zshrc` or `~/.bashrc`:
```bash
# CCB Core
export CCB_SIDECAR_AUTOSTART=1
export CCB_SIDECAR_DIRECTION=right
export CCB_CLI_READY_WAIT_S=20
export CCB_SIDECAR_SESSION_WAIT_S=15

# DeepSeek (stable reply + optional sidecar)
export CCB_DSKASKD_QUICK_MODE=1
export CCB_DSKASKD_ALLOW_NO_SESSION=1
export CCB_DSKASKD_FORCE_SIDECAR=1
export CCB_DSKASKD_SIDECAR_MIN_OPEN_S=5
export DEEPSEEK_BIN=/path/to/deepseek

# OpenCode sidecar stability
export CCB_OASKD_SESSION_WAIT_S=12
export CCB_OASKD_SIDECAR_MIN_OPEN_S=5

# Kimi - CLI starts slowly, increase wait time
export CCB_KASKD_STARTUP_WAIT_S=25
export CCB_KASKD_SIDECAR_MIN_OPEN_S=10

# iFlow (GLM) - Model responds slowly, increase wait time
export CCB_IASKD_STARTUP_WAIT_S=30
export CCB_IASKD_SIDECAR_MIN_OPEN_S=15

# Gemini
export CCB_GASKD_READY_WAIT_S=15
```

### Claude Code Startup Hook (Optional)
Copy `config/ccb-startup-hook.sh` to `~/.claude/hooks/` and configure Claude Code's `settings.json`:
```json
{
  "hooks": {
    "SessionStart": [
      {
        "matcher": "startup|resume",
        "hooks": [
          {
            "type": "command",
            "command": "$HOME/.claude/hooks/ccb-startup-hook.sh",
            "timeout": 10
          }
        ]
      }
    ]
  }
}
```
This will automatically check CCB provider status when Claude Code starts.

---

## Usage

### From Claude Code
```bash
# Using prefixes
@codex review this code
@gemini search for latest React docs
@deepseek 分析这个算法

# Using ask command
ask codex "explain this function"
ask gemini "what is the weather today"
```

### Direct Commands
```bash
# Ask questions
cask "review this code"
gask "search for documentation"
dskask "分析代码"

# Check connectivity
cping
gping
dskping

# Get pending replies (when explicitly needed)
cpend
gpend
dskpend
```

---

## File Structure
```
~/.local/share/codex-dual/
├── bin/           # 45 command scripts (ask/ping/pend for each provider)
├── lib/           # 57 library scripts
├── config/        # Configuration templates
├── skills/        # Claude Code skills
├── codex_skills/  # Codex skills
├── commands/      # Custom commands
├── ccb            # Main CCB binary
└── install.sh     # Installer script
```

---

## Troubleshooting

### Provider not responding
1. Check connectivity: `<provider>ping`
2. Verify CLI is installed and authenticated
3. Check environment variables are set

### Sidecar not opening
1. Ensure WezTerm is running
2. Check `CCB_SIDECAR_AUTOSTART=1`
3. Verify `CCB_SIDECAR_DIRECTION` is set

### DeepSeek TUI mode issues
Set `CCB_DSKASKD_QUICK_MODE=0` for TUI mode (less stable but interactive)

---

## Acknowledgements

This project would not be possible without:

- **[bfly123](https://github.com/bfly123)** - Original author of claude_code_bridge. Thank you for creating this innovative multi-AI collaboration framework!
- **[Grafbase / Nexus Router](https://github.com/grafbase/nexus)** - Inspiration for the Unified Router's intelligent task routing architecture. Their work on AI gateway and provider routing influenced our implementation.
- **The claude_code_bridge community** - For feedback and contributions
- **Anthropic** - For Claude and Claude Code
- **OpenAI** - For Codex
- **Google** - For Gemini
- **DeepSeek, Kimi, Qwen, iFlow teams** - For their excellent AI assistants

---

## License

MIT License - See [LICENSE](LICENSE) for details.

---

## Contributing

Issues and PRs are welcome! Please feel free to:
- Report bugs
- Suggest new features
- Add support for more providers
- Improve documentation

---

*Built with ❤️ by Leo, Claude, and Codex*
