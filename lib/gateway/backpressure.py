"""
Backpressure Controller for CCB Gateway.

Dynamically adjusts concurrency limits based on system load and performance metrics
to prevent overload and ensure graceful degradation.
"""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, Callable, List
from enum import Enum


class LoadLevel(Enum):
    """System load levels."""
    LOW = "low"           # Can accept more load
    NORMAL = "normal"     # Operating normally
    HIGH = "high"         # Approaching limits
    CRITICAL = "critical" # At or over capacity


@dataclass
class BackpressureMetrics:
    """Metrics used for backpressure decisions."""
    queue_depth: int = 0
    processing_count: int = 0
    max_concurrent: int = 10
    avg_latency_ms: float = 0.0
    latency_p95_ms: float = 0.0
    success_rate: float = 1.0
    requests_per_second: float = 0.0
    timestamp: float = field(default_factory=time.time)

    def utilization(self) -> float:
        """Calculate current utilization (0.0 to 1.0+)."""
        if self.max_concurrent == 0:
            return 1.0
        return self.processing_count / self.max_concurrent


@dataclass
class BackpressureConfig:
    """Configuration for backpressure controller."""
    # Concurrency limits
    min_concurrent: int = 2
    max_concurrent: int = 20
    initial_concurrent: int = 10

    # Queue thresholds
    queue_depth_low: int = 10       # Below this, scale up
    queue_depth_high: int = 50      # Above this, scale down
    queue_depth_critical: int = 100 # Reject new requests

    # Latency thresholds (ms)
    latency_target_ms: float = 5000.0   # Target latency
    latency_high_ms: float = 15000.0    # Start scaling down
    latency_critical_ms: float = 30000.0 # Aggressive scale down

    # Success rate thresholds
    success_rate_low: float = 0.8   # Below this, scale down
    success_rate_critical: float = 0.5  # Aggressive scale down

    # Adjustment settings
    scale_up_step: int = 2     # How much to increase
    scale_down_step: int = 1   # How much to decrease
    cooldown_s: float = 10.0   # Time between adjustments
    evaluation_window_s: float = 60.0  # Window for metrics


