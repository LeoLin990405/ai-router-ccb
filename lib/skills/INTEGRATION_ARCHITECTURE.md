# CCB-FindSkills Integration Architecture

## 概览

本文档描述 CCB Gateway 与 find-skills 功能的集成架构，实现**任务驱动的技能发现和学习系统**。

## 核心目标

1. **自动发现** - 根据用户任务自动发现相关技能
2. **智能推荐** - 基于历史使用数据推荐最合适的技能
3. **记忆扩展** - 将技能使用记录存储到记忆系统
4. **持续学习** - 系统随使用不断优化推荐准确度

---

## 系统架构

### 组件图

```
┌─────────────────────────────────────────────────────────────────┐
│                    CCB Gateway (v0.18+)                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌────────────────────────────────────────────────────────┐    │
│  │       Memory Middleware (Enhanced v0.19)               │    │
│  ├────────────────────────────────────────────────────────┤    │
│  │  Pre-Request Hook:                                      │    │
│  │  1. Extract keywords                                    │    │
│  │  2. ✨ Skills Discovery.get_recommendations()          │    │
│  │  3. Memory search                                       │    │
│  │  4. Provider recommendation                             │    │
│  │  5. Context injection (+ skills recommendations)       │    │
│  │                                                          │    │
│  │  Post-Response Hook:                                    │    │
│  │  1. Record conversation                                 │    │
│  │  2. ✨ Skills Discovery.record_usage()                 │    │
│  │  3. Update statistics                                   │    │
│  └────────────────────────────────────────────────────────┘    │
│                          │                                       │
│  ┌────────────────────────▼─────────────────────────────┐      │
│  │       ✨ Skills Discovery Service (New)              │      │
│  ├───────────────────────────────────────────────────────┤      │
│  │  • scan_local_skills() → scan-skills.sh              │      │
│  │  • search_remote_skills() → find-skills API          │      │
│  │  • match_skills() → Keyword + History matching       │      │
│  │  • record_usage() → Update learning database         │      │
│  └───────────────────────────────────────────────────────┘      │
│                          │                                       │
│  ┌────────────────────────▼─────────────────────────────┐      │
│  │       Memory Backend (ccb_memory.db)                  │      │
│  ├───────────────────────────────────────────────────────┤      │
│  │  ✨ New Tables:                                       │      │
│  │  • skills_cache (name, description, triggers, ...)   │      │
│  │  • skills_usage (skill_name, keywords, success, ...) │      │
│  │                                                        │      │
│  │  Existing Tables:                                      │      │
│  │  • conversations (question, answer, ...)              │      │
│  │  • conversations_fts (full-text search)               │      │
│  └────────────────────────────────────────────────────────┘      │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

---

## 数据流程

### 1. 用户请求 → Skills Discovery

```
用户: "帮我创建一个 PDF"
    │
    ├─→ [Gateway] 接收请求
    │
    ├─→ [Memory Middleware: Pre-Request]
    │   │
    │   ├─→ 提取关键词: ["create", "PDF", "help"]
    │   │
    │   ├─→ [Skills Discovery Service]
    │   │   ├─→ match_skills("帮我创建一个 PDF")
    │   │   │   │
    │   │   │   ├─→ 1. 查询 skills_cache (缓存)
    │   │   │   │     WHERE skill_name LIKE '%pdf%'
    │   │   │   │     OR description LIKE '%pdf%'
    │   │   │   │     OR triggers LIKE '%pdf%'
    │   │   │   │
    │   │   │   ├─→ 2. 检查 skills_usage (历史)
    │   │   │   │     SELECT skill_name, COUNT(*)
    │   │   │   │     FROM skills_usage
    │   │   │   │     WHERE task_keywords LIKE '%pdf%'
    │   │   │   │     AND success = 1
    │   │   │   │
    │   │   │   └─→ 3. 计算相关性得分
    │   │   │         • 名称匹配: +10
    │   │   │         • 描述匹配: +5
    │   │   │         • 触发器匹配: +3
    │   │   │         • 已安装: +2
    │   │   │         • 历史使用: +5 (per keyword)
    │   │   │
    │   │   └─→ 返回 top 3 推荐:
    │   │       [
    │   │         {
    │   │           "name": "pdf",
    │   │           "description": "PDF manipulation toolkit",
    │   │           "relevance_score": 23,
    │   │           "installed": true,
    │   │           "usage_command": "/pdf"
    │   │         }
    │   │       ]
    │   │
    │   ├─→ 注入到上下文:
    │   │   """
    │   │   # 系统上下文
    │   │   ## 🛠️ 相关技能推荐
    │   │   - **/pdf** (score: 23) - PDF manipulation toolkit
    │   │     ✓ 已安装，可直接使用: `/pdf`
    │   │
    │   │   ## 💭 相关记忆
    │   │   ...
    │   │
    │   │   ---
    │   │   # 用户请求
    │   │   帮我创建一个 PDF
    │   │   """
    │   │
    │   └─→ 发送到 Provider
    │
    ├─→ [Provider] AI 看到推荐的技能，使用 /pdf
    │
    └─→ [Memory Middleware: Post-Response]
        │
        ├─→ 记录对话到 conversations
        │
        └─→ [Skills Discovery Service]
            └─→ record_usage(
                  skill_name="pdf",
                  task_keywords="create PDF help",
                  provider="kimi",
                  success=true
                )
                │
                └─→ INSERT INTO skills_usage
                    (skill_name, task_keywords, provider, success)
                    VALUES ('pdf', 'create PDF help', 'kimi', 1)
