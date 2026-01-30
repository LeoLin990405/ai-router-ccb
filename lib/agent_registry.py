"""
Agent Registry for CCB

Defines specialized agents with specific capabilities and provider mappings.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List, Dict, Any
from pathlib import Path
import yaml


class AgentCapability(Enum):
    """Agent capability types."""
    # Core capabilities
    CODE_WRITE = "code_write"
    CODE_REFACTOR = "code_refactor"
    CODE_REVIEW = "code_review"
    REASONING = "reasoning"
    ANALYSIS = "analysis"
    DOCUMENTATION = "documentation"
    NAVIGATION = "navigation"
    FRONTEND = "frontend"
    BACKEND = "backend"
    TESTING = "testing"
    # Extended capabilities (Phase 4G)
    WORKFLOW = "workflow"           # Workflow orchestration
    AUTOMATION = "automation"       # Task automation
    MULTILINGUAL = "multilingual"   # Multilingual processing
    TRANSLATION = "translation"     # Translation tasks
    AUTONOMOUS = "autonomous"       # Self-directed execution
    LONG_RUNNING = "long_running"   # Long-running tasks


@dataclass
class AgentConfig:
    """Configuration for a specialized agent."""
    name: str
    description: str
    capabilities: List[AgentCapability] = field(default_factory=list)
    preferred_providers: List[str] = field(default_factory=list)
    fallback_providers: List[str] = field(default_factory=list)
    tools: List[str] = field(default_factory=list)
    system_prompt: str = ""
    enabled: bool = True
    max_iterations: int = 10
    temperature: float = 0.7


@dataclass
class AgentMatch:
    """Result of matching a task to an agent."""
    agent: str
    confidence: float
    matched_capabilities: List[AgentCapability]
    reason: str


class AgentRegistry:
    """
    Registry of specialized agents.

    Each agent has specific capabilities and preferred providers.
    """

    # Default agent configurations
    DEFAULT_AGENTS: Dict[str, AgentConfig] = {
        "sisyphus": AgentConfig(
            name="sisyphus",
            description="Code implementation specialist. Writes, modifies, and refactors code.",
            capabilities=[
                AgentCapability.CODE_WRITE,
                AgentCapability.CODE_REFACTOR,
                AgentCapability.BACKEND,
            ],
            preferred_providers=["codex", "gemini"],
            fallback_providers=["claude", "opencode"],
            tools=["file_write", "file_edit", "bash", "grep", "glob"],
            system_prompt="""You are Sisyphus, a code implementation specialist.
Your role is to write clean, efficient, and well-documented code.
Focus on:
- Writing production-ready code
- Following best practices and design patterns
- Proper error handling
- Clear variable and function naming
""",
        ),
        "oracle": AgentConfig(
            name="oracle",
            description="Deep reasoning and analysis specialist. Solves complex problems.",
            capabilities=[
                AgentCapability.REASONING,
                AgentCapability.ANALYSIS,
            ],
            preferred_providers=["deepseek", "claude"],
            fallback_providers=["gemini", "codex"],
            tools=["read", "grep", "web_search"],
            system_prompt="""You are Oracle, a deep reasoning specialist.
Your role is to analyze complex problems and provide thorough solutions.
Focus on:
- Breaking down complex problems
- Considering edge cases
- Providing step-by-step reasoning
- Mathematical and algorithmic analysis
""",
        ),
        "librarian": AgentConfig(
            name="librarian",
            description="Documentation and knowledge specialist. Queries docs and explains code.",
            capabilities=[
                AgentCapability.DOCUMENTATION,
                AgentCapability.ANALYSIS,
            ],
            preferred_providers=["claude", "gemini"],
            fallback_providers=["codex", "kimi"],
            tools=["read", "context7", "web_search", "grep"],
            system_prompt="""You are Librarian, a documentation specialist.
