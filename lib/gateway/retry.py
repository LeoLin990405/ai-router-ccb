"""
Retry and Fallback Logic for CCB Gateway.

Provides automatic retry with exponential backoff and provider fallback chains.
"""
from __future__ import annotations

import asyncio
import random
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Dict, List, Callable, Any, TYPE_CHECKING

from lib.common.logging import get_logger

if TYPE_CHECKING:
    from .backends.base_backend import BackendResult
    from .models import GatewayRequest


logger = get_logger("gateway.retry")


class ErrorType(Enum):
    """Classification of errors for retry decisions."""
    RETRYABLE_TRANSIENT = "retryable_transient"  # Network errors, timeouts, 5xx
    RETRYABLE_RATE_LIMIT = "retryable_rate_limit"  # 429 rate limit
    NON_RETRYABLE_AUTH = "non_retryable_auth"  # 401, 403 auth errors
    NON_RETRYABLE_CLIENT = "non_retryable_client"  # Other 4xx client errors
    NON_RETRYABLE_PERMANENT = "non_retryable_permanent"  # Permanent failures


# Rate limit handling defaults
GEMINI_RATE_LIMIT_MIN_TIMEOUT_S = 600.0


# Default fallback chains for providers
DEFAULT_FALLBACK_CHAINS: Dict[str, List[str]] = {
    "claude": ["deepseek", "gemini"],
    "gemini": ["claude", "deepseek"],
    "deepseek": ["claude", "qwen"],
    "codex": ["opencode", "claude"],
    "opencode": ["codex", "claude"],
    "kimi": ["qwen", "deepseek"],
    "qwen": ["kimi", "deepseek"],
    "iflow": ["claude", "deepseek"],
}

# Default provider groups for parallel queries
DEFAULT_PROVIDER_GROUPS: Dict[str, List[str]] = {
    "all": ["claude", "gemini", "deepseek", "codex"],
    "fast": ["claude", "deepseek"],
    "reasoning": ["deepseek", "claude"],
    "coding": ["codex", "claude", "opencode"],
    "chinese": ["deepseek", "kimi", "qwen"],
}


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""
    enabled: bool = True
    max_retries: int = 3
    base_delay_s: float = 1.0
    max_delay_s: float = 30.0
    exponential_base: float = 2.0
    jitter: bool = True
    # Fallback configuration
    fallback_enabled: bool = True
    fallback_chains: Dict[str, List[str]] = field(default_factory=lambda: DEFAULT_FALLBACK_CHAINS.copy())
    # Provider groups for parallel queries
    provider_groups: Dict[str, List[str]] = field(default_factory=lambda: DEFAULT_PROVIDER_GROUPS.copy())

    def get_delay(self, attempt: int) -> float:
        """Calculate delay for a given retry attempt."""
        delay = self.base_delay_s * (self.exponential_base ** attempt)
        delay = min(delay, self.max_delay_s)
        if self.jitter:
            delay = delay * (0.5 + random.random())
        return delay

    def get_fallbacks(self, provider: str) -> List[str]:
        """Get fallback providers for a given provider."""
        return self.fallback_chains.get(provider, [])

    def get_provider_group(self, group_name: str) -> List[str]:
        """Get providers in a named group."""
        # Remove @ prefix if present
        name = group_name.lstrip("@")
        return self.provider_groups.get(name, [])


