"""
Retry Policy System for CCB

Provides automatic retry with exponential backoff and provider fallback chains.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, List, Tuple, Callable, Any
from enum import Enum
import time
import random


HANDLED_EXCEPTIONS = (Exception,)


class RetryReason(Enum):
    """Reasons for retry."""
    TIMEOUT = "timeout"
    FAILED = "failed"
    UNAVAILABLE = "unavailable"
    RATE_LIMITED = "rate_limited"
    ERROR = "error"


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""
    # Maximum number of retry attempts
    max_attempts: int = 3
    # Base backoff time in seconds
    backoff_base_s: float = 1.0
    # Maximum backoff time in seconds
    backoff_max_s: float = 30.0
    # Backoff multiplier (exponential factor)
    backoff_multiplier: float = 2.0
    # Add jitter to backoff (0.0 to 1.0)
    jitter: float = 0.1
    # Status codes/reasons that should trigger retry
    retry_on: List[str] = field(default_factory=lambda: ["failed", "timeout", "unavailable"])
    # Fallback provider chain
    fallback_chain: List[str] = field(default_factory=list)
    # Whether to use fallback providers
    use_fallback: bool = True


@dataclass
class RetryAttempt:
    """Record of a single retry attempt."""
    attempt_number: int
    provider: str
    success: bool
    latency_ms: float
    error: Optional[str] = None
    reason: Optional[RetryReason] = None


@dataclass
class RetryResult:
    """Result of retry execution."""
    success: bool
    final_provider: str
    total_attempts: int
    attempts: List[RetryAttempt]
    result: Optional[str] = None
    error: Optional[str] = None
    total_latency_ms: float = 0.0


class RetryExecutor:
    """
    Executes operations with automatic retry and fallback.

    Supports exponential backoff with jitter and provider fallback chains.
    """

    # Default fallback chains for providers
    DEFAULT_FALLBACK_CHAINS = {
        "claude": ["gemini", "codex"],
        "gemini": ["claude", "codex"],
        "codex": ["claude", "gemini"],
        "opencode": ["claude", "codex"],
        "droid": ["claude", "codex"],
        "iflow": ["claude", "gemini"],
        "kimi": ["claude", "qwen"],
        "qwen": ["claude", "kimi"],
    }

    def __init__(self, config: Optional[RetryConfig] = None):
        """
        Initialize the retry executor.

        Args:
            config: Retry configuration (uses defaults if not provided)
        """
        self.config = config or RetryConfig()

    def calculate_backoff(self, attempt: int) -> float:
        """
        Calculate backoff time for a given attempt.

        Uses exponential backoff with optional jitter.

        Args:
            attempt: The attempt number (0-indexed)

        Returns:
            Backoff time in seconds
        """
        # Exponential backoff
        backoff = self.config.backoff_base_s * (self.config.backoff_multiplier ** attempt)

        # Cap at maximum
        backoff = min(backoff, self.config.backoff_max_s)

        # Add jitter
        if self.config.jitter > 0:
            jitter_range = backoff * self.config.jitter
            backoff += random.uniform(-jitter_range, jitter_range)

        return max(0, backoff)

    def should_retry(self, error: Optional[str], reason: Optional[RetryReason], attempt: int) -> bool:
        """
        Determine if a retry should be attempted.

        Args:
            error: Error message from the failed attempt
            reason: Reason for failure
            attempt: Current attempt number (0-indexed)

        Returns:
            True if should retry, False otherwise
        """
        # Check if we've exceeded max attempts
        if attempt >= self.config.max_attempts - 1:
            return False

        # Check if the reason is retryable
        if reason:
            return reason.value in self.config.retry_on

        # Check error message for retryable patterns
        if error:
            error_lower = error.lower()
            retryable_patterns = [
                "timeout", "timed out",
                "connection", "network",
                "unavailable", "not available",
                "rate limit", "too many requests",
                "temporary", "transient",
            ]
            return any(pattern in error_lower for pattern in retryable_patterns)

        return False

    def get_fallback_provider(
        self,
        original_provider: str,
        failed_providers: List[str],
    ) -> Optional[str]:
        """
        Get the next fallback provider.

        Args:
            original_provider: The original provider that was tried
            failed_providers: List of providers that have already failed

        Returns:
            Next fallback provider or None if no fallbacks available
        """
        if not self.config.use_fallback:
            return None

        # Get fallback chain for this provider
        chain = self.config.fallback_chain
        if not chain:
            chain = self.DEFAULT_FALLBACK_CHAINS.get(original_provider, [])

        # Find first provider not in failed list
        for provider in chain:
            if provider not in failed_providers:
                return provider

        return None

    def execute_with_retry(
        self,
        execute_fn: Callable[[str], Tuple[bool, Optional[str], Optional[str]]],
        provider: str,
        on_retry: Optional[Callable[[RetryAttempt], None]] = None,
    ) -> RetryResult:
        """
        Execute a function with automatic retry.

        Args:
            execute_fn: Function to execute. Takes provider name, returns (success, result, error)
            provider: Initial provider to use
            on_retry: Optional callback called before each retry

        Returns:
            RetryResult with execution details
        """
        attempts: List[RetryAttempt] = []
        failed_providers: List[str] = []
        current_provider = provider
        total_start = time.time()

        for attempt_num in range(self.config.max_attempts):
            # Execute the function
            start_time = time.time()
            try:
                success, result, error = execute_fn(current_provider)
                latency_ms = (time.time() - start_time) * 1000

                # Determine retry reason
                reason = None
                if not success:
                    if error and "timeout" in error.lower():
                        reason = RetryReason.TIMEOUT
                    elif error and "unavailable" in error.lower():
                        reason = RetryReason.UNAVAILABLE
                    elif error and "rate" in error.lower():
                        reason = RetryReason.RATE_LIMITED
                    else:
                        reason = RetryReason.FAILED

                attempt = RetryAttempt(
                    attempt_number=attempt_num + 1,
                    provider=current_provider,
                    success=success,
                    latency_ms=latency_ms,
                    error=error,
                    reason=reason,
                )
                attempts.append(attempt)

                if success:
                    return RetryResult(
                        success=True,
                        final_provider=current_provider,
                        total_attempts=len(attempts),
                        attempts=attempts,
                        result=result,
                        total_latency_ms=(time.time() - total_start) * 1000,
                    )

                # Check if we should retry
                if not self.should_retry(error, reason, attempt_num):
                    break

                # Try fallback provider
                failed_providers.append(current_provider)
                fallback = self.get_fallback_provider(provider, failed_providers)
                if fallback:
                    current_provider = fallback

                # Calculate and apply backoff
                backoff = self.calculate_backoff(attempt_num)
                if backoff > 0:
                    time.sleep(backoff)

                # Call retry callback
                if on_retry:
                    on_retry(attempt)

            except HANDLED_EXCEPTIONS as e:
                latency_ms = (time.time() - start_time) * 1000
                attempt = RetryAttempt(
                    attempt_number=attempt_num + 1,
                    provider=current_provider,
                    success=False,
                    latency_ms=latency_ms,
                    error=str(e),
                    reason=RetryReason.ERROR,
                )
                attempts.append(attempt)

                if not self.should_retry(str(e), RetryReason.ERROR, attempt_num):
                    break

                # Try fallback
                failed_providers.append(current_provider)
                fallback = self.get_fallback_provider(provider, failed_providers)
                if fallback:
                    current_provider = fallback

                backoff = self.calculate_backoff(attempt_num)
                if backoff > 0:
                    time.sleep(backoff)

                if on_retry:
                    on_retry(attempt)

        # All attempts failed
        last_attempt = attempts[-1] if attempts else None
        return RetryResult(
            success=False,
            final_provider=current_provider,
            total_attempts=len(attempts),
            attempts=attempts,
            error=last_attempt.error if last_attempt else "No attempts made",
            total_latency_ms=(time.time() - total_start) * 1000,
        )

    def execute_simple(
        self,
        execute_fn: Callable[[], bool],
        on_retry: Optional[Callable[[int, float], None]] = None,
    ) -> Tuple[bool, int]:
        """
        Simple retry execution without provider fallback.

        Args:
            execute_fn: Function to execute, returns True on success
            on_retry: Optional callback(attempt_num, backoff_s) called before retry

        Returns:
            Tuple of (success, total_attempts)
        """
        for attempt in range(self.config.max_attempts):
            try:
                if execute_fn():
                    return True, attempt + 1
            except HANDLED_EXCEPTIONS:
                pass

            if attempt < self.config.max_attempts - 1:
                backoff = self.calculate_backoff(attempt)
                if on_retry:
                    on_retry(attempt + 1, backoff)
                if backoff > 0:
                    time.sleep(backoff)

        return False, self.config.max_attempts


def create_retry_config_from_dict(config_dict: dict) -> RetryConfig:
    """
    Create RetryConfig from a dictionary (e.g., from YAML config).

    Args:
        config_dict: Configuration dictionary

    Returns:
        RetryConfig instance
    """
    return RetryConfig(
        max_attempts=config_dict.get("max_attempts", 3),
        backoff_base_s=config_dict.get("backoff_base_s", 1.0),
        backoff_max_s=config_dict.get("backoff_max_s", 30.0),
        backoff_multiplier=config_dict.get("backoff_multiplier", 2.0),
        jitter=config_dict.get("jitter", 0.1),
        retry_on=config_dict.get("retry_on", ["failed", "timeout", "unavailable"]),
        fallback_chain=config_dict.get("fallback_chain", []),
        use_fallback=config_dict.get("use_fallback", True),
    )
