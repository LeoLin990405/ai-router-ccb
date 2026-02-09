"""iFlow provider communication reader."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, List, Optional

from .base import BaseCommReader, CommMessage


class IFlowCommReader(BaseCommReader):
    """Reader for iFlow CLI session logs."""

    def __init__(self, home_dir: Optional[str] = None, work_dir: Optional[Path] = None):
        super().__init__("iflow", home_dir=home_dir)
        self.work_dir = Path(work_dir).expanduser() if work_dir else Path.cwd()

    def _default_home(self) -> str:
        return "~/.iflow"

    @property
    def projects_root(self) -> Path:
        return self.home_dir / "projects"

    def _path_to_slug(self, path: Path) -> str:
        normalized = str(path).replace("/", "-").replace("\\", "-")
        if normalized.startswith("-"):
            return normalized
        return f"-{normalized}"

    def _project_dir(self) -> Optional[Path]:
        if not self.projects_root.exists():
            return None

        project_dir = self.projects_root / self._path_to_slug(self.work_dir.absolute())
        if project_dir.exists():
            return project_dir

        return None

    def _resolve_preferred_session(self) -> Optional[Path]:
        if not self._preferred_session:
            return None

        preferred = Path(self._preferred_session).expanduser()
        if preferred.exists() and preferred.is_file():
            return preferred

        project_dir = self._project_dir()
        if project_dir is None:
            return None

        if preferred.suffix:
            candidate = project_dir / preferred.name
            if candidate.exists() and candidate.is_file():
                return candidate
        else:
            candidate = project_dir / f"session-{preferred.name}.jsonl"
            if candidate.exists() and candidate.is_file():
                return candidate

        return None

    def _latest_session_in_project(self, project_dir: Path) -> Optional[Path]:
        latest_path: Optional[Path] = None
        latest_mtime = -1.0

        try:
            for path in project_dir.glob("session-*.jsonl"):
                if not path.is_file():
                    continue
                try:
                    mtime = path.stat().st_mtime
                except OSError:
                    continue
                if mtime >= latest_mtime:
                    latest_mtime = mtime
                    latest_path = path
        except OSError:
            return None

        return latest_path

    def _find_session_file(self) -> Optional[Path]:
        preferred = self._resolve_preferred_session()
        if preferred is not None:
            return preferred

        project_dir = self._project_dir()
        if project_dir is not None:
            latest = self._latest_session_in_project(project_dir)
            if latest is not None:
                return latest

        root = self.projects_root
        if not root.exists():
            return None

        latest_path: Optional[Path] = None
        latest_mtime = -1.0

        try:
            for path in root.glob("*/session-*.jsonl"):
                if not path.is_file():
                    continue
                try:
                    mtime = path.stat().st_mtime
                except OSError:
                    continue
                if mtime >= latest_mtime:
                    latest_mtime = mtime
                    latest_path = path
        except OSError:
            return None

        return latest_path

    def _extract_content_text(self, content: Any) -> str:
        if content is None:
            return ""

        if isinstance(content, str):
            return content.strip()

        if not isinstance(content, list):
            return ""

        texts: List[str] = []
        for item in content:
            if not isinstance(item, dict):
                continue

            item_type = str(item.get("type") or "").strip().lower()
            if item_type in {"thinking", "thinking_delta", "tool_use"}:
                continue

            text = item.get("text")
            if not text and item_type == "text":
                text = item.get("content")

            if isinstance(text, str) and text.strip():
                texts.append(text.strip())

        return "\n".join(texts).strip()

    def _extract_message(self, entry: dict, role: str) -> Optional[str]:
        if not isinstance(entry, dict):
            return None

        entry_type = str(entry.get("type") or "").strip().lower()

        if entry_type == role:
            message = entry.get("message")
            if isinstance(message, dict):
                content_text = self._extract_content_text(message.get("content"))
                return content_text or None

        if entry_type == "message":
            message = entry.get("message")
            if isinstance(message, dict):
                msg_role = str(message.get("role") or "").strip().lower()
                if msg_role == role:
                    content_text = self._extract_content_text(message.get("content"))
                    return content_text or None

        msg_role = str(entry.get("role") or entry_type).strip().lower()
        if msg_role == role:
            content_text = self._extract_content_text(entry.get("content") or entry.get("message"))
            return content_text or None

        return None

    def _parse_messages(self, content: str) -> List[CommMessage]:
        messages: List[CommMessage] = []

        for raw_line in content.splitlines():
            line = raw_line.strip()
            if not line:
                continue

            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue

            if not isinstance(entry, dict):
                continue

            role: Optional[str] = None
            text = self._extract_message(entry, "assistant")
            if text:
                role = "assistant"
            else:
                text = self._extract_message(entry, "user")
                if text:
                    role = "user"

            if not role or not text:
                continue

            timestamp_raw = entry.get("timestamp", 0)
            try:
                timestamp = float(timestamp_raw)
            except (TypeError, ValueError):
                timestamp = 0.0

            messages.append(
                CommMessage(
                    role=role,
                    content=text,
                    timestamp=timestamp,
                    metadata={"type": entry.get("type")},
                )
            )

        return messages
