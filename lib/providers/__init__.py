"""Provider communication readers and legacy provider specs compatibility."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Optional

from .base import BaseCommReader, CommMessage, CommState
from .claude import ClaudeCommReader
from .codex import CodexCommReader
from .droid import DroidCommReader
from .factory import get_comm_reader
from .gemini import GeminiCommReader
from .iflow import IFlowCommReader
from .kimi import KimiCommReader
from .opencode import OpenCodeCommReader
from .qwen import QwenCommReader

_LEGACY_MODULE: Optional[ModuleType] = None


def _load_legacy_specs_module() -> Optional[ModuleType]:
    global _LEGACY_MODULE
    if _LEGACY_MODULE is not None:
        return _LEGACY_MODULE

    legacy_path = Path(__file__).resolve().parent.parent / "providers.py"
    if not legacy_path.exists():
        return None

    spec = importlib.util.spec_from_file_location("lib._providers_specs", legacy_path)
    if spec is None or spec.loader is None:
        return None

    module = importlib.util.module_from_spec(spec)
    sys.modules.setdefault("lib._providers_specs", module)
    spec.loader.exec_module(module)
    _LEGACY_MODULE = module
    return module


def __getattr__(name: str):
    legacy = _load_legacy_specs_module()
    if legacy is not None and hasattr(legacy, name):
        value = getattr(legacy, name)
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "BaseCommReader",
    "CommMessage",
    "CommState",
    "ClaudeCommReader",
    "CodexCommReader",
    "DroidCommReader",
    "GeminiCommReader",
    "IFlowCommReader",
    "KimiCommReader",
    "OpenCodeCommReader",
    "QwenCommReader",
    "get_comm_reader",
    "ProviderDaemonSpec",
    "ProviderClientSpec",
    "CASKD_SPEC",
    "GASKD_SPEC",
    "OASKD_SPEC",
    "LASKD_SPEC",
    "DASKD_SPEC",
    "IASKD_SPEC",
    "KASKD_SPEC",
    "QASKD_SPEC",
    "GRKASKD_SPEC",
    "CASK_CLIENT_SPEC",
    "GASK_CLIENT_SPEC",
    "OASK_CLIENT_SPEC",
    "LASK_CLIENT_SPEC",
    "DASK_CLIENT_SPEC",
    "IASK_CLIENT_SPEC",
    "KASK_CLIENT_SPEC",
    "QASK_CLIENT_SPEC",
    "GRKASK_CLIENT_SPEC",
]
