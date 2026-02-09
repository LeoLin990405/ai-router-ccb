"""OpenAI-compatible response extractor."""

from __future__ import annotations

from typing import Any, Dict, Optional

from .base import ContentExtractor


class OpenAIExtractor(ContentExtractor):
    """Extract content and tokens from OpenAI chat completion payloads."""

    def extract_response(self, data: Dict[str, Any]) -> str:
        choices = data.get("choices", [])
        if not isinstance(choices, list) or not choices:
            return ""

        first = choices[0]
        if not isinstance(first, dict):
            return ""

        message = first.get("message", {})
        if not isinstance(message, dict):
            return ""

        content = message.get("content", "")
        if isinstance(content, str):
            return content

        if isinstance(content, list):
            text_parts = []
            for item in content:
                if not isinstance(item, dict):
                    continue
                text = item.get("text")
                if isinstance(text, str) and text:
                    text_parts.append(text)
            return "\n".join(text_parts)

        return str(content) if content is not None else ""

    def extract_tokens(self, data: Dict[str, Any]) -> Optional[int]:
        usage = data.get("usage", {})
        if not isinstance(usage, dict):
            return 0

        total = usage.get("total_tokens", 0)
        try:
            return int(total)
        except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError):
            return 0
