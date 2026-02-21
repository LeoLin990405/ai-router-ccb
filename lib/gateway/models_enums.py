"""Enum definitions for gateway/domain models."""
from __future__ import annotations

from enum import Enum


class RequestStatus(Enum):
    """Request lifecycle states."""
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"
    RETRYING = "retrying"  # Request is being retried
    FALLBACK = "fallback"  # Request switched to fallback provider

class ErrorType(Enum):
    """Classification of errors for retry decisions."""
    RETRYABLE_TRANSIENT = "retryable_transient"  # Network errors, timeouts, 5xx
    RETRYABLE_RATE_LIMIT = "retryable_rate_limit"  # 429 rate limit
    NON_RETRYABLE_AUTH = "non_retryable_auth"  # 401, 403 auth errors
    NON_RETRYABLE_CLIENT = "non_retryable_client"  # Other 4xx client errors
    NON_RETRYABLE_PERMANENT = "non_retryable_permanent"  # Permanent failures

class BackendType(Enum):
    """Types of provider backends."""
    HTTP_API = "http_api"      # Direct HTTP API (OpenAI, Anthropic)
    CLI_EXEC = "cli_exec"      # CLI subprocess execution (Codex, Gemini CLI)
    FIFO_PIPE = "fifo_pipe"    # FIFO/named pipe (legacy)
    TERMINAL = "terminal"      # WezTerm terminal (legacy compatibility)

class ProviderStatus(Enum):
    """Provider health status."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"
    UNKNOWN = "unknown"

class AuthStatus(Enum):
    """Provider authentication status."""
    VALID = "valid"              # Auth is valid and working
    EXPIRED = "expired"          # Auth token has expired
    INVALID = "invalid"          # Auth credentials are invalid
    NEEDS_REAUTH = "needs_reauth"  # Requires re-authentication
    UNKNOWN = "unknown"          # Status not yet checked

class DiscussionStatus(Enum):
    """Discussion session lifecycle states."""
    PENDING = "pending"
    ROUND_1 = "round_1"  # Proposal round
    ROUND_2 = "round_2"  # Review round
    ROUND_3 = "round_3"  # Revision round
    SUMMARIZING = "summarizing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class MessageType(Enum):
    """Types of discussion messages."""
    PROPOSAL = "proposal"  # Initial proposal in round 1
    REVIEW = "review"  # Review/feedback in round 2
    REVISION = "revision"  # Revised proposal in round 3
    SUMMARY = "summary"  # Final summary by orchestrator
