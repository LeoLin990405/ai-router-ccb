"""Build the unified tool index from all sources."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple

try:
    from lib.common.logging import get_logger
except ImportError:  # pragma: no cover - script mode fallback
    from common.logging import get_logger  # type: ignore

logger = get_logger("skills.tool_index_builder")

SKILLS_DIRS = [
    Path.home() / ".claude" / "skills",
    Path.home() / ".codex" / "skills",
    Path.home() / ".agents" / "skills",
]
MCP_CONFIG_CANDIDATES = [
    Path.home() / ".claude" / "mcp_servers.json",
    Path.home() / ".ccb_config" / "mcp_servers.json",
]
MCP_MANIFEST = Path.home() / ".ccb_config" / "mcp_tools_manifest.json"


def build_index() -> List[Dict[str, Any]]:
    entries: List[Dict[str, Any]] = []
    entries.extend(_scan_local_skills())
    entries.extend(_scan_mcp_servers())
    entries.extend(_scan_mcp_tools())

    deduped: Dict[str, Dict[str, Any]] = {}
    for entry in entries:
        entry_id = entry.get("id")
        if entry_id:
            deduped[str(entry_id)] = entry

    result = list(deduped.values())
    logger.info("Built tool index with %s entries", len(result))
    return result


def _scan_local_skills() -> List[Dict[str, Any]]:
    entries: List[Dict[str, Any]] = []

    for skills_dir in SKILLS_DIRS:
        if not skills_dir.exists() or not skills_dir.is_dir():
            continue

        for skill_dir in sorted(skills_dir.iterdir()):
            if not skill_dir.is_dir():
                continue

            skill_md = skill_dir / "SKILL.md"
            if not skill_md.exists():
                continue

            description, triggers, keywords = _parse_skill_md(skill_md)
            name = skill_dir.name
            entries.append(
                {
                    "id": f"skill:{name}",
                    "type": "skill",
                    "name": name,
                    "description": description,
                    "keywords": keywords,
                    "triggers": triggers,
                    "installed": True,
                    "source": "local",
                    "path": str(skill_dir),
                }
            )

    return entries


def _parse_skill_md(path: Path) -> Tuple[str, List[str], List[str]]:
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()

    description = ""
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            continue
        description = stripped
        break

    triggers: List[str] = []
    trigger_pattern = re.compile(r"TRIGGERS\s*-\s*(.+)", re.IGNORECASE)
    for line in lines:
        match = trigger_pattern.search(line)
        if not match:
            continue
        items = [item.strip() for item in re.split(r"[,，;；]", match.group(1)) if item.strip()]
        triggers.extend(items)

    keywords: List[str] = []
    if description:
        keywords.extend(
            [
                token.lower()
                for token in re.findall(r"[A-Za-z][A-Za-z0-9\-]{2,}", description)
                if len(token) >= 3
            ]
        )

    for trigger in triggers:
        for token in re.findall(r"[A-Za-z][A-Za-z0-9\-]{2,}", trigger):
            keywords.append(token.lower())

    if not keywords:
        fallback = path.parent.name.replace("_", "-")
        keywords = [fallback.lower()]

    return description or f"Skill: {path.parent.name}", list(dict.fromkeys(triggers)), list(dict.fromkeys(keywords[:12]))


def _read_mcp_config() -> Dict[str, Any]:
    for candidate in MCP_CONFIG_CANDIDATES:
        if not candidate.exists():
            continue
        try:
            payload = json.loads(candidate.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                continue
            if "mcpServers" in payload and isinstance(payload.get("mcpServers"), dict):
                return payload["mcpServers"]
            return payload
        except (json.JSONDecodeError, OSError, TypeError, ValueError):
            logger.debug("Failed to parse MCP config: %s", candidate, exc_info=True)

    return {}


def _scan_mcp_servers() -> List[Dict[str, Any]]:
    entries: List[Dict[str, Any]] = []
    config = _read_mcp_config()

    for server_name, server_config in config.items():
        description = f"MCP server: {server_name}"
        if isinstance(server_config, dict) and isinstance(server_config.get("description"), str):
            description = server_config["description"]

        entries.append(
            {
                "id": f"mcp-server:{server_name}",
                "type": "mcp-server",
                "name": server_name,
                "description": description,
                "keywords": [server_name, "mcp", "server"],
                "installed": True,
                "source": "mcp-config",
            }
        )

    return entries


def _scan_mcp_tools() -> List[Dict[str, Any]]:
    entries: List[Dict[str, Any]] = []
    if not MCP_MANIFEST.exists():
        return entries

    try:
        payload = json.loads(MCP_MANIFEST.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError, TypeError, ValueError):
        logger.debug("Failed to parse MCP tool manifest", exc_info=True)
        return entries

    tools = payload if isinstance(payload, list) else []
    for tool in tools:
        if not isinstance(tool, dict):
            continue

        server = str(tool.get("server") or "unknown")
        name = str(tool.get("name") or "unknown")
        keywords = tool.get("keywords")
        if not isinstance(keywords, list):
            keywords = [name, server, "mcp"]

        entries.append(
            {
                "id": f"mcp-tool:{server}.{name}",
                "type": "mcp-tool",
                "name": name,
                "description": str(tool.get("description") or ""),
                "keywords": [str(item) for item in keywords if item],
                "server": server,
                "installed": True,
                "source": "mcp-active",
            }
        )

    return entries
