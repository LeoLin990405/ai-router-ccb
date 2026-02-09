# Hivemind v1.1 — 知识库 + 智能路由统一规格书

> **前置条件**: v1.0 优化重构完成且测试通过
> **目标版本**: v1.0.0 → v1.1.0
> **生成日期**: 2026-02-09
> **两大目标**:
> 1. 知识库多 Agent 共享层 — 让蜂群所有 Agent 能读写共享知识
> 2. Skill/MCP 智能路由 — 自动发现并激活最匹配的 skill 或 MCP tool

---

## 0. 执行摘要

### 当前状态 (v1.0 完成后)

| 组件 | 状态 | 多 Agent? |
|------|------|-----------|
| Knowledge Hub (NotebookLM + Obsidian + MinerU) | ✅ | ❌ 单用户 |
| Memory V2 (13表 + FTS5) | ✅ | ❌ 无 agent_id |
| Gateway `/knowledge/*` API | ✅ 7 端点 | ❌ 无 agent 上下文 |
| 本地 Skills | 68 个 | ❌ 只能手动选 |
| MCP Servers | 2 活跃 + 15 可装 | ❌ 无自动发现 |
| MCP Tools | ~60+ | ❌ 无索引 |
| 远程 Skills | skills.sh 生态 | ❌ 只有 find-skills |

### 目标状态 (v1.1)

```
┌─────────────────────────────────────────────────────────────────┐
│                    Hivemind v1.1 新增层                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────────────────┐  ┌──────────────────────────────┐ │
│  │  Shared Knowledge Base  │  │    Skill / MCP Router        │ │
│  │  (多 Agent 共享知识)     │  │    (智能工具发现)             │ │
│  │                         │  │                              │ │
│  │  • agent_id 感知        │  │  • 统一索引 (skill+MCP+远程) │ │
│  │  • 发布/订阅            │  │  • 关键词匹配               │ │
│  │  • 共识机制             │  │  • 自动安装/激活             │ │
│  │  • 统一查询             │  │  • 使用反馈学习              │ │
│  └────────┬────────────────┘  └──────────────┬───────────────┘ │
│           │                                   │                 │
│  ─────────┴───────────────────────────────────┴──────────────── │
│                     Gateway API (v1.0)                          │
│           /shared-knowledge/*    /tool-router/*                 │
├─────────────────────────────────────────────────────────────────┤
│  已有基础:                                                      │
│  Knowledge Hub │ Memory V2 │ 68 Skills │ MCP │ 9 Providers     │
└─────────────────────────────────────────────────────────────────┘
```

---

## 1. 模块 A: 多 Agent 共享知识层

### 1.1 问题

当前知识系统是单用户设计:
- Agent A 学到的东西，Agent B 看不到
- 无法记录"谁发现了什么"
- 不能跨 Memory + NotebookLM + Obsidian 统一查询
- 多 Agent 意见冲突时无共识机制

### 1.2 数据库变更

在 v1.0 统一数据库 `data/hivemind.db` 基础上新增表:

