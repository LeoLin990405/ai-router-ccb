#!/usr/bin/env python3
"""
JSONL Parser for Claude Code Sessions

Parses Claude Code's session.jsonl files and extracts meaningful content
while filtering out noise (system reminders, protocol markers, signatures).
"""

import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


def _emit(message: str = "") -> None:
    sys.stdout.write(f"{message}\n")


@dataclass
class Message:
    """A single message in the conversation."""
    role: str  # 'user' or 'assistant'
    content: str
    timestamp: str
    uuid: str
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    thinking: Optional[str] = None


@dataclass
class ToolCall:
    """A tool invocation record."""
    tool_name: str
    input_params: Dict[str, Any]
    result: Optional[str] = None
    timestamp: str = ""
    is_error: bool = False


@dataclass
class FileChange:
    """A file modification record."""
    file_path: str
    action: str  # 'read', 'write', 'edit', 'create', 'delete'
    lines_added: int = 0
    lines_removed: int = 0


@dataclass
class SessionData:
    """Parsed session data."""
    session_id: str
    project_path: str
    model: str
    start_time: str
    end_time: str
    messages: List[Message] = field(default_factory=list)
    tool_calls: List[ToolCall] = field(default_factory=list)
    file_changes: List[FileChange] = field(default_factory=list)
    git_branch: str = ""
    version: str = ""


class ClaudeJsonlParser:
    """Parser for Claude Code session.jsonl files."""

    # Patterns to filter out noise content
    NOISE_PATTERNS = [
        r'<system-reminder>.*?</system-reminder>',  # System reminders
        r'<claude-mem-context>.*?</claude-mem-context>',  # Memory context blocks
        r'"signature"\s*:\s*"[A-Za-z0-9+/=]+"',  # Base64 signatures
        r'IMPORTANT:.*?(?=\n\n|\Z)',  # Guardrail warnings (multiline)
        r'<!-- CCB_CONFIG_START -->.*?<!-- CCB_CONFIG_END -->',  # CCB config blocks
        r'<!-- TASK_WORKFLOW_START -->.*?<!-- TASK_WORKFLOW_END -->',  # Workflow blocks
        r'<!-- SKILLS_MAINTENANCE_START -->.*?<!-- SKILLS_MAINTENANCE_END -->',  # Skills blocks
    ]

    # Tool categories for summary
    TOOL_CATEGORIES = {
        'file_read': ['Read', 'Glob', 'Grep'],
        'file_write': ['Write', 'Edit', 'NotebookEdit'],
        'execution': ['Bash', 'Task'],
        'web': ['WebFetch', 'WebSearch'],
        'user_interaction': ['AskUserQuestion'],
    }

    def __init__(self):
        self._compiled_patterns = [
            re.compile(p, re.DOTALL | re.IGNORECASE)
            for p in self.NOISE_PATTERNS
        ]

    def parse(self, jsonl_path: Path) -> SessionData:
        """Parse a session.jsonl file and return structured data."""
        if not jsonl_path.exists():
            raise FileNotFoundError(f"Session file not found: {jsonl_path}")

        lines = jsonl_path.read_text().splitlines()

        session_data = SessionData(
            session_id=jsonl_path.stem[:8],
            project_path="",
            model="",
            start_time="",
            end_time="",
        )

        messages = []
        tool_calls = []
        file_changes = []

        for line in lines:
            if not line.strip():
                continue

            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue

            # Skip file history snapshots
            if obj.get('type') == 'file-history-snapshot':
                continue

            # Skip progress updates
            if obj.get('type') == 'progress':
                continue

            # Extract session metadata
            if not session_data.session_id and obj.get('sessionId'):
                session_data.session_id = obj['sessionId'][:8]

            if not session_data.project_path and obj.get('cwd'):
                session_data.project_path = obj['cwd']

            if not session_data.version and obj.get('version'):
                session_data.version = obj['version']

            if not session_data.git_branch and obj.get('gitBranch'):
                session_data.git_branch = obj['gitBranch']

            # Process user messages
            if obj.get('type') == 'user':
                msg = self._extract_user_message(obj)
                if msg:
                    messages.append(msg)
                    if not session_data.start_time:
                        session_data.start_time = msg.timestamp

            # Process assistant messages
            elif obj.get('type') == 'assistant':
                msg, tools = self._extract_assistant_message(obj)
                if msg:
                    messages.append(msg)
                    session_data.end_time = msg.timestamp
                    if not session_data.model and obj.get('message', {}).get('model'):
                        session_data.model = obj['message']['model']
                tool_calls.extend(tools)

                # Extract file changes from tool calls
                for tool in tools:
                    fc = self._extract_file_change(tool)
                    if fc:
                        file_changes.append(fc)

        session_data.messages = self._deduplicate_messages(messages)
        session_data.tool_calls = tool_calls
        session_data.file_changes = self._deduplicate_file_changes(file_changes)

        return session_data

    def _extract_user_message(self, obj: Dict) -> Optional[Message]:
        """Extract user message from a jsonl entry."""
        message_data = obj.get('message', {})
        content = message_data.get('content', '')

        # Handle list content (tool results)
        if isinstance(content, list):
            text_parts = []
            for item in content:
                if isinstance(item, dict):
                    if item.get('type') == 'text':
                        text_parts.append(item.get('text', ''))
                    elif item.get('type') == 'tool_result':
                        # Skip tool results in user messages
                        pass
                elif isinstance(item, str):
                    text_parts.append(item)
            content = '\n'.join(text_parts)

        content = self._clean_content(content)

        if not content or len(content) < 3:
            return None

        return Message(
            role='user',
            content=content,
            timestamp=obj.get('timestamp', ''),
            uuid=obj.get('uuid', ''),
        )

    def _extract_assistant_message(self, obj: Dict) -> Tuple[Optional[Message], List[ToolCall]]:
        """Extract assistant message and tool calls from a jsonl entry."""
        message_data = obj.get('message', {})
        content_list = message_data.get('content', [])

        if not isinstance(content_list, list):
            content_list = [content_list] if content_list else []

        text_parts = []
        tool_calls = []
        thinking = None

        for item in content_list:
            if not isinstance(item, dict):
                continue

            item_type = item.get('type', '')

            if item_type == 'text':
                text = item.get('text', '')
                cleaned = self._clean_content(text)
                if cleaned:
                    text_parts.append(cleaned)

            elif item_type == 'thinking':
                # Store thinking but don't include in main content
                thinking = item.get('thinking', '')[:500]  # Truncate

            elif item_type == 'tool_use':
                tool_call = ToolCall(
                    tool_name=item.get('name', ''),
                    input_params=item.get('input', {}),
                    timestamp=obj.get('timestamp', ''),
                )
                tool_calls.append(tool_call)

        content = '\n\n'.join(text_parts)

        if not content and not tool_calls:
            return None, []

        message = Message(
            role='assistant',
            content=content,
            timestamp=obj.get('timestamp', ''),
            uuid=obj.get('uuid', ''),
            tool_calls=[{'name': tc.tool_name, 'input': tc.input_params} for tc in tool_calls],
            thinking=thinking,
        ) if content else None

        return message, tool_calls

    def _extract_file_change(self, tool_call: ToolCall) -> Optional[FileChange]:
        """Extract file change from a tool call."""
        name = tool_call.tool_name
        params = tool_call.input_params

        if name == 'Read':
            return FileChange(
                file_path=params.get('file_path', ''),
                action='read',
            )
        elif name == 'Write':
            return FileChange(
                file_path=params.get('file_path', ''),
                action='write',
            )
        elif name == 'Edit':
            return FileChange(
                file_path=params.get('file_path', ''),
                action='edit',
            )

        return None

    def _clean_content(self, content: str) -> str:
        """Remove noise patterns from content."""
        if not content:
            return ""

        # Apply all noise filters
        for pattern in self._compiled_patterns:
            content = pattern.sub('', content)

        # Clean up excessive whitespace
        content = re.sub(r'\n{3,}', '\n\n', content)
        content = content.strip()

        return content

    def _deduplicate_messages(self, messages: List[Message]) -> List[Message]:
        """Remove duplicate messages (same uuid or very similar content)."""
        seen_uuids = set()
        result = []

        for msg in messages:
            if msg.uuid in seen_uuids:
                continue
            seen_uuids.add(msg.uuid)
            result.append(msg)

        return result

    def _deduplicate_file_changes(self, changes: List[FileChange]) -> List[FileChange]:
        """Consolidate file changes to unique paths with action summary."""
        path_to_actions = {}

        for fc in changes:
            if not fc.file_path:
                continue

            if fc.file_path not in path_to_actions:
                path_to_actions[fc.file_path] = set()
            path_to_actions[fc.file_path].add(fc.action)

        result = []
        for path, actions in path_to_actions.items():
            # Prioritize write actions
            if 'write' in actions or 'edit' in actions:
                action = 'modified'
            else:
                action = 'read'

            result.append(FileChange(file_path=path, action=action))

        return result

    def get_tool_summary(self, tool_calls: List[ToolCall]) -> Dict[str, int]:
        """Summarize tool usage counts."""
        counts = {}
        for tc in tool_calls:
            name = tc.tool_name
            counts[name] = counts.get(name, 0) + 1
        return counts

    def get_session_duration(self, session: SessionData) -> Optional[str]:
        """Calculate session duration as human-readable string."""
        if not session.start_time or not session.end_time:
            return None

        try:
            start = datetime.fromisoformat(session.start_time.replace('Z', '+00:00'))
            end = datetime.fromisoformat(session.end_time.replace('Z', '+00:00'))
            delta = end - start

            minutes = int(delta.total_seconds() / 60)
            if minutes < 60:
                return f"{minutes} min"
            else:
                hours = minutes // 60
                mins = minutes % 60
                return f"{hours}h {mins}m"
        except (ValueError, TypeError, OSError):
            return None


