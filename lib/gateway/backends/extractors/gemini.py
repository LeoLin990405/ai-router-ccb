"""Gemini response extractor."""

from __future__ import annotations

from typing import Any, Dict, Optional

from .base import ContentExtractor


class GeminiExtractor(ContentExtractor):
    """Extract content and tokens from Gemini generateContent payloads."""

    def extract_response(self, data: Dict[str, Any]) -> str:
        candidates = data.get("candidates", [])
        if not isinstance(candidates, list) or not candidates:
            return ""

        first = candidates[0]
        if not isinstance(first, dict):
            return ""

        content = first.get("content", {})
        if not isinstance(content, dict):
            return ""

        parts = content.get("parts", [])
        if not isinstance(parts, list):
            return ""

        text_parts = []
        for part in parts:
            if not isinstance(part, dict):
                continue
            text = part.get("text")
            if isinstance(text, str) and text:
                text_parts.append(text)

        return "".join(text_parts)

    def extract_tokens(self, data: Dict[str, Any]) -> Optional[int]:
        usage = data.get("usageMetadata", {})
        if not isinstance(usage, dict):
            return 0

        total = usage.get("totalTokenCount", 0)
        try:
            return int(total)
        except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError):
            return 0