```

### 2. 自动学习循环

```
Time: T0 (首次使用)
  用户: "Create a PDF"
  → Skills Discovery: pdf (score: 15, no history)
  → AI 使用 /pdf
  → Record usage: success

Time: T1 (再次使用)
  用户: "Generate a PDF report"
  → Skills Discovery: pdf (score: 20, +5 from history)
  → AI 使用 /pdf
  → Record usage: success

Time: T2 (相似任务)
  用户: "Make a PDF invoice"
  → Skills Discovery: pdf (score: 25, +10 from history)
  → AI 自信使用 /pdf
  → Record usage: success

Result: 系统越用越聪明！
```

---

## 数据库架构

### skills_cache 表

```sql
CREATE TABLE skills_cache (
    skill_name TEXT PRIMARY KEY,        -- Skill 名称
    description TEXT,                   -- 描述
    triggers TEXT,                      -- JSON array 触发关键词
    source TEXT,                        -- 'local' | 'remote'
    installed INTEGER DEFAULT 0,        -- 是否已安装
    last_updated TEXT NOT NULL,         -- 最后更新时间
    metadata TEXT                       -- JSON 额外信息
);

-- Example:
INSERT INTO skills_cache VALUES (
    'pdf',
    'Comprehensive PDF manipulation toolkit',
    '["pdf", "document", "create", "merge", "split"]',
    'local',
    1,
    '2026-02-04T13:00:00',
    '{"version": "1.0", "author": "CCB Team"}'
);
```

### skills_usage 表

```sql
CREATE TABLE skills_usage (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    skill_name TEXT NOT NULL,           -- 使用的 skill
    task_keywords TEXT NOT NULL,        -- 任务关键词
    provider TEXT,                      -- 使用的 Provider
    timestamp TEXT NOT NULL,            -- 时间
    success INTEGER DEFAULT 1,          -- 是否成功
    FOREIGN KEY (skill_name) REFERENCES skills_cache(skill_name)
);

CREATE INDEX idx_skills_usage_keywords
ON skills_usage(task_keywords);

-- Example:
INSERT INTO skills_usage VALUES (
    1,
    'pdf',
    'create PDF document',
    'kimi',
    '2026-02-04T13:05:00',
    1
);
```

---

## API 接口

### CLI Commands

```bash
# 刷新技能缓存
ccb-skills scan

# 查找匹配的技能
ccb-skills match "create a PDF"

# 查看统计
ccb-skills stats

# 列出所有技能
ccb-skills list
ccb-skills list --installed

# 获取推荐
ccb-skills recommend "build a React component"
```

### Python API

```python
from lib.skills.skills_discovery import SkillsDiscoveryService

# 初始化
service = SkillsDiscoveryService()

# 刷新缓存
service._refresh_cache()

# 匹配技能
recommendations = service.get_recommendations("create a PDF")
# {
#   'found': True,
#   'skills': [{'name': 'pdf', 'relevance_score': 23, ...}],
#   'message': '💡 发现 1 个相关 Skill: /pdf'
# }

