-- Shared Knowledge Layer v1.1

CREATE TABLE IF NOT EXISTS agents (
    agent_id    TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    provider    TEXT,
    role        TEXT DEFAULT 'general',
    created_at  REAL DEFAULT (strftime('%s', 'now')),
    last_active REAL,
    metadata    TEXT DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS shared_knowledge (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_id    TEXT NOT NULL,
    category    TEXT NOT NULL CHECK(category IN (
        'code_pattern', 'solution', 'architecture',
        'debugging', 'api_usage', 'best_practice',
        'config', 'learning', 'other'
    )),
    title       TEXT NOT NULL,
    content     TEXT NOT NULL,
    tags        TEXT DEFAULT '[]',
    source_request_id TEXT,
    confidence  REAL DEFAULT 0.5,
    created_at  REAL DEFAULT (strftime('%s', 'now')),
    updated_at  REAL DEFAULT (strftime('%s', 'now')),
    access_count INTEGER DEFAULT 0,
    metadata    TEXT DEFAULT '{}',
    FOREIGN KEY (agent_id) REFERENCES agents(agent_id)
);

CREATE VIRTUAL TABLE IF NOT EXISTS shared_knowledge_fts
USING fts5(title, content, tags, tokenize='trigram');

CREATE TRIGGER IF NOT EXISTS shared_knowledge_ai
AFTER INSERT ON shared_knowledge BEGIN
    INSERT INTO shared_knowledge_fts(rowid, title, content, tags)
    VALUES (new.id, new.title, new.content, new.tags);
END;

CREATE TRIGGER IF NOT EXISTS shared_knowledge_ad
AFTER DELETE ON shared_knowledge BEGIN
    DELETE FROM shared_knowledge_fts WHERE rowid = old.id;
END;

CREATE TRIGGER IF NOT EXISTS shared_knowledge_au
AFTER UPDATE OF title, content, tags ON shared_knowledge BEGIN
    DELETE FROM shared_knowledge_fts WHERE rowid = old.id;
    INSERT INTO shared_knowledge_fts(rowid, title, content, tags)
    VALUES (new.id, new.title, new.content, new.tags);
END;

CREATE TABLE IF NOT EXISTS knowledge_votes (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    knowledge_id INTEGER NOT NULL,
    agent_id    TEXT NOT NULL,
    vote        TEXT NOT NULL CHECK(vote IN ('agree', 'disagree', 'cite')),
    comment     TEXT,
    created_at  REAL DEFAULT (strftime('%s', 'now')),
    FOREIGN KEY (knowledge_id) REFERENCES shared_knowledge(id) ON DELETE CASCADE,
    UNIQUE(knowledge_id, agent_id, vote)
);

CREATE TABLE IF NOT EXISTS knowledge_access_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    knowledge_id INTEGER NOT NULL,
    agent_id    TEXT,
    query       TEXT,
    relevance_score REAL,
    accessed_at REAL DEFAULT (strftime('%s', 'now')),
    FOREIGN KEY (knowledge_id) REFERENCES shared_knowledge(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_sk_agent ON shared_knowledge(agent_id);
CREATE INDEX IF NOT EXISTS idx_sk_category ON shared_knowledge(category);
CREATE INDEX IF NOT EXISTS idx_sk_created ON shared_knowledge(created_at);
CREATE INDEX IF NOT EXISTS idx_sk_confidence ON shared_knowledge(confidence DESC);
CREATE INDEX IF NOT EXISTS idx_kv_knowledge ON knowledge_votes(knowledge_id);
CREATE INDEX IF NOT EXISTS idx_kal_knowledge ON knowledge_access_log(knowledge_id);
CREATE INDEX IF NOT EXISTS idx_kal_accessed ON knowledge_access_log(accessed_at);
