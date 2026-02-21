"""
Smart Cache for CCB Gateway.

Provides intelligent caching of AI responses to reduce API calls.
"""
from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List

from .state_store import StateStore


@dataclass
class CacheConfig:
    """Configuration for response caching."""
    enabled: bool = True
    default_ttl_s: float = 3600.0  # 1 hour default
    max_entries: int = 10000
    # TTL by provider (some responses may be more stable)
    provider_ttl_s: Dict[str, float] = field(default_factory=lambda: {
        "claude": 3600.0,
        "gemini": 3600.0,
        "codex": 1800.0,
        "opencode": 1800.0,
    })
    # Don't cache responses shorter than this
    min_response_length: int = 10
    # Don't cache if message contains these patterns (case-insensitive)
    no_cache_patterns: List[str] = field(default_factory=lambda: [
        "current time",
        "current date",
        "today",
        "now",
        "latest",
        "recent",
        "weather",
        "stock price",
        "random",
    ])

    def get_ttl(self, provider: str) -> float:
        """Get TTL for a provider."""
        return self.provider_ttl_s.get(provider, self.default_ttl_s)

    def should_cache_message(self, message: str) -> bool:
        """Check if a message should be cached based on patterns."""
        message_lower = message.lower()
        return not any(p in message_lower for p in self.no_cache_patterns)


@dataclass
class CacheEntry:
    """A cached response entry."""
    cache_key: str
    provider: str
    message_hash: str
    response: str
    tokens_used: Optional[int]
    created_at: float
    expires_at: float
    hit_count: int = 0
    last_hit_at: Optional[float] = None
    metadata: Optional[Dict[str, Any]] = None

    def is_expired(self) -> bool:
        """Check if the entry has expired."""
        return time.time() > self.expires_at

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "cache_key": self.cache_key,
            "provider": self.provider,
            "message_hash": self.message_hash,
            "response": self.response,
            "tokens_used": self.tokens_used,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "hit_count": self.hit_count,
            "last_hit_at": self.last_hit_at,
            "metadata": self.metadata,
        }


@dataclass
class CacheStats:
    """Cache statistics."""
    hits: int = 0
    misses: int = 0
    total_entries: int = 0
    expired_entries: int = 0
    total_tokens_saved: int = 0
    size_bytes: int = 0
    valid_entries: int = 0
    valid_size_bytes: int = 0
    oldest_entry: Optional[float] = None
    newest_entry: Optional[float] = None
    next_expiration: Optional[float] = None
    avg_ttl_remaining_s: Optional[float] = None

    @property
    def hit_rate(self) -> float:
        """Calculate cache hit rate."""
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": self.hit_rate,
            "total_entries": self.total_entries,
            "expired_entries": self.expired_entries,
            "total_tokens_saved": self.total_tokens_saved,
            "size_bytes": self.size_bytes,
            "valid_entries": self.valid_entries,
            "valid_size_bytes": self.valid_size_bytes,
            "oldest_entry": self.oldest_entry,
            "newest_entry": self.newest_entry,
            "next_expiration": self.next_expiration,
            "avg_ttl_remaining_s": self.avg_ttl_remaining_s,
        }


def generate_cache_key(provider: str, message: str, model: Optional[str] = None) -> str:
    """
    Generate a cache key for a request.

    Args:
        provider: Provider name
        message: The message/prompt
        model: Optional model name

    Returns:
        Cache key string
    """
    # Normalize message (strip whitespace, lowercase for comparison)
    normalized = message.strip().lower()

    # Create hash of normalized message
    message_hash = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]

    # Include provider and optional model in key
    if model:
        return f"{provider}:{model}:{message_hash}"
    return f"{provider}:{message_hash}"


def generate_message_hash(message: str) -> str:
    """Generate a hash of the message for storage."""
    return hashlib.sha256(message.strip().encode("utf-8")).hexdigest()



try:
    from .cache_manager_core import CacheManagerCoreMixin
    from .cache_manager_stats import CacheManagerStatsMixin
except ImportError:  # pragma: no cover - script mode
    from cache_manager_core import CacheManagerCoreMixin
    from cache_manager_stats import CacheManagerStatsMixin


class CacheManager(CacheManagerCoreMixin, CacheManagerStatsMixin):
    """Manages cache lifecycle, retrieval, and analytics."""

