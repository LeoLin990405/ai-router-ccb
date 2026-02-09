"""Data models for memory consolidator."""
from __future__ import annotations

import json
from typing import Any, Dict


class SessionArchive:
    """Represents a parsed session archive from database."""

    def __init__(self, data: Dict[str, Any]):
        """Initialize from database row dictionary."""
        self.archive_id = data.get('archive_id', '')
        self.session_id = data.get('session_id', '')
        self.project_path = data.get('project_path', '')
        self.timestamp = data.get('start_time', '')
        self.duration = str(data.get('duration_minutes', 0)) + ' 分钟'
        self.model = data.get('model', '')
        self.task_summary = data.get('task_summary', '')
        self.message_count = data.get('message_count', 0)
        self.tool_call_count = data.get('tool_call_count', 0)

        # Parse JSON fields
        self.key_messages = data.get('key_messages', [])
        if isinstance(self.key_messages, str):
            try:
                self.key_messages = json.loads(self.key_messages)
            except json.JSONDecodeError:
                self.key_messages = []

        self.tool_calls = data.get('tool_usage', {})
        if isinstance(self.tool_calls, str):
            try:
                self.tool_calls = json.loads(self.tool_calls)
            except json.JSONDecodeError:
                self.tool_calls = {}

        self.file_changes = data.get('file_changes', [])
        if isinstance(self.file_changes, str):
            try:
                self.file_changes = json.loads(self.file_changes)
            except json.JSONDecodeError:
                self.file_changes = []

        self.learnings = data.get('learnings', [])
        if isinstance(self.learnings, str):
            try:
                self.learnings = json.loads(self.learnings)
            except json.JSONDecodeError:
                self.learnings = []


