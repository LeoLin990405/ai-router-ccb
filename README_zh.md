# 单轮次优化 Claude Code Bridge (CCB)

> 本仓库基于 **bfly123/claude_code_bridge** 优化，感谢原作者与社区贡献。

[English](README.md) | **中文说明**

## 目标
围绕“**按需开窗、任务结束自动收尾**”的单轮次协作模式优化：
- Claude 作为主脑
- 其他 CLI 在调用时自动拉起 sidecar
- 任务完成自动关闭

## 核心优化点
- **自动分屏/自动关闭**：`ask <provider>` 触发 sidecar，完成后收尾。
- **WezTerm 精准锚点**：支持指定 pane，避免“分屏失败/错窗”。
- **统一发送延迟**：所有 CLI 按 `CCB_CLI_READY_WAIT_S` 延迟发送。
- **Gemini 启动保护**：增加启动就绪判断，避免“未就绪就发送”。
- **DeepSeek 稳定回包**：默认 quick/headless 模式，Claude 能稳定接收。
- **OpenCode 稳定性**：等待 session 文件 + 最短开窗时间，避免秒关。
- **统一命令体系**：`ask/ping/pend` 统一入口，含 DeepSeek。

## 快速开始
1. 安装 WezTerm 与各 Provider CLI
2. 配置环境变量（示例见下）
3. 运行 `claude` 并使用 `ask` 调用

### 示例配置（zsh）
```bash
export CCB_SIDECAR_AUTOSTART=1
export CCB_SIDECAR_DIRECTION=right
export CCB_CLI_READY_WAIT_S=20

# DeepSeek（稳定回包 + 仍可开窗）
export CCB_DSKASKD_QUICK_MODE=1
export CCB_DSKASKD_ALLOW_NO_SESSION=1
export CCB_DSKASKD_FORCE_SIDECAR=1
export CCB_DSKASKD_SIDECAR_MIN_OPEN_S=5
export DEEPSEEK_BIN=/Users/leo/.npm-global/bin/deepseek

# OpenCode sidecar 稳定性
export CCB_OASKD_SESSION_WAIT_S=12
export CCB_OASKD_SIDECAR_MIN_OPEN_S=5
```

## 使用示例
```bash
ask gemini "测试联网"
ask opencode "测试联网"
ask deepseek "测试联网"
```

## 说明
- 若坚持使用 DeepSeek 交互 TUI，可设置 `CCB_DSKASKD_QUICK_MODE=0`（稳定性会下降）。
- Sidecar 的关闭基于请求生命周期，可用 `*_MIN_OPEN_S` 调整停留时间。

## 致谢
本仓库是 **bfly123/claude_code_bridge** 的优化版本，感谢原作者与社区。
