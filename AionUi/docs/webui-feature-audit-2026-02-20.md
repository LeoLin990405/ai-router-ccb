# HiveMind WebUI 功能审计（2026-02-20）

## 0. 修复进度（实时）
- 更新时间：2026-02-21
- 修复策略：一次一个问题，单项测试通过后再进入下一个

### 0.1 已完成
1. `agent-teams/chat` 崩溃修复（空值 `SelectItem`）
- 代码：`src/renderer/pages/agentTeams/ChatPage.tsx`
- 结果：页面可渲染，`A <Select.Item /> must have a value...` 不再出现

2. WebUI CSP 与网关调用不一致修复
- 代码：`src/webserver/config/constants.ts`
- 结果：`localhost:8765`/`localhost:25808` 请求不再被 CSP 拦截

3. Skills 编辑器 Monaco 本地加载修复（不再依赖 CDN）
- 代码：`src/renderer/pages/skills/SkillEditor.tsx`
- 依赖：`package.json` / `package-lock.json`（新增 `monaco-editor`）
- 结果：`/skills/new` 可正常渲染编辑器

4. Gateway 同源代理修复（`localhost:8765` CORS/可达链路）
- 代码：`src/webserver/routes/apiRoutes.ts`、`src/renderer/services/gatewayBaseUrl.ts`
- 影响：`/knowledge`、`/monitor*`、`/settings/hivemind`、`/agent-teams/chat`
- 结果：前端统一走 `/api/gateway/*`

5. WebUI Settings 浏览器模式失效功能移除（避免无效 403）
- 代码：`src/renderer/components/SettingsModal/contents/WebuiModalContent.tsx`
- 结果：浏览器模式仅保留 Channels，不再请求 `/api/v1/webui/status`

6. WebSocket 鉴权路径收敛（登录态驱动 + cookie 优先）
- 代码：`src/renderer/services/api/index.ts`、`src/renderer/context/AuthContext.tsx`、`src/webserver/websocket/SocketIOManager.ts`
- 结果：`invalid signature` 噪音已移除

7. 侧边栏信息架构收敛：`Hivemind` 与 `Agent Teams` 并列入口合并
- 代码：`src/renderer/layouts/SidebarNav.tsx`、`src/renderer/nexus/components/Sidebar/NexusSidebar.tsx`
- 结果：主导航只保留单一聊天入口（跳转 `/agent-teams/chat`）

8. 聊天页“分群”下拉移除（单 Scene 聊天优先）
- 代码：`src/renderer/pages/agentTeams/ChatPage.tsx`
- 结果：`agent-teams/chat` 不再展示 Team 关联下拉，避免与团队管理概念重复

9. WebSocket 传输降级（先可用后优化）
- 代码：`src/renderer/services/api/websocket-manager.ts`
- 代码：`src/adapter/browser.ts`
- 结果：WebUI 改为 `polling-only`，最小回归中未再出现 websocket 首连失败告警

10. 监控入口文案收敛（降低双入口歧义）
- 代码：`src/renderer/layouts/SidebarNav.tsx`、`src/renderer/nexus/components/Sidebar/NexusSidebar.tsx`、`src/renderer/pages/agentTeams/index.tsx`
- 结果：主导航显示 `System Monitor`，团队导航显示 `Team Monitor`

### 0.2 当前剩余阻塞
1. 无 P0 阻塞项（当前版本可用）
2. 非阻塞项：`/settings/webui` Slack/Discord 仍为 `Coming Soon`
3. 非阻塞项：`/monitor` 与 `/agent-teams/monitor` 仍是双入口，但文案已区分系统/团队

## 1. 测试范围与方法
- 测试目标：`/Users/leo/.local/share/codex-dual/AionUi` WebUI 路由与核心交互
- 运行方式：`npm run webui`（`http://127.0.0.1:25808`）
- 实测方式：Playwright 路由访问 + 控制台/网络采样 + 构建校验
- 工程校验：每次修复后执行 `npx eslint <changed-files>` + `npm run build:web`

