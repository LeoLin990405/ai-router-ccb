# CCB - Claude Code Bridge (优化版)

> **基于 [bfly123/claude_code_bridge](https://github.com/bfly123/claude_code_bridge) 的优化分支**
>
> 特别感谢原作者 **bfly123** 和社区创建了这个出色的多 AI 协作框架。

[English](README.md) | **中文说明**

---

## 关于本项目

这是一个**协作优化项目**，由以下成员共同完成：
- **Leo** ([@LeoLin990405](https://github.com/LeoLin990405)) - 项目负责人 & 集成
- **Claude** (Anthropic Claude Opus 4.5) - 架构设计 & 代码优化
- **Codex** (OpenAI GPT-5.2 Codex) - 脚本开发 & 调试

我们专注于提升单轮次、按需 AI 协作工作流的**可靠性**、**稳定性**和**易用性**。

---

## 主要优化与改进

### 1. 扩展的 Provider 支持
| Provider | 原版 | 本分支 |
|----------|------|--------|
| Claude | ✓ | ✓ |
| Codex | ✓ | ✓ |
| Gemini | ✓ | ✓ (增强) |
| OpenCode | ✓ | ✓ (增强) |
| iFlow | ✗ | ✓ **新增** |
| Kimi | ✗ | ✓ **新增** |
| Qwen | ✗ | ✓ **新增** |
| DeepSeek | ✗ | ✓ **新增** |
| Grok | ✗ | ✓ **新增** |

### 2. Sidecar 自动管理
- **自动打开**：调用 `ask <provider>` 时按需打开窗格
- **自动关闭**：任务完成后自动关闭窗格
- **可配置时间**：`*_MIN_OPEN_S` 变量控制最小打开时长

### 3. WezTerm 集成改进
- **显式窗格定位**：避免"无分割/错误窗口"问题
- **锚点覆盖**：通过 `CCB_SIDECAR_DIRECTION` 实现可靠的窗格定位
- **边框脚本**：为活动 AI 会话提供视觉反馈

### 4. Provider 特定稳定性修复

#### Gemini
- 额外的就绪检查，防止"发送前未就绪"错误
- 改进的启动门控，支持可配置延迟

#### OpenCode
- 会话文件等待机制 (`CCB_OASKD_SESSION_WAIT_S`)
- 最小打开时间，防止即时关闭

#### DeepSeek
- 快速/无头模式，确保可靠回复 (`CCB_DSKASKD_QUICK_MODE`)
- 可选的 sidecar 预览窗口
- 强制 sidecar 选项用于调试

#### Kimi / Qwen / iFlow
- 完整命令集：`*ask`、`*ping`、`*pend`
- 与其他 provider 行为一致
- **Kimi**：CLI 启动较慢，建议设置 `CCB_KASKD_STARTUP_WAIT_S=25`
- **iFlow (GLM)**：模型响应较慢，建议设置 `CCB_IASKD_STARTUP_WAIT_S=30`

### 5. 统一命令接口
所有 provider 现在支持相同的命令模式：
```bash
# 提问（后台，非阻塞）
<provider>ask "你的问题"

# 检查连接
<provider>ping

# 获取待处理回复（仅在明确请求时使用）
<provider>pend
```

### 6. 配置改进
- 通过 `CCB_CLI_READY_WAIT_S` 统一 CLI 延迟
- 每个 provider 的环境变量用于微调
- 集中配置在 `~/.ccb/ccb.config`

### 7. CLAUDE.md 集成
- 为所有 provider 预配置协作规则
- 带前缀和快捷方式的命令映射
- 快速路径分发，最小化延迟

### 8. 统一路由引擎 (Unified Router) **新增**
受 [Nexus Router](https://github.com/grafbase/nexus) 启发，CCB 现在包含智能路由引擎，可根据任务类型自动选择最佳 AI provider：

```bash
# 智能路由 - 自动选择最佳 provider
ccb ask "添加 React 组件"        # → gemini (前端)
ccb ask "设计 API 接口"          # → codex (后端)
ccb ask "分析这个算法的复杂度"    # → deepseek (推理)

# 仅显示路由决策（不执行）
ccb route "帮我审查这段代码"

# 检查所有 provider 健康状态
ccb health
```

| 任务类型 | 关键词 | 推荐 Provider |
|----------|--------|---------------|
| 前端开发 | react, vue, component, 前端 | gemini |
| 后端开发 | api, endpoint, 后端, 接口 | codex |
| 架构设计 | design, architect, 设计, 架构 | claude |
| 深度推理 | analyze, reason, 分析, 推理 | deepseek |
| 代码审查 | review, check, 审查, 检查 | gemini |
| 快速问答 | what, how, why, 什么, 怎么 | claude |

配置文件：`~/.ccb_config/unified-router.yaml`

---

## 快速开始

### 前置条件
- [WezTerm](https://wezfurlong.org/wezterm/)（推荐）或 tmux
- 已安装的 Provider CLI：
  - `claude` (Anthropic)
  - `codex` (OpenAI)
  - `gemini` (Google)
  - `opencode` (OpenCode CLI)
  - `deepseek` (DeepSeek CLI)
  - 其他按需安装

### 安装
```bash
# 克隆此仓库
git clone https://github.com/LeoLin990405/-Claude-Code-Bridge.git ~/.local/share/codex-dual

# 运行安装脚本
cd ~/.local/share/codex-dual
./install.sh
```

### 环境变量（示例）
添加到 `~/.zshrc` 或 `~/.bashrc`：
```bash
# CCB 核心
export CCB_SIDECAR_AUTOSTART=1
export CCB_SIDECAR_DIRECTION=right
export CCB_CLI_READY_WAIT_S=20
export CCB_SIDECAR_SESSION_WAIT_S=15

# DeepSeek（稳定回复 + 可选 sidecar）
export CCB_DSKASKD_QUICK_MODE=1
export CCB_DSKASKD_ALLOW_NO_SESSION=1
export CCB_DSKASKD_FORCE_SIDECAR=1
export CCB_DSKASKD_SIDECAR_MIN_OPEN_S=5
export DEEPSEEK_BIN=/path/to/deepseek

# OpenCode sidecar 稳定性
export CCB_OASKD_SESSION_WAIT_S=12
export CCB_OASKD_SIDECAR_MIN_OPEN_S=5

# Kimi - CLI 启动较慢，增加等待时间
export CCB_KASKD_STARTUP_WAIT_S=25
export CCB_KASKD_SIDECAR_MIN_OPEN_S=10

# iFlow (GLM) - 模型响应较慢，增加等待时间
export CCB_IASKD_STARTUP_WAIT_S=30
export CCB_IASKD_SIDECAR_MIN_OPEN_S=15

# Gemini
export CCB_GASKD_READY_WAIT_S=15
```

### Claude Code 启动 Hook（可选）
将 `config/ccb-startup-hook.sh` 复制到 `~/.claude/hooks/` 并配置 Claude Code 的 `settings.json`：
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
这将在 Claude Code 启动时自动检查 CCB provider 状态。

---

## 使用方法

### 在 Claude Code 中使用
```bash
# 使用前缀
@codex 审查这段代码
@gemini 搜索最新的 React 文档
@deepseek 分析这个算法

# 使用 ask 命令
ask codex "解释这个函数"
ask gemini "今天天气怎么样"
```

### 直接命令
```bash
# 提问
cask "审查这段代码"
gask "搜索文档"
dskask "分析代码"

# 检查连接
cping
gping
dskping

# 获取待处理回复（需要时）
cpend
gpend
dskpend
```

---

## 文件结构
```
~/.local/share/codex-dual/
├── bin/           # 45 个命令脚本（每个 provider 的 ask/ping/pend）
├── lib/           # 57 个库脚本
├── config/        # 配置模板
├── skills/        # Claude Code skills
├── codex_skills/  # Codex skills
├── commands/      # 自定义命令
├── ccb            # CCB 主程序
└── install.sh     # 安装脚本
```

---

## 故障排除

### Provider 无响应
1. 检查连接：`<provider>ping`
2. 验证 CLI 已安装并认证
3. 检查环境变量是否设置

### Sidecar 未打开
1. 确保 WezTerm 正在运行
2. 检查 `CCB_SIDECAR_AUTOSTART=1`
3. 验证 `CCB_SIDECAR_DIRECTION` 已设置

### DeepSeek TUI 模式问题
设置 `CCB_DSKASKD_QUICK_MODE=0` 启用 TUI 模式（稳定性较低但可交互）

---

## 致谢

本项目的实现离不开：

- **[bfly123](https://github.com/bfly123)** - claude_code_bridge 原作者。感谢您创建了这个创新的多 AI 协作框架！
- **[Grafbase / Nexus Router](https://github.com/grafbase/nexus)** - 统一路由引擎的灵感来源。他们在 AI 网关和 provider 路由方面的工作影响了我们的实现。
- **claude_code_bridge 社区** - 提供反馈和贡献
- **Anthropic** - Claude 和 Claude Code
- **OpenAI** - Codex
- **Google** - Gemini
- **DeepSeek、Kimi、Qwen、iFlow 团队** - 优秀的 AI 助手

---

## 许可证

MIT 许可证 - 详见 [LICENSE](LICENSE)

---

## 贡献

欢迎提交 Issue 和 PR！您可以：
- 报告 Bug
- 建议新功能
- 添加更多 provider 支持
- 改进文档

---

*由 Leo、Claude 和 Codex 共同构建 ❤️*
