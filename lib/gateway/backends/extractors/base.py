"""Base interface for parsing provider HTTP responses."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional


class ContentExtractor(ABC):
    """Parse provider response payloads into normalized fields."""

    @abstractmethod
    def extract_response(self, data: Dict[str, Any]) -> str:
        """Extract assistant response text from provider payload."""

    @abstractmethod
    def extract_tokens(self, data: Dict[str, Any]) -> Optional[int]:
        """Extract total token usage from provider payload if available."""
