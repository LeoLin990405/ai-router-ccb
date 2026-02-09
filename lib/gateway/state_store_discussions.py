"""StateStore operation helpers extracted from ``StateStore``."""

from __future__ import annotations

import json
import sqlite3
import time
from typing import Optional, List, Dict, Any

from .models import (
    RequestStatus,
    GatewayRequest,
    GatewayResponse,
    ProviderInfo,
    ProviderStatus,
    BackendType,
    DiscussionStatus,
    DiscussionSession,
    DiscussionMessage,
    DiscussionConfig,
    MessageType,
)


def create_discussion_session_impl(self, session: DiscussionSession) -> DiscussionSession:
    """Create a new discussion session."""
    with self._get_connection() as conn:
        conn.execute("""
            INSERT INTO discussion_sessions (
                id, topic, status, current_round, providers,
                config, created_at, updated_at, summary, metadata
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            session.id,
            session.topic,
            session.status.value,
            session.current_round,
            json.dumps(session.providers),
            json.dumps(session.config.to_dict()),
            session.created_at,
            session.updated_at,
            session.summary,
            json.dumps(session.metadata) if session.metadata else None,
        ))
    return session

def get_discussion_session_impl(self, session_id: str) -> Optional[DiscussionSession]:
    """Get a discussion session by ID."""
    with self._get_connection() as conn:
        cursor = conn.execute(
            "SELECT * FROM discussion_sessions WHERE id = ?",
            (session_id,)
        )
        row = cursor.fetchone()
        if row:
            return self._row_to_discussion_session(row)
    return None

def update_discussion_session_impl(
    self,
    session_id: str,
    status: Optional[DiscussionStatus] = None,
    current_round: Optional[int] = None,
    summary: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> bool:
    """Update a discussion session."""
    now = time.time()
    updates = ["updated_at = ?"]
    params: List[Any] = [now]

    if status is not None:
        updates.append("status = ?")
        params.append(status.value)

    if current_round is not None:
        updates.append("current_round = ?")
        params.append(current_round)

    if summary is not None:
        updates.append("summary = ?")
        params.append(summary)

    if metadata is not None:
        updates.append("metadata = ?")
        params.append(json.dumps(metadata))

    params.append(session_id)

    with self._get_connection() as conn:
        cursor = conn.execute(
            f"UPDATE discussion_sessions SET {', '.join(updates)} WHERE id = ?",
            params
        )
        return cursor.rowcount > 0

def list_discussion_sessions_impl(
    self,
    status: Optional[DiscussionStatus] = None,
    limit: int = 50,
    offset: int = 0,
) -> List[DiscussionSession]:
    """List discussion sessions with optional filtering."""
    query = "SELECT * FROM discussion_sessions WHERE 1=1"
    params: List[Any] = []

    if status:
        query += " AND status = ?"
        params.append(status.value)

    query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    with self._get_connection() as conn:
        cursor = conn.execute(query, params)
        return [self._row_to_discussion_session(row) for row in cursor.fetchall()]

def delete_discussion_session_impl(self, session_id: str) -> bool:
    """Delete a discussion session and its messages."""
    with self._get_connection() as conn:
        # Delete messages first
        conn.execute(
            "DELETE FROM discussion_messages WHERE session_id = ?",
            (session_id,)
        )
        # Delete session
        cursor = conn.execute(
            "DELETE FROM discussion_sessions WHERE id = ?",
            (session_id,)
        )
        return cursor.rowcount > 0

def _row_to_discussion_session_impl(self, row: sqlite3.Row) -> DiscussionSession:
    """Convert database row to DiscussionSession."""
    return DiscussionSession(
        id=row["id"],
        topic=row["topic"],
        status=DiscussionStatus(row["status"]),
        current_round=row["current_round"],
        providers=json.loads(row["providers"]),
        config=DiscussionConfig.from_dict(json.loads(row["config"])) if row["config"] else DiscussionConfig(),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        summary=row["summary"],
        metadata=json.loads(row["metadata"]) if row["metadata"] else None,
    )

def create_discussion_message_impl(self, message: DiscussionMessage) -> DiscussionMessage:
    """Create a new discussion message."""
    with self._get_connection() as conn:
        conn.execute("""
            INSERT INTO discussion_messages (
                id, session_id, round_number, provider, message_type,
                content, references_messages, latency_ms, status,
                created_at, metadata
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            message.id,
            message.session_id,
            message.round_number,
            message.provider,
            message.message_type.value,
            message.content,
            json.dumps(message.references_messages) if message.references_messages else None,
            message.latency_ms,
            message.status,
            message.created_at,
            json.dumps(message.metadata) if message.metadata else None,
        ))
    return message

