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
import sys
import yaml

if TYPE_CHECKING:
    from rate_limiter import RateLimiter

# Import unified provider commands
def _warn(message: str) -> None:
    sys.stderr.write(f"{message}\n")


from provider_commands import (
    ALL_PROVIDERS,
    PROVIDER_COMMANDS,
    PROVIDER_PING_COMMANDS,
    get_ask_command,
    get_ping_command,
)


HANDLED_EXCEPTIONS = (Exception,)


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



try:
    from .unified_router_core import UnifiedRouterCoreMixin
    from .unified_router_magic import UnifiedRouterMagicMixin
except ImportError:  # pragma: no cover - script mode
    from unified_router_core import UnifiedRouterCoreMixin
    from unified_router_magic import UnifiedRouterMagicMixin


class UnifiedRouter(UnifiedRouterCoreMixin, UnifiedRouterMagicMixin):
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
        TaskType.REASONING: "claude",
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
            "provider": "claude",
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