# 记录使用
service.record_usage(
    skill_name="pdf",
    task_keywords="create PDF",
    provider="kimi",
    success=True
)
```

---

## 配置

### gateway_config.json

```json
{
  "memory": {
    "enabled": true,
    "auto_inject": true,
    "auto_record": true,
    "max_injected_memories": 5,
    "inject_system_context": true,
    "injection_strategy": "recent_plus_relevant"
  },
  "skills": {
    "auto_discover": true,          // ✨ 自动发现技能
    "recommend_skills": true,       // ✨ 推荐技能给用户
    "max_recommendations": 3,       // ✨ 最多推荐数量
    "cache_ttl_hours": 24           // 缓存过期时间
  },
  "recommendation": {
    "enabled": true,
    "auto_switch_provider": false,
    "confidence_threshold": 0.7
  }
}
```

---

## 使用示例

### Example 1: 自动发现 PDF Skill

```bash
# 用户请求
$ ccb-cli kimi "帮我创建一个 PDF 报告"

# Gateway 日志输出
[MemoryMiddleware] Pre-request: provider=kimi, message_len=15
[MemoryMiddleware] Extracted keywords: ['帮', '创建', 'pdf', '报告']
[SkillsDiscovery] Searching for skills matching: ['帮', '创建', 'pdf', '报告']
[SkillsDiscovery] Found 1 matching skill: pdf (score: 18)
[MemoryMiddleware] 💡 发现 1 个相关 Skill: /pdf

# AI 响应
基于你的需求，我可以使用 /pdf skill 来帮你创建 PDF 报告...

# Gateway 后处理日志
[MemoryMiddleware] Conversation recorded: provider=kimi
[MemoryMiddleware] Recorded skill usage: ['pdf']
```

### Example 2: 查看技能统计

```bash
$ ccb-skills stats

📊 Skills Statistics

  Total skills in cache: 53
  Installed skills: 45
  Total usage records: 127

  Top 10 most used skills:
    - pdf: 23 uses
    - xlsx: 18 uses
    - pptx: 15 uses
    - frontend-design: 12 uses
    - sql2sh: 10 uses
    ...
```

### Example 3: 手动查找技能

```bash
$ ccb-skills recommend "build a React dashboard"

💡 Analyzing task: build a React dashboard

✓ 发现 3 个相关 Skill: frontend-design, webapp-testing, canvas-design

1. frontend-design (Relevance: 25)
   Create distinctive, production-grade frontend interfaces
   ✓ Installed - Use: /frontend-design

2. webapp-testing (Relevance: 12)
   Toolkit for testing local web applications
   ✓ Installed - Use: /webapp-testing

3. canvas-design (Relevance: 8)
   Create beautiful visual art in .png and .pdf
   ✓ Installed - Use: /canvas-design
```

---

## 优势

### 1. **零配置记忆**
用户无需手动记录使用了哪些 skills，系统自动学习。

### 2. **智能推荐**
基于关键词 + 历史使用的混合算法，推荐越来越准确。

### 3. **完全透明**
所有推荐都有分数和理由，用户可查看统计数据。

### 4. **可扩展**
- 未来可接入远程 find-skills API
- 可添加向量搜索提高语义匹配
- 可支持技能依赖关系

---

## 未来增强

### v0.20 (Q3 2026)

- [ ] **向量搜索** - 使用 Qdrant 做语义匹配
- [ ] **远程 Skills Registry** - 连接中心化 skills 库
- [ ] **自动安装** - 发现未安装的 skill 时自动安装
- [ ] **Skills 依赖图** - 管理 skill 之间的依赖关系

### v0.21 (Q4 2026)

- [ ] **个性化推荐** - 每个用户独立的使用偏好
- [ ] **A/B 测试** - 测试不同推荐算法效果
- [ ] **Skills 市场** - 社区共享和评分系统

---

## 总结

CCB-FindSkills 集成实现了一个**自学习的技能推荐系统**：

1. **任务驱动** - 根据用户任务自动发现相关技能
2. **持续学习** - 使用越多，推荐越准确
3. **记忆扩展** - 技能使用记录融入记忆系统
4. **完全透明** - 用户可查看推荐理由和统计

这是 CCB Gateway v0.19 的核心功能之一！

---

**作者**: CCB Team
**版本**: 0.19-alpha
**日期**: 2026-02-04
