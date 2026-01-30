"""
Unified Router Engine - Nexus CLI + CCB Integration

Provides intelligent task routing to select the optimal AI provider
based on task type, file patterns, and keywords.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List, Dict, Any
from pathlib import Path
import re
import fnmatch
import os
import yaml


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

    # All available providers (must match CCB's supported providers)
    # CCB supports: codex, gemini, opencode, claude, droid, iflow, kimi, qwen, deepseek
    ALL_PROVIDERS = [
        "claude",    # lask - Claude Code CLI
        "codex",     # cask - Codex CLI (OpenAI)
        "gemini",    # gask - Gemini CLI (Google)
        "opencode",  # oask - OpenCode CLI
        "droid",     # dask - Droid CLI
        "iflow",     # iask - iFlow CLI
        "kimi",      # kask - Kimi CLI (Moonshot)
        "qwen",      # qask - Qwen CLI (Alibaba)
        "deepseek",  # dskask - DeepSeek CLI
    ]

    # Provider to ask command mapping (CCB daemon commands)
    PROVIDER_COMMANDS = {
        "claude": "lask",     # Claude uses lask (not cask)
        "codex": "cask",      # Codex uses cask
        "gemini": "gask",
        "opencode": "oask",
        "droid": "dask",
        "iflow": "iask",
        "kimi": "kask",
        "qwen": "qask",
        "deepseek": "dskask",
    }

    # Provider to ping command mapping
    PROVIDER_PING_COMMANDS = {
        "claude": "lping",
        "codex": "cping",
        "gemini": "gping",
        "opencode": "oping",
        "droid": "dping",
        "iflow": "iping",
        "kimi": "kping",
        "qwen": "qping",
        "deepseek": "dskping",
    }

    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize the router with optional configuration.

        Args:
            config_path: Path to YAML configuration file
        """
        self.config: Dict[str, Any] = {}
        self.custom_rules: List[RoutingRule] = []
        self._provider_health: Dict[str, ProviderHealth] = {}

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
    ) -> RoutingDecision:
        """
        Determine the optimal provider for a given task.

        Args:
            message: The user's message/query
            files: Optional list of file paths involved
            preferred_provider: Optional user-specified provider preference

        Returns:
            RoutingDecision with provider, channel, and reasoning
        """
        # If user explicitly specified a provider, use it
        if preferred_provider and preferred_provider in self.ALL_PROVIDERS:
            return RoutingDecision(
                provider=preferred_provider,
                channel=ChannelType.CCB_DAEMON,
                fallback=ChannelType.DIRECT_CLI,
                task_type=TaskType.GENERAL,
                reason=f"User specified provider: {preferred_provider}",
                confidence=1.0,
            )

        # Try custom rules first
        custom_match = self._match_custom_rules(message, files)
        if custom_match:
            return custom_match

        # Infer task type from message
        task_type = self._infer_task_type(message)

        # Select provider based on task type and files
        provider = self._select_provider(task_type, files)

        return RoutingDecision(
            provider=provider,
            channel=ChannelType.CCB_DAEMON,
            fallback=ChannelType.DIRECT_CLI,
            task_type=task_type,
            reason=f"Task type '{task_type.value}' → {provider}",
            confidence=0.8,
        )

    def _match_custom_rules(
        self,
        message: str,
        files: Optional[List[str]] = None,
    ) -> Optional[RoutingDecision]:
        """Check if any custom routing rules match."""
        msg_lower = message.lower()

        for rule in self.custom_rules:
            # Check keyword match
            keyword_match = any(kw.lower() in msg_lower for kw in rule.keywords)

            # Check file pattern match
            pattern_match = False
            if files and rule.patterns:
                for f in files:
                    for pattern in rule.patterns:
                        if fnmatch.fnmatch(f, pattern):
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
        return self.PROVIDER_COMMANDS.get(provider, "lask")

    def get_provider_ping_command(self, provider: str) -> str:
        """Get the ping command for a provider."""
        return self.PROVIDER_PING_COMMANDS.get(provider, "lping")

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
