"""
Provider Performance Tracking System for CCB

Tracks response times, success rates, and token usage for each AI provider.
Persists data to SQLite for analysis and routing optimization.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Optional, List, Dict, Any
import sqlite3
import time
from pathlib import Path
from contextlib import contextmanager

from lib.common.paths import default_gateway_db_path, default_performance_db_path


@dataclass
class PerformanceMetric:
    """Single performance measurement."""
    provider: str
    latency_ms: float
    success: bool
    token_count: Optional[int] = None
    timestamp: float = 0.0
    task_id: Optional[str] = None
    error: Optional[str] = None

    def __post_init__(self):
        if self.timestamp == 0.0:
            self.timestamp = time.time()


@dataclass
class ProviderStats:
    """Aggregated statistics for a provider."""
    provider: str
    total_requests: int
    successful_requests: int
    failed_requests: int
    success_rate: float
    avg_latency_ms: float
    min_latency_ms: float
    max_latency_ms: float
    p50_latency_ms: float
    p95_latency_ms: float
    total_tokens: int
    period_hours: int


HANDLED_EXCEPTIONS = (Exception,)


class PerformanceTracker:
    """
    SQLite-backed performance tracker for CCB providers.

    Tracks latency, success rate, and token usage for routing optimization.
    """

    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize the performance tracker.

        Args:
            db_path: Path to SQLite database. Defaults to data/performance.db
        """
        if db_path:
            self.db_path = Path(db_path)
        else:
            self.db_path = default_performance_db_path()

        # Gateway database as fallback data source
        self.gateway_db_path = default_gateway_db_path()

        # Ensure directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    @contextmanager
    def _get_connection(self):
        """Get a database connection with row factory."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_db(self) -> None:
        """Initialize the SQLite database schema."""
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS performance_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    provider TEXT NOT NULL,
                    latency_ms REAL NOT NULL,
                    success INTEGER NOT NULL,
                    token_count INTEGER,
                    timestamp REAL NOT NULL,
                    task_id TEXT,
                    error TEXT
                )
            """)
            # Create indexes for common queries
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_perf_provider
                ON performance_metrics(provider)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_perf_timestamp
                ON performance_metrics(timestamp)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_perf_provider_timestamp
                ON performance_metrics(provider, timestamp)
            """)

    def record_metric(self, metric: PerformanceMetric) -> None:
        """
        Record a single performance metric.

        Args:
            metric: The performance metric to record
        """
        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO performance_metrics
                (provider, latency_ms, success, token_count, timestamp, task_id, error)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                metric.provider,
                metric.latency_ms,
                1 if metric.success else 0,
                metric.token_count,
                metric.timestamp,
                metric.task_id,
                metric.error,
            ))

    def record(
        self,
        provider: str,
        latency_ms: float,
        success: bool,
        token_count: Optional[int] = None,
        task_id: Optional[str] = None,
        error: Optional[str] = None,
    ) -> None:
        """
        Convenience method to record a metric.

        Args:
            provider: Provider name
            latency_ms: Response latency in milliseconds
            success: Whether the request succeeded
            token_count: Optional token count
            task_id: Optional associated task ID
            error: Optional error message
        """
        metric = PerformanceMetric(
            provider=provider,
            latency_ms=latency_ms,
            success=success,
            token_count=token_count,
            task_id=task_id,
            error=error,
        )
        self.record_metric(metric)

    def get_provider_stats(self, provider: str, hours: int = 24) -> Optional[ProviderStats]:
        """
        Get aggregated statistics for a provider.

        Args:
            provider: Provider name
            hours: Time window in hours (default: 24)

        Returns:
            ProviderStats or None if no data
        """
        cutoff = time.time() - (hours * 3600)

        with self._get_connection() as conn:
            # Get basic stats
            cursor = conn.execute("""
                SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as successful,
                    SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END) as failed,
                    AVG(latency_ms) as avg_latency,
                    MIN(latency_ms) as min_latency,
                    MAX(latency_ms) as max_latency,
                    SUM(COALESCE(token_count, 0)) as total_tokens
                FROM performance_metrics
                WHERE provider = ? AND timestamp >= ?
            """, (provider, cutoff))

            row = cursor.fetchone()
            if not row or row["total"] == 0:
                return None

            total = row["total"]
            successful = row["successful"]
            failed = row["failed"]

            # Get percentiles (p50, p95)
            cursor = conn.execute("""
                SELECT latency_ms
                FROM performance_metrics
                WHERE provider = ? AND timestamp >= ?
                ORDER BY latency_ms
            """, (provider, cutoff))

            latencies = [r["latency_ms"] for r in cursor.fetchall()]
            p50_idx = int(len(latencies) * 0.5)
            p95_idx = int(len(latencies) * 0.95)

            return ProviderStats(
                provider=provider,
                total_requests=total,
                successful_requests=successful,
                failed_requests=failed,
                success_rate=successful / total if total > 0 else 0.0,
                avg_latency_ms=row["avg_latency"] or 0.0,
                min_latency_ms=row["min_latency"] or 0.0,
                max_latency_ms=row["max_latency"] or 0.0,
                p50_latency_ms=latencies[p50_idx] if latencies else 0.0,
                p95_latency_ms=latencies[p95_idx] if p95_idx < len(latencies) else (latencies[-1] if latencies else 0.0),
                total_tokens=row["total_tokens"] or 0,
                period_hours=hours,
            )

    def get_all_stats(self, hours: int = 24) -> List[ProviderStats]:
        """
        Get statistics for all providers.

        Args:
            hours: Time window in hours (default: 24)

        Returns:
            List of ProviderStats for all providers with data
        """
        cutoff = time.time() - (hours * 3600)

        with self._get_connection() as conn:
            cursor = conn.execute("""
                SELECT DISTINCT provider
                FROM performance_metrics
                WHERE timestamp >= ?
            """, (cutoff,))

            providers = [row["provider"] for row in cursor.fetchall()]

        stats = []
        stats_providers = set()
        for provider in providers:
            provider_stats = self.get_provider_stats(provider, hours)
            if provider_stats:
                stats.append(provider_stats)
                stats_providers.add(provider)

        # Also get stats from gateway.db and merge (for providers not in performance.db)
        if self.gateway_db_path.exists():
            gateway_stats = self._get_stats_from_gateway(hours)
            for gs in gateway_stats:
                if gs.provider not in stats_providers:
                    stats.append(gs)
                    stats_providers.add(gs.provider)

        # Sort by total requests descending
        stats.sort(key=lambda s: s.total_requests, reverse=True)
        return stats

    def _get_stats_from_gateway(self, hours: int = 24) -> List[ProviderStats]:
        """
        Get statistics from gateway.db as fallback.

        Args:
            hours: Time window in hours

        Returns:
            List of ProviderStats from gateway database
        """
        cutoff = time.time() - (hours * 3600)
        stats = []

        try:
            conn = sqlite3.connect(str(self.gateway_db_path))
            conn.row_factory = sqlite3.Row

            # Get stats from requests table
            # Calculate latency from completed_at - created_at
            cursor = conn.execute("""
                SELECT
                    provider,
                    COUNT(*) as total,
                    SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as successful,
                    SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed,
                    AVG(CASE WHEN completed_at IS NOT NULL THEN (completed_at - created_at) * 1000 END) as avg_latency,
                    MIN(CASE WHEN completed_at IS NOT NULL THEN (completed_at - created_at) * 1000 END) as min_latency,
                    MAX(CASE WHEN completed_at IS NOT NULL THEN (completed_at - created_at) * 1000 END) as max_latency
                FROM requests
                WHERE created_at >= ?
                GROUP BY provider
            """, (cutoff,))

            for row in cursor.fetchall():
                total = row["total"]
                successful = row["successful"] or 0
                failed = row["failed"] or 0

                stats.append(ProviderStats(
                    provider=row["provider"],
                    total_requests=total,
                    successful_requests=successful,
                    failed_requests=failed,
                    success_rate=successful / total if total > 0 else 0.0,
                    avg_latency_ms=row["avg_latency"] or 0.0,
                    min_latency_ms=row["min_latency"] or 0.0,
                    max_latency_ms=row["max_latency"] or 0.0,
                    p50_latency_ms=row["avg_latency"] or 0.0,  # Approximate
                    p95_latency_ms=row["max_latency"] or 0.0,  # Approximate
                    total_tokens=0,  # Not tracked in gateway.db
                    period_hours=hours,
                ))

            conn.close()
        except HANDLED_EXCEPTIONS:
            pass  # Silently fail if gateway.db is not accessible

        return stats

    def get_best_provider(
        self,
        candidates: Optional[List[str]] = None,
        hours: int = 24,
        min_requests: int = 5,
    ) -> Optional[str]:
        """
        Get the best performing provider based on success rate and latency.

        Args:
            candidates: Optional list of candidate providers to consider
            hours: Time window in hours
            min_requests: Minimum requests required for consideration

        Returns:
            Best provider name or None if insufficient data
        """
        all_stats = self.get_all_stats(hours)

        if candidates:
            all_stats = [s for s in all_stats if s.provider in candidates]

        # Filter by minimum requests
        all_stats = [s for s in all_stats if s.total_requests >= min_requests]

        if not all_stats:
            return None

        # Score: success_rate * 0.7 + (1 - normalized_latency) * 0.3
        max_latency = max(s.avg_latency_ms for s in all_stats) or 1.0

        def score(stats: ProviderStats) -> float:
            latency_score = 1.0 - (stats.avg_latency_ms / max_latency)
            return stats.success_rate * 0.7 + latency_score * 0.3

        best = max(all_stats, key=score)
        return best.provider

    def get_recent_metrics(
        self,
        provider: Optional[str] = None,
        limit: int = 100,
        hours: Optional[int] = None,
    ) -> List[PerformanceMetric]:
        """
        Get recent performance metrics.

        Args:
            provider: Optional provider filter
            limit: Maximum number of metrics to return
            hours: Optional time window in hours

        Returns:
            List of PerformanceMetric objects
        """
        query = "SELECT * FROM performance_metrics WHERE 1=1"
        params: List[Any] = []

        if provider:
            query += " AND provider = ?"
            params.append(provider)

        if hours:
            cutoff = time.time() - (hours * 3600)
            query += " AND timestamp >= ?"
            params.append(cutoff)

        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)

        with self._get_connection() as conn:
            cursor = conn.execute(query, params)
            return [
                PerformanceMetric(
                    provider=row["provider"],
                    latency_ms=row["latency_ms"],
                    success=bool(row["success"]),
                    token_count=row["token_count"],
                    timestamp=row["timestamp"],
                    task_id=row["task_id"],
                    error=row["error"],
                )
                for row in cursor.fetchall()
            ]

    def cleanup_old_metrics(self, retention_days: int = 30, hours: int = None) -> int:
        """
        Remove metrics older than retention period.

        Args:
            retention_days: Number of days to retain (default: 30)
            hours: Alternative: number of hours to retain (overrides retention_days)

        Returns:
            Number of metrics deleted
        """
        if hours is not None:
            cutoff = time.time() - (hours * 3600)
        else:
            cutoff = time.time() - (retention_days * 24 * 3600)

        with self._get_connection() as conn:
            cursor = conn.execute(
                "DELETE FROM performance_metrics WHERE timestamp < ?",
                (cutoff,)
            )
            return cursor.rowcount

    def get_summary(self, hours: int = 24) -> Dict[str, Any]:
        """
        Get a summary of all performance data.

        Args:
            hours: Time window in hours

        Returns:
            Summary dictionary
        """
        all_stats = self.get_all_stats(hours)

        if not all_stats:
            return {
                "period_hours": hours,
                "total_requests": 0,
                "providers": [],
            }

        total_requests = sum(s.total_requests for s in all_stats)
        total_successful = sum(s.successful_requests for s in all_stats)
        total_tokens = sum(s.total_tokens for s in all_stats)

        return {
            "period_hours": hours,
            "total_requests": total_requests,
            "total_successful": total_successful,
            "total_failed": total_requests - total_successful,
            "overall_success_rate": total_successful / total_requests if total_requests > 0 else 0.0,
            "total_tokens": total_tokens,
            "provider_count": len(all_stats),
            "best_provider": self.get_best_provider(hours=hours),
            "providers": [
                {
                    "provider": s.provider,
                    "requests": s.total_requests,
                    "success_rate": s.success_rate,
                    "avg_latency_ms": s.avg_latency_ms,
                    "p95_latency_ms": s.p95_latency_ms,
                    "tokens": s.total_tokens,
                }
                for s in all_stats
            ],
        }