Your role is to find and explain documentation and code.
Focus on:
- Finding relevant documentation
- Explaining complex concepts clearly
- Providing code examples
- Answering technical questions
""",
        ),
        "explorer": AgentConfig(
            name="explorer",
            description="Codebase navigation specialist. Finds files, functions, and patterns.",
            capabilities=[
                AgentCapability.NAVIGATION,
                AgentCapability.ANALYSIS,
            ],
            preferred_providers=["gemini", "claude"],
            fallback_providers=["codex", "opencode"],
            tools=["glob", "grep", "read", "bash"],
            system_prompt="""You are Explorer, a codebase navigation specialist.
Your role is to help navigate and understand codebases.
Focus on:
- Finding relevant files and functions
- Understanding code structure
- Tracing code flow
- Identifying patterns and dependencies
""",
        ),
        "frontend": AgentConfig(
            name="frontend",
            description="Frontend development specialist. React, Vue, CSS, and UI/UX.",
            capabilities=[
                AgentCapability.FRONTEND,
                AgentCapability.CODE_WRITE,
            ],
            preferred_providers=["gemini", "claude"],
            fallback_providers=["codex", "opencode"],
            tools=["file_write", "file_edit", "read", "glob"],
            system_prompt="""You are Frontend, a frontend development specialist.
Your role is to build beautiful and functional user interfaces.
Focus on:
- React, Vue, and modern frameworks
- CSS and responsive design
- Accessibility and UX best practices
- Component architecture
""",
        ),
        "reviewer": AgentConfig(
            name="reviewer",
            description="Code review specialist. Reviews code for quality and issues.",
            capabilities=[
                AgentCapability.CODE_REVIEW,
                AgentCapability.ANALYSIS,
                AgentCapability.TESTING,
            ],
            preferred_providers=["gemini", "claude"],
            fallback_providers=["codex", "deepseek"],
            tools=["read", "grep", "glob"],
            system_prompt="""You are Reviewer, a code review specialist.
Your role is to review code for quality, bugs, and improvements.
Focus on:
- Code quality and readability
- Potential bugs and edge cases
- Performance issues
- Security vulnerabilities
- Best practices adherence
""",
        ),
        # Phase 4G: New agents for full provider coverage
        "workflow": AgentConfig(
            name="workflow",
            description="Workflow automation specialist. Orchestrates multi-step tasks.",
            capabilities=[
                AgentCapability.WORKFLOW,
                AgentCapability.AUTOMATION,
            ],
            preferred_providers=["iflow", "droid"],
            fallback_providers=["claude", "codex"],
            tools=["bash", "read", "file_write", "glob"],
            system_prompt="""You are Workflow, a workflow automation specialist.
Your role is to design and orchestrate multi-step workflows.
Focus on:
- Breaking complex tasks into steps
- Identifying dependencies
- Error handling and recovery
- Progress tracking
""",
        ),
        "polyglot": AgentConfig(
            name="polyglot",
            description="Multilingual specialist. Handles translation and long-context tasks.",
            capabilities=[
                AgentCapability.MULTILINGUAL,
                AgentCapability.TRANSLATION,
                AgentCapability.DOCUMENTATION,
            ],
            preferred_providers=["kimi", "qwen"],
            fallback_providers=["claude", "gemini"],
            tools=["read", "file_write", "file_edit"],
            system_prompt="""You are Polyglot, a multilingual specialist.
Your role is to handle translation and multilingual tasks.
Focus on:
- Preserving meaning in translations
- Technical accuracy
- Long document handling
- Natural, fluent output
""",
        ),
        "autonomous": AgentConfig(
            name="autonomous",
            description="Autonomous execution specialist. Handles long-running tasks.",
            capabilities=[
                AgentCapability.AUTONOMOUS,
                AgentCapability.LONG_RUNNING,
                AgentCapability.CODE_WRITE,
            ],
            preferred_providers=["droid", "codex"],
            fallback_providers=["claude", "opencode"],
            tools=["bash", "read", "file_write", "file_edit", "glob", "grep"],
            system_prompt="""You are Autonomous, a self-directed task execution specialist.
