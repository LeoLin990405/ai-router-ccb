"""Auto-split mixins for gateway CacheManager."""
from __future__ import annotations

import sqlite3
import time
from typing import Any, Dict, List, Optional

try:
    from .cache import CacheConfig, CacheEntry, CacheStats, generate_cache_key, generate_message_hash
    from .state_store import StateStore
except ImportError:  # pragma: no cover - script mode
    from cache import CacheConfig, CacheEntry, CacheStats, generate_cache_key, generate_message_hash
    from state_store import StateStore


class CacheManagerStatsMixin:
    """Mixin methods extracted from CacheManager."""

    def get_stats(self) -> CacheStats:
        """
        Get cache statistics.

        Returns:
            CacheStats object
        """
        now = time.time()
        with self.store._get_connection() as conn:
            cursor = conn.execute("""
                SELECT
                    COUNT(*) as total_count,
                    SUM(CASE WHEN expires_at > ? THEN 1 ELSE 0 END) as valid_count,
                    SUM(CASE WHEN expires_at <= ? THEN 1 ELSE 0 END) as expired_count,
                    COALESCE(SUM(LENGTH(response)), 0) as total_size,
                    COALESCE(SUM(CASE WHEN expires_at > ? THEN LENGTH(response) ELSE 0 END), 0) as valid_size,
                    MIN(created_at) as oldest,
                    MAX(created_at) as newest,
                    MIN(CASE WHEN expires_at > ? THEN expires_at END) as next_expiration,
                    AVG(CASE WHEN expires_at > ? THEN (expires_at - ?) END) as avg_ttl_remaining
                FROM response_cache
            """, (now, now, now, now, now, now))
            row = cursor.fetchone()

            self._stats.total_entries = row["total_count"] or 0
            self._stats.valid_entries = row["valid_count"] or 0
            self._stats.expired_entries = row["expired_count"] or 0
            self._stats.size_bytes = row["total_size"] or 0
            self._stats.valid_size_bytes = row["valid_size"] or 0
            self._stats.oldest_entry = row["oldest"]
            self._stats.newest_entry = row["newest"]
            self._stats.next_expiration = row["next_expiration"]
            self._stats.avg_ttl_remaining_s = row["avg_ttl_remaining"]

        return self._stats

    def list_entries(
        self,
        provider: Optional[str] = None,
        limit: int = 100,
        include_expired: bool = False,
    ) -> List[CacheEntry]:
        """
        List cache entries.

        Args:
            provider: Optional provider filter
            limit: Maximum entries to return
            include_expired: Whether to include expired entries

        Returns:
            List of CacheEntry objects
        """
        query = "SELECT * FROM response_cache WHERE 1=1"
        params: List[Any] = []

        if provider:
            query += " AND provider = ?"
            params.append(provider)

        if not include_expired:
            query += " AND expires_at > ?"
            params.append(time.time())

        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        with self.store._get_connection() as conn:
            cursor = conn.execute(query, params)
            return [self._row_to_entry(row) for row in cursor.fetchall()]

    def get_top_entries(self, limit: int = 10) -> List[CacheEntry]:
        """
        Get top cache entries by hit count.

        Args:
            limit: Maximum entries to return

        Returns:
            List of CacheEntry objects sorted by hit_count descending
        """
        now = time.time()
        with self.store._get_connection() as conn:
            cursor = conn.execute("""
                SELECT * FROM response_cache
                WHERE expires_at > ?
                ORDER BY hit_count DESC
                LIMIT ?
            """, (now, limit))
            return [self._row_to_entry(row) for row in cursor.fetchall()]

    def get_provider_stats(self) -> Dict[str, Dict[str, Any]]:
        """
        Get cache statistics per provider.

        Returns:
            Dict of provider -> stats
        """
        now = time.time()
        stats: Dict[str, Dict[str, Any]] = {}

        with self.store._get_connection() as conn:
            cursor = conn.execute("""
                SELECT provider,
                       COUNT(*) as entry_count,
                       SUM(hit_count) as total_hits,
                       AVG(hit_count) as avg_hits
                FROM response_cache
                WHERE expires_at > ?
                GROUP BY provider
            """, (now,))

            for row in cursor.fetchall():
                stats[row["provider"]] = {
                    "entry_count": row["entry_count"],
                    "total_hits": row["total_hits"] or 0,
                    "avg_hits": row["avg_hits"] or 0.0,
                }

        return stats

