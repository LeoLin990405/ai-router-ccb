<p align="center">
  <img src="https://img.shields.io/github/stars/LeoLin990405/ai-router-ccb?style=social" alt="Stars">
  <img src="https://img.shields.io/github/license/LeoLin990405/ai-router-ccb?color=blue" alt="License">
  <img src="https://img.shields.io/badge/Python-3.9+-3776AB?logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white" alt="FastAPI">
</p>

<h1 align="center">
  <br>
  🤖
  <br>
  CCB Gateway
  <br>
</h1>

<h4 align="center">企业级多 AI 编排平台</h4>

<p align="center">
  <em>Claude 作为主脑，通过统一 Gateway API 调度 7 个 AI Provider，支持实时监控和模型切换</em>
</p>

<p align="center">
  <a href="#-特性">特性</a> •
  <a href="#-快速开始">快速开始</a> •
  <a href="#-ccb-cli">ccb-cli</a> •
  <a href="#-web-ui">Web UI</a> •
  <a href="#-api-参考">API</a> •
  <a href="#-模型切换">模型切换</a>
</p>

<p align="center">
  <a href="README.md">English</a> | <strong>简体中文</strong>
</p>

<p align="center">
  <img src="screenshots/webui-demo.gif" alt="CCB Gateway Web UI 演示" width="700">
</p>

---

## 概述

**CCB Gateway** 是一个生产级多 AI 编排平台，**Claude 作为主脑（Orchestrator）**，通过统一的 Gateway API 智能调度 7 个 AI Provider。

```
                    ┌─────────────────────────────┐
                    │   Claude (Orchestrator)     │
                    │      Claude Code CLI        │
                    └─────────────┬───────────────┘
                                  │
              ┌───────────────────┼───────────────────┐
              │                   │                   │
    ┌─────────▼─────────┐ ┌──────▼──────┐ ┌─────────▼─────────┐
    │   ccb-cli (新)    │ │ Gateway API │ │   ccb-submit      │
    │  直接 CLI 调用    │ │  REST/WS    │ │   异步队列        │
    └─────────┬─────────┘ └──────┬──────┘ └─────────┬─────────┘
              │                  │                   │
              └──────────────────┼───────────────────┘
                                 │
          ┌───────────┬──────────┼──────────┬───────────┐
          ▼           ▼          ▼          ▼           ▼
     ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐
     │  Kimi   │ │  Qwen   │ │DeepSeek │ │  Codex  │ │ Gemini  │
     │  🚀 7s  │ │  🚀 12s │ │  ⚡ 16s │ │ 🐢 48s  │ │ 🐢 71s  │
     └─────────┘ └─────────┘ └─────────┘ └─────────┘ └─────────┘
                      ┌─────────┐ ┌─────────┐
                      │  iFlow  │ │OpenCode │
                      │  ⚡ 25s │ │  ⚡ 42s │
                      └─────────┘ └─────────┘
```

### 为什么选择 CCB Gateway？

| 挑战 | 解决方案 |
|------|----------|
| 多个 AI CLI 接口不统一 | **统一 Gateway API** + **ccb-cli** 统一入口 |
| 手动选择 Provider | **智能路由**，基于速度分级自动降级 |
| Provider 内部无法切换模型 | **动态模型选择**（o3, gpt-4o, gemini-3-flash 等）|
| 无法观察 AI 操作 | **实时监控**，WebSocket + Web UI |
| 无缓存或重试逻辑 | **内置缓存、重试和降级链** |
| 看不到 AI 思考过程 | **思考链 & 原始输出捕获** |

---

## ✨ 特性

### 🆕 ccb-cli (v0.11)

直接 CLI 工具，支持模型选择 - 无需 Gateway：

```bash
ccb-cli <provider> [model] <prompt>
```

| Provider | 可用模型 | 示例 |
|----------|----------|------|
| **Codex** | o3, o4-mini, o1-pro, gpt-4o, gpt-5.2-codex | `ccb-cli codex o3 "复杂算法"` |
| **Gemini** | 3f, 3p, 2.5f, 2.5p | `ccb-cli gemini 3f "React 组件"` |
| **OpenCode** | mm, kimi, ds, glm | `ccb-cli opencode mm "通用任务"` |
| **DeepSeek** | reasoner, chat | `ccb-cli deepseek chat "快速问答"` |
| **Kimi** | thinking, normal | `ccb-cli kimi thinking "详细分析"` |
| **iFlow** | thinking, normal | `ccb-cli iflow "工作流任务"` |
| **Qwen** | - | `ccb-cli qwen "代码生成"` |

### 核心网关

- **REST API** - `POST /api/ask`, `GET /api/reply/{id}`, `GET /api/status`
- **WebSocket** - 实时事件推送 `/api/ws`
- **优先级队列** - SQLite 持久化的请求优先级队列
- **多后端** - HTTP API、CLI 执行、WezTerm 集成
- **健康监控** - 自动 Provider 健康检查

