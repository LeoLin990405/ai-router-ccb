"""
Smart Auto-Router for CCB Gateway.

Automatically selects the best provider based on task keywords, characteristics,
and real-time performance metrics.
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Tuple, Callable


@dataclass
class RoutingRule:
    """A rule for routing requests to providers."""
    keywords: List[str]
    provider: str
    model: Optional[str] = None
    priority: int = 50  # Higher = more specific
    description: str = ""


@dataclass
class RoutingDecision:
    """Result of routing decision."""
    provider: str
    model: Optional[str] = None
    confidence: float = 1.0
    matched_keywords: List[str] = field(default_factory=list)
    rule_description: str = ""
    performance_score: float = 1.0  # New: performance-based score


@dataclass
class ProviderPerformance:
    """Real-time performance metrics for a provider."""
    provider: str
    avg_latency_ms: float = 0.0
    success_rate: float = 1.0
    cost_per_request: float = 0.0
    total_requests: int = 0
    recent_requests: int = 0  # Last hour
    last_success: Optional[float] = None
    last_failure: Optional[float] = None
    is_healthy: bool = True
    latency_samples: List[float] = field(default_factory=list)

    def record_request(self, latency_ms: float, success: bool) -> None:
        """Record a request result."""
        self.total_requests += 1
        self.recent_requests += 1

        if success:
            self.last_success = time.time()
            # Update latency samples
            self.latency_samples.append(latency_ms)
            if len(self.latency_samples) > 50:
                self.latency_samples = self.latency_samples[-50:]
            self.avg_latency_ms = sum(self.latency_samples) / len(self.latency_samples)
        else:
            self.last_failure = time.time()

        # Recalculate success rate (weighted toward recent)
        # This is a simplified exponential moving average
        alpha = 0.1  # Weight for new observation
        current_success = 1.0 if success else 0.0
        self.success_rate = alpha * current_success + (1 - alpha) * self.success_rate

    def calculate_score(
        self,
        latency_weight: float = 0.3,
        success_weight: float = 0.5,
        cost_weight: float = 0.2,
    ) -> float:
        """Calculate overall performance score (0.0 to 1.0, higher is better)."""
        # Normalize latency (assuming 30s is worst case)
        latency_score = max(0, 1 - (self.avg_latency_ms / 30000))

        # Success rate is already 0-1
        success_score = self.success_rate

        # Normalize cost (assuming $0.10 per request is worst case)
        cost_score = max(0, 1 - (self.cost_per_request / 0.10))

        # Health penalty
        health_multiplier = 1.0 if self.is_healthy else 0.5

        return (
            latency_score * latency_weight +
            success_score * success_weight +
            cost_score * cost_weight
        ) * health_multiplier


# Default routing rules based on task types
DEFAULT_ROUTING_RULES: List[RoutingRule] = [
    # Frontend/UI tasks -> Gemini
    RoutingRule(
        keywords=["react", "vue", "css", "html", "frontend", "ui", "component", "tailwind", "sass", "less", "styled"],
        provider="gemini",
        model="3f",
        priority=80,
        description="Frontend development tasks",
    ),
    # Algorithm/Math tasks -> Codex o3 or DeepSeek
    RoutingRule(
        keywords=[
            "algorithm",
            "algorithms",
            "proof",
            "math",
            "optimize",
            "optimization",
            "complexity",
            "leetcode",
            "dynamic programming",
            "graph",
            "算法",
            "复杂度",
            "排序",
            "递归",
            "动态规划",
            "二分",
            "图论",
            "证明",
            "数学",
            "最优化",
        ],
        provider="codex",
        model="o3",
        priority=85,
        description="Algorithm and mathematical reasoning",
    ),
    # Code review -> Codex
    RoutingRule(
        keywords=["review", "审查", "检查", "analyze code", "code quality", "refactor"],
        provider="codex",
        model="o3",
        priority=75,
        description="Code review and analysis",
    ),
    # Image/Visual tasks -> GPT-4o
    RoutingRule(
        keywords=["image", "picture", "screenshot", "visual", "图片", "图像", "截图", "看图"],
        provider="codex",
        model="gpt-4o",
        priority=90,
        description="Image and visual analysis",
    ),
    # Long document/Analysis -> Kimi (128k context)
    RoutingRule(
        keywords=["document", "summary", "paper", "article", "论文", "文档", "总结", "分析长"],
        provider="kimi",
        priority=70,
        description="Long document analysis",
    ),
    # Chinese writing/Translation -> Kimi
    RoutingRule(
        keywords=["翻译", "中文", "写作", "文案", "translate", "chinese"],
        provider="kimi",
        priority=75,
        description="Chinese language tasks",
    ),
    # Python/General coding -> Qwen
    RoutingRule(
        keywords=["python", "script", "automation", "脚本"],
        provider="qwen",
        priority=60,
        description="Python and scripting",
    ),
    # SQL/Database -> Qwen
    RoutingRule(
        keywords=["sql", "database", "query", "数据库", "mysql", "postgres", "sqlite"],
        provider="qwen",
        priority=70,
        description="SQL and database tasks",
    ),
    # Shell/Bash -> Kimi
    RoutingRule(
        keywords=["bash", "shell", "terminal", "命令行", "linux", "unix"],
        provider="kimi",
        priority=60,
        description="Shell and terminal tasks",
    ),
    # Deep reasoning -> DeepSeek
    RoutingRule(
        keywords=["详细", "推理", "reasoning", "think through", "step by step", "深入"],
        provider="deepseek",
        model="reasoner",
        priority=65,
        description="Deep reasoning tasks",
    ),
    # Quick questions -> Kimi (fast)
    RoutingRule(
        keywords=["quick", "fast", "简单", "快速", "explain", "what is", "how to"],
        provider="kimi",
        priority=40,
        description="Quick questions and explanations",
    ),
    # Workflow/Automation -> iFlow
    RoutingRule(
        keywords=["workflow", "automation", "自动化", "流程", "pipeline"],
        provider="iflow",
        priority=70,
        description="Workflow automation",
    ),
]


class SmartRouter:
    """
    Smart router that selects providers based on task characteristics and performance.

    Uses keyword matching, configurable rules, and real-time performance metrics
    to route requests to the most appropriate provider.
    """

    def __init__(
        self,
        rules: Optional[List[RoutingRule]] = None,
        default_provider: str = "kimi",
        available_providers: Optional[List[str]] = None,
        performance_weight: float = 0.3,
    ):
        """
        Initialize the smart router.

        Args:
            rules: List of routing rules (uses defaults if None)
            default_provider: Fallback provider when no rules match
            available_providers: List of available provider names
            performance_weight: Weight given to performance vs keyword matching (0-1)
        """
        self.rules = rules or DEFAULT_ROUTING_RULES.copy()
        self.default_provider = default_provider
        self.available_providers = available_providers or []
        self.performance_weight = performance_weight

        # Performance tracking
        self._performance: Dict[str, ProviderPerformance] = {}
        self._metrics_getter: Optional[Callable[[str], Dict[str, Any]]] = None

        # Sort rules by priority (highest first)
        self.rules.sort(key=lambda r: r.priority, reverse=True)

    def set_metrics_getter(self, getter: Callable[[str], Dict[str, Any]]) -> None:
        """Set function to get external metrics for a provider."""
        self._metrics_getter = getter

    def record_request(self, provider: str, latency_ms: float, success: bool) -> None:
        """Record a request result for performance tracking."""
        if provider not in self._performance:
            self._performance[provider] = ProviderPerformance(provider=provider)
        self._performance[provider].record_request(latency_ms, success)

    def update_provider_health(self, provider: str, is_healthy: bool) -> None:
        """Update health status for a provider."""
        if provider not in self._performance:
            self._performance[provider] = ProviderPerformance(provider=provider)
        self._performance[provider].is_healthy = is_healthy

    def get_performance(self, provider: str) -> Optional[ProviderPerformance]:
        """Get performance metrics for a provider."""
        return self._performance.get(provider)

    def route(self, message: str) -> RoutingDecision:
        """
        Route a message to the best provider.

        Args:
            message: The message to route

        Returns:
            RoutingDecision with selected provider and metadata
        """
        message_lower = message.lower()

        # Find matching rules
        matches: List[Tuple[RoutingRule, List[str], float]] = []

        for rule in self.rules:
            # Skip if provider not available
            if self.available_providers and rule.provider not in self.available_providers:
                continue

            matched_keywords = []
            for keyword in rule.keywords:
                if keyword.lower() in message_lower:
                    matched_keywords.append(keyword)

            if matched_keywords:
                # Calculate confidence based on keyword matches
                confidence = len(matched_keywords) / len(rule.keywords)
                confidence = min(confidence * (rule.priority / 100), 1.0)
                matches.append((rule, matched_keywords, confidence))

        if not matches:
            # No matches, use default provider
            perf = self._performance.get(self.default_provider)
            perf_score = perf.calculate_score() if perf else 1.0

            return RoutingDecision(
                provider=self.default_provider,
                confidence=0.5,
                rule_description="Default routing (no keyword matches)",
                performance_score=perf_score,
            )

        # Calculate combined scores (keyword + performance)
        scored_matches: List[Tuple[RoutingRule, List[str], float, float]] = []

        for rule, keywords, keyword_conf in matches:
            # Get performance score
            perf = self._performance.get(rule.provider)
            if perf:
                perf_score = perf.calculate_score()
            elif self._metrics_getter:
                # Try to get external metrics
                try:
                    metrics = self._metrics_getter(rule.provider)
                    perf_score = max(0.5, metrics.get("success_rate", 1.0))
                except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError):
                    perf_score = 0.8  # Neutral if metrics unavailable
            else:
                perf_score = 0.8  # Neutral default

            # Skip unhealthy providers if we have alternatives
            if perf and not perf.is_healthy and len(matches) > 1:
                continue

            # Combined score
            combined = (
                keyword_conf * (1 - self.performance_weight) +
                perf_score * self.performance_weight
            )
            scored_matches.append((rule, keywords, keyword_conf, combined))

        if not scored_matches:
            # All matches were unhealthy, use default
            return RoutingDecision(
                provider=self.default_provider,
                confidence=0.3,
                rule_description="Fallback (matched providers unhealthy)",
                performance_score=0.5,
            )

        # Select best match considering both keyword and performance
        best_rule, best_keywords, best_keyword_conf, best_combined = max(
            scored_matches,
            key=lambda x: (x[0].priority, x[3]),  # Primary: priority, Secondary: combined score
        )

        perf = self._performance.get(best_rule.provider)
        perf_score = perf.calculate_score() if perf else 1.0

        return RoutingDecision(
            provider=best_rule.provider,
            model=best_rule.model,
            confidence=best_combined,
            matched_keywords=best_keywords,
            rule_description=best_rule.description,
            performance_score=perf_score,
        )

    def add_rule(self, rule: RoutingRule) -> None:
        """Add a new routing rule."""
        self.rules.append(rule)
        self.rules.sort(key=lambda r: r.priority, reverse=True)

    def remove_rule(self, keywords: List[str]) -> bool:
        """Remove a rule by its keywords."""
        for i, rule in enumerate(self.rules):
            if set(rule.keywords) == set(keywords):
                self.rules.pop(i)
                return True
        return False

    def get_rules(self) -> List[Dict[str, Any]]:
        """Get all routing rules as dictionaries."""
        return [
            {
                "keywords": rule.keywords,
                "provider": rule.provider,
                "model": rule.model,
                "priority": rule.priority,
                "description": rule.description,
            }
            for rule in self.rules
        ]

    def set_available_providers(self, providers: List[str]) -> None:
        """Update the list of available providers."""
        self.available_providers = providers

    def get_all_performance(self) -> Dict[str, Dict[str, Any]]:
        """Get performance data for all tracked providers."""
        return {
            provider: {
                "avg_latency_ms": round(perf.avg_latency_ms, 2),
                "success_rate": round(perf.success_rate, 3),
                "total_requests": perf.total_requests,
                "recent_requests": perf.recent_requests,
                "is_healthy": perf.is_healthy,
                "score": round(perf.calculate_score(), 3),
            }
            for provider, perf in self._performance.items()
        }

    def get_best_provider_for_task(
        self,
        task_type: str,
        exclude: Optional[List[str]] = None,
    ) -> Optional[str]:
        """
        Get the best provider for a specific task type.

        Args:
            task_type: Type of task (e.g., "frontend", "algorithm", "chinese")
            exclude: Providers to exclude from selection

        Returns:
            Best provider name or None
        """
        exclude = exclude or []

        # Find matching rules for this task type
        candidates = []
        for rule in self.rules:
            if rule.provider in exclude:
                continue
            if self.available_providers and rule.provider not in self.available_providers:
                continue

            # Check if task type matches any keyword
            if any(task_type.lower() in kw.lower() for kw in rule.keywords):
                perf = self._performance.get(rule.provider)
                if perf and not perf.is_healthy:
                    continue  # Skip unhealthy
                score = perf.calculate_score() if perf else 0.8
                candidates.append((rule.provider, rule.priority, score))

        if not candidates:
            # Return default if healthy
            perf = self._performance.get(self.default_provider)
            if perf and not perf.is_healthy:
                return None
            return self.default_provider if self.default_provider not in exclude else None

        # Sort by priority then score
        candidates.sort(key=lambda x: (x[1], x[2]), reverse=True)
        return candidates[0][0]

    def reset_performance(self, provider: Optional[str] = None) -> None:
        """Reset performance tracking for one or all providers."""
        if provider:
            if provider in self._performance:
                self._performance[provider] = ProviderPerformance(provider=provider)
        else:
            self._performance.clear()


# Convenience function for direct routing
def auto_route(message: str, available_providers: Optional[List[str]] = None) -> RoutingDecision:
    """
    Route a message to the best provider.

    Args:
        message: The message to route
        available_providers: Optional list of available providers

    Returns:
        RoutingDecision with selected provider
    """
    router = SmartRouter(available_providers=available_providers)
    return router.route(message)
