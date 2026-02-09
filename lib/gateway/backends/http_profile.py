"""Profile helpers for HTTP backend provider execution settings."""

from __future__ import annotations

from dataclasses import dataclass

from ..gateway_config import ProviderConfig


_DEFAULT_MODELS = {
    "anthropic": "claude-sonnet-4-20250514",
    "gemini": "gemini-2.0-flash",
    "openai": "gpt-4",
}


@dataclass(frozen=True)
class HTTPExecutionProfile:
    """Resolved execution settings for one HTTP API kind."""

    api_kind: str
    api_base_url: str
    model: str
    max_tokens: int
    timeout_s: float
    provider_name: str


def normalize_api_kind(api_kind: str) -> str:
    """Normalize unsupported API kind to the OpenAI-compatible default."""
    return api_kind if api_kind in _DEFAULT_MODELS else "openai"


def resolve_http_profile(config: ProviderConfig, api_kind: str) -> HTTPExecutionProfile:
    """Resolve effective HTTP execution profile for a given API kind."""
    kind = normalize_api_kind(api_kind)
    model = config.model or _DEFAULT_MODELS[kind]

    return HTTPExecutionProfile(
        api_kind=kind,
        api_base_url=config.api_base_url or "",
        model=model,
        max_tokens=config.max_tokens,
        timeout_s=config.timeout_s,
        provider_name=config.name or "",
    )