### 生产级功能

- **API 认证** - 基于 API Key 的认证，SHA-256 哈希
- **限流** - 令牌桶算法，支持按 Key 限流
- **响应缓存** - SQLite 缓存，支持 TTL 和模式排除
- **重试与降级** - 指数退避，自动 Provider 降级
- **并行查询** - 同时查询多个 Provider
- **Prometheus 指标** - `/metrics` 端点用于监控
- **流式响应** - Server-Sent Events 实时响应

### Provider 速度分级

| 分级 | Providers | 响应时间 | 适用场景 |
|------|-----------|----------|----------|
| 🚀 **快速** | Kimi, Qwen | 5-15 秒 | 快速任务、简单问题 |
| ⚡ **中速** | DeepSeek, iFlow, OpenCode | 15-60 秒 | 复杂推理、编程 |
| 🐢 **慢速** | Codex, Gemini | 60-120 秒 | 深度分析、代码审查 |

---

## 🚀 快速开始

### 方式 1: ccb-cli（推荐）

无需 Gateway - 直接 CLI 访问，支持模型选择：

```bash
# 安装（已包含在 ccb-dual 中）
# 脚本位置 ~/.ccb_config/scripts/ccb-cli

# 快速中文问答
ccb-cli kimi "什么是递归"

# 复杂算法用 o3
ccb-cli codex o3 "设计 LRU 缓存算法"

# 前端用 Gemini 3 Flash
ccb-cli gemini 3f "React 登录组件"

# 快速响应
ccb-cli deepseek chat "HTTP 状态码 200 表示？"

# 详细推理
ccb-cli kimi thinking "逐步分析这个问题"
```

### 方式 2: Gateway API

完整功能的异步 API，支持缓存、重试和监控：

```bash
# 启动 Gateway
cd ~/.local/share/codex-dual
python3 -m lib.gateway.gateway_server --port 8765

# 提交请求
curl -X POST http://localhost:8765/api/ask \
  -H "Content-Type: application/json" \
  -d '{"provider": "kimi", "message": "你好"}'

# 获取响应
curl "http://localhost:8765/api/reply/{request_id}"
```

### 方式 3: ccb-submit（异步）

```bash
# 异步提交并轮询
REQUEST_ID=$(ccb-submit kimi "你好")
ccb-query get $REQUEST_ID
```

---

## 🛠️ ccb-cli

### 安装

```bash
# 已安装在
~/.ccb_config/scripts/ccb-cli

# 添加到 PATH（如未添加）
export PATH="$HOME/.ccb_config/scripts:$PATH"
```

### 模型快速参考

```bash
# Codex 模型（OpenAI）
ccb-cli codex o3 "..."        # 最强推理
ccb-cli codex o4-mini "..."   # 快速
ccb-cli codex gpt-4o "..."    # 多模态
ccb-cli codex o1-pro "..."    # 专业推理

# Gemini 模型
ccb-cli gemini 3f "..."       # Gemini 3 Flash（快）
ccb-cli gemini 3p "..."       # Gemini 3 Pro（强）
ccb-cli gemini 2.5f "..."     # Gemini 2.5 Flash
ccb-cli gemini 2.5p "..."     # Gemini 2.5 Pro

# OpenCode 模型
ccb-cli opencode mm "..."     # MiniMax M2.1
ccb-cli opencode kimi "..."   # Kimi via OpenCode
ccb-cli opencode ds "..."     # DeepSeek Reasoner

# DeepSeek 模式
ccb-cli deepseek reasoner "..." # 深度推理
ccb-cli deepseek chat "..."     # 快速对话

# 思考模式（Kimi/iFlow）
ccb-cli kimi thinking "..."     # 显示推理链
ccb-cli iflow thinking "..."    # GLM 带思考
```

### 任务 → 模型选择

| 任务类型 | 推荐命令 |
|----------|----------|
| 复杂算法 | `ccb-cli codex o3 "..."` |
| 快速代码 | `ccb-cli codex o4-mini "..."` |
| 前端开发 | `ccb-cli gemini 3f "..."` |
| 深度分析 | `ccb-cli gemini 3p "..."` |
| 中文问答 | `ccb-cli kimi "..."` |
| 详细推理 | `ccb-cli kimi thinking "..."` |
| 快速对话 | `ccb-cli deepseek chat "..."` |
| 图像分析 | `ccb-cli codex gpt-4o "..."` |

---

## 🖥️ Web UI

启动 Gateway 后访问 `http://localhost:8765/`。

<p align="center">
  <img src="screenshots/dashboard.png" alt="仪表盘" width="700">
  <br>
  <em>仪表盘 - 实时网关统计和 Provider 状态</em>
</p>

### 标签页

