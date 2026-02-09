"""Shared infrastructure for Hivemind modules."""

from .auth import (
    extract_auth_url,
    handle_auth,
    is_auth_required,
    open_auth_terminal,
    open_auth_url,
    should_auto_open_auth,
)
from .errors import (
    AuthError,
    BackendError,
    ConfigError,
    HivemindError,
    KnowledgeError,
    ProviderError,
    RateLimitError,
    TimeoutError,
)
from .logging import get_logger, setup_logging
from .paths import (
    data_dir,
    default_gateway_db_path,
    default_performance_db_path,
    project_root,
)
from .tokens import estimate_input_output_tokens, estimate_tokens

__all__ = [
    "AuthError",
    "BackendError",
    "ConfigError",
    "HivemindError",
    "KnowledgeError",
    "ProviderError",
    "RateLimitError",
    "TimeoutError",
    "extract_auth_url",
    "get_logger",
    "handle_auth",
    "is_auth_required",
    "open_auth_terminal",
    "open_auth_url",
    "should_auto_open_auth",
    "setup_logging",
    "project_root",
    "data_dir",
    "default_gateway_db_path",
    "default_performance_db_path",
    "estimate_input_output_tokens",
    "estimate_tokens",
]
