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
  <em>Claude 作为主脑，通过统一 Gateway API 调度 8 个 AI Provider，支持实时监控和模型切换</em>
</p>

<p align="center">
  <a href="#-特性">特性</a> •
  <a href="#-快速开始">快速开始</a> •
  <a href="#-ccb-cli">ccb-cli</a> •
  <a href="#-多-ai-讨论">多AI讨论</a> •
  <a href="#-web-ui">Web UI</a> •
  <a href="#-api-参考">API</a>
</p>

<p align="center">
  <a href="README.md">English</a> | <strong>简体中文</strong>
</p>

<p align="center">
  <img src="screenshots/webui-demo.gif" alt="CCB Gateway Web UI 演示" width="700">
</p>

---

## 概述

**CCB Gateway** 是一个生产级多 AI 编排平台，**Claude 作为主脑（Orchestrator）**，通过统一的 Gateway API 智能调度 8 个 AI Provider。

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
          ┌───────────┬──────────┼──────────┬───────────┬───────────┐
          ▼           ▼          ▼          ▼           ▼           ▼
     ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐
     │  Kimi   │ │  Qwen   │ │DeepSeek │ │  Qoder  │ │  Codex  │ │ Gemini  │
     │  🚀 7s  │ │  🚀 12s │ │  ⚡ 16s │ │  ⚡ 30s │ │ 🐢 48s  │ │ 🐢 71s  │
     └─────────┘ └─────────┘ └─────────┘ └─────────┘ └─────────┘ └─────────┘
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
| 无法多 AI 协作讨论 | **多 AI 讨论**，支持多轮迭代 |
| 会话间上下文丢失 | **集成记忆系统 (v0.18)**，自动注入和记录 |
| 不知道哪个 AI 最适合任务 | **智能推荐**，基于 provider 优势和历史表现 |
| AI 不知道有什么工具可用 | **预加载上下文** - 53 个 Skills + 4 个 MCP Servers 自动注入 |

---

## ✨ 特性

### 🆕 集成记忆系统 (v0.18)

**自动上下文注入和持久化记忆** - 所有 AI providers 现在都有记忆，知道有什么工具可用：

**预加载上下文：**
- 🎯 **53 个 Claude Code Skills** - 每次请求自动注入（frontend-design, pdf, xlsx, pptx, ccb 等）
- 🔌 **4 个 MCP Servers** - 实时工具可用性（chroma-mcp 等）
- 🤖 **8 个 AI Providers** - 模型、优势和使用场景预加载
- 🚀 **零查找开销** - 对话过程中无需搜索 skills

**记忆后端：**
- 💾 **SQLite 存储** - 所有对话本地持久化存储在 `~/.ccb/ccb_memory.db`
- 🔎 **全文搜索** - 即时找到相关的历史对话（FTS5）
- 📊 **使用分析** - 追踪哪个 AI 擅长哪些任务
- ☁️ **云端同步** - Google Drive 备份，每小时自动同步 (v0.17)

**自动集成 (v0.18)：**
- 🎯 **Pre-Request Hook** - 自动注入系统上下文（Skills/MCP/Providers）+ 相关记忆
- 📝 **Post-Response Hook** - 自动记录每次对话到数据库
- 🔄 **透明集成** - 使用 ccb-cli 即可，无需额外命令
- 🚀 **高性能** - <5% 延迟开销，每次请求 <100ms

```bash
# 现在所有 ccb-cli 调用都自动拥有记忆！
ccb-cli kimi "帮我做前端"
# [Gateway Middleware]
#   ✓ 系统上下文已注入（53 Skills + 4 MCP + 8 Providers）
#   ✓ 已注入 2 条相关记忆
#
# Response: 基于之前关于 React 的讨论...
#
# 💡 [已注入 2 条相关记忆]

# 查询能力
python3 lib/memory/registry.py find frontend ui
# 推荐: gemini: ccb-cli gemini

# 查看对话历史
python3 lib/memory/memory_lite.py recent 10

# 获取任务相关上下文
python3 lib/memory/memory_lite.py context algorithm reasoning
```

**快速开始：**
```bash
# 初始化注册表
python3 lib/memory/registry.py scan

# 使用增强版 CLI
ccb-mem kimi "你的问题"

# 查询统计
python3 lib/memory/memory_lite.py stats
```

**文档：**
- [快速开始指南](lib/memory/QUICKSTART.md)
- [架构设计](lib/memory/ARCHITECTURE.md)
- [实现总结](lib/memory/SUMMARY.md)

