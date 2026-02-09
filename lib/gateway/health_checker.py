"""
Health Checker for CCB Gateway.

Provides periodic health checks for all configured providers,
with automatic disable/enable based on availability.
"""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, Callable, Awaitable, List

from .models import ProviderStatus, GatewayRequest


@dataclass
class ProviderHealth:
    """Health status for a single provider."""
    provider: str
    status: ProviderStatus = ProviderStatus.UNKNOWN
    last_check: Optional[float] = None
    last_success: Optional[float] = None
    last_failure: Optional[float] = None
    consecutive_failures: int = 0
    consecutive_successes: int = 0
    avg_latency_ms: float = 0.0
    latency_samples: List[float] = field(default_factory=list)
    error_message: Optional[str] = None
    auto_disabled: bool = False

    def record_success(self, latency_ms: float) -> None:
        """Record a successful health check."""
        self.last_check = time.time()
        self.last_success = time.time()
        self.consecutive_failures = 0
        self.consecutive_successes += 1
        self.error_message = None

        # Update latency tracking
        self.latency_samples.append(latency_ms)
        if len(self.latency_samples) > 10:
            self.latency_samples = self.latency_samples[-10:]
        self.avg_latency_ms = sum(self.latency_samples) / len(self.latency_samples)

        # Update status
        if self.consecutive_successes >= 2:
            self.status = ProviderStatus.HEALTHY
            self.auto_disabled = False
        elif self.status == ProviderStatus.UNAVAILABLE:
            self.status = ProviderStatus.DEGRADED

    def record_failure(self, error: Optional[str] = None) -> None:
        """Record a failed health check."""
        self.last_check = time.time()
        self.last_failure = time.time()
        self.consecutive_successes = 0
        self.consecutive_failures += 1
        self.error_message = error

        # Update status based on consecutive failures
        if self.consecutive_failures >= 3:
            self.status = ProviderStatus.UNAVAILABLE
            self.auto_disabled = True
        elif self.consecutive_failures >= 2:
            self.status = ProviderStatus.DEGRADED

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "provider": self.provider,
            "status": self.status.value,
            "last_check": self.last_check,
            "last_success": self.last_success,
            "last_failure": self.last_failure,
            "consecutive_failures": self.consecutive_failures,
            "consecutive_successes": self.consecutive_successes,
            "avg_latency_ms": round(self.avg_latency_ms, 2),
            "error_message": self.error_message,
            "auto_disabled": self.auto_disabled,
        }