```sql
-- ═══ 新增表 ═══

-- Agent 注册表
CREATE TABLE IF NOT EXISTS agents (
    agent_id TEXT PRIMARY KEY,         -- "kimi", "codex", "gemini", ...
    display_name TEXT NOT NULL,
    capabilities TEXT,                 -- JSON: ["中文", "代码", "推理"]
    trust_score REAL DEFAULT 0.5,      -- 0-1, 随使用动态调整
    last_active TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

-- 共享知识条目
CREATE TABLE IF NOT EXISTS shared_knowledge (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category TEXT NOT NULL,            -- 'fact' | 'insight' | 'decision' | 'constraint' | 'preference'
    topic TEXT NOT NULL,               -- 关键词/主题，用于快速匹配
    content TEXT NOT NULL,
    source_agent TEXT NOT NULL,        -- 谁贡献的
    source_context TEXT,               -- 来源上下文 (request_id, session_id 等)
    confidence REAL DEFAULT 1.0,       -- 初始置信度
    consensus_count INTEGER DEFAULT 1, -- 多少 Agent 认同
    expires_at TEXT,                   -- 可选过期时间
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (source_agent) REFERENCES agents(agent_id)
);

-- 共识投票
CREATE TABLE IF NOT EXISTS knowledge_votes (
    knowledge_id INTEGER NOT NULL,
    agent_id TEXT NOT NULL,
    vote TEXT NOT NULL,                -- 'agree' | 'disagree' | 'uncertain'
    reason TEXT,
    voted_at TEXT DEFAULT (datetime('now')),
    PRIMARY KEY (knowledge_id, agent_id),
    FOREIGN KEY (knowledge_id) REFERENCES shared_knowledge(id),
    FOREIGN KEY (agent_id) REFERENCES agents(agent_id)
);

-- Agent 访问日志 (用于学习哪些知识对谁有用)
CREATE TABLE IF NOT EXISTS knowledge_access_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    knowledge_id INTEGER NOT NULL,
    agent_id TEXT NOT NULL,
    access_type TEXT NOT NULL,         -- 'read' | 'cite' | 'update'
    was_useful INTEGER,                -- 1=有用, 0=无用, NULL=未反馈
    accessed_at TEXT DEFAULT (datetime('now'))
);

-- FTS5 全文搜索
CREATE VIRTUAL TABLE IF NOT EXISTS shared_knowledge_fts USING fts5(
    topic, content,
    content='shared_knowledge',
    content_rowid='id'
);

-- ═══ 修改已有表 ═══

-- Memory V2 sessions 加 agent_id
-- ALTER TABLE sessions ADD COLUMN agent_id TEXT;
-- (v1.0 重构时已改 schema, 这里只需确保字段存在)
```

### 1.3 Gateway API 新端点

```
POST   /api/shared-knowledge/publish     ← Agent 发布新知识
GET    /api/shared-knowledge/query       ← 统一查询 (跨 Memory + NotebookLM + Obsidian)
POST   /api/shared-knowledge/vote        ← Agent 对知识投票 (共识)
GET    /api/shared-knowledge/feed        ← 最近发布的知识 (分页)
GET    /api/shared-knowledge/agent/:id   ← 某 Agent 的贡献
GET    /api/shared-knowledge/stats       ← 知识库统计
DELETE /api/shared-knowledge/:id         ← 删除/废弃知识
```

#### 端点详细设计

**POST /api/shared-knowledge/publish**

```json
// Request
{
  "agent_id": "kimi",
  "category": "insight",
  "topic": "React hooks 性能",
  "content": "useCallback 在依赖数组频繁变化时反而会降低性能，因为闭包创建的开销",
  "source_context": {"request_id": "abc123", "session_id": "xyz"}
}

// Response
{
  "id": 42,
  "status": "published",
  "confidence": 1.0,
  "consensus_count": 1
}
```

**GET /api/shared-knowledge/query**

```json
// Request: /api/shared-knowledge/query?q=React性能&sources=all&agent_id=codex
// 参数:
//   q           - 查询文本
//   sources     - all | memory | notebooklm | obsidian | shared (默认 all)
//   agent_id    - 查询者 (用于记录访问日志)
//   min_confidence - 最低置信度 (默认 0.3)
//   limit       - 结果数 (默认 10)

// Response
{
  "results": [
    {
      "source": "shared_knowledge",
      "id": 42,
      "topic": "React hooks 性能",
      "content": "useCallback 在依赖数组...",
      "source_agent": "kimi",
      "confidence": 0.9,
      "consensus_count": 3,
      "relevance_score": 0.87
    },
    {
      "source": "notebooklm",
      "notebook_id": "abc",
      "content": "React 性能优化指南...",
      "relevance_score": 0.72
    },
    {
      "source": "memory",
      "session_id": "xyz",
      "content": "之前讨论过 useMemo...",
      "relevance_score": 0.65
    }
  ],
  "query_time_ms": 45
}
```

**POST /api/shared-knowledge/vote**

