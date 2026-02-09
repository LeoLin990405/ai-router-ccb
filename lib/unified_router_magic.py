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


class UnifiedRouterMagicMixin:
    """Mixin methods extracted from UnifiedRouter."""

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

