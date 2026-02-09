"""Error hierarchy for Hivemind."""

from __future__ import annotations


class HivemindError(Exception):
    """Base exception for all Hivemind errors."""


class ProviderError(HivemindError):
    """Provider-related error."""

    def __init__(self, provider: str, message: str, retryable: bool = False):
        self.provider = provider
        self.retryable = retryable
        super().__init__(f"[{provider}] {message}")


class AuthError(ProviderError):
    """Authentication failed and should not be retried immediately."""

    def __init__(self, provider: str, message: str = "authentication failed"):
        super().__init__(provider, message, retryable=False)


class TimeoutError(ProviderError):
    """Provider timeout that is usually retryable."""

    def __init__(self, provider: str, timeout_s: float):
        super().__init__(provider, f"timeout after {timeout_s}s", retryable=True)


class RateLimitError(ProviderError):
    """Rate-limited error that is retryable after a delay."""

    def __init__(self, provider: str, retry_after: float = 0):
        self.retry_after = retry_after
        super().__init__(provider, "rate limited", retryable=True)


class BackendError(HivemindError):
    """Backend execution error."""


class ConfigError(HivemindError):
    """Configuration error."""


class KnowledgeError(HivemindError):
    """Knowledge subsystem error."""
