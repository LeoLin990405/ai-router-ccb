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


class MemoryV2MessagesMixin:
    """Mixin methods extracted from CCBMemoryV2."""

    def record_message(
        self,
        role: str,
        content: str,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        request_id: Optional[str] = None,
        latency_ms: Optional[int] = None,
        tokens: int = 0,
        context_injected: bool = False,
        context_count: int = 0,
        skills_used: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        session_id: Optional[str] = None
    ) -> str:
        """Record a message in the current session

        Args:
            role: 'user' | 'assistant' | 'system'
            content: Message content
            provider: AI provider (kimi, codex, etc.)
            model: Model name
            request_id: Gateway request ID
            latency_ms: Response latency
            tokens: Token count
            context_injected: Whether context was injected
            context_count: Number of injected memories
            skills_used: List of skills used
            metadata: Additional metadata
            session_id: Optional session ID (uses current if None)

        Returns:
            message_id: UUID of the recorded message
        """
        # Ensure we have a session
        if session_id is None:
            if self.current_session_id is None:
                session_id = self.create_session()
            else:
                session_id = self.current_session_id
        else:
            session_id = self.get_or_create_session(session_id)

        message_id = str(uuid.uuid4())
        now = datetime.now().isoformat()

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Get next sequence number
        cursor.execute("""
            SELECT COALESCE(MAX(sequence), 0) + 1
            FROM messages
            WHERE session_id = ?
        """, (session_id,))
        sequence = cursor.fetchone()[0]

        # Insert message
        cursor.execute("""
            INSERT INTO messages (
                message_id, session_id, request_id, sequence,
                role, content, provider, model,
                timestamp, latency_ms, tokens,
                context_injected, context_count, skills_used,
                metadata
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            message_id, session_id, request_id, sequence,
            role, content, provider, model,
            now, latency_ms, tokens,
            1 if context_injected else 0, context_count,
            json.dumps(skills_used or []),
            json.dumps(metadata or {})
        ))

        conn.commit()
        conn.close()

        return message_id

    def record_conversation(
        self,
        provider: str,
        question: str,
        answer: str,
        request_id: Optional[str] = None,
        model: Optional[str] = None,
        latency_ms: Optional[int] = None,
        tokens: int = 0,
        context_injected: bool = False,
        context_count: int = 0,
        skills_used: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        session_id: Optional[str] = None
    ) -> Dict[str, str]:
        """Record a complete conversation (user + assistant)

        Args:
            provider: AI provider
            question: User question
            answer: Assistant answer
            request_id: Gateway request ID
            model: Model name
            latency_ms: Response latency
            tokens: Token count
            context_injected: Whether context was injected
            context_count: Number of injected memories
            skills_used: List of skills used
            metadata: Additional metadata
            session_id: Optional session ID

        Returns:
            Dict with user_message_id and assistant_message_id
        """
        # Record user message
        user_message_id = self.record_message(
            role="user",
            content=question,
            request_id=request_id,
            session_id=session_id
        )

        # Record assistant message
        assistant_message_id = self.record_message(
            role="assistant",
            content=answer,
            provider=provider,
            model=model,
            request_id=request_id,
            latency_ms=latency_ms,
            tokens=tokens,
            context_injected=context_injected,
            context_count=context_count,
            skills_used=skills_used,
            metadata=metadata,
            session_id=self.current_session_id  # Use same session
        )

        return {
            "user_message_id": user_message_id,
            "assistant_message_id": assistant_message_id,
            "session_id": self.current_session_id
        }

    # ========================================================================
    # Context Injection Tracking
    # ========================================================================

    def record_context_injection(
        self,
        message_id: str,
        injection_type: str,
        reference_id: Optional[str] = None,
        relevance_score: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Record context injection for a message

        Args:
            message_id: Target message ID
            injection_type: 'memory' | 'skill' | 'provider' | 'mcp'
            reference_id: Reference to injected content
            relevance_score: Relevance score
            metadata: Additional metadata
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO context_injections (
                message_id, injection_type, reference_id, relevance_score, metadata
            ) VALUES (?, ?, ?, ?, ?)
        """, (
            message_id, injection_type, reference_id, relevance_score,
            json.dumps(metadata or {})
        ))

        conn.commit()
        conn.close()

    # ========================================================================
    # Search and Retrieval
    # ========================================================================

    def search_messages(
        self,
        query: str,
        limit: int = 10,
        provider: Optional[str] = None,
        session_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Search messages using FTS5

        Args:
            query: Search query
            limit: Maximum results
            provider: Filter by provider
            session_id: Filter by session

        Returns:
            List of matching messages
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        sql = """
            SELECT m.message_id, m.session_id, m.role, m.content,
                   m.provider, m.timestamp, m.tokens
            FROM messages m
            JOIN messages_fts fts ON m.rowid = fts.rowid
            WHERE messages_fts MATCH ?
        """
        params = [query]

        if provider:
            sql += " AND m.provider = ?"
            params.append(provider)

        if session_id:
            sql += " AND m.session_id = ?"
            params.append(session_id)

        sql += " ORDER BY m.timestamp DESC LIMIT ?"
        params.append(limit)

        cursor.execute(sql, params)

        columns = [desc[0] for desc in cursor.description]
        messages = []
        for row in cursor.fetchall():
            messages.append(dict(zip(columns, row)))

        conn.close()
        return messages

    def get_session_context(
        self,
        session_id: str,
        window_size: int = 10
    ) -> List[Dict[str, Any]]:
        """Get recent context for a session

        Args:
            session_id: Session ID
            window_size: Number of recent messages

        Returns:
            List of recent messages in chronological order
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT message_id, role, content, provider, timestamp
            FROM messages
            WHERE session_id = ?
            ORDER BY sequence DESC
            LIMIT ?
        """, (session_id, window_size))

        columns = [desc[0] for desc in cursor.description]
        messages = []
        for row in cursor.fetchall():
            messages.append(dict(zip(columns, row)))

        conn.close()

        # Return in chronological order
        return list(reversed(messages))

    # ========================================================================
    # Statistics and Analytics
    # ========================================================================

    def get_stats(self) -> Dict[str, Any]:
        """Get memory statistics for current user

        Returns:
            Statistics dictionary
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Session stats
        cursor.execute("""
            SELECT COUNT(*) FROM sessions WHERE user_id = ?
        """, (self.user_id,))
        total_sessions = cursor.fetchone()[0]

        # Message stats
        cursor.execute("""
            SELECT COUNT(*) FROM messages m
            JOIN sessions s ON m.session_id = s.session_id
            WHERE s.user_id = ?
        """, (self.user_id,))
        total_messages = cursor.fetchone()[0]

        # Token stats
        cursor.execute("""
            SELECT SUM(tokens) FROM messages m
            JOIN sessions s ON m.session_id = s.session_id
            WHERE s.user_id = ?
        """, (self.user_id,))
        total_tokens = cursor.fetchone()[0] or 0

        # Provider stats
        cursor.execute("""
            SELECT * FROM provider_stats ORDER BY total_requests DESC
        """)
        columns = [desc[0] for desc in cursor.description]
        provider_stats = []
        for row in cursor.fetchall():
            provider_stats.append(dict(zip(columns, row)))

        conn.close()

        return {
            "user_id": self.user_id,
            "total_sessions": total_sessions,
            "total_messages": total_messages,
            "total_tokens": total_tokens,
            "provider_stats": provider_stats
        }

    # ========================================================================
    # Observations CRUD (Phase 2: Write APIs)
    # ========================================================================

