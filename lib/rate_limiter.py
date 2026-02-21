"""
Rate Limiting System for CCB

Provides per-provider rate limiting with Token Bucket and Sliding Window algorithms.
Uses SQLite for persistent state storage.
"""
from __future__ import annotations

import sqlite3
import time
import threading
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional, Dict, List, Any


class RateLimitAlgorithm(Enum):
    """Rate limiting algorithm types."""
    TOKEN_BUCKET = "token_bucket"
    SLIDING_WINDOW = "sliding_window"


@dataclass
class RateLimitConfig:
    """Configuration for rate limiting a provider."""
    rpm: int = 60              # requests per minute
    tpm: int = 100000          # tokens per minute
    burst_size: int = 10       # burst allowance (for token bucket)
    algorithm: RateLimitAlgorithm = RateLimitAlgorithm.TOKEN_BUCKET
    enabled: bool = True


@dataclass
class RateLimitStats:
    """Statistics for a provider's rate limit."""
    provider: str
    current_rpm: int = 0
    current_tpm: int = 0
    limit_rpm: int = 60
    limit_tpm: int = 100000
    available_tokens: float = 0.0
    is_limited: bool = False
    wait_time_s: float = 0.0
    total_requests: int = 0
    total_limited: int = 0
    last_request_at: Optional[float] = None


@dataclass
class TokenBucketState:
    """State for token bucket algorithm."""
    tokens: float
    last_update: float
    max_tokens: float
    refill_rate: float  # tokens per second


