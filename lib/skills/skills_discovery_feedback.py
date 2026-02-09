"""Auto-split mixin methods for SkillsDiscoveryService."""
from __future__ import annotations

import json
import os
import re
import sqlite3
import subprocess
from datetime import datetime, timedelta
from typing import Dict, List

from .skills_discovery_shared import logger


class SkillsDiscoveryFeedbackMixin:
    """Mixin methods extracted from SkillsDiscoveryService."""

    def record_feedback(
        self,
        skill_name: str,
        rating: int,
        task_keywords: str = None,
        task_description: str = None,
        helpful: bool = True,
        comment: str = None,
        user_id: str = "default"
    ) -> bool:
        """Record user feedback for a skill

        Args:
            skill_name: Name of the skill
            rating: Rating 1-5
            task_keywords: Keywords from the task (optional)
            task_description: Full task description (optional)
            helpful: Whether the skill was helpful
            comment: User comment (optional)
            user_id: User ID

        Returns:
            True if feedback was recorded
        """
        if rating < 1 or rating > 5:
            return False

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            cursor.execute("""
                INSERT INTO skills_feedback
                (skill_name, user_id, rating, task_keywords, task_description, helpful, comment, timestamp, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                skill_name,
                user_id,
                rating,
                json.dumps(task_keywords.split() if task_keywords else []),
                task_description,
                1 if helpful else 0,
                comment,
                datetime.now().isoformat(),
                json.dumps({})
            ))

            conn.commit()
            return True
        except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError) as e:
            logger.exception("Feedback error: %s", e)
            return False
        finally:
            conn.close()

    def get_skill_feedback_stats(self, skill_name: str) -> Dict:
        """Get feedback statistics for a skill

        Args:
            skill_name: Name of the skill

        Returns:
            Dictionary with feedback statistics
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            cursor.execute("""
                SELECT
                    COUNT(*) as total_feedback,
                    AVG(rating) as avg_rating,
                    SUM(CASE WHEN helpful = 1 THEN 1 ELSE 0 END) as helpful_count,
                    MAX(timestamp) as last_feedback
                FROM skills_feedback
                WHERE skill_name = ?
            """, (skill_name,))

            row = cursor.fetchone()
            if not row or row[0] == 0:
                return {
                    "skill_name": skill_name,
                    "total_feedback": 0,
                    "avg_rating": None,
                    "helpful_rate": None,
                    "last_feedback": None
                }

            return {
                "skill_name": skill_name,
                "total_feedback": row[0],
                "avg_rating": round(row[1], 2) if row[1] else None,
                "helpful_rate": round(row[2] / row[0], 2) if row[0] > 0 else None,
                "last_feedback": row[3]
            }
        finally:
            conn.close()

    def get_feedback_boost(self, skill_name: str) -> float:
        """Calculate feedback-based boost for skill ranking (Phase 5)

        The boost formula:
        boost = avg_rating * helpful_rate * recency_weight

        Args:
            skill_name: Name of the skill

        Returns:
            Boost value (0.0 to ~5.0)
        """
        stats = self.get_skill_feedback_stats(skill_name)

        if not stats["avg_rating"]:
            return 0.0

        avg_rating = stats["avg_rating"]  # 1-5
        helpful_rate = stats["helpful_rate"] or 0.5  # 0-1
        total = stats["total_feedback"]

        # Recency weight based on last feedback
        recency_weight = 1.0
        if stats["last_feedback"]:
            try:
                last_feedback = datetime.fromisoformat(stats["last_feedback"])
                days_ago = (datetime.now() - last_feedback).days
                # Decay over 30 days
                recency_weight = max(0.5, 1.0 - (days_ago / 60))
            except (ValueError, TypeError):
                pass

        # Confidence factor based on number of feedbacks
        confidence = min(1.0, total / 5)  # Full confidence at 5 feedbacks

        # Final boost: normalized to ~0-2 range
        boost = (avg_rating / 5) * helpful_rate * recency_weight * confidence * 2
        return round(boost, 3)

    def get_all_feedback_stats(self) -> List[Dict]:
        """Get feedback statistics for all skills with feedback

        Returns:
            List of feedback stats dictionaries
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            cursor.execute("""
                SELECT skill_name,
                       COUNT(*) as total_feedback,
                       AVG(rating) as avg_rating,
                       SUM(CASE WHEN helpful = 1 THEN 1 ELSE 0 END) as helpful_count
                FROM skills_feedback
                GROUP BY skill_name
                ORDER BY total_feedback DESC
            """)

            results = []
            for row in cursor.fetchall():
                results.append({
                    "skill_name": row[0],
                    "total_feedback": row[1],
                    "avg_rating": round(row[2], 2) if row[2] else None,
                    "helpful_rate": round(row[3] / row[1], 2) if row[1] > 0 else None
                })

            return results
        finally:
            conn.close()

