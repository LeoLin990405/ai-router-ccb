/**
 * @license
 * Copyright 2025 AionUi (aionui.com)
 * SPDX-License-Identifier: Apache-2.0
 */

import type Database from 'better-sqlite3';

/**
 * Initialize database schema with all tables and indexes
 */
export function initSchema(db: Database.Database): void {
  // Enable foreign keys
  db.pragma('foreign_keys = ON');
  // Enable Write-Ahead Logging for better performance
  try {
    db.pragma('journal_mode = WAL');
  } catch (error) {
    console.warn('[Database] Failed to enable WAL mode, using default journal mode:', error);
    // Continue with default journal mode if WAL fails
  }

  // Users table (账户系统)
  db.exec(`
    CREATE TABLE IF NOT EXISTS users (
      id TEXT PRIMARY KEY,
      username TEXT UNIQUE NOT NULL,
      email TEXT UNIQUE,
      password_hash TEXT NOT NULL,
      avatar_path TEXT,
      jwt_secret TEXT,
      created_at INTEGER NOT NULL,
      updated_at INTEGER NOT NULL,
      last_login INTEGER
    );

    CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
    CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
  `);

  // Conversations table (会话表 - 存储TChatConversation)
  db.exec(`
    CREATE TABLE IF NOT EXISTS conversations (
      id TEXT PRIMARY KEY,
      user_id TEXT NOT NULL,
      name TEXT NOT NULL,
      type TEXT NOT NULL CHECK(type IN ('gemini', 'acp', 'codex', 'openclaw-gateway', 'hivemind')),
      extra TEXT NOT NULL,
      model TEXT,
      status TEXT CHECK(status IN ('pending', 'running', 'finished')),
      created_at INTEGER NOT NULL,
      updated_at INTEGER NOT NULL,
      FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    );

    CREATE INDEX IF NOT EXISTS idx_conversations_user_id ON conversations(user_id);
    CREATE INDEX IF NOT EXISTS idx_conversations_updated_at ON conversations(updated_at);
    CREATE INDEX IF NOT EXISTS idx_conversations_type ON conversations(type);
    CREATE INDEX IF NOT EXISTS idx_conversations_user_updated ON conversations(user_id, updated_at DESC);
  `);

  // Messages table (消息表 - 存储TMessage)
  db.exec(`
    CREATE TABLE IF NOT EXISTS messages (
      id TEXT PRIMARY KEY,
      conversation_id TEXT NOT NULL,
      msg_id TEXT,
      type TEXT NOT NULL,
      content TEXT NOT NULL,
      position TEXT CHECK(position IN ('left', 'right', 'center', 'pop')),
      status TEXT CHECK(status IN ('finish', 'pending', 'error', 'work')),
      created_at INTEGER NOT NULL,
      FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
    );

    CREATE INDEX IF NOT EXISTS idx_messages_conversation_id ON messages(conversation_id);
    CREATE INDEX IF NOT EXISTS idx_messages_created_at ON messages(created_at);
    CREATE INDEX IF NOT EXISTS idx_messages_type ON messages(type);
    CREATE INDEX IF NOT EXISTS idx_messages_msg_id ON messages(msg_id);
    CREATE INDEX IF NOT EXISTS idx_messages_conversation_created ON messages(conversation_id, created_at);
  `);




  // Skills Manager tables
  db.exec(`
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

    CREATE INDEX IF NOT EXISTS idx_skills_category ON skills(category);
    CREATE INDEX IF NOT EXISTS idx_skills_name ON skills(name);

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

    CREATE INDEX IF NOT EXISTS idx_ai_tools_name ON ai_tools(name);
    CREATE INDEX IF NOT EXISTS idx_ai_tools_enabled ON ai_tools(enabled);

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

    CREATE INDEX IF NOT EXISTS idx_mapping_skill ON skill_tool_mapping(skill_id);
    CREATE INDEX IF NOT EXISTS idx_mapping_tool ON skill_tool_mapping(tool_id);
    CREATE INDEX IF NOT EXISTS idx_mapping_enabled ON skill_tool_mapping(enabled);

    INSERT OR IGNORE INTO ai_tools (
      id, name, type, display_name, skills_path, config_path, enabled, detected, created_at, updated_at
    ) VALUES
      ('tool-claude', 'claude-code', 'builtin', 'Claude Code', '~/.claude/skills/', '~/.claude/config.json', 1, 0, strftime('%s', 'now') * 1000, strftime('%s', 'now') * 1000),
      ('tool-codex', 'codex', 'builtin', 'Codex', '~/.codex/skills/', '~/.codex/config.json', 1, 0, strftime('%s', 'now') * 1000, strftime('%s', 'now') * 1000),
      ('tool-opencode', 'opencode', 'builtin', 'OpenCode', '~/.opencode/skills/', '~/.opencode/config.json', 1, 0, strftime('%s', 'now') * 1000, strftime('%s', 'now') * 1000);
  `);
  // Agent Teams tables
  db.exec(`
    CREATE TABLE IF NOT EXISTS agent_teams (
      id TEXT PRIMARY KEY,
      name TEXT NOT NULL,
      description TEXT,
      status TEXT NOT NULL DEFAULT 'active',
      max_teammates INTEGER NOT NULL DEFAULT 5,
      task_allocation_strategy TEXT NOT NULL DEFAULT 'round_robin',

      created_at INTEGER NOT NULL,
      updated_at INTEGER NOT NULL,
      started_at INTEGER,
      completed_at INTEGER,

      total_tasks INTEGER NOT NULL DEFAULT 0,
      completed_tasks INTEGER NOT NULL DEFAULT 0,
      failed_tasks INTEGER NOT NULL DEFAULT 0,
      total_cost_usd REAL NOT NULL DEFAULT 0.0,

      metadata TEXT
    );

    CREATE INDEX IF NOT EXISTS idx_agent_teams_status ON agent_teams(status);
    CREATE INDEX IF NOT EXISTS idx_agent_teams_created_at ON agent_teams(created_at DESC);

    CREATE TABLE IF NOT EXISTS agent_teammates (
      id TEXT PRIMARY KEY,
      team_id TEXT NOT NULL,
      name TEXT NOT NULL,
      role TEXT NOT NULL,
      provider TEXT NOT NULL,
      model TEXT NOT NULL,
      status TEXT NOT NULL DEFAULT 'idle',
      current_task_id TEXT,
      skills TEXT NOT NULL DEFAULT '[]',
      tasks_completed INTEGER NOT NULL DEFAULT 0,
      tasks_failed INTEGER NOT NULL DEFAULT 0,
      total_tokens INTEGER NOT NULL DEFAULT 0,
      total_cost_usd REAL NOT NULL DEFAULT 0.0,
      avg_task_duration_ms INTEGER NOT NULL DEFAULT 0,
      created_at INTEGER NOT NULL,
      updated_at INTEGER NOT NULL,
      last_active_at INTEGER,
      metadata TEXT,
      FOREIGN KEY (team_id) REFERENCES agent_teams(id) ON DELETE CASCADE
    );

    CREATE INDEX IF NOT EXISTS idx_teammates_team_id ON agent_teammates(team_id);
    CREATE INDEX IF NOT EXISTS idx_teammates_status ON agent_teammates(status);
    CREATE INDEX IF NOT EXISTS idx_teammates_provider ON agent_teammates(provider);

    CREATE TABLE IF NOT EXISTS agent_tasks (
      id TEXT PRIMARY KEY,
      team_id TEXT NOT NULL,
      subject TEXT NOT NULL,
      description TEXT NOT NULL,
      status TEXT NOT NULL DEFAULT 'pending',
      priority INTEGER NOT NULL DEFAULT 5,
      assigned_to TEXT,
      provider TEXT,
      model TEXT,
      created_at INTEGER NOT NULL,
      updated_at INTEGER NOT NULL,
      started_at INTEGER,
      completed_at INTEGER,
      input_tokens INTEGER NOT NULL DEFAULT 0,
      output_tokens INTEGER NOT NULL DEFAULT 0,
      cost_usd REAL NOT NULL DEFAULT 0.0,
      blocks TEXT NOT NULL DEFAULT '[]',
      blocked_by TEXT NOT NULL DEFAULT '[]',
      result TEXT,
      error TEXT,
      metadata TEXT,
      FOREIGN KEY (team_id) REFERENCES agent_teams(id) ON DELETE CASCADE,
      FOREIGN KEY (assigned_to) REFERENCES agent_teammates(id) ON DELETE SET NULL
    );

    CREATE INDEX IF NOT EXISTS idx_tasks_team_id ON agent_tasks(team_id);
    CREATE INDEX IF NOT EXISTS idx_tasks_status ON agent_tasks(status);
    CREATE INDEX IF NOT EXISTS idx_tasks_assigned_to ON agent_tasks(assigned_to);
    CREATE INDEX IF NOT EXISTS idx_tasks_created_at ON agent_tasks(created_at DESC);
    CREATE INDEX IF NOT EXISTS idx_tasks_priority ON agent_tasks(priority DESC);

    CREATE TABLE IF NOT EXISTS agent_task_dependencies (
      id TEXT PRIMARY KEY,
      task_id TEXT NOT NULL,
      depends_on_task_id TEXT NOT NULL,
      dependency_type TEXT NOT NULL DEFAULT 'finish_to_start',
      created_at INTEGER NOT NULL,
      FOREIGN KEY (task_id) REFERENCES agent_tasks(id) ON DELETE CASCADE,
      FOREIGN KEY (depends_on_task_id) REFERENCES agent_tasks(id) ON DELETE CASCADE,
      UNIQUE(task_id, depends_on_task_id)
    );

    CREATE INDEX IF NOT EXISTS idx_deps_task_id ON agent_task_dependencies(task_id);
    CREATE INDEX IF NOT EXISTS idx_deps_depends_on ON agent_task_dependencies(depends_on_task_id);

    CREATE TABLE IF NOT EXISTS agent_team_messages (
      id TEXT PRIMARY KEY,
      team_id TEXT NOT NULL,
      type TEXT NOT NULL,
      from_teammate_id TEXT,
      to_teammate_id TEXT,
      subject TEXT,
      content TEXT NOT NULL,
      task_id TEXT,
      created_at INTEGER NOT NULL,
      metadata TEXT,
      FOREIGN KEY (team_id) REFERENCES agent_teams(id) ON DELETE CASCADE,
      FOREIGN KEY (from_teammate_id) REFERENCES agent_teammates(id) ON DELETE SET NULL,
      FOREIGN KEY (to_teammate_id) REFERENCES agent_teammates(id) ON DELETE SET NULL,
      FOREIGN KEY (task_id) REFERENCES agent_tasks(id) ON DELETE SET NULL
    );

    CREATE INDEX IF NOT EXISTS idx_messages_team_id ON agent_team_messages(team_id);
    CREATE INDEX IF NOT EXISTS idx_messages_created_at ON agent_team_messages(created_at DESC);
    CREATE INDEX IF NOT EXISTS idx_messages_type ON agent_team_messages(type);
    CREATE INDEX IF NOT EXISTS idx_messages_task_id ON agent_team_messages(task_id);

    CREATE TABLE IF NOT EXISTS agent_sessions (
      id TEXT PRIMARY KEY,
      teammate_id TEXT NOT NULL,
      task_id TEXT NOT NULL,
      status TEXT NOT NULL DEFAULT 'running',
      provider TEXT NOT NULL,
      model TEXT NOT NULL,
      input_tokens INTEGER NOT NULL DEFAULT 0,
      output_tokens INTEGER NOT NULL DEFAULT 0,
      cost_usd REAL NOT NULL DEFAULT 0.0,
      started_at INTEGER NOT NULL,
      completed_at INTEGER,
      duration_ms INTEGER,
      result TEXT,
      error TEXT,
      metadata TEXT,
      FOREIGN KEY (teammate_id) REFERENCES agent_teammates(id) ON DELETE CASCADE,
      FOREIGN KEY (task_id) REFERENCES agent_tasks(id) ON DELETE CASCADE
    );

    CREATE INDEX IF NOT EXISTS idx_sessions_teammate_id ON agent_sessions(teammate_id);
    CREATE INDEX IF NOT EXISTS idx_sessions_task_id ON agent_sessions(task_id);
    CREATE INDEX IF NOT EXISTS idx_sessions_status ON agent_sessions(status);
    CREATE INDEX IF NOT EXISTS idx_sessions_started_at ON agent_sessions(started_at DESC);
  `);
  console.log('[Database] Schema initialized successfully');
}

/**
 * Get database version for migration tracking
 * Uses SQLite's built-in user_version pragma
 */
export function getDatabaseVersion(db: Database.Database): number {
  try {
    const result = db.pragma('user_version', { simple: true }) as number;
    return result;
  } catch {
    return 0;
  }
}

/**
 * Set database version
 * Uses SQLite's built-in user_version pragma
 */
export function setDatabaseVersion(db: Database.Database, version: number): void {
  db.pragma(`user_version = ${version}`);
}

/**
 * Current database schema version
 * Update this when adding new migrations in migrations.ts
 */
export const CURRENT_DB_VERSION = 15;
