"""
Polyglot Agent - Multilingual Specialist

Handles multilingual tasks, translation, and long-context processing.
"""
from __future__ import annotations

from typing import Optional, List, Dict, Any

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from agent_registry import AgentConfig, AgentCapability


class PolyglotAgent:
    """
    Multilingual specialist agent.

    Capabilities:
    - Multilingual text processing
    - Translation between languages
    - Long-context document handling
    - Cross-cultural communication
    """

    NAME = "polyglot"
    DESCRIPTION = "Multilingual specialist. Handles translation, multilingual tasks, and long-context processing."

    SYSTEM_PROMPT = """You are Polyglot, a multilingual specialist.

Your role is to handle multilingual tasks, translation, and long-context processing.

Guidelines:
1. Preserve meaning and nuance in translations
2. Maintain technical accuracy for code-related content
3. Handle long documents efficiently
4. Respect cultural context and idioms
5. Support code comments and documentation in multiple languages
6. Provide natural, fluent output

Language capabilities:
- Chinese (Simplified/Traditional)
- English
- Japanese
- Korean
- European languages
- Technical/programming terminology

Output format:
- Clear, natural language output
- Preserve formatting and structure
- Note any ambiguities or alternatives
- Maintain code syntax when translating comments
"""

    CAPABILITIES = [
        AgentCapability.MULTILINGUAL,
        AgentCapability.TRANSLATION,
        AgentCapability.DOCUMENTATION,
    ]

    PREFERRED_PROVIDERS = ["kimi", "qwen"]
    FALLBACK_PROVIDERS = ["claude", "gemini"]

    TOOLS = [
        "read",
        "file_write",
        "file_edit",
    ]

    @classmethod
    def get_config(cls) -> AgentConfig:
        """Get the agent configuration."""
        return AgentConfig(
            name=cls.NAME,
            description=cls.DESCRIPTION,
            capabilities=cls.CAPABILITIES,
            preferred_providers=cls.PREFERRED_PROVIDERS,
            fallback_providers=cls.FALLBACK_PROVIDERS,
            tools=cls.TOOLS,
            system_prompt=cls.SYSTEM_PROMPT,
        )

    @classmethod
    def can_handle(cls, task: str, files: Optional[List[str]] = None) -> float:
        """Check if this agent can handle the task."""
        task_lower = task.lower()
        score = 0.0

        # Check for translation keywords
        translation_keywords = [
            "translate", "translation", "翻译", "译",
            "convert to", "in chinese", "in english", "in japanese",
            "转换", "中文", "英文", "日文",
        ]
        for kw in translation_keywords:
            if kw in task_lower:
                score += 0.4

        # Check for multilingual indicators
        multilingual_keywords = [
            "multilingual", "multi-language", "localize", "localization",
            "i18n", "internationalization", "l10n",
            "多语言", "本地化", "国际化",
        ]
        for kw in multilingual_keywords:
            if kw in task_lower:
                score += 0.3

        # Check for long-context indicators
        longcontext_keywords = [
            "long document", "entire file", "whole file", "full document",
            "长文档", "整个文件", "完整文档",
        ]
        for kw in longcontext_keywords:
            if kw in task_lower:
                score += 0.2

        # Detect Chinese characters in task
        import re
        if re.search(r'[\u4e00-\u9fff]', task):
            score += 0.1

        return min(1.0, score)

    @classmethod
    def format_task(cls, task: str, context: Dict[str, Any]) -> str:
        """Format a task with context for execution."""
        parts = [cls.SYSTEM_PROMPT, "", "Task:", task]

        if context.get("source_language"):
            parts.extend(["", f"Source language: {context['source_language']}"])

        if context.get("target_language"):
            parts.extend([f"Target language: {context['target_language']}"])

        if context.get("files"):
            parts.extend(["", "Files:", ", ".join(context["files"])])

        return "\n".join(parts)