```json
// Request
{
  "knowledge_id": 42,
  "agent_id": "codex",
  "vote": "agree",
  "reason": "经验证 useCallback 在依赖数组 >5 项时确实有此问题"
}

// Response
{
  "knowledge_id": 42,
  "consensus_count": 3,
  "confidence": 0.93,   // 自动根据投票更新
  "votes": {"agree": 3, "disagree": 0, "uncertain": 1}
}
```

### 1.4 统一查询路由逻辑

```python
async def unified_query(q: str, sources: str = "all") -> List[Result]:
    """统一查询: 并行搜索所有知识源，按相关性排序返回。"""
    tasks = []

    if sources in ("all", "shared"):
        tasks.append(search_shared_knowledge(q))     # SQLite FTS5

    if sources in ("all", "memory"):
        tasks.append(search_memory(q))                # Memory V2 FTS5

    if sources in ("all", "notebooklm"):
        tasks.append(search_notebooklm(q))            # ccb-knowledge query

    if sources in ("all", "obsidian"):
        tasks.append(search_obsidian(q))              # Obsidian vault 搜索

    results = await asyncio.gather(*tasks, return_exceptions=True)

    # 合并 + 按 relevance_score 排序
    merged = []
    for r in results:
        if isinstance(r, list):
            merged.extend(r)
    merged.sort(key=lambda x: x.get("relevance_score", 0), reverse=True)
    return merged
```

### 1.5 置信度算法

```python
def update_confidence(knowledge_id: int) -> float:
    """根据投票和使用反馈更新知识置信度。"""
    votes = get_votes(knowledge_id)
    access = get_access_log(knowledge_id)

    # 投票因子: agree +0.1, disagree -0.2, uncertain ±0
    vote_score = sum(
        0.1 if v.vote == "agree" else -0.2 if v.vote == "disagree" else 0
        for v in votes
    )

    # 使用因子: 被引用越多越可信
    cite_count = sum(1 for a in access if a.access_type == "cite")
    use_score = min(cite_count * 0.05, 0.3)

    # 时间衰减: 每30天 -0.05
    age_days = (now() - knowledge.created_at).days
    decay = max(-0.5, -(age_days // 30) * 0.05)

    confidence = max(0.0, min(1.0, 0.5 + vote_score + use_score + decay))
    return confidence
```

---

## 2. 模块 B: Skill / MCP 智能路由

### 2.1 问题

| 资源 | 数量 | 发现方式 | 用户体验 |
|------|------|----------|----------|
| 本地 Skills | 68 | scan-skills.sh | 要记住名字或 triggers |
| MCP Tools | ~60+ | 运行时可见 | 不知道有什么 |
| 可装 MCP Servers | 15 个 | 插件市场 .mcp.json | 需要手动装 |
| 远程 Skills | skills.sh | npx skills find | 需要知道搜什么 |

**目标**: 用户说"我要做 X"→ 系统自动推荐最佳 skill/tool → 一键激活。

### 2.2 统一索引设计

```
~/.claude/skills/skill-router/
├── SKILL.md           ← Skill 定义 (always-on advisor)
├── index.json         ← 统一索引 (自动生成)
├── build-index.sh     ← 索引构建脚本
├── router.py          ← 匹配算法
└── usage-stats.json   ← 使用统计 (反馈学习)
```

**index.json 结构**:

