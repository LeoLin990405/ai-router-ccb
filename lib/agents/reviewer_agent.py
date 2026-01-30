"""
Reviewer Agent - Code Review Specialist

Reviews code for quality, security, and best practices.
"""
from __future__ import annotations

from typing import Optional, List, Dict, Any

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from agent_registry import AgentConfig, AgentCapability


class ReviewerAgent:
    """
    Code review specialist agent.

    Capabilities:
    - Code quality review
    - Security vulnerability detection
    - Best practices validation
    - Performance analysis
    - Test coverage assessment
    """

    NAME = "reviewer"
    DESCRIPTION = "Code review specialist. Reviews code for quality, security, and best practices."

    SYSTEM_PROMPT = """You are Reviewer, a code review specialist.

Your role is to review code for quality, bugs, security issues, and improvements.

Guidelines:
1. Check for code quality and readability
2. Identify potential bugs and edge cases
3. Look for security vulnerabilities (OWASP Top 10)
4. Assess performance implications
5. Verify best practices adherence
6. Check test coverage adequacy

Review checklist:
- Logic errors and edge cases
- Input validation and sanitization
- Error handling completeness
- Resource management (memory, connections)
- Concurrency issues (race conditions, deadlocks)
- Security (injection, XSS, CSRF, auth issues)
- Performance (N+1 queries, unnecessary loops)
- Code style and naming conventions

Output format:
- Summary of findings
- Critical issues (must fix)
- Warnings (should fix)
- Suggestions (nice to have)
- Positive observations
"""

    CAPABILITIES = [
        AgentCapability.CODE_REVIEW,
        AgentCapability.ANALYSIS,
        AgentCapability.TESTING,
    ]

    PREFERRED_PROVIDERS = ["gemini", "claude"]
    FALLBACK_PROVIDERS = ["codex", "deepseek"]

    TOOLS = [
        "read",
        "grep",
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

        # Check for review keywords
        review_keywords = [
            "review", "check", "audit", "inspect", "examine",
            "security", "vulnerability", "bug", "issue",
            "quality", "best practice", "code smell",
            "审查", "检查", "审计", "安全", "漏洞", "质量",
        ]
        for kw in review_keywords:
            if kw in task_lower:
                score += 0.3

        # Check for testing keywords
        test_keywords = [
            "test", "coverage", "spec", "unit test", "integration",
            "测试", "覆盖率",
        ]
        for kw in test_keywords:
            if kw in task_lower:
                score += 0.2

        return min(1.0, score)

    @classmethod
    def format_task(cls, task: str, context: Dict[str, Any]) -> str:
        """Format a task with context for execution."""
        parts = [cls.SYSTEM_PROMPT, "", "Review Request:", task]

        if context.get("files"):
            parts.extend(["", "Files to review:", ", ".join(context["files"])])

        if context.get("focus_areas"):
            parts.extend(["", "Focus areas:", context["focus_areas"]])

        return "\n".join(parts)