### 🆕 Web UI 优化 (v0.15)

Gateway Web UI 重大性能改进和新功能：

**性能修复：**
- **内存减少 80%** - Monitor 标签页限制 1000 行输出（循环缓冲区）
- **响应速度提升 3 倍** - WebSocket 消息批处理，FPS 从 <10 提升到 >30
- **Qoder 集成** - 完整前端支持，紫色品牌标识 🤖

**新增功能：**
- **💰 成本追踪** - 实时成本仪表板，Provider 分解和趋势可视化
- **✨ 讨论模板** - 内置 5 个讨论模板快速启动（代码审查、架构审查、API 设计、Bug 分析、性能优化）
- **📥 数据导出** - 一键导出请求历史（CSV/JSON）和讨论记录（JSON）

<p align="center">
  <img src="screenshots/webui-v015-features.png" alt="v0.15 新功能" width="700">
  <br>
  <em>v0.15 新功能：成本仪表板、讨论模板、数据导出</em>
</p>

### 🆕 Gateway 自动启动 (v0.13)

使用 ccb-cli 时 Gateway 自动启动 - 无需手动启动：

```bash
# 首次调用自动启动 Gateway
ccb-cli kimi "你好"
# ⚡ Gateway 未运行，正在启动...
# ✓ Gateway 已启动 (PID: 12345)
# Kimi 响应...

# macOS: 使用 launchd 开机自启
cp config/com.ccb.gateway.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.ccb.gateway.plist
```

### 🆕 ccb-cli (v0.11)

直接 CLI 工具，支持模型选择 - 通过 Gateway 路由：

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
| **Qoder** | - | `ccb-cli qoder "审查这段代码"` |

### 🆕 多 AI 讨论 (v0.12)

编排多个 AI Provider 进行协作讨论：

```bash
# 启动讨论
ccb-discussion "设计一个分布式缓存系统"

# 指定 Provider
ccb-discussion -p kimi,qwen,deepseek "API 设计最佳实践"

# 快速模式（2 轮）
ccb-discussion --quick "代码审查方法"

# 等待完成
ccb-discussion -w "架构决策"
```

**讨论流程：**
```
第 1 轮: 提案      →   第 2 轮: 互评      →   第 3 轮: 修订
┌─────────────┐         ┌─────────────┐         ┌─────────────┐
│ 所有 AI     │   ───►  │ 所有 AI     │   ───►  │ 根据反馈   │
│ 提出方案    │         │ 互相评审    │         │ 修订方案   │
└─────────────┘         └─────────────┘         └─────────────┘
                              │
                              ▼
                    ┌─────────────────┐
                    │ Claude 汇总     │
                    │ 共识/分歧点     │
                    └─────────────────┘
```

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
- **智能降级** - 基于可靠性的 Provider 选择
- **并行查询** - 同时查询多个 Provider
- **多 AI 讨论** - 迭代式协作讨论
- **讨论模板** - 常见场景的预置模板
- **讨论导出** - 导出到 Markdown、JSON、HTML 或 Obsidian
- **统一结果 API** - 统一查询所有 AI 响应
- **成本追踪** - 每个 provider 的 token 使用和成本监控
- **智能路由** - 基于关键词的自动 provider 选择
- **认证状态监控** - 追踪 provider 认证状态
- **记忆系统** - 持久化对话历史和能力注册表
- **上下文注入** - 自动添加记忆上下文到提示词
- **智能推荐** - 基于任务类型和历史表现选择 AI

### Provider 速度分级

| 分级 | Providers | 响应时间 | 适用场景 |
|------|-----------|----------|----------|
| 🚀 **快速** | Kimi, Qwen | 5-15 秒 | 快速任务、简单问题 |
| ⚡ **中速** | DeepSeek, iFlow, OpenCode | 15-60 秒 | 复杂推理、编程 |
| 🐢 **慢速** | Codex, Gemini | 60-120 秒 | 深度分析、代码审查 |

---

## 🚀 快速开始

### 步骤 0: 初始化记忆系统（可选但推荐）

启用持久化记忆和智能推荐：

```bash
# 扫描能力（skills、providers、MCP servers）
cd ~/.local/share/codex-dual
python3 lib/memory/registry.py scan

# 使用 ccb-mem 实现自动上下文注入
export PATH="$HOME/.local/share/codex-dual/bin:$PATH"

# 现在使用 ccb-mem 代替 ccb-cli
ccb-mem kimi "帮我做前端"
# 🧠 正在注入记忆上下文...
# [系统自动添加相关记忆、skills 和推荐]
```

