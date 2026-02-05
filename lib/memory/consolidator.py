#!/usr/bin/env python3
"""
Memory Consolidator - System 2: Nightly Memory Integration

Collects recent session archives and generates structured long-term memory.
This is the "slow, deep thinking" part of the dual-system memory architecture.

Phase 3 Enhancement: LLM-powered insight extraction
"""

import asyncio
import json
import re
import sys
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

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
    """System 2: Consolidates session archives into structured long-term memory."""

    # Gateway API URL for LLM calls
    GATEWAY_URL = "http://localhost:8765"

    # Default LLM provider for consolidation (Kimi is fast and has free quota)
    DEFAULT_LLM_PROVIDER = "kimi"

    def __init__(
        self,
        archive_dir: Optional[Path] = None,
        memory_dir: Optional[Path] = None,
        llm_provider: str = None
    ):
        self.archive_dir = archive_dir or Path.home() / ".ccb" / "context_archive"
        self.memory_dir = memory_dir or Path.home() / ".ccb" / "memories"
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        self.llm_provider = llm_provider or self.DEFAULT_LLM_PROVIDER

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