```json
{
  "version": "1.0",
  "built_at": "2026-02-09T10:00:00Z",
  "entries": [
    {
      "id": "skill:pdf",
      "type": "skill",
      "name": "pdf",
      "description": "PDF manipulation toolkit for extracting text...",
      "keywords": ["pdf", "extract", "merge", "split", "form", "table"],
      "triggers": ["pdf", "PDF"],
      "source": "local",
      "status": "installed",
      "activate": "/pdf",
      "install_cmd": null
    },
    {
      "id": "mcp:github:create_pull_request",
      "type": "mcp-tool",
      "name": "create_pull_request",
      "server": "github",
      "description": "Create a new pull request in a GitHub repository",
      "keywords": ["pr", "pull request", "github", "merge", "review"],
      "source": "mcp-active",
      "status": "active",
      "activate": "mcp__github__create_pull_request",
      "install_cmd": null
    },
    {
      "id": "mcp-server:playwright",
      "type": "mcp-server",
      "name": "playwright",
      "description": "Browser automation and testing",
      "keywords": ["browser", "test", "e2e", "screenshot", "web", "playwright"],
      "source": "marketplace",
      "status": "available",
      "activate": null,
      "install_cmd": "从 ~/.claude/plugins/.../playwright/.mcp.json 安装",
      "mcp_config_path": "~/.claude/plugins/marketplaces/claude-plugins-official/external_plugins/playwright/.mcp.json"
    },
    {
      "id": "remote:vercel-react-best-practices",
      "type": "remote-skill",
      "name": "vercel-react-best-practices",
      "description": "React and Next.js performance optimization",
      "keywords": ["react", "nextjs", "performance", "vercel"],
      "source": "skills.sh",
      "status": "available",
      "activate": null,
      "install_cmd": "npx skills add vercel-labs/agent-skills@vercel-react-best-practices -g -y"
    }
  ]
}
```

### 2.3 索引构建脚本 (build-index.sh)

```bash
#!/bin/bash
# build-index.sh — 从 4 个来源构建统一索引

OUTPUT="$HOME/.claude/skills/skill-router/index.json"

python3 << 'PYEOF'
import json, os, re, subprocess, sys
from pathlib import Path
from datetime import datetime

entries = []

# ── Source 1: 本地 Skills ──
skills_dir = Path.home() / ".claude" / "skills"
for skill_dir in sorted(skills_dir.iterdir()):
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.exists():
        continue

    text = skill_md.read_text(encoding="utf-8", errors="replace")

    # 解析 frontmatter
    name = skill_dir.name
    description = ""
    triggers = []
    if text.startswith("---"):
        fm_end = text.find("---", 3)
        if fm_end > 0:
            fm = text[3:fm_end]
            for line in fm.split("\n"):
                if line.strip().startswith("description:"):
                    description = line.split(":", 1)[1].strip().strip("'\"")
                if line.strip().startswith("- "):
                    triggers.append(line.strip("- \n"))

    # 提取关键词 (from description + triggers)
    keywords = list(set(triggers + re.findall(r'\b[a-zA-Z]{3,}\b', description.lower())))

    entries.append({
        "id": f"skill:{name}",
        "type": "skill",
        "name": name,
        "description": description[:200],
        "keywords": keywords[:20],
        "triggers": triggers,
        "source": "local",
        "status": "installed",
        "activate": f"/{name}",
        "install_cmd": None,
    })

# ── Source 2: MCP Server 插件市场 ──
marketplace = Path.home() / ".claude" / "plugins" / "marketplaces" / "claude-plugins-official" / "external_plugins"
if marketplace.exists():
    for plugin_dir in sorted(marketplace.iterdir()):
        mcp_json = plugin_dir / ".mcp.json"
        if not mcp_json.exists():
            continue
        try:
            config = json.loads(mcp_json.read_text())
            for server_name, server_cfg in config.items():
                entries.append({
                    "id": f"mcp-server:{server_name}",
                    "type": "mcp-server",
                    "name": server_name,
                    "description": f"{server_name} MCP server",
                    "keywords": [server_name, plugin_dir.name],
                    "triggers": [],
                    "source": "marketplace",
                    "status": "available",
                    "activate": None,
                    "install_cmd": f"install from {mcp_json}",
                    "mcp_config_path": str(mcp_json),
                })
        except json.JSONDecodeError:
            pass

# ── Source 3: 已配置的 MCP Servers + Tools ──
# (运行时通过 ListMcpResourcesTool 获取, 这里标记占位)
# 实际工具列表在 Claude 运行时动态获取

# ── Output ──
index = {
    "version": "1.0",
    "built_at": datetime.now().isoformat(),
    "entry_count": len(entries),
    "entries": entries,
}

output_path = os.environ.get("OUTPUT", str(Path.home() / ".claude/skills/skill-router/index.json"))
Path(output_path).parent.mkdir(parents=True, exist_ok=True)
Path(output_path).write_text(json.dumps(index, ensure_ascii=False, indent=2))
print(f"Built index: {len(entries)} entries → {output_path}")
PYEOF
```