def classify_error(error: str, status_code: Optional[int] = None) -> ErrorType:
    """
    Classify an error to determine retry behavior.

    Args:
        error: Error message string
        status_code: HTTP status code if available

    Returns:
        ErrorType classification
    """
    error_lower = error.lower()

    # Check status code first
    if status_code:
        if status_code == 429:
            return ErrorType.RETRYABLE_RATE_LIMIT
        if status_code in (401, 403):
            return ErrorType.NON_RETRYABLE_AUTH
        if 400 <= status_code < 500:
            return ErrorType.NON_RETRYABLE_CLIENT
        if status_code >= 500:
            return ErrorType.RETRYABLE_TRANSIENT

    # Check error message patterns
    # Rate limit patterns
    rate_limit_patterns = [
        "rate limit",
        "too many requests",
        "quota exceeded",
        "throttl",
    ]
    if any(p in error_lower for p in rate_limit_patterns):
        return ErrorType.RETRYABLE_RATE_LIMIT

    # Auth patterns
    auth_patterns = [
        "unauthorized",
        "authentication",
        "invalid api key",
        "api key not found",
        "forbidden",
        "access denied",
    ]
    if any(p in error_lower for p in auth_patterns):
        return ErrorType.NON_RETRYABLE_AUTH

    # Transient/retryable patterns
    transient_patterns = [
        "timeout",
        "timed out",
        "connection",
        "network",
        "temporary",
        "unavailable",
        "overloaded",
        "server error",
        "internal error",
        "bad gateway",
        "service unavailable",
    ]
    if any(p in error_lower for p in transient_patterns):
        return ErrorType.RETRYABLE_TRANSIENT

    # Client error patterns
    client_patterns = [
        "invalid",
        "malformed",
        "bad request",
        "not found",
        "unsupported",
    ]
    if any(p in error_lower for p in client_patterns):
        return ErrorType.NON_RETRYABLE_CLIENT

    # Default to transient (retryable) for unknown errors
    return ErrorType.RETRYABLE_TRANSIENT


def extract_status_code(error: str) -> Optional[int]:
    """Extract HTTP status code from error message."""
    import re
    # Match patterns like "API error 429:", "status 500", "HTTP 503"
    patterns = [
        r"error\s+(\d{3})",
        r"status\s+(\d{3})",
        r"http\s+(\d{3})",
        r"\b(\d{3})\b.*error",
    ]
    for pattern in patterns:
        match = re.search(pattern, error.lower())
        if match:
            code = int(match.group(1))
            if 100 <= code < 600:
                return code
    return None


@dataclass
class RetryState:
    """Tracks state during retry attempts."""
    original_provider: str
    current_provider: str
    attempt: int = 0
    total_attempts: int = 0
    fallback_index: int = -1
    errors: List[Dict[str, Any]] = field(default_factory=list)
    start_time: float = field(default_factory=time.time)

    def record_error(self, provider: str, error: str, error_type: ErrorType) -> None:
        """Record an error for tracking."""
        self.errors.append({
            "provider": provider,
            "error": error,
            "error_type": error_type.value,
            "attempt": self.attempt,
            "timestamp": time.time(),
        })

    def get_summary(self) -> Dict[str, Any]:
        """Get summary of retry attempts."""
        return {
            "original_provider": self.original_provider,
            "final_provider": self.current_provider,
            "total_attempts": self.total_attempts,
            "fallback_used": self.fallback_index >= 0,
            "errors": self.errors,
            "total_time_ms": (time.time() - self.start_time) * 1000,
        }


