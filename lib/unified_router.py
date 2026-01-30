"""
Unified Router Engine - Nexus CLI + CCB Integration

Provides intelligent task routing to select the optimal AI provider
based on task type, file patterns, and keywords.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List, Dict, Any, TYPE_CHECKING
from pathlib import Path
import re
import fnmatch
import os
import yaml

if TYPE_CHECKING:
    from rate_limiter import RateLimiter

# Import unified provider commands
from provider_commands import (
    ALL_PROVIDERS,
    PROVIDER_COMMANDS,
    PROVIDER_PING_COMMANDS,
    get_ask_command,
    get_ping_command,
)


class TaskType(Enum):
    """Task categories for routing decisions."""
    QUICK_QUERY = "quick_query"
    CODE_REVIEW = "code_review"
    FRONTEND = "frontend"
    BACKEND = "backend"
    ARCHITECTURE = "architecture"
    REASONING = "reasoning"
    GENERAL = "general"


class ChannelType(Enum):
    """Communication channels for AI providers."""
    CCB_DAEMON = "ccb_daemon"
    DIRECT_CLI = "direct_cli"


class ProviderStatus(Enum):
    """Health status of a provider."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"
    UNKNOWN = "unknown"


@dataclass
class RoutingDecision:
    """Result of a routing decision."""
    provider: str
    channel: ChannelType
    fallback: Optional[ChannelType]
    task_type: TaskType
    reason: str
    confidence: float = 1.0
    rate_limited: bool = False
    wait_time_s: float = 0.0


@dataclass
class ProviderHealth:
    """Health status of a provider."""
    provider: str
    status: ProviderStatus
    latency_ms: Optional[float] = None
    last_check: Optional[float] = None
    error: Optional[str] = None


@dataclass
class RoutingRule:
    """A single routing rule from configuration."""
    name: str
    provider: str
    patterns: List[str] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)
    priority: int = 0


@dataclass
class MagicKeywordMatch:
    """Result of magic keyword detection."""
    keyword: str
    action: str
    provider: Optional[str] = None
    providers: Optional[List[str]] = None
    features: Optional[List[str]] = None
    description: str = ""


