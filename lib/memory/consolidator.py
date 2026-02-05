#!/usr/bin/env python3
"""
Memory Consolidator - System 2: Nightly Memory Integration

Collects recent session archives and generates structured long-term memory.
This is the "slow, deep thinking" part of the dual-system memory architecture.

Phase 3 Enhancement: LLM-powered insight extraction
v2.0 Enhancement: Heuristic memory management (merge, abstract, forget, decay)
"""

import asyncio
import json
import math
import re
import sqlite3
import sys
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

# For LLM integration
try:
    import httpx
    HAS_HTTPX = True
except ImportError:
    HAS_HTTPX = False


class SessionArchive:
    """Represents a parsed context archive (Markdown file)."""

    def __init__(self, path: Path):
        self.path = path
        self.session_id = ""
        self.project_path = ""
        self.timestamp = ""
        self.duration = ""
        self.model = ""
        self.task_summary = ""
        self.key_messages: List[Dict[str, str]] = []
        self.tool_calls: Dict[str, int] = {}
        self.file_changes: List[Dict[str, str]] = []
        self.learnings: List[str] = []

        self._parse()

    def _parse(self):
        """Parse the markdown archive file."""
        content = self.path.read_text(encoding='utf-8')
        lines = content.split('\n')

        current_section = None

        for i, line in enumerate(lines):
            line_stripped = line.strip()

            # Extract session ID from title
            if line_stripped.startswith('# Session:'):
                self.session_id = line_stripped.split(':')[-1].strip()
                continue

            # Detect sections
            if line_stripped.startswith('## '):
                current_section = line_stripped[3:].strip().lower()
                continue

            # Parse metadata
            if current_section == 'metadata':
                if '项目路径' in line:
                    match = re.search(r'`(.+?)`', line)
                    if match:
                        self.project_path = match.group(1)
                elif '时间' in line:
                    match = re.search(r'\*\*时间\*\*:\s*(.+)', line)
                    if match:
                        self.timestamp = match.group(1)
                elif '时长' in line:
                    match = re.search(r'\*\*时长\*\*:\s*(.+)', line)
                    if match:
                        self.duration = match.group(1)
                elif '模型' in line:
                    match = re.search(r'\*\*模型\*\*:\s*(.+)', line)
                    if match:
                        self.model = match.group(1)

            # Parse task summary
            elif current_section == '任务摘要':
                if line_stripped and not line_stripped.startswith('#'):
                    self.task_summary = line_stripped

            # Parse tool calls
            elif current_section == '工具调用':
                match = re.match(r'-\s+\*\*(.+?)\*\*:\s*(\d+)', line_stripped)
                if match:
                    self.tool_calls[match.group(1)] = int(match.group(2))

            # Parse file changes
            elif current_section == '文件变更':
                match = re.search(r'`(.+?)`\s*\((\w+)\)', line_stripped)
                if match:
                    self.file_changes.append({
                        'path': match.group(1),
                        'action': match.group(2)
                    })

            # Parse learnings
            elif current_section == '学到的知识':
                if line_stripped.startswith('- '):
                    self.learnings.append(line_stripped[2:])


