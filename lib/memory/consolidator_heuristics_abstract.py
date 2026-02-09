"""Auto-split mixin methods for NightlyConsolidator."""
from __future__ import annotations

import asyncio
import json
import math
import re
import sqlite3
import uuid
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from .consolidator_models import SessionArchive
from .consolidator_shared import CONSOLIDATOR_ERRORS, HAS_HTTPX, httpx, logger


class ConsolidatorHeuristicsAbstractMixin:
    """Mixin methods extracted from NightlyConsolidator."""

    async def abstract_memory_groups(self) -> Dict[str, Any]:
        """
        Create abstractions for large groups of related memories.

        Uses LLM to generate summaries for memory groups.

        Returns:
            Dict with abstraction statistics
        """
        system2_config = self.config.get("system2", {})
        min_group_size = system2_config.get("abstract_group_min_size", 5)

        stats = {"abstracted_count": 0, "groups_processed": 0}

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            # Find categories with many observations
            cursor.execute("""
                SELECT category, COUNT(*) as count
                FROM observations
                GROUP BY category
                HAVING count >= ?
            """, (min_group_size,))

            large_categories = cursor.fetchall()
            stats["groups_processed"] = len(large_categories)

            # For each large category, generate an abstract
            for category, count in large_categories:
                # Get sample observations from category
                cursor.execute("""
                    SELECT content FROM observations
                    WHERE category = ?
                    ORDER BY created_at DESC
                    LIMIT 10
                """, (category,))

                contents = [row[0] for row in cursor.fetchall()]

                # Generate abstract via LLM
                if HAS_HTTPX and contents:
                    abstract = await self._generate_abstract(category, contents)
                    if abstract:
                        self._save_abstract(cursor, category, abstract, count)
                        stats["abstracted_count"] += 1

            conn.commit()
            return stats

        except CONSOLIDATOR_ERRORS as e:
            logger.warning("abstract_memory_groups error: %s", e)
            return stats
        finally:
            conn.close()

    async def _generate_abstract(
        self,
        category: str,
        contents: List[str]
    ) -> Optional[str]:
        """Generate an abstract summary for a group of memories."""
        prompt = f"""总结以下关于 "{category}" 的记忆内容，生成一个简洁的摘要（不超过200字）：

{chr(10).join(['- ' + c[:200] for c in contents[:10]])}

请直接输出摘要内容，不需要额外的格式。"""

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{self.GATEWAY_URL}/api/ask",
                    params={"wait": "true", "timeout": "45"},
                    json={
                        "message": prompt,
                        "provider": self.llm_provider
                    }
                )

                if response.status_code == 200:
                    result = response.json()
                    return result.get("response", "")[:500]

        except CONSOLIDATOR_ERRORS as e:
            logger.warning("_generate_abstract error: %s", e)

        return None

    def _save_abstract(
        self,
        cursor: sqlite3.Cursor,
        category: str,
        abstract: str,
        source_count: int
    ):
        """Save an abstract as a new observation."""
        import uuid

        now = datetime.now().isoformat()
        abstract_id = str(uuid.uuid4())

        cursor.execute("""
            INSERT INTO observations
            (observation_id, user_id, category, content, tags, source, confidence, created_at, updated_at, metadata)
            VALUES (?, 'default', ?, ?, '["abstract", "summary"]', 'consolidator', 0.85, ?, ?, ?)
        """, (
            abstract_id,
            f"abstract_{category}",
            f"[摘要] {category}: {abstract}",
            now,
            now,
            json.dumps({"source_count": source_count, "original_category": category})
        ))

        # Log the abstraction
        cursor.execute("""
            INSERT INTO consolidation_log
            (consolidation_type, source_ids, result_id, llm_provider, status, created_at)
            VALUES ('abstract', ?, ?, ?, 'completed', ?)
        """, (json.dumps([category]), abstract_id, self.llm_provider, now))

    def forget_expired_memories(self, max_age_days: int = None) -> Dict[str, Any]:
        """
        Clean up memories that should be forgotten.

        Criteria:
        - importance_score < 0.01
        - age > max_age_days (default 90)
        - score_source = 'forget' (manually marked)

        Returns:
            Dict with forget statistics
        """
        decay_config = self.config.get("decay", {})
        max_age = max_age_days or decay_config.get("max_age_days", 90)

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        stats = {"forgotten_count": 0, "archived_count": 0}

        try:
            now = datetime.now().isoformat()

            # Find memories to forget
            cursor.execute("""
                SELECT mi.memory_id, mi.memory_type
                FROM memory_importance mi
                WHERE mi.importance_score < 0.01
                   OR mi.score_source = 'forget'
                   OR (mi.created_at < datetime('now', ?) AND mi.importance_score < 0.1)
            """, (f'-{max_age} days',))

            to_forget = cursor.fetchall()

            for memory_id, memory_type in to_forget:
                # Delete from importance table
                cursor.execute(
                    "DELETE FROM memory_importance WHERE memory_id = ?",
                    (memory_id,)
                )

                # For messages, we archive rather than delete
                if memory_type == 'message':
                    # Mark as archived in the session
                    cursor.execute("""
                        UPDATE messages SET metadata = json_set(
                            COALESCE(metadata, '{}'),
                            '$.archived', true,
                            '$.archived_at', ?
                        ) WHERE message_id = ?
                    """, (now, memory_id))
                    stats["archived_count"] += 1

                # For observations marked for forgetting, delete
                elif memory_type == 'observation':
                    cursor.execute(
                        "DELETE FROM observations WHERE observation_id = ?",
                        (memory_id,)
                    )
                    stats["forgotten_count"] += 1

            # Log the forgetting
            if to_forget:
                forgotten_ids = [m[0] for m in to_forget]
                cursor.execute("""
                    INSERT INTO consolidation_log
                    (consolidation_type, source_ids, status, metadata, created_at)
                    VALUES ('forget', ?, 'completed', ?, ?)
                """, (
                    json.dumps(forgotten_ids[:100]),  # Limit logged IDs
                    json.dumps({"total": len(to_forget)}),
                    now
                ))

            conn.commit()
            return stats

        except CONSOLIDATOR_ERRORS as e:
            logger.warning("forget_expired_memories error: %s", e)
            return stats
        finally:
            conn.close()

    def _log_consolidation(self, results: Dict[str, Any]):
        """Log the consolidation run to database."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            now = datetime.now().isoformat()

            cursor.execute("""
                INSERT INTO consolidation_log
                (consolidation_type, source_ids, status, metadata, created_at)
                VALUES ('nightly', '[]', ?, ?, ?)
            """, (results.get("status", "completed"), json.dumps(results), now))

            conn.commit()
        except CONSOLIDATOR_ERRORS as e:
            logger.warning("_log_consolidation error: %s", e)
        finally:
            conn.close()

    def get_consolidation_stats(self) -> Dict[str, Any]:
        """Get consolidation statistics."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        stats = {}

        try:
            # Total consolidations
            cursor.execute("SELECT COUNT(*) FROM consolidation_log")
            stats["total_consolidations"] = cursor.fetchone()[0]

            # By type
            cursor.execute("""
                SELECT consolidation_type, COUNT(*)
                FROM consolidation_log
                GROUP BY consolidation_type
            """)
            stats["by_type"] = dict(cursor.fetchall())

            # Recent activity
            cursor.execute("""
                SELECT COUNT(*) FROM consolidation_log
                WHERE created_at > datetime('now', '-7 days')
            """)
            stats["recent_7d"] = cursor.fetchone()[0]

            # Last consolidation
            cursor.execute("""
                SELECT created_at, consolidation_type, status
                FROM consolidation_log
                ORDER BY created_at DESC
                LIMIT 1
            """)
            row = cursor.fetchone()
            if row:
                stats["last_consolidation"] = {
                    "timestamp": row[0],
                    "type": row[1],
                    "status": row[2]
                }

        except sqlite3.OperationalError:
            stats["error"] = "consolidation_log table not found"

        conn.close()
        return stats


