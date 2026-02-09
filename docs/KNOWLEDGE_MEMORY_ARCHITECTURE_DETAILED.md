# CCB 知识库 + 记忆库 详细架构文档

**文档版本**: 2.0
**更新日期**: 2026-02-08
**状态**: 当前实现 (v1.0)

---

## 目录

1. [系统总览](#1-系统总览)
2. [三大数据库架构](#2-三大数据库架构)
3. [记忆系统 (Memory System)](#3-记忆系统-memory-system)
4. [知识系统 (Knowledge System)](#4-知识系统-knowledge-system)
5. [Ollama 集成详解](#5-ollama-集成详解)
6. [Gateway 记忆中间件 (Memory Middleware)](#6-gateway-记忆中间件)
7. [完整请求生命周期](#7-完整请求生命周期)
8. [当前限制与差距](#8-当前限制与差距)

---

## 1. 系统总览

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              CCB Gateway (:8765)                                │
│                                                                                 │
│  ┌───────────────────────────────────────────────────────────────────────────┐  │
│  │                        Memory Middleware (v2.0)                           │  │
│  │                                                                           │  │
│  │  Pre-Request:                        Post-Response:                       │  │
│  │  ┌──────────────┐                    ┌──────────────┐                     │  │
│  │  │ 1. Ollama    │                    │ 1. 记录对话  │                     │  │
│  │  │    关键词提取 │                    │ 2. 更新统计  │                     │  │
│  │  │ 2. FTS5 检索 │                    │ 3. 记录注入  │                     │  │
│  │  │ 3. αR+βI+γT  │                    │    追踪信息  │                     │  │
│  │  │    评分排序   │                    └──────────────┘                     │  │
│  │  │ 4. 注入上下文│                                                         │  │
│  │  └──────────────┘                                                         │  │
│  └───────────────────────────────────────────────────────────────────────────┘  │
│                                                                                 │
│       │                    │                     │                               │
│       ▼                    ▼                     ▼                               │
│  ┌─────────┐        ┌──────────┐          ┌──────────┐                          │
│  │ Memory  │        │Knowledge │          │ Gateway  │                          │
│  │ System  │        │ System   │          │ Core     │                          │
│  │         │        │          │          │          │                          │
│  │ ~/.ccb/ │        │ data/    │          │ ~/.ccb_  │                          │
│  │ ccb_    │        │knowledge_│          │ config/  │                          │
│  │ memory  │        │index.db  │          │ gateway  │                          │
│  │ .db     │        │          │          │ .db      │                          │
│  └─────────┘        └──────────┘          └──────────┘                          │
│                          │                                                      │
│              ┌───────────┴───────────┐                                          │
│              ▼                       ▼                                          │
│        ┌──────────┐          ┌──────────┐                                      │
│        │NotebookLM│          │ Obsidian │                                      │
│        │(254+ NB) │          │(本地 MD) │                                      │
│        │ 云端 API │          │~/Desktop/│                                      │
│        │          │          │新笔记    │                                      │
│        └──────────┘          └──────────┘                                      │
└─────────────────────────────────────────────────────────────────────────────────┘
```

**三大系统完全隔离**：各自有独立 SQLite 数据库，无跨库查询。

---

## 2. 三大数据库架构

### 2.1 记忆数据库 `~/.ccb/ccb_memory.db`

**用途**: 存储所有 AI 对话历史、观察笔记、重要性评分、访问日志

| 表名 | 行数级别 | 用途 |
|------|----------|------|
| `sessions` | ~100s | 会话管理 |
| `messages` | ~10K+ | 对话记录 (user/assistant) |
| `messages_fts` | (FTS5 虚拟表) | 全文搜索索引 (Porter 词干) |
| `observations` | ~100s | 人工/LLM 提取的知识点 |
| `observations_fts` | (FTS5 虚拟表) | 观察全文搜索 |
| `memory_importance` | ~10K+ | 重要性评分 + 访问计数 |
| `memory_access_log` | ~10K+ | 每次检索的详细日志 |
| `context_injections` | ~1K+ | 注入追踪 (透明度) |
| `request_memory_map` | ~1K+ | 请求→注入映射 |
| `stream_entries` | ~10K+ | 思考链 + 流式内容 |
| `consolidation_log` | ~100s | System 2 整合日志 |
| `archived_sessions` | ~10s | gzip 压缩归档 |

### 2.2 知识数据库 `data/knowledge_index.db`

**用途**: NotebookLM notebooks 本地索引 + 查询缓存

| 表名 | 行数级别 | 用途 |
|------|----------|------|
| `notebooks` | 254+ | NotebookLM notebooks 元数据 |
| `query_cache` | ~1K+ | 查询结果缓存 (TTL 24h) |

### 2.3 网关数据库 `~/.ccb_config/gateway.db`

**用途**: 请求队列、Provider 状态、监控指标

| 表名 | 行数级别 | 用途 |
|------|----------|------|
| `requests` | ~10K+ | 异步请求队列 |
| `responses` | ~10K+ | 响应存储 |
| `provider_status` | 9 | Provider 健康状态 |
| `metrics` | ~10K+ | 性能指标 |
| `discussion_sessions` | ~100s | 多 AI 讨论会话 |
| `discussion_messages` | ~1K+ | 讨论消息 |

---

## 3. 记忆系统 (Memory System)

### 3.1 架构层次

```
┌────────────────────────────────────────────────────────────────┐
│                     CCBMemoryV2 (主接口)                        │
│                  lib/memory/memory_v2.py                        │
│                                                                 │
│  方法: record_message(), search_messages(),                     │
│        create_observation(), search_with_scores(),              │
│        track_request_injection(), archive_session()             │
├────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────────────┐    ┌──────────────────────────┐       │
│  │  HeuristicRetriever │    │     VectorSearch         │       │
│  │  (System 1: 快速)   │    │    (System 2: 深度)      │       │
│  │                     │    │                          │       │
│  │  • FTS5 全文搜索    │    │  • sentence-transformers │       │
│  │  • BM25 评分        │    │  • all-MiniLM-L6-v2     │       │
│  │  • αR+βI+γT 公式   │    │  • 384 维向量           │       │
│  │  • Ebbinghaus 遗忘  │    │  • Cosine 相似度        │       │
│  │  • 访问追踪         │    │  • 混合检索             │       │
│  │                     │    │                          │       │
│  │  延迟: <50ms        │    │  延迟: 100-500ms        │       │
│  └─────────────────────┘    └──────────────────────────┘       │
│            │                            │                       │
│            │         ┌──────────────────┘                       │
│            ▼         ▼                                          │
│  ┌─────────────────────────┐                                   │
│  │    SQLite (ccb_memory.db)│                                   │
│  │    • messages + FTS5     │                                   │
│  │    • observations + FTS5 │                                   │
│  │    • memory_importance   │                                   │
│  │    • memory_access_log   │                                   │
│  └─────────────────────────┘                                   │
│                                                                 │
│  ┌─────────────────────────┐                                   │
│  │ Vector Backend (可选)    │                                   │
│  │  ┌───────┐ ┌────────┐  │                                   │
│  │  │Qdrant │ │ChromaDB│  │                                   │
│  │  │:6333  │ │ 本地   │  │                                   │
│  │  └───────┘ └────────┘  │                                   │
│  │  ┌──────────────────┐  │                                   │
│  │  │  InMemory (默认) │  │                                   │
│  │  └──────────────────┘  │                                   │
│  └─────────────────────────┘                                   │
└────────────────────────────────────────────────────────────────┘
```

### 3.2 启发式检索器 (HeuristicRetriever) — 核心算法

**灵感来源**: Stanford "Generative Agents" 论文 (Park et al., 2023)

#### 评分公式

```
final_score = α × R + β × I + γ × T

其中:
  α = 0.4  (相关性权重)
  β = 0.3  (重要性权重)
  γ = 0.3  (时效性权重)
```

#### R: 相关性分数 (Relevance)

**来源**: SQLite FTS5 全文搜索 + BM25 算法

```sql
-- 消息搜索
SELECT m.message_id, m.content, m.provider, m.timestamp,
       bm25(messages_fts) as fts_rank
FROM messages m
JOIN messages_fts fts ON m.rowid = fts.rowid
WHERE messages_fts MATCH ?
ORDER BY fts_rank
LIMIT 50
```

**BM25 归一化** (原始值为负数，越小越相关):
```python
relevance = min(1.0, max(0.0, (25 + fts_rank) / 25))

# 举例:
#   fts_rank = -20  → relevance = (25-20)/25 = 0.20  (高相关)
#   fts_rank = -5   → relevance = (25-5)/25 = 0.80   (极高相关)
#   fts_rank = 0    → relevance = 25/25 = 1.0
#   无匹配          → relevance = 0.5 (默认)
```

#### I: 重要性分数 (Importance)

**来源**: `memory_importance` 表

```
默认值: 0.5 (新记忆)
来源标记:
  - 'user':      用户手动标记 (set_importance)
  - 'llm':       LLM 评估的重要性
  - 'heuristic': 系统自动计算

每次被检索命中: +0.01 (access_boost)
上限: 1.0
```

#### T: 时效性分数 (Recency)

**Ebbinghaus 遗忘曲线**:

```python
T = exp(-λ × hours_since_last_access)

其中 λ = 0.1 (衰减率)

时间衰减示例:
  0 小时前访问  → T = exp(0)     = 1.000 (完全新鲜)
  1 小时前     → T = exp(-0.1)  = 0.905
  5 小时前     → T = exp(-0.5)  = 0.607
  10 小时前    → T = exp(-1.0)  = 0.368
  24 小时前    → T = exp(-2.4)  = 0.091
  48 小时前    → T = exp(-4.8)  = 0.008
  168 小时(1周) → T = exp(-16.8) ≈ 0.000 → 被截断为 min_recency = 0.01

从未访问过   → 默认 168 小时 → T ≈ 0.01
```

#### 完整检索流程

```
输入: query = "React hooks 最佳实践"

Step 1: FTS5 搜索 messages (候选池 50 条)
  → "我之前问过 React useEffect 清理函数" (fts_rank=-8)
  → "React 组件生命周期讨论" (fts_rank=-12)
  → ... (共 50 条)

Step 2: FTS5 搜索 observations (候选池 50 条)
  → "React 18 新特性总结" (fts_rank=-6)
  → ... (共 50 条)

Step 3: 对每条候选评分
  消息 #1: R=0.68, I=0.5(默认), T=0.37(10h前)
           final = 0.4×0.68 + 0.3×0.5 + 0.3×0.37 = 0.533

  消息 #2: R=0.52, I=0.7(被多次检索), T=0.91(1h前)
           final = 0.4×0.52 + 0.3×0.7 + 0.3×0.91 = 0.691

  观察 #1: R=0.76, I=0.6, T=0.09(24h前)
           final = 0.4×0.76 + 0.3×0.6 + 0.3×0.09 = 0.511

Step 4: 按 final_score 降序排序
  → 消息 #2 (0.691) > 消息 #1 (0.533) > 观察 #1 (0.511)

Step 5: 取 top 5

Step 6: 记录访问日志 + 更新 access_count
```

### 3.3 向量搜索系统 (VectorSearch) — 深度语义

#### 嵌入模型

```python
模型: sentence-transformers/all-MiniLM-L6-v2
维度: 384
类型: BERT 变体 (110M 参数)
加载: 单例模式 (首次加载 ~2s, 之后复用)
```

#### 后端选择

| 后端 | 适用场景 | 持久化 | 性能 |
|------|----------|--------|------|
| **Qdrant** (`:6333`) | 生产环境 | 磁盘 | 100K+ 向量, <10ms |
| **ChromaDB** | 开发环境 | `~/.ccb/chroma/` | 10K 向量, <50ms |
| **InMemory** (默认) | 轻量测试 | 无 | 1K 向量, <5ms |

#### 混合检索

```python
VectorConfig:
  vector_weight: 0.5   # 向量相似度权重
  bm25_weight:   0.5   # BM25 文本匹配权重

混合分数 = 0.5 × cosine_similarity + 0.5 × bm25_score
```

#### 数据同步

```python
sync_from_database(db_path="~/.ccb/ccb_memory.db"):
  1. 读取 messages 表 → 生成 embedding → 写入向量后端
  2. 读取 observations 表 → 生成 embedding → 写入向量后端
  3. 批量处理: batch_size=100
```

### 3.4 数据库 Schema 详解

#### messages 表

```sql
CREATE TABLE messages (
    message_id    TEXT PRIMARY KEY,        -- UUID
    session_id    TEXT REFERENCES sessions, -- 所属会话
    request_id    TEXT,                     -- Gateway 请求 ID
    sequence      INTEGER,                 -- 会话内顺序
    role          TEXT,                     -- 'user' | 'assistant' | 'system'
    content       TEXT,                     -- 完整消息内容
    provider      TEXT,                     -- 'kimi' | 'qwen' | 'codex' | ...
    model         TEXT,                     -- 具体模型名
    timestamp     TEXT,                     -- ISO 8601
    latency_ms    INTEGER,                 -- 响应延迟
    tokens        INTEGER,                 -- Token 数
    context_injected  INTEGER DEFAULT 0,   -- 是否注入了上下文 (0/1)
    context_count     INTEGER DEFAULT 0,   -- 注入的记忆条数
    skills_used   TEXT,                     -- JSON 数组: ["skill1", "skill2"]
    metadata      TEXT,                     -- JSON 自由字段
    importance_score  REAL DEFAULT 0.5,    -- 重要性 (0-1)
    last_accessed_at  TEXT,                -- 最近被检索时间
    access_count      INTEGER DEFAULT 0    -- 被检索次数
);

CREATE VIRTUAL TABLE messages_fts USING fts5(
    content, provider,
    tokenize='porter'    -- Porter 词干提取
);
```

#### observations 表

```sql
CREATE TABLE observations (
    observation_id    TEXT PRIMARY KEY,     -- UUID
    user_id           TEXT,                 -- 所属用户
    category          TEXT,                 -- 'insight' | 'preference' | 'fact' | 'note' | 'discussion'
    content           TEXT,                 -- 观察内容
    tags              TEXT,                 -- JSON 数组: ["react", "frontend"]
    source            TEXT,                 -- 'manual' | 'llm_extracted' | 'consolidator' | 'discussion'
    confidence        REAL,                 -- 置信度 (0-1)
    created_at        TEXT,                 -- ISO 8601
    updated_at        TEXT,
    metadata          TEXT,                 -- JSON
    importance_score  REAL DEFAULT 0.5,
    last_accessed_at  TEXT,
    access_count      INTEGER DEFAULT 0,
    decay_rate        REAL DEFAULT 0.05     -- 自定义衰减率
);

CREATE VIRTUAL TABLE observations_fts USING fts5(
    content, category, tags,
    tokenize='porter'
);
```

#### memory_importance 表

```sql
CREATE TABLE memory_importance (
    memory_id         TEXT PRIMARY KEY,
    memory_type       TEXT,                -- 'message' | 'observation'
    importance_score  REAL DEFAULT 0.5,    -- 当前重要性
    access_count      INTEGER DEFAULT 0,   -- 总访问次数
    last_accessed_at  TEXT,                -- 最近访问时间
    decay_rate        REAL DEFAULT 0.05,   -- 个体衰减率
    score_source      TEXT,                -- 'user' | 'llm' | 'heuristic' | 'forget'
    created_at        TEXT,
    updated_at        TEXT
);
```

#### memory_access_log 表

```sql
CREATE TABLE memory_access_log (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    memory_id        TEXT,
    memory_type      TEXT,
    accessed_at      TEXT,                -- ISO 8601
    access_context   TEXT,                -- 'retrieval' | 'injection' | 'user_view' | 'search'
    request_id       TEXT,                -- 关联的 Gateway 请求
    query_text       TEXT,                -- 触发检索的查询 (前 500 字符)
    relevance_score  REAL                 -- 该次检索的相关性分数
);
```

---

## 4. 知识系统 (Knowledge System)

### 4.1 架构层次

```
┌────────────────────────────────────────────────────────────────┐
│                    KnowledgeRouter (路由层)                      │
│                  lib/knowledge/router.py                        │
│                                                                 │
│  统一查询接口: query(question, source="auto")                    │
│  路由决策: auto → NotebookLM 或 Obsidian                        │
│  查询缓存: MD5(question:source:notebook_id) → 24h TTL           │
├────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────────────┐  ┌──────────────────────┐            │
│  │   NotebookLMClient   │  │   ObsidianSearch     │            │
│  │                      │  │                      │            │
│  │  • CLI: notebooklm   │  │  • Vault 路径:       │            │
│  │  • 254+ notebooks    │  │    ~/Desktop/新笔记   │            │
│  │  • AI 问答 + 播客    │  │  • Markdown 文件搜索  │            │
│  │  • 来源管理          │  │  • 排除: .obsidian,  │            │
│  │                      │  │    .trash, templates │            │
│  └──────────────────────┘  └──────────────────────┘            │
│                                                                 │
│  ┌──────────────────────────────────────────────────┐          │
│  │             IndexManager (SQLite)                 │          │
│  │         data/knowledge_index.db                   │          │
│  │                                                   │          │
│  │  notebooks: id, title, description, topics,       │          │
│  │             source_count, query_count             │          │
│  │                                                   │          │
│  │  query_cache: query_hash, answer, references,     │          │
│  │               ttl=86400                           │          │
│  └──────────────────────────────────────────────────┘          │
└────────────────────────────────────────────────────────────────┘
```

### 4.2 路由决策逻辑

```python
def query(question, source="auto", notebook_id=None, use_cache=True):
    """
    路由优先级:

    1. 检查缓存 (如果 use_cache=True)
       cache_key = MD5(question + ":" + source + ":" + notebook_id)
       → 命中且未过期 → 直接返回 (cached=True)

    2. source="notebooklm" → 直接查 NotebookLM
    3. source="obsidian"   → 直接查 Obsidian
    4. source="auto"       → _auto_route()

    5. 结果写入缓存
    """

def _auto_route(question, notebook_id=None):
    """
    自动路由:

    1. 如果指定了 notebook_id → NotebookLM

    2. 如果 local_first=True:
       a. 先查 Obsidian
       b. 如果 confidence >= 0.7 → 返回 Obsidian 结果
       c. 否则 → 降级到 NotebookLM

    3. 如果 NotebookLM 可用:
       a. IndexManager.find_best_notebook(question)
       b. 用关键词评分找最匹配的 notebook
       c. 查询该 notebook

    4. 全部失败 → 返回 {source: "none", error: "..."}
    """
```

### 4.3 Notebook 关键词匹配算法

```python
def find_best_notebook(question):
    """
    评分规则:
      title 匹配    → +3 分
      description 匹配 → +2 分
      topics 匹配    → +1 分

    对 question 的每个词检查是否出现在 notebook 的 title/description/topics 中
    返回总分最高的 notebook
    """

def find_notebooks_by_keyword(query, limit=10):
    """
    SQL:
    SELECT id, title, description, topics
    FROM notebooks
    WHERE title LIKE '%keyword%'
       OR description LIKE '%keyword%'
       OR topics LIKE '%keyword%'
    """
```

### 4.4 知识数据库 Schema

```sql
-- notebooks: NotebookLM 索引
CREATE TABLE notebooks (
    id           TEXT PRIMARY KEY,          -- NotebookLM notebook ID
    title        TEXT NOT NULL,             -- 标题
    description  TEXT,                      -- 描述
    topics       TEXT,                      -- JSON 数组: ["react", "frontend"]
    source_count INTEGER DEFAULT 0,         -- 来源数量
    created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_queried TIMESTAMP,                 -- 最近查询时间
    query_count  INTEGER DEFAULT 0          -- 查询次数
);

-- query_cache: 查询结果缓存
CREATE TABLE query_cache (
    query_hash      TEXT PRIMARY KEY,       -- MD5(question:source:notebook_id)
    source          TEXT,                   -- 'notebooklm' | 'obsidian'
    question        TEXT,                   -- 原始问题
    answer          TEXT,                   -- 回答内容
    references_json TEXT,                   -- JSON: 参考来源列表
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ttl             INTEGER DEFAULT 86400   -- 秒 (24 小时)
);
```

### 4.5 查询返回格式

```python
{
    "answer": "React hooks 是...",           # 回答内容
    "source": "notebooklm",                  # 来源: auto|notebooklm|obsidian|none
    "references": [                          # 参考列表
        {"title": "React 笔记", "path": "..."}
    ],
    "confidence": 0.85,                      # 置信度 (0-1)
    "cached": False,                         # 是否缓存命中
    "error": None,                           # 错误信息
    "notebook_id": "abc123"                  # NotebookLM notebook ID
}
```

---

## 5. Ollama 集成详解

### 5.1 使用位置

Ollama **仅**在一个地方被使用：`MemoryMiddleware._extract_keywords_with_llm()`

**用途**: 在记忆检索前，从用户问题中提取 2-3 个核心关键词，用于 FTS5 全文搜索。

### 5.2 模型路由策略

```
用户消息
  │
  ▼
┌─────────────────────────────────────────┐
│ _extract_keywords_with_llm(text)        │
│                                          │
│  尝试 1: qwen2.5:7b (本地)              │
│  ├── Ollama API: localhost:11434         │
│  ├── 超时: 6 秒                          │
│  ├── 热启动延迟: ~0.5 秒                 │
│  ├── 冷启动延迟: ~5 秒                   │
│  ├── 模型大小: 7.6GB                     │
│  │                                       │
│  ├── 成功 → 返回关键词                    │
│  ├── ConnectionError → Ollama 未运行     │
│  │   └── 直接跳到 regex 降级              │
│  └── Timeout → 尝试下一个模型             │
│                                          │
│  尝试 2: deepseek-v3.1:671b-cloud (云端) │
│  ├── Ollama API: localhost:11434         │
│  │   (通过 Ollama 云端代理)               │
│  ├── 超时: 10 秒                         │
│  ├── 延迟: 1.5-3 秒                      │
│  ├── 模型大小: 671B 参数 (云端)           │
│  │                                       │
│  ├── 成功 → 返回关键词                    │
│  └── 失败 → regex 降级                   │
│                                          │
│  降级 3: _extract_keywords_regex()       │
│  ├── 无 LLM 依赖                         │
│  ├── 延迟: <10ms                         │
│  ├── 中文: 提取 3-4 字词 [\u4e00-\u9fff] │
│  ├── 英文: 提取 3+ 字母单词               │
│  ├── 过滤停用词                           │
│  └── 返回 top 5 关键词                    │
└─────────────────────────────────────────┘
```

### 5.3 Ollama API 调用详情

```python
# 请求
POST http://localhost:11434/api/generate
Content-Type: application/json

{
    "model": "qwen2.5:7b",           # 或 "deepseek-v3.1:671b-cloud"
    "prompt": "从下面的问题中提取2-3个最核心的关键词（名词或名词短语），用逗号分隔。\n只返回关键词，不要其他解释。\n\n问题：如何使用 React hooks 管理状态？\n\n关键词：",
    "stream": false,
    "options": {
        "temperature": 0.3,           # 低温度 = 更确定性
        "num_predict": 50             # 最多生成 50 tokens
    }
}

# 响应
{
    "model": "qwen2.5:7b",
    "response": "React hooks, 状态管理, useState",
    "done": true
}

# 后处理
keywords = "React hooks, 状态管理, useState"
         → split(",")
         → strip()
         → ["React hooks", "状态管理", "useState"]
```

### 5.4 Regex 降级逻辑

```python
def _extract_keywords_regex(text):
    # 1. 提取中文词 (3-4 字)
    chinese = re.findall(r'[\u4e00-\u9fff]{3,4}', text)

    # 2. 提取英文词 (3+ 字母)
    english = re.findall(r'[a-zA-Z]{3,}', text)

    # 3. 合并去重
    all_keywords = list(dict.fromkeys(chinese + english))

    # 4. 过滤停用词
    stopwords = {'the', 'and', 'for', 'that', 'this', ...}
    filtered = [w for w in all_keywords if w.lower() not in stopwords]

    # 5. 返回 top 5
    return filtered[:5]

    # 6. 如果为空且原文 ≤10 字符 → 返回原文
```

### 5.5 日志示例

```
[MemoryMiddleware] LLM extracted (local:qwen2.5:7b): ['React hooks', '状态管理']
[MemoryMiddleware] LLM extracted (cloud:deepseek-v3.1): ['React', 'hooks', '状态管理']
[MemoryMiddleware] LLM extraction failed, using regex: ['React', 'hooks']
```

---

## 6. Gateway 记忆中间件

### 6.1 中间件配置

```python
MemoryMiddleware 默认配置:
{
    "memory": {
        "enabled": True,
        "auto_inject": True,                    # 自动注入记忆到 prompt
        "auto_record": True,                    # 自动记录对话
        "max_injected_memories": 5,             # 最多注入 5 条记忆
        "inject_system_context": True,          # 注入系统上下文
        "injection_strategy": "recent_plus_relevant",  # 检索策略
        "use_heuristic_retrieval": True         # 使用启发式检索 (v2.0)
    },
    "skills": {
        "auto_discover": True,                  # 自动发现相关 skills
        "recommend_skills": True,               # 推荐 skills
        "max_recommendations": 3                # 最多推荐 3 个
    },
    "recommendation": {
        "enabled": True,
        "auto_switch_provider": False,          # 不自动切换 Provider
        "confidence_threshold": 0.7             # 推荐置信度阈值
    }
}
```

### 6.2 Pre-Request 完整流程

```
用户发送请求: "帮我优化这个 React 组件"
  │
  ▼
[1] 提取关键词 (_extract_keywords)
  │  Ollama qwen2.5:7b → ["React", "组件", "优化"]
  │
  ▼
[2] 启发式记忆检索 (HeuristicRetriever.retrieve)
  │  FTS5 搜索 "React 组件 优化"
  │  → 候选池: 50 messages + 50 observations
  │  → αR+βI+γT 评分
  │  → Top 5 结果:
  │    #1: "上次讨论的 React 性能优化" (score: 0.72)
  │    #2: "React memo 使用建议" (score: 0.65)
  │    #3: "组件拆分最佳实践" (score: 0.58)
  │
  ▼
[3] Skills 发现 (SkillsDiscoveryService)
  │  关键词匹配已安装 skills
  │  → 推荐: /frontend (score: 0.85)
  │
  ▼
[4] 系统上下文构建 (SystemContextBuilder)
  │  当前 Provider 信息 + Agent 角色
  │
  ▼
[5] 注入上下文到 prompt
  │
  │  修改后的 message:
  │  ┌──────────────────────────────────────────┐
  │  │ # 系统上下文                              │
  │  │                                           │
  │  │ ## 💭 相关记忆                             │
  │  │ 1. [kimi] (score: 0.72) React 性能优化... │
  │  │    A: 使用 React.memo 和 useMemo...       │
  │  │ 2. [qwen] (score: 0.65) memo 建议...     │
  │  │    A: 只在 props 变化频繁时使用...         │
  │  │                                           │
  │  │ ## 🛠️ 相关技能推荐                         │
  │  │ - /frontend (score: 0.85) - 前端开发      │
  │  │   ✓ 已安装                                │
  │  │                                           │
  │  │ ---                                       │
  │  │                                           │
  │  │ # 用户请求                                │
  │  │ 帮我优化这个 React 组件                    │
  │  └──────────────────────────────────────────┘
  │
  ▼
[6] 标记注入元数据
  │  request._memory_injected = True
  │  request._memory_count = 3
  │  request._skills_recommended = True
  │
  ▼
[7] 请求发送到 Provider (Kimi/Qwen/...)
```

### 6.3 Post-Response 完整流程

```
Provider 返回响应
  │
  ▼
[1] 记录对话 (CCBMemoryV2.record_conversation)
  │  INSERT INTO messages (user_msg)
  │  INSERT INTO messages (assistant_msg)
  │  同步到 FTS5 索引
  │
  ▼
[2] 记录注入追踪 (track_request_injection)
  │  INSERT INTO request_memory_map:
  │    request_id, provider, original_message,
  │    injected_memory_ids: ["mem1", "mem2", "mem3"],
  │    injected_skills: ["frontend"],
  │    relevance_scores: {"mem1": 0.72, "mem2": 0.65, "mem3": 0.58}
  │
  ▼
[3] 更新记忆访问日志
  │  INSERT INTO memory_access_log:
  │    被检索到的每条记忆 → 记录 accessed_at, query_text, relevance_score
  │
  ▼
[4] 更新重要性 (被检索 = 有价值)
     UPDATE memory_importance SET access_count += 1
```

---

## 7. 完整请求生命周期

```
┌────────┐     ┌─────────┐     ┌──────────────┐     ┌──────────┐     ┌────────┐
│ 用户   │     │ Gateway │     │   Memory     │     │ Ollama   │     │Provider│
│        │     │ API     │     │  Middleware   │     │ (本地)   │     │(AI)    │
└───┬────┘     └────┬────┘     └──────┬───────┘     └────┬─────┘     └───┬────┘
    │               │                  │                   │              │
    │ ccb-cli kimi  │                  │                   │              │
    │ "React优化"   │                  │                   │              │
    │──────────────►│                  │                   │              │
    │               │                  │                   │              │
    │               │ pre_request()    │                   │              │
    │               │─────────────────►│                   │              │
    │               │                  │                   │              │
    │               │                  │ 提取关键词         │              │
    │               │                  │──────────────────►│              │
    │               │                  │                   │              │
    │               │                  │ ["React","优化"]   │              │
    │               │                  │◄──────────────────│              │
    │               │                  │                   │              │
    │               │                  │ FTS5 搜索          │              │
    │               │                  │ (ccb_memory.db)   │              │
    │               │                  │ αR+βI+γT 评分     │              │
    │               │                  │                   │              │
    │               │                  │ 注入上下文到 prompt │              │
    │               │                  │                   │              │
    │               │ 修改后的 request  │                   │              │
    │               │◄─────────────────│                   │              │
    │               │                  │                   │              │
    │               │ 发送到 Provider   │                   │              │
    │               │─────────────────────────────────────────────────────►│
    │               │                  │                   │              │
    │               │ AI 响应           │                   │              │
    │               │◄─────────────────────────────────────────────────────│
    │               │                  │                   │              │
    │               │ post_response()  │                   │              │
    │               │─────────────────►│                   │              │
    │               │                  │                   │              │
    │               │                  │ 记录到 messages    │              │
    │               │                  │ 记录注入追踪       │              │
    │               │                  │ 更新访问日志       │              │
    │               │                  │                   │              │
    │               │◄─────────────────│                   │              │
    │               │                  │                   │              │
    │ 返回响应       │                  │                   │              │
    │◄──────────────│                  │                   │              │
    │               │                  │                   │              │
```

### 时间线 (典型快速路径)

| 阶段 | 耗时 | 累计 |
|------|------|------|
| 接收请求 | ~1ms | 1ms |
| Ollama 关键词提取 (热) | ~500ms | ~500ms |
| FTS5 搜索 + 评分 | ~30ms | ~530ms |
| 上下文格式化 + 注入 | ~5ms | ~535ms |
| Provider 响应 (Kimi) | ~5,000ms | ~5,535ms |
| 记录对话 + 日志 | ~20ms | ~5,555ms |
| **总计** | **~5.5s** | |

---

## 8. 当前限制与差距

### 8.1 系统隔离问题

| 问题 | 说明 | v1.1 计划 |
|------|------|-----------|
| **三库隔离** | Memory/Knowledge/Gateway 无法跨库查询 | 统一查询层 |
| **无 agent_id** | 记忆无法区分不同 Agent 的贡献 | 添加 agent_id 字段 |
| **Knowledge 不可搜记忆** | KnowledgeRouter 不查 Memory | 联合查询 |
| **Memory 不知 Knowledge** | HeuristicRetriever 不查 NotebookLM | 联合查询 |

### 8.2 记忆系统限制

| 限制 | 影响 | 解决方向 |
|------|------|----------|
| FTS5 Porter 分词 | 中文分词质量一般 | 考虑 jieba 分词 |
| 向量搜索未默认启用 | 仅 FTS5 可用 | 部署 Qdrant 或 Chroma |
| Ollama 必须运行 | 关键词提取依赖 | regex 降级已实现 |
| 无跨 Agent 共享 | 每个 Agent 独立 | v1.1 shared_knowledge 表 |

### 8.3 知识系统限制

| 限制 | 影响 | 解决方向 |
|------|------|----------|
| 关键词匹配简单 | title/description LIKE 匹配 | 语义向量匹配 |
| 缓存 TTL 固定 24h | 无法按需调整 | 分类 TTL 策略 |
| NotebookLM 限流 | 高频查询被拒 | 缓存 + 请求队列 |
| Obsidian 仅文件搜索 | 无语义理解 | 向量化 Obsidian 笔记 |

### 8.4 v1.1 规划 (已写入 HIVEMIND_V1.1_KNOWLEDGE_ROUTER_SPEC.md)

- **Module A**: 多 Agent 共享知识层 (4 新表, 7 新 API)
- **Module B**: Skill/MCP 智能路由 (统一索引, 关键词匹配)
- **A+B 集成**: 知识驱动的工具推荐
- **预计新增代码**: ~1,510 行
- **状态**: 等待 Codex 完成 v1.0 优化后执行

---

## 附录: 关键文件索引

| 文件 | 行数 | 用途 |
|------|------|------|
| `lib/memory/memory_v2.py` | ~1820 | 记忆主接口 + 数据库操作 |
| `lib/memory/heuristic_retriever.py` | ~753 | 启发式检索 (αR+βI+γT) |
| `lib/memory/vector_search.py` | ~740 | 向量搜索 (Qdrant/Chroma/InMemory) |
| `lib/memory/ARCHITECTURE.md` | ~294 | 记忆架构文档 |
| `lib/knowledge/router.py` | ~300 | 知识路由器 |
| `lib/gateway/middleware/memory_middleware.py` | ~800 | Gateway 记忆中间件 |
| `docs/HIVEMIND_V1.1_KNOWLEDGE_ROUTER_SPEC.md` | ~350 | v1.1 统一计划 |
