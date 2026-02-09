"""Compatibility alias for gateway config module."""

from .gateway_config import (
    AuthConfig,
    CacheConfig,
    GatewayConfig,
    MetricsConfig,
    ParallelConfig,
    ProviderConfig,
    RateLimitConfig,
    RetryConfig,
    StreamConfig,
)

__all__ = [
    "GatewayConfig",
    "ProviderConfig",
    "RetryConfig",
    "CacheConfig",
    "StreamConfig",
    "ParallelConfig",
    "AuthConfig",
    "RateLimitConfig",
    "MetricsConfig",
]

