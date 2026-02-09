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


class SkillsDiscoveryRankingMixin:
    """Mixin methods extracted from SkillsDiscoveryService."""

    def _rank_skills(self, skills: List[Dict], keywords: List[str], top_k: int) -> List[Dict]:
        """Rank skills by relevance to keywords

        Enhanced with feedback-based boost (Phase 5).

        Args:
            skills: List of skill dictionaries
            keywords: List of keywords
            top_k: Number of top skills to return

        Returns:
            Ranked list of skills with scores
        """
        scored_skills = []

        for skill in skills:
            score = 0

            # Score based on keyword matches
            skill_text = (
                skill['name'].lower() + ' ' +
                skill['description'].lower() + ' ' +
                ' '.join(skill.get('triggers', [])).lower()
            )

            for keyword in keywords:
                # Exact match in name: +10
                if keyword in skill['name'].lower():
                    score += 10
                # Match in description: +5
                elif keyword in skill['description'].lower():
                    score += 5
                # Match in triggers: +3
                elif any(keyword in t.lower() for t in skill.get('triggers', [])):
                    score += 3

            # Bonus for installed skills: +2
            if skill.get('installed'):
                score += 2

            # Check usage history
            usage_boost = self._get_usage_boost(skill['name'], keywords)
            score += usage_boost

            # Phase 5: Add feedback-based boost
            feedback_boost = self.get_feedback_boost(skill['name'])
            score += feedback_boost * 5  # Scale feedback boost

            scored_skills.append({
                **skill,
                'relevance_score': score,
                'usage_boost': usage_boost,
                'feedback_boost': feedback_boost
            })

        # Sort by score and return top K
        scored_skills.sort(key=lambda x: x['relevance_score'], reverse=True)
        return scored_skills[:top_k]

    def _get_usage_boost(self, skill_name: str, keywords: List[str]) -> int:
        """Get usage-based relevance boost

        Args:
            skill_name: Name of the skill
            keywords: Current task keywords

        Returns:
            Boost score based on historical usage
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Check if this skill has been successfully used for similar keywords
        boost = 0
        for keyword in keywords:
            cursor.execute("""
                SELECT COUNT(*) FROM skills_usage
                WHERE skill_name = ?
                AND task_keywords LIKE ?
                AND success = 1
            """, (skill_name, f"%{keyword}%"))

            count = cursor.fetchone()[0]
            boost += min(count, 5)  # Cap at +5 per keyword

        conn.close()
        return boost

    def record_usage(self, skill_name: str, task_keywords: str, provider: str, success: bool = True):
        """Record skill usage for learning

        Args:
            skill_name: Name of the skill used
            task_keywords: Keywords from the task
            provider: AI provider that used the skill
            success: Whether the usage was successful
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO skills_usage
            (skill_name, task_keywords, provider, timestamp, success)
            VALUES (?, ?, ?, ?, ?)
        """, (
            skill_name,
            task_keywords,
            provider,
            datetime.now().isoformat(),
            1 if success else 0
        ))

        conn.commit()
        conn.close()

    # ========================================================================
    # Skills Feedback System (Phase 5: Feedback Loop)
    # ========================================================================

