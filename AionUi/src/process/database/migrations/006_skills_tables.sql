-- migrations/006_skills_tables.sql
-- Skills Manager tables

BEGIN TRANSACTION;

CREATE TABLE IF NOT EXISTS skills (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  category TEXT NOT NULL DEFAULT 'custom',
  description TEXT,
  file_path TEXT NOT NULL,
  content TEXT,
  manifest TEXT,
  created_at INTEGER NOT NULL,
  updated_at INTEGER NOT NULL,
  version TEXT DEFAULT '1.0.0',
  author TEXT,
  tags TEXT,
  UNIQUE(name, category)
);

CREATE TABLE IF NOT EXISTS ai_tools (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL UNIQUE,
  type TEXT NOT NULL,
  display_name TEXT NOT NULL,
  skills_path TEXT NOT NULL,
  config_path TEXT,
  icon_url TEXT,
  enabled INTEGER DEFAULT 1,
  detected INTEGER DEFAULT 0,
  last_detected_at INTEGER,
  created_at INTEGER NOT NULL,
  updated_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS skill_tool_mapping (
  id TEXT PRIMARY KEY,
  skill_id TEXT NOT NULL,
  tool_id TEXT NOT NULL,
  enabled INTEGER DEFAULT 1,
  synced INTEGER DEFAULT 0,
  symlink_path TEXT,
  synced_at INTEGER,
  sync_error TEXT,
  created_at INTEGER NOT NULL,
  updated_at INTEGER NOT NULL,
  FOREIGN KEY (skill_id) REFERENCES skills(id) ON DELETE CASCADE,
  FOREIGN KEY (tool_id) REFERENCES ai_tools(id) ON DELETE CASCADE,
  UNIQUE(skill_id, tool_id)
);

CREATE INDEX IF NOT EXISTS idx_skills_category ON skills(category);
CREATE INDEX IF NOT EXISTS idx_skills_name ON skills(name);
CREATE INDEX IF NOT EXISTS idx_ai_tools_name ON ai_tools(name);
CREATE INDEX IF NOT EXISTS idx_ai_tools_enabled ON ai_tools(enabled);
CREATE INDEX IF NOT EXISTS idx_mapping_skill ON skill_tool_mapping(skill_id);
CREATE INDEX IF NOT EXISTS idx_mapping_tool ON skill_tool_mapping(tool_id);
CREATE INDEX IF NOT EXISTS idx_mapping_enabled ON skill_tool_mapping(enabled);

INSERT OR IGNORE INTO ai_tools (id, name, type, display_name, skills_path, config_path, enabled, detected, created_at, updated_at) VALUES
  ('tool-claude', 'claude-code', 'builtin', 'Claude Code', '~/.claude/skills/', '~/.claude/config.json', 1, 0, strftime('%s', 'now') * 1000, strftime('%s', 'now') * 1000),
  ('tool-codex', 'codex', 'builtin', 'Codex', '~/.codex/skills/', '~/.codex/config.json', 1, 0, strftime('%s', 'now') * 1000, strftime('%s', 'now') * 1000),
  ('tool-opencode', 'opencode', 'builtin', 'OpenCode', '~/.opencode/skills/', '~/.opencode/config.json', 1, 0, strftime('%s', 'now') * 1000, strftime('%s', 'now') * 1000);

COMMIT;
