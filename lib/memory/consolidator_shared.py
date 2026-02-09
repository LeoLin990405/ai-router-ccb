"""Shared dependencies for memory consolidator modules."""
from __future__ import annotations

try:
    import httpx
    HAS_HTTPX = True
except ImportError:  # pragma: no cover - optional dependency
    httpx = None  # type: ignore[assignment]
    HAS_HTTPX = False

try:
    from lib.common.logging import get_logger
except ImportError:  # pragma: no cover - script mode
    try:
        from common.logging import get_logger  # type: ignore
    except ImportError:  # pragma: no cover - fallback
        import logging

        def get_logger(name: str):
            return logging.getLogger(name)


logger = get_logger("memory.consolidator")
CONSOLIDATOR_ERRORS = (Exception,)