def main():
    """CLI for testing the parser."""
    import sys

    if len(sys.argv) < 2:
        _emit("Usage: jsonl_parser.py <session.jsonl>")
        sys.exit(1)

    path = Path(sys.argv[1])
    parser = ClaudeJsonlParser()

    try:
        session = parser.parse(path)

        _emit(f"Session ID: {session.session_id}")
        _emit(f"Project: {session.project_path}")
        _emit(f"Model: {session.model}")
        _emit(f"Duration: {parser.get_session_duration(session)}")
        _emit(f"Messages: {len(session.messages)}")
        _emit(f"Tool Calls: {len(session.tool_calls)}")
        _emit(f"Files Changed: {len(session.file_changes)}")

        _emit("\nTool Summary:")
        for tool, count in parser.get_tool_summary(session.tool_calls).items():
            _emit(f"  - {tool}: {count}")

        _emit("\nFile Changes:")
        for fc in session.file_changes[:10]:
            _emit(f"  - [{fc.action}] {fc.file_path}")

        _emit("\nSample Messages:")
        for msg in session.messages[:3]:
            preview = msg.content[:100].replace('\n', ' ')
            _emit(f"  [{msg.role}] {preview}...")

    except (RuntimeError, ValueError, TypeError, OSError, json.JSONDecodeError) as e:
        _emit(f"Error parsing session: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