| 标签页 | 快捷键 | 描述 |
|--------|--------|------|
| **仪表盘** | `1` | 网关统计、Provider 状态、活动日志 |
| **监控** | `2` | 实时 AI 输出流（网格/聚焦视图）|
| **请求** | `3` | 请求历史，支持搜索和过滤 |
| **测试** | `4` | 交互式 API 测试控制台 |
| **对比** | `5` | 并排 Provider 对比 |
| **API Keys** | `6` | API 密钥管理 |
| **配置** | `7` | 网关配置查看器 |

<p align="center">
  <img src="screenshots/monitor.png" alt="实时监控" width="700">
  <br>
  <em>监控 - 实时查看 AI 响应流</em>
</p>

### 功能特性

- **深色/浅色主题** - `D` 键切换
- **国际化支持** - 中英文双语
- **键盘快捷键** - `1-7` 切换标签页，`R` 刷新，`?` 帮助
- **实时更新** - WebSocket 驱动的实时数据

---

## 📡 API 参考

### 端点

| 方法 | 端点 | 描述 |
|------|------|------|
| `POST` | `/api/ask` | 提交请求 |
| `GET` | `/api/reply/{id}` | 获取响应 |
| `GET` | `/api/status` | 网关状态 |
| `GET` | `/api/requests` | 列出请求 |
| `GET` | `/metrics` | Prometheus 指标 |

### Provider 分组

```bash
# 全部 7 个 Provider
curl -d '{"provider": "@all", "message": "测试"}' ...

# 仅快速 Provider
curl -d '{"provider": "@fast", "message": "测试"}' ...

# 中文优化
curl -d '{"provider": "@chinese", "message": "测试"}' ...

# 代码任务
curl -d '{"provider": "@coding", "message": "测试"}' ...
```

---

## 🔄 模型切换

### 各 Provider 可用模型

| Provider | 可用模型 |
|----------|----------|
| **Codex** | `o3`, `o4-mini`, `o3-mini`, `o1`, `o1-pro`, `gpt-5.2-codex`, `gpt-4.5`, `gpt-4.1`, `gpt-4o` |
| **Gemini** | `gemini-3-flash-preview`, `gemini-3-pro-preview`, `gemini-2.5-flash`, `gemini-2.5-pro` |
| **OpenCode** | `opencode/minimax-m2.1-free`, `opencode/kimi-k2.5-free`, `deepseek/deepseek-reasoner` |
| **DeepSeek** | `deepseek-reasoner`, `deepseek-chat` |
| **Kimi** | `kimi-for-coding` + `--thinking` 选项 |
| **iFlow** | `GLM-4.7` + `--thinking` 选项 |
| **Qwen** | `coder-model`（OAuth 单模型）|

### Gateway 配置

编辑 `~/.ccb_config/gateway.yaml`：

```yaml
providers:
  codex:
    cli_args: ["exec", "--json", "-m", "o3"]  # 在这里切换模型

  gemini:
    cli_args: ["-m", "gemini-3-flash-preview", "-p"]

  opencode:
    cli_args: ["run", "--format", "json", "-m", "opencode/minimax-m2.1-free"]
```

修改配置后重启 Gateway。

---

## 📦 安装

### 前置条件

- Python 3.9+
- Provider CLI: `codex`, `gemini`, `opencode`, `deepseek`, `kimi`, `qwen`, `iflow`

### 安装步骤

```bash
# 克隆
git clone https://github.com/LeoLin990405/ai-router-ccb.git ~/.local/share/codex-dual

# 依赖
pip install fastapi uvicorn pyyaml aiohttp prometheus-client

# 启动 Gateway
python3 -m lib.gateway.gateway_server --port 8765

# 或直接使用 ccb-cli（无需 Gateway）
ccb-cli kimi "你好"
```

---

## 🔄 最近更新

### v0.11.x - ccb-cli & 模型切换（最新）
- **ccb-cli** - 直接 CLI 工具，支持模型选择
- **模型快捷方式** - `o3`, `3f`, `mm`, `reasoner`, `thinking`
- **expect 脚本** - 自动化 CLI 交互
- **更新文档** - 完整模型指南

### v0.10.x - 实时监控
- **实时 AI 监控** - 实时查看 AI 输出流
- **网格/聚焦视图** - 多 Provider 或单 Provider 监控
- **WebSocket 集成** - 实时 stream_chunk 事件

### v0.9.x - Provider 优化
- **Provider 速度分级** - 快速/中速/慢速分类
- **Gemini OAuth 自动刷新** - 无缝令牌管理
- **Provider 分组** - `@fast`、`@chinese`、`@coding`

---

## 🙏 致谢

- **[bfly123/claude_code_bridge](https://github.com/bfly123/claude_code_bridge)** - 原始多 AI 协作框架

---

## 📄 许可证

MIT 许可证 - 详见 [LICENSE](LICENSE)

---

<p align="center">
  <sub>人机协作共同构建</sub>
  <br>
  <sub>⭐ 如果觉得有用，请给个 Star！</sub>
</p>
