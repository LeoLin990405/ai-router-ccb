"""Auto-split mixins for HeuristicRetriever."""
from __future__ import annotations

import json
import math
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .heuristic_retriever_shared import logger


class HeuristicRetrieverOpsMixin:
    """Mixin methods extracted from HeuristicRetriever."""

    def _log_access_batch(
        self,
        memories: List[ScoredMemory],
        query: str,
        request_id: Optional[str],
        context: str
    ):
        """Log access for a batch of memories."""
        if not memories:
            return

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            now = datetime.now().isoformat()

            for memory in memories:
                cursor.execute("""
                    INSERT INTO memory_access_log
                    (memory_id, memory_type, accessed_at, access_context, request_id, query_text, relevance_score)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    memory.memory_id,
                    memory.memory_type,
                    now,
                    context,
                    request_id,
                    query[:500] if query else None,  # Truncate long queries
                    memory.relevance_score
                ))

            conn.commit()
        except sqlite3.OperationalError as e:
            logger.warning("Access logging error: %s", e)
        finally:
            conn.close()

    def set_importance(
        self,
        memory_id: str,
        memory_type: str,
        importance: float,
        source: str = 'user'
    ) -> bool:
        """
        Set importance score for a memory.

        Args:
            memory_id: Memory UUID
            memory_type: 'message' or 'observation'
            importance: Score between 0.0 and 1.0
            source: 'user', 'llm', or 'heuristic'

        Returns:
            True if successful
        """
        importance = max(0.0, min(1.0, importance))  # Clamp to 0-1

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
        except sqlite3.OperationalError as e:
            logger.warning("Set importance error: %s", e)
            return False
        finally:
            conn.close()

    def boost_importance(
        self,
        memory_id: str,
        memory_type: str,
        boost: Optional[float] = None
    ) -> float:
        """
        Boost importance score for a memory (e.g., on user interaction).

        Args:
            memory_id: Memory UUID
            memory_type: 'message' or 'observation'
            boost: Amount to boost (default from config)

        Returns:
            New importance score
        """
        boost = boost or self.config.access_boost

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            # Get current importance
            cursor.execute("""
                SELECT importance_score FROM memory_importance
                WHERE memory_id = ? AND memory_type = ?
            """, (memory_id, memory_type))

            row = cursor.fetchone()
            current = row[0] if row else self.config.default_importance

            # Calculate new importance (capped at 1.0)
            new_importance = min(1.0, current + boost)

            # Update
            now = datetime.now().isoformat()
            cursor.execute("""
                INSERT INTO memory_importance
                (memory_id, memory_type, importance_score, score_source, updated_at)
                VALUES (?, ?, ?, 'heuristic', ?)
                ON CONFLICT(memory_id) DO UPDATE SET
                    importance_score = ?,
                    updated_at = ?
            """, (memory_id, memory_type, new_importance, now, new_importance, now))

            conn.commit()
            return new_importance
        except sqlite3.OperationalError as e:
            logger.warning("Boost importance error: %s", e)
            return self.config.default_importance
        finally:
            conn.close()

    def get_statistics(self) -> Dict[str, Any]:
        """Get retrieval system statistics."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            stats = {}

            # Total tracked memories
            cursor.execute("SELECT COUNT(*) FROM memory_importance")
            stats['tracked_memories'] = cursor.fetchone()[0]

            # By type
            cursor.execute("""
                SELECT memory_type, COUNT(*)
                FROM memory_importance
                GROUP BY memory_type
            """)
            stats['by_type'] = dict(cursor.fetchall())

            # Importance distribution
            cursor.execute("""
                SELECT
                    SUM(CASE WHEN importance_score >= 0.8 THEN 1 ELSE 0 END) as high,
                    SUM(CASE WHEN importance_score >= 0.5 AND importance_score < 0.8 THEN 1 ELSE 0 END) as medium,
                    SUM(CASE WHEN importance_score < 0.5 THEN 1 ELSE 0 END) as low
                FROM memory_importance
            """)
            row = cursor.fetchone()
            stats['importance_distribution'] = {
                'high': row[0] or 0,
                'medium': row[1] or 0,
                'low': row[2] or 0
            }

            # Recent accesses
            cursor.execute("""
                SELECT COUNT(*) FROM memory_access_log
                WHERE accessed_at > datetime('now', '-24 hours')
            """)
            stats['accesses_24h'] = cursor.fetchone()[0]

            # Total accesses
            cursor.execute("SELECT COUNT(*) FROM memory_access_log")
            stats['total_accesses'] = cursor.fetchone()[0]

            # Average access count
            cursor.execute("SELECT AVG(access_count) FROM memory_importance")
            stats['avg_access_count'] = cursor.fetchone()[0] or 0

            # Config
            stats['config'] = {
                'alpha': self.config.alpha,
                'beta': self.config.beta,
                'gamma': self.config.gamma,
                'decay_lambda': self.config.decay_lambda
            }

            return stats

        except sqlite3.OperationalError as e:
            return {'error': str(e)}
        finally:
            conn.close()


# Convenience function for quick retrieval