class NightlyConsolidator:
    """System 2: Consolidates session archives into structured long-term memory.

    v2.0 Enhancement: Full System 2 capabilities including:
    - Merge: Combine similar memories
    - Abstract: Generate summaries from memory groups
    - Forget: Clean up low-importance, old memories
    - Decay: Apply time-based importance decay
    """

    # Gateway API URL for LLM calls
    GATEWAY_URL = "http://localhost:8765"

    # Default LLM provider for consolidation (Kimi is fast and has free quota)
    DEFAULT_LLM_PROVIDER = "kimi"

    # Database path
    DB_PATH = Path.home() / ".ccb" / "ccb_memory.db"

    def __init__(
        self,
        archive_dir: Optional[Path] = None,
        memory_dir: Optional[Path] = None,
        llm_provider: str = None,
        db_path: Optional[Path] = None
    ):
        self.archive_dir = archive_dir or Path.home() / ".ccb" / "context_archive"
        self.memory_dir = memory_dir or Path.home() / ".ccb" / "memories"
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        self.llm_provider = llm_provider or self.DEFAULT_LLM_PROVIDER
        self.db_path = db_path or self.DB_PATH

        # v2.0: Load heuristic config
        self.config = self._load_heuristic_config()

    async def consolidate_with_llm(self, hours: int = 24) -> Dict[str, Any]:
        """
        LLM-enhanced consolidation (Phase 3: LLM Consolidator).

        Uses LLM to extract deeper insights from sessions.

        Args:
            hours: How many hours back to look for sessions

        Returns:
            Consolidated memory dictionary with LLM insights
        """
        # First do basic consolidation
        memory = self.consolidate(hours=hours)

        if memory.get("status") == "no_sessions":
            return memory

        # If no httpx or gateway unavailable, return basic consolidation
        if not HAS_HTTPX:
            memory["llm_enhanced"] = False
            memory["llm_error"] = "httpx not installed"
            return memory

        # Collect raw session data for LLM analysis
        cutoff = datetime.now() - timedelta(hours=hours)
        archives = self._collect_archives(cutoff)
        sessions = [SessionArchive(path) for path in archives]

        # Extract insights via LLM
        try:
            llm_insights = await self._extract_insights_via_llm(sessions, memory)

            if llm_insights:
                memory["llm_enhanced"] = True
                memory["llm_learnings"] = llm_insights.get("learnings", [])
                memory["llm_preferences"] = llm_insights.get("preferences", [])
                memory["llm_patterns"] = llm_insights.get("patterns", [])
                memory["llm_summary"] = llm_insights.get("summary", "")

                # Save updated memory
                self._save_memory(memory)
            else:
                memory["llm_enhanced"] = False
                memory["llm_error"] = "No insights extracted"

        except Exception as e:
            memory["llm_enhanced"] = False
            memory["llm_error"] = str(e)

        return memory

    async def _extract_insights_via_llm(
        self,
        sessions: List['SessionArchive'],
        basic_memory: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Call LLM to extract deeper insights from sessions.

        Args:
            sessions: Parsed session archives
            basic_memory: Basic consolidated memory

        Returns:
            LLM-extracted insights dict or None
        """
        # Build prompt
        prompt = self._build_consolidation_prompt(sessions, basic_memory)

        # Call Gateway API
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(
                    f"{self.GATEWAY_URL}/api/ask",
                    params={"wait": "true", "timeout": "90"},
                    json={
                        "message": prompt,
                        "provider": self.llm_provider
                    }
                )

                if response.status_code != 200:
                    print(f"[Consolidator] LLM request failed: {response.status_code}")
                    return None

                result = response.json()

                # Parse LLM response
                llm_response = result.get("response", "")
                return self._parse_llm_response(llm_response)

        except httpx.TimeoutException:
            print("[Consolidator] LLM request timed out")
            return None
        except Exception as e:
            print(f"[Consolidator] LLM request error: {e}")
            return None

    def _build_consolidation_prompt(
        self,
        sessions: List['SessionArchive'],
        basic_memory: Dict[str, Any]
    ) -> str:
        """
        Build prompt for LLM consolidation.

        Args:
            sessions: Parsed session archives
            basic_memory: Basic consolidated memory

        Returns:
            Formatted prompt string
        """
        # Summarize sessions
        session_summaries = []
        for s in sessions[:10]:  # Limit to 10 sessions
            summary = f"""
Session: {s.session_id[:8]}
Project: {s.project_path}
Task: {s.task_summary[:200] if s.task_summary else 'N/A'}
Tools: {', '.join(list(s.tool_calls.keys())[:5])}
Learnings: {'; '.join(s.learnings[:3])}
"""
            session_summaries.append(summary)

        # Format basic insights
        basic_insights = "\n".join([
            f"- {i['pattern']}"
            for i in basic_memory.get("cross_session_insights", [])
        ])

        # Build prompt
        prompt = f"""你是一个记忆整合分析师。请分析以下用户的最近 AI 会话记录，提取有价值的洞察。

## 会话概览
- 处理的会话数: {len(sessions)}
- 时间范围: {basic_memory.get('time_range_hours', 24)} 小时
- 使用的模型: {', '.join(basic_memory.get('models_used', []))}

## 会话详情
{''.join(session_summaries)}

## 已有的基础洞察
{basic_insights if basic_insights else '无'}

## 所有学到的知识
{chr(10).join(['- ' + l for l in basic_memory.get('all_learnings', [])[:15]])}

---

请分析以上信息，输出 JSON 格式的结构化洞察：

```json
{{
  "summary": "一句话总结用户这段时间的主要活动",
  "learnings": [
    {{"content": "具体的学习内容", "confidence": 0.9, "category": "technical"}},
    ...
  ],
  "preferences": [
    {{"type": "工作习惯/工具偏好/编码风格", "value": "具体偏好", "evidence": "证据来源"}}
  ],
  "patterns": [
    {{"pattern": "发现的行为模式", "frequency": 3, "significance": "为什么重要"}}
  ]
}}
```

注意：
1. learnings 的 category 可选: "technical", "workflow", "preference", "insight"
2. confidence 范围 0-1，表示确定程度
3. 只输出有价值的、可操作的洞察
4. 用中文回答
"""
        return prompt

    def _parse_llm_response(self, response: str) -> Optional[Dict[str, Any]]:
        """
        Parse LLM response to extract structured insights.

        Args:
            response: Raw LLM response text

        Returns:
            Parsed insights dict or None
        """
        try:
            # Try to extract JSON from response
            json_match = re.search(r'```json\s*(.*?)\s*```', response, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
            else:
                # Try to find raw JSON
                json_match = re.search(r'\{[\s\S]*\}', response)
                if json_match:
                    json_str = json_match.group(0)
                else:
                    return None

            parsed = json.loads(json_str)

            # Validate structure
            result = {
                "summary": parsed.get("summary", ""),
                "learnings": [],
                "preferences": [],
                "patterns": []
            }

            # Parse learnings
            for learning in parsed.get("learnings", []):
                if isinstance(learning, dict) and learning.get("content"):
                    result["learnings"].append({
                        "content": learning["content"],
                        "confidence": float(learning.get("confidence", 0.8)),
                        "category": learning.get("category", "insight")
                    })

            # Parse preferences
            for pref in parsed.get("preferences", []):
                if isinstance(pref, dict) and pref.get("value"):
                    result["preferences"].append({
                        "type": pref.get("type", "unknown"),
                        "value": pref["value"],
                        "evidence": pref.get("evidence", "")
                    })

            # Parse patterns
            for pattern in parsed.get("patterns", []):
                if isinstance(pattern, dict) and pattern.get("pattern"):
                    result["patterns"].append({
                        "pattern": pattern["pattern"],
                        "frequency": int(pattern.get("frequency", 1)),
                        "significance": pattern.get("significance", "")
                    })

            return result

        except json.JSONDecodeError as e:
            print(f"[Consolidator] Failed to parse LLM JSON: {e}")
            return None
        except Exception as e:
            print(f"[Consolidator] Parse error: {e}")
            return None

    def consolidate(self, hours: int = 24) -> Dict[str, Any]:
        """
        Consolidate recent session archives into structured memory.

        Args:
            hours: How many hours back to look for sessions

        Returns:
            Consolidated memory dictionary
        """
        # Collect recent archives
        cutoff = datetime.now() - timedelta(hours=hours)
        archives = self._collect_archives(cutoff)

        if not archives:
            return {"status": "no_sessions", "message": "No sessions found in the specified time range"}

        # Parse all archives
        sessions = [SessionArchive(path) for path in archives]

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

        # Save memory
        self._save_memory(memory)

        return memory

    def _collect_archives(self, cutoff: datetime) -> List[Path]:
        """Collect archive files modified after cutoff time."""
        if not self.archive_dir.exists():
            return []

        archives = []
        for path in self.archive_dir.glob("*.md"):
            if path.stat().st_mtime > cutoff.timestamp():
                archives.append(path)

        # Sort by modification time
        archives.sort(key=lambda p: p.stat().st_mtime)
        return archives

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
                path = fc["path"]
                action = fc["action"]
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
                file_sessions[fc["path"]].add(session.session_id)

        # Return files touched by more than one session
        return {f for f, s in file_sessions.items() if len(s) > 1}

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

    def _save_memory(self, memory: Dict[str, Any]):
        """Save memory to JSON and optionally Markdown."""
        date_str = memory["date"]

        # Save JSON
        json_path = self.memory_dir / f"{date_str}.json"
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(memory, f, ensure_ascii=False, indent=2)

        # Save human-readable Markdown
        md_path = self.memory_dir / f"{date_str}.md"
        md_content = self._generate_markdown(memory)
        md_path.write_text(md_content, encoding='utf-8')

        print(f"✓ Saved memory: {json_path}")
        print(f"✓ Saved summary: {md_path}")

    def _generate_markdown(self, memory: Dict[str, Any]) -> str:
        """Generate human-readable Markdown from memory."""
        lines = []

        lines.append(f"# Daily Memory: {memory['date']}")
        lines.append("")

        # Overview
        lines.append("## 概览")
        lines.append(f"- **处理会话数**: {memory['sessions_processed']}")
        lines.append(f"- **时间范围**: 最近 {memory['time_range_hours']} 小时")
        lines.append(f"- **使用的模型**: {', '.join(memory['models_used'])}")
        lines.append("")

        # Project Progress
        if memory.get('project_progress'):
            lines.append("## 项目进展")
            for proj, data in memory['project_progress'].items():
                lines.append(f"\n### {proj}")
                if data.get('tasks'):
                    lines.append("**任务:**")
                    for task in data['tasks'][:5]:
                        lines.append(f"- {task}")
                if data.get('files_modified'):
                    lines.append(f"\n**修改的文件**: {len(data['files_modified'])} 个")
                if data.get('learnings'):
                    lines.append("**学到的知识:**")
                    for l in data['learnings'][:3]:
                        lines.append(f"- {l}")
            lines.append("")

        # Tool Usage
        if memory.get('tool_usage_total'):
            lines.append("## 工具使用统计")
            for tool, count in list(memory['tool_usage_total'].items())[:10]:
                lines.append(f"- **{tool}**: {count}次")
            lines.append("")

        # Insights
        if memory.get('cross_session_insights'):
            lines.append("## 跨会话洞察")
            for insight in memory['cross_session_insights']:
                confidence = int(insight['confidence'] * 100)
                lines.append(f"- {insight['pattern']} (置信度: {confidence}%)")
            lines.append("")

        # All Learnings
        if memory.get('all_learnings'):
            lines.append("## 所有学到的知识")
            for learning in memory['all_learnings']:
                lines.append(f"- {learning}")
            lines.append("")

        # Footer
        lines.append("---")
        lines.append(f"*Generated at {memory['generated_at']}*")

        return "\n".join(lines)

    # ========================================================================
    # v2.0: Heuristic Memory Management
    # ========================================================================

    def _load_heuristic_config(self) -> Dict[str, Any]:
        """Load heuristic configuration from file."""
        config_path = Path.home() / ".ccb" / "heuristic_config.json"

        if config_path.exists():
            try:
                with open(config_path) as f:
                    return json.load(f)
            except Exception:
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

        except Exception as e:
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

        except Exception as e:
            print(f"[Consolidator] apply_decay_to_all error: {e}")
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

        except Exception as e:
            print(f"[Consolidator] merge_similar_memories error: {e}")
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

        except Exception as e:
            print(f"[Consolidator] _merge_group error: {e}")
            return None

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

        except Exception as e:
            print(f"[Consolidator] abstract_memory_groups error: {e}")
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

        except Exception as e:
            print(f"[Consolidator] _generate_abstract error: {e}")

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

        except Exception as e:
            print(f"[Consolidator] forget_expired_memories error: {e}")
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
        except Exception as e:
            print(f"[Consolidator] _log_consolidation error: {e}")
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


def main():
    """CLI entry point for consolidator."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Consolidate session archives into long-term memory"
    )
    parser.add_argument(
        "--hours",
        type=int,
        default=24,
        help="Hours to look back (default: 24)"
    )
    parser.add_argument(
        "--archive-dir",
        type=Path,
        help="Archive directory (default: ~/.ccb/context_archive)"
    )
    parser.add_argument(
        "--memory-dir",
        type=Path,
        help="Memory output directory (default: ~/.ccb/memories)"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output JSON to stdout instead of saving"
    )
    parser.add_argument(
        "--llm",
        action="store_true",
        help="Use LLM for enhanced consolidation (Phase 3)"
    )
    parser.add_argument(
        "--llm-provider",
        type=str,
        default="kimi",
        help="LLM provider for consolidation (default: kimi)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run without saving (for testing)"
    )

    args = parser.parse_args()

    consolidator = NightlyConsolidator(
        archive_dir=args.archive_dir,
        memory_dir=args.memory_dir,
        llm_provider=args.llm_provider
    )

    # Choose consolidation method
    if args.llm:
        # Use LLM-enhanced consolidation
        memory = asyncio.run(consolidator.consolidate_with_llm(hours=args.hours))
    else:
        # Basic consolidation
        memory = consolidator.consolidate(hours=args.hours)

    if args.json or args.dry_run:
        print(json.dumps(memory, ensure_ascii=False, indent=2))
    elif memory.get("status") == "no_sessions":
        print("No sessions found in the specified time range")
        sys.exit(0)
    else:
        if memory.get("llm_enhanced"):
            print(f"✓ LLM-enhanced consolidation complete")
            print(f"  - Learnings: {len(memory.get('llm_learnings', []))}")
            print(f"  - Preferences: {len(memory.get('llm_preferences', []))}")
            print(f"  - Patterns: {len(memory.get('llm_patterns', []))}")
        else:
            print(f"✓ Basic consolidation complete")
            if memory.get("llm_error"):
                print(f"  ⚠ LLM error: {memory.get('llm_error')}")


if __name__ == "__main__":
    main()