Your role is to handle long-running tasks with minimal supervision.
Focus on:
- Planning complete tasks
- Progress checkpoints
- Autonomous error handling
- Clear status reporting
""",
            max_iterations=20,
        ),
    }

    # Capability to keyword mapping for task matching
    CAPABILITY_KEYWORDS: Dict[AgentCapability, List[str]] = {
        AgentCapability.CODE_WRITE: [
            "implement", "write", "create", "add", "build", "develop",
            "实现", "编写", "创建", "添加", "开发",
        ],
        AgentCapability.CODE_REFACTOR: [
            "refactor", "improve", "optimize", "clean", "restructure",
            "重构", "优化", "改进", "清理",
        ],
        AgentCapability.CODE_REVIEW: [
            "review", "check", "audit", "inspect", "examine",
            "审查", "检查", "审计",
        ],
        AgentCapability.REASONING: [
            "analyze", "reason", "think", "deduce", "solve", "algorithm",
            "分析", "推理", "思考", "算法", "解决",
        ],
        AgentCapability.ANALYSIS: [
            "understand", "explain", "investigate", "debug", "trace",
            "理解", "解释", "调查", "调试",
        ],
        AgentCapability.DOCUMENTATION: [
            "document", "docs", "explain", "describe", "comment",
            "文档", "说明", "描述", "注释",
        ],
        AgentCapability.NAVIGATION: [
            "find", "search", "locate", "where", "navigate",
            "查找", "搜索", "定位", "导航",
        ],
        AgentCapability.FRONTEND: [
            "react", "vue", "angular", "css", "ui", "component", "frontend",
            "前端", "组件", "界面", "样式",
        ],
        AgentCapability.BACKEND: [
            "api", "server", "database", "backend", "endpoint",
            "后端", "接口", "数据库", "服务器",
        ],
        AgentCapability.TESTING: [
            "test", "spec", "coverage", "mock", "assert",
            "测试", "断言", "覆盖率",
        ],
        # Phase 4G: New capability keywords
        AgentCapability.WORKFLOW: [
            "workflow", "pipeline", "automate", "automation", "orchestrate",
            "schedule", "batch", "process", "sequence",
            "工作流", "流程", "自动化", "编排", "批处理",
        ],
        AgentCapability.AUTOMATION: [
            "automate", "script", "cron", "scheduled", "recurring",
            "自动", "脚本", "定时", "循环",
        ],
        AgentCapability.MULTILINGUAL: [
            "multilingual", "multi-language", "localize", "i18n", "l10n",
            "多语言", "本地化", "国际化",
        ],
        AgentCapability.TRANSLATION: [
            "translate", "translation", "convert to chinese", "convert to english",
            "翻译", "译成", "转换",
        ],
        AgentCapability.AUTONOMOUS: [
            "autonomous", "background", "unattended", "self-directed",
            "自主", "后台", "无人值守",
        ],
        AgentCapability.LONG_RUNNING: [
            "long-running", "long task", "entire project", "all files",
            "长时间", "整个项目", "所有文件",
        ],
    }

    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize the agent registry.

        Args:
            config_path: Optional path to YAML configuration file
        """
        self.agents: Dict[str, AgentConfig] = {**self.DEFAULT_AGENTS}

        if config_path:
            self._load_config(config_path)
        else:
            # Try default config location
            default_path = Path.home() / ".ccb_config" / "agents.yaml"
            if default_path.exists():
                self._load_config(str(default_path))

    def _load_config(self, config_path: str) -> None:
        """Load agent configurations from YAML file."""
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f) or {}

            for agent_data in config.get("agents", []):
                name = agent_data.get("name")
                if not name:
                    continue

                capabilities = [
                    AgentCapability(c) for c in agent_data.get("capabilities", [])
                    if c in [e.value for e in AgentCapability]
                ]

                agent = AgentConfig(
                    name=name,
                    description=agent_data.get("description", ""),
                    capabilities=capabilities,
                    preferred_providers=agent_data.get("preferred_providers", []),
                    fallback_providers=agent_data.get("fallback_providers", []),
                    tools=agent_data.get("tools", []),
                    system_prompt=agent_data.get("system_prompt", ""),
                    enabled=agent_data.get("enabled", True),
                    max_iterations=agent_data.get("max_iterations", 10),
                    temperature=agent_data.get("temperature", 0.7),
                )
                self.agents[name] = agent

        except Exception as e:
            print(f"Warning: Failed to load agent config from {config_path}: {e}")

    def get_agent(self, name: str) -> Optional[AgentConfig]:
        """Get an agent by name."""
        return self.agents.get(name)

    def list_agents(self) -> List[AgentConfig]:
        """List all registered agents."""
        return [a for a in self.agents.values() if a.enabled]

    def match_task(self, task: str, files: Optional[List[str]] = None) -> AgentMatch:
        """
        Match a task to the best agent.

        Args:
            task: The task description
            files: Optional list of files involved

        Returns:
            AgentMatch with the best agent and confidence
        """
        task_lower = task.lower()
        scores: Dict[str, tuple] = {}  # agent -> (score, matched_capabilities)

        for agent_name, agent in self.agents.items():
            if not agent.enabled:
                continue

            score = 0.0
            matched_caps = []

            # Score based on capability keywords
            for cap in agent.capabilities:
                keywords = self.CAPABILITY_KEYWORDS.get(cap, [])
                for keyword in keywords:
                    if keyword.lower() in task_lower:
                        score += 1.0
                        if cap not in matched_caps:
                            matched_caps.append(cap)

            # Bonus for file pattern matching
            if files:
                for f in files:
                    f_lower = f.lower()
                    if AgentCapability.FRONTEND in agent.capabilities:
                        if any(ext in f_lower for ext in ['.tsx', '.jsx', '.vue', '.css', '.scss']):
                            score += 0.5
                    if AgentCapability.BACKEND in agent.capabilities:
                        if any(ext in f_lower for ext in ['.go', '.rs', '.py', '.java']):
                            score += 0.5
                        if any(path in f_lower for path in ['api/', 'routes/', 'controllers/']):
                            score += 0.5

            if score > 0:
                scores[agent_name] = (score, matched_caps)

        if not scores:
            # Default to librarian for general queries
            return AgentMatch(
                agent="librarian",
                confidence=0.5,
                matched_capabilities=[AgentCapability.DOCUMENTATION],
                reason="Default agent for general queries",
            )

        # Find best match
        best_agent = max(scores, key=lambda a: scores[a][0])
        best_score, matched_caps = scores[best_agent]

        # Normalize confidence (0-1)
        max_possible = len(self.agents[best_agent].capabilities) * 2
        confidence = min(1.0, best_score / max_possible)

        return AgentMatch(
            agent=best_agent,
            confidence=confidence,
            matched_capabilities=matched_caps,
            reason=f"Matched capabilities: {', '.join(c.value for c in matched_caps)}",
        )

    def get_provider_for_agent(self, agent_name: str) -> Optional[str]:
        """Get the preferred provider for an agent."""
        agent = self.agents.get(agent_name)
        if not agent or not agent.preferred_providers:
            return None
        return agent.preferred_providers[0]

    def register_agent(self, agent: AgentConfig) -> None:
        """Register a new agent."""
        self.agents[agent.name] = agent


# Singleton instance
_agent_registry: Optional[AgentRegistry] = None


def get_agent_registry() -> AgentRegistry:
    """Get the global agent registry instance."""
    global _agent_registry
    if _agent_registry is None:
        _agent_registry = AgentRegistry()
    return _agent_registry
