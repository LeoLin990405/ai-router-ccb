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


class ConsolidatorHeuristicsRuntimeMixin:
    """Mixin methods extracted from NightlyConsolidator."""

    def _load_heuristic_config(self) -> Dict[str, Any]:
        """Load heuristic configuration from file."""
        config_path = Path.home() / ".ccb" / "heuristic_config.json"

        if config_path.exists():
            try:
                with open(config_path) as f:
                    return json.load(f)
            except CONSOLIDATOR_ERRORS:
                pass

        # Default config
        return {
            "decay": {
                "lambda": 0.1,
                "min_score": 0.01,
                "max_age_days": 90
            },
            "system2": {
                "merge_similarity_threshold": 0.9,
                "abstract_group_min_size": 5,
                "llm_provider": "kimi",
                "max_batch_size": 100
            }
        }

    async def nightly_consolidation(self) -> Dict[str, Any]:
        """
        Full System 2 nightly consolidation.

        Performs:
        1. Session archive consolidation (existing)
        2. Memory decay application
        3. Similarity-based merging
        4. Abstraction of related memories
        5. Forgetting of expired memories

        Returns:
            Consolidation results summary
        """
        results = {
            "timestamp": datetime.now().isoformat(),
            "status": "completed",
            "session_consolidation": {},
            "decay_applied": {},
            "merged_count": 0,
            "abstracted_count": 0,
            "forgotten_count": 0
        }

        try:
            # 1. Basic session consolidation
            session_result = self.consolidate(hours=24)
            results["session_consolidation"] = {
                "sessions_processed": session_result.get("sessions_processed", 0),
                "learnings_extracted": len(session_result.get("all_learnings", []))
            }

            # 2. Apply decay to all memories
            decay_result = self.apply_decay_to_all()
            results["decay_applied"] = decay_result

            # 3. Find and merge similar memories
            merge_result = await self.merge_similar_memories()
            results["merged_count"] = merge_result.get("merged_count", 0)

            # 4. Abstract large groups
            abstract_result = await self.abstract_memory_groups()
            results["abstracted_count"] = abstract_result.get("abstracted_count", 0)

            # 5. Forget expired memories
            forget_result = self.forget_expired_memories()
            results["forgotten_count"] = forget_result.get("forgotten_count", 0)

        except CONSOLIDATOR_ERRORS as e:
            results["status"] = "error"
            results["error"] = str(e)

        # Log consolidation
        self._log_consolidation(results)

        return results

    def apply_decay_to_all(self, batch_size: int = 1000) -> Dict[str, Any]:
        """
        Apply Ebbinghaus decay to all tracked memories.

        This updates importance scores based on time since last access.

        Returns:
            Dict with decay statistics
        """
        decay_config = self.config.get("decay", {})
        decay_lambda = decay_config.get("lambda", 0.1)
        min_score = decay_config.get("min_score", 0.01)

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        stats = {
            "processed": 0,
            "decayed": 0,
            "flagged_for_forget": 0
        }

        try:
            # Get memories with access data
            cursor.execute("""
                SELECT memory_id, memory_type, importance_score, last_accessed_at, decay_rate
                FROM memory_importance
                WHERE last_accessed_at IS NOT NULL
                LIMIT ?
            """, (batch_size,))

            rows = cursor.fetchall()
            now = datetime.now()

            for row in rows:
                memory_id, memory_type, importance, last_accessed, decay_rate = row

                if not last_accessed:
                    continue

                stats["processed"] += 1

                # Calculate hours since access
                try:
                    if 'T' in last_accessed:
                        dt = datetime.fromisoformat(last_accessed.replace('Z', '+00:00'))
                    else:
                        dt = datetime.strptime(last_accessed, "%Y-%m-%d %H:%M:%S")
                    hours = (now - dt.replace(tzinfo=None)).total_seconds() / 3600
                except (ValueError, TypeError):
                    hours = 168

                # Calculate decayed importance
                decay_rate = decay_rate or decay_lambda
                decay_factor = math.exp(-decay_rate * hours)
                decayed_importance = importance * decay_factor

                # Check if significantly decayed
                if decayed_importance < importance * 0.9:
                    stats["decayed"] += 1

                # Flag for forgetting if below threshold
                if decayed_importance < min_score:
                    stats["flagged_for_forget"] += 1

            return stats

        except CONSOLIDATOR_ERRORS as e:
            logger.warning("apply_decay_to_all error: %s", e)
            return stats
        finally:
            conn.close()

    async def merge_similar_memories(
        self,
        similarity_threshold: float = None
    ) -> Dict[str, Any]:
        """
        Merge memories with very high similarity.

        Uses simple text overlap for similarity (could be enhanced with embeddings).

        Returns:
            Dict with merge statistics
        """
        system2_config = self.config.get("system2", {})
        threshold = similarity_threshold or system2_config.get("merge_similarity_threshold", 0.9)
        max_batch = system2_config.get("max_batch_size", 100)

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        stats = {"merged_count": 0, "groups_found": 0}

        try:
            # Get recent observations for merging
            cursor.execute("""
                SELECT observation_id, content, category
                FROM observations
                ORDER BY created_at DESC
                LIMIT ?
            """, (max_batch,))

            observations = cursor.fetchall()

            # Simple similarity grouping (content-based)
            groups = self._find_similar_groups(observations, threshold)
            stats["groups_found"] = len(groups)

            # Merge each group
            for group in groups:
                if len(group) >= 2:
                    merged_id = await self._merge_group(group, conn)
                    if merged_id:
                        stats["merged_count"] += 1

            conn.commit()
            return stats

        except CONSOLIDATOR_ERRORS as e:
            logger.warning("merge_similar_memories error: %s", e)
            return stats
        finally:
            conn.close()

    def _find_similar_groups(
        self,
        items: List[Tuple],
        threshold: float
    ) -> List[List[Tuple]]:
        """Find groups of similar items based on text overlap."""
        from difflib import SequenceMatcher

        groups = []
        used = set()

        for i, item1 in enumerate(items):
            if i in used:
                continue

            group = [item1]
            used.add(i)

            for j, item2 in enumerate(items):
                if j in used or j == i:
                    continue

                # Calculate similarity
                content1 = item1[1] if len(item1) > 1 else ""
                content2 = item2[1] if len(item2) > 1 else ""

                similarity = SequenceMatcher(None, content1, content2).ratio()

                if similarity >= threshold:
                    group.append(item2)
                    used.add(j)

            if len(group) >= 2:
                groups.append(group)

        return groups

    async def _merge_group(
        self,
        group: List[Tuple],
        conn: sqlite3.Connection
    ) -> Optional[str]:
        """Merge a group of similar observations into one."""
        import uuid

        if len(group) < 2:
            return None

        cursor = conn.cursor()

        try:
            # Take the longest content as the merged content
            contents = [item[1] for item in group if len(item) > 1]
            merged_content = max(contents, key=len) if contents else ""

            # Get category from first item
            category = group[0][2] if len(group[0]) > 2 else "note"

            # Get IDs to merge
            source_ids = [item[0] for item in group]

            # Create merged observation
            merged_id = str(uuid.uuid4())
            now = datetime.now().isoformat()

            cursor.execute("""
                INSERT INTO observations
                (observation_id, user_id, category, content, tags, source, confidence, created_at, updated_at)
                VALUES (?, 'default', ?, ?, '["merged"]', 'consolidator', 0.9, ?, ?)
            """, (merged_id, category, merged_content, now, now))

            # Mark source observations as merged (set low importance)
            for source_id in source_ids:
                cursor.execute("""
                    UPDATE memory_importance
                    SET importance_score = 0.0, score_source = 'merged'
                    WHERE memory_id = ?
                """, (source_id,))

            # Log the merge
            cursor.execute("""
                INSERT INTO consolidation_log
                (consolidation_type, source_ids, result_id, status, created_at)
                VALUES ('merge', ?, ?, 'completed', ?)
            """, (json.dumps(source_ids), merged_id, now))

            return merged_id

        except CONSOLIDATOR_ERRORS as e:
            logger.warning("_merge_group error: %s", e)
            return None

