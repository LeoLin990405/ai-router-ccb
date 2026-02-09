#!/usr/bin/env python3
"""
CCB Memory Backend using Mem0

Provides persistent memory across all CCB providers.
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional

try:
    from lib.common.logging import get_logger
except ImportError:  # pragma: no cover - script mode
    try:
        from common.logging import get_logger  # type: ignore
    except ImportError:  # pragma: no cover - fallback
        import logging

        def get_logger(name: str):
            return logging.getLogger(name)


logger = get_logger("memory.backend")


def _emit(message: str = "") -> None:
    sys.stdout.write(f"{message}\n")


try:
    from mem0 import Memory

    HAS_MEM0 = True
except ImportError:
    HAS_MEM0 = False
    logger.warning("mem0ai not installed. Install with: pip install mem0ai")


class CCBMemory:
    """Unified memory layer for CCB system."""

    def __init__(self, user_id: str = "leo", config_path: Optional[Path] = None):
        if not HAS_MEM0:
            raise RuntimeError("mem0ai is not installed")

        self.user_id = user_id
        self.config_path = config_path or Path.home() / ".ccb" / "memory_config.json"

        # Load CCB config first
        self.config = self._load_config()

        # Initialize Mem0 with simple config (use environment variables)
        # Mem0 will automatically use OPENAI_API_KEY from environment
        self.memory = Memory()

    def _load_config(self) -> Dict[str, Any]:
        """Load memory configuration."""
        if self.config_path.exists():
            with open(self.config_path) as f:
                return json.load(f)

        # Default config
        default_config = {
            "enabled": True,
            "auto_record": True,
            "context_injection": True,
            "max_context_tokens": 2000,
            "privacy": {
                "exclude_patterns": ["password", "api_key", "secret", "token"]
            },
        }

        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.config_path, "w") as f:
            json.dump(default_config, f, indent=2)

        return default_config

    def record_conversation(
        self,
        provider: str,
        question: str,
        answer: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Record a conversation to memory."""
        if not self.config.get("auto_record", True):
            return ""

        # Check privacy patterns
        if self._contains_sensitive(question) or self._contains_sensitive(answer):
            return ""

        # Create memory content
        content = f"[{provider}] Q: {question}\nA: {answer[:500]}"  # Limit answer length

        meta = metadata or {}
        meta.update(
            {
                "provider": provider,
                "timestamp": datetime.now().isoformat(),
                "question": question[:200],  # Store truncated for search
            }
        )

        try:
            result = self.memory.add(content, user_id=self.user_id, metadata=meta)
            return result.get("memory_id", "")
        except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError) as e:
            logger.warning("Failed to record memory: %s", e)
            return ""

    def search_context(
        self,
        query: str,
        limit: int = 5,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Search for relevant context."""
        if not self.config.get("enabled", True):
            return []

        try:
            results = self.memory.search(query=query, user_id=self.user_id, limit=limit)
            return results
        except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError) as e:
            logger.warning("Failed to search memory: %s", e)
            return []

    def get_task_context(self, task_keywords: List[str]) -> Dict[str, Any]:
        """Get comprehensive context for a task."""
        # Search for relevant memories
        query = " ".join(task_keywords)
        memories = self.search_context(query, limit=3)

        # Get provider recommendations from registry
        from .registry import CCBRegistry

        registry = CCBRegistry()
        providers = registry.find_provider_for_task(task_keywords)

        # Get relevant skills
        registry_data = registry.load_cache() or registry.generate_registry()
        relevant_skills = []
        for skill in registry_data.get("skills", []):
            for keyword in task_keywords:
                if keyword.lower() in skill.get("description", "").lower():
                    relevant_skills.append(skill["name"])
                    break

        return {
            "memories": memories,
            "recommended_providers": providers[:3],
            "relevant_skills": relevant_skills[:5],
            "query": query,
        }

    def _contains_sensitive(self, text: str) -> bool:
        """Check if text contains sensitive information."""
        patterns = self.config.get("privacy", {}).get("exclude_patterns", [])
        text_lower = text.lower()
        return any(pattern in text_lower for pattern in patterns)

    def format_context_for_prompt(self, context: Dict[str, Any]) -> str:
        """Format context into human-readable prompt addition."""
        lines = []

        # Add relevant memories
        if context.get("memories"):
            lines.append("## 相关记忆")
            for i, memory in enumerate(context["memories"][:3], 1):
                content = memory.get("memory", "")
                if content:
                    lines.append(f"{i}. {content[:200]}")

        # Add provider recommendations
        if context.get("recommended_providers"):
            lines.append("\n## 推荐使用的 AI")
            for provider in context["recommended_providers"]:
                lines.append(f"- {provider['provider']}: {provider['command']}")

        # Add relevant skills
        if context.get("relevant_skills"):
            lines.append("\n## 可用的 Skills")
            lines.append(f"- {', '.join(context['relevant_skills'][:5])}")

        return "\n".join(lines)

    def record_learning(self, learning: str, category: str = "general"):
        """Record a learning or insight."""
        self.memory.add(
            f"Learning ({category}): {learning}",
            user_id=self.user_id,
            metadata={
                "type": "learning",
                "category": category,
                "timestamp": datetime.now().isoformat(),
            },
        )

    def get_all_memories(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get all memories for the user."""
        try:
            return self.memory.get_all(user_id=self.user_id)
        except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError) as e:
            logger.warning("Failed to get all memories: %s", e)
            return []


def main():
    """CLI for memory operations."""
    import sys

    if not HAS_MEM0:
        _emit("Error: mem0ai is not installed")
        _emit("Install with: pip install mem0ai")
        sys.exit(1)

    memory = CCBMemory()

    if len(sys.argv) < 2:
        _emit("Usage: memory_backend.py [record|search|context|list] [args...]")
        sys.exit(1)

    command = sys.argv[1]

    if command == "record":
        if len(sys.argv) < 5:
            _emit("Usage: memory_backend.py record <provider> <question> <answer>")
            sys.exit(1)

        provider = sys.argv[2]
        question = sys.argv[3]
        answer = sys.argv[4]

        memory_id = memory.record_conversation(provider, question, answer)
        if memory_id:
            _emit(f"✓ Recorded memory: {memory_id}")
        else:
            _emit("✗ Failed to record (may contain sensitive data)")

    elif command == "search":
        if len(sys.argv) < 3:
            _emit("Usage: memory_backend.py search <query>")
            sys.exit(1)

        query = " ".join(sys.argv[2:])
        results = memory.search_context(query)

        if results:
            _emit(f"Found {len(results)} results for: {query}\n")
            for i, result in enumerate(results, 1):
                _emit(f"{i}. {result.get('memory', '')[:200]}")
                _emit(f"   Metadata: {result.get('metadata', {})}")
                _emit()
        else:
            _emit("No results found.")

    elif command == "context":
        if len(sys.argv) < 3:
            _emit("Usage: memory_backend.py context <task_keywords...>")
            sys.exit(1)

        keywords = sys.argv[2:]
        context = memory.get_task_context(keywords)

        _emit(memory.format_context_for_prompt(context))

    elif command == "list":
        memories = memory.get_all_memories(limit=20)
        _emit(f"Total memories: {len(memories)}\n")
        for i, mem in enumerate(memories[:20], 1):
            _emit(f"{i}. {mem.get('memory', '')[:100]}")

    else:
        _emit(f"Unknown command: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()
