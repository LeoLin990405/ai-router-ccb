"""Discussion exporters for markdown/json/html and Obsidian."""

from __future__ import annotations

import json
from datetime import datetime
from typing import List

from .models import DiscussionSession, DiscussionMessage, MessageType
from .state_store import StateStore


class DiscussionExporter:
    """Exports discussions to various formats (Markdown, JSON, HTML)."""

    def __init__(self, store: StateStore):
        self.store = store

    def export(
        self,
        session_id: str,
        format: str = "md",
        include_metadata: bool = True,
    ) -> str:
        """
        Export a discussion to the specified format.

        Args:
            session_id: The discussion session ID
            format: Export format - 'md', 'json', or 'html'
            include_metadata: Whether to include metadata in export

        Returns:
            Exported content as string
        """
        session = self.store.get_discussion_session(session_id)
        if not session:
            raise ValueError(f"Discussion not found: {session_id}")

        messages = self.store.get_discussion_messages(session_id)

        if format == "json":
            return self._export_json(session, messages, include_metadata)
        elif format == "html":
            return self._export_html(session, messages, include_metadata)
        else:  # Default to markdown
            return self._export_markdown(session, messages, include_metadata)

    def _export_markdown(
        self,
        session: DiscussionSession,
        messages: List[DiscussionMessage],
        include_metadata: bool,
    ) -> str:
        """Export discussion to Markdown format."""
        lines = []

        # Header with metadata
        if include_metadata:
            lines.append("---")
            lines.append(f"title: \"{session.topic}\"")
            lines.append(f"session_id: {session.id}")
            lines.append(f"status: {session.status.value}")
            lines.append(f"providers: [{', '.join(session.providers)}]")
            lines.append(f"created_at: {datetime.fromtimestamp(session.created_at).isoformat()}")
            if session.updated_at:
                lines.append(f"updated_at: {datetime.fromtimestamp(session.updated_at).isoformat()}")
            lines.append("---")
            lines.append("")

        # Title
        lines.append(f"# {session.topic}")
        lines.append("")
        lines.append(f"**Participants:** {', '.join(session.providers)}")
        lines.append(f"**Status:** {session.status.value}")
        lines.append("")

        # Group messages by round
        round_1 = [m for m in messages if m.round_number == 1]
        round_2 = [m for m in messages if m.round_number == 2]
        round_3 = [m for m in messages if m.round_number == 3]
        summary_msgs = [m for m in messages if m.message_type == MessageType.SUMMARY]

        # Round 1: Proposals
        if round_1:
            lines.append("## Round 1: Initial Proposals")
            lines.append("")
            for msg in round_1:
                lines.append(f"### {msg.provider}")
                if msg.latency_ms:
                    lines.append(f"*Response time: {msg.latency_ms:.0f}ms*")
                lines.append("")
                lines.append(msg.content or "*No content*")
                lines.append("")

        # Round 2: Reviews
        if round_2:
            lines.append("## Round 2: Reviews and Feedback")
            lines.append("")
            for msg in round_2:
                lines.append(f"### {msg.provider}")
                if msg.latency_ms:
                    lines.append(f"*Response time: {msg.latency_ms:.0f}ms*")
                lines.append("")
                lines.append(msg.content or "*No content*")
                lines.append("")

        # Round 3: Revisions
        if round_3:
            lines.append("## Round 3: Revised Proposals")
            lines.append("")
            for msg in round_3:
                lines.append(f"### {msg.provider}")
                if msg.latency_ms:
                    lines.append(f"*Response time: {msg.latency_ms:.0f}ms*")
                lines.append("")
                lines.append(msg.content or "*No content*")
                lines.append("")

        # Summary
        if session.summary or summary_msgs:
            lines.append("## Summary")
            lines.append("")
            if summary_msgs:
                for msg in summary_msgs:
                    lines.append(f"*Synthesized by {msg.provider}*")
                    lines.append("")
                    lines.append(msg.content or session.summary or "*No summary*")
            else:
                lines.append(session.summary or "*No summary available*")
            lines.append("")

        return "\n".join(lines)

    def _export_json(
        self,
        session: DiscussionSession,
        messages: List[DiscussionMessage],
        include_metadata: bool,
    ) -> str:
        """Export discussion to JSON format."""
        data = {
            "session": {
                "id": session.id,
                "topic": session.topic,
                "status": session.status.value,
                "providers": session.providers,
                "current_round": session.current_round,
                "summary": session.summary,
                "created_at": session.created_at,
                "updated_at": session.updated_at,
            },
            "messages": [
                {
                    "id": m.id,
                    "round_number": m.round_number,
                    "provider": m.provider,
                    "message_type": m.message_type.value,
                    "content": m.content,
                    "status": m.status,
                    "latency_ms": m.latency_ms,
                    "created_at": m.created_at,
                }
                for m in messages
            ],
        }

        if include_metadata:
            data["session"]["config"] = session.config.to_dict()
            data["session"]["metadata"] = session.metadata
            for i, m in enumerate(messages):
                data["messages"][i]["metadata"] = m.metadata

        return json.dumps(data, indent=2, ensure_ascii=False)

    def _export_html(
        self,
        session: DiscussionSession,
        messages: List[DiscussionMessage],
        include_metadata: bool,
    ) -> str:
        """Export discussion to HTML format."""
        # Group messages by round
        round_1 = [m for m in messages if m.round_number == 1]
        round_2 = [m for m in messages if m.round_number == 2]
        round_3 = [m for m in messages if m.round_number == 3]
        summary_msgs = [m for m in messages if m.message_type == MessageType.SUMMARY]

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{session.topic} - CCB Discussion</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            max-width: 900px;
            margin: 0 auto;
            padding: 20px;
            background: #f5f5f5;
            color: #333;
        }}
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            border-radius: 10px;
            margin-bottom: 30px;
        }}
        .header h1 {{
            margin: 0 0 10px 0;
        }}
        .meta {{
            opacity: 0.9;
            font-size: 14px;
        }}
        .round {{
            background: white;
            border-radius: 10px;
            padding: 20px;
            margin-bottom: 20px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}
        .round h2 {{
            color: #667eea;
            border-bottom: 2px solid #eee;
            padding-bottom: 10px;
        }}
        .message {{
            border-left: 4px solid #667eea;
            padding: 15px;
            margin: 15px 0;
            background: #f9f9f9;
            border-radius: 0 8px 8px 0;
        }}
        .message h3 {{
            margin: 0 0 10px 0;
            color: #333;
        }}
        .message .latency {{
            font-size: 12px;
            color: #888;
            margin-bottom: 10px;
        }}
        .message .content {{
            white-space: pre-wrap;
            line-height: 1.6;
        }}
        .summary {{
            background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
        }}
        .summary h2 {{
            color: #2d3748;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>{session.topic}</h1>
        <div class="meta">
            <strong>Participants:</strong> {', '.join(session.providers)}<br>
            <strong>Status:</strong> {session.status.value}<br>
            <strong>Session ID:</strong> {session.id}
        </div>
    </div>
"""

        def render_messages(msgs: List[DiscussionMessage], title: str) -> str:
            if not msgs:
                return ""
            html_part = f'<div class="round"><h2>{title}</h2>'
            for msg in msgs:
                latency = f'<div class="latency">Response time: {msg.latency_ms:.0f}ms</div>' if msg.latency_ms else ''
                content = (msg.content or '*No content*').replace('<', '&lt;').replace('>', '&gt;')
                html_part += f'''
                <div class="message">
                    <h3>{msg.provider}</h3>
                    {latency}
                    <div class="content">{content}</div>
                </div>
'''
            html_part += '</div>'
            return html_part

        html += render_messages(round_1, "Round 1: Initial Proposals")
        html += render_messages(round_2, "Round 2: Reviews and Feedback")
        html += render_messages(round_3, "Round 3: Revised Proposals")

        # Summary
        if session.summary or summary_msgs:
            summary_content = ""
            if summary_msgs:
                for msg in summary_msgs:
                    summary_content = (msg.content or session.summary or "*No summary*").replace('<', '&lt;').replace('>', '&gt;')
            else:
                summary_content = (session.summary or "*No summary available*").replace('<', '&lt;').replace('>', '&gt;')

            html += f'''
    <div class="round summary">
        <h2>Summary</h2>
        <div class="content" style="white-space: pre-wrap; line-height: 1.6;">{summary_content}</div>
    </div>
'''

        html += """
</body>
</html>
"""
        return html

class ObsidianExporter:
    """Exports discussions to Obsidian vault format."""

    def __init__(self, store: StateStore):
        self.store = store

    def export_to_vault(
        self,
        session_id: str,
        vault_path: str,
        folder: str = "CCB Discussions",
    ) -> str:
        """
        Export a discussion to an Obsidian vault.

        Args:
            session_id: The discussion session ID
            vault_path: Path to the Obsidian vault
            folder: Subfolder within the vault

        Returns:
            Path to the created file
        """
        from pathlib import Path

        session = self.store.get_discussion_session(session_id)
        if not session:
            raise ValueError(f"Discussion not found: {session_id}")

        messages = self.store.get_discussion_messages(session_id)

        # Generate content
        content = self._generate_obsidian_content(session, messages)

        # Create filename
        date_str = datetime.fromtimestamp(session.created_at).strftime("%Y-%m-%d")
        topic_slug = self._slugify(session.topic[:50])
        filename = f"{date_str} - {topic_slug}.md"

        # Create folder if needed
        vault = Path(vault_path).expanduser()
        target_dir = vault / folder
        target_dir.mkdir(parents=True, exist_ok=True)

        # Write file
        target_path = target_dir / filename
        with open(target_path, "w", encoding="utf-8") as f:
            f.write(content)

        return str(target_path)

    def _slugify(self, text: str) -> str:
        """Convert text to a safe filename slug."""
        import re
        # Replace spaces and special chars
        slug = re.sub(r'[^\w\s-]', '', text)
        slug = re.sub(r'[\s_]+', '-', slug)
        return slug.strip('-').lower()

    def _generate_obsidian_content(
        self,
        session: DiscussionSession,
        messages: List[DiscussionMessage],
    ) -> str:
        """Generate Obsidian-compatible markdown content."""
        lines = []

        # YAML frontmatter
        lines.append("---")
        lines.append(f"title: \"{session.topic}\"")
        lines.append(f"session_id: {session.id}")
        lines.append(f"status: {session.status.value}")
        lines.append(f"providers:")
        for p in session.providers:
            lines.append(f"  - {p}")
        lines.append(f"created: {datetime.fromtimestamp(session.created_at).strftime('%Y-%m-%dT%H:%M:%S')}")
        lines.append("tags:")
        lines.append("  - ccb-discussion")
        lines.append("  - ai-collaboration")
        for p in session.providers:
            lines.append(f"  - provider/{p}")
        lines.append("---")
        lines.append("")

        # Title and metadata
        lines.append(f"# {session.topic}")
        lines.append("")
        lines.append("> [!info] Discussion Metadata")
        lines.append(f"> **Participants:** {', '.join(session.providers)}")
        lines.append(f"> **Status:** {session.status.value}")
        lines.append(f"> **Session ID:** `{session.id}`")
        lines.append("")

        # Group messages by round
        round_1 = [m for m in messages if m.round_number == 1]
        round_2 = [m for m in messages if m.round_number == 2]
        round_3 = [m for m in messages if m.round_number == 3]
        summary_msgs = [m for m in messages if m.message_type == MessageType.SUMMARY]

        # Round 1
        if round_1:
            lines.append("## 📝 Round 1: Initial Proposals")
            lines.append("")
            for msg in round_1:
                lines.append(f"### {msg.provider}")
                if msg.latency_ms:
                    lines.append(f"*⏱️ {msg.latency_ms:.0f}ms*")
                lines.append("")
                lines.append(msg.content or "*No content*")
                lines.append("")

        # Round 2
        if round_2:
            lines.append("## 🔍 Round 2: Reviews")
            lines.append("")
            for msg in round_2:
                lines.append(f"### {msg.provider}")
                if msg.latency_ms:
                    lines.append(f"*⏱️ {msg.latency_ms:.0f}ms*")
                lines.append("")
                lines.append(msg.content or "*No content*")
                lines.append("")

        # Round 3
        if round_3:
            lines.append("## ✏️ Round 3: Revisions")
            lines.append("")
            for msg in round_3:
                lines.append(f"### {msg.provider}")
                if msg.latency_ms:
                    lines.append(f"*⏱️ {msg.latency_ms:.0f}ms*")
                lines.append("")
                lines.append(msg.content or "*No content*")
                lines.append("")

        # Summary
        if session.summary or summary_msgs:
            lines.append("## 📋 Summary")
            lines.append("")
            lines.append("> [!summary]")
            summary_content = ""
            if summary_msgs:
                summary_content = summary_msgs[0].content or session.summary or "*No summary*"
            else:
                summary_content = session.summary or "*No summary available*"

            # Indent for callout
            for line in summary_content.split("\n"):
                lines.append(f"> {line}")
            lines.append("")

        # Footer
        lines.append("---")
        lines.append("*Generated by CCB Gateway*")

        return "\n".join(lines)
