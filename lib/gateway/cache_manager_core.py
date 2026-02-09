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


class CacheManagerCoreMixin:
    """Mixin methods extracted from CacheManager."""

    def __init__(self, store: StateStore, config: Optional[CacheConfig] = None):
        """
        Initialize the cache manager.

        Args:
            store: StateStore instance for persistence
            config: Cache configuration
        """
        self.store = store
        self.config = config or CacheConfig()
        self._stats = CacheStats()
        self._init_cache_table()

    def _init_cache_table(self) -> None:
        """Initialize the cache table in the database."""
        with self.store._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS response_cache (
                    cache_key TEXT PRIMARY KEY,
                    provider TEXT NOT NULL,
                    message_hash TEXT NOT NULL,
                    response TEXT NOT NULL,
                    tokens_used INTEGER,
                    created_at REAL NOT NULL,
                    expires_at REAL NOT NULL,
                    hit_count INTEGER DEFAULT 0,
                    last_hit_at REAL,
                    metadata TEXT
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_cache_provider ON response_cache(provider)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_cache_expires ON response_cache(expires_at)")

    def get(
        self,
        provider: str,
        message: str,
        model: Optional[str] = None,
    ) -> Optional[CacheEntry]:
        """
        Get a cached response.

        Args:
            provider: Provider name
            message: The message/prompt
            model: Optional model name

        Returns:
            CacheEntry if found and not expired, None otherwise
        """
        if not self.config.enabled:
            return None

        cache_key = generate_cache_key(provider, message, model)

        with self.store._get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM response_cache WHERE cache_key = ?",
                (cache_key,)
            )
            row = cursor.fetchone()

            if not row:
                self._stats.misses += 1
                return None

            entry = self._row_to_entry(row)

            if entry.is_expired():
                # Delete expired entry
                conn.execute("DELETE FROM response_cache WHERE cache_key = ?", (cache_key,))
                self._stats.misses += 1
                return None

            # Update hit count
            now = time.time()
            conn.execute(
                "UPDATE response_cache SET hit_count = hit_count + 1, last_hit_at = ? WHERE cache_key = ?",
                (now, cache_key)
            )

            self._stats.hits += 1
            if entry.tokens_used:
                self._stats.total_tokens_saved += entry.tokens_used

            entry.hit_count += 1
            entry.last_hit_at = now
            return entry

    def put(
        self,
        provider: str,
        message: str,
        response: str,
        tokens_used: Optional[int] = None,
        model: Optional[str] = None,
        ttl_s: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[CacheEntry]:
        """
        Store a response in the cache.

        Args:
            provider: Provider name
            message: The message/prompt
            response: The response to cache
            tokens_used: Optional token count
            model: Optional model name
            ttl_s: Optional TTL override
            metadata: Optional metadata

        Returns:
            CacheEntry if stored, None if caching was skipped
        """
        if not self.config.enabled:
            return None

        # Check if message should be cached
        if not self.config.should_cache_message(message):
            return None

        # Check minimum response length
        if len(response) < self.config.min_response_length:
            return None

        cache_key = generate_cache_key(provider, message, model)
        message_hash = generate_message_hash(message)
        now = time.time()
        ttl = ttl_s or self.config.get_ttl(provider)
        expires_at = now + ttl

        entry = CacheEntry(
            cache_key=cache_key,
            provider=provider,
            message_hash=message_hash,
            response=response,
            tokens_used=tokens_used,
            created_at=now,
            expires_at=expires_at,
            metadata=metadata,
        )

        with self.store._get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO response_cache (
                    cache_key, provider, message_hash, response, tokens_used,
                    created_at, expires_at, hit_count, last_hit_at, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                entry.cache_key,
                entry.provider,
                entry.message_hash,
                entry.response,
                entry.tokens_used,
                entry.created_at,
                entry.expires_at,
                entry.hit_count,
                entry.last_hit_at,
                json.dumps(entry.metadata) if entry.metadata else None,
            ))

        return entry

    def invalidate(self, cache_key: str) -> bool:
        """
        Invalidate a specific cache entry.

        Args:
            cache_key: The cache key to invalidate

        Returns:
            True if entry was deleted
        """
        with self.store._get_connection() as conn:
            cursor = conn.execute(
                "DELETE FROM response_cache WHERE cache_key = ?",
                (cache_key,)
            )
            return cursor.rowcount > 0

    def clear(self, provider: Optional[str] = None) -> int:
        """
        Clear cache entries.

        Args:
            provider: Optional provider to clear (clears all if None)

        Returns:
            Number of entries cleared
        """
        with self.store._get_connection() as conn:
            if provider:
                cursor = conn.execute(
                    "DELETE FROM response_cache WHERE provider = ?",
                    (provider,)
                )
            else:
                cursor = conn.execute("DELETE FROM response_cache")
            return cursor.rowcount

    def cleanup_expired(self) -> int:
        """
        Remove expired cache entries.

        Returns:
            Number of entries removed
        """
        now = time.time()
        with self.store._get_connection() as conn:
            cursor = conn.execute(
                "DELETE FROM response_cache WHERE expires_at < ?",
                (now,)
            )
            return cursor.rowcount

    def _row_to_entry(self, row) -> CacheEntry:
        """Convert database row to CacheEntry."""
        return CacheEntry(
            cache_key=row["cache_key"],
            provider=row["provider"],
            message_hash=row["message_hash"],
            response=row["response"],
            tokens_used=row["tokens_used"],
            created_at=row["created_at"],
            expires_at=row["expires_at"],
            hit_count=row["hit_count"],
            last_hit_at=row["last_hit_at"],
            metadata=json.loads(row["metadata"]) if row["metadata"] else None,
        )

    def enforce_max_entries(self) -> int:
        """
        Remove oldest entries if cache exceeds max_entries limit.

        Returns:
            Number of entries removed
        """
        with self.store._get_connection() as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM response_cache")
            count = cursor.fetchone()[0]

            if count <= self.config.max_entries:
                return 0

            # Remove oldest entries (by created_at) to get under limit
            excess = count - self.config.max_entries
            cursor = conn.execute("""
                DELETE FROM response_cache
                WHERE cache_key IN (
                    SELECT cache_key FROM response_cache
                    ORDER BY created_at ASC
                    LIMIT ?
                )
            """, (excess,))
            return cursor.rowcount

