"""
State Store for CCB Gateway.

SQLite-backed persistent storage for requests, responses, and provider status.
"""
from __future__ import annotations

import json
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Optional, List, Dict, Any, Iterator

from .models import (
    RequestStatus,
    GatewayRequest,
    GatewayResponse,
    ProviderInfo,
    ProviderStatus,
    BackendType,
)


class StateStore:
    """
    SQLite-backed state store for the gateway.

    Stores:
    - Requests and their status
    - Responses from providers
    - Provider health/status information
    - Request metrics for analytics
    """

    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize the state store.

        Args:
            db_path: Path to SQLite database. Defaults to ~/.ccb_config/gateway.db
        """
        if db_path:
            self.db_path = Path(db_path)
        else:
            self.db_path = Path.home() / ".ccb_config" / "gateway.db"

        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    @contextmanager
    def _get_connection(self) -> Iterator[sqlite3.Connection]:
        """Get a database connection with row factory."""
        conn = sqlite3.connect(str(self.db_path), timeout=30.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_db(self) -> None:
        """Initialize the database schema."""
        with self._get_connection() as conn:
            # Requests table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS requests (
                    id TEXT PRIMARY KEY,
                    provider TEXT NOT NULL,
                    message TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'queued',
                    priority INTEGER NOT NULL DEFAULT 50,
                    timeout_s REAL NOT NULL DEFAULT 300.0,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL,
                    backend_type TEXT,
                    routed_at REAL,
                    started_at REAL,
                    completed_at REAL,
                    metadata TEXT
                )
            """)

            # Responses table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS responses (
                    request_id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    response TEXT,
                    error TEXT,
                    provider TEXT,
                    latency_ms REAL,
                    tokens_used INTEGER,
                    created_at REAL NOT NULL,
                    metadata TEXT,
                    thinking TEXT,
                    raw_output TEXT,
                    FOREIGN KEY (request_id) REFERENCES requests(id)
                )
            """)

            # Add thinking and raw_output columns if they don't exist (migration)
            try:
                conn.execute("ALTER TABLE responses ADD COLUMN thinking TEXT")
            except sqlite3.OperationalError:
                pass  # Column already exists
            try:
                conn.execute("ALTER TABLE responses ADD COLUMN raw_output TEXT")
            except sqlite3.OperationalError:
                pass  # Column already exists

            # Provider status table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS provider_status (
                    name TEXT PRIMARY KEY,
                    backend_type TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'unknown',
                    queue_depth INTEGER DEFAULT 0,
                    avg_latency_ms REAL DEFAULT 0.0,
                    success_rate REAL DEFAULT 1.0,
                    last_check REAL,
                    error TEXT,
                    enabled INTEGER DEFAULT 1,
                    priority INTEGER DEFAULT 50,
                    rate_limit_rpm INTEGER,
                    timeout_s REAL DEFAULT 300.0,
                    updated_at REAL NOT NULL
                )
            """)

            # Metrics table for analytics
            conn.execute("""
                CREATE TABLE IF NOT EXISTS metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    provider TEXT NOT NULL,
                    request_id TEXT,
                    event_type TEXT NOT NULL,
                    latency_ms REAL,
                    success INTEGER,
                    error TEXT,
                    timestamp REAL NOT NULL
                )
            """)

            # Create indexes
            conn.execute("CREATE INDEX IF NOT EXISTS idx_requests_status ON requests(status)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_requests_provider ON requests(provider)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_requests_created ON requests(created_at)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_requests_priority ON requests(priority DESC, created_at ASC)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_responses_request ON responses(request_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_metrics_provider ON metrics(provider)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_metrics_timestamp ON metrics(timestamp)")

    # ==================== Request Operations ====================

    def create_request(self, request: GatewayRequest) -> GatewayRequest:
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

    def get_request(self, request_id: str) -> Optional[GatewayRequest]:
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

    def update_request_status(
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

    def list_requests(
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

    def get_pending_requests(self, limit: int = 10) -> List[GatewayRequest]:
        """Get pending requests ordered by priority."""
        return self.list_requests(status=RequestStatus.QUEUED, limit=limit)

    def cancel_request(self, request_id: str) -> bool:
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

    def cleanup_old_requests(self, max_age_hours: int = 24) -> int:
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

    def _row_to_request(self, row: sqlite3.Row) -> GatewayRequest:
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

    # ==================== Response Operations ====================

    def save_response(self, response: GatewayResponse) -> None:
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

    def get_response(self, request_id: str) -> Optional[GatewayResponse]:
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

    # ==================== Provider Status Operations ====================

    def update_provider_status(self, info: ProviderInfo) -> None:
        """Update provider status."""
        with self._get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO provider_status (
                    name, backend_type, status, queue_depth, avg_latency_ms,
                    success_rate, last_check, error, enabled, priority,
                    rate_limit_rpm, timeout_s, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                info.name,
                info.backend_type.value,
                info.status.value,
                info.queue_depth,
                info.avg_latency_ms,
                info.success_rate,
                info.last_check,
                info.error,
                1 if info.enabled else 0,
                info.priority,
                info.rate_limit_rpm,
                info.timeout_s,
                time.time(),
            ))

    def get_provider_status(self, name: str) -> Optional[ProviderInfo]:
        """Get provider status."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM provider_status WHERE name = ?",
                (name,)
            )
            row = cursor.fetchone()
            if row:
                return self._row_to_provider_info(row)
        return None

    def list_provider_status(self) -> List[ProviderInfo]:
        """List all provider statuses."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM provider_status ORDER BY priority DESC, name"
            )
            return [self._row_to_provider_info(row) for row in cursor.fetchall()]

    def _row_to_provider_info(self, row: sqlite3.Row) -> ProviderInfo:
        """Convert database row to ProviderInfo."""
        return ProviderInfo(
            name=row["name"],
            backend_type=BackendType(row["backend_type"]),
            status=ProviderStatus(row["status"]),
            queue_depth=row["queue_depth"],
            avg_latency_ms=row["avg_latency_ms"],
            success_rate=row["success_rate"],
            last_check=row["last_check"],
            error=row["error"],
            enabled=bool(row["enabled"]),
            priority=row["priority"],
            rate_limit_rpm=row["rate_limit_rpm"],
            timeout_s=row["timeout_s"],
        )

    # ==================== Metrics Operations ====================

    def record_metric(
        self,
        provider: str,
        event_type: str,
        request_id: Optional[str] = None,
        latency_ms: Optional[float] = None,
        success: bool = True,
        error: Optional[str] = None,
    ) -> None:
        """Record a metric event."""
        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO metrics (
                    provider, request_id, event_type, latency_ms,
                    success, error, timestamp
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                provider,
                request_id,
                event_type,
                latency_ms,
                1 if success else 0,
                error,
                time.time(),
            ))

    def get_provider_metrics(
        self,
        provider: str,
        hours: int = 24,
    ) -> Dict[str, Any]:
        """Get aggregated metrics for a provider."""
        cutoff = time.time() - (hours * 3600)
        with self._get_connection() as conn:
            cursor = conn.execute("""
                SELECT
                    COUNT(*) as total,
                    SUM(success) as successes,
                    AVG(latency_ms) as avg_latency,
                    MAX(latency_ms) as max_latency,
                    MIN(latency_ms) as min_latency
                FROM metrics
                WHERE provider = ? AND timestamp > ?
            """, (provider, cutoff))
            row = cursor.fetchone()
            if row:
                total = row["total"] or 0
                successes = row["successes"] or 0
                return {
                    "provider": provider,
                    "total_requests": total,
                    "successful_requests": successes,
                    "success_rate": successes / total if total > 0 else 1.0,
                    "avg_latency_ms": row["avg_latency"] or 0.0,
                    "max_latency_ms": row["max_latency"] or 0.0,
                    "min_latency_ms": row["min_latency"] or 0.0,
                }
        return {
            "provider": provider,
            "total_requests": 0,
            "successful_requests": 0,
            "success_rate": 1.0,
            "avg_latency_ms": 0.0,
            "max_latency_ms": 0.0,
            "min_latency_ms": 0.0,
        }

    def cleanup_old_metrics(self, max_age_hours: int = 168) -> int:
        """Remove metrics older than specified age (default 7 days)."""
        cutoff = time.time() - (max_age_hours * 3600)
        with self._get_connection() as conn:
            cursor = conn.execute(
                "DELETE FROM metrics WHERE timestamp < ?",
                (cutoff,)
            )
            return cursor.rowcount

    # ==================== Statistics ====================

    def get_stats(self) -> Dict[str, Any]:
        """Get overall gateway statistics."""
        with self._get_connection() as conn:
            # Request counts by status
            cursor = conn.execute("""
                SELECT status, COUNT(*) as count
                FROM requests
                GROUP BY status
            """)
            status_counts = {row["status"]: row["count"] for row in cursor.fetchall()}

            # Active requests
            cursor = conn.execute("""
                SELECT COUNT(*) as count
                FROM requests
                WHERE status IN ('queued', 'processing')
            """)
            active = cursor.fetchone()["count"]

            # Provider queue depths
            cursor = conn.execute("""
                SELECT provider, COUNT(*) as count
                FROM requests
                WHERE status = 'queued'
                GROUP BY provider
            """)
            queue_depths = {row["provider"]: row["count"] for row in cursor.fetchall()}

            return {
                "total_requests": sum(status_counts.values()),
                "active_requests": active,
                "status_counts": status_counts,
                "queue_depths": queue_depths,
            }
