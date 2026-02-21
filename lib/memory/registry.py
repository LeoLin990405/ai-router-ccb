#!/usr/bin/env python3
"""
CCB Registry System - Unified Skills & MCP Inventory

Maintains real-time inventory of:
- Claude Code skills
- MCP servers
- CCB providers
- Available models
"""

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional

import psutil

try:
    from lib.common.logging import get_logger
except ImportError:  # pragma: no cover - script mode
    try:
        from common.logging import get_logger  # type: ignore
    except ImportError:  # pragma: no cover - fallback
        import logging

        def get_logger(name: str):
            return logging.getLogger(name)


logger = get_logger("memory.registry")


def _emit(message: str = "") -> None:
    sys.stdout.write(f"{message}\n")


class CCBRegistry:
    """Registry for CCB capabilities."""

    def __init__(self, cache_path: Optional[Path] = None):
        self.cache_path = cache_path or Path.home() / ".ccb" / "registry_cache.json"
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)

        # Key paths
        self.claude_skills_dir = Path.home() / ".claude" / "skills"
        self.ccb_skills_dir = Path.home() / ".local" / "share" / "codex-dual" / "skills"

    def scan_skills(self) -> List[Dict[str, Any]]:
        """Scan all available skills from ~/.claude/skills."""
        skills = []

        if not self.claude_skills_dir.exists():
            return skills

        for skill_dir in self.claude_skills_dir.iterdir():
            if not skill_dir.is_dir():
                continue

            skill_md = skill_dir / "SKILL.md"
            if not skill_md.exists():
                continue

            try:
                skill_info = self._parse_skill_md(skill_md)
                skill_info["location"] = str(skill_dir)
                skills.append(skill_info)
            except (OSError, ValueError, TypeError, KeyError, AttributeError) as e:
                logger.warning("Failed to parse %s: %s", skill_dir.name, e)

        return skills

    def _parse_skill_md(self, skill_md: Path) -> Dict[str, Any]:
        """Parse SKILL.md frontmatter and extract metadata."""
        with open(skill_md) as f:
            content = f.read()

        # Simple frontmatter parser
        info = {"name": skill_md.parent.name, "description": "", "triggers": []}

        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                frontmatter = parts[1]
                for line in frontmatter.split("\n"):
                    line = line.strip()
                    if line.startswith("name:"):
                        info["name"] = line.split(":", 1)[1].strip()
                    elif line.startswith("description:"):
                        info["description"] = line.split(":", 1)[1].strip()
                    elif line.startswith("  - "):
                        info["triggers"].append(line[4:].strip())

        # Fallback: extract first line as description
        if not info["description"]:
            lines = content.split("\n")
            for line in lines:
                line = line.strip()
                if line and not line.startswith("#") and not line.startswith("---"):
                    info["description"] = line[:200]
                    break

        return info

    def scan_mcp_servers(self) -> List[Dict[str, Any]]:
        """Scan running MCP servers from processes."""
        mcp_servers = []

        for proc in psutil.process_iter(["pid", "name", "cmdline"]):
            try:
                cmdline = proc.info.get("cmdline", [])
                if not cmdline:
                    continue

                cmdline_str = " ".join(cmdline)

                # Detect MCP servers
                if "mcp" in cmdline_str.lower():
                    server_info = {
                        "pid": proc.info["pid"],
                        "name": self._extract_mcp_name(cmdline),
                        "cmdline": cmdline_str,
                        "status": "running",
                    }
                    mcp_servers.append(server_info)

            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        return mcp_servers

    def _extract_mcp_name(self, cmdline: List[str]) -> str:
        """Extract MCP server name from command line."""
        for part in cmdline:
            if "mcp" in part.lower():
                # Extract from paths like /path/to/chroma-mcp
                if "/" in part:
                    return Path(part).name
                return part
        return "unknown-mcp"

    def scan_providers(self) -> List[Dict[str, Any]]:
        """Scan CCB providers and their capabilities."""
        providers = [
            {
                "name": "claude",
                "command": "claude",
                "models": ["sonnet-4.5", "opus-4.5", "haiku-4"],
                "strengths": ["code", "reasoning", "analysis"],
                "speed": "medium",
            },
            {
                "name": "codex",
                "command": "ccb-cli codex",
                "models": ["o3", "o4-mini", "gpt-4o", "o1-pro"],
                "strengths": ["algorithm", "math", "code-review"],
                "speed": "slow",
            },
            {
                "name": "gemini",
                "command": "ccb-cli gemini",
                "models": ["3f", "3p", "2.5f", "2.5p"],
                "strengths": ["frontend", "ui", "multimodal"],
                "speed": "slow",
            },
            {
                "name": "kimi",
                "command": "ccb-cli kimi",
                "models": ["thinking", "normal"],
                "strengths": ["chinese", "long-context", "fast"],
                "speed": "fast",
            },
            {
                "name": "qwen",
                "command": "ccb-cli qwen",
                "models": ["coder"],
                "strengths": ["code", "data", "multilingual"],
                "speed": "fast",
            },
            {
                "name": "iflow",
                "command": "ccb-cli iflow",
                "models": ["thinking", "normal"],
                "strengths": ["workflow", "automation"],
                "speed": "medium",
            },
            {
                "name": "opencode",
                "command": "ccb-cli opencode",
                "models": ["mm", "kimi", "ds", "glm"],
                "strengths": ["multi-model", "flexibility"],
                "speed": "medium",
            },
        ]

        # Check which providers are actually available
        for provider in providers:
            provider["available"] = self._check_provider_available(provider["command"])

        return providers

    def _check_provider_available(self, command: str) -> bool:
        """Check if a provider command is available."""
        cmd_parts = command.split()
        try:
            result = subprocess.run(
                [cmd_parts[0], "--version"] if len(cmd_parts) == 1 else [cmd_parts[0], "--help"],
                capture_output=True,
                timeout=2,
            )
            return result.returncode == 0
        except (OSError, ValueError, subprocess.SubprocessError):
            return False

    def generate_registry(self) -> Dict[str, Any]:
        """Generate complete registry of all capabilities."""
        registry = {
            "generated_at": datetime.now().isoformat(),
            "skills": self.scan_skills(),
            "mcp_servers": self.scan_mcp_servers(),
            "providers": self.scan_providers(),
            "stats": {
                "total_skills": 0,
                "total_mcp_servers": 0,
                "available_providers": 0,
            },
        }

        registry["stats"]["total_skills"] = len(registry["skills"])
        registry["stats"]["total_mcp_servers"] = len(registry["mcp_servers"])
        registry["stats"]["available_providers"] = sum(1 for p in registry["providers"] if p["available"])

        return registry

    def save_cache(self, registry: Dict[str, Any]):
        """Save registry to cache file."""
        with open(self.cache_path, "w") as f:
            json.dump(registry, f, indent=2)

    def load_cache(self) -> Optional[Dict[str, Any]]:
        """Load registry from cache."""
        if not self.cache_path.exists():
            return None

        try:
            with open(self.cache_path) as f:
                return json.load(f)
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            return None

    def get_skill_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """Get skill information by name."""
        registry = self.load_cache() or self.generate_registry()
        for skill in registry.get("skills", []):
            if skill["name"] == name:
                return skill
        return None

    def find_provider_for_task(self, task_keywords: List[str]) -> List[Dict[str, Any]]:
        """Recommend providers based on task keywords."""
        registry = self.load_cache() or self.generate_registry()

        matches = []
        for provider in registry.get("providers", []):
            if not provider.get("available"):
                continue

            score = 0
            for keyword in task_keywords:
                keyword_lower = keyword.lower()
                for strength in provider.get("strengths", []):
                    if keyword_lower in strength.lower():
                        score += 1

            if score > 0:
                matches.append(
                    {
                        "provider": provider["name"],
                        "score": score,
                        "command": provider["command"],
                        "recommended_model": provider["models"][0] if provider["models"] else None,
                    }
                )

        matches.sort(key=lambda x: x["score"], reverse=True)
        return matches


