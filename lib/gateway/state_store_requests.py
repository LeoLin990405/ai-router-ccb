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


def create_request_impl(self, request: GatewayRequest) -> GatewayRequest:
    """Create a new request in the store."""
    with self._get_connection() as conn:
        conn.execute("""
            INSERT INTO requests (
                id, provider, message, status, priority, timeout_s,
                created_at, updated_at, backend_type, routed_at,
                started_at, completed_at, metadata
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            request.id,
            request.provider,
            request.message,
            request.status.value,
            request.priority,
            request.timeout_s,
            request.created_at,
            request.updated_at,
            request.backend_type.value if request.backend_type else None,
            request.routed_at,
            request.started_at,
            request.completed_at,
            json.dumps(request.metadata) if request.metadata else None,
        ))
    return request

def get_request_impl(self, request_id: str) -> Optional[GatewayRequest]:
    """Get a request by ID."""
    with self._get_connection() as conn:
        cursor = conn.execute(
            "SELECT * FROM requests WHERE id = ?",
            (request_id,)
        )
        row = cursor.fetchone()
        if row:
            return self._row_to_request(row)
    return None

def update_request_status_impl(
    self,
    request_id: str,
    status: RequestStatus,
    backend_type: Optional[BackendType] = None,
) -> bool:
    """Update request status."""
    now = time.time()
    with self._get_connection() as conn:
        updates = ["status = ?", "updated_at = ?"]
        params: List[Any] = [status.value, now]

        if backend_type:
            updates.append("backend_type = ?")
            params.append(backend_type.value)

        if status == RequestStatus.PROCESSING:
            updates.append("started_at = ?")
            params.append(now)
            updates.append("routed_at = ?")
            params.append(now)
        elif status in (RequestStatus.COMPLETED, RequestStatus.FAILED, RequestStatus.TIMEOUT):
            updates.append("completed_at = ?")
            params.append(now)

        params.append(request_id)
        cursor = conn.execute(
            f"UPDATE requests SET {', '.join(updates)} WHERE id = ?",
            params
        )
        return cursor.rowcount > 0

def list_requests_impl(
    self,
    status: Optional[RequestStatus] = None,
    provider: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    order_by: str = "created_at",
    order_desc: bool = True,
) -> List[GatewayRequest]:
    """List requests with optional filtering.

    Args:
        status: Filter by request status
        provider: Filter by provider name
        limit: Maximum number of results
        offset: Number of results to skip
        order_by: Field to order by (created_at, updated_at, priority)
        order_desc: If True, order descending; if False, ascending
    """
    query = "SELECT * FROM requests WHERE 1=1"
    params: List[Any] = []

    if status:
        query += " AND status = ?"
        params.append(status.value)

    if provider:
        query += " AND provider = ?"
        params.append(provider)

    # Validate order_by to prevent SQL injection
    valid_order_fields = {"created_at", "updated_at", "priority"}
    if order_by not in valid_order_fields:
        order_by = "created_at"

    order_dir = "DESC" if order_desc else "ASC"
    query += f" ORDER BY {order_by} {order_dir} LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    with self._get_connection() as conn:
        cursor = conn.execute(query, params)
        return [self._row_to_request(row) for row in cursor.fetchall()]

def get_pending_requests_impl(self, limit: int = 10) -> List[GatewayRequest]:
    """Get pending requests ordered by priority."""
    return self.list_requests(status=RequestStatus.QUEUED, limit=limit)

def cancel_request_impl(self, request_id: str) -> bool:
    """Cancel a pending or processing request."""
    with self._get_connection() as conn:
        cursor = conn.execute("""
            UPDATE requests
            SET status = ?, updated_at = ?
            WHERE id = ? AND status IN (?, ?)
        """, (
            RequestStatus.CANCELLED.value,
            time.time(),
            request_id,
            RequestStatus.QUEUED.value,
            RequestStatus.PROCESSING.value,
        ))
        return cursor.rowcount > 0

def cleanup_old_requests_impl(self, max_age_hours: int = 24) -> int:
    """Remove requests older than specified age."""
    cutoff = time.time() - (max_age_hours * 3600)
    with self._get_connection() as conn:
        # Delete responses first (foreign key)
        conn.execute("""
            DELETE FROM responses
            WHERE request_id IN (
                SELECT id FROM requests WHERE created_at < ?
            )
        """, (cutoff,))
        cursor = conn.execute(
            "DELETE FROM requests WHERE created_at < ?",
            (cutoff,)
        )
        return cursor.rowcount

def _row_to_request_impl(self, row: sqlite3.Row) -> GatewayRequest:
    """Convert database row to GatewayRequest."""
    return GatewayRequest(
        id=row["id"],
        provider=row["provider"],
        message=row["message"],
        status=RequestStatus(row["status"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        priority=row["priority"],
        timeout_s=row["timeout_s"],
        backend_type=BackendType(row["backend_type"]) if row["backend_type"] else None,
        routed_at=row["routed_at"],
        started_at=row["started_at"],
        completed_at=row["completed_at"],
        metadata=json.loads(row["metadata"]) if row["metadata"] else None,
    )

def save_response_impl(self, response: GatewayResponse) -> None:
    """Save a response."""
    with self._get_connection() as conn:
        conn.execute("""
            INSERT OR REPLACE INTO responses (
                request_id, status, response, error, provider,
                latency_ms, tokens_used, created_at, metadata,
                thinking, raw_output
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            response.request_id,
            response.status.value,
            response.response,
            response.error,
            response.provider,
            response.latency_ms,
            response.tokens_used,
            time.time(),
            json.dumps(response.metadata) if response.metadata else None,
            response.thinking,
            response.raw_output,
        ))

def get_response_impl(self, request_id: str) -> Optional[GatewayResponse]:
    """Get response for a request."""
    with self._get_connection() as conn:
        cursor = conn.execute(
            "SELECT * FROM responses WHERE request_id = ?",
            (request_id,)
        )
        row = cursor.fetchone()
        if row:
            return GatewayResponse(
                request_id=row["request_id"],
                status=RequestStatus(row["status"]),
                response=row["response"],
                error=row["error"],
                provider=row["provider"],
                latency_ms=row["latency_ms"],
                tokens_used=row["tokens_used"],
                metadata=json.loads(row["metadata"]) if row["metadata"] else None,
                thinking=row["thinking"] if "thinking" in row.keys() else None,
                raw_output=row["raw_output"] if "raw_output" in row.keys() else None,
            )
    return None

