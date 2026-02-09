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


class MemoryV2ImportanceMixin:
    """Mixin methods extracted from CCBMemoryV2."""

    def log_access(
        self,
        memory_id: str,
        memory_type: str,
        access_context: str = 'retrieval',
        request_id: Optional[str] = None,
        query_text: Optional[str] = None,
        relevance_score: Optional[float] = None
    ) -> bool:
        """Log an access event for a memory (updates recency).

        Args:
            memory_id: UUID of the memory
            memory_type: 'message' or 'observation'
            access_context: 'retrieval', 'injection', 'user_view', 'search'
            request_id: Gateway request ID (optional)
            query_text: Query that triggered access (optional)
            relevance_score: Relevance score at access time (optional)

        Returns:
            True if logged successfully
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            now = datetime.now().isoformat()

            cursor.execute("""
                INSERT INTO memory_access_log
                (memory_id, memory_type, accessed_at, access_context, request_id, query_text, relevance_score)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                memory_id,
                memory_type,
                now,
                access_context,
                request_id,
                query_text[:500] if query_text else None,
                relevance_score
            ))

            conn.commit()
            return True
        except MEMORY_V2_ERRORS as e:
            logger.warning("log_access error: %s", e)
            return False
        finally:
            conn.close()

    def set_importance(
        self,
        memory_id: str,
        memory_type: str,
        importance: float,
        source: str = 'user'
    ) -> bool:
        """Set importance score for a memory.

        Args:
            memory_id: UUID of the memory
            memory_type: 'message' or 'observation'
            importance: Score between 0.0 and 1.0
            source: 'user', 'llm', 'heuristic', or 'default'

        Returns:
            True if set successfully
        """
        importance = max(0.0, min(1.0, importance))

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            now = datetime.now().isoformat()

            cursor.execute("""
                INSERT INTO memory_importance
                (memory_id, memory_type, importance_score, score_source, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(memory_id) DO UPDATE SET
                    importance_score = excluded.importance_score,
                    score_source = excluded.score_source,
                    updated_at = excluded.updated_at
            """, (memory_id, memory_type, importance, source, now, now))

            conn.commit()
            return True
        except MEMORY_V2_ERRORS as e:
            logger.warning("set_importance error: %s", e)
            return False
        finally:
            conn.close()

    def get_importance(self, memory_id: str, memory_type: str) -> Dict[str, Any]:
        """Get importance and access data for a memory.

        Args:
            memory_id: UUID of the memory
            memory_type: 'message' or 'observation'

        Returns:
            Dict with importance_score, access_count, last_accessed_at, decay_rate
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            cursor.execute("""
                SELECT importance_score, access_count, last_accessed_at, decay_rate
                FROM memory_importance
                WHERE memory_id = ? AND memory_type = ?
            """, (memory_id, memory_type))

            row = cursor.fetchone()
            if row:
                return {
                    'importance_score': row[0] or 0.5,
                    'access_count': row[1] or 0,
                    'last_accessed_at': row[2],
                    'decay_rate': row[3] or 0.1
                }

            return {
                'importance_score': 0.5,
                'access_count': 0,
                'last_accessed_at': None,
                'decay_rate': 0.1
            }
        except MEMORY_V2_ERRORS as e:
            logger.warning("get_importance error: %s", e)
            return {
                'importance_score': 0.5,
                'access_count': 0,
                'last_accessed_at': None,
                'decay_rate': 0.1
            }
        finally:
            conn.close()

    def mark_for_forgetting(
        self,
        memory_id: str,
        memory_type: str,
        reason: str = 'manual'
    ) -> bool:
        """Mark a memory for forgetting (System 2 will clean up).

        Args:
            memory_id: UUID of the memory
            memory_type: 'message' or 'observation'
            reason: Reason for forgetting

        Returns:
            True if marked successfully
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            now = datetime.now().isoformat()

            # Set importance to 0 to trigger forgetting
            cursor.execute("""
                INSERT INTO memory_importance
                (memory_id, memory_type, importance_score, score_source, created_at, updated_at)
                VALUES (?, ?, 0.0, 'forget', ?, ?)
                ON CONFLICT(memory_id) DO UPDATE SET
                    importance_score = 0.0,
                    score_source = 'forget',
                    updated_at = ?
            """, (memory_id, memory_type, now, now, now))

            # Log the action
            cursor.execute("""
                INSERT INTO consolidation_log
                (consolidation_type, source_ids, status, metadata, created_at)
                VALUES ('forget', ?, 'pending', ?, ?)
            """, (
                json.dumps([memory_id]),
                json.dumps({'reason': reason, 'memory_type': memory_type}),
                now
            ))

            conn.commit()
            return True
        except MEMORY_V2_ERRORS as e:
            logger.warning("mark_for_forgetting error: %s", e)
            return False
        finally:
            conn.close()

    def apply_decay(
        self,
        batch_size: int = 1000,
        min_importance: float = 0.01
    ) -> Dict[str, int]:
        """Apply time decay to all tracked memories.

        Note: This is primarily informational - recency is calculated
        dynamically during retrieval. This method updates stored values
        for reporting purposes.

        Args:
            batch_size: Number of memories to process per batch
            min_importance: Memories below this are flagged for forgetting

        Returns:
            Dict with counts: updated, flagged_for_forget
        """
        import math
        from datetime import datetime

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        stats = {'updated': 0, 'flagged_for_forget': 0}

        try:
            # Get all memories with access data
            cursor.execute("""
                SELECT memory_id, memory_type, last_accessed_at, decay_rate, importance_score
                FROM memory_importance
                WHERE last_accessed_at IS NOT NULL
                LIMIT ?
            """, (batch_size,))

            rows = cursor.fetchall()
            now = datetime.now()

            for row in rows:
                memory_id, memory_type, last_accessed, decay_rate, importance = row

                if not last_accessed:
                    continue

                # Calculate hours since access
                try:
                    if 'T' in last_accessed:
                        dt = datetime.fromisoformat(last_accessed.replace('Z', '+00:00'))
                    else:
                        dt = datetime.strptime(last_accessed, "%Y-%m-%d %H:%M:%S")
                    hours = (now - dt.replace(tzinfo=None)).total_seconds() / 3600
                except (ValueError, TypeError):
                    hours = 168  # Default 1 week

                # Calculate decayed recency
                decay_rate = decay_rate or 0.1
                recency = math.exp(-decay_rate * hours)

                # Check if should flag for forgetting
                if recency < min_importance and importance < min_importance:
                    stats['flagged_for_forget'] += 1

                stats['updated'] += 1

            conn.commit()
            return stats

        except MEMORY_V2_ERRORS as e:
            logger.warning("apply_decay error: %s", e)
            return stats
        finally:
            conn.close()

    def search_with_scores(
        self,
        query: str,
        limit: int = 10,
        provider: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Search messages with heuristic scores (R/I/T).

        Uses the HeuristicRetriever for αR + βI + γT scoring.

        Args:
            query: Search query
            limit: Maximum results
            provider: Filter by provider

        Returns:
            List of messages with scores
        """
        try:
            from .heuristic_retriever import HeuristicRetriever

            retriever = HeuristicRetriever(db_path=self.db_path)
            results = retriever.retrieve(
                query,
                limit=limit,
                memory_types=['message'],
                provider=provider
            )

            return [
                {
                    'message_id': m.memory_id,
                    'content': m.content,
                    'provider': m.provider,
                    'timestamp': m.timestamp,
                    'role': m.role,
                    'session_id': m.session_id,
                    # Scores
                    'relevance_score': m.relevance_score,
                    'importance_score': m.importance_score,
                    'recency_score': m.recency_score,
                    'final_score': m.final_score,
                    # Access data
                    'access_count': m.access_count,
                    'last_accessed_at': m.last_accessed_at
                }
                for m in results
            ]
        except ImportError:
            # Fall back to basic search
            return self.search_messages(query, limit=limit, provider=provider)
        except MEMORY_V2_ERRORS as e:
            logger.warning("search_with_scores error: %s", e)
            return self.search_messages(query, limit=limit, provider=provider)

    def get_memory_stats_v2(self) -> Dict[str, Any]:
        """Get extended statistics including heuristic system metrics.

        Returns:
            Extended statistics dictionary
        """
        base_stats = self.get_stats()

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            # Heuristic system stats
            heuristic_stats = {}

            # Tracked memories
            try:
                cursor.execute("SELECT COUNT(*) FROM memory_importance")
                heuristic_stats['tracked_memories'] = cursor.fetchone()[0]
            except sqlite3.OperationalError:
                heuristic_stats['tracked_memories'] = 0

            # By importance level
            try:
                cursor.execute("""
                    SELECT
                        SUM(CASE WHEN importance_score >= 0.8 THEN 1 ELSE 0 END) as high,
                        SUM(CASE WHEN importance_score >= 0.5 AND importance_score < 0.8 THEN 1 ELSE 0 END) as medium,
                        SUM(CASE WHEN importance_score < 0.5 THEN 1 ELSE 0 END) as low
                    FROM memory_importance
                """)
                row = cursor.fetchone()
                heuristic_stats['importance_distribution'] = {
                    'high': row[0] or 0,
                    'medium': row[1] or 0,
                    'low': row[2] or 0
                }
            except sqlite3.OperationalError:
                heuristic_stats['importance_distribution'] = {'high': 0, 'medium': 0, 'low': 0}

            # Access logs
            try:
                cursor.execute("SELECT COUNT(*) FROM memory_access_log")
                heuristic_stats['total_accesses'] = cursor.fetchone()[0]

                cursor.execute("""
                    SELECT COUNT(*) FROM memory_access_log
                    WHERE accessed_at > datetime('now', '-24 hours')
                """)
                heuristic_stats['accesses_24h'] = cursor.fetchone()[0]
            except sqlite3.OperationalError:
                heuristic_stats['total_accesses'] = 0
                heuristic_stats['accesses_24h'] = 0

            # Consolidation logs
            try:
                cursor.execute("SELECT COUNT(*) FROM consolidation_log")
                heuristic_stats['total_consolidations'] = cursor.fetchone()[0]
            except sqlite3.OperationalError:
                heuristic_stats['total_consolidations'] = 0

            base_stats['heuristic'] = heuristic_stats
            return base_stats

        finally:
            conn.close()


