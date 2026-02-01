"""
Rate Limiter for CCB Gateway.

Implements token bucket algorithm for request rate limiting.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, Callable, Awaitable

try:
    from fastapi import Request
    from fastapi.responses import JSONResponse
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False


@dataclass
class RateLimitConfig:
    """Configuration for rate limiting."""
    enabled: bool = True
    requests_per_minute: int = 60  # Default: 60 RPM
    burst_size: int = 10  # Allow burst of up to 10 requests
    by_api_key: bool = True  # Rate limit per API key
    by_ip: bool = True  # Rate limit per IP address
    # Separate limits for different endpoint types
    endpoint_limits: Dict[str, int] = field(default_factory=lambda: {
        "/api/ask": 30,  # More restrictive for AI requests
        "/api/ask/stream": 30,
        "/api/admin": 10,  # Very restrictive for admin endpoints
    })


@dataclass
class TokenBucket:
    """Token bucket for rate limiting."""
    capacity: float  # Maximum tokens (burst size)
    tokens: float  # Current tokens
    refill_rate: float  # Tokens per second
    last_refill: float  # Last refill timestamp

    @classmethod
    def create(cls, requests_per_minute: int, burst_size: int) -> "TokenBucket":
        """Create a new token bucket."""
        now = time.time()
        refill_rate = requests_per_minute / 60.0  # Convert to per-second
        return cls(
            capacity=float(burst_size),
            tokens=float(burst_size),  # Start full
            refill_rate=refill_rate,
            last_refill=now,
        )

    def refill(self) -> None:
        """Refill tokens based on elapsed time."""
        now = time.time()
        elapsed = now - self.last_refill
        self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)
        self.last_refill = now

    def consume(self, tokens: float = 1.0) -> bool:
        """
        Try to consume tokens.

        Args:
            tokens: Number of tokens to consume

        Returns:
            True if tokens were consumed, False if insufficient tokens
        """
        self.refill()
        if self.tokens >= tokens:
            self.tokens -= tokens
            return True
        return False

    def time_until_available(self, tokens: float = 1.0) -> float:
        """
        Calculate time until tokens are available.

        Args:
            tokens: Number of tokens needed

        Returns:
            Seconds until tokens are available (0 if already available)
        """
        self.refill()
        if self.tokens >= tokens:
            return 0.0
        needed = tokens - self.tokens
        return needed / self.refill_rate


@dataclass
class RateLimitInfo:
    """Information about rate limit status."""
    allowed: bool
    limit: int
    remaining: int
    reset_after_s: float
    key: str

    def to_headers(self) -> Dict[str, str]:
        """Convert to rate limit headers."""
        return {
            "X-RateLimit-Limit": str(self.limit),
            "X-RateLimit-Remaining": str(max(0, self.remaining)),
            "X-RateLimit-Reset-After": f"{self.reset_after_s:.1f}",
        }


class RateLimiter:
    """
    Token bucket rate limiter.

    Supports per-key and per-IP rate limiting with configurable limits.
    """

    def __init__(self, config: Optional[RateLimitConfig] = None):
        """
        Initialize the rate limiter.

        Args:
            config: Rate limit configuration
        """
        self.config = config or RateLimitConfig()
        self._buckets: Dict[str, TokenBucket] = {}
        self._cleanup_interval = 300.0  # Cleanup every 5 minutes
        self._last_cleanup = time.time()

    def _get_bucket_key(
        self,
        api_key_id: Optional[str],
        ip_address: Optional[str],
        endpoint: Optional[str] = None,
    ) -> str:
        """Generate a bucket key for the request."""
        parts = []
        if self.config.by_api_key and api_key_id:
            parts.append(f"key:{api_key_id}")
        if self.config.by_ip and ip_address:
            parts.append(f"ip:{ip_address}")
        if endpoint:
            parts.append(f"ep:{endpoint}")
        return ":".join(parts) if parts else "global"

    def _get_limit_for_endpoint(self, path: str) -> int:
        """Get the rate limit for a specific endpoint."""
        for prefix, limit in self.config.endpoint_limits.items():
            if path.startswith(prefix):
                return limit
        return self.config.requests_per_minute

    def _get_or_create_bucket(
        self,
        key: str,
        requests_per_minute: int,
    ) -> TokenBucket:
        """Get or create a token bucket for the key."""
        if key not in self._buckets:
            self._buckets[key] = TokenBucket.create(
                requests_per_minute=requests_per_minute,
                burst_size=self.config.burst_size,
            )
        return self._buckets[key]

    def _maybe_cleanup(self) -> None:
        """Periodically cleanup old buckets."""
        now = time.time()
        if now - self._last_cleanup < self._cleanup_interval:
            return

        self._last_cleanup = now
        # Remove buckets that haven't been used in a while
        stale_threshold = now - 3600  # 1 hour
        stale_keys = [
            key for key, bucket in self._buckets.items()
            if bucket.last_refill < stale_threshold
        ]
        for key in stale_keys:
            del self._buckets[key]

    def check(
        self,
        api_key_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        endpoint: Optional[str] = None,
        key_rate_limit: Optional[int] = None,
    ) -> RateLimitInfo:
        """
        Check if a request is allowed.

        Args:
            api_key_id: Optional API key ID
            ip_address: Optional IP address
            endpoint: Optional endpoint path
            key_rate_limit: Optional per-key rate limit override

        Returns:
            RateLimitInfo with allow/deny decision
        """
        if not self.config.enabled:
            return RateLimitInfo(
                allowed=True,
                limit=0,
                remaining=0,
                reset_after_s=0.0,
                key="disabled",
            )

        self._maybe_cleanup()

        # Determine rate limit
        if key_rate_limit:
            limit = key_rate_limit
        elif endpoint:
            limit = self._get_limit_for_endpoint(endpoint)
        else:
            limit = self.config.requests_per_minute

        # Get bucket key
        bucket_key = self._get_bucket_key(api_key_id, ip_address, endpoint)

        # Get or create bucket
        bucket = self._get_or_create_bucket(bucket_key, limit)

        # Try to consume a token
        allowed = bucket.consume(1.0)
        reset_after = bucket.time_until_available(1.0) if not allowed else 0.0

        return RateLimitInfo(
            allowed=allowed,
            limit=limit,
            remaining=int(bucket.tokens),
            reset_after_s=reset_after,
            key=bucket_key,
        )

    def get_stats(self) -> Dict[str, Any]:
        """Get rate limiter statistics."""
        return {
            "enabled": self.config.enabled,
            "total_buckets": len(self._buckets),
            "config": {
                "requests_per_minute": self.config.requests_per_minute,
                "burst_size": self.config.burst_size,
                "by_api_key": self.config.by_api_key,
                "by_ip": self.config.by_ip,
            },
        }


class RateLimitMiddleware:
    """
    FastAPI middleware for rate limiting.
    """

    def __init__(self, limiter: RateLimiter):
        """
        Initialize the rate limit middleware.

        Args:
            limiter: RateLimiter instance
        """
        self.limiter = limiter

    async def __call__(
        self,
        request: "Request",
        call_next: Callable[["Request"], Awaitable[Any]],
    ):
        """Process the request."""
        if not HAS_FASTAPI:
            return await call_next(request)

        if not self.limiter.config.enabled:
            return await call_next(request)

        # Get identifiers
        api_key_id = None
        key_rate_limit = None
        if hasattr(request.state, "api_key") and request.state.api_key:
            api_key_id = request.state.api_key.key_id
            key_rate_limit = request.state.api_key.rate_limit_rpm

        ip_address = request.client.host if request.client else None
        endpoint = request.url.path

        # Check rate limit
        result = self.limiter.check(
            api_key_id=api_key_id,
            ip_address=ip_address,
            endpoint=endpoint,
            key_rate_limit=key_rate_limit,
        )

        if not result.allowed:
            return JSONResponse(
                status_code=429,
                content={
                    "error": "Rate limit exceeded",
                    "detail": f"Too many requests. Try again in {result.reset_after_s:.1f} seconds.",
                    "retry_after": result.reset_after_s,
                },
                headers=result.to_headers(),
            )

        # Add rate limit headers to response
        response = await call_next(request)

        # Add headers to response
        for key, value in result.to_headers().items():
            response.headers[key] = value

        return response
