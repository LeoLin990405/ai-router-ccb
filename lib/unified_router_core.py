"""Auto-split mixins for UnifiedRouter."""
from __future__ import annotations

import fnmatch
import os
import re
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional

import yaml

from provider_commands import (
    ALL_PROVIDERS,
    PROVIDER_COMMANDS,
    PROVIDER_PING_COMMANDS,
    get_ask_command,
    get_ping_command,
)

if TYPE_CHECKING:
    from rate_limiter import RateLimiter

try:
    from .unified_router import (
        ChannelType,
        HANDLED_EXCEPTIONS,
        MagicKeywordMatch,
        ProviderStatus,
        RoutingDecision,
        RoutingRule,
        TaskType,
        _warn,
    )
except ImportError:  # pragma: no cover - script mode
    from unified_router import (
        ChannelType,
        HANDLED_EXCEPTIONS,
        MagicKeywordMatch,
        ProviderStatus,
        RoutingDecision,
        RoutingRule,
        TaskType,
        _warn,
    )


class UnifiedRouterCoreMixin:
    """Mixin methods extracted from UnifiedRouter."""

    def __init__(self, config_path: Optional[str] = None, rate_limiter: Optional["RateLimiter"] = None):
        """
        Initialize the router with optional configuration.

        Args:
            config_path: Path to YAML configuration file
            rate_limiter: Optional rate limiter instance
        """
        self.config: Dict[str, Any] = {}
        self.custom_rules: List[RoutingRule] = []
        self._provider_health: Dict[str, ProviderHealth] = {}
        self._rate_limiter = rate_limiter

        if config_path:
            self._load_config(config_path)
        else:
            # Try default config location
            default_path = Path.home() / ".ccb_config" / "unified-router.yaml"
            if default_path.exists():
                self._load_config(str(default_path))

    def _load_config(self, config_path: str) -> None:
        """Load configuration from YAML file."""
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                self.config = yaml.safe_load(f) or {}

            # Parse routing rules
            for rule_data in self.config.get("routing_rules", []):
                rule = RoutingRule(
                    name=rule_data.get("name", "unnamed"),
                    provider=rule_data.get("provider", "claude"),
                    patterns=rule_data.get("patterns", []),
                    keywords=rule_data.get("keywords", []),
                    priority=rule_data.get("priority", 0),
                )
                self.custom_rules.append(rule)

            # Sort by priority (higher first)
            self.custom_rules.sort(key=lambda r: r.priority, reverse=True)
        except HANDLED_EXCEPTIONS as e:
            _warn(f"Warning: Failed to load config from {config_path}: {e}")

    def route(
        self,
        message: str,
        files: Optional[List[str]] = None,
        preferred_provider: Optional[str] = None,
        enable_magic_keywords: bool = True,
        check_rate_limit: bool = True,
    ) -> RoutingDecision:
        """
        Determine the optimal provider for a given task.

        Args:
            message: The user's message/query
            files: Optional list of file paths involved
            preferred_provider: Optional user-specified provider preference
            enable_magic_keywords: Whether to check for magic keywords (default: True)
            check_rate_limit: Whether to check rate limits (default: True)

        Returns:
            RoutingDecision with provider, channel, and reasoning
        """
        # Check for magic keywords first (if enabled)
        if enable_magic_keywords:
            magic_match = self._detect_magic_keywords(message)
            if magic_match:
                decision = self._handle_magic_keyword(magic_match, message)
                return self._apply_rate_limit_check(decision) if check_rate_limit else decision

        # If user explicitly specified a provider, use it
        if preferred_provider and preferred_provider in ALL_PROVIDERS:
            decision = RoutingDecision(
                provider=preferred_provider,
                channel=ChannelType.CCB_DAEMON,
                fallback=ChannelType.DIRECT_CLI,
                task_type=TaskType.GENERAL,
                reason=f"User specified provider: {preferred_provider}",
                confidence=1.0,
            )
            return self._apply_rate_limit_check(decision) if check_rate_limit else decision

        # Try custom rules first
        custom_match = self._match_custom_rules(message, files)
        if custom_match:
            return self._apply_rate_limit_check(custom_match) if check_rate_limit else custom_match

        # Infer task type from message
        task_type = self._infer_task_type(message)

        # Select provider based on task type and files
        provider = self._select_provider(task_type, files)

        decision = RoutingDecision(
            provider=provider,
            channel=ChannelType.CCB_DAEMON,
            fallback=ChannelType.DIRECT_CLI,
            task_type=task_type,
            reason=f"Task type '{task_type.value}' → {provider}",
            confidence=0.8,
        )
        return self._apply_rate_limit_check(decision) if check_rate_limit else decision

    def _apply_rate_limit_check(self, decision: RoutingDecision) -> RoutingDecision:
        """Apply rate limit check to a routing decision."""
        if not self._rate_limiter:
            return decision

        wait_time = self._rate_limiter.get_wait_time(decision.provider)
        if wait_time > 0:
            decision.rate_limited = True
            decision.wait_time_s = wait_time
            decision.reason += f" (rate limited, wait {wait_time:.1f}s)"

        return decision

    def acquire_rate_limit(self, provider: str, tokens: int = 1, block: bool = False) -> bool:
        """
        Acquire rate limit tokens for a provider.

        Args:
            provider: The provider to acquire tokens for
            tokens: Number of tokens to acquire
            block: Whether to block until tokens are available

        Returns:
            True if tokens were acquired, False if rate limited
        """
        if not self._rate_limiter:
            return True
        return self._rate_limiter.acquire(provider, tokens, block)

    def _match_custom_rules(
        self,
        message: str,
        files: Optional[List[str]] = None,
    ) -> Optional[RoutingDecision]:
        """Check if any custom routing rules match."""
        msg_lower = message.lower()
        # Split message into words for whole-word matching
        import re
        words = set(re.findall(r'\b\w+\b', msg_lower))

        for rule in self.custom_rules:
            # Check keyword match - use word boundary matching for short keywords
            keyword_match = False
            for kw in rule.keywords:
                kw_lower = kw.lower()
                # For short keywords (<=3 chars), require whole word match
                # For longer keywords, allow substring match
                if len(kw_lower) <= 3:
                    if kw_lower in words:
                        keyword_match = True
                        break
                else:
                    if kw_lower in msg_lower:
                        keyword_match = True
                        break

            # Check file pattern match
            pattern_match = False
            if files and rule.patterns:
                for f in files:
                    for pattern in rule.patterns:
                        # Handle ** glob patterns more flexibly
                        if '**' in pattern:
                            # Convert ** pattern to regex-like matching
                            # **/api/** should match api/routes.py, src/api/v1/routes.py, etc.
                            simple_pattern = pattern.replace('**/', '').replace('/**', '')
                            if fnmatch.fnmatch(f, simple_pattern) or simple_pattern in f:
                                pattern_match = True
                                break
                        elif fnmatch.fnmatch(f, pattern):
                            pattern_match = True
                            break
                    if pattern_match:
                        break

            if keyword_match or pattern_match:
                match_reason = []
                if keyword_match:
                    match_reason.append("keyword")
                if pattern_match:
                    match_reason.append("file pattern")

                return RoutingDecision(
                    provider=rule.provider,
                    channel=ChannelType.CCB_DAEMON,
                    fallback=ChannelType.DIRECT_CLI,
                    task_type=TaskType.GENERAL,
                    reason=f"Custom rule '{rule.name}' matched ({', '.join(match_reason)})",
                    confidence=0.9,
                )

        return None

    def _infer_task_type(self, message: str) -> TaskType:
        """Infer the task type from the message content."""
        msg_lower = message.lower()

        # Score each task type
        scores: Dict[TaskType, int] = {t: 0 for t in TaskType}

        for task_type, keywords in self.TASK_KEYWORDS.items():
            for keyword in keywords:
                if keyword.lower() in msg_lower:
                    scores[task_type] += 1

        # Find the highest scoring task type
        best_type = max(scores, key=lambda t: scores[t])

        # If no keywords matched, default to GENERAL
        if scores[best_type] == 0:
            return TaskType.GENERAL

        return best_type

    def _select_provider(
        self,
        task_type: TaskType,
        files: Optional[List[str]] = None,
    ) -> str:
        """Select the best provider based on task type and files."""
        # Check file patterns first (more specific)
        if files:
            for f in files:
                for pattern, provider in self.FILE_PATTERN_PROVIDERS.items():
                    if fnmatch.fnmatch(f, pattern):
                        return provider

        # Fall back to task type mapping
        default_provider = self.config.get("default_provider", "claude")
        return self.DEFAULT_PROVIDER_MAP.get(task_type, default_provider)

    def get_provider_command(self, provider: str) -> str:
        """Get the ask command for a provider."""
        return get_ask_command(provider)

    def get_provider_ping_command(self, provider: str) -> str:
        """Get the ping command for a provider."""
        return get_ping_command(provider)

    def format_decision(self, decision: RoutingDecision) -> str:
        """Format a routing decision for display."""
        lines = [
            f"Provider:   {decision.provider}",
            f"Channel:    {decision.channel.value}",
            f"Fallback:   {decision.fallback.value if decision.fallback else 'none'}",
            f"Task Type:  {decision.task_type.value}",
            f"Confidence: {decision.confidence:.0%}",
            f"Reason:     {decision.reason}",
        ]
        return "\n".join(lines)

