-- CCB Memory System v2.0 - Schema Migration
-- Adds heuristic retrieval support: Importance, Recency, Access Tracking
-- Migration date: 2026-02-05
-- Note: SQLite does not support datetime() as default value

-- ============================================================================
-- 1. Memory Importance Table - 重要性评分表
-- ============================================================================
CREATE TABLE IF NOT EXISTS memory_importance (
    memory_id TEXT PRIMARY KEY,                 -- UUID of message or observation
    memory_type TEXT NOT NULL,                  -- 'message' | 'observation'
    importance_score REAL DEFAULT 0.5,          -- 0.0-1.0 normalized score
    score_source TEXT DEFAULT 'default',        -- 'default' | 'user' | 'llm' | 'heuristic'
    last_accessed_at TEXT,                      -- ISO 8601 timestamp
    access_count INTEGER DEFAULT 0,             -- Total access count
    decay_rate REAL DEFAULT 0.1,                -- Per-hour decay rate (λ)
    created_at TEXT,
    updated_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_importance_score ON memory_importance(importance_score DESC);
CREATE INDEX IF NOT EXISTS idx_importance_accessed ON memory_importance(last_accessed_at DESC);
CREATE INDEX IF NOT EXISTS idx_importance_type ON memory_importance(memory_type);

-- ============================================================================
-- 2. Memory Access Log Table - 记忆访问日志
-- ============================================================================
CREATE TABLE IF NOT EXISTS memory_access_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    memory_id TEXT NOT NULL,                    -- Reference to memory
    memory_type TEXT NOT NULL,                  -- 'message' | 'observation'
    accessed_at TEXT,                           -- Access timestamp
    access_context TEXT,                        -- 'retrieval' | 'injection' | 'user_view' | 'search'
    request_id TEXT,                            -- Gateway request ID (if applicable)
    query_text TEXT,                            -- Query that triggered access (if search)
    relevance_score REAL                        -- FTS/vector score at access time
);

CREATE INDEX IF NOT EXISTS idx_access_memory ON memory_access_log(memory_id);
CREATE INDEX IF NOT EXISTS idx_access_time ON memory_access_log(accessed_at DESC);
CREATE INDEX IF NOT EXISTS idx_access_context ON memory_access_log(access_context);
CREATE INDEX IF NOT EXISTS idx_access_request ON memory_access_log(request_id);

-- ============================================================================
-- 3. Consolidation Log Table - System 2 合并记录
-- ============================================================================
CREATE TABLE IF NOT EXISTS consolidation_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    consolidation_type TEXT NOT NULL,           -- 'merge' | 'abstract' | 'forget' | 'decay'
    source_ids TEXT NOT NULL,                   -- JSON array of source memory IDs
    result_id TEXT,                             -- Result memory ID (for merge/abstract)
    llm_provider TEXT,                          -- Provider used for LLM operations
    llm_model TEXT,                             -- Model used
    status TEXT DEFAULT 'completed',            -- 'pending' | 'in_progress' | 'completed' | 'failed'
    error_message TEXT,                         -- Error message if failed
    metadata TEXT,                              -- JSON: additional info
    created_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_consolidation_type ON consolidation_log(consolidation_type);
CREATE INDEX IF NOT EXISTS idx_consolidation_status ON consolidation_log(status);
CREATE INDEX IF NOT EXISTS idx_consolidation_time ON consolidation_log(created_at DESC);

-- ============================================================================
-- 4. Add new columns to messages table
-- ============================================================================

-- Check if columns exist before adding (SQLite workaround via try-catch in code)
-- These ALTER statements will fail silently if columns exist

-- importance_score: 0.0-1.0, default 0.5 (neutral)
-- last_accessed_at: ISO 8601 timestamp
-- access_count: number of times accessed
-- decay_rate: per-hour decay rate

-- Note: SQLite doesn't support ALTER TABLE ADD COLUMN IF NOT EXISTS
-- These will be wrapped in try-except in Python migration code

-- ALTER TABLE messages ADD COLUMN importance_score REAL DEFAULT 0.5;
-- ALTER TABLE messages ADD COLUMN last_accessed_at TEXT;
-- ALTER TABLE messages ADD COLUMN access_count INTEGER DEFAULT 0;

-- ============================================================================
-- 5. Add new columns to observations table
-- ============================================================================

