"""
Skills Loader for CCB

Provides extensible skill plugins for CCB.
"""
from __future__ import annotations

import importlib.util
import json
import re
import traceback
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, List, Dict, Any, Callable


@dataclass
class SkillParameter:
    """A skill parameter definition."""
    name: str
    type: str  # string, int, float, bool, list, dict
    description: str = ""
    required: bool = False
    default: Any = None


@dataclass
class SkillConfig:
    """Configuration for a skill."""
    name: str
    description: str
    version: str = "1.0.0"
    author: str = ""
    parameters: List[SkillParameter] = field(default_factory=list)
    triggers: List[str] = field(default_factory=list)
    enabled: bool = True
    path: str = ""


@dataclass
class SkillResult:
    """Result from skill execution."""
    success: bool
    output: Any = None
    error: Optional[str] = None
    skill_name: str = ""


def _warn(message: str) -> None:
    sys.stderr.write(f"{message}\n")


HANDLED_EXCEPTIONS = (Exception,)


class SkillLoader:
    """
    Skills loader for CCB.

    Features:
    - Load skills from directory
    - Execute skills with parameters
    - Skill discovery and matching
    - YAML/JSON skill definitions
    """

    def __init__(self, skills_dir: Optional[str] = None):
        """
        Initialize the skills loader.

        Args:
            skills_dir: Directory containing skill definitions
        """
        self._skills_dir = skills_dir or str(Path.home() / ".ccb_config" / "skills")
        self._skills: Dict[str, SkillConfig] = {}
        self._handlers: Dict[str, Callable] = {}

    def load_skills(self) -> int:
        """
        Load all skills from the skills directory.

        Returns:
            Number of skills loaded
        """
        skills_path = Path(self._skills_dir)
        if not skills_path.exists():
            skills_path.mkdir(parents=True, exist_ok=True)
            return 0

        count = 0

        # Load from subdirectories (each skill in its own folder)
        for skill_dir in skills_path.iterdir():
            if skill_dir.is_dir():
                skill = self._load_skill_from_dir(skill_dir)
                if skill:
                    self._skills[skill.name] = skill
                    count += 1

        # Load from single files
        for skill_file in skills_path.glob("*.py"):
            skill = self._load_skill_from_file(skill_file)
            if skill:
                self._skills[skill.name] = skill
                count += 1

        return count

    def _load_skill_from_dir(self, skill_dir: Path) -> Optional[SkillConfig]:
        """Load a skill from a directory."""
        # Look for SKILL.md, skill.yaml, or skill.json
        config_file = None
        for name in ["SKILL.md", "skill.yaml", "skill.yml", "skill.json"]:
            if (skill_dir / name).exists():
                config_file = skill_dir / name
                break

        if not config_file:
            return None

        try:
            config = self._parse_skill_config(config_file)
            if not config:
                return None

            config.path = str(skill_dir)

            # Load handler if exists
            handler_file = skill_dir / "handler.py"
            if handler_file.exists():
                handler = self._load_handler(handler_file)
                if handler:
                    self._handlers[config.name] = handler

            return config

        except HANDLED_EXCEPTIONS as e:
            _warn(f"Failed to load skill from {skill_dir}: {e}")
            return None

    def _load_skill_from_file(self, skill_file: Path) -> Optional[SkillConfig]:
        """Load a skill from a single Python file."""
        try:
            spec = importlib.util.spec_from_file_location(
                skill_file.stem, skill_file
            )
            if not spec or not spec.loader:
                return None

            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            # Look for SKILL_CONFIG
            if not hasattr(module, "SKILL_CONFIG"):
                return None

            config_dict = module.SKILL_CONFIG
            config = SkillConfig(
                name=config_dict.get("name", skill_file.stem),
                description=config_dict.get("description", ""),
                version=config_dict.get("version", "1.0.0"),
                author=config_dict.get("author", ""),
                triggers=config_dict.get("triggers", []),
                path=str(skill_file),
            )

            # Parse parameters
            for param in config_dict.get("parameters", []):
                config.parameters.append(SkillParameter(
                    name=param.get("name", ""),
                    type=param.get("type", "string"),
                    description=param.get("description", ""),
                    required=param.get("required", False),
                    default=param.get("default"),
                ))

            # Load handler
            if hasattr(module, "execute"):
                self._handlers[config.name] = module.execute

            return config

        except HANDLED_EXCEPTIONS as e:
            _warn(f"Failed to load skill from {skill_file}: {e}")
            return None

    def _parse_skill_config(self, config_file: Path) -> Optional[SkillConfig]:
        """Parse a skill configuration file."""
        content = config_file.read_text()

        if config_file.suffix == ".md":
            return self._parse_skill_md(content, config_file)
        elif config_file.suffix in (".yaml", ".yml"):
            return self._parse_skill_yaml(content)
        elif config_file.suffix == ".json":
            return self._parse_skill_json(content)

        return None

    def _parse_skill_md(self, content: str, config_file: Path) -> Optional[SkillConfig]:
        """Parse SKILL.md format with YAML frontmatter."""
        # Extract YAML frontmatter
        match = re.match(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
        if not match:
            return None

        frontmatter = match.group(1)
        return self._parse_skill_yaml(frontmatter)

    def _parse_skill_yaml(self, content: str) -> Optional[SkillConfig]:
        """Parse YAML skill config."""
        try:
            import yaml
            data = yaml.safe_load(content)
        except ImportError:
            # Fallback to simple parsing
            data = self._simple_yaml_parse(content)
        except HANDLED_EXCEPTIONS:
            return None

        if not data:
            return None

        config = SkillConfig(
            name=data.get("name", ""),
            description=data.get("description", ""),
            version=data.get("version", "1.0.0"),
            author=data.get("author", ""),
            triggers=data.get("triggers", []),
        )

        for param in data.get("parameters", []):
            config.parameters.append(SkillParameter(
                name=param.get("name", ""),
                type=param.get("type", "string"),
                description=param.get("description", ""),
                required=param.get("required", False),
                default=param.get("default"),
            ))

        return config

    def _parse_skill_json(self, content: str) -> Optional[SkillConfig]:
        """Parse JSON skill config."""
        try:
            data = json.loads(content)
        except HANDLED_EXCEPTIONS:
            return None

        config = SkillConfig(
            name=data.get("name", ""),
            description=data.get("description", ""),
            version=data.get("version", "1.0.0"),
            author=data.get("author", ""),
            triggers=data.get("triggers", []),
        )

        for param in data.get("parameters", []):
            config.parameters.append(SkillParameter(
                name=param.get("name", ""),
                type=param.get("type", "string"),
                description=param.get("description", ""),
                required=param.get("required", False),
                default=param.get("default"),
            ))

        return config

    def _simple_yaml_parse(self, content: str) -> Dict[str, Any]:
        """Simple YAML parser for basic key-value pairs."""
        result = {}
        current_list = None
        current_key = None

        for line in content.split("\n"):
            line = line.rstrip()
            if not line or line.startswith("#"):
                continue

            # List item
            if line.strip().startswith("- "):
                if current_key and current_list is not None:
                    current_list.append(line.strip()[2:])
                continue

            # Key-value pair
            if ":" in line:
                key, _, value = line.partition(":")
                key = key.strip()
                value = value.strip()

                if value:
                    result[key] = value
                    current_key = None
                    current_list = None
                else:
                    # Start of list or nested object
                    result[key] = []
                    current_key = key
                    current_list = result[key]

        return result

    def _load_handler(self, handler_file: Path) -> Optional[Callable]:
        """Load a handler function from a Python file."""
        try:
            spec = importlib.util.spec_from_file_location(
                handler_file.stem, handler_file
            )
            if not spec or not spec.loader:
                return None

            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            if hasattr(module, "execute"):
                return module.execute

            return None

        except HANDLED_EXCEPTIONS as e:
            _warn(f"Failed to load handler from {handler_file}: {e}")
            return None

    def register_skill(
        self,
        config: SkillConfig,
        handler: Optional[Callable] = None,
    ) -> None:
        """
        Register a skill programmatically.

        Args:
            config: Skill configuration
            handler: Handler function
        """
        self._skills[config.name] = config
        if handler:
            self._handlers[config.name] = handler

    def get_skill(self, name: str) -> Optional[SkillConfig]:
        """Get a skill by name."""
        return self._skills.get(name)

    def list_skills(self) -> List[SkillConfig]:
        """List all loaded skills."""
        return list(self._skills.values())

    def execute_skill(
        self,
        name: str,
        args: Optional[Dict[str, Any]] = None,
    ) -> SkillResult:
        """
        Execute a skill.

        Args:
            name: Skill name
            args: Arguments to pass to the skill

        Returns:
            SkillResult
        """
        skill = self._skills.get(name)
        if not skill:
            return SkillResult(
                success=False,
                error=f"Skill '{name}' not found",
                skill_name=name,
            )

        if not skill.enabled:
            return SkillResult(
                success=False,
                error=f"Skill '{name}' is disabled",
                skill_name=name,
            )

        handler = self._handlers.get(name)
        if not handler:
            return SkillResult(
                success=False,
                error=f"No handler for skill '{name}'",
                skill_name=name,
            )

        # Validate required parameters
        args = args or {}
        for param in skill.parameters:
            if param.required and param.name not in args:
                return SkillResult(
                    success=False,
                    error=f"Missing required parameter: {param.name}",
                    skill_name=name,
                )
            # Apply defaults
            if param.name not in args and param.default is not None:
                args[param.name] = param.default

        try:
            result = handler(args)
            return SkillResult(
                success=True,
                output=result,
                skill_name=name,
            )
        except HANDLED_EXCEPTIONS as e:
            return SkillResult(
                success=False,
                error=f"{type(e).__name__}: {str(e)}",
                skill_name=name,
            )

    def match_skill(self, query: str) -> Optional[SkillConfig]:
        """
        Find a skill that matches a query.

        Args:
            query: Query string

        Returns:
            Matching skill or None
        """
        query_lower = query.lower()

        for skill in self._skills.values():
            if not skill.enabled:
                continue

            # Check triggers
            for trigger in skill.triggers:
                if trigger.lower() in query_lower:
                    return skill

            # Check name
            if skill.name.lower() in query_lower:
                return skill

        return None

    def enable_skill(self, name: str) -> bool:
        """Enable a skill."""
        if name in self._skills:
            self._skills[name].enabled = True
            return True
        return False

    def disable_skill(self, name: str) -> bool:
        """Disable a skill."""
        if name in self._skills:
            self._skills[name].enabled = False
            return True
        return False

    def get_skill_stats(self) -> Dict[str, Any]:
        """Get statistics about loaded skills."""
        enabled = sum(1 for s in self._skills.values() if s.enabled)
        with_handlers = sum(1 for n in self._skills if n in self._handlers)

        return {
            "total_skills": len(self._skills),
            "enabled_skills": enabled,
            "disabled_skills": len(self._skills) - enabled,
            "with_handlers": with_handlers,
            "skills_dir": self._skills_dir,
        }


# Singleton instance
_skills_loader: Optional[SkillLoader] = None


def get_skills_loader() -> SkillLoader:
    """Get the global skills loader instance."""
    global _skills_loader
    if _skills_loader is None:
        _skills_loader = SkillLoader()
    return _skills_loader