### 2.4 匹配算法

```python
"""skill-router 匹配算法。"""
import json
import re
from pathlib import Path
from typing import List, Dict, Optional

INDEX_PATH = Path.home() / ".claude" / "skills" / "skill-router" / "index.json"
USAGE_PATH = Path.home() / ".claude" / "skills" / "skill-router" / "usage-stats.json"


def load_index() -> List[Dict]:
    if not INDEX_PATH.exists():
        return []
    return json.loads(INDEX_PATH.read_text()).get("entries", [])


def load_usage() -> Dict:
    if not USAGE_PATH.exists():
        return {}
    return json.loads(USAGE_PATH.read_text())


def extract_keywords(query: str) -> List[str]:
    """从用户查询中提取关键词。"""
    # 英文词
    en_words = re.findall(r'\b[a-zA-Z][a-zA-Z0-9.-]+\b', query.lower())
    # 中文关键词映射
    cn_map = {
        "前端": ["frontend", "react", "vue", "css", "html", "ui"],
        "后端": ["backend", "api", "server", "database"],
        "测试": ["test", "testing", "e2e", "playwright"],
        "部署": ["deploy", "docker", "ci", "cd"],
        "文档": ["doc", "documentation", "readme", "markdown"],
        "数据": ["data", "analysis", "sql", "csv", "excel", "xlsx"],
        "图表": ["chart", "graph", "d3", "visualization"],
        "设计": ["design", "ui", "ux", "figma"],
        "浏览器": ["browser", "playwright", "selenium", "web"],
        "演示": ["presentation", "pptx", "slides"],
        "PDF": ["pdf", "extract", "merge"],
        "知识库": ["knowledge", "notebooklm", "obsidian"],
        "研究": ["research", "notebooklm", "knowledge"],
        "笔记": ["obsidian", "note", "markdown"],
        "GitHub": ["github", "pr", "issue", "repo"],
        "安全": ["security", "vulnerability", "audit"],
    }
    cn_keywords = []
    for cn, en_list in cn_map.items():
        if cn in query:
            cn_keywords.extend(en_list)

    return list(set(en_words + cn_keywords))


def match_score(entry: Dict, keywords: List[str], usage: Dict) -> float:
    """计算条目与查询的匹配分数。"""
    score = 0.0

    entry_keywords = set(k.lower() for k in entry.get("keywords", []))
    entry_triggers = set(t.lower() for t in entry.get("triggers", []))
    entry_name = entry.get("name", "").lower()
    entry_desc = entry.get("description", "").lower()

    for kw in keywords:
        kw_lower = kw.lower()
        # 精确匹配 trigger: +3
        if kw_lower in entry_triggers:
            score += 3.0
        # 精确匹配 keyword: +2
        if kw_lower in entry_keywords:
            score += 2.0
        # 名称包含: +2
        if kw_lower in entry_name:
            score += 2.0
        # 描述包含: +1
        if kw_lower in entry_desc:
            score += 1.0

    # 已安装加分 (优先推荐已有的)
    if entry.get("status") == "installed":
        score += 1.0
    elif entry.get("status") == "active":
        score += 1.5

    # 历史使用频率加分
    entry_id = entry.get("id", "")
    use_count = usage.get(entry_id, {}).get("count", 0)
    score += min(use_count * 0.1, 1.0)

    return score


def find_tools(query: str, top_k: int = 5) -> List[Dict]:
    """根据查询找到最匹配的工具/技能。"""
    entries = load_index()
    usage = load_usage()
    keywords = extract_keywords(query)

    if not keywords:
        return []

    scored = []
    for entry in entries:
        s = match_score(entry, keywords, usage)
        if s > 0:
            scored.append({**entry, "_score": s})

    scored.sort(key=lambda x: x["_score"], reverse=True)
    return scored[:top_k]
```

