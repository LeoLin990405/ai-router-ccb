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


class MemoryV2DiscussionMixin:
    """Mixin methods extracted from CCBMemoryV2."""

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
        except MEMORY_V2_ERRORS as e:
            logger.warning("track_request_injection error: %s", e)
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

