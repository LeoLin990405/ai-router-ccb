"""
Backend implementations for CCB Gateway.

Provides different backend types for communicating with AI providers:
- HTTP API (OpenAI, Anthropic)
- CLI Execution (Codex, Gemini CLI)
- FIFO/Pipe (legacy)
- Terminal (legacy WezTerm integration)
"""
from .base_backend import BaseBackend, BackendResult
from .http import HTTPBackend
from .cli import CLIBackend, InteractiveCLIBackend
from .obsidian_backend import ObsidianBackend

__all__ = [
    "BaseBackend",
    "BackendResult",
    "HTTPBackend",
    "CLIBackend",
    "InteractiveCLIBackend",
    "ObsidianBackend",
]
