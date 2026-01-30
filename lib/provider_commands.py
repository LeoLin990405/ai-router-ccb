"""
Provider Commands - Single Source of Truth

Unified mapping of providers to their CLI commands.
"""
from __future__ import annotations

from typing import Dict


# All available providers (must match CCB's supported providers)
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
PROVIDER_COMMANDS: Dict[str, str] = {
    "claude": "lask",
    "codex": "cask",
    "gemini": "gask",
    "opencode": "oask",
    "droid": "dask",
    "iflow": "iask",
    "kimi": "kask",
    "qwen": "qask",
    "deepseek": "dskask",
}

# Provider to ping command mapping
PROVIDER_PING_COMMANDS: Dict[str, str] = {
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

# Provider to pend command mapping (for checking results)
PROVIDER_PEND_COMMANDS: Dict[str, str] = {
    "claude": "lpend",
    "codex": "cpend",
    "gemini": "gpend",
    "opencode": "opend",
    "droid": "dpend",
    "iflow": "ipend",
    "kimi": "kpend",
    "qwen": "qpend",
    "deepseek": "dskpend",
}


def get_ask_command(provider: str) -> str:
    """Get the ask command for a provider."""
    return PROVIDER_COMMANDS.get(provider, "lask")


def get_ping_command(provider: str) -> str:
    """Get the ping command for a provider."""
    return PROVIDER_PING_COMMANDS.get(provider, "lping")


def get_pend_command(provider: str) -> str:
    """Get the pend command for a provider."""
    return PROVIDER_PEND_COMMANDS.get(provider, "lpend")


def is_valid_provider(provider: str) -> bool:
    """Check if a provider is valid."""
    return provider in ALL_PROVIDERS
