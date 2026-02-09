"""Auto-split mixins for Memory v2."""
from __future__ import annotations

import gzip
import json
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from .memory_v2_shared import MEMORY_V2_ERRORS, logger


class MemoryV2SessionMixin:
    """Mixin methods extracted from CCBMemoryV2."""

    def _init_db(self):
        """Initialize database with v2 schema"""
        conn = sqlite3.connect(self.db_path)

        # Read and execute schema
        schema_file = Path(__file__).parent / "schema_v2.sql"
        if schema_file.exists():
            with open(schema_file) as f:
                conn.executescript(f.read())
        else:
            logger.warning("schema_v2.sql not found")

        conn.commit()
        conn.close()

    # ========================================================================
    # Session Management
    # ========================================================================

    def create_session(self, metadata: Optional[Dict[str, Any]] = None) -> str:
        """Create a new session

        Args:
            metadata: Optional metadata (title, tags, project, etc.)

        Returns:
            session_id: UUID of the new session
        """
        session_id = str(uuid.uuid4())
        now = datetime.now().isoformat()

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO sessions (session_id, user_id, created_at, last_active, metadata)
            VALUES (?, ?, ?, ?, ?)
        """, (session_id, self.user_id, now, now, json.dumps(metadata or {})))

        conn.commit()
        conn.close()

        self.current_session_id = session_id
        return session_id

    def get_or_create_session(self, session_id: Optional[str] = None) -> str:
        """Get existing session or create new one

        Args:
            session_id: Optional session ID to use

        Returns:
            session_id: Active session ID
        """
        if session_id:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
                SELECT session_id FROM sessions
                WHERE session_id = ? AND user_id = ?
            """, (session_id, self.user_id))

            if cursor.fetchone():
                conn.close()
                self.current_session_id = session_id
                return session_id

            conn.close()

        # Create new session
        return self.create_session()

    def list_sessions(self, limit: int = 20) -> List[Dict[str, Any]]:
        """List recent sessions for current user

        Args:
            limit: Maximum number of sessions to return

        Returns:
            List of session dictionaries
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM session_overview
            WHERE user_id = ?
            ORDER BY last_active DESC
            LIMIT ?
        """, (self.user_id, limit))

        columns = [desc[0] for desc in cursor.description]
        sessions = []
        for row in cursor.fetchall():
            sessions.append(dict(zip(columns, row)))

        conn.close()
        return sessions

    # ========================================================================
    # Message Recording
    # ========================================================================

