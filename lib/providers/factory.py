"""Factory helpers for provider communication readers."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from .base import BaseCommReader
from .claude import ClaudeCommReader
from .codex import CodexCommReader
from .droid import DroidCommReader
from .gemini import GeminiCommReader
from .iflow import IFlowCommReader
from .kimi import KimiCommReader
from .opencode import OpenCodeCommReader
from .qwen import QwenCommReader


def get_comm_reader(
    provider: str,
    *,
    home_dir: Optional[str] = None,
    work_dir: Optional[Path] = None,
) -> BaseCommReader:
    """Return a comm reader implementation by provider name."""
    normalized = (provider or "").strip().lower()

    if normalized in {"claude", "cl"}:
        return ClaudeCommReader(home_dir=home_dir, work_dir=work_dir)

    if normalized in {"codex", "cx"}:
        return CodexCommReader(home_dir=home_dir, work_dir=work_dir)

    if normalized in {"droid", "dr"}:
        return DroidCommReader(home_dir=home_dir, work_dir=work_dir)

    if normalized in {"gemini", "gm"}:
        return GeminiCommReader(home_dir=home_dir, work_dir=work_dir)

    if normalized in {"iflow", "if"}:
        return IFlowCommReader(home_dir=home_dir, work_dir=work_dir)

    if normalized == "kimi":
        return KimiCommReader(home_dir=home_dir, work_dir=work_dir)

    if normalized in {"opencode", "oc"}:
        return OpenCodeCommReader(home_dir=home_dir, work_dir=work_dir)

    if normalized in {"qwen", "qw"}:
        return QwenCommReader(home_dir=home_dir, work_dir=work_dir)

    raise ValueError(f"Unsupported provider for comm reader: {provider}")
