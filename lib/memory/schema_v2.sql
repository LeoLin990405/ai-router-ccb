-- CCB Memory System - Schema v2.0
-- 按照 CCB Gateway 架构设计的记忆系统

-- ============================================================================
-- 1. Sessions Table - 会话管理
-- ============================================================================
CREATE TABLE IF NOT EXISTS sessions (
    session_id TEXT PRIMARY KEY,           -- UUID
    user_id TEXT NOT NULL,                 -- 用户ID（支持多用户）
    created_at TEXT NOT NULL,              -- 创建时间
    last_active TEXT NOT NULL,             -- 最后活跃时间
    context_window INTEGER DEFAULT 10,     -- 上下文窗口大小
    metadata TEXT,                         -- JSON: {title, tags, project, ...}
    archived INTEGER DEFAULT 0             -- 是否归档
);

CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_active ON sessions(last_active);
CREATE INDEX IF NOT EXISTS idx_sessions_archived ON sessions(archived);

-- ============================================================================
-- 2. Messages Table - 消息记录（替代旧的 conversations）
-- ============================================================================
CREATE TABLE IF NOT EXISTS messages (
    message_id TEXT PRIMARY KEY,           -- UUID
    session_id TEXT NOT NULL,              -- 关联到会话
    request_id TEXT,                       -- Gateway Request ID（可追踪）
    sequence INTEGER NOT NULL,             -- 消息序号（会话内）

    -- 消息内容
    role TEXT NOT NULL,                    -- 'user' | 'assistant' | 'system'
    content TEXT NOT NULL,                 -- 消息内容

    -- Provider 信息
    provider TEXT,                         -- kimi, codex, gemini, ...
    model TEXT,                            -- thinking, o3, 3f, ...

    -- 时间和性能
    timestamp TEXT NOT NULL,               -- ISO 8601
    latency_ms INTEGER,                    -- 响应延迟
    tokens INTEGER DEFAULT 0,              -- Token 使用量

    -- 上下文注入信息
    context_injected INTEGER DEFAULT 0,    -- 是否注入了上下文
    context_count INTEGER DEFAULT 0,       -- 注入的记忆条数
    skills_used TEXT,                      -- JSON: ["pdf", "xlsx"]

    -- 元数据
    metadata TEXT                          -- JSON: 扩展信息
);

CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id);
CREATE INDEX IF NOT EXISTS idx_messages_request ON messages(request_id);
CREATE INDEX IF NOT EXISTS idx_messages_timestamp ON messages(timestamp);
CREATE INDEX IF NOT EXISTS idx_messages_provider ON messages(provider);

-- Foreign key
CREATE TRIGGER IF NOT EXISTS fk_messages_session
BEFORE INSERT ON messages
BEGIN
    SELECT RAISE(ABORT, 'Foreign key violation')
    WHERE NEW.session_id NOT IN (SELECT session_id FROM sessions);
END;

-- ============================================================================
-- 3. Context Injections Table - 上下文注入记录
-- ============================================================================
CREATE TABLE IF NOT EXISTS context_injections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id TEXT NOT NULL,              -- 关联到消息
    injection_type TEXT NOT NULL,          -- 'memory' | 'skill' | 'provider' | 'mcp'

    -- 注入内容引用
    reference_id TEXT,                     -- 引用的 message_id 或 skill_name
    relevance_score REAL,                  -- 相关性得分

    -- 元数据
    metadata TEXT                          -- JSON: 详细信息
);

CREATE INDEX IF NOT EXISTS idx_context_message ON context_injections(message_id);
CREATE INDEX IF NOT EXISTS idx_context_type ON context_injections(injection_type);

-- ============================================================================
-- 4. Skills Usage Table - 技能使用记录（保留并增强）
-- ============================================================================
CREATE TABLE IF NOT EXISTS skills_usage (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id TEXT,                       -- 关联到消息
    skill_name TEXT NOT NULL,
    task_keywords TEXT NOT NULL,
    provider TEXT,
    timestamp TEXT NOT NULL,
    success INTEGER DEFAULT 1,
    latency_ms INTEGER                     -- 技能执行耗时
);

CREATE INDEX IF NOT EXISTS idx_skills_message ON skills_usage(message_id);
CREATE INDEX IF NOT EXISTS idx_skills_keywords ON skills_usage(task_keywords);

-- ============================================================================
-- 5. Skills Cache Table - 技能缓存（保留）
-- ============================================================================
CREATE TABLE IF NOT EXISTS skills_cache (
    skill_name TEXT PRIMARY KEY,
    description TEXT,
    triggers TEXT,                         -- JSON array
    source TEXT,                           -- 'local' | 'remote'
    installed INTEGER DEFAULT 0,
    last_updated TEXT NOT NULL,
    metadata TEXT                          -- JSON
);

