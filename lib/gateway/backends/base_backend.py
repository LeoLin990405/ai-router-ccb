"""
Base Backend Abstract Class.

Defines the interface that all backend implementations must follow.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, Dict, Any
import time

from ..models import GatewayRequest, ProviderStatus
from ..gateway_config import ProviderConfig


@dataclass
class BackendResult:
    """Result from a backend execution."""
    success: bool
    response: Optional[str] = None
    error: Optional[str] = None
    latency_ms: float = 0.0
    tokens_used: Optional[int] = None
    metadata: Optional[Dict[str, Any]] = None
    # Extended output fields for monitoring
    thinking: Optional[str] = None  # Extracted thinking/reasoning chain
    raw_output: Optional[str] = None  # Full raw CLI output

    @classmethod
    def ok(
        cls,
        response: str,
        latency_ms: float = 0.0,
        tokens_used: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
        thinking: Optional[str] = None,
        raw_output: Optional[str] = None,
    ) -> "BackendResult":
        """Create a successful result."""
        return cls(
            success=True,
            response=response,
            latency_ms=latency_ms,
            tokens_used=tokens_used,
            metadata=metadata,
            thinking=thinking,
            raw_output=raw_output,
        )

    @classmethod
    def fail(
        cls,
        error: str,
        latency_ms: float = 0.0,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> "BackendResult":
        """Create a failed result."""
        return cls(
            success=False,
            error=error,
            latency_ms=latency_ms,
            metadata=metadata,
        )


class BaseBackend(ABC):
    """
    Abstract base class for provider backends.

    All backend implementations must inherit from this class and
    implement the required methods.
    """

    def __init__(self, config: ProviderConfig):
        """
        Initialize the backend.

        Args:
            config: Provider configuration
        """
        self.config = config
        self.name = config.name
        self._status = ProviderStatus.UNKNOWN
        self._last_check: Optional[float] = None
        self._last_error: Optional[str] = None

    @property
    def status(self) -> ProviderStatus:
        """Get current provider status."""
        return self._status

    @abstractmethod
    async def execute(self, request: GatewayRequest) -> BackendResult:
        """
        Execute a request against the provider.

        Args:
            request: The request to execute

        Returns:
            BackendResult with response or error
        """
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """
        Check if the provider is healthy.

        Returns:
            True if healthy, False otherwise
        """
        pass

    async def check_health(self) -> ProviderStatus:
        """
        Perform health check and update status.

        Returns:
            Current provider status
        """
        try:
            start = time.time()
            healthy = await self.health_check()
            latency = (time.time() - start) * 1000

            self._last_check = time.time()

            if healthy:
                self._status = ProviderStatus.HEALTHY
                self._last_error = None
            else:
                self._status = ProviderStatus.UNAVAILABLE

            return self._status

        except Exception as e:
            self._status = ProviderStatus.UNAVAILABLE
            self._last_error = str(e)
            self._last_check = time.time()
            return self._status

    def get_status_info(self) -> Dict[str, Any]:
        """Get detailed status information."""
        return {
            "name": self.name,
            "status": self._status.value,
            "last_check": self._last_check,
            "last_error": self._last_error,
            "config": {
                "timeout_s": self.config.timeout_s,
                "enabled": self.config.enabled,
            },
        }

    async def shutdown(self) -> None:
        """
        Shutdown the backend gracefully.

        Override in subclasses if cleanup is needed.
        """
        pass
