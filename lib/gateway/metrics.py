"""
Prometheus Metrics for CCB Gateway.

Provides observability and monitoring capabilities.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from collections import defaultdict

# Try to import prometheus_client, but make it optional
try:
    from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
    HAS_PROMETHEUS = True
except ImportError:
    HAS_PROMETHEUS = False


@dataclass
class MetricsBucket:
    """A histogram bucket for latency tracking."""
    le: float  # Less than or equal to
    count: int = 0


@dataclass
class HistogramData:
    """Data for a histogram metric."""
    buckets: List[MetricsBucket] = field(default_factory=list)
    sum: float = 0.0
    count: int = 0

    @classmethod
    def create(cls, bucket_boundaries: List[float]) -> "HistogramData":
        """Create histogram with specified bucket boundaries."""
        buckets = [MetricsBucket(le=b) for b in bucket_boundaries]
        buckets.append(MetricsBucket(le=float("inf")))  # +Inf bucket
        return cls(buckets=buckets)

    def observe(self, value: float) -> None:
        """Record an observation."""
        self.sum += value
        self.count += 1
        for bucket in self.buckets:
            if value <= bucket.le:
                bucket.count += 1


class GatewayMetrics:
    """
    Prometheus metrics collector for the gateway.

    Provides both native prometheus_client integration (if available)
    and a fallback implementation for environments without it.
    """

    # Default latency buckets (in seconds)
    DEFAULT_LATENCY_BUCKETS = [0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0]

    def __init__(self, use_prometheus_client: bool = True):
        """
        Initialize metrics collector.

        Args:
            use_prometheus_client: Whether to use prometheus_client library if available
        """
        self._use_native = use_prometheus_client and HAS_PROMETHEUS
        self._start_time = time.time()

        if self._use_native:
            self._init_prometheus_metrics()
        else:
            self._init_fallback_metrics()

    def _init_prometheus_metrics(self) -> None:
        """Initialize native prometheus_client metrics."""
        # Request counters
        self.requests_total = Counter(
            "gateway_requests_total",
            "Total number of requests",
            ["provider", "status"],
        )

        # Request latency histogram
        self.request_latency = Histogram(
            "gateway_request_latency_seconds",
            "Request latency in seconds",
            ["provider"],
            buckets=self.DEFAULT_LATENCY_BUCKETS,
        )

        # Queue depth gauge
        self.queue_depth = Gauge(
            "gateway_queue_depth",
            "Current queue depth",
            ["provider"],
        )

        # Active connections gauge
        self.active_connections = Gauge(
            "gateway_active_connections",
            "Number of active WebSocket connections",
        )

        # Cache metrics
        self.cache_hits = Counter(
            "gateway_cache_hits_total",
            "Total cache hits",
        )
        self.cache_misses = Counter(
            "gateway_cache_misses_total",
            "Total cache misses",
        )

        # Retry metrics
        self.retries_total = Counter(
            "gateway_retries_total",
            "Total number of retries",
            ["provider", "reason"],
        )

        # Fallback metrics
        self.fallbacks_total = Counter(
            "gateway_fallbacks_total",
            "Total number of fallbacks",
            ["from_provider", "to_provider"],
        )

        # Rate limit metrics
        self.rate_limit_hits = Counter(
            "gateway_rate_limit_hits_total",
            "Total rate limit hits",
            ["key_type"],  # "api_key" or "ip"
        )

        # Token usage
        self.tokens_used = Counter(
            "gateway_tokens_used_total",
            "Total tokens used",
            ["provider"],
        )

        # Error counter
        self.errors_total = Counter(
            "gateway_errors_total",
            "Total errors",
            ["provider", "error_type"],
        )

    def _init_fallback_metrics(self) -> None:
        """Initialize fallback metrics (no prometheus_client)."""
        self._counters: Dict[str, Dict[tuple, int]] = defaultdict(lambda: defaultdict(int))
        self._gauges: Dict[str, Dict[tuple, float]] = defaultdict(lambda: defaultdict(float))
        self._histograms: Dict[str, Dict[tuple, HistogramData]] = defaultdict(dict)

    # ==================== Counter Methods ====================

    def inc_requests(self, provider: str, status: str) -> None:
        """Increment request counter."""
        if self._use_native:
            self.requests_total.labels(provider=provider, status=status).inc()
        else:
            self._counters["requests_total"][(provider, status)] += 1

    def inc_cache_hit(self) -> None:
        """Increment cache hit counter."""
        if self._use_native:
            self.cache_hits.inc()
        else:
            self._counters["cache_hits"][()] += 1

    def inc_cache_miss(self) -> None:
        """Increment cache miss counter."""
        if self._use_native:
            self.cache_misses.inc()
        else:
            self._counters["cache_misses"][()] += 1

    def inc_retries(self, provider: str, reason: str) -> None:
        """Increment retry counter."""
        if self._use_native:
            self.retries_total.labels(provider=provider, reason=reason).inc()
        else:
            self._counters["retries_total"][(provider, reason)] += 1

    def inc_fallbacks(self, from_provider: str, to_provider: str) -> None:
        """Increment fallback counter."""
        if self._use_native:
            self.fallbacks_total.labels(from_provider=from_provider, to_provider=to_provider).inc()
        else:
            self._counters["fallbacks_total"][(from_provider, to_provider)] += 1

    def inc_rate_limit_hit(self, key_type: str) -> None:
        """Increment rate limit hit counter."""
        if self._use_native:
            self.rate_limit_hits.labels(key_type=key_type).inc()
        else:
            self._counters["rate_limit_hits"][(key_type,)] += 1

    def inc_tokens(self, provider: str, count: int) -> None:
        """Increment token usage counter."""
        if self._use_native:
            self.tokens_used.labels(provider=provider).inc(count)
        else:
            self._counters["tokens_used"][(provider,)] += count

    def inc_errors(self, provider: str, error_type: str) -> None:
        """Increment error counter."""
        if self._use_native:
            self.errors_total.labels(provider=provider, error_type=error_type).inc()
        else:
            self._counters["errors_total"][(provider, error_type)] += 1

    # ==================== Gauge Methods ====================

    def set_queue_depth(self, provider: str, depth: int) -> None:
        """Set queue depth gauge."""
        if self._use_native:
            self.queue_depth.labels(provider=provider).set(depth)
        else:
            self._gauges["queue_depth"][(provider,)] = float(depth)

    def set_active_connections(self, count: int) -> None:
        """Set active connections gauge."""
        if self._use_native:
            self.active_connections.set(count)
        else:
            self._gauges["active_connections"][()] = float(count)

    # ==================== Histogram Methods ====================

    def observe_latency(self, provider: str, latency_s: float) -> None:
        """Record request latency."""
        if self._use_native:
            self.request_latency.labels(provider=provider).observe(latency_s)
        else:
            key = (provider,)
            if key not in self._histograms["request_latency"]:
                self._histograms["request_latency"][key] = HistogramData.create(
                    self.DEFAULT_LATENCY_BUCKETS
                )
            self._histograms["request_latency"][key].observe(latency_s)

    # ==================== Export Methods ====================

    def export(self) -> bytes:
        """
        Export metrics in Prometheus format.

        Returns:
            Prometheus-formatted metrics as bytes
        """
        if self._use_native:
            return generate_latest()
        else:
            return self._export_fallback()

    def _export_fallback(self) -> bytes:
        """Export metrics using fallback implementation."""
        lines = []

        # Export counters
        for metric_name, values in self._counters.items():
            lines.append(f"# HELP gateway_{metric_name} {metric_name}")
            lines.append(f"# TYPE gateway_{metric_name} counter")
            for labels, value in values.items():
                label_str = self._format_labels(metric_name, labels)
                lines.append(f"gateway_{metric_name}{label_str} {value}")

        # Export gauges
        for metric_name, values in self._gauges.items():
            lines.append(f"# HELP gateway_{metric_name} {metric_name}")
            lines.append(f"# TYPE gateway_{metric_name} gauge")
            for labels, value in values.items():
                label_str = self._format_labels(metric_name, labels)
                lines.append(f"gateway_{metric_name}{label_str} {value}")

        # Export histograms
        for metric_name, values in self._histograms.items():
            lines.append(f"# HELP gateway_{metric_name} {metric_name}")
            lines.append(f"# TYPE gateway_{metric_name} histogram")
            for labels, histogram in values.items():
                label_str = self._format_labels(metric_name, labels)
                for bucket in histogram.buckets:
                    le_str = "+Inf" if bucket.le == float("inf") else str(bucket.le)
                    if label_str:
                        bucket_labels = label_str[:-1] + f',le="{le_str}"' + "}"
                    else:
                        bucket_labels = f'{{le="{le_str}"}}'
                    lines.append(f"gateway_{metric_name}_bucket{bucket_labels} {bucket.count}")
                lines.append(f"gateway_{metric_name}_sum{label_str} {histogram.sum}")
                lines.append(f"gateway_{metric_name}_count{label_str} {histogram.count}")

        # Add uptime
        uptime = time.time() - self._start_time
        lines.append("# HELP gateway_uptime_seconds Gateway uptime in seconds")
        lines.append("# TYPE gateway_uptime_seconds gauge")
        lines.append(f"gateway_uptime_seconds {uptime:.2f}")

        return "\n".join(lines).encode("utf-8")

    def _format_labels(self, metric_name: str, labels: tuple) -> str:
        """Format labels for Prometheus output."""
        if not labels:
            return ""

        # Map metric names to label names
        label_names = {
            "requests_total": ["provider", "status"],
            "retries_total": ["provider", "reason"],
            "fallbacks_total": ["from_provider", "to_provider"],
            "rate_limit_hits": ["key_type"],
            "tokens_used": ["provider"],
            "errors_total": ["provider", "error_type"],
            "queue_depth": ["provider"],
            "request_latency": ["provider"],
        }

        names = label_names.get(metric_name, [f"label{i}" for i in range(len(labels))])
        pairs = [f'{name}="{value}"' for name, value in zip(names, labels)]
        return "{" + ",".join(pairs) + "}"

    def get_content_type(self) -> str:
        """Get the content type for metrics export."""
        if self._use_native:
            return CONTENT_TYPE_LATEST
        return "text/plain; charset=utf-8"

    def get_summary(self) -> Dict[str, Any]:
        """Get a summary of metrics as a dictionary."""
        if self._use_native:
            # For native prometheus, we'd need to sample the metrics
            # This is a simplified version
            return {
                "uptime_s": time.time() - self._start_time,
                "prometheus_client": True,
            }
        else:
            return {
                "uptime_s": time.time() - self._start_time,
                "prometheus_client": False,
                "counters": {k: dict(v) for k, v in self._counters.items()},
                "gauges": {k: dict(v) for k, v in self._gauges.items()},
            }


# Global metrics instance (singleton pattern)
_metrics: Optional[GatewayMetrics] = None


def get_metrics() -> GatewayMetrics:
    """Get or create the global metrics instance."""
    global _metrics
    if _metrics is None:
        _metrics = GatewayMetrics()
    return _metrics


def reset_metrics() -> None:
    """Reset the global metrics instance (for testing)."""
    global _metrics
    _metrics = None