-- ============================================================================
-- 6. Provider Stats Table - Provider 统计
-- ============================================================================
CREATE TABLE IF NOT EXISTS provider_stats (
    provider TEXT PRIMARY KEY,
    total_requests INTEGER DEFAULT 0,
    total_success INTEGER DEFAULT 0,
    total_failures INTEGER DEFAULT 0,
    avg_latency_ms REAL,
    total_tokens INTEGER DEFAULT 0,
    last_used TEXT
);

CREATE INDEX IF NOT EXISTS idx_provider_lastused ON provider_stats(last_used);

-- ============================================================================
-- 7. FTS5 Full-Text Search Index - 全文搜索索引
-- ============================================================================
CREATE VIRTUAL TABLE IF NOT EXISTS messages_fts USING fts5(
    content,                               -- 消息内容
    provider,                              -- Provider
    skills_used,                           -- 使用的技能
    content='messages',
    content_rowid='rowid',
    tokenize='porter unicode61'           -- 支持中文
);

-- ============================================================================
-- 8. Learnings Table - 学习记录（保留）
-- ============================================================================
CREATE TABLE IF NOT EXISTS learnings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT,                       -- 关联到会话
    timestamp TEXT NOT NULL,
    category TEXT NOT NULL,
    content TEXT NOT NULL,
    metadata TEXT
);

CREATE INDEX IF NOT EXISTS idx_learnings_session ON learnings(session_id);
CREATE INDEX IF NOT EXISTS idx_learnings_category ON learnings(category);

-- ============================================================================
-- 9. Request Memory Map Table - 请求记忆注入追踪（Phase 1: Transparency）
-- ============================================================================
CREATE TABLE IF NOT EXISTS request_memory_map (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id TEXT NOT NULL UNIQUE,        -- Gateway Request ID
    session_id TEXT,                        -- 关联到会话
    provider TEXT,                          -- 请求的 Provider
    original_message TEXT,                  -- 原始用户消息

    -- 注入详情
    injected_memory_ids TEXT,               -- JSON array of memory message_ids
    injected_skills TEXT,                   -- JSON array of skill names
    injected_system_context INTEGER DEFAULT 0,  -- 是否注入了系统上下文

    -- 元数据
    injection_timestamp TEXT NOT NULL,      -- 注入时间
    memory_count INTEGER DEFAULT 0,         -- 注入的记忆条数
    skills_count INTEGER DEFAULT 0,         -- 注入的技能数
    relevance_scores TEXT,                  -- JSON: {memory_id: score, ...}

    -- 追踪字段
    metadata TEXT                           -- JSON: 扩展信息
);

CREATE INDEX IF NOT EXISTS idx_request_memory_map_request ON request_memory_map(request_id);
CREATE INDEX IF NOT EXISTS idx_request_memory_map_session ON request_memory_map(session_id);
CREATE INDEX IF NOT EXISTS idx_request_memory_map_timestamp ON request_memory_map(injection_timestamp);

-- ============================================================================
-- 10. Archived Sessions Table - 归档会话（分区存储）
-- ============================================================================
CREATE TABLE IF NOT EXISTS archived_sessions (
    session_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    archived_at TEXT NOT NULL,
    message_count INTEGER,
    total_tokens INTEGER,

    -- 压缩存储的会话数据
    compressed_data BLOB                   -- GZIP 压缩的 JSON
);

CREATE INDEX IF NOT EXISTS idx_archived_user ON archived_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_archived_date ON archived_sessions(archived_at);

-- ============================================================================
-- 11. Observations Table - 用户观察/洞察记录（Phase 2: Write APIs）
-- ============================================================================
CREATE TABLE IF NOT EXISTS observations (
    observation_id TEXT PRIMARY KEY,        -- UUID
    user_id TEXT NOT NULL,                  -- 用户ID（支持多用户）
    category TEXT NOT NULL,                 -- 'insight', 'preference', 'fact', 'note'
    content TEXT NOT NULL,                  -- 观察内容
    tags TEXT,                              -- JSON array of tags

    -- 来源和可信度
    source TEXT DEFAULT 'manual',           -- 'manual', 'llm_extracted', 'consolidator'
    confidence REAL DEFAULT 1.0,            -- 可信度 0-1

    -- 时间
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,

    -- 元数据
    metadata TEXT                           -- JSON: 扩展信息
);

CREATE INDEX IF NOT EXISTS idx_observations_user ON observations(user_id);
CREATE INDEX IF NOT EXISTS idx_observations_category ON observations(category);
CREATE INDEX IF NOT EXISTS idx_observations_created ON observations(created_at);

-- Observations FTS5 索引
CREATE VIRTUAL TABLE IF NOT EXISTS observations_fts USING fts5(
    content,
    tags,
    content='observations',
    content_rowid='rowid',
    tokenize='porter unicode61'
);