class UnifiedRouter:
    """
    Unified routing engine that combines Nexus CLI's intelligent routing
    with CCB's multi-provider infrastructure.
    """

    # Default task keywords for inference
    TASK_KEYWORDS: Dict[TaskType, List[str]] = {
        TaskType.QUICK_QUERY: [
            "what", "how", "why", "explain", "describe", "tell",
            "什么", "怎么", "为什么", "解释", "说明"
        ],
        TaskType.CODE_REVIEW: [
            "review", "check", "audit", "inspect", "examine", "analyze code",
            "审查", "检查", "审计", "代码审查"
        ],
        TaskType.FRONTEND: [
            "react", "vue", "angular", "svelte", "component", "ui", "ux",
            "css", "style", "layout", "responsive", "animation",
            "前端", "组件", "界面", "样式"
        ],
        TaskType.BACKEND: [
            "api", "endpoint", "database", "server", "rest", "graphql",
            "authentication", "authorization", "middleware", "route",
            "后端", "接口", "数据库", "服务器"
        ],
        TaskType.ARCHITECTURE: [
            "design", "architect", "plan", "structure", "pattern",
            "microservice", "monolith", "scalability", "system",
            "设计", "架构", "规划", "系统设计"
        ],
        TaskType.REASONING: [
            "analyze", "reason", "think", "deduce", "infer", "complex",
            "algorithm", "optimize", "prove", "mathematical",
            "分析", "推理", "思考", "算法", "优化", "深度"
        ],
    }

    # Default provider mapping by task type
    DEFAULT_PROVIDER_MAP: Dict[TaskType, str] = {
        TaskType.QUICK_QUERY: "claude",
        TaskType.CODE_REVIEW: "gemini",
        TaskType.FRONTEND: "gemini",
        TaskType.BACKEND: "codex",
        TaskType.ARCHITECTURE: "claude",
        TaskType.REASONING: "deepseek",
        TaskType.GENERAL: "claude",
    }

    # File pattern to provider mapping
    FILE_PATTERN_PROVIDERS: Dict[str, str] = {
        # Frontend patterns
        "**/*.tsx": "gemini",
        "**/*.jsx": "gemini",
        "**/*.vue": "gemini",
        "**/*.svelte": "gemini",
        "**/components/**": "gemini",
        "**/pages/**": "gemini",
        "**/styles/**": "gemini",
        "**/*.css": "gemini",
        "**/*.scss": "gemini",
        # Backend patterns
        "**/api/**": "codex",
        "**/routes/**": "codex",
        "**/controllers/**": "codex",
        "**/services/**": "codex",
        "**/models/**": "codex",
        "**/*.go": "codex",
        "**/*.rs": "codex",
    }

    # Use unified provider commands from provider_commands module
    # ALL_PROVIDERS, PROVIDER_COMMANDS, PROVIDER_PING_COMMANDS are imported

    # Magic keywords for enhanced routing behavior
    # These keywords trigger special actions when detected in messages
    MAGIC_KEYWORDS: Dict[str, Dict[str, Any]] = {
        "@search": {
            "action": "web_search",
            "provider": "gemini",
            "description": "Trigger web search",
        },
        "@docs": {
            "action": "context7_lookup",
            "provider": "claude",
            "description": "Query Context7 documentation",
        },
        "@deep": {
            "action": "deep_reasoning",
            "provider": "deepseek",
            "description": "Force deep reasoning mode",
        },
        "@review": {
            "action": "code_review",
            "provider": "gemini",
            "description": "Force code review mode",
        },
        "@all": {
            "action": "multi_provider",
            "providers": ["claude", "gemini", "codex"],
            "description": "Query multiple providers",
        },
        "smartroute": {
            "action": "full_auto",
            "features": ["auto_retry", "aggregate_results", "parallel_execution"],
            "description": "Enable all smart features",
        },
    }

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
        except Exception as e:
            print(f"Warning: Failed to load config from {config_path}: {e}")

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

    def _detect_magic_keywords(self, message: str) -> Optional[MagicKeywordMatch]:
        """
        Detect magic keywords in the message.

        Args:
            message: The user's message

        Returns:
            MagicKeywordMatch if a keyword is found, None otherwise
        """
        msg_lower = message.lower()

        # Check configured magic keywords first
        magic_config = self.config.get("magic_keywords", {})
        if magic_config.get("enabled", True):
            for kw_config in magic_config.get("keywords", []):
                keyword = kw_config.get("keyword", "")
                if keyword and keyword.lower() in msg_lower:
                    return MagicKeywordMatch(
                        keyword=keyword,
                        action=kw_config.get("action", ""),
                        provider=kw_config.get("provider"),
                        providers=kw_config.get("providers"),
                        features=kw_config.get("features"),
                        description=kw_config.get("description", ""),
                    )

        # Fall back to built-in magic keywords
        for keyword, config in self.MAGIC_KEYWORDS.items():
            if keyword.lower() in msg_lower:
                return MagicKeywordMatch(
                    keyword=keyword,
                    action=config.get("action", ""),
                    provider=config.get("provider"),
                    providers=config.get("providers"),
                    features=config.get("features"),
                    description=config.get("description", ""),
                )

        return None

    def _handle_magic_keyword(
        self,
        match: MagicKeywordMatch,
        message: str,
    ) -> RoutingDecision:
        """
        Handle a magic keyword match and return appropriate routing decision.

        Args:
            match: The magic keyword match
            message: Original message

        Returns:
            RoutingDecision based on the magic keyword
        """
        action = match.action

        if action == "multi_provider":
            # For multi-provider, return the first provider but include info about others
            providers = match.providers or ["claude", "gemini", "codex"]
            return RoutingDecision(
                provider=providers[0],
                channel=ChannelType.CCB_DAEMON,
                fallback=ChannelType.DIRECT_CLI,
                task_type=TaskType.GENERAL,
                reason=f"Magic keyword '{match.keyword}' → multi-provider ({', '.join(providers)})",
                confidence=1.0,
            )

        elif action == "full_auto":
            # Full auto mode - use intelligent routing with all features
            features = match.features or []
            return RoutingDecision(
                provider=self.config.get("default_provider", "claude"),
                channel=ChannelType.CCB_DAEMON,
                fallback=ChannelType.DIRECT_CLI,
                task_type=TaskType.GENERAL,
                reason=f"Magic keyword 'smartroute' → full auto mode ({', '.join(features)})",
                confidence=1.0,
            )

        else:
            # Standard magic keyword - route to specified provider
            provider = match.provider or self.config.get("default_provider", "claude")
            return RoutingDecision(
                provider=provider,
                channel=ChannelType.CCB_DAEMON,
                fallback=ChannelType.DIRECT_CLI,
                task_type=TaskType.GENERAL,
                reason=f"Magic keyword '{match.keyword}' → {provider} ({match.description})",
                confidence=1.0,
            )

    def get_magic_keyword_info(self, keyword: str) -> Optional[Dict[str, Any]]:
        """
        Get information about a magic keyword.

        Args:
            keyword: The keyword to look up

        Returns:
            Dict with keyword configuration or None
        """
        # Check config first
        magic_config = self.config.get("magic_keywords", {})
        for kw_config in magic_config.get("keywords", []):
            if kw_config.get("keyword", "").lower() == keyword.lower():
                return kw_config

        # Fall back to built-in
        return self.MAGIC_KEYWORDS.get(keyword.lower())

    def list_magic_keywords(self) -> List[Dict[str, Any]]:
        """
        List all available magic keywords.

        Returns:
            List of keyword configurations
        """
        keywords = []

        # Add built-in keywords
        for kw, config in self.MAGIC_KEYWORDS.items():
            keywords.append({
                "keyword": kw,
                "source": "built-in",
                **config,
            })

        # Add/override with config keywords
        magic_config = self.config.get("magic_keywords", {})
        for kw_config in magic_config.get("keywords", []):
            kw = kw_config.get("keyword", "")
            # Check if it overrides a built-in
            existing = next((k for k in keywords if k["keyword"] == kw), None)
            if existing:
                existing.update(kw_config)
                existing["source"] = "config (override)"
            else:
                keywords.append({
                    "source": "config",
                    **kw_config,
                })

        return keywords