def main():
    """CLI for registry operations."""
    import sys

    registry_sys = CCBRegistry()

    if len(sys.argv) < 2:
        _emit("Usage: registry.py [scan|list|find] [args...]")
        sys.exit(1)

    command = sys.argv[1]

    if command == "scan":
        _emit("Scanning capabilities...")
        registry = registry_sys.generate_registry()
        registry_sys.save_cache(registry)
        _emit(f"✓ Found {registry['stats']['total_skills']} skills")
        _emit(f"✓ Found {registry['stats']['total_mcp_servers']} MCP servers")
        _emit(f"✓ Found {registry['stats']['available_providers']} available providers")

    elif command == "list":
        registry = registry_sys.load_cache()
        if not registry:
            _emit("No cache found. Run 'scan' first.")
            sys.exit(1)

        if len(sys.argv) > 2:
            list_type = sys.argv[2]
            if list_type == "skills":
                for skill in registry.get("skills", []):
                    _emit(f"- {skill['name']}: {skill['description'][:80]}")
            elif list_type == "providers":
                for provider in registry.get("providers", []):
                    status = "✓" if provider["available"] else "✗"
                    _emit(f"{status} {provider['name']}: {', '.join(provider['strengths'])}")
            elif list_type == "mcp":
                for mcp in registry.get("mcp_servers", []):
                    _emit(f"- {mcp['name']} (PID: {mcp['pid']})")
        else:
            _emit(json.dumps(registry, indent=2))

    elif command == "find":
        if len(sys.argv) < 3:
            _emit("Usage: registry.py find <task_keywords...>")
            sys.exit(1)

        keywords = sys.argv[2:]
        matches = registry_sys.find_provider_for_task(keywords)

        if matches:
            _emit(f"Recommended providers for: {' '.join(keywords)}")
            for match in matches[:3]:
                _emit(f"  {match['score']}★ {match['provider']}: {match['command']}")
        else:
            _emit("No matching providers found.")

    else:
        _emit(f"Unknown command: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()
