"""Pydantic compatibility layer for gateway models."""
from __future__ import annotations

try:
    from pydantic import BaseModel, Field
    HAS_PYDANTIC = True
except ImportError:  # pragma: no cover - optional dependency
    HAS_PYDANTIC = False

    class BaseModel:
        """Fallback BaseModel when pydantic is unavailable."""

        def __init__(self, **data):
            for key, value in data.items():
                setattr(self, key, value)

        def dict(self, *args, **kwargs):
            return self.__dict__.copy()

        def model_dump(self, *args, **kwargs):
            return self.__dict__.copy()

    def Field(default=None, *, default_factory=None, **kwargs):
        if default_factory is not None:
            return default_factory()
        return default