详见[记忆系统文档](lib/memory/QUICKSTART.md)。

### 方式 1: ccb-cli（推荐）

Gateway 自动启动 - 直接运行命令即可：

```bash
# 安装（已包含在 ccb-dual 中）
# 脚本位置 ~/.ccb_config/scripts/ccb-cli

# 快速中文问答（Gateway 按需自动启动）
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
# Gateway 由 ccb-cli 自动启动，或手动启动：
cd ~/.local/share/codex-dual
python3 -m lib.gateway.gateway_server --port 8765

# 或安装为 launchd 服务（macOS 开机自启）：
cp config/com.ccb.gateway.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.ccb.gateway.plist

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

## 🗣️ 多 AI 讨论

### 概述

讨论功能实现真正的多 AI 协作，所有 Provider 能看到并回应彼此的观点，形成多轮迭代讨论。

### CLI 用法

```bash
# 基本讨论
ccb-discussion "设计一个微服务架构"

# 指定 Provider
ccb-discussion -p kimi,qwen,deepseek "最佳缓存策略"

# 快速模式（2 轮，更短超时）
ccb-discussion --quick "代码审查规范"

# 等待完成并显示结果
ccb-discussion -w "API 版本控制方案"

# 检查已有讨论的状态
ccb-discussion -s <session_id>

# 列出最近的讨论
ccb-discussion -l
```

### API 用法

```bash
# 通过 API 启动讨论
curl -X POST http://localhost:8765/api/discussion/start \
  -H "Content-Type: application/json" \
  -d '{"topic": "设计分布式缓存", "provider_group": "@coding"}'

# 获取讨论状态
curl http://localhost:8765/api/discussion/{session_id}

# 获取讨论的所有消息
curl http://localhost:8765/api/discussion/{session_id}/messages

# 列出所有讨论
curl http://localhost:8765/api/discussions

# 获取统一结果（请求 + 讨论）
curl http://localhost:8765/api/results
```

### 讨论轮次

| 轮次 | 类型 | 描述 |
|------|------|------|
| 1 | **提案** | 每个 AI 提供初始分析/方案 |
| 2 | **互评** | 每个 AI 评审其他人的方案，给出反馈 |
| 3 | **修订** | 每个 AI 根据收到的反馈修订方案 |
| 最终 | **汇总** | 编排者综合共识和分歧点 |

### Provider 分组

```bash
# 所有可用 Provider
ccb-discussion -g @all "话题"

# 仅快速 Provider（Kimi, Qwen）
ccb-discussion -g @fast "话题"

# 代码相关（Kimi, Qwen, DeepSeek, Codex, Gemini）
ccb-discussion -g @coding "话题"
```

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
| **监控** | `2` | 实时 AI 输出流（网格/聚焦视图，性能优化）|
| **讨论** | `3` | 多 AI 讨论监控，支持模板 |
| **请求** | `4` | 请求历史，支持搜索、过滤和导出（CSV/JSON）|
| **成本** | `5` | 💰 实时成本追踪和可视化（新增）|
| **测试** | `6` | 交互式 API 测试控制台 |
| **对比** | `7` | 并排 Provider 对比 |
| **API Keys** | `8` | API 密钥管理 |
| **配置** | `9` | 网关配置查看器 |

<p align="center">
  <img src="screenshots/discussions.png" alt="讨论" width="700">
  <br>
  <em>讨论 - 实时监控多 AI 协作讨论</em>
</p>

<p align="center">
  <img src="screenshots/costs.png" alt="成本追踪" width="700">
  <br>
  <em>成本 - 实时成本追踪，Provider 分解和 7 天趋势可视化（v0.15 新增）</em>
</p>

<p align="center">
  <img src="screenshots/monitor.png" alt="实时监控" width="700">
  <br>
  <em>监控 - 实时查看 AI 响应流，性能优化</em>
</p>

<p align="center">
  <img src="screenshots/export.png" alt="数据导出" width="700">
  <br>
  <em>导出 - 一键下载请求历史（CSV 或 JSON 格式）（v0.15 新增）</em>
</p>

### 功能特性

- **🚀 性能优化** - 内存减少 80%，UI 响应速度提升 3 倍
- **💰 成本追踪** - 实时成本监控，Provider 分解
- **📥 数据导出** - 导出请求/讨论为 CSV/JSON
- **✨ 讨论模板** - 内置模板快速启动讨论
- **深色/浅色主题** - `D` 键切换
- **国际化支持** - 中英文双语
- **键盘快捷键** - `1-9` 切换标签页，`R` 刷新，`?` 帮助
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
| `POST` | `/api/discussion/start` | 启动多 AI 讨论 |
| `GET` | `/api/discussion/{id}` | 获取讨论状态 |
| `GET` | `/api/results` | 统一结果查询 |
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

### v0.15.x - Web UI 优化（最新）

**性能改进：**
- **Monitor 内存修复** - 循环缓冲区限制输出为 1000 行（内存减少 80%）
- **WebSocket 批处理** - 50ms 消息批处理提升 UI 响应速度（FPS 提升 3-5 倍）
- **UI 稳定性** - 消除了流式输出时的内存泄漏和 DOM 抖动

**新增功能：**
- **💰 成本仪表板** - 实时成本追踪，Provider 分解和 7 天趋势图表
- **✨ 讨论模板** - 内置 5 个模板快速启动讨论
- **📥 数据导出** - 一键导出请求（CSV/JSON）和讨论（JSON）
- **🤖 Qoder 集成** - 完整前端支持，紫色品牌标识

**UI 增强：**
- 新增成本标签页（快捷键：5）
- 讨论模板模态框，动态变量表单
- 请求标签页导出下拉菜单
- Provider 特定颜色编码（Qoder 为紫色）

```bash
# 访问新功能
open http://localhost:8765
# 按 5 查看成本仪表板
# 按 3 → "Use Template" 快速启动讨论
# 按 4 → "Export" 下载数据