def update_discussion_message_impl(
    self,
    message_id: str,
    content: Optional[str] = None,
    status: Optional[str] = None,
    latency_ms: Optional[float] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> bool:
    """Update a discussion message."""
    updates = []
    params: List[Any] = []

    if content is not None:
        updates.append("content = ?")
        params.append(content)

    if status is not None:
        updates.append("status = ?")
        params.append(status)

    if latency_ms is not None:
        updates.append("latency_ms = ?")
        params.append(latency_ms)

    if metadata is not None:
        updates.append("metadata = ?")
        params.append(json.dumps(metadata))

    if not updates:
        return False

    params.append(message_id)

    with self._get_connection() as conn:
        cursor = conn.execute(
            f"UPDATE discussion_messages SET {', '.join(updates)} WHERE id = ?",
            params
        )
        return cursor.rowcount > 0

def get_discussion_messages_impl(
    self,
    session_id: str,
    round_number: Optional[int] = None,
    provider: Optional[str] = None,
    message_type: Optional[MessageType] = None,
) -> List[DiscussionMessage]:
    """Get discussion messages with optional filtering."""
    query = "SELECT * FROM discussion_messages WHERE session_id = ?"
    params: List[Any] = [session_id]

    if round_number is not None:
        query += " AND round_number = ?"
        params.append(round_number)

    if provider is not None:
        query += " AND provider = ?"
        params.append(provider)

    if message_type is not None:
        query += " AND message_type = ?"
        params.append(message_type.value)

    query += " ORDER BY round_number ASC, created_at ASC"

    with self._get_connection() as conn:
        cursor = conn.execute(query, params)
        return [self._row_to_discussion_message(row) for row in cursor.fetchall()]

def _row_to_discussion_message_impl(self, row: sqlite3.Row) -> DiscussionMessage:
    """Convert database row to DiscussionMessage."""
    return DiscussionMessage(
        id=row["id"],
        session_id=row["session_id"],
        round_number=row["round_number"],
        provider=row["provider"],
        message_type=MessageType(row["message_type"]),
        content=row["content"],
        references_messages=json.loads(row["references_messages"]) if row["references_messages"] else None,
        latency_ms=row["latency_ms"],
        status=row["status"],
        created_at=row["created_at"],
        metadata=json.loads(row["metadata"]) if row["metadata"] else None,
    )

def cleanup_old_discussions_impl(self, max_age_hours: int = 168) -> int:
    """Remove discussions older than specified age (default 7 days)."""
    cutoff = time.time() - (max_age_hours * 3600)
    with self._get_connection() as conn:
        # Delete messages first
        conn.execute("""
            DELETE FROM discussion_messages
            WHERE session_id IN (
                SELECT id FROM discussion_sessions WHERE created_at < ?
            )
        """, (cutoff,))
        # Delete sessions
        cursor = conn.execute(
            "DELETE FROM discussion_sessions WHERE created_at < ?",
            (cutoff,)
        )
        return cursor.rowcount

def create_discussion_template_impl(
    self,
    name: str,
    topic_template: str,
    description: Optional[str] = None,
    default_providers: Optional[List[str]] = None,
    default_config: Optional[Dict[str, Any]] = None,
    category: Optional[str] = None,
) -> Dict[str, Any]:
    """Create a new discussion template."""
    import uuid
    template_id = str(uuid.uuid4())[:12]
    now = time.time()

    with self._get_connection() as conn:
        conn.execute("""
            INSERT INTO discussion_templates (
                id, name, description, topic_template, default_providers,
                default_config, category, created_at, updated_at, is_builtin
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
        """, (
            template_id,
            name,
            description,
            topic_template,
            json.dumps(default_providers) if default_providers else None,
            json.dumps(default_config) if default_config else None,
            category,
            now,
            now,
        ))

    return self.get_discussion_template(template_id)

def get_discussion_template_impl(self, template_id: str) -> Optional[Dict[str, Any]]:
    """Get a discussion template by ID."""
    with self._get_connection() as conn:
        cursor = conn.execute(
            "SELECT * FROM discussion_templates WHERE id = ?",
            (template_id,)
        )
        row = cursor.fetchone()
        if row:
            return self._row_to_template(row)
    return None

def get_discussion_template_by_name_impl(self, name: str) -> Optional[Dict[str, Any]]:
    """Get a discussion template by name."""
    with self._get_connection() as conn:
        cursor = conn.execute(
            "SELECT * FROM discussion_templates WHERE name = ?",
            (name,)
        )
        row = cursor.fetchone()
        if row:
            return self._row_to_template(row)
    return None

def list_discussion_templates_impl(
    self,
    category: Optional[str] = None,
    include_builtin: bool = True,
) -> List[Dict[str, Any]]:
    """List discussion templates with optional filtering."""
    query = "SELECT * FROM discussion_templates WHERE 1=1"
    params: List[Any] = []

    if category:
        query += " AND category = ?"
        params.append(category)

    if not include_builtin:
        query += " AND is_builtin = 0"

    query += " ORDER BY usage_count DESC, name ASC"

    with self._get_connection() as conn:
        cursor = conn.execute(query, params)
        return [self._row_to_template(row) for row in cursor.fetchall()]

def update_discussion_template_impl(
    self,
    template_id: str,
    name: Optional[str] = None,
    description: Optional[str] = None,
    topic_template: Optional[str] = None,
    default_providers: Optional[List[str]] = None,
    default_config: Optional[Dict[str, Any]] = None,
    category: Optional[str] = None,
) -> bool:
    """Update a discussion template."""
    updates = ["updated_at = ?"]
    params: List[Any] = [time.time()]

    if name is not None:
        updates.append("name = ?")
        params.append(name)
    if description is not None:
        updates.append("description = ?")
        params.append(description)
    if topic_template is not None:
        updates.append("topic_template = ?")
        params.append(topic_template)
    if default_providers is not None:
        updates.append("default_providers = ?")
        params.append(json.dumps(default_providers))
    if default_config is not None:
        updates.append("default_config = ?")
        params.append(json.dumps(default_config))
    if category is not None:
        updates.append("category = ?")
        params.append(category)

    params.append(template_id)

    with self._get_connection() as conn:
        # Don't allow updating builtin templates
        cursor = conn.execute(
            f"UPDATE discussion_templates SET {', '.join(updates)} WHERE id = ? AND is_builtin = 0",
            params
        )
        return cursor.rowcount > 0

def delete_discussion_template_impl(self, template_id: str) -> bool:
    """Delete a discussion template (only non-builtin)."""
    with self._get_connection() as conn:
        cursor = conn.execute(
            "DELETE FROM discussion_templates WHERE id = ? AND is_builtin = 0",
            (template_id,)
        )
        return cursor.rowcount > 0

def increment_template_usage_impl(self, template_id: str) -> None:
    """Increment the usage count for a template."""
    with self._get_connection() as conn:
        conn.execute(
            "UPDATE discussion_templates SET usage_count = usage_count + 1 WHERE id = ?",
            (template_id,)
        )

def _row_to_template_impl(self, row: sqlite3.Row) -> Dict[str, Any]:
    """Convert database row to template dictionary."""
    return {
        "id": row["id"],
        "name": row["name"],
        "description": row["description"],
        "topic_template": row["topic_template"],
        "default_providers": json.loads(row["default_providers"]) if row["default_providers"] else None,
        "default_config": json.loads(row["default_config"]) if row["default_config"] else None,
        "category": row["category"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "usage_count": row["usage_count"],
        "is_builtin": bool(row["is_builtin"]),
    }

