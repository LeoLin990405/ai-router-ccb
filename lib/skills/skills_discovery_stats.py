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


class SkillsDiscoveryStatsMixin:
    """Mixin methods extracted from SkillsDiscoveryService."""

    def get_stats(self) -> Dict:
        """Get comprehensive statistics for skills discovery

        Returns:
            Dictionary with skills cache, usage, and feedback statistics
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            stats = {
                'cache': {},
                'usage': {},
                'feedback': {},
                'top_skills': []
            }

            # Cache statistics
            cursor.execute("""
                SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN installed = 1 THEN 1 ELSE 0 END) as installed,
                    SUM(CASE WHEN source = 'local' THEN 1 ELSE 0 END) as local,
                    SUM(CASE WHEN source = 'remote' THEN 1 ELSE 0 END) as remote
                FROM skills_cache
            """)
            row = cursor.fetchone()
            stats['cache'] = {
                'total': row[0] or 0,
                'installed': row[1] or 0,
                'local': row[2] or 0,
                'remote': row[3] or 0
            }

            # Usage statistics
            cursor.execute("""
                SELECT
                    COUNT(*) as total_uses,
                    COUNT(DISTINCT skill_name) as unique_skills,
                    SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as successful,
                    COUNT(DISTINCT DATE(timestamp)) as active_days
                FROM skills_usage
            """)
            row = cursor.fetchone()
            stats['usage'] = {
                'total_uses': row[0] or 0,
                'unique_skills': row[1] or 0,
                'successful': row[2] or 0,
                'success_rate': round((row[2] or 0) / row[0] * 100, 1) if row[0] else 0,
                'active_days': row[3] or 0
            }

            # Feedback statistics (check if table exists)
            cursor.execute("""
                SELECT name FROM sqlite_master
                WHERE type='table' AND name='skills_feedback'
            """)
            if cursor.fetchone():
                cursor.execute("""
                    SELECT
                        COUNT(*) as total,
                        AVG(rating) as avg_rating,
                        SUM(CASE WHEN helpful = 1 THEN 1 ELSE 0 END) as helpful
                    FROM skills_feedback
                """)
                row = cursor.fetchone()
                stats['feedback'] = {
                    'total': row[0] or 0,
                    'avg_rating': round(row[1], 2) if row[1] else None,
                    'helpful_rate': round((row[2] or 0) / row[0] * 100, 1) if row[0] else 0
                }
            else:
                stats['feedback'] = {'total': 0, 'avg_rating': None, 'helpful_rate': 0}

            # Top skills by usage
            cursor.execute("""
                SELECT skill_name, COUNT(*) as uses
                FROM skills_usage
                GROUP BY skill_name
                ORDER BY uses DESC
                LIMIT 5
            """)
            stats['top_skills'] = [
                {'name': row[0], 'uses': row[1]}
                for row in cursor.fetchall()
            ]

            return stats
        finally:
            conn.close()

    def get_usage_stats(self) -> Dict:
        """Get usage-focused statistics for API compatibility."""
        stats = self.get_stats()
        return {
            'usage': stats.get('usage', {}),
            'top_skills': stats.get('top_skills', []),
            'cache': stats.get('cache', {}),
            'feedback': stats.get('feedback', {}),
        }

    def list_all_skills(self) -> List[Dict]:
        """List all cached skills, refreshing cache if needed."""
        if self._is_cache_stale():
            self._refresh_cache()

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            cursor.execute("""
                SELECT skill_name, description, triggers, source, installed, last_updated, metadata
                FROM skills_cache
                ORDER BY installed DESC, skill_name ASC
            """)

            skills = []
            for row in cursor.fetchall():
                raw_triggers = row[2]
                if isinstance(raw_triggers, str) and raw_triggers:
                    try:
                        triggers = json.loads(raw_triggers)
                    except (json.JSONDecodeError, TypeError):
                        triggers = []
                else:
                    triggers = []

                raw_metadata = row[6]
                metadata = {}
                if isinstance(raw_metadata, str) and raw_metadata:
                    try:
                        metadata = json.loads(raw_metadata)
                    except (json.JSONDecodeError, TypeError):
                        metadata = {}

                skills.append({
                    'name': row[0],
                    'description': row[1] or '',
                    'triggers': triggers,
                    'source': row[3] or 'local',
                    'installed': bool(row[4]),
                    'last_updated': row[5],
                    'metadata': metadata,
                })

            return skills
        finally:
            conn.close()

    def get_recommendations(self, task_description: str, auto_install: bool = False) -> Dict:
        """Get skill recommendations with installation instructions

        Args:
            task_description: User's task description
            auto_install: Whether to automatically install recommended remote skills

        Returns:
            Dictionary with recommendations and installation info
        """
        matched_skills = self.match_skills(task_description, top_k=3, search_remote=True)

        recommendations = {
            'found': len(matched_skills) > 0,
            'skills': [],
            'message': ''
        }

        for skill in matched_skills:
            # Load metadata for install command
            metadata = skill.get('metadata', {})
            if isinstance(metadata, str):
                try:
                    metadata = json.loads(metadata)
                except (json.JSONDecodeError, TypeError):
                    metadata = {}

            skill_info = {
                'name': skill['name'],
                'description': skill['description'],
                'relevance_score': skill['relevance_score'],
                'installed': skill['installed'],
                'source': skill.get('source', 'local'),
                'usage_command': f"/{skill['name']}" if skill['installed'] else None,
                'install_command': None,
                'url': None
            }

            if not skill['installed']:
                # Get install command from metadata
                install_cmd = metadata.get('install_command')
                if install_cmd:
                    skill_info['install_command'] = install_cmd
                    skill_info['url'] = metadata.get('url')

                # Auto-install if requested
                if auto_install and install_cmd:
                    logger.info("Auto-installing %s...", skill['name'])
                    self._install_skill(install_cmd)

            recommendations['skills'].append(skill_info)

        # Generate message
        if matched_skills:
            installed = [s for s in matched_skills if s['installed']]
            not_installed = [s for s in matched_skills if not s['installed']]

            if installed:
                recommendations['message'] = (
                    f"💡 发现 {len(installed)} 个相关 Skill: " +
                    ", ".join([f"/{s['name']}" for s in installed])
                )

            if not_installed:
                skill_names = ", ".join([s['name'] for s in not_installed])
                if recommendations['message']:
                    recommendations['message'] += f"\n📦 可安装: {skill_names}"
                else:
                    recommendations['message'] = f"📦 发现 {len(not_installed)} 个可安装 Skill: {skill_names}"
        else:
            recommendations['message'] = "未找到相关 Skill"

        return recommendations

    def _install_skill(self, install_command: str) -> bool:
        """Install a skill using the provided command

        Args:
            install_command: Shell command to install skill

        Returns:
            True if installation succeeded
        """
        try:
            result = subprocess.run(
                install_command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=60
            )

            if result.returncode == 0:
                logger.info("Installation succeeded")
                return True
            else:
                logger.warning("Installation failed: %s", result.stderr)
                return False

        except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError) as e:
            logger.exception("Installation error: %s", e)
            return False


