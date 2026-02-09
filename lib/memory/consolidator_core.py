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


class ConsolidatorCoreMixin:
    """Mixin methods extracted from NightlyConsolidator."""

    def consolidate(self, hours: int = 24) -> Dict[str, Any]:
        """
        Consolidate recent session archives into structured memory.

        v2.1: Saves to database instead of JSON/Markdown files.

        Args:
            hours: How many hours back to look for sessions

        Returns:
            Consolidated memory dictionary
        """
        # Collect recent archives from database
        cutoff = datetime.now() - timedelta(hours=hours)
        sessions = self._collect_archives(cutoff)

        if not sessions:
            return {"status": "no_sessions", "message": "No sessions found in the specified time range"}

        # Build consolidated memory
        memory = {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "generated_at": datetime.now().isoformat(),
            "time_range_hours": hours,
            "sessions_processed": len(sessions),
            "models_used": list(set(s.model for s in sessions if s.model)),
            "project_progress": self._summarize_projects(sessions),
            "tool_usage_total": self._aggregate_tool_usage(sessions),
            "files_touched": self._aggregate_file_changes(sessions),
            "all_learnings": self._collect_learnings(sessions),
            "causal_chains": self._find_causal_chains(sessions),
            "cross_session_insights": self._extract_insights(sessions),
        }

        # Save to database
        self._save_memory_to_db(memory)

        return memory

    def _collect_archives(self, cutoff: datetime) -> List[SessionArchive]:
        """Collect session archives from DATABASE after cutoff time.

        v2.1: Now reads from database instead of Markdown files.
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            cursor.execute("""
                SELECT * FROM session_archives
                WHERE created_at >= ?
                ORDER BY created_at ASC
            """, (cutoff.isoformat(),))

            columns = [desc[0] for desc in cursor.description]
            archives = []

            for row in cursor.fetchall():
                data = dict(zip(columns, row))
                archives.append(SessionArchive(data))

            return archives

        except sqlite3.OperationalError as e:
            logger.warning("Database error when collecting archives: %s", e)
            return []
        finally:
            conn.close()

    def _summarize_projects(self, sessions: List[SessionArchive]) -> Dict[str, Any]:
        """Group and summarize sessions by project."""
        projects = defaultdict(lambda: {
            "sessions": [],
            "tasks": [],
            "files_modified": set(),
            "tools_used": defaultdict(int),
            "learnings": [],
            "total_duration": ""
        })

        for session in sessions:
            project_key = self._normalize_project_path(session.project_path)

            proj = projects[project_key]
            proj["sessions"].append(session.session_id)
            if session.task_summary:
                proj["tasks"].append(session.task_summary)

            for fc in session.file_changes:
                proj["files_modified"].add(fc["path"])

            for tool, count in session.tool_calls.items():
                proj["tools_used"][tool] += count

            proj["learnings"].extend(session.learnings)

        # Convert sets to lists for JSON serialization
        result = {}
        for proj_path, data in projects.items():
            result[proj_path] = {
                "sessions": data["sessions"],
                "tasks": data["tasks"],
                "files_modified": list(data["files_modified"]),
                "tools_used": dict(data["tools_used"]),
                "learnings": list(set(data["learnings"]))[:10],  # Dedupe and limit
            }

        return result

    def _aggregate_tool_usage(self, sessions: List[SessionArchive]) -> Dict[str, int]:
        """Aggregate tool usage across all sessions."""
        total = defaultdict(int)
        for session in sessions:
            for tool, count in session.tool_calls.items():
                total[tool] += count
        return dict(sorted(total.items(), key=lambda x: -x[1]))

    def _aggregate_file_changes(self, sessions: List[SessionArchive]) -> Dict[str, Dict]:
        """Aggregate file changes across sessions."""
        files = defaultdict(lambda: {"read": 0, "modified": 0, "sessions": set()})

        for session in sessions:
            for fc in session.file_changes:
                # Handle both dict and object formats
                if isinstance(fc, dict):
                    path = fc.get("path", "")
                    action = fc.get("action", "read")
                else:
                    path = getattr(fc, 'path', str(fc))
                    action = getattr(fc, 'action', 'read')

                files[path]["sessions"].add(session.session_id)
                if action in ("modified", "write", "edit"):
                    files[path]["modified"] += 1
                else:
                    files[path]["read"] += 1

        # Convert to serializable format
        result = {}
        for path, data in files.items():
            result[path] = {
                "read_count": data["read"],
                "modify_count": data["modified"],
                "session_count": len(data["sessions"])
            }

        return result

    def _save_memory_to_db(self, memory: Dict[str, Any]):
        """Save consolidated memory to database."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            memory_id = str(uuid.uuid4())
            now = datetime.now().isoformat()

            cursor.execute("""
                INSERT OR REPLACE INTO consolidated_memories (
                    memory_id, user_id, date, time_range_hours, sessions_processed,
                    models_used, project_progress, tool_usage_total, files_touched,
                    all_learnings, causal_chains, cross_session_insights,
                    llm_enhanced, llm_learnings, llm_preferences, llm_patterns, llm_summary,
                    metadata, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                memory_id,
                'default',
                memory.get('date'),
                memory.get('time_range_hours'),
                memory.get('sessions_processed'),
                json.dumps(memory.get('models_used', []), ensure_ascii=False),
                json.dumps(memory.get('project_progress', {}), ensure_ascii=False),
                json.dumps(memory.get('tool_usage_total', {}), ensure_ascii=False),
                json.dumps(memory.get('files_touched', {}), ensure_ascii=False),
                json.dumps(memory.get('all_learnings', []), ensure_ascii=False),
                json.dumps(memory.get('causal_chains', []), ensure_ascii=False),
                json.dumps(memory.get('cross_session_insights', []), ensure_ascii=False),
                1 if memory.get('llm_enhanced') else 0,
                json.dumps(memory.get('llm_learnings', []), ensure_ascii=False),
                json.dumps(memory.get('llm_preferences', []), ensure_ascii=False),
                json.dumps(memory.get('llm_patterns', []), ensure_ascii=False),
                memory.get('llm_summary', ''),
                json.dumps({
                    'generated_at': memory.get('generated_at'),
                    'llm_error': memory.get('llm_error')
                }, ensure_ascii=False),
                now
            ))

            conn.commit()
            logger.info("Saved consolidated memory to database: %s", memory["date"])

        except CONSOLIDATOR_ERRORS as e:
            logger.warning("Error saving to database: %s", e)
            conn.rollback()
        finally:
            conn.close()

    def _save_memory(self, memory: Dict[str, Any]):
        """Save memory - now delegates to database method.

        Kept for backward compatibility.
        """
        self._save_memory_to_db(memory)

    def _collect_learnings(self, sessions: List[SessionArchive]) -> List[str]:
        """Collect and deduplicate all learnings."""
        all_learnings = []
        seen = set()

        for session in sessions:
            for learning in session.learnings:
                normalized = learning.lower().strip()
                if normalized not in seen and len(learning) > 10:
                    seen.add(normalized)
                    all_learnings.append(learning)

        return all_learnings[:20]  # Limit to top 20

    def _find_causal_chains(self, sessions: List[SessionArchive]) -> List[Dict]:
        """
        Identify causal chains across sessions.

        A causal chain is a sequence of related tasks/decisions that
        span multiple sessions.
        """
        chains = []

        # Group sessions by project
        project_sessions = defaultdict(list)
        for session in sessions:
            project_key = self._normalize_project_path(session.project_path)
            project_sessions[project_key].append(session)

        # For each project, look for related task sequences
        for project, proj_sessions in project_sessions.items():
            if len(proj_sessions) < 2:
                continue

            # Simple heuristic: sessions working on related files form a chain
            file_overlap = self._find_file_overlap(proj_sessions)
            if file_overlap:
                chain = {
                    "chain_id": f"chain_{project.replace('/', '_')[:20]}",
                    "project": project,
                    "steps": [
                        {
                            "session": s.session_id,
                            "task": s.task_summary[:100] if s.task_summary else "unknown",
                            "timestamp": s.timestamp
                        }
                        for s in proj_sessions
                    ],
                    "shared_files": list(file_overlap)[:5]
                }
                chains.append(chain)

        return chains

    def _find_file_overlap(self, sessions: List[SessionArchive]) -> Set[str]:
        """Find files touched by multiple sessions."""
        file_sessions = defaultdict(set)

        for session in sessions:
            for fc in session.file_changes:
                # Handle both dict and object formats
                if isinstance(fc, dict):
                    path = fc.get("path", "")
                else:
                    path = getattr(fc, 'path', str(fc))
                file_sessions[path].add(session.session_id)

        # Return files touched by more than one session
        return {f for f, s in file_sessions.items() if len(s) > 1}

    def get_consolidated_memories(
        self,
        days: int = 30,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Get consolidated memories from database.

        Args:
            days: How many days back to look
            limit: Maximum results

        Returns:
            List of consolidated memory dictionaries
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            cursor.execute("""
                SELECT * FROM consolidated_memories
                WHERE created_at >= datetime('now', ?)
                ORDER BY date DESC
                LIMIT ?
            """, (f'-{days} days', limit))

            columns = [desc[0] for desc in cursor.description]
            results = []

            for row in cursor.fetchall():
                result = dict(zip(columns, row))
                # Parse JSON fields
                json_fields = [
                    'models_used', 'project_progress', 'tool_usage_total',
                    'files_touched', 'all_learnings', 'causal_chains',
                    'cross_session_insights', 'llm_learnings', 'llm_preferences',
                    'llm_patterns', 'metadata'
                ]
                for field in json_fields:
                    if result.get(field):
                        try:
                            result[field] = json.loads(result[field])
                        except json.JSONDecodeError:
                            pass
                results.append(result)

            return results

        except sqlite3.OperationalError:
            return []
        finally:
            conn.close()

    def search_consolidated(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Search consolidated memories.

        Args:
            query: Search query
            limit: Maximum results

        Returns:
            List of matching memories
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            cursor.execute("""
                SELECT * FROM consolidated_memories
                WHERE all_learnings LIKE ? OR llm_summary LIKE ?
                ORDER BY date DESC
                LIMIT ?
            """, (f'%{query}%', f'%{query}%', limit))

            columns = [desc[0] for desc in cursor.description]
            results = []

            for row in cursor.fetchall():
                result = dict(zip(columns, row))
                for field in ['all_learnings', 'project_progress', 'cross_session_insights']:
                    if result.get(field):
                        try:
                            result[field] = json.loads(result[field])
                        except json.JSONDecodeError:
                            pass
                results.append(result)

            return results

        except sqlite3.OperationalError:
            return []
        finally:
            conn.close()

    def _extract_insights(self, sessions: List[SessionArchive]) -> List[Dict]:
        """
        Extract cross-session insights and patterns.

        These are observations about user behavior, preferences,
        or recurring patterns.
        """
        insights = []

        # Analyze tool preferences
        tool_totals = self._aggregate_tool_usage(sessions)
        top_tools = list(tool_totals.keys())[:3]
        if top_tools:
            insights.append({
                "pattern": f"Most used tools: {', '.join(top_tools)}",
                "confidence": 0.9,
                "type": "tool_preference"
            })

        # Analyze project focus
        project_counts = defaultdict(int)
        for session in sessions:
            project_key = self._normalize_project_path(session.project_path)
            project_counts[project_key] += 1

        if project_counts:
            top_project = max(project_counts.items(), key=lambda x: x[1])
            insights.append({
                "pattern": f"Primary project: {top_project[0]} ({top_project[1]} sessions)",
                "confidence": 0.85,
                "type": "project_focus"
            })

        # Check for file modification patterns
        file_changes = self._aggregate_file_changes(sessions)
        hot_files = [f for f, d in file_changes.items() if d["modify_count"] > 2]
        if hot_files:
            insights.append({
                "pattern": f"Frequently modified files: {', '.join(hot_files[:3])}",
                "confidence": 0.8,
                "type": "file_hotspots"
            })

        return insights

    def _normalize_project_path(self, path: str) -> str:
        """Normalize project path for grouping."""
        if not path:
            return "unknown"

        # Expand ~ to home
        if path.startswith("~"):
            path = str(Path.home()) + path[1:]

        # Get the main project directory (2-3 levels from home)
        home = str(Path.home())
        if path.startswith(home):
            relative = path[len(home):].strip('/')
            if not relative:
                # User's home directory itself
                return "~"
            parts = relative.split('/')
            if len(parts) >= 2:
                return '~/' + '/'.join(parts[:2])
            elif parts:
                return '~/' + parts[0]

        return path

    # Old _save_memory is replaced by _save_memory_to_db above

    # ========================================================================
    # v2.0: Heuristic Memory Management
    # ========================================================================