class HealthChecker:
    """
    Periodic health checker for all configured providers.

    Features:
    - Configurable check interval (default: 30s)
    - Automatic disable of unhealthy providers
    - Automatic re-enable when provider recovers
    - Latency tracking and averaging
    - Callback support for status changes
    """

    def __init__(
        self,
        check_interval_s: float = 30.0,
        failure_threshold: int = 3,
        recovery_threshold: int = 2,
        check_timeout_s: float = 15.0,
    ):
        """
        Initialize the health checker.

        Args:
            check_interval_s: Interval between health checks
            failure_threshold: Consecutive failures before marking unavailable
            recovery_threshold: Consecutive successes before marking healthy
            check_timeout_s: Timeout for each health check request
        """
        self.check_interval_s = check_interval_s
        self.failure_threshold = failure_threshold
        self.recovery_threshold = recovery_threshold
        self.check_timeout_s = check_timeout_s

        self._providers: Dict[str, ProviderHealth] = {}
        self._backends: Dict[str, Any] = {}
        self._provider_timeouts: Dict[str, float] = {}
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._on_status_change: Optional[Callable[[str, ProviderStatus, ProviderStatus], Awaitable[None]]] = None

    def register_provider(self, provider: str, backend: Any) -> None:
        """Register a provider for health checking."""
        self._providers[provider] = ProviderHealth(provider=provider)
        self._backends[provider] = backend

    def set_provider_timeout(self, provider: str, timeout_s: float) -> None:
        """Set per-provider health check timeout."""
        if timeout_s > 0:
            self._provider_timeouts[provider] = float(timeout_s)

    def unregister_provider(self, provider: str) -> None:
        """Unregister a provider from health checking."""
        self._providers.pop(provider, None)
        self._backends.pop(provider, None)

    def set_status_change_callback(
        self,
        callback: Callable[[str, ProviderStatus, ProviderStatus], Awaitable[None]],
    ) -> None:
        """Set callback for status changes. Args: (provider, old_status, new_status)"""
        self._on_status_change = callback

    async def start(self) -> None:
        """Start the health checker background task."""
        if self._running:
            return

        self._running = True
        self._task = asyncio.create_task(self._check_loop())

    async def stop(self) -> None:
        """Stop the health checker."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _check_loop(self) -> None:
        """Main health check loop."""
        while self._running:
            # Run health checks for all providers concurrently
            tasks = [
                self._check_provider(provider, backend)
                for provider, backend in self._backends.items()
            ]
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)

            # Wait for next interval
            await asyncio.sleep(self.check_interval_s)

    async def _check_provider(self, provider: str, backend: Any) -> None:
        """Check health of a single provider."""
        health = self._providers.get(provider)
        if not health:
            return

        old_status = health.status

        # Create a simple test request
        timeout_s = self._provider_timeouts.get(provider, self.check_timeout_s)
        test_request = GatewayRequest.create(
            provider=provider,
            message="ping",
            timeout_s=timeout_s,
            metadata={"health_check": True},
        )

        start_time = time.time()
        try:
            result = await asyncio.wait_for(
                backend.execute(test_request),
                timeout=timeout_s,
            )

            latency_ms = (time.time() - start_time) * 1000

            if result.success:
                health.record_success(latency_ms)
            else:
                health.record_failure(result.error)

        except asyncio.TimeoutError:
            health.record_failure("Health check timed out")
        except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError) as e:
            health.record_failure(str(e))

        # Notify on status change
        if health.status != old_status and self._on_status_change:
            try:
                await self._on_status_change(provider, old_status, health.status)
            except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError):
                pass  # Don't let callback errors affect health checks

    async def check_now(self, provider: Optional[str] = None) -> Dict[str, ProviderHealth]:
        """
        Run immediate health check(s).

        Args:
            provider: Specific provider to check, or None for all

        Returns:
            Dictionary of provider health statuses
        """
        if provider:
            backend = self._backends.get(provider)
            if backend:
                await self._check_provider(provider, backend)
            return {provider: self._providers.get(provider)} if provider in self._providers else {}
        else:
            tasks = [
                self._check_provider(p, b)
                for p, b in self._backends.items()
            ]
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
            return dict(self._providers)

    def get_health(self, provider: str) -> Optional[ProviderHealth]:
        """Get health status for a specific provider."""
        return self._providers.get(provider)

    def get_all_health(self) -> Dict[str, ProviderHealth]:
        """Get health status for all providers."""
        return dict(self._providers)

    def get_healthy_providers(self) -> List[str]:
        """Get list of healthy provider names."""
        return [
            p for p, h in self._providers.items()
            if h.status == ProviderStatus.HEALTHY
        ]

    def get_available_providers(self) -> List[str]:
        """Get list of available (not unavailable) provider names."""
        return [
            p for p, h in self._providers.items()
            if h.status != ProviderStatus.UNAVAILABLE
        ]

    def is_provider_healthy(self, provider: str) -> bool:
        """Check if a provider is healthy."""
        health = self._providers.get(provider)
        return health is not None and health.status == ProviderStatus.HEALTHY

    def is_provider_available(self, provider: str) -> bool:
        """Check if a provider is available (not unavailable)."""
        health = self._providers.get(provider)
        return health is None or health.status != ProviderStatus.UNAVAILABLE

    def get_stats(self) -> Dict[str, Any]:
        """Get health checker statistics."""
        total = len(self._providers)
        healthy = sum(1 for h in self._providers.values() if h.status == ProviderStatus.HEALTHY)
        degraded = sum(1 for h in self._providers.values() if h.status == ProviderStatus.DEGRADED)
        unavailable = sum(1 for h in self._providers.values() if h.status == ProviderStatus.UNAVAILABLE)
        unknown = sum(1 for h in self._providers.values() if h.status == ProviderStatus.UNKNOWN)

        return {
            "running": self._running,
            "check_interval_s": self.check_interval_s,
            "total_providers": total,
            "healthy": healthy,
            "degraded": degraded,
            "unavailable": unavailable,
            "unknown": unknown,
            "providers": {p: h.to_dict() for p, h in self._providers.items()},
        }

    def force_enable(self, provider: str) -> bool:
        """Force enable a provider that was auto-disabled."""
        health = self._providers.get(provider)
        if health:
            health.auto_disabled = False
            health.status = ProviderStatus.UNKNOWN
            health.consecutive_failures = 0
            return True
        return False

    def force_disable(self, provider: str) -> bool:
        """Force disable a provider."""
        health = self._providers.get(provider)
        if health:
            health.status = ProviderStatus.UNAVAILABLE
            health.auto_disabled = True
            return True
        return False
