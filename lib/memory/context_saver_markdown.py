"""Auto-split mixins for ContextSaver."""

import json
import os
import re
import sqlite3
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

from memory.jsonl_parser import ClaudeJsonlParser, Message, SessionData, ToolCall

try:
    from lib.common.logging import get_logger
except ImportError:  # pragma: no cover - script mode
    try:
        from common.logging import get_logger  # type: ignore
    except ImportError:  # pragma: no cover - fallback
        import logging

        def get_logger(name: str):
            return logging.getLogger(name)


logger = get_logger("memory.context_saver")


class ContextSaverMarkdownMixin:
    """Mixin methods extracted from ContextSaver."""

    def _generate_markdown(self, session: SessionData) -> str:
        """Generate Markdown content from parsed session data."""
        lines = []

        # Header
        lines.append(f"# Session: {session.session_id}")
        lines.append("")

        # Metadata
        lines.append("## Metadata")
        lines.append(f"- **项目路径**: `{session.project_path}`")
        if session.start_time:
            start_str = self._format_timestamp(session.start_time)
            end_str = self._format_timestamp(session.end_time) if session.end_time else "ongoing"
            lines.append(f"- **时间**: {start_str} ~ {end_str}")

        duration = self.parser.get_session_duration(session)
        if duration:
            lines.append(f"- **时长**: {duration}")

        lines.append(f"- **模型**: {session.model or 'unknown'}")

        if session.git_branch and session.git_branch != 'HEAD':
            lines.append(f"- **Git 分支**: {session.git_branch}")

        lines.append("")

        # Task Summary
        task_summary = self._extract_task_summary(session)
        if task_summary:
            lines.append("## 任务摘要")
            lines.append(task_summary)
            lines.append("")

        # Key Conversations
        key_messages = self._extract_key_messages(session)
        if key_messages:
            lines.append("## 关键对话")
            lines.append("")
            for msg in key_messages:
                time_str = self._format_time_short(msg.timestamp)
                role_cn = "用户" if msg.role == "user" else "Claude"
                lines.append(f"### {role_cn} {time_str}")

                # Format content as blockquote for user, normal for assistant
                if msg.role == "user":
                    content = self._truncate_content(msg.content, 500)
                    lines.append(f"> {content.replace(chr(10), chr(10) + '> ')}")
                else:
                    content = self._truncate_content(msg.content, 1000)
                    lines.append(content)

                lines.append("")

        # Tool Usage Summary
        tool_summary = self.parser.get_tool_summary(session.tool_calls)
        if tool_summary:
            lines.append("## 工具调用")
            for tool, count in sorted(tool_summary.items(), key=lambda x: -x[1]):
                lines.append(f"- **{tool}**: {count}次")
            lines.append("")

        # File Changes
        if session.file_changes:
            lines.append("## 文件变更")
            for fc in session.file_changes[:20]:  # Limit to top 20
                action_emoji = "📝" if fc.action == "modified" else "📖"
                # Shorten path for readability
                short_path = self._shorten_path(fc.file_path)
                lines.append(f"- {action_emoji} `{short_path}` ({fc.action})")
            lines.append("")

        # Learnings (extracted from thinking or conversation patterns)
        learnings = self._extract_learnings(session)
        if learnings:
            lines.append("## 学到的知识")
            for learning in learnings:
                lines.append(f"- {learning}")
            lines.append("")

        # Footer
        lines.append("---")
        lines.append(f"*Archived by ccb-mem at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*")

        return "\n".join(lines)

    def _extract_task_summary(self, session: SessionData) -> str:
        """Extract a brief task summary from the first user message."""
        for msg in session.messages:
            if msg.role == "user" and len(msg.content) > 10:
                # Take first sentence or first 200 chars
                content = msg.content.strip()
                first_sentence = re.split(r'[。.!?！？\n]', content)[0]
                if len(first_sentence) > 200:
                    first_sentence = first_sentence[:200] + "..."
                return first_sentence

        return ""

    def _extract_key_messages(self, session: SessionData, max_messages: int = 8) -> List[Message]:
        """Select the most important messages from the session."""
        key_messages = []

        # Always include first user message
        for msg in session.messages:
            if msg.role == "user":
                key_messages.append(msg)
                break

        # Include messages with substantial content
        for msg in session.messages:
            if msg in key_messages:
                continue

            # Skip very short messages
            if len(msg.content) < 50:
                continue

            # Prioritize user messages
            if msg.role == "user":
                key_messages.append(msg)
            # Include assistant messages with code blocks or structured content
            elif msg.role == "assistant":
                if '```' in msg.content or '##' in msg.content or len(msg.content) > 300:
                    key_messages.append(msg)

            if len(key_messages) >= max_messages:
                break

        # Sort by timestamp
        key_messages.sort(key=lambda m: m.timestamp)

        return key_messages

    def _extract_learnings(self, session: SessionData) -> List[str]:
        """Extract insights and learnings from the session."""
        learnings = []

        # Look for patterns in assistant messages
        learning_patterns = [
            r'(?:发现|原来|注意到)[：:]\s*(.+?)(?:\n|$)',
            r'(?:这是因为|原因是)[：:]\s*(.+?)(?:\n|$)',
            r'(?:学到|明白了)[：:]\s*(.+?)(?:\n|$)',
            r'(?:关键点|要点)[：:]\s*(.+?)(?:\n|$)',
        ]

        for msg in session.messages:
            if msg.role != "assistant":
                continue

            for pattern in learning_patterns:
                matches = re.findall(pattern, msg.content, re.IGNORECASE)
                for match in matches[:2]:  # Max 2 per pattern
                    if len(match) > 20 and len(match) < 200:
                        learnings.append(match.strip())

        # Deduplicate
        seen = set()
        unique = []
        for l in learnings:
            if l not in seen:
                seen.add(l)
                unique.append(l)

        return unique[:5]  # Max 5 learnings

    def _format_timestamp(self, ts: str) -> str:
        """Format ISO timestamp to readable format."""
        if not ts:
            return "unknown"
        try:
            dt = datetime.fromisoformat(ts.replace('Z', '+00:00'))
            return dt.strftime("%Y-%m-%d %H:%M")
        except (ValueError, TypeError):
            return ts[:16] if len(ts) > 16 else ts

    def _format_time_short(self, ts: str) -> str:
        """Format timestamp to short time only."""
        if not ts:
            return ""
        try:
            dt = datetime.fromisoformat(ts.replace('Z', '+00:00'))
            return dt.strftime("%H:%M")
        except (ValueError, TypeError):
            return ""

    def _truncate_content(self, content: str, max_len: int) -> str:
        """Truncate content to max length, preserving word boundaries."""
        if len(content) <= max_len:
            return content

        truncated = content[:max_len]
        # Try to break at word boundary
        last_space = truncated.rfind(' ')
        if last_space > max_len * 0.7:
            truncated = truncated[:last_space]

        return truncated + "..."

    def _shorten_path(self, path: str) -> str:
        """Shorten file path for display."""
        home = str(Path.home())
        if path.startswith(home):
            return "~" + path[len(home):]
        return path


