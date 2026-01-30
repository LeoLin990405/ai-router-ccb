# CCB - 多 AI 协作平台

<p align="center">
  <strong>智能多 AI 编排：9 个 Provider + 专业化 Agent</strong>
</p>

<p align="center">
  <a href="#特性">特性</a> •
  <a href="#快速开始">快速开始</a> •
  <a href="#agent-系统">Agent</a> •
  <a href="#provider-列表">Provider</a> •
  <a href="#安装">安装</a>
</p>

[English](README.md) | **中文**

---

## 致谢

本项目站在巨人的肩膀上。特别感谢：

- **[bfly123/claude_code_bridge](https://github.com/bfly123/claude_code_bridge)** - 启发本项目的原始多 AI 协作框架。感谢您开创了桥接多个 AI 助手的概念！

- **[Grafbase/Nexus](https://github.com/grafbase/nexus)** - 智能路由引擎的灵感来源。他们在 AI 网关架构方面的工作影响了我们的统一路由设计。

- **[code-yeongyu/oh-my-opencode](https://github.com/code-yeongyu/oh-my-opencode)** - Agent 编排模式、Sisyphus Agent 概念和魔法关键词系统的灵感来源。

---

## 特性

### 核心能力
- **9 个 AI Provider**：Claude、Codex、Gemini、OpenCode、DeepSeek、Droid、iFlow、Kimi、Qwen
- **智能路由**：根据任务类型自动选择最佳 Provider
- **魔法关键词**：`@deep`、`@review`、`@all` 触发特殊行为
- **统一接口**：所有 Provider 使用一致的命令模式

### 专业化 Agent（9 个）
| Agent | 用途 | 首选 Provider |
|-------|------|---------------|
| **Sisyphus** | 代码实现 | Codex, Gemini |
| **Oracle** | 深度推理与分析 | DeepSeek, Claude |
| **Librarian** | 文档与搜索 | Claude, Gemini |
| **Explorer** | 代码库导航 | Gemini, Claude |
| **Frontend** | UI/UX 开发 | Gemini, Claude |
| **Reviewer** | 代码审查与测试 | Gemini, Claude |
| **Workflow** | 多步骤自动化 | iFlow, Droid |
| **Polyglot** | 翻译与多语言 | Kimi, Qwen |
| **Autonomous** | 长时间任务 | Droid, Codex |

### 高级特性
- **速率限制**：每个 Provider 独立的令牌桶算法
- **MCP 聚合**：跨服务器统一工具发现
- **OAuth2 认证**：安全的 Web API 访问
- **LSP/AST 工具**：基于 tree-sitter 的代码智能
- **Hooks & Skills**：可扩展的插件系统
- **性能分析**：追踪延迟、成功率
- **智能缓存**：减少重复请求
- **批量处理**：并行任务执行

---

## 快速开始

```bash
# 智能路由 - 自动选择最佳 Provider
ccb ask "添加 React 组件"        # → gemini (前端)
ccb ask "设计 API 接口"          # → codex (后端)
ccb ask "分析算法复杂度"         # → deepseek (推理)

# 魔法关键词
ccb ask "@deep 分析这个算法"     # 强制深度推理
ccb ask "@review 检查这段代码"   # 强制代码审查
ccb ask "@all 最佳方案是什么"    # 多 Provider 查询

# Agent 执行
ccb-agent auto "实现排序函数"           # 自动选择 Agent
ccb-agent execute reviewer "审计代码"   # 指定 Agent

# Provider 命令
cask "你的问题"    # Codex
gask "你的问题"    # Gemini
dskask "你的问题"  # DeepSeek
```

---

## Agent 系统

### Agent 选择
```bash
# 列出所有 Agent
ccb-agent list

# 自动选择最佳 Agent
ccb-agent auto "你的任务描述"

# 使用指定 Agent 执行
ccb-agent execute <agent> "任务"

# 显示哪个 Agent 会被选中
ccb-agent match "你的任务"
```

### Agent 能力矩阵

| 能力 | Agent | 关键词 |
|------|-------|--------|
| 代码编写 | Sisyphus, Frontend, Autonomous | 实现, 创建, 开发 |
| 代码审查 | Reviewer | 审查, 审计, 检查 |
| 深度推理 | Oracle | 分析, 推理, 算法 |
| 文档处理 | Librarian, Polyglot | 文档, 解释, 翻译 |
| 代码导航 | Explorer | 查找, 搜索, 定位 |
| 工作流 | Workflow | 自动化, 流程, 批处理 |
| 翻译 | Polyglot | 翻译, 多语言 |
| 长任务 | Autonomous | 后台, 长时间 |

---

## Provider 列表

| Provider | Ask 命令 | Ping 命令 | 最佳用途 |
|----------|----------|-----------|----------|
| Claude | `lask` | `lping` | 架构设计、通用问答 |
| Codex | `cask` | `cping` | 后端、API 开发 |
| Gemini | `gask` | `gping` | 前端、代码审查 |
| OpenCode | `oask` | `oping` | 通用编码 |
| DeepSeek | `dskask` | `dskping` | 深度推理、算法 |
| Droid | `dask` | `dping` | 自主执行 |
| iFlow | `iask` | `iping` | 工作���自动化 |
| Kimi | `kask` | `kping` | 中文、长上下文 |
| Qwen | `qask` | `qping` | 多语言 |

---

## 路由规则

| 任务类型 | 关键词 | 文件模式 | Provider |
|----------|--------|----------|----------|
| 前端 | react, vue, 组件 | `*.tsx`, `*.vue` | Gemini |
| 后端 | api, 接口, 服务器 | `api/**`, `routes/**` | Codex |
| 推理 | 分析, 算法 | - | DeepSeek |
| 架构 | 设计, 架构 | - | Claude |
| 审查 | 审查, 检查, 审计 | - | Gemini |

### 魔法关键词

| 关键词 | 动作 | 描述 |
|--------|------|------|
| `@deep` | 深度推理 | 强制使用 DeepSeek |
| `@review` | 代码审查 | 强制 Gemini 审查模式 |
| `@docs` | 文档查询 | 查询 Context7 |
| `@search` | 网络搜索 | 触发网络搜索 |
| `@all` | 多 Provider | 同时查询多个 Provider |

---

## 安装

### 前置条件
- [WezTerm](https://wezfurlong.org/wezterm/) 或 tmux
- Provider CLI：`claude`、`codex`、`gemini` 等

### 安装步骤
```bash
git clone https://github.com/LeoLin990405/ccb.git ~/.local/share/codex-dual
cd ~/.local/share/codex-dual && ./install.sh
```

### 环境变量
```bash
# 添加到 ~/.zshrc 或 ~/.bashrc
export CCB_SIDECAR_AUTOSTART=1
export CCB_SIDECAR_DIRECTION=right
export CCB_CLI_READY_WAIT_S=20
```

---

## 命令参考

### CCB 命令
```bash
ccb ask "问题"               # 智能路由
ccb route "消息"             # 显示路由决策
ccb health                   # 检查 Provider 健康状态
ccb magic                    # 列出魔法关键词

# 任务管理
ccb tasks list
ccb tasks stats

# 性能分析
ccb stats
ccb cache stats

# 批量处理
ccb batch run -f tasks.txt

# Web 仪表盘
ccb web
```

### Agent 命令
```bash
ccb-agent list               # 列出 Agent
ccb-agent auto "任务"        # 自动选择 Agent
ccb-agent execute <agent> "任务"
ccb-agent match "任务"       # 显示匹配的 Agent
```

### 速率限制
```bash
ccb-ratelimit status
ccb-ratelimit set claude --rpm 50
```

---

## 架构

```
┌─────────────────────────────────────────────────────────────────────┐
│                         CCB 平台                                     │
├─────────────────────────────────────────────────────────────────────┤
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                    Agent 层 (9 个 Agent)                     │   │
│  │  Sisyphus │ Oracle │ Librarian │ Explorer │ Frontend        │   │
│  │  Reviewer │ Workflow │ Polyglot │ Autonomous                 │   │
│  └─────────────────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                    路由引擎                                   │   │
│  │  任务分析 → Provider 选择 → 降级链                            │   │
│  └─────────────────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                 Provider 层 (9 个 Provider)                  │   │
│  │  Claude │ Codex │ Gemini │ OpenCode │ DeepSeek              │   │
│  │  Droid │ iFlow │ Kimi │ Qwen                                 │   │
│  └─────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 文件结构

```
~/.local/share/codex-dual/
├── bin/                    # CLI 命令
│   ├── ccb-ask, ccb-agent, ccb-ratelimit
│   └── cask, gask, dskask, ...
├── lib/                    # 核心模块
│   ├── unified_router.py   # 路由引擎
│   ├── agent_registry.py   # Agent 定义
│   ├── agent_executor.py   # Agent 执行器
│   ├── provider_commands.py # Provider 映射
│   └── agents/             # Agent 实现
├── mcp/                    # MCP 服务器
└── config/                 # 配置模板

~/.ccb_config/
├── unified-router.yaml     # 路由规则
├── phase4.yaml             # 高级特性配置
└── *.db                    # SQLite 数据库
```

---

## 贡献者

- **Leo** ([@LeoLin990405](https://github.com/LeoLin990405)) - 项目负责人
- **Claude** (Anthropic Claude Opus 4.5) - 架构设计与实现

---

## 许可证

MIT 许可证 - 详见 [LICENSE](LICENSE)

---

<p align="center">
  <sub>人与 AI 协作构建</sub>
</p>