class BackpressureController:
    """
    Dynamic backpressure controller for the gateway.

    Features:
    - Monitors queue depth, latency, and success rate
    - Dynamically adjusts max_concurrent
    - Supports graceful degradation under load
    - Provides load level indicators
    - Callback support for limit changes
    """

    def __init__(
        self,
        config: Optional[BackpressureConfig] = None,
        queue_getter: Optional[Callable[[], int]] = None,
        processing_getter: Optional[Callable[[], int]] = None,
    ):
        """
        Initialize the backpressure controller.

        Args:
            config: Configuration settings
            queue_getter: Callable that returns current queue depth
            processing_getter: Callable that returns current processing count
        """
        self.config = config or BackpressureConfig()
        self._queue_getter = queue_getter
        self._processing_getter = processing_getter

        self._current_max_concurrent = self.config.initial_concurrent
        self._last_adjustment = 0.0
        self._running = False
        self._task: Optional[asyncio.Task] = None

        # Metrics history
        self._latency_samples: List[float] = []
        self._success_samples: List[bool] = []
        self._request_timestamps: List[float] = []

        # Callbacks
        self._on_limit_change: Optional[Callable[[int, int], None]] = None
        self._on_load_change: Optional[Callable[[LoadLevel, LoadLevel], None]] = None

        self._current_load = LoadLevel.NORMAL

    def set_queue_getter(self, getter: Callable[[], int]) -> None:
        """Set the function to get current queue depth."""
        self._queue_getter = getter

    def set_processing_getter(self, getter: Callable[[], int]) -> None:
        """Set the function to get current processing count."""
        self._processing_getter = getter

    def set_limit_change_callback(self, callback: Callable[[int, int], None]) -> None:
        """Set callback for limit changes. Args: (old_limit, new_limit)"""
        self._on_limit_change = callback

    def set_load_change_callback(self, callback: Callable[[LoadLevel, LoadLevel], None]) -> None:
        """Set callback for load level changes. Args: (old_level, new_level)"""
        self._on_load_change = callback

    async def start(self, evaluation_interval_s: float = 5.0) -> None:
        """Start the backpressure controller."""
        if self._running:
            return

        self._running = True
        self._task = asyncio.create_task(self._evaluation_loop(evaluation_interval_s))

    async def stop(self) -> None:
        """Stop the backpressure controller."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _evaluation_loop(self, interval_s: float) -> None:
        """Main evaluation loop."""
        while self._running:
            self._evaluate_and_adjust()
            await asyncio.sleep(interval_s)

    def record_request_start(self) -> None:
        """Record that a request has started processing."""
        now = time.time()
        self._request_timestamps.append(now)
        # Keep only recent timestamps
        cutoff = now - self.config.evaluation_window_s
        self._request_timestamps = [t for t in self._request_timestamps if t > cutoff]

    def record_request_complete(self, latency_ms: float, success: bool) -> None:
        """Record request completion metrics."""
        now = time.time()

        # Record latency
        self._latency_samples.append(latency_ms)
        if len(self._latency_samples) > 100:
            self._latency_samples = self._latency_samples[-100:]

        # Record success
        self._success_samples.append(success)
        if len(self._success_samples) > 100:
            self._success_samples = self._success_samples[-100:]

    def get_metrics(self) -> BackpressureMetrics:
        """Get current metrics."""
        queue_depth = self._queue_getter() if self._queue_getter else 0
        processing = self._processing_getter() if self._processing_getter else 0

        # Calculate average latency
        avg_latency = sum(self._latency_samples) / len(self._latency_samples) if self._latency_samples else 0

        # Calculate P95 latency
        if self._latency_samples:
            sorted_latencies = sorted(self._latency_samples)
            p95_idx = int(len(sorted_latencies) * 0.95)
            p95_latency = sorted_latencies[min(p95_idx, len(sorted_latencies) - 1)]
        else:
            p95_latency = 0

        # Calculate success rate
        if self._success_samples:
            success_rate = sum(1 for s in self._success_samples if s) / len(self._success_samples)
        else:
            success_rate = 1.0

        # Calculate requests per second
        now = time.time()
        cutoff = now - 60.0  # Last minute
        recent_requests = [t for t in self._request_timestamps if t > cutoff]
        rps = len(recent_requests) / 60.0

        return BackpressureMetrics(
            queue_depth=queue_depth,
            processing_count=processing,
            max_concurrent=self._current_max_concurrent,
            avg_latency_ms=avg_latency,
            latency_p95_ms=p95_latency,
            success_rate=success_rate,
            requests_per_second=rps,
        )

    def get_load_level(self) -> LoadLevel:
        """Determine current load level."""
        metrics = self.get_metrics()
        config = self.config

        # Critical conditions
        if (metrics.queue_depth >= config.queue_depth_critical or
            metrics.success_rate < config.success_rate_critical or
            metrics.latency_p95_ms >= config.latency_critical_ms):
            return LoadLevel.CRITICAL

        # High conditions
        if (metrics.queue_depth >= config.queue_depth_high or
            metrics.success_rate < config.success_rate_low or
            metrics.latency_p95_ms >= config.latency_high_ms or
            metrics.utilization() > 0.9):
            return LoadLevel.HIGH

        # Low conditions
        if (metrics.queue_depth <= config.queue_depth_low and
            metrics.utilization() < 0.5 and
            metrics.latency_p95_ms < config.latency_target_ms):
            return LoadLevel.LOW

        return LoadLevel.NORMAL

    def _evaluate_and_adjust(self) -> None:
        """Evaluate metrics and adjust limits if needed."""
        now = time.time()

        # Check cooldown
        if now - self._last_adjustment < self.config.cooldown_s:
            return

        old_load = self._current_load
        new_load = self.get_load_level()

        # Update load level
        if new_load != old_load:
            self._current_load = new_load
            if self._on_load_change:
                try:
                    self._on_load_change(old_load, new_load)
                except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError):
                    pass

        # Adjust concurrency based on load
        old_limit = self._current_max_concurrent
        new_limit = old_limit

        if new_load == LoadLevel.CRITICAL:
            # Aggressive scale down
            new_limit = max(
                self.config.min_concurrent,
                old_limit - self.config.scale_down_step * 2
            )
        elif new_load == LoadLevel.HIGH:
            # Scale down
            new_limit = max(
                self.config.min_concurrent,
                old_limit - self.config.scale_down_step
            )
        elif new_load == LoadLevel.LOW:
            # Scale up
            new_limit = min(
                self.config.max_concurrent,
                old_limit + self.config.scale_up_step
            )
        # NORMAL: no change

        if new_limit != old_limit:
            self._current_max_concurrent = new_limit
            self._last_adjustment = now

            if self._on_limit_change:
                try:
                    self._on_limit_change(old_limit, new_limit)
                except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError):
                    pass

    def get_max_concurrent(self) -> int:
        """Get current max concurrent limit."""
        return self._current_max_concurrent

    def should_accept_request(self) -> bool:
        """Check if a new request should be accepted."""
        load = self.get_load_level()
        if load == LoadLevel.CRITICAL:
            # Only accept if queue is not at critical level
            queue_depth = self._queue_getter() if self._queue_getter else 0
            return queue_depth < self.config.queue_depth_critical
        return True

    def get_rejection_reason(self) -> Optional[str]:
        """Get reason for rejecting requests, if any."""
        metrics = self.get_metrics()
        config = self.config

        if metrics.queue_depth >= config.queue_depth_critical:
            return f"Queue depth ({metrics.queue_depth}) exceeds critical threshold ({config.queue_depth_critical})"

        if metrics.success_rate < config.success_rate_critical:
            return f"Success rate ({metrics.success_rate:.1%}) below critical threshold ({config.success_rate_critical:.1%})"

        return None

    def get_stats(self) -> Dict[str, Any]:
        """Get backpressure controller statistics."""
        metrics = self.get_metrics()
        return {
            "running": self._running,
            "current_max_concurrent": self._current_max_concurrent,
            "load_level": self._current_load.value,
            "metrics": {
                "queue_depth": metrics.queue_depth,
                "processing_count": metrics.processing_count,
                "utilization": round(metrics.utilization(), 3),
                "avg_latency_ms": round(metrics.avg_latency_ms, 2),
                "latency_p95_ms": round(metrics.latency_p95_ms, 2),
                "success_rate": round(metrics.success_rate, 3),
                "requests_per_second": round(metrics.requests_per_second, 2),
            },
            "config": {
                "min_concurrent": self.config.min_concurrent,
                "max_concurrent": self.config.max_concurrent,
                "queue_depth_critical": self.config.queue_depth_critical,
                "latency_target_ms": self.config.latency_target_ms,
            },
            "should_accept": self.should_accept_request(),
        }

    def reset(self) -> None:
        """Reset the controller to initial state."""
        self._current_max_concurrent = self.config.initial_concurrent
        self._last_adjustment = 0.0
        self._latency_samples.clear()
        self._success_samples.clear()
        self._request_timestamps.clear()
        self._current_load = LoadLevel.NORMAL
