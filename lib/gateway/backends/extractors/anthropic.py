"""Anthropic response extractor."""

from __future__ import annotations

from typing import Any, Dict, Optional

from .base import ContentExtractor


class AnthropicExtractor(ContentExtractor):
    """Extract content and tokens from Anthropic Messages API payloads."""

    def extract_response(self, data: Dict[str, Any]) -> str:
        content = data.get("content", [])
        if not isinstance(content, list):
            return ""

        text_parts = []
        for block in content:
            if not isinstance(block, dict):
                continue
            if block.get("type") != "text":
                continue
            text = block.get("text")
            if isinstance(text, str) and text:
                text_parts.append(text)

        return "\n".join(text_parts)

    def extract_tokens(self, data: Dict[str, Any]) -> Optional[int]:
        usage = data.get("usage", {})
        if not isinstance(usage, dict):
            return 0

        input_tokens = usage.get("input_tokens", 0)
        output_tokens = usage.get("output_tokens", 0)
        try:
            return int(input_tokens) + int(output_tokens)
        except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError):
            return 0