### 2.5 Gateway API 端点

```
GET  /api/tool-router/search?q=...      ← 搜索匹配的工具
POST /api/tool-router/rebuild-index     ← 重建索引
GET  /api/tool-router/stats             ← 索引统计
POST /api/tool-router/feedback          ← 使用反馈 (学习)
GET  /api/tool-router/index             ← 查看完整索引
```

### 2.6 SKILL.md (skill-router)

```yaml
---
name: skill-router
description: 智能工具路由 - 自动发现并推荐最匹配的 Skill、MCP Tool 或远程插件
triggers:
  - 找工具
  - find tool
  - 有没有
  - 怎么做
  - how to
  - 推荐
---
```

---

## 3. 集成: A + B 联动

### 3.1 知识驱动的工具推荐

当 skill-router 无法确定最佳工具时，查询共享知识库:

```python
async def enhanced_find_tools(query: str) -> List[Dict]:
    """增强版: 结合索引匹配 + 共享知识。"""
    # 1. 索引匹配
    candidates = find_tools(query, top_k=10)

    # 2. 查共享知识: "之前用什么工具做过类似的事?"
    knowledge = await query_shared_knowledge(
        f"tool recommendation for: {query}",
        category="tool-usage"
    )

    # 3. 如果共享知识有推荐，提升对应工具的分数
    for k in knowledge:
        for c in candidates:
            if c["name"] in k["content"]:
                c["_score"] += 2.0  # 历史经验加分

    candidates.sort(key=lambda x: x["_score"], reverse=True)
    return candidates[:5]
```

### 3.2 工具使用后自动发布知识

```python
async def after_tool_use(tool_id: str, task: str, success: bool):
    """工具使用后自动记录到共享知识。"""
    if success:
        await publish_knowledge(
            agent_id="claude",  # 或当前 agent
            category="tool-usage",
            topic=f"tool:{tool_id}",
            content=f"用 {tool_id} 成功完成: {task}",
        )
        # 更新使用统计
        update_usage_stats(tool_id, success=True)
```

### 3.3 跨 Agent 工具发现

```
Agent A (Kimi): "我需要做 PDF OCR"
  │
  ├── [1] skill-router 搜索 → 匹配 "pdf" skill + "mineru" (MinerU API)
  ├── [2] 查共享知识 → "Claude 之前用 pdf-to-notebook --method mineru 成功处理过扫描件"
  │
  └── 推荐: pdf-to-notebook --method mineru
      (附带历史使用经验)
```

---

## 4. 实现 Phase 划分

### Phase 1: 共享知识表 + 基础 API (2-3h)

**依赖**: v1.0 完成

