"""
Workflow Agent - Workflow Automation Specialist

Orchestrates multi-step workflows and automation tasks.
"""
from __future__ import annotations

from typing import Optional, List, Dict, Any

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from agent_registry import AgentConfig, AgentCapability


class WorkflowAgent:
    """
    Workflow automation specialist agent.

    Capabilities:
    - Multi-step workflow orchestration
    - Task automation and scheduling
    - Pipeline creation and management
    - Process optimization
    """

    NAME = "workflow"
    DESCRIPTION = "Workflow automation specialist. Orchestrates multi-step tasks and automation."

    SYSTEM_PROMPT = """You are Workflow, a workflow automation specialist.

Your role is to design and orchestrate multi-step workflows and automation tasks.

Guidelines:
1. Break complex tasks into sequential or parallel steps
2. Identify dependencies between steps
3. Handle errors and retries gracefully
4. Optimize for efficiency and reliability
5. Provide clear progress tracking
6. Support rollback when needed

Workflow design principles:
- Idempotent operations where possible
- Clear input/output contracts between steps
- Proper error handling and recovery
- Logging and observability
- Resource cleanup on failure

Output format:
- Workflow overview
- Step-by-step breakdown
- Dependencies and ordering
- Error handling strategy
- Expected outcomes
"""

    CAPABILITIES = [
        AgentCapability.WORKFLOW,
        AgentCapability.AUTOMATION,
    ]

    PREFERRED_PROVIDERS = ["iflow", "droid"]
    FALLBACK_PROVIDERS = ["claude", "codex"]

    TOOLS = [
        "bash",
        "read",
        "file_write",
        "glob",
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

        # Check for workflow keywords
        workflow_keywords = [
            "workflow", "pipeline", "automate", "automation",
            "orchestrate", "schedule", "batch", "process",
            "step", "sequence", "parallel",
            "工作流", "流程", "自动化", "编排", "批处理",
        ]
        for kw in workflow_keywords:
            if kw in task_lower:
                score += 0.3

        # Check for multi-step indicators
        multistep_keywords = [
            "then", "after", "before", "first", "next", "finally",
            "multi-step", "multiple steps", "series of",
            "然后", "之后", "首先", "接下来", "最后",
        ]
        for kw in multistep_keywords:
            if kw in task_lower:
                score += 0.2

        return min(1.0, score)

    @classmethod
    def format_task(cls, task: str, context: Dict[str, Any]) -> str:
        """Format a task with context for execution."""
        parts = [cls.SYSTEM_PROMPT, "", "Workflow Request:", task]

        if context.get("steps"):
            parts.extend(["", "Predefined steps:", "\n".join(f"- {s}" for s in context["steps"])])

        if context.get("constraints"):
            parts.extend(["", "Constraints:", context["constraints"]])

        return "\n".join(parts)
