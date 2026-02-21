"""
Oracle Agent - Deep Reasoning Specialist

Analyzes complex problems and provides thorough solutions.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, List, Dict, Any

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from agent_registry import AgentConfig, AgentCapability


class OracleAgent:
    """
    Deep reasoning specialist agent.

    Capabilities:
    - Complex problem analysis
    - Algorithm design
    - Mathematical reasoning
    - Step-by-step problem solving
    """

    NAME = "oracle"
    DESCRIPTION = "Deep reasoning and analysis specialist. Solves complex problems."

    SYSTEM_PROMPT = """You are Oracle, a deep reasoning specialist.

Your role is to analyze complex problems and provide thorough solutions.

Guidelines:
1. Break down complex problems into smaller parts
2. Consider all edge cases and constraints
3. Provide step-by-step reasoning
4. Use mathematical notation when appropriate
5. Validate your conclusions
6. Consider alternative approaches

When analyzing:
- State your assumptions clearly
- Show your work and reasoning
- Identify potential issues or limitations
- Suggest optimizations if applicable

Output format:
- Problem understanding
- Analysis and reasoning
- Solution or recommendation
- Complexity analysis (if applicable)
"""

    CAPABILITIES = [
        AgentCapability.REASONING,
        AgentCapability.ANALYSIS,
    ]

    PREFERRED_PROVIDERS = ["claude", "gemini"]
    FALLBACK_PROVIDERS = ["gemini", "codex"]

    TOOLS = [
        "read",
        "grep",
        "web_search",
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

        # Check for reasoning keywords
        reasoning_keywords = [
            "analyze", "reason", "think", "deduce", "solve", "prove",
            "algorithm", "complexity", "optimize", "mathematical",
            "why", "how does", "explain why",
            "分析", "推理", "思考", "算法", "优化", "证明",
        ]
        for kw in reasoning_keywords:
            if kw in task_lower:
                score += 0.3

        # Check for complexity indicators
        complexity_terms = [
            "complex", "difficult", "challenging", "tricky",
            "edge case", "corner case", "trade-off",
            "复杂", "困难", "边界情况",
        ]
        for term in complexity_terms:
            if term in task_lower:
                score += 0.2

        return min(1.0, score)

    @classmethod
    def format_task(cls, task: str, context: Dict[str, Any]) -> str:
        """Format a task with context for execution."""
        parts = [cls.SYSTEM_PROMPT, "", "Problem:", task]

        if context.get("constraints"):
            parts.extend(["", "Constraints:", context["constraints"]])

        return "\n".join(parts)
