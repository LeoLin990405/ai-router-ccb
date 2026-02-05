#!/usr/bin/env python3
"""
CCB Memory System v2.0 - Redesigned for CCB Gateway Architecture

按照 CCB 设计理念重构的记忆系统：
- Session-based: 会话导向
- Request-aware: 请求追踪
- Context-linked: 上下文链接
- Multi-user: 多用户隔离
- Partitioned: 分区存储
"""

import sqlite3
import json
import uuid
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime
import gzip


class CCBMemoryV2:
    """CCB Memory System v2.0"""

    def __init__(self, db_path: str = None, user_id: str = "default"):
        """Initialize CCB Memory v2

        Args:
            db_path: Path to database (default: ~/.ccb/ccb_memory_v2.db)
            user_id: User ID for multi-user isolation
        """
        if db_path is None:
            db_path = Path.home() / ".ccb" / "ccb_memory.db"  # 使用主数据库路径
        else:
            db_path = Path(db_path)

        self.db_path = db_path
        self.user_id = user_id
        self.current_session_id = None

        # Ensure directory exists
        db_path.parent.mkdir(parents=True, exist_ok=True)

        # Initialize database
        self._init_db()

    def _init_db(self):
        """Initialize database with v2 schema"""
        conn = sqlite3.connect(self.db_path)

        # Read and execute schema
        schema_file = Path(__file__).parent / "schema_v2.sql"
        if schema_file.exists():
            with open(schema_file) as f:
                conn.executescript(f.read())
        else:
            print(f"[CCBMemoryV2] Warning: schema_v2.sql not found")

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

    def create_observation(
        self,
        content: str,
        category: str = "note",
        tags: List[str] = None,
        source: str = "manual",
        confidence: float = 1.0,
        metadata: Dict[str, Any] = None
    ) -> str:
        """Create a new observation

        Args:
            content: Observation content
            category: Category ('insight', 'preference', 'fact', 'note')
            tags: List of tags
            source: Source ('manual', 'llm_extracted', 'consolidator')
            confidence: Confidence score 0-1
            metadata: Additional metadata

        Returns:
            observation_id: UUID of created observation
        """
        observation_id = str(uuid.uuid4())
        now = datetime.now().isoformat()

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            cursor.execute("""
                INSERT INTO observations (
                    observation_id, user_id, category, content, tags,
                    source, confidence, created_at, updated_at, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                observation_id,
                self.user_id,
                category,
                content,
                json.dumps(tags or []),
                source,
                confidence,
                now,
                now,
                json.dumps(metadata or {})
            ))

            conn.commit()
            return observation_id
        finally:
            conn.close()

    def get_observation(self, observation_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific observation

        Args:
            observation_id: Observation ID

        Returns:
            Observation dict or None
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            cursor.execute("""
                SELECT * FROM observations
                WHERE observation_id = ? AND user_id = ?
            """, (observation_id, self.user_id))

            row = cursor.fetchone()
            if not row:
                return None

            columns = [desc[0] for desc in cursor.description]
            result = dict(zip(columns, row))

            # Parse JSON fields
            result['tags'] = json.loads(result.get('tags', '[]'))
            result['metadata'] = json.loads(result.get('metadata', '{}'))

            return result
        finally:
            conn.close()

    def update_observation(
        self,
        observation_id: str,
        content: str = None,
        category: str = None,
        tags: List[str] = None,
        confidence: float = None,
        metadata: Dict[str, Any] = None
    ) -> bool:
        """Update an existing observation

        Args:
            observation_id: Observation ID
            content: New content (optional)
            category: New category (optional)
            tags: New tags (optional)
            confidence: New confidence (optional)
            metadata: New metadata (optional)

        Returns:
            True if updated successfully
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            # Build dynamic update query
            updates = []
            params = []

            if content is not None:
                updates.append("content = ?")
                params.append(content)
            if category is not None:
                updates.append("category = ?")
                params.append(category)
            if tags is not None:
                updates.append("tags = ?")
                params.append(json.dumps(tags))
            if confidence is not None:
                updates.append("confidence = ?")
                params.append(confidence)
            if metadata is not None:
                updates.append("metadata = ?")
                params.append(json.dumps(metadata))

            if not updates:
                return False

            updates.append("updated_at = ?")
            params.append(datetime.now().isoformat())

            params.extend([observation_id, self.user_id])

            cursor.execute(f"""
                UPDATE observations
                SET {', '.join(updates)}
                WHERE observation_id = ? AND user_id = ?
            """, params)

            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def delete_observation(self, observation_id: str) -> bool:
        """Delete an observation

        Args:
            observation_id: Observation ID

        Returns:
            True if deleted successfully
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            cursor.execute("""
                DELETE FROM observations
                WHERE observation_id = ? AND user_id = ?
            """, (observation_id, self.user_id))

            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def search_observations(
        self,
        query: str = None,
        category: str = None,
        tags: List[str] = None,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """Search observations

        Args:
            query: Full-text search query (optional)
            category: Filter by category (optional)
            tags: Filter by tags (optional)
            limit: Maximum results

        Returns:
            List of observations
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            if query:
                # FTS5 search
                sql = """
                    SELECT o.* FROM observations o
                    JOIN observations_fts fts ON o.rowid = fts.rowid
                    WHERE observations_fts MATCH ? AND o.user_id = ?
                """
                params = [query, self.user_id]
            else:
                sql = "SELECT * FROM observations WHERE user_id = ?"
                params = [self.user_id]

            if category:
                sql += " AND category = ?"
                params.append(category)

            sql += " ORDER BY created_at DESC LIMIT ?"
            params.append(limit)

            cursor.execute(sql, params)

            columns = [desc[0] for desc in cursor.description]
            results = []
            for row in cursor.fetchall():
                result = dict(zip(columns, row))
                result['tags'] = json.loads(result.get('tags', '[]'))
                result['metadata'] = json.loads(result.get('metadata', '{}'))

                # Filter by tags if specified
                if tags:
                    if not any(t in result['tags'] for t in tags):
                        continue

                results.append(result)

            return results
        finally:
            conn.close()

    def list_observations(
        self,
        category: str = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """List observations for current user

        Args:
            category: Optional category filter
            limit: Maximum results

        Returns:
            List of observations
        """
        return self.search_observations(category=category, limit=limit)

    # ========================================================================
    # Discussion Memory (Phase 6)
    # ========================================================================

    def record_discussion(
        self,
        session_id: str,
        topic: str,
        providers: List[str],
        summary: str = None,
        insights: List[Dict[str, Any]] = None,
        messages: List[Dict[str, Any]] = None,
        metadata: Dict[str, Any] = None
    ) -> str:
        """Record a multi-AI discussion to memory

        Args:
            session_id: Discussion session ID
            topic: Discussion topic
            providers: List of participating providers
            summary: Discussion summary
            insights: List of extracted insights
            messages: Discussion messages (optional, can be large)
            metadata: Additional metadata

        Returns:
            observation_id: ID of created observation
        """
        # Create an observation for the discussion
        content_parts = [f"Discussion: {topic}"]

        if summary:
            content_parts.append(f"\nSummary: {summary}")

        if insights:
            content_parts.append("\nKey Insights:")
            for insight in insights[:5]:  # Limit to 5 insights
                if isinstance(insight, dict):
                    content_parts.append(f"- {insight.get('content', insight)}")
                else:
                    content_parts.append(f"- {insight}")

        content = "\n".join(content_parts)

        # Build metadata
        full_metadata = {
            "type": "discussion",
            "discussion_session_id": session_id,
            "providers": providers,
            "provider_count": len(providers),
            "has_messages": messages is not None,
            "message_count": len(messages) if messages else 0,
            **(metadata or {})
        }

        # Optionally store messages if not too large
        if messages and len(json.dumps(messages)) < 50000:
            full_metadata["messages_sample"] = messages[:10]

        observation_id = self.create_observation(
            content=content,
            category="discussion",
            tags=["multi-ai", "discussion", *providers],
            source="discussion",
            confidence=0.95,
            metadata=full_metadata
        )

        return observation_id

    def get_discussion_memory(
        self,
        discussion_session_id: str = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Get discussion memories

        Args:
            discussion_session_id: Filter by specific discussion session
            limit: Maximum results

        Returns:
            List of discussion observations
        """
        observations = self.search_observations(
            category="discussion",
            limit=limit
        )

        if discussion_session_id:
            observations = [
                obs for obs in observations
                if obs.get("metadata", {}).get("discussion_session_id") == discussion_session_id
            ]

        return observations

    # ========================================================================
    # Request Memory Tracking (Phase 1: Transparency)
    # ========================================================================

    def track_request_injection(
        self,
        request_id: str,
        provider: str,
        original_message: str,
        injected_memory_ids: List[str] = None,
        injected_skills: List[str] = None,
        injected_system_context: bool = False,
        relevance_scores: Dict[str, float] = None,
        session_id: str = None,
        metadata: Dict[str, Any] = None
    ) -> bool:
        """Track what was injected into a request

        Args:
            request_id: Gateway request ID
            provider: Provider being used
            original_message: Original user message (before injection)
            injected_memory_ids: List of memory message_ids injected
            injected_skills: List of skill names recommended
            injected_system_context: Whether system context was injected
            relevance_scores: Dict of memory_id -> relevance score
            session_id: Optional session ID
            metadata: Additional metadata

        Returns:
            True if tracking succeeded
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            cursor.execute("""
                INSERT OR REPLACE INTO request_memory_map (
                    request_id, session_id, provider, original_message,
                    injected_memory_ids, injected_skills, injected_system_context,
                    injection_timestamp, memory_count, skills_count,
                    relevance_scores, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                request_id,
                session_id or self.current_session_id,
                provider,
                original_message,
                json.dumps(injected_memory_ids or []),
                json.dumps(injected_skills or []),
                1 if injected_system_context else 0,
                datetime.now().isoformat(),
                len(injected_memory_ids or []),
                len(injected_skills or []),
                json.dumps(relevance_scores or {}),
                json.dumps(metadata or {})
            ))

            conn.commit()
            return True
        except Exception as e:
            print(f"[CCBMemoryV2] track_request_injection error: {e}")
            return False
        finally:
            conn.close()

    def get_request_injection(self, request_id: str) -> Optional[Dict[str, Any]]:
        """Get injection details for a specific request

        Args:
            request_id: Gateway request ID

        Returns:
            Injection details or None
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            cursor.execute("""
                SELECT * FROM request_memory_map WHERE request_id = ?
            """, (request_id,))

            row = cursor.fetchone()
            if not row:
                return None

            columns = [desc[0] for desc in cursor.description]
            result = dict(zip(columns, row))

            # Parse JSON fields
            result['injected_memory_ids'] = json.loads(result.get('injected_memory_ids', '[]'))
            result['injected_skills'] = json.loads(result.get('injected_skills', '[]'))
            result['relevance_scores'] = json.loads(result.get('relevance_scores', '{}'))
            result['metadata'] = json.loads(result.get('metadata', '{}'))

            return result
        finally:
            conn.close()

    def get_request_injections(
        self,
        limit: int = 20,
        session_id: str = None
    ) -> List[Dict[str, Any]]:
        """Get recent request injections

        Args:
            limit: Maximum number of results
            session_id: Optional session filter

        Returns:
            List of injection records
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            if session_id:
                cursor.execute("""
                    SELECT * FROM request_memory_map
                    WHERE session_id = ?
                    ORDER BY injection_timestamp DESC
                    LIMIT ?
                """, (session_id, limit))
            else:
                cursor.execute("""
                    SELECT * FROM request_memory_map
                    ORDER BY injection_timestamp DESC
                    LIMIT ?
                """, (limit,))

            columns = [desc[0] for desc in cursor.description]
            results = []
            for row in cursor.fetchall():
                result = dict(zip(columns, row))
                # Parse JSON fields
                result['injected_memory_ids'] = json.loads(result.get('injected_memory_ids', '[]'))
                result['injected_skills'] = json.loads(result.get('injected_skills', '[]'))
                result['relevance_scores'] = json.loads(result.get('relevance_scores', '{}'))
                result['metadata'] = json.loads(result.get('metadata', '{}'))
                results.append(result)

            return results
        finally:
            conn.close()

    def get_injected_memories_for_request(self, request_id: str) -> List[Dict[str, Any]]:
        """Get full memory details for memories injected into a request

        Args:
            request_id: Gateway request ID

        Returns:
            List of memory messages that were injected
        """
        injection = self.get_request_injection(request_id)
        if not injection or not injection.get('injected_memory_ids'):
            return []

        memory_ids = injection['injected_memory_ids']
        if not memory_ids:
            return []

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            placeholders = ','.join(['?' for _ in memory_ids])
            cursor.execute(f"""
                SELECT message_id, session_id, role, content, provider, timestamp, tokens
                FROM messages
                WHERE message_id IN ({placeholders})
            """, memory_ids)

            columns = [desc[0] for desc in cursor.description]
            results = []
            for row in cursor.fetchall():
                result = dict(zip(columns, row))
                # Add relevance score if available
                result['relevance_score'] = injection['relevance_scores'].get(result['message_id'])
                results.append(result)

            return results
        finally:
            conn.close()

    # ========================================================================
    # Session Archival
    # ========================================================================

    def archive_session(self, session_id: str):
        """Archive old session to compressed storage

        Args:
            session_id: Session to archive
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Get session and messages
        cursor.execute("""
            SELECT s.*, COUNT(m.message_id) as message_count, SUM(m.tokens) as total_tokens
            FROM sessions s
            LEFT JOIN messages m ON s.session_id = m.session_id
            WHERE s.session_id = ?
            GROUP BY s.session_id
        """, (session_id,))

        session_data = cursor.fetchone()
        if not session_data:
            conn.close()
            return

        # Get all messages
        cursor.execute("""
            SELECT * FROM messages WHERE session_id = ?
            ORDER BY sequence
        """, (session_id,))

        messages = cursor.fetchall()

        # Compress and archive
        archive_data = {
            "session": session_data,
            "messages": messages
        }

        compressed = gzip.compress(json.dumps(archive_data).encode())

        cursor.execute("""
            INSERT INTO archived_sessions (
                session_id, user_id, created_at, archived_at,
                message_count, total_tokens, compressed_data
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            session_id,
            session_data[1],  # user_id
            session_data[2],  # created_at
            datetime.now().isoformat(),
            session_data[-2],  # message_count
            session_data[-1],  # total_tokens
            compressed
        ))

        # Delete from active tables
        cursor.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
        cursor.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))

        conn.commit()
        conn.close()


# Backward compatibility wrapper
class CCBLightMemory:
    """Backward compatibility wrapper for old memory_lite API"""

    def __init__(self, user_id: str = "leo"):
        self.v2 = CCBMemoryV2(user_id=user_id)

    def record_conversation(self, provider: str, question: str, answer: str,
                          metadata: Optional[Dict] = None, tokens: int = 0):
        """Backward compatible conversation recording"""
        return self.v2.record_conversation(
            provider=provider,
            question=question,
            answer=answer,
            tokens=tokens,
            metadata=metadata
        )

    def search_conversations(self, query: str, limit: int = 5,
                            provider: Optional[str] = None):
        """Backward compatible search"""
        messages = self.v2.search_messages(query, limit=limit*2, provider=provider)

        # Convert to old format
        results = []
        for msg in messages:
            if msg['role'] == 'assistant':
                results.append({
                    "id": msg['message_id'],
                    "timestamp": msg['timestamp'],
                    "provider": msg['provider'],
                    "question": "",  # Would need to fetch user message
                    "answer": msg['content'][:300],
                    "metadata": {}
                })

        return results[:limit]

    def get_stats(self):
        """Backward compatible stats"""
        return self.v2.get_stats()