# 成本 API
curl "http://localhost:8765/api/costs/summary"
curl "http://localhost:8765/api/costs/by-provider"

# 模板 API
curl "http://localhost:8765/api/discussion/templates"
```

### v0.14.x - 高级功能

**Phase 6 - 讨论增强：**
- **讨论导出** - 导出讨论为 Markdown、JSON 或 HTML
- **WebSocket 实时** - `discussion_provider_started/completed` 事件实时更新
- **讨论模板** - 5 个内置模板（架构审查、代码审查、API 设计、Bug 分析、性能优化）
- **讨论继续** - 从已完成的讨论继续讨论后续话题

**Phase 7 - 运维与监控：**
- **Shell 自动补全** - Bash/Zsh 补全 ccb-cli（providers、models、agents）
- **Provider 认证状态** - 跟踪认证状态，检测认证失败
- **成本追踪仪表板** - 每个 Provider 的 Token 使用和成本追踪
- **智能降级** - 基于可靠性的 Provider 选择（`ProviderReliabilityScore`）

**Phase 8 - 集成：**
- **macOS 通知** - 长时间操作的系统通知
- **智能自动路由** - 基于关键词的自动 Provider 选择（`POST /api/route`）
- **Obsidian 集成** - 导出讨论到 Obsidian vault，带 YAML frontmatter

```bash
# 新 CLI 功能
ccb-discussion -e <session_id> -f md > discussion.md  # 导出讨论
ccb-discussion -e <session_id> -f html -o report.html  # HTML 导出

# Shell 补全（添加到 ~/.bashrc 或 ~/.zshrc）
source ~/.local/share/codex-dual/bin/ccb-cli-completion.bash  # Bash
source ~/.local/share/codex-dual/bin/ccb-cli-completion.zsh   # Zsh

# 新 API 端点
curl "http://localhost:8765/api/discussion/{id}/export?format=md"
curl -X POST "http://localhost:8765/api/discussion/templates/arch-review/use" \
  -d '{"variables": {"subject": "My API", "context": "REST microservice"}}'
curl "http://localhost:8765/api/costs/summary"
curl -X POST "http://localhost:8765/api/route" -d '{"message": "React component"}'
```

### v0.13.x - Gateway 自动启动
- **Gateway 自动启动** - ccb-cli 未运行时自动启动 Gateway
- **launchd 服务** - macOS 登录时自动启动，支持 KeepAlive
- **统一架构** - 所有 ccb-cli 调用通过 Gateway 路由，享受缓存/监控

### v0.12.x - 多 AI 讨论
- **讨论执行器** - 编排多轮 AI 讨论
- **3 轮流程** - 提案 → 互评 → 修订 → 汇总
- **ccb-discussion CLI** - 讨论命令行界面
- **统一结果 API** - 统一查询所有 AI 响应
- **WebSocket 事件** - 实时讨论进度

### v0.11.x - ccb-cli & 模型切换
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
