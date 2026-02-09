"""Compatibility shim for legacy ``gateway.backends.http_backend`` imports."""

from .http import HTTPBackend

__all__ = ["HTTPBackend"]