class RetryExecutor:
    """
    Executes requests with retry and fallback logic.

    Usage:
        executor = RetryExecutor(config, backends)
        result, state = await executor.execute_with_retry(request)
    """

    def __init__(
        self,
        config: RetryConfig,
        backends: Dict[str, Any],
        available_providers: Optional[List[str]] = None,
    ):
        """
        Initialize the retry executor.

        Args:
            config: Retry configuration
            backends: Dict of provider name -> backend instance
            available_providers: List of available provider names (defaults to backends keys)
        """
        self.config = config
        self.backends = backends
        self.available_providers = available_providers or list(backends.keys())

    def _ensure_min_timeout(self, request: "GatewayRequest", min_timeout_s: float) -> None:
        """Ensure request timeout is at least min_timeout_s."""
        if request.timeout_s < min_timeout_s:
            request.timeout_s = min_timeout_s

    async def execute_with_retry(
        self,
        request: "GatewayRequest",
        execute_func: Optional[Callable] = None,
    ) -> tuple["BackendResult", RetryState]:
        """
        Execute a request with retry and fallback logic.

        Args:
            request: The request to execute
            execute_func: Optional custom execution function

        Returns:
            Tuple of (result, retry_state)
        """
        from .backends.base_backend import BackendResult

        state = RetryState(
            original_provider=request.provider,
            current_provider=request.provider,
        )

        if not self.config.enabled:
            # Retry disabled, execute once
            result = await self._execute_once(request, execute_func)
            state.total_attempts = 1
            return result, state

        # Get fallback chain
        fallbacks = self.config.get_fallbacks(request.provider)
        fallbacks = [p for p in fallbacks if p in self.available_providers]

        while True:
            # Execute with current provider
            logger.debug(
                "Executing provider=%s fallback_index=%s",
                request.provider,
                state.fallback_index,
            )
            result = await self._execute_with_retries(request, state, execute_func)
            logger.debug(
                "Provider %s result success=%s error=%s",
                request.provider,
                result.success,
                result.error[:100] if result.error else "None",
            )

            if result.success:
                return result, state

            # Check if we should try fallback
            if not self.config.fallback_enabled:
                logger.debug("Fallback disabled, returning failure")
                return result, state

            # Try next fallback
            state.fallback_index += 1
            if state.fallback_index >= len(fallbacks):
                # No more fallbacks
                logger.debug("No more fallbacks available (tried %s fallbacks)", state.fallback_index)
                return result, state

            # Switch to fallback provider
            next_provider = fallbacks[state.fallback_index]
            logger.debug("Switching to fallback provider: %s", next_provider)
            state.current_provider = next_provider
            request.provider = next_provider
            state.attempt = 0  # Reset attempt counter for new provider

    async def _execute_with_retries(
        self,
        request: "GatewayRequest",
        state: RetryState,
        execute_func: Optional[Callable],
    ) -> "BackendResult":
        """Execute request with retries for current provider."""
        from .backends.base_backend import BackendResult

        last_result: Optional[BackendResult] = None

        while state.attempt <= self.config.max_retries:
            state.total_attempts += 1

            # Execute
            result = await self._execute_once(request, execute_func)

            if result.success:
                return result

            last_result = result

            # Classify error
            status_code = extract_status_code(result.error or "")
            error_type = classify_error(result.error or "", status_code)
            state.record_error(state.current_provider, result.error or "", error_type)

            # Check if retryable
            if error_type in (ErrorType.NON_RETRYABLE_AUTH, ErrorType.NON_RETRYABLE_CLIENT, ErrorType.NON_RETRYABLE_PERMANENT):
                # Don't retry non-retryable errors
                break

            state.attempt += 1

            if state.attempt > self.config.max_retries:
                break

            # Calculate delay
            delay = self.config.get_delay(state.attempt - 1)

            # For rate limits, use longer delay
            if error_type == ErrorType.RETRYABLE_RATE_LIMIT:
                delay = max(delay, 5.0)  # At least 5 seconds for rate limits
                if request.provider == "gemini":
                    self._ensure_min_timeout(request, GEMINI_RATE_LIMIT_MIN_TIMEOUT_S)

            await asyncio.sleep(delay)

        return last_result or BackendResult.fail("No result from execution")

    async def _execute_once(
        self,
        request: "GatewayRequest",
        execute_func: Optional[Callable],
    ) -> "BackendResult":
        """Execute request once."""
        from .backends.base_backend import BackendResult

        provider = request.provider
        backend = self.backends.get(provider)

        if not backend:
            return BackendResult.fail(f"No backend available for provider: {provider}")

        try:
            if execute_func:
                return await execute_func(request, backend)
            else:
                return await backend.execute(request)
        except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError) as e:
            return BackendResult.fail(str(e))


def should_retry(error_type: ErrorType) -> bool:
    """Check if an error type should be retried."""
    return error_type in (ErrorType.RETRYABLE_TRANSIENT, ErrorType.RETRYABLE_RATE_LIMIT)


def should_fallback(error_type: ErrorType) -> bool:
    """Check if an error type should trigger fallback."""
    # Fallback on any failure except auth errors (which would fail on fallback too)
    return error_type != ErrorType.NON_RETRYABLE_AUTH


def detect_auth_failure(error: str, status_code: Optional[int] = None) -> bool:
    """
    Detect if an error indicates an authentication failure.

    Args:
        error: Error message string
        status_code: HTTP status code if available

    Returns:
        True if the error indicates auth failure
    """
    error_type = classify_error(error, status_code)
    return error_type == ErrorType.NON_RETRYABLE_AUTH

try:
    from .retry_reliability import ProviderReliabilityScore, ReliabilityTracker
except ImportError:  # pragma: no cover - script mode
    from retry_reliability import ProviderReliabilityScore, ReliabilityTracker