-- ALTER TABLE observations ADD COLUMN importance_score REAL DEFAULT 0.5;
-- ALTER TABLE observations ADD COLUMN last_accessed_at TEXT;
-- ALTER TABLE observations ADD COLUMN access_count INTEGER DEFAULT 0;
-- ALTER TABLE observations ADD COLUMN decay_rate REAL DEFAULT 0.05;

-- ============================================================================
-- 6. Create view for heuristic scoring
-- ============================================================================
CREATE VIEW IF NOT EXISTS memory_scores AS
SELECT
    mi.memory_id,
    mi.memory_type,
    mi.importance_score,
    mi.last_accessed_at,
    mi.access_count,
    mi.decay_rate,
    -- Calculate recency score using Ebbinghaus decay
    -- recency = exp(-λ * hours_since_access)
    CASE
        WHEN mi.last_accessed_at IS NULL THEN 0.1
        ELSE exp(-mi.decay_rate * (julianday('now') - julianday(mi.last_accessed_at)) * 24)
    END as recency_score,
    mi.updated_at
FROM memory_importance mi;

-- ============================================================================
-- 7. Create combined memory view with scores
-- ============================================================================
CREATE VIEW IF NOT EXISTS messages_with_scores AS
SELECT
    m.message_id,
    m.session_id,
    m.role,
    m.content,
    m.provider,
    m.timestamp,
    m.tokens,
    COALESCE(mi.importance_score, 0.5) as importance_score,
    COALESCE(mi.access_count, 0) as access_count,
    mi.last_accessed_at,
    -- Recency calculation
    CASE
        WHEN mi.last_accessed_at IS NULL THEN 0.1
        ELSE exp(-COALESCE(mi.decay_rate, 0.1) * (julianday('now') - julianday(mi.last_accessed_at)) * 24)
    END as recency_score
FROM messages m
LEFT JOIN memory_importance mi ON m.message_id = mi.memory_id AND mi.memory_type = 'message';

-- ============================================================================
-- 8. Trigger to auto-update memory_importance on access
-- ============================================================================
CREATE TRIGGER IF NOT EXISTS update_importance_on_access
AFTER INSERT ON memory_access_log
BEGIN
    INSERT INTO memory_importance (memory_id, memory_type, last_accessed_at, access_count)
    VALUES (NEW.memory_id, NEW.memory_type, NEW.accessed_at, 1)
    ON CONFLICT(memory_id) DO UPDATE SET
        last_accessed_at = NEW.accessed_at,
        access_count = access_count + 1,
        updated_at = datetime('now');
END;

-- ============================================================================
-- 9. Decay scheduled task view
-- ============================================================================
CREATE VIEW IF NOT EXISTS memories_needing_decay AS
SELECT
    mi.memory_id,
    mi.memory_type,
    mi.importance_score,
    mi.last_accessed_at,
    mi.decay_rate,
    -- Hours since last access
    (julianday('now') - julianday(mi.last_accessed_at)) * 24 as hours_since_access,
    -- Calculated recency
    exp(-mi.decay_rate * (julianday('now') - julianday(mi.last_accessed_at)) * 24) as recency_score,
    -- Flag memories that should be forgotten (recency < 0.01 and older than 90 days)
    CASE
        WHEN exp(-mi.decay_rate * (julianday('now') - julianday(mi.last_accessed_at)) * 24) < 0.01
             AND (julianday('now') - julianday(mi.created_at)) > 90
        THEN 1
        ELSE 0
    END as should_forget
FROM memory_importance mi
WHERE mi.last_accessed_at IS NOT NULL;

-- ============================================================================
-- 10. Statistics views
-- ============================================================================
CREATE VIEW IF NOT EXISTS memory_statistics AS
SELECT
    (SELECT COUNT(*) FROM messages) as total_messages,
    (SELECT COUNT(*) FROM observations) as total_observations,
    (SELECT COUNT(*) FROM memory_importance) as tracked_memories,
    (SELECT COUNT(*) FROM memory_access_log) as total_accesses,
    (SELECT COUNT(*) FROM consolidation_log) as total_consolidations,
    (SELECT COUNT(*) FROM memory_importance WHERE importance_score >= 0.8) as high_importance_count,
    (SELECT COUNT(*) FROM memory_importance WHERE importance_score <= 0.2) as low_importance_count,
    (SELECT AVG(access_count) FROM memory_importance) as avg_access_count;
