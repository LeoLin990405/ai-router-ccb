"""
Autonomous Agent - Self-Directed Task Execution Specialist

Handles long-running, autonomous tasks with minimal supervision.
"""
from __future__ import annotations

from typing import Optional, List, Dict, Any

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from agent_registry import AgentConfig, AgentCapability


class AutonomousAgent:
    """
    Autonomous task execution specialist agent.

    Capabilities:
    - Long-running task execution
    - Background processing
    - Self-directed problem solving
    - Minimal supervision operation
    """

    NAME = "autonomous"
    DESCRIPTION = "Autonomous execution specialist. Handles long-running tasks with minimal supervision."

    SYSTEM_PROMPT = """You are Autonomous, a self-directed task execution specialist.

Your role is to handle long-running, complex tasks that require minimal supervision.

Guidelines:
1. Plan the complete task before starting
2. Break work into checkpoints for progress tracking
3. Handle errors autonomously when possible
4. Report progress at key milestones
5. Make reasonable decisions without constant input
6. Document actions taken for review

Execution principles:
- Verify prerequisites before starting
- Create backups before destructive operations
- Log all significant actions
- Implement graceful degradation
- Provide clear completion status

Output format:
- Task plan overview
- Progress updates at milestones
- Decisions made and rationale
- Final status and results
- Any issues encountered
"""

    CAPABILITIES = [
        AgentCapability.AUTONOMOUS,
        AgentCapability.LONG_RUNNING,
        AgentCapability.CODE_WRITE,
    ]

    PREFERRED_PROVIDERS = ["droid", "codex"]
    FALLBACK_PROVIDERS = ["claude", "opencode"]

    TOOLS = [
        "bash",
        "read",
        "file_write",
        "file_edit",
        "glob",
        "grep",
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
            max_iterations=20,  # Allow more iterations for long tasks
        )

    @classmethod
    def can_handle(cls, task: str, files: Optional[List[str]] = None) -> float:
        """Check if this agent can handle the task."""
        task_lower = task.lower()
        score = 0.0

        # Check for autonomous keywords
        autonomous_keywords = [
            "autonomous", "background", "long-running", "unattended",
            "自主", "后台", "长时间", "无人值守",
        ]
        for kw in autonomous_keywords:
            if kw in task_lower:
                score += 0.4

        # Check for delegation indicators
        delegation_keywords = [
            "let it", "run this", "execute", "handle this",
            "take care of", "do this for me",
            "让它", "执行", "处理", "帮我",
        ]
        for kw in delegation_keywords:
            if kw in task_lower:
                score += 0.2

        # Check for long task indicators
        long_task_keywords = [
            "entire", "all files", "whole project", "complete",
            "migration", "refactor all", "update all",
            "整个", "所有文件", "完整", "迁移",
        ]
        for kw in long_task_keywords:
            if kw in task_lower:
                score += 0.2

        return min(1.0, score)

    @classmethod
    def format_task(cls, task: str, context: Dict[str, Any]) -> str:
        """Format a task with context for execution."""
        parts = [cls.SYSTEM_PROMPT, "", "Task:", task]

        if context.get("working_dir"):
            parts.extend(["", f"Working directory: {context['working_dir']}"])

        if context.get("files"):
            parts.extend(["", "Scope:", ", ".join(context["files"])])

        if context.get("constraints"):
            parts.extend(["", "Constraints:", context["constraints"]])

        if context.get("checkpoints"):
            parts.extend(["", "Checkpoints:", "\n".join(f"- {c}" for c in context["checkpoints"])])

        return "\n".join(parts)
