"""Auto-split mixins for HeuristicRetriever."""
from __future__ import annotations

import json
import math
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .heuristic_retriever_shared import logger


try:
    from .heuristic_retriever import ScoredMemory
except ImportError:  # pragma: no cover - script mode
    from heuristic_retriever import ScoredMemory


class HeuristicRetrieverSearchMixin:
    """Mixin methods extracted from HeuristicRetriever."""

    def _search_messages_fts(
        self,
        query: str,
        limit: int = 50,
        provider: Optional[str] = None,
        session_id: Optional[str] = None
    ) -> List[ScoredMemory]:
        """Search messages using FTS5."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            # Build query with optional filters
            sql = """
                SELECT
                    m.message_id,
                    m.session_id,
                    m.role,
                    m.content,
                    m.provider,
                    m.timestamp,
                    m.tokens,
                    bm25(messages_fts) as fts_rank
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

            sql += " ORDER BY fts_rank LIMIT ?"
            params.append(limit)

            cursor.execute(sql, params)

            results = []
            for row in cursor.fetchall():
                # Normalize FTS rank to 0-1 (bm25 returns negative values, lower is better)
                fts_rank = row[7]
                # Convert BM25 score: higher negative means more relevant
                # Typical range is -25 to 0, so normalize
                relevance = min(1.0, max(0.0, (25 + fts_rank) / 25)) if fts_rank else 0.5

                memory = ScoredMemory(
                    memory_id=row[0],
                    memory_type='message',
                    content=row[3] or '',
                    relevance_score=relevance,
                    session_id=row[1],
                    role=row[2],
                    provider=row[4],
                    timestamp=row[5],
                    raw_data={
                        'tokens': row[6],
                        'fts_rank': fts_rank
                    }
                )
                results.append(memory)

            return results

        except sqlite3.OperationalError as e:
            logger.warning("FTS search error: %s", e)
            return []
        finally:
            conn.close()

    def _search_observations_fts(
        self,
        query: str,
        limit: int = 50
    ) -> List[ScoredMemory]:
        """Search observations using FTS5."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            sql = """
                SELECT
                    o.observation_id,
                    o.category,
                    o.content,
                    o.tags,
                    o.source,
                    o.confidence,
                    o.created_at,
                    bm25(observations_fts) as fts_rank
                FROM observations o
                JOIN observations_fts fts ON o.rowid = fts.rowid
                WHERE observations_fts MATCH ?
                ORDER BY fts_rank
                LIMIT ?
            """

            cursor.execute(sql, [query, limit])

            results = []
            for row in cursor.fetchall():
                fts_rank = row[7]
                relevance = min(1.0, max(0.0, (25 + fts_rank) / 25)) if fts_rank else 0.5

                # Parse tags
                try:
                    tags = json.loads(row[3]) if row[3] else []
                except json.JSONDecodeError:
                    tags = []

                memory = ScoredMemory(
                    memory_id=row[0],
                    memory_type='observation',
                    content=row[2] or '',
                    relevance_score=relevance,
                    category=row[1],
                    tags=tags,
                    timestamp=row[6],
                    raw_data={
                        'source': row[4],
                        'confidence': row[5],
                        'fts_rank': fts_rank
                    }
                )
                results.append(memory)

            return results

        except sqlite3.OperationalError as e:
            logger.warning("Observations FTS error: %s", e)
            return []
        finally:
            conn.close()

    def _get_importance_data(self, memory_id: str, memory_type: str) -> Dict[str, Any]:
        """Get importance and access data for a memory."""
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
                    'importance_score': row[0] or self.config.default_importance,
                    'access_count': row[1] or 0,
                    'last_accessed_at': row[2],
                    'decay_rate': row[3] or self.config.decay_lambda
                }

            return {
                'importance_score': self.config.default_importance,
                'access_count': 0,
                'last_accessed_at': None,
                'decay_rate': self.config.decay_lambda
            }

        except sqlite3.OperationalError:
            return {
                'importance_score': self.config.default_importance,
                'access_count': 0,
                'last_accessed_at': None,
                'decay_rate': self.config.decay_lambda
            }
        finally:
            conn.close()

    def _calculate_recency(self, last_accessed_at: Optional[str]) -> float:
        """
        Calculate recency score using Ebbinghaus forgetting curve.

        Formula: recency = exp(-λ × hours_since_access)

        Args:
            last_accessed_at: ISO 8601 timestamp of last access

        Returns:
            Recency score between min_recency and 1.0
        """
        if not last_accessed_at:
            # Never accessed - treat as 1 week old
            hours_since = 168
        else:
            try:
                # Parse timestamp
                if 'T' in last_accessed_at:
                    dt = datetime.fromisoformat(last_accessed_at.replace('Z', '+00:00'))
                else:
                    dt = datetime.strptime(last_accessed_at, "%Y-%m-%d %H:%M:%S")

                delta = datetime.now() - dt.replace(tzinfo=None)
                hours_since = delta.total_seconds() / 3600
            except (ValueError, TypeError):
                hours_since = 168  # Default to 1 week

        # Apply Ebbinghaus decay
        recency = math.exp(-self.config.decay_lambda * hours_since)

        # Clamp to minimum
        return max(self.config.min_recency, recency)