## 2. 逐项测试结果（Step 1）

### 2.1 结果总览
- 路由级能力：核心页面可访问，关键路径可用
- 最小回归（8 路由）：`requestFailures=0`、`consoleErrors=0`、`consoleWarnings=0`
- 构建校验：通过（多次 `build:web`）
- 代码规范：本轮新增改动均通过 ESLint（仅保留历史 warning）

### 2.2 关键路由状态（摘要）
| 路由 | 状态 | 结论 |
|---|---|---|
| `/guid` | 正常 | 主聊天入口可用 |
| `/agent-teams/chat` | 正常 | 已移除分群下拉，保持单场景聊天 |
| `/knowledge` | 正常 | 请求已改为 `/api/gateway/knowledge/v2/*` |
| `/monitor*` | 正常 | 请求走 `/api/gateway/api/monitor/*` |
| `/settings/hivemind` | 正常 | 网关状态请求走同源代理 |
| `/settings/webui` | 正常（含占位） | Channels 可用；Slack/Discord 占位 |
| `/skills/new` | 正常 | Monaco 本地加载生效 |

## 3. 功能盘点、重复项与低价值项（Step 2）

### 3.1 当前实现了多少功能
按“可访问功能页面（路由级）”统计：
- 已实现并可访问：25 个路由页面
- 稳定可用：核心路径可用
- 占位功能：`/settings/webui` 中 Slack/Discord

### 3.2 重复/重叠功能
1. `Hivemind` 与 `Agent Teams` 侧边栏并列入口问题已消除。
- 收敛代码：`src/renderer/layouts/SidebarNav.tsx`、`src/renderer/nexus/components/Sidebar/NexusSidebar.tsx`

2. 旧 `hivemind` 会话与新 `agent-teams/chat` 仍处于“半迁移”状态。
- 证据：`src/renderer/pages/conversation/ChatConversation.tsx` 中仍保留历史重定向分支

3. 监控能力仍有双入口（`/monitor` 与 `/agent-teams/monitor`），当前已做文案区分（System/Team），后续可继续做结构收敛。

### 3.3 低价值或当前不可用项
1. `/test/components` 属于内部展示页，不应默认暴露在生产信息架构中。
2. `/settings/webui` 中 Slack/Discord 仍为占位能力。
- 代码：`src/renderer/components/SettingsModal/contents/ChannelModalContent.tsx`

### 3.4 关键设计与工程问题
1. `agent-teams/chat` 崩溃问题（P0）已修复。
2. Gateway 链路（CSP + CORS + 调用路径）不一致问题（P0）已修复。
3. 聊天域语义混乱（P1）已完成第一阶段收敛：入口并列与聊天页分群下拉已清理。
4. 实时链路采用“稳定优先”策略：WebUI 暂走 polling-only，后续再评估 websocket 回切。

## 4. 结论：Hivemind 与 Agent Teams 是否应并列
不应长期并列，且本轮已完成第一阶段收敛。
- 已完成：侧边栏并列入口合并，聊天页分群下拉移除。
- 仍待完成：清理历史 `hivemind` 分支与二级入口语义，彻底统一为“单聊天场景 + 团队能力”。

## 5. 后续计划（Step 3）

### 5.1 已完成（按单项修复执行）
1. 修复 `agent-teams/chat` 崩溃。
2. 修复 Gateway 同源链路与 CSP/CORS 问题。
3. 修复 Skills Monaco 加载策略。
4. 合并 `Hivemind` / `Agent Teams` 侧边栏入口。
5. 移除聊天页分群下拉，保留单场景聊天。

### 5.2 下一步（继续一次一个）
1. 清理历史 `hivemind` 会话分支（保留 Obsidian 特例时在 UI 上明确说明）。
2. 将本次路由检查固化为自动化 smoke test。
3. 评估是否保留双监控入口（若保留，增加跳转引导与说明）。