| 任务 | 文件 | 行数 |
|------|------|------|
| 创建 shared_knowledge 等 4 张表 | `data/schema_v1.1.sql` | ~60 |
| 初始化 agents 表 (9 个 Provider) | migration script | ~30 |
| 实现 /api/shared-knowledge/* 6 个端点 | `gateway/routes/shared_knowledge.py` | ~300 |
| 注册到 app.py | `gateway/app.py` | +5 |

### Phase 2: 统一查询层 (2h)

| 任务 | 文件 | 行数 |
|------|------|------|
| 实现 unified_query() 并行搜索 | `knowledge/unified_query.py` | ~150 |
| 集成到 /api/shared-knowledge/query | routes | ~50 |
| 测试: 跨 Memory + NotebookLM + shared 查询 | `tests/` | ~100 |

### Phase 3: Skill/MCP 索引构建 (2h)

| 任务 | 文件 | 行数 |
|------|------|------|
| 创建 skill-router 目录 + SKILL.md | `~/.claude/skills/skill-router/` | ~50 |
| 实现 build-index.sh (4 源扫描) | `build-index.sh` | ~100 |
| 实现 router.py (匹配算法) | `router.py` | ~150 |
| 首次构建索引 | 运行 build-index.sh | - |

### Phase 4: Gateway 集成 (1-2h)

| 任务 | 文件 | 行数 |
|------|------|------|
| 实现 /api/tool-router/* 5 个端点 | `gateway/routes/tool_router.py` | ~200 |
| 使用反馈 + 统计 | usage-stats.json 读写 | ~50 |
| 注册到 app.py | `gateway/app.py` | +3 |

### Phase 5: A+B 联动 (1h)

| 任务 | 文件 | 行数 |
|------|------|------|
| enhanced_find_tools() 知识增强 | `router.py` | +30 |
| after_tool_use() 自动发布 | `router.py` | +20 |
| 集成测试 | `tests/` | ~80 |

### Phase 6: CLI 工具 (1h)

| 任务 | 文件 | 行数 |
|------|------|------|
| `ccb-knowledge` 加 shared 子命令 | `bin/ccb-knowledge` | +50 |
| `ccb-tools` 新 CLI (搜索/推荐) | `bin/ccb-tools` | ~80 |

---

## 5. 总工作量估算

| Phase | 内容 | 时间 | 新增代码 |
|-------|------|------|----------|
| Phase 1 | 共享知识表 + API | 2-3h | ~400 行 |
| Phase 2 | 统一查询层 | 2h | ~300 行 |
| Phase 3 | Skill/MCP 索引 | 2h | ~300 行 |
| Phase 4 | Gateway 集成 | 1-2h | ~250 行 |
| Phase 5 | A+B 联动 | 1h | ~130 行 |
| Phase 6 | CLI 工具 | 1h | ~130 行 |
| **Total** | | **~10h** | **~1,510 行** |

---

## 6. 验收标准

### 6.1 共享知识

- [ ] 9 个 Agent 已注册到 agents 表
- [ ] Agent 可通过 API 发布知识
- [ ] 统一查询可跨 Memory + NotebookLM + Obsidian + shared 返回结果
- [ ] 投票/共识机制工作
- [ ] 置信度随投票和时间动态变化

### 6.2 工具路由

- [ ] index.json 包含 68+ skills + 15+ MCP servers
- [ ] 关键词搜索准确率 > 80% (前 3 结果包含正确工具)
- [ ] 已安装工具优先于未安装
- [ ] 使用反馈影响后续推荐排序
- [ ] `ccb-tools search "PDF OCR"` 返回正确结果

### 6.3 联动

- [ ] 工具使用后自动记录到共享知识
- [ ] 共享知识中的历史经验影响工具推荐

---

## 7. 约束

1. **v1.0 必须先完成** — 本规格书依赖 v1.0 的 routes/ 拆分和统一数据库
2. **不改已有 API** — 只新增端点，不修改 /knowledge/* 和 /api/memory/*
3. **索引离线构建** — build-index.sh 可定时运行或手动触发，不在请求路径上
4. **MCP 运行时工具不索引** — 已活跃的 MCP tools 在运行时通过 ListMcpResourcesTool 获取，不存入静态索引
5. **渐进增强** — Phase 1-4 是核心，Phase 5-6 可推迟

---

## 8. 与 v1.0 优化规格书的关系

```
v0.26.0 (当前)
    │
    ▼ ── v1.0 优化 (Codex 执行中) ──
    │   Phase 1: common/ 基础设施
    │   Phase 2: gateway_api.py 拆分
    │   Phase 3: Provider 通信统一
    │   Phase 4: Backend 重构
    │   Phase 5: 数据库统一
    │   Phase 6: 测试补充
    │   Phase 7: 清理
    │
    ▼ ── v1.0.0 (测试通过) ──
    │
    ▼ ── v1.1 本规格书 ──
    │   Phase 1: 共享知识表
    │   Phase 2: 统一查询
    │   Phase 3: Skill/MCP 索引
    │   Phase 4: Gateway 集成
    │   Phase 5: A+B 联动
    │   Phase 6: CLI
    │
    ▼ ── v1.1.0 ──
```
