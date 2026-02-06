#!/usr/bin/env python3
"""
Skills Discovery Service for CCB Gateway

Purpose:
- Discover relevant skills based on task analysis
- Integrate with find-skills and scan-skills
- Cache skill metadata in memory database
- Provide skill recommendations
"""

import os
import json
import subprocess
import sqlite3
import re
from typing import List, Dict, Optional
from datetime import datetime, timedelta


class SkillsDiscoveryService:
    """Discovers and manages Claude Code skills for CCB Gateway"""

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
        print("[SkillsDiscovery] Database initialized")

    def scan_local_skills(self) -> List[Dict]:
        """Scan local skills using scan-skills.sh

        Returns:
            List of skill metadata dictionaries
        """
        scan_script = os.path.join(self.skills_dir, "scan-skills.sh")

        if not os.path.exists(scan_script):
            print(f"[SkillsDiscovery] scan-skills.sh not found at {scan_script}")
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
                print(f"[SkillsDiscovery] scan-skills.sh failed: {result.stderr}")
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

            print(f"[SkillsDiscovery] Scanned {len(skills)} local skills")
            return skills

        except Exception as e:
            print(f"[SkillsDiscovery] Error scanning local skills: {e}")
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
        print(f"[SkillsDiscovery] Searching remote skills: npx skills find {query}")

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
                print(f"[SkillsDiscovery] Skills find failed: {result.stderr}")
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

            print(f"[SkillsDiscovery] Found {len(skills)} remote skills")
            return skills

        except subprocess.TimeoutExpired:
            print(f"[SkillsDiscovery] Skills find timeout")
            return []
        except Exception as e:
            print(f"[SkillsDiscovery] Error searching remote skills: {e}")
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
            print("[SkillsDiscovery] Refreshing skills cache...")
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

        print(f"[SkillsDiscovery] Cache refreshed with {len(local_skills)} skills")

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

        print(f"[SkillsDiscovery] Cached {len(remote_skills)} remote skills")

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
        except Exception as e:
            print(f"[SkillsDiscovery] Feedback error: {e}")
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
            except:
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
                except:
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
                    print(f"[SkillsDiscovery] Auto-installing {skill['name']}...")
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
                print(f"[SkillsDiscovery] Installation succeeded")
                return True
            else:
                print(f"[SkillsDiscovery] Installation failed: {result.stderr}")
                return False

        except Exception as e:
            print(f"[SkillsDiscovery] Installation error: {e}")
            return False


# CLI interface
if __name__ == "__main__":
    import sys

    service = SkillsDiscoveryService()

    if len(sys.argv) < 2:
        print("Usage:")
        print("  python3 skills_discovery.py scan          # Refresh cache")
        print("  python3 skills_discovery.py match <task>  # Find matching skills")
        print("  python3 skills_discovery.py stats         # Show usage stats")
        sys.exit(1)

    command = sys.argv[1]

    if command == "scan":
        service._refresh_cache()
        print("✓ Skills cache refreshed")

    elif command == "match":
        if len(sys.argv) < 3:
            print("Error: Please provide a task description")
            sys.exit(1)

        task = " ".join(sys.argv[2:])
        recommendations = service.get_recommendations(task)

        print(f"\n{recommendations['message']}\n")

        for skill in recommendations['skills']:
            print(f"  • {skill['name']} (score: {skill['relevance_score']})")
            print(f"    {skill['description']}")
            if skill['installed']:
                print(f"    Usage: {skill['usage_command']}")
            else:
                print(f"    Not installed")
            print()

    elif command == "stats":
        stats = service.get_stats()

        print("\n📊 Skills Discovery Statistics\n")
        print("=" * 40)

        # Cache stats
        cache = stats['cache']
        print(f"\n📦 Skills Cache:")
        print(f"   Total cached:  {cache['total']}")
        print(f"   Installed:     {cache['installed']}")
        print(f"   Local:         {cache['local']}")
        print(f"   Remote:        {cache['remote']}")

        # Usage stats
        usage = stats['usage']
        print(f"\n📈 Usage Statistics:")
        print(f"   Total uses:    {usage['total_uses']}")
        print(f"   Unique skills: {usage['unique_skills']}")
        print(f"   Success rate:  {usage['success_rate']}%")
        print(f"   Active days:   {usage['active_days']}")

        # Feedback stats
        feedback = stats['feedback']
        print(f"\n⭐ Feedback Statistics:")
        print(f"   Total feedback: {feedback['total']}")
        if feedback['avg_rating']:
            print(f"   Avg rating:     {feedback['avg_rating']}/5")
        print(f"   Helpful rate:   {feedback['helpful_rate']}%")

        # Top skills
        if stats['top_skills']:
            print(f"\n🏆 Top Skills by Usage:")
            for i, skill in enumerate(stats['top_skills'], 1):
                print(f"   {i}. {skill['name']} ({skill['uses']} uses)")

        print("\n" + "=" * 40)

    else:
        print(f"Unknown command: {command}")
        sys.exit(1)
