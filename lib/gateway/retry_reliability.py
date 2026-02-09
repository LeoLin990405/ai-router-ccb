"""Reliability tracking helpers for gateway retry logic."""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

try:
    from .retry import detect_auth_failure
except ImportError:  # pragma: no cover - script mode
    from retry import detect_auth_failure


@dataclass
class ProviderReliabilityScore:
    """
    Tracks reliability metrics for a provider.

    Used for intelligent fallback decisions based on historical performance.
    """
    provider: str
    success_count: int = 0
    failure_count: int = 0
    timeout_count: int = 0
    auth_failure_count: int = 0
    last_success: Optional[float] = None
    last_failure: Optional[float] = None
    last_auth_failure: Optional[float] = None

    @property
    def total_requests(self) -> int:
        """Total number of requests made to this provider."""
        return self.success_count + self.failure_count + self.timeout_count

    @property
    def reliability_score(self) -> float:
        """
        Calculate reliability score from 0.0 to 1.0.

        Considers:
        - Success rate (70% weight)
        - Auth failure penalty (30% weight)
        """
        if self.total_requests == 0:
            return 1.0  # Assume reliable if no data

        success_rate = self.success_count / self.total_requests

        # Penalize auth failures heavily
        auth_penalty = min(self.auth_failure_count * 0.1, 0.3)

        score = (success_rate * 0.7) + ((1.0 - auth_penalty) * 0.3)
        return max(0.0, min(1.0, score))

    @property
    def is_healthy(self) -> bool:
        """
        Check if provider is considered healthy.

        Unhealthy if:
        - Auth failures >= 3 (needs re-auth)
        - Reliability score < 0.3
        """
        if self.auth_failure_count >= 3:
            return False
        return self.reliability_score >= 0.3

    @property
    def needs_reauth(self) -> bool:
        """Check if provider needs re-authentication."""
        return self.auth_failure_count >= 3

    def record_success(self) -> None:
        """Record a successful request."""
        self.success_count += 1
        self.last_success = time.time()

    def record_failure(self, is_auth_failure: bool = False, is_timeout: bool = False) -> None:
        """Record a failed request."""
        if is_timeout:
            self.timeout_count += 1
        else:
            self.failure_count += 1

        if is_auth_failure:
            self.auth_failure_count += 1
            self.last_auth_failure = time.time()

        self.last_failure = time.time()

    def reset_auth_failures(self) -> None:
        """Reset auth failure count (after re-authentication)."""
        self.auth_failure_count = 0
        self.last_auth_failure = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "provider": self.provider,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "timeout_count": self.timeout_count,
            "auth_failure_count": self.auth_failure_count,
            "total_requests": self.total_requests,
            "reliability_score": self.reliability_score,
            "is_healthy": self.is_healthy,
            "needs_reauth": self.needs_reauth,
            "last_success": self.last_success,
            "last_failure": self.last_failure,
        }


class ReliabilityTracker:
    """
    Tracks reliability scores for all providers.

    Used for intelligent provider selection and fallback decisions.
    """

    def __init__(self):
        self._scores: Dict[str, ProviderReliabilityScore] = {}
        self._lock: Optional[asyncio.Lock] = None

    def _ensure_lock(self) -> asyncio.Lock:
        """Lazily create lock when an event loop is available."""
        if self._lock is None:
            self._lock = asyncio.Lock()
        return self._lock

    def get_score(self, provider: str) -> ProviderReliabilityScore:
        """Get reliability score for a provider."""
        if provider not in self._scores:
            self._scores[provider] = ProviderReliabilityScore(provider=provider)
        return self._scores[provider]

    async def record_success(self, provider: str) -> None:
        """Record a successful request."""
        async with self._ensure_lock():
            self.get_score(provider).record_success()

    async def record_failure(
        self,
        provider: str,
        error: str,
        is_timeout: bool = False,
    ) -> None:
        """Record a failed request."""
        async with self._ensure_lock():
            is_auth = detect_auth_failure(error)
            self.get_score(provider).record_failure(
                is_auth_failure=is_auth,
                is_timeout=is_timeout,
            )

    async def reset_auth(self, provider: str) -> None:
        """Reset auth failures for a provider after re-auth."""
        async with self._ensure_lock():
            self.get_score(provider).reset_auth_failures()

    def get_healthy_providers(self, providers: List[str]) -> List[str]:
        """Get list of healthy providers from the given list."""
        return [p for p in providers if self.get_score(p).is_healthy]

    def get_best_fallback(
        self,
        primary: str,
        fallback_chain: List[str],
    ) -> Optional[str]:
        """
        Get the best fallback provider based on reliability.

        Returns the fallback with highest reliability score that is healthy.
        """
        candidates = [
            (p, self.get_score(p))
            for p in fallback_chain
            if p != primary and self.get_score(p).is_healthy
        ]

        if not candidates:
            return None

        # Sort by reliability score descending
        candidates.sort(key=lambda x: x[1].reliability_score, reverse=True)
        return candidates[0][0]

    def get_all_scores(self) -> Dict[str, Dict[str, Any]]:
        """Get all reliability scores as dictionary."""
        return {p: s.to_dict() for p, s in self._scores.items()}
