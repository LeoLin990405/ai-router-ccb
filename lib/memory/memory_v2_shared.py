"""Shared logging and error aliases for Memory v2 modules."""
from __future__ import annotations

try:
    from lib.common.logging import get_logger
except ImportError:  # pragma: no cover - script mode
    try:
        from common.logging import get_logger  # type: ignore
    except ImportError:  # pragma: no cover - fallback
        import logging

        def get_logger(name: str):
            return logging.getLogger(name)


logger = get_logger("memory.v2")
MEMORY_V2_ERRORS = (Exception,)
