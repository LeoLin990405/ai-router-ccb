"""
Agent Executor for CCB

Executes tasks using specialized agents with provider routing.
"""
from __future__ import annotations

import subprocess
import time
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Callable
from pathlib import Path

from agent_registry import (
    AgentRegistry, AgentConfig, AgentCapability, AgentMatch,
    get_agent_registry,
)
from provider_commands import PROVIDER_COMMANDS, get_ask_command


@dataclass
class AgentContext:
    """Context for agent execution."""
    task: str
    files: List[str] = field(default_factory=list)
    working_dir: str = "."
    max_iterations: int = 10
    timeout_s: float = 300.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentResult:
    """Result of agent execution."""
    agent: str
    provider: str
    success: bool
    response: Optional[str] = None
    error: Optional[str] = None
    iterations: int = 0
    latency_ms: float = 0.0
    delegations: List["AgentResult"] = field(default_factory=list)


class AgentExecutor:
    """
    Executes tasks using specialized agents.

    Features:
    - Agent selection based on task
    - Provider routing per agent
    - Task delegation between agents
    - Iteration tracking
    """

    # Use unified provider commands from provider_commands module
    PROVIDER_COMMANDS = PROVIDER_COMMANDS

    def __init__(
        self,
        registry: Optional[AgentRegistry] = None,
        on_iteration: Optional[Callable[[int, str], None]] = None,
    ):
        """
        Initialize the agent executor.

        Args:
            registry: Optional agent registry (uses global if not provided)
            on_iteration: Optional callback for iteration updates
        """
        self.registry = registry or get_agent_registry()
        self.on_iteration = on_iteration
        self._execution_stack: List[str] = []  # Track delegation depth

    def execute(
        self,
        agent_name: str,
        task: str,
        context: Optional[AgentContext] = None,
    ) -> AgentResult:
        """
        Execute a task with a specific agent.

        Args:
            agent_name: Name of the agent to use
            task: The task to execute
            context: Optional execution context

        Returns:
            AgentResult with the response
        """
        start_time = time.time()

        # Get agent config
        agent = self.registry.get_agent(agent_name)
        if not agent:
            return AgentResult(
                agent=agent_name,
                provider="unknown",
                success=False,
                error=f"Agent '{agent_name}' not found",
                latency_ms=(time.time() - start_time) * 1000,
            )

        if not agent.enabled:
            return AgentResult(
                agent=agent_name,
                provider="unknown",
                success=False,
                error=f"Agent '{agent_name}' is disabled",
                latency_ms=(time.time() - start_time) * 1000,
            )

        # Check for circular delegation
        if agent_name in self._execution_stack:
            return AgentResult(
                agent=agent_name,
                provider="unknown",
                success=False,
                error=f"Circular delegation detected: {' -> '.join(self._execution_stack)} -> {agent_name}",
                latency_ms=(time.time() - start_time) * 1000,
            )

        self._execution_stack.append(agent_name)

        try:
            # Select provider
            provider = self._select_provider(agent)

            # Build prompt with agent context
            prompt = self._build_prompt(agent, task, context)

            # Execute with provider
            result = self._execute_with_provider(
                provider=provider,
                prompt=prompt,
                timeout_s=context.timeout_s if context else agent.max_iterations * 30,
            )

            latency_ms = (time.time() - start_time) * 1000

            if result["success"]:
                return AgentResult(
                    agent=agent_name,
                    provider=provider,
                    success=True,
                    response=result["response"],
                    iterations=1,
                    latency_ms=latency_ms,
                )
            else:
                # Try fallback providers
                for fallback in agent.fallback_providers:
                    result = self._execute_with_provider(
                        provider=fallback,
                        prompt=prompt,
                        timeout_s=context.timeout_s if context else 60,
                    )
                    if result["success"]:
                        return AgentResult(
                            agent=agent_name,
                            provider=fallback,
                            success=True,
                            response=result["response"],
                            iterations=1,
                            latency_ms=(time.time() - start_time) * 1000,
                        )

                return AgentResult(
                    agent=agent_name,
                    provider=provider,
                    success=False,
                    error=result.get("error", "Execution failed"),
                    latency_ms=(time.time() - start_time) * 1000,
                )

        finally:
            self._execution_stack.pop()

    def _select_provider(self, agent: AgentConfig) -> str:
        """Select the best provider for an agent."""
        if agent.preferred_providers:
            return agent.preferred_providers[0]
        return "claude"  # Default fallback

    def _build_prompt(
        self,
        agent: AgentConfig,
        task: str,
        context: Optional[AgentContext],
    ) -> str:
        """Build the prompt for agent execution."""
        parts = []

        # Add system prompt
        if agent.system_prompt:
            parts.append(f"[System]\n{agent.system_prompt}\n")

        # Add context
        if context:
            if context.files:
                parts.append(f"[Files]\n{', '.join(context.files)}\n")
            if context.working_dir != ".":
                parts.append(f"[Working Directory]\n{context.working_dir}\n")

        # Add task
        parts.append(f"[Task]\n{task}")

        return "\n".join(parts)

    def _execute_with_provider(
        self,
        provider: str,
        prompt: str,
        timeout_s: float,
    ) -> Dict[str, Any]:
        """Execute a prompt with a specific provider."""
        ask_cmd = self.PROVIDER_COMMANDS.get(provider, "lask")

        try:
            cmd = f"{ask_cmd} <<'EOF'\n{prompt}\nEOF"
            result = subprocess.run(
                ["bash", "-c", cmd],
                capture_output=True,
                text=True,
                timeout=timeout_s,
            )

            if result.returncode == 0:
                return {
                    "success": True,
                    "response": result.stdout,
                }
            else:
                return {
                    "success": False,
                    "error": result.stderr or f"Exit code: {result.returncode}",
                }

        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "error": "Timeout",
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }

    def delegate(
        self,
        from_agent: str,
        to_agent: str,
        subtask: str,
        context: Optional[AgentContext] = None,
    ) -> AgentResult:
        """
        Delegate a subtask from one agent to another.

        Args:
            from_agent: The delegating agent
            to_agent: The agent to delegate to
            subtask: The subtask to execute
            context: Optional execution context

        Returns:
            AgentResult from the delegated agent
        """
        # Add delegation context
        if context is None:
            context = AgentContext(task=subtask)

        context.metadata["delegated_from"] = from_agent

        return self.execute(to_agent, subtask, context)

    def auto_execute(
        self,
        task: str,
        files: Optional[List[str]] = None,
        context: Optional[AgentContext] = None,
    ) -> AgentResult:
        """
        Automatically select and execute the best agent for a task.

        Args:
            task: The task to execute
            files: Optional list of files involved
            context: Optional execution context

        Returns:
            AgentResult from the selected agent
        """
        # Match task to agent
        match = self.registry.match_task(task, files)

        # Create context if not provided
        if context is None:
            context = AgentContext(task=task, files=files or [])

        # Execute with matched agent
        return self.execute(match.agent, task, context)


def format_agent_result(result: AgentResult, verbose: bool = False) -> str:
    """Format an agent result for display."""
    lines = []

    if verbose:
        lines.append("=" * 60)
        lines.append(f"Agent:     {result.agent}")
        lines.append(f"Provider:  {result.provider}")
        lines.append(f"Success:   {result.success}")
        lines.append(f"Latency:   {result.latency_ms:.0f}ms")
        if result.iterations > 1:
            lines.append(f"Iterations: {result.iterations}")
        if result.delegations:
            lines.append(f"Delegations: {len(result.delegations)}")
        lines.append("=" * 60)
        lines.append("")

    if result.success and result.response:
        lines.append(result.response)
    elif result.error:
        lines.append(f"Error: {result.error}")

    return "\n".join(lines)


# Singleton instance
_agent_executor: Optional[AgentExecutor] = None


def get_agent_executor() -> AgentExecutor:
    """Get the global agent executor instance."""
    global _agent_executor
    if _agent_executor is None:
        _agent_executor = AgentExecutor()
    return _agent_executor
