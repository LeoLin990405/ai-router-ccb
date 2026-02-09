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


class SkillsDiscoveryCoreMixin:
    """Mixin methods extracted from SkillsDiscoveryService."""

    def __init__(self, db_path: str = None):
        """Initialize Skills Discovery Service

        Args:
            db_path: Path to SQLite database (default: ~/.ccb/ccb_memory.db)
        """
        if db_path is None:
            db_path = os.path.expanduser("~/.ccb/ccb_memory.db")

        self.db_path = db_path
        self.skills_dir = os.path.expanduser("~/.claude/skills")
        self.cache_ttl = timedelta(hours=24)  # Cache skills for 24 hours

        # Initialize database tables
        self._init_db()

    @staticmethod

    def _strip_ansi(text: str) -> str:
        """Remove ANSI color codes from text

        Args:
            text: Text with ANSI codes

        Returns:
            Clean text without ANSI codes
        """
        ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        return ansi_escape.sub('', text)

    def _init_db(self):
        """Initialize skills-related database tables"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Skills metadata cache
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS skills_cache (
                skill_name TEXT PRIMARY KEY,
                description TEXT,
                triggers TEXT,  -- JSON array
                source TEXT,    -- 'local' or 'remote'
                installed INTEGER DEFAULT 0,
                last_updated TEXT NOT NULL,
                metadata TEXT   -- JSON
            )
        """)

        # Skills usage tracking
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS skills_usage (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                skill_name TEXT NOT NULL,
                task_keywords TEXT NOT NULL,
                provider TEXT,
                timestamp TEXT NOT NULL,
                success INTEGER DEFAULT 1,
                FOREIGN KEY (skill_name) REFERENCES skills_cache(skill_name)
            )
        """)

        # Create index for fast keyword search
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_skills_usage_keywords
            ON skills_usage(task_keywords)
        """)

        conn.commit()
        conn.close()
        logger.info("Database initialized")

    def scan_local_skills(self) -> List[Dict]:
        """Scan local skills using scan-skills.sh

        Returns:
            List of skill metadata dictionaries
        """
        scan_script = os.path.join(self.skills_dir, "scan-skills.sh")

        if not os.path.exists(scan_script):
            logger.warning("scan-skills.sh not found at %s", scan_script)
            return []

        try:
            # Run scan-skills.sh
            result = subprocess.run(
                [scan_script],
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode != 0:
                logger.warning("scan-skills.sh failed: %s", result.stderr)
                return []

            # Parse output (assuming format: skill_name | description | triggers)
            skills = []
            for line in result.stdout.strip().split('\n'):
                if '|' in line:
                    parts = [p.strip() for p in line.split('|')]
                    if len(parts) >= 2:
                        skills.append({
                            'name': parts[0],
                            'description': parts[1],
                            'triggers': parts[2].split(',') if len(parts) > 2 else [],
                            'source': 'local',
                            'installed': 1
                        })

            logger.info("Scanned %s local skills", len(skills))
            return skills

        except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError) as e:
            logger.exception("Error scanning local skills: %s", e)
            return []

    def search_remote_skills(self, keywords: List[str]) -> List[Dict]:
        """Search remote skills using Vercel Skills CLI (npx skills find)

        Args:
            keywords: List of search keywords

        Returns:
            List of skill metadata dictionaries
        """
        if not keywords:
            return []

        query = " ".join(keywords[:3])  # Use up to 3 keywords
        logger.info("Searching remote skills: npx skills find %s", query)

        try:
            # Run npx skills find with --no-color to avoid ANSI codes
            result = subprocess.run(
                ["npx", "skills", "find", query, "--no-color"],
                capture_output=True,
                text=True,
                timeout=30,
                env={**os.environ, "NO_COLOR": "1"}  # Force no color
            )

            if result.returncode != 0:
                logger.warning("Skills find failed: %s", result.stderr)
                return []

            # Parse output
            # Expected format:
            # Install with npx skills add <owner/repo@skill>
            #
            # owner/repo@skill-name
            # └ https://skills.sh/owner/repo/skill-name
            skills = []

            # Strip ANSI codes from output
            clean_output = self._strip_ansi(result.stdout)
            lines = clean_output.strip().split('\n')

            i = 0
            while i < len(lines):
                line = lines[i].strip()

                # Skip empty lines and headers
                if not line or line.startswith('Install with'):
                    i += 1
                    continue

                # Parse skill reference (owner/repo@skill-name)
                if '@' in line and '/' in line and not line.startswith('└'):
                    parts = line.split('@')
                    if len(parts) == 2:
                        repo = parts[0].strip()  # owner/repo
                        skill_name = parts[1].strip()  # skill-name

                        # Try to get URL from next line
                        url = None
                        if i + 1 < len(lines):
                            next_line = lines[i + 1].strip()
                            if next_line.startswith('└'):
                                url = next_line.replace('└', '').strip()

                        skills.append({
                            'name': skill_name,
                            'description': f"Remote skill from {repo}",
                            'triggers': keywords,
                            'source': 'remote',
                            'installed': 0,
                            'install_command': f"npx skills add {repo}@{skill_name} -g -y",
                            'url': url or f"https://skills.sh/{repo}/{skill_name}"
                        })

                i += 1

            logger.info("Found %s remote skills", len(skills))
            return skills

        except subprocess.TimeoutExpired:
            logger.warning("Skills find timeout")
            return []
        except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError) as e:
            logger.exception("Error searching remote skills: %s", e)
            return []

    def match_skills(self, task_description: str, top_k: int = 5, search_remote: bool = True) -> List[Dict]:
        """Match skills based on task description

        Args:
            task_description: User's task description
            top_k: Number of top skills to return
            search_remote: Whether to search remote skills via npx skills find

        Returns:
            List of matched skill dictionaries with relevance scores
        """
        # Extract keywords from task description
        keywords = self._extract_keywords(task_description)

        # Search in cache first (local skills)
        cached_skills = self._search_cache(keywords)

        # If cache is stale or empty, refresh
        if not cached_skills or self._is_cache_stale():
            logger.info("Refreshing skills cache...")
            self._refresh_cache()
            cached_skills = self._search_cache(keywords)

        # Optionally search remote skills
        remote_skills = []
        if search_remote and keywords:
            remote_skills = self.search_remote_skills(keywords)

            # Cache remote skills for future use
            if remote_skills:
                self._cache_remote_skills(remote_skills)

        # Combine local and remote skills
        all_skills = cached_skills + remote_skills

        # Rank skills by relevance
        ranked_skills = self._rank_skills(all_skills, keywords, top_k)

        return ranked_skills

    def get_tool_recommendations(self, task: str, limit: int = 5) -> Dict:
        """Get unified tool recommendations using ToolIndex when available."""
        query = str(task or "").strip()
        if not query:
            return {"source": "tool_index", "results": [], "count": 0}

        tool_index_cls = None
        try:
            from lib.skills.tool_index import ToolIndex

            tool_index_cls = ToolIndex
        except ImportError:
            try:
                from skills.tool_index import ToolIndex  # type: ignore

                tool_index_cls = ToolIndex
            except ImportError:
                tool_index_cls = None

        if tool_index_cls is not None:
            try:
                index = tool_index_cls()
                if getattr(index, "_entries", None):
                    results = index.search(query, limit=limit)
                    return {
                        "source": "tool_index",
                        "results": results,
                        "count": len(results),
                    }
            except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError):
                logger.debug("ToolIndex query failed", exc_info=True)

        fallback = self.get_recommendations(query)
        normalized = []
        for skill in fallback.get("skills", []):
            normalized.append(
                {
                    "id": f"skill:{skill.get('name')}",
                    "type": "skill",
                    "name": skill.get("name"),
                    "description": skill.get("description"),
                    "installed": bool(skill.get("installed")),
                    "_score": skill.get("relevance_score", 0),
                }
            )

        return {
            "source": "skills_discovery",
            "results": normalized,
            "count": len(normalized),
            "message": fallback.get("message", ""),
        }

    def _extract_keywords(self, text: str) -> List[str]:
        """Extract keywords from text

        Args:
            text: Input text

        Returns:
            List of keywords
        """
        # Simple keyword extraction (can be improved with NLP)
        # Remove special characters and split
        text_lower = text.lower()
        words = re.findall(r'\b\w+\b', text_lower)

        # Filter out common stop words
        stop_words = {'a', 'an', 'the', 'is', 'are', 'was', 'were', 'help', 'me', 'can', 'you', 'please'}
        keywords = [w for w in words if w not in stop_words and len(w) > 2]

        return keywords

    def _search_cache(self, keywords: List[str]) -> List[Dict]:
        """Search skills cache by keywords

        Args:
            keywords: List of keywords

        Returns:
            List of matching skills
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Build query for keyword matching
        # Match against skill_name, description, and triggers
        query = """
            SELECT skill_name, description, triggers, source, installed, metadata
            FROM skills_cache
            WHERE
        """

        # Add keyword conditions
        conditions = []
        params = []
        for keyword in keywords:
            pattern = f"%{keyword}%"
            conditions.append(
                "(skill_name LIKE ? OR description LIKE ? OR triggers LIKE ?)"
            )
            params.extend([pattern, pattern, pattern])

        query += " OR ".join(conditions)

        cursor.execute(query, params)
        rows = cursor.fetchall()

        skills = []
        for row in rows:
            skills.append({
                'name': row[0],
                'description': row[1],
                'triggers': json.loads(row[2]) if row[2] else [],
                'source': row[3],
                'installed': bool(row[4]),
                'metadata': json.loads(row[5]) if row[5] else {}
            })

        conn.close()
        return skills

    def _is_cache_stale(self) -> bool:
        """Check if cache is stale

        Returns:
            True if cache needs refresh
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT last_updated FROM skills_cache
            ORDER BY last_updated DESC LIMIT 1
        """)

        row = cursor.fetchone()
        conn.close()

        if not row:
            return True

        last_updated = datetime.fromisoformat(row[0])
        return datetime.now() - last_updated > self.cache_ttl

    def _refresh_cache(self):
        """Refresh skills cache from local and remote sources"""
        # Scan local skills
        local_skills = self.scan_local_skills()

        # Update cache
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        timestamp = datetime.now().isoformat()

        for skill in local_skills:
            cursor.execute("""
                INSERT OR REPLACE INTO skills_cache
                (skill_name, description, triggers, source, installed, last_updated, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                skill['name'],
                skill['description'],
                json.dumps(skill.get('triggers', [])),
                skill['source'],
                skill['installed'],
                timestamp,
                json.dumps(skill.get('metadata', {}))
            ))

        conn.commit()
        conn.close()

        logger.info("Cache refreshed with %s skills", len(local_skills))

    def _cache_remote_skills(self, remote_skills: List[Dict]):
        """Cache remote skills to database

        Args:
            remote_skills: List of remote skill dictionaries
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        timestamp = datetime.now().isoformat()

        for skill in remote_skills:
            cursor.execute("""
                INSERT OR REPLACE INTO skills_cache
                (skill_name, description, triggers, source, installed, last_updated, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                skill['name'],
                skill['description'],
                json.dumps(skill.get('triggers', [])),
                skill['source'],
                0,  # Remote skills not installed by default
                timestamp,
                json.dumps({
                    'install_command': skill.get('install_command'),
                    'url': skill.get('url')
                })
            ))

        conn.commit()
        conn.close()

        logger.info("Cached %s remote skills", len(remote_skills))

