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


class MemoryV2ObservationMixin:
    """Mixin methods extracted from CCBMemoryV2."""

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