-- 自动更新 Observations FTS5 索引
CREATE TRIGGER IF NOT EXISTS observations_fts_insert
AFTER INSERT ON observations
BEGIN
    INSERT INTO observations_fts(rowid, content, tags)
    VALUES (NEW.rowid, NEW.content, NEW.tags);
END;

CREATE TRIGGER IF NOT EXISTS observations_fts_delete
AFTER DELETE ON observations
BEGIN
    DELETE FROM observations_fts WHERE rowid = OLD.rowid;
END;

CREATE TRIGGER IF NOT EXISTS observations_fts_update
AFTER UPDATE ON observations
BEGIN
    DELETE FROM observations_fts WHERE rowid = OLD.rowid;
    INSERT INTO observations_fts(rowid, content, tags)
    VALUES (NEW.rowid, NEW.content, NEW.tags);
END;

-- ============================================================================
-- 12. Skills Feedback Table - 技能反馈记录（Phase 5: Feedback Loop）
-- ============================================================================
CREATE TABLE IF NOT EXISTS skills_feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    skill_name TEXT NOT NULL,               -- 技能名称
    user_id TEXT NOT NULL DEFAULT 'default', -- 用户ID
    rating INTEGER NOT NULL,                -- 评分 1-5
    task_keywords TEXT,                     -- JSON: 任务关键词
    task_description TEXT,                  -- 任务描述
    helpful INTEGER DEFAULT 1,              -- 是否有帮助 0/1
    comment TEXT,                           -- 用户评论
    timestamp TEXT NOT NULL,                -- 反馈时间
    metadata TEXT                           -- JSON: 扩展信息
);

CREATE INDEX IF NOT EXISTS idx_skills_feedback_skill ON skills_feedback(skill_name);
CREATE INDEX IF NOT EXISTS idx_skills_feedback_user ON skills_feedback(user_id);
CREATE INDEX IF NOT EXISTS idx_skills_feedback_timestamp ON skills_feedback(timestamp);
CREATE INDEX IF NOT EXISTS idx_skills_feedback_rating ON skills_feedback(rating);

-- ============================================================================
-- Triggers - 自动维护
-- ============================================================================

-- 自动更新 session.last_active
CREATE TRIGGER IF NOT EXISTS update_session_active
AFTER INSERT ON messages
BEGIN
    UPDATE sessions
    SET last_active = NEW.timestamp
    WHERE session_id = NEW.session_id;
END;

-- 自动更新 FTS5 索引
CREATE TRIGGER IF NOT EXISTS messages_fts_insert
AFTER INSERT ON messages
BEGIN
    INSERT INTO messages_fts(rowid, content, provider, skills_used)
    VALUES (NEW.rowid, NEW.content, NEW.provider, NEW.skills_used);
END;

CREATE TRIGGER IF NOT EXISTS messages_fts_delete
AFTER DELETE ON messages
BEGIN
    DELETE FROM messages_fts WHERE rowid = OLD.rowid;
END;

-- 自动更新 Provider 统计
CREATE TRIGGER IF NOT EXISTS update_provider_stats
AFTER INSERT ON messages
WHEN NEW.role = 'assistant' AND NEW.provider IS NOT NULL
BEGIN
    INSERT INTO provider_stats (provider, total_requests, total_success, avg_latency_ms, total_tokens, last_used)
    VALUES (NEW.provider, 1, 1, NEW.latency_ms, NEW.tokens, NEW.timestamp)
    ON CONFLICT(provider) DO UPDATE SET
        total_requests = total_requests + 1,
        total_success = total_success + 1,
        avg_latency_ms = (avg_latency_ms * total_requests + NEW.latency_ms) / (total_requests + 1),
        total_tokens = total_tokens + NEW.tokens,
        last_used = NEW.timestamp;
END;

-- ============================================================================
-- Views - 便捷查询视图
-- ============================================================================

-- 会话概览视图
CREATE VIEW IF NOT EXISTS session_overview AS
SELECT
    s.session_id,
    s.user_id,
    s.created_at,
    s.last_active,
    COUNT(m.message_id) as message_count,
    SUM(m.tokens) as total_tokens,
    GROUP_CONCAT(DISTINCT m.provider) as providers_used
FROM sessions s
LEFT JOIN messages m ON s.session_id = m.session_id
GROUP BY s.session_id;

-- 最近对话视图
CREATE VIEW IF NOT EXISTS recent_conversations AS
SELECT
    m1.message_id as user_message_id,
    m1.content as user_message,
    m1.timestamp as user_timestamp,
    m2.message_id as assistant_message_id,
    m2.content as assistant_message,
    m2.provider,
    m2.latency_ms,
    m2.tokens,
    m2.timestamp as assistant_timestamp,
    m1.session_id
FROM messages m1
JOIN messages m2 ON m1.session_id = m2.session_id
    AND m2.sequence = m1.sequence + 1
WHERE m1.role = 'user' AND m2.role = 'assistant'
ORDER BY m1.timestamp DESC;
