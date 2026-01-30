# AI Router CCB - 智能多 AI 协作平台

> **基于 [bfly123/claude_code_bridge](https://github.com/bfly123/claude_code_bridge) 的优化分支，新增智能任务路由功能**
>
> 特别感谢原作者 **bfly123** 和社区创建了这个出色的多 AI 协作框架。

[English](README.md) | **中文说明**

---

## 关于本项目

**AI Router CCB** 是一个统一的 AI 协作平台，能够根据任务类型、关键词和文件模式智能地将任务路由到最佳 AI provider。

### 核心特性
- **智能路由**：自动为每个任务选择最佳 AI provider
- **魔法关键词**：特殊关键词（`@deep`、`@review`、`@all` 等）触发增强行为
- **任务追踪**：基于 SQLite 的任务管理，支持状态追踪
- **性能分析**：追踪 provider 延迟、成功率和 Token 使用量
- **智能缓存**：缓存响应以减少重复请求
- **自动重试**：指数退避和 provider 降级链
- **多 Provider 查询**：同时查询多个 provider 并聚合结果
- **批量处理**：并行处理多个任务
- **Web 仪表盘**：实时监控和管理界面
- **9 个 AI Provider**：Claude、Codex、Gemini、OpenCode、DeepSeek、Droid、iFlow、Kimi、Qwen
- **统一接口**：所有 provider 使用一致的命令模式
- **健康监控**：实时 provider 状态检查
- **可配置规则**：基于 YAML 的路由配置
- **Context7 集成**：可选的文档查询功能，减少 AI 幻觉

### Phase 4 高级特性（新增）
- **速率限制**：Token Bucket 算法，支持每个 Provider 独立限制
- **MCP 聚合**：聚合多个 MCP 服务器，统一工具发现
- **专业化 Agent**：6 个 AI Agent（Sisyphus、Oracle、Librarian、Explorer、Frontend、Reviewer）
- **OAuth2 认证**：Web API 的 Token 认证
- **LSP/AST 工具**：基于 Language Server Protocol 和 tree-sitter 的代码智能
- **Hooks/Skills 系统**：事件驱动的钩子和可扩展的技能插件

### 贡献者
- **Leo** ([@LeoLin990405](https://github.com/LeoLin990405)) - 项目负责人 & 集成
- **Claude** (Anthropic Claude Opus 4.5) - 架构设计 & 代码优化
- **Codex** (OpenAI GPT-5.2 Codex) - 脚本开发 & 调试

---

## 智能任务路由

AI Router CCB 的核心创新是其智能路由引擎，灵感来自 [Nexus Router](https://github.com/grafbase/nexus)。

### 快速开始
```bash
# 智能路由 - 自动选择最佳 provider
ccb ask "添加 React 组件"        # → gemini (前端)
ccb ask "设计 API 接口"          # → codex (后端)
ccb ask "分析这个算法的复杂度"    # → deepseek (推理)

# 魔法关键词 - 触发特殊行为
ccb ask "@deep 分析这个算法"      # → deepseek (强制)
ccb ask "@review 检查这段代码"    # → gemini (代码审查模式)
ccb ask "@all 最佳方案是什么"     # → 多 provider 查询

# 仅显示路由决策（不执行）
ccb route "帮我审查这段代码"

# 检查所有 provider 健康状态
ccb health

# 列出可用的魔法关键词
ccb magic

# 强制指定 provider
ccb ask -p claude "任何问题"

# 基于文件上下文路由
ccb route -f src/components/Button.tsx "修改这个文件"

# 任务追踪
ccb ask --track "分析这段代码"   # 创建追踪任务
ccb tasks list                   # 列出所有任务
ccb tasks stats                  # 显示任务统计
```

### 路由规则

| 任务类型 | 关键词 | 文件模式 | Provider |
|----------|--------|----------|----------|
| 前端开发 | react, vue, component, 前端, 组件 | `*.tsx`, `*.vue`, `components/**` | gemini |
| 后端开发 | api, endpoint, 后端, 接口 | `api/**`, `routes/**`, `services/**` | codex |
| 架构设计 | design, architect, 设计, 架构 | - | claude |
| 深度推理 | analyze, reason, 分析, 推理, 算法 | - | deepseek |
| 代码审查 | review, check, 审查, 检查 | - | gemini |
| 快速问答 | what, how, why, 什么, 怎么 | - | claude |

### 魔法关键词

魔法关键词在消息中被检测到时会触发特殊路由行为：

| 关键词 | 动作 | Provider | 描述 |
|--------|------|----------|------|
| `@search` | web_search | gemini | 触发网络搜索 |
| `@docs` | context7_lookup | claude | 查询 Context7 文档 |
| `@deep` | deep_reasoning | deepseek | 强制深度推理模式 |
| `@review` | code_review | gemini | 强制代码审查模式 |
| `@all` | multi_provider | claude,gemini,codex | 查询多个 provider |
| `smartroute` | full_auto | - | 启用所有智能功能 |

```bash
# 示例
ccb ask "@deep 分析这个算法的时间复杂度"
ccb ask "@review 检查这段代码的安全问题"
ccb ask "@all 这个问题的最佳方案是什么"
ccb route "smartroute 优化这个函数"
```

---

## 性能分析

追踪和分析 provider 性能：

```bash
# 查看所有 provider 统计（最近 24 小时）
ccb stats

# 查看特定 provider 统计
ccb stats --provider claude --hours 48

# 显示最近请求
ccb stats recent --limit 20

# 获取汇总报告
ccb stats summary

# 查找最佳 provider
ccb stats best

# 导出数据
ccb stats --export csv > performance.csv
ccb stats --export json > performance.json

# 清理旧数据
ccb stats cleanup --days 30
```

### 追踪指标
- **延迟**：响应时间（毫秒）
- **成功率**：成功请求百分比
- **Token 使用量**：输入/输出 Token 数量（如可用）
- **请求量**：每个 provider 的总请求数

---

## 智能缓存

通过智能响应缓存减少重复请求：

```bash
# 查看缓存统计
ccb cache stats

# 列出缓存条目
ccb cache list --limit 20

# 获取特定缓存条目
ccb cache get <key>

# 清空所有缓存
ccb cache clear

# 清理过期条目
ccb cache cleanup
```

### 缓存特性
- **自动缓存**：响应自动缓存（可配置 TTL）
- **命中率追踪**：监控缓存效果
- **Provider 标记**：缓存条目按 provider 标记
- **按请求禁用**：使用 `--no-cache` 标志绕过缓存

```bash
# 绕过缓存获取新鲜响应
ccb ask --no-cache "现在几点了"
```

---

## 自动重试与降级

自动重试（指数退避）和 provider 降级链：

```bash
# 启用重试（默认）
ccb ask --retry "你的问题"

# 禁用重试
ccb ask --no-retry "你的问题"

# 自定义重试次数
ccb ask --max-retries 5 "你的问题"
```

### 降级链
当 provider 失败时，CCB 自动尝试降级 provider：

| 主 Provider | 降级链 |
|-------------|--------|
| claude | gemini → codex |
| gemini | claude → codex |
| codex | claude → gemini |
| deepseek | claude → gemini |
| kimi | claude → qwen |
| qwen | claude → kimi |

---

## 多 Provider 查询

同时查询多个 provider 并聚合结果：

```bash
# 查询所有默认 provider（claude, gemini, codex）
ccb ask "@all 最佳方案是什么"

# 指定 provider
ccb ask --multi --providers claude,gemini,deepseek "分析这个"

# 不同聚合策略
ccb ask --multi --strategy all "你的问题"      # 显示所有结果
ccb ask --multi --strategy merge "你的问题"   # 合并结果
ccb ask --multi --strategy compare "你的问题" # 并排比较
ccb ask --multi --strategy first_success "问题" # 第一个成功的响应
```

---

## 批量处理

并行处理多个任务，支持 SQLite 持久化：

```bash
# 从文件读取（每行一条消息）
ccb batch run -f tasks.txt

# 从命令行
ccb batch run "消息1" "消息2" "消息3"

# 从 stdin
echo -e "任务1\n任务2\n任务3" | ccb batch run --stdin

# 指定 provider
ccb batch run -p claude -f tasks.txt

# 控制并发数
ccb batch run -c 10 -f tasks.txt  # 10 个并发任务

# 输出结果到文件
ccb batch run -f tasks.txt -o results.txt

# 检查任务状态
ccb batch status <job_id>

# 列出最近任务
ccb batch list

# 取消任务
ccb batch cancel <job_id>

# 清理旧任务
ccb batch cleanup --hours 24

# 删除特定任务
ccb batch delete <job_id>
```

### 批量处理特性
- **SQLite 持久化**：任务在进程重启后保留
- **并行执行**：可配置并发数
- **进度追踪**：实时状态更新
- **任务管理**：列出、取消、清理、删除

---

## Web 仪表盘

通过 Web 界面实时监控和管理：

```bash
# 启动 Web 服务器（默认：localhost:8080）
ccb web

# 自定义端口
ccb web --port 9000

# 允许外部访问
ccb web --host 0.0.0.0

# 不自动打开浏览器
ccb web --no-browser
```

### 仪表盘功能
- **概览**：总请求数、成功率、缓存统计
- **Provider 性能**：每个 provider 的延迟、成功率
- **任务管理**：查看和管理任务
- **缓存管理**：查看和清理缓存
- **健康状态**：实时 provider 健康检查

**注意**：需要安装 `pip install fastapi uvicorn jinja2`

### 配置
编辑 `~/.ccb_config/unified-router.yaml` 自定义路由规则：
```yaml
routing_rules:
  - name: frontend
    priority: 10
    patterns:
      - "**/components/**"
      - "**/*.tsx"
    keywords:
      - react
      - vue
      - 前端
    provider: gemini

# 任务追踪配置
task_tracking:
  enabled: true
  db_path: ~/.ccb_config/tasks.db
  auto_cleanup: true
  cleanup_hours: 24

# 魔法关键词配置
magic_keywords:
  enabled: true
  keywords:
    - keyword: "@deep"
      action: deep_reasoning
      provider: deepseek
      description: "强制深度推理模式"
```

---

## 任务追踪系统

跨多个 AI provider 追踪和管理任务：

```bash
# 创建追踪任务
ccb ask --track "分析这段代码"
# 输出: [Task] Created task: abc123

# 列出所有任务
ccb tasks list
ccb tasks list --status running
ccb tasks list --provider deepseek

# 获取任务详情
ccb tasks get abc123

# 取消任务
ccb tasks cancel abc123

# 查看统计
ccb tasks stats

# 清理旧任务
ccb tasks cleanup --hours 24
```

### 任务状态生命周期
```
pending → running → completed
                  → failed
                  → cancelled
```

---

## Phase 4：高级特性

### 速率限制

通过智能速率限制保护 API 配额：

```bash
# 查看速率限制状态
ccb-ratelimit status

# 设置 provider 限制
ccb-ratelimit set claude --rpm 50 --tpm 100000

# 重置计数器
ccb-ratelimit reset claude

# 测试速率限制
ccb-ratelimit test claude --requests 10
```

### 专业化 Agent

6 个专业化 AI Agent，针对不同任务类型：

| Agent | 描述 | 首选 Provider |
|-------|------|---------------|
| Sisyphus | 代码实现 | codex, gemini |
| Oracle | 深度推理与分析 | deepseek, claude |
| Librarian | 文档与搜索 | claude |
| Explorer | 代码库导航 | gemini |
| Frontend | UI/UX 开发 | gemini, claude |
| Reviewer | 代码审查与测试 | claude, deepseek |

```bash
# 列出可用 Agent
ccb-agent list

# 显示 Agent 详情
ccb-agent info sisyphus

# 使用特定 Agent 执行
ccb-agent execute sisyphus "实现一个排序函数"

# 自动选择最佳 Agent
ccb-agent auto "分析这个算法"

# 显示哪个 Agent 会被选中
ccb-agent match "找出所有 API 端点"
```

### MCP 聚合

聚合多个 MCP 服务器，统一工具发现：

```bash
# 列出聚合服务器的所有工具
ccb-mcp list-tools

# 调用工具
ccb-mcp call github.list_issues --owner anthropics --repo claude

# 检查服务器健康状态
ccb-mcp health
```

### OAuth2 认证

使用 Token 认证保护 Web API：

```bash
# 创建访问令牌
curl -X POST http://localhost:8080/api/auth/token \
  -d '{"username": "admin", "password": "admin", "scopes": ["read", "write"]}'

# 在请求中使用令牌
curl -H "Authorization: Bearer <token>" http://localhost:8080/api/stats
```

### LSP/AST 工具

基于 Language Server Protocol 和 tree-sitter 的代码智能：

- **查找引用**：定位符号的所有使用位置
- **跳转定义**：跳转到符号定义
- **重命名符号**：跨文件重构
- **AST 分析**：解析和分析代码结构

### Hooks 与 Skills

使用自定义钩子和技能扩展 CCB：

```bash
# Hooks：事件驱动的扩展
# 将 Python 文件放在 ~/.ccb_config/hooks/

# Skills：可复用的任务插件
# 将技能文件夹放在 ~/.ccb_config/skills/
```

**配置文件**：`~/.ccb_config/phase4.yaml`

---

## 支持的 Provider

| Provider | 命令 | Ping | 描述 |
|----------|------|------|------|
| Claude | `lask` | `lping` | 通用、架构、快速问答 |
| Codex | `cask` | `cping` | 后端、API、系统编程 |
| Gemini | `gask` | `gping` | 前端、代码审查、多模态 |
| OpenCode | `oask` | `oping` | 通用编码辅助 |
| DeepSeek | `dskask` | `dskping` | 深度推理、算法、优化 |
| Droid | `dask` | `dping` | 自动化任务执行 |
| iFlow | `iask` | `iping` | 工作流自动化 |
| Kimi | `kask` | `kping` | 中文、长上下文 |
| Qwen | `qask` | `qping` | 多语言、通用 |

---

## 安装

### 前置条件
- [WezTerm](https://wezfurlong.org/wezterm/)（推荐）或 tmux
- 已安装的 Provider CLI：
  - `claude` (Anthropic)
  - `codex` (OpenAI)
  - `gemini` (Google)
  - 其他按需安装

### 安装步骤
```bash
# 克隆此仓库
git clone https://github.com/LeoLin990405/ai-router-ccb.git ~/.local/share/codex-dual

# 运行安装脚本
cd ~/.local/share/codex-dual
./install.sh
```

### 环境变量
添加到 `~/.zshrc` 或 `~/.bashrc`：
```bash
# CCB 核心
export CCB_SIDECAR_AUTOSTART=1
export CCB_SIDECAR_DIRECTION=right
export CCB_CLI_READY_WAIT_S=20

# DeepSeek
export CCB_DSKASKD_QUICK_MODE=1
export CCB_DSKASKD_ALLOW_NO_SESSION=1

# Kimi - CLI 启动较慢
export CCB_KASKD_STARTUP_WAIT_S=25

# iFlow (GLM) - 模型响应较慢
export CCB_IASKD_STARTUP_WAIT_S=30
```

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

# 获取待处理回复
cpend
gpend
dskpend
```

### CCB 命令
```bash
# 启动 provider
ccb codex gemini opencode

# 智能路由
ccb ask "你的问题"
ccb ask --track "追踪的问题"      # 带任务追踪
ccb ask --no-cache "新鲜查询"     # 绕过缓存
ccb ask --retry "可靠查询"        # 带自动重试
ccb route "仅显示路由"
ccb health
ccb magic                         # 列出魔法关键词

# 任务管理
ccb tasks list
ccb tasks get <task_id>
ccb tasks stats
ccb tasks cleanup

# 性能分析
ccb stats                         # 查看 provider 统计
ccb stats --provider claude       # 特定 provider
ccb stats best                    # 最佳 provider

# 缓存管理
ccb cache stats                   # 缓存统计
ccb cache list                    # 列出条目
ccb cache clear                   # 清空缓存

# 批量处理
ccb batch run -f tasks.txt        # 处理批量任务
ccb batch status <job_id>         # 检查状态
ccb batch list                    # 列出任务

# Web 仪表盘
ccb web                           # 启动 Web UI

# 文档查询（需要 Context7）
ccb docs react "如何使用 hooks"
ccb docs pandas "dataframe 操作"

# 管理
ccb kill
ccb version
ccb update
```

---

## 文件结构
```
~/.local/share/codex-dual/
├── bin/                    # 命令脚本 (ask/ping/pend)
│   ├── ccb-ask            # 智能路由 CLI
│   ├── ccb-tasks          # 任务管理 CLI
│   ├── ccb-stats          # 性能分析 CLI
│   ├── ccb-cache          # 缓存管理 CLI
│   ├── ccb-batch          # 批量处理 CLI
│   ├── ccb-web            # Web 仪表盘 CLI
│   ├── ccb-docs           # 文档查询 CLI
│   ├── ccb-agent          # Agent 执行 CLI (Phase 4)
│   ├── ccb-ratelimit      # 速率限制 CLI (Phase 4)
│   ├── cask, gask, ...    # Provider ask 命令
│   └── cping, gping, ...  # Provider ping 命令
├── lib/                    # 库模块
│   ├── unified_router.py  # 路由引擎（含魔法关键词）
│   ├── task_tracker.py    # 任务追踪系统
│   ├── performance_tracker.py  # 性能分析
│   ├── response_cache.py  # 智能缓存系统
│   ├── retry_policy.py    # 自动重试与降级
│   ├── multi_provider.py  # 多 Provider 执行
│   ├── batch_processor.py # 批量任务处理
│   ├── web_server.py      # Web 仪表盘服务器
│   ├── context7_client.py # Context7 集成
│   ├── rate_limiter.py    # 速率限制 (Phase 4)
│   ├── mcp_aggregator.py  # MCP 聚合 (Phase 4)
│   ├── agent_registry.py  # Agent 注册表 (Phase 4)
│   ├── agent_executor.py  # Agent 执行器 (Phase 4)
│   ├── auth_provider.py   # OAuth2 认证 (Phase 4)
│   ├── auth_middleware.py # 认证中间件 (Phase 4)
│   ├── lsp_client.py      # LSP 客户端 (Phase 4)
│   ├── ast_analyzer.py    # AST 分析器 (Phase 4)
│   ├── hooks_manager.py   # Hooks 系统 (Phase 4)
│   ├── skills_loader.py   # Skills 加载器 (Phase 4)
│   ├── agents/            # 专业化 Agent (Phase 4)
│   └── *_daemon.py        # Provider 守护进程
├── mcp/                    # MCP 服务器
│   ├── ccb-delegation/    # 委托 MCP 服务器
│   └── ccb-aggregator/    # 聚合 MCP 服务器 (Phase 4)
├── config/                 # 配置模板
├── ccb                     # CCB 主程序
└── install.sh              # 安装脚本

~/.ccb_config/
├── unified-router.yaml    # 路由配置
├── phase4.yaml            # Phase 4 配置
├── tasks.db               # 任务追踪数据库
├── performance.db         # 性能指标数据库
├── cache.db               # 响应缓存数据库
├── ratelimit.db           # 速率限制数据库 (Phase 4)
├── auth.db                # 认证数据库 (Phase 4)
├── hooks/                 # 自定义钩子 (Phase 4)
├── skills/                # 自定义技能 (Phase 4)
├── logs/                  # 日志文件
└── .*-session             # Provider 会话文件
```

---

## 故障排除

### Provider 无响应
1. 检查连接：`<provider>ping`
2. 验证 CLI 已安装并认证
3. 检查环境变量

### 路由不符合预期
1. 检查路由决策：`ccb route "你的消息"`
2. 查看 `~/.ccb_config/unified-router.yaml`
3. 使用 `-v` 标志查看详细输出：`ccb ask -v "消息"`

### Sidecar 未打开
1. 确保 WezTerm 正在运行
2. 检查 `CCB_SIDECAR_AUTOSTART=1`
3. 验证 `CCB_SIDECAR_DIRECTION` 已设置

---

## 致谢

本项目的实现离不开：

- **[bfly123](https://github.com/bfly123)** - claude_code_bridge 原作者。感谢您创建了这个创新的多 AI 协作框架！
- **[Grafbase / Nexus Router](https://github.com/grafbase/nexus)** - 统一路由引擎的灵感来源。他们在 AI 网关和 provider 路由方面的工作影响了我们的实现。
- **[code-yeongyu / oh-my-opencode](https://github.com/code-yeongyu/oh-my-opencode)** - Agent 编排模式、多 Agent 架构和后台任务执行的灵感来源。他们的 Sisyphus Agent 和魔法关键词概念影响了我们的设计。
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