class RateLimiter:
    """
    Rate limiter with support for multiple providers and algorithms.

    Uses SQLite for persistent state storage across restarts.
    """

    # Default rate limits per provider
    DEFAULT_LIMITS: Dict[str, RateLimitConfig] = {
        "claude": RateLimitConfig(rpm=50, tpm=100000, burst_size=10),
        "codex": RateLimitConfig(rpm=60, tpm=150000, burst_size=15),
        "gemini": RateLimitConfig(rpm=60, tpm=120000, burst_size=12),
        "opencode": RateLimitConfig(rpm=60, tpm=100000, burst_size=10),
        "droid": RateLimitConfig(rpm=30, tpm=50000, burst_size=5),
        "iflow": RateLimitConfig(rpm=30, tpm=50000, burst_size=5),
        "kimi": RateLimitConfig(rpm=30, tpm=80000, burst_size=8),
        "qwen": RateLimitConfig(rpm=30, tpm=80000, burst_size=8),
    }

    def __init__(
        self,
        db_path: Optional[str] = None,
        config: Optional[Dict[str, RateLimitConfig]] = None,
    ):
        """
        Initialize the rate limiter.

        Args:
            db_path: Path to SQLite database for persistent state
            config: Optional custom rate limit configurations
        """
        if db_path is None:
            db_path = str(Path.home() / ".ccb_config" / "ratelimit.db")

        self.db_path = db_path
        self.configs: Dict[str, RateLimitConfig] = {**self.DEFAULT_LIMITS}
        if config:
            self.configs.update(config)

        # In-memory state for token buckets
        self._buckets: Dict[str, TokenBucketState] = {}
        self._lock = threading.RLock()  # Use RLock to allow reentrant locking

        # Initialize database
        self._init_db()
        self._load_state()

    def _init_db(self) -> None:
        """Initialize the SQLite database."""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS rate_limit_state (
                    provider TEXT PRIMARY KEY,
                    tokens REAL NOT NULL,
                    last_update REAL NOT NULL,
                    max_tokens REAL NOT NULL,
                    refill_rate REAL NOT NULL
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS rate_limit_requests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    provider TEXT NOT NULL,
                    timestamp REAL NOT NULL,
                    tokens_used INTEGER DEFAULT 1,
                    was_limited INTEGER DEFAULT 0
                )
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_requests_provider_time
                ON rate_limit_requests(provider, timestamp)
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS rate_limit_config (
                    provider TEXT PRIMARY KEY,
                    rpm INTEGER NOT NULL,
                    tpm INTEGER NOT NULL,
                    burst_size INTEGER NOT NULL,
                    algorithm TEXT NOT NULL,
                    enabled INTEGER DEFAULT 1
                )
            """)

            conn.commit()

    def _load_state(self) -> None:
        """Load state from database."""
        with sqlite3.connect(self.db_path) as conn:
            # Load bucket states
            cursor = conn.execute(
                "SELECT provider, tokens, last_update, max_tokens, refill_rate FROM rate_limit_state"
            )
            for row in cursor:
                provider, tokens, last_update, max_tokens, refill_rate = row
                self._buckets[provider] = TokenBucketState(
                    tokens=tokens,
                    last_update=last_update,
                    max_tokens=max_tokens,
                    refill_rate=refill_rate,
                )

            # Load custom configs
            cursor = conn.execute(
                "SELECT provider, rpm, tpm, burst_size, algorithm, enabled FROM rate_limit_config"
            )
            for row in cursor:
                provider, rpm, tpm, burst_size, algorithm, enabled = row
                self.configs[provider] = RateLimitConfig(
                    rpm=rpm,
                    tpm=tpm,
                    burst_size=burst_size,
                    algorithm=RateLimitAlgorithm(algorithm),
                    enabled=bool(enabled),
                )

    def _save_bucket_state(self, provider: str, state: TokenBucketState) -> None:
        """Save bucket state to database."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO rate_limit_state
                (provider, tokens, last_update, max_tokens, refill_rate)
                VALUES (?, ?, ?, ?, ?)
            """, (provider, state.tokens, state.last_update, state.max_tokens, state.refill_rate))
            conn.commit()

    def _get_or_create_bucket(self, provider: str) -> TokenBucketState:
        """Get or create a token bucket for a provider."""
        if provider not in self._buckets:
            config = self.configs.get(provider, RateLimitConfig())
            # refill_rate = rpm / 60 (tokens per second)
            refill_rate = config.rpm / 60.0
            self._buckets[provider] = TokenBucketState(
                tokens=float(config.burst_size),
                last_update=time.time(),
                max_tokens=float(config.burst_size),
                refill_rate=refill_rate,
            )
        return self._buckets[provider]

    def _refill_bucket(self, bucket: TokenBucketState) -> None:
        """Refill tokens based on elapsed time."""
        now = time.time()
        elapsed = now - bucket.last_update
        tokens_to_add = elapsed * bucket.refill_rate
        bucket.tokens = min(bucket.max_tokens, bucket.tokens + tokens_to_add)
        bucket.last_update = now

    def acquire(
        self,
        provider: str,
        tokens: int = 1,
        block: bool = False,
        timeout_s: float = 30.0,
    ) -> bool:
        """
        Attempt to acquire tokens for a request.

        Args:
            provider: The provider to acquire tokens for
            tokens: Number of tokens to acquire (default: 1)
            block: If True, block until tokens are available
            timeout_s: Maximum time to wait if blocking

        Returns:
            True if tokens were acquired, False if rate limited
        """
        config = self.configs.get(provider, RateLimitConfig())

        # If rate limiting is disabled for this provider, always allow
        if not config.enabled:
            return True

        with self._lock:
            bucket = self._get_or_create_bucket(provider)
            self._refill_bucket(bucket)

            start_time = time.time()

            while True:
                if bucket.tokens >= tokens:
                    bucket.tokens -= tokens
                    self._save_bucket_state(provider, bucket)
                    self._record_request(provider, tokens, was_limited=False)
                    return True

                if not block:
                    self._record_request(provider, tokens, was_limited=True)
                    return False

                # Calculate wait time
                tokens_needed = tokens - bucket.tokens
                wait_time = tokens_needed / bucket.refill_rate

                # Check timeout
                elapsed = time.time() - start_time
                if elapsed + wait_time > timeout_s:
                    self._record_request(provider, tokens, was_limited=True)
                    return False

                # Wait and refill
                time.sleep(min(wait_time, 0.1))
                self._refill_bucket(bucket)

    def _record_request(
        self,
        provider: str,
        tokens: int,
        was_limited: bool,
    ) -> None:
        """Record a request in the database."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO rate_limit_requests (provider, timestamp, tokens_used, was_limited)
                VALUES (?, ?, ?, ?)
            """, (provider, time.time(), tokens, int(was_limited)))
            conn.commit()

    def get_wait_time(self, provider: str, tokens: int = 1) -> float:
        """
        Get the estimated wait time until tokens are available.

        Args:
            provider: The provider to check
            tokens: Number of tokens needed

        Returns:
            Wait time in seconds (0 if tokens are available)
        """
        config = self.configs.get(provider, RateLimitConfig())
        if not config.enabled:
            return 0.0

        with self._lock:
            bucket = self._get_or_create_bucket(provider)
            self._refill_bucket(bucket)

            if bucket.tokens >= tokens:
                return 0.0

            tokens_needed = tokens - bucket.tokens
            return tokens_needed / bucket.refill_rate

    def reset(self, provider: str) -> None:
        """
        Reset rate limit state for a provider.

        Args:
            provider: The provider to reset
        """
        with self._lock:
            config = self.configs.get(provider, RateLimitConfig())
            refill_rate = config.rpm / 60.0

            self._buckets[provider] = TokenBucketState(
                tokens=float(config.burst_size),
                last_update=time.time(),
                max_tokens=float(config.burst_size),
                refill_rate=refill_rate,
            )
            self._save_bucket_state(provider, self._buckets[provider])

    def reset_all(self) -> None:
        """Reset rate limit state for all providers."""
        for provider in self.configs:
            self.reset(provider)

    def get_stats(self, provider: str) -> RateLimitStats:
        """
        Get rate limit statistics for a provider.

        Args:
            provider: The provider to get stats for

        Returns:
            RateLimitStats with current state
        """
        config = self.configs.get(provider, RateLimitConfig())

        with self._lock:
            bucket = self._get_or_create_bucket(provider)
            self._refill_bucket(bucket)

            # Get request counts from last minute
            with sqlite3.connect(self.db_path) as conn:
                one_minute_ago = time.time() - 60

                cursor = conn.execute("""
                    SELECT COUNT(*), SUM(tokens_used), SUM(was_limited)
                    FROM rate_limit_requests
                    WHERE provider = ? AND timestamp > ?
                """, (provider, one_minute_ago))
                row = cursor.fetchone()
                current_rpm = row[0] or 0
                current_tpm = row[1] or 0
                total_limited = row[2] or 0

                cursor = conn.execute("""
                    SELECT COUNT(*), MAX(timestamp)
                    FROM rate_limit_requests
                    WHERE provider = ?
                """, (provider,))
                row = cursor.fetchone()
                total_requests = row[0] or 0
                last_request_at = row[1]

            wait_time = self.get_wait_time(provider)

            return RateLimitStats(
                provider=provider,
                current_rpm=current_rpm,
                current_tpm=current_tpm,
                limit_rpm=config.rpm,
                limit_tpm=config.tpm,
                available_tokens=bucket.tokens,
                is_limited=bucket.tokens < 1,
                wait_time_s=wait_time,
                total_requests=total_requests,
                total_limited=total_limited,
                last_request_at=last_request_at,
            )

    def get_all_stats(self) -> List[RateLimitStats]:
        """Get rate limit statistics for all providers."""
        return [self.get_stats(p) for p in self.configs]

    def set_config(
        self,
        provider: str,
        rpm: Optional[int] = None,
        tpm: Optional[int] = None,
        burst_size: Optional[int] = None,
        enabled: Optional[bool] = None,
    ) -> None:
        """
        Update rate limit configuration for a provider.

        Args:
            provider: The provider to configure
            rpm: Requests per minute limit
            tpm: Tokens per minute limit
            burst_size: Burst allowance
            enabled: Whether rate limiting is enabled
        """
        config = self.configs.get(provider, RateLimitConfig())

        if rpm is not None:
            config.rpm = rpm
        if tpm is not None:
            config.tpm = tpm
        if burst_size is not None:
            config.burst_size = burst_size
        if enabled is not None:
            config.enabled = enabled

        self.configs[provider] = config

        # Save to database
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO rate_limit_config
                (provider, rpm, tpm, burst_size, algorithm, enabled)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                provider,
                config.rpm,
                config.tpm,
                config.burst_size,
                config.algorithm.value,
                int(config.enabled),
            ))
            conn.commit()

        # Reset bucket with new config
        self.reset(provider)

    def cleanup_old_records(self, hours: int = 24) -> int:
        """
        Clean up old request records.

        Args:
            hours: Delete records older than this many hours

        Returns:
            Number of records deleted
        """
        cutoff = time.time() - (hours * 3600)

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "DELETE FROM rate_limit_requests WHERE timestamp < ?",
                (cutoff,)
            )
            conn.commit()
            return cursor.rowcount


# Singleton instance
_rate_limiter: Optional[RateLimiter] = None


def get_rate_limiter() -> RateLimiter:
    """Get the global rate limiter instance."""
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = RateLimiter()
    return _rate_limiter
