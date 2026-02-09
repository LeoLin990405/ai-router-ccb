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


def update_provider_status_impl(self, info: ProviderInfo) -> None:
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

def get_provider_status_impl(self, name: str) -> Optional[ProviderInfo]:
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

def list_provider_status_impl(self) -> List[ProviderInfo]:
    """List all provider statuses."""
    with self._get_connection() as conn:
        cursor = conn.execute(
            "SELECT * FROM provider_status ORDER BY priority DESC, name"
        )
        return [self._row_to_provider_info(row) for row in cursor.fetchall()]

def _row_to_provider_info_impl(self, row: sqlite3.Row) -> ProviderInfo:
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

def record_metric_impl(
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

def get_provider_metrics_impl(
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

def cleanup_old_metrics_impl(self, max_age_hours: int = 168) -> int:
    """Remove metrics older than specified age (default 7 days)."""
    cutoff = time.time() - (max_age_hours * 3600)
    with self._get_connection() as conn:
        cursor = conn.execute(
            "DELETE FROM metrics WHERE timestamp < ?",
            (cutoff,)
        )
        return cursor.rowcount

def get_stats_impl(self) -> Dict[str, Any]:
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

