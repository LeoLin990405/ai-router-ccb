"""Auto-split mixins for ContextSaver."""

import json
import os
import re
import sqlite3
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

from memory.jsonl_parser import ClaudeJsonlParser, Message, SessionData, ToolCall

try:
    from lib.common.logging import get_logger
except ImportError:  # pragma: no cover - script mode
    try:
        from common.logging import get_logger  # type: ignore
    except ImportError:  # pragma: no cover - fallback
        import logging

        def get_logger(name: str):
            return logging.getLogger(name)


logger = get_logger("memory.context_saver")


class ContextSaverCoreMixin:
    """Mixin methods extracted from ContextSaver."""

    def __init__(self, archive_dir: Optional[Path] = None, db_path: Optional[Path] = None):
        # Keep archive_dir for backward compatibility, but we use database now
        self.archive_dir = archive_dir or Path.home() / ".ccb" / "context_archive"
        self.archive_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = db_path or self.DB_PATH
        self.parser = ClaudeJsonlParser()

        # Ensure database tables exist
        self._init_db()

    def _init_db(self):
        """Ensure session archive tables exist."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Session archives table (System 1 output)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS session_archives (
                archive_id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                user_id TEXT DEFAULT 'default',
                project_path TEXT,
                git_branch TEXT,
                model TEXT,
                start_time TEXT,
                end_time TEXT,
                duration_minutes INTEGER,
                message_count INTEGER DEFAULT 0,
                tool_call_count INTEGER DEFAULT 0,
                task_summary TEXT,
                key_messages TEXT,  -- JSON array
                tool_usage TEXT,    -- JSON object
                file_changes TEXT,  -- JSON array
                learnings TEXT,     -- JSON array
                metadata TEXT,      -- JSON object
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(session_id)
            )
        """)

        # Index for efficient queries
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_session_archives_created
            ON session_archives(created_at DESC)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_session_archives_project
            ON session_archives(project_path)
        """)

        conn.commit()
        conn.close()

    def save_session(self, session_path: Path, force: bool = False) -> Optional[str]:
        """
        Save a session to DATABASE.

        Args:
            session_path: Path to the session.jsonl file
            force: If True, save even if session seems trivial

        Returns:
            archive_id if saved successfully, or None if skipped
        """
        if not session_path.exists():
            logger.warning("Session file not found: %s", session_path)
            return None

        try:
            session = self.parser.parse(session_path)
        except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError, json.JSONDecodeError) as e:
            logger.warning("Error parsing session: %s", e)
            return None

        # Skip trivial sessions (less than 2 meaningful messages)
        if not force and len(session.messages) < 2:
            return None

        # Save to database
        archive_id = self._save_to_database(session)
        return archive_id

    def _save_to_database(self, session: SessionData) -> str:
        """Save session data to SQLite database."""
        archive_id = str(uuid.uuid4())

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            # Extract structured data
            task_summary = self._extract_task_summary(session)
            key_messages = self._extract_key_messages(session)
            tool_summary = self.parser.get_tool_summary(session.tool_calls)
            learnings = self._extract_learnings(session)
            duration = self.parser.get_session_duration(session)

            # Convert to JSON
            key_messages_json = json.dumps([
                {
                    'role': m.role,
                    'content': self._truncate_content(m.content, 1000),
                    'timestamp': m.timestamp
                }
                for m in key_messages
            ], ensure_ascii=False)

            file_changes_json = json.dumps([
                {'path': fc.file_path, 'action': fc.action}
                for fc in session.file_changes[:50]
            ], ensure_ascii=False)

            # Calculate duration in minutes
            duration_minutes = 0
            if duration:
                # Parse duration string like "45 分钟" or "1 小时 30 分钟"
                import re
                hours_match = re.search(r'(\d+)\s*小时', duration)
                mins_match = re.search(r'(\d+)\s*分', duration)
                if hours_match:
                    duration_minutes += int(hours_match.group(1)) * 60
                if mins_match:
                    duration_minutes += int(mins_match.group(1))

            cursor.execute("""
                INSERT OR REPLACE INTO session_archives (
                    archive_id, session_id, user_id, project_path, git_branch, model,
                    start_time, end_time, duration_minutes, message_count, tool_call_count,
                    task_summary, key_messages, tool_usage, file_changes, learnings, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                archive_id,
                session.session_id,
                'default',
                session.project_path,
                session.git_branch,
                session.model,
                session.start_time,
                session.end_time,
                duration_minutes,
                len(session.messages),
                len(session.tool_calls),
                task_summary,
                key_messages_json,
                json.dumps(tool_summary, ensure_ascii=False),
                file_changes_json,
                json.dumps(learnings, ensure_ascii=False),
                json.dumps({
                    'file_count': len(session.file_changes),
                    'source_file': str(session.session_id)
                }, ensure_ascii=False)
            ))

            conn.commit()
            logger.info("Session archived to database: %s", archive_id[:8])
            return archive_id

        except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError, sqlite3.Error) as e:
            logger.warning("Error saving to database: %s", e)
            conn.rollback()
            return None
        finally:
            conn.close()

    def get_recent_archives(self, hours: int = 24, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent session archives from database.

        Args:
            hours: How many hours back to look
            limit: Maximum number of archives to return

        Returns:
            List of archive dictionaries
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            cursor.execute("""
                SELECT * FROM session_archives
                WHERE created_at >= datetime('now', ?)
                ORDER BY created_at DESC
                LIMIT ?
            """, (f'-{hours} hours', limit))

            columns = [desc[0] for desc in cursor.description]
            results = []
            for row in cursor.fetchall():
                result = dict(zip(columns, row))
                # Parse JSON fields
                for field in ['key_messages', 'tool_usage', 'file_changes', 'learnings', 'metadata']:
                    if result.get(field):
                        try:
                            result[field] = json.loads(result[field])
                        except json.JSONDecodeError:
                            pass
                results.append(result)

            return results
        finally:
            conn.close()

    def search_archives(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Search session archives by task summary or project.

        Args:
            query: Search query
            limit: Maximum results

        Returns:
            List of matching archives
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            cursor.execute("""
                SELECT * FROM session_archives
                WHERE task_summary LIKE ? OR project_path LIKE ?
                ORDER BY created_at DESC
                LIMIT ?
            """, (f'%{query}%', f'%{query}%', limit))

            columns = [desc[0] for desc in cursor.description]
            results = []
            for row in cursor.fetchall():
                result = dict(zip(columns, row))
                for field in ['key_messages', 'tool_usage', 'file_changes', 'learnings', 'metadata']:
                    if result.get(field):
                        try:
                            result[field] = json.loads(result[field])
                        except json.JSONDecodeError:
                            pass
                results.append(result)

            return results
        finally:
            conn.close()

    def get_archive_stats(self) -> Dict[str, Any]:
        """Get statistics about session archives.

        Returns:
            Statistics dictionary
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            # Total archives
            cursor.execute("SELECT COUNT(*) FROM session_archives")
            total = cursor.fetchone()[0]

            # Recent archives (last 24h)
            cursor.execute("""
                SELECT COUNT(*) FROM session_archives
                WHERE created_at >= datetime('now', '-24 hours')
            """)
            recent_24h = cursor.fetchone()[0]

            # Recent archives (last 7d)
            cursor.execute("""
                SELECT COUNT(*) FROM session_archives
                WHERE created_at >= datetime('now', '-7 days')
            """)
            recent_7d = cursor.fetchone()[0]

            # Total messages
            cursor.execute("SELECT SUM(message_count) FROM session_archives")
            total_messages = cursor.fetchone()[0] or 0

            # Total tool calls
            cursor.execute("SELECT SUM(tool_call_count) FROM session_archives")
            total_tool_calls = cursor.fetchone()[0] or 0

            # Projects worked on
            cursor.execute("SELECT COUNT(DISTINCT project_path) FROM session_archives")
            unique_projects = cursor.fetchone()[0]

            return {
                'total_archives': total,
                'recent_24h': recent_24h,
                'recent_7d': recent_7d,
                'total_messages': total_messages,
                'total_tool_calls': total_tool_calls,
                'unique_projects': unique_projects
            }
        except sqlite3.OperationalError:
            return {'error': 'session_archives table not found'}
        finally:
            conn.close()

    # Keep the original markdown generation for backward compatibility

