"""Qwen provider communication reader."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, List, Optional

from .base import BaseCommReader, CommMessage


class QwenCommReader(BaseCommReader):
    """Reader for Qwen CLI session logs."""

    def __init__(self, home_dir: Optional[str] = None, work_dir: Optional[Path] = None):
        super().__init__("qwen", home_dir=home_dir)
        self.work_dir = Path(work_dir).expanduser() if work_dir else Path.cwd()

    def _default_home(self) -> str:
        return "~/.qwen"

    @property
    def projects_root(self) -> Path:
        return self.home_dir / "projects"

    def _compute_project_hash(self) -> str:
        try:
            abs_path = str(self.work_dir.absolute())
            return abs_path.replace("/", "-")
        except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError):
            return ""

    def _project_chats_dir(self) -> Optional[Path]:
        project_hash = self._compute_project_hash()
        if not project_hash:
            return None

        chats_dir = self.projects_root / project_hash / "chats"
        if chats_dir.exists():
            return chats_dir

        return None

    def _resolve_preferred_session(self) -> Optional[Path]:
        if not self._preferred_session:
            return None

        preferred = Path(self._preferred_session).expanduser()
        if preferred.exists() and preferred.is_file():
            return preferred

        chats_dir = self._project_chats_dir()
        if chats_dir is None:
            return None

        if preferred.suffix:
            candidate = chats_dir / preferred.name
            if candidate.exists() and candidate.is_file():
                return candidate
        else:
            candidate = chats_dir / f"{preferred.name}.jsonl"
            if candidate.exists() and candidate.is_file():
                return candidate

        return None

    def _latest_session_in_dir(self, chats_dir: Path) -> Optional[Path]:
        latest_file: Optional[Path] = None
        latest_mtime = -1.0

        try:
            for path in chats_dir.glob("*.jsonl"):
                if not path.is_file() or path.name.startswith("."):
                    continue
                try:
                    mtime = path.stat().st_mtime
                except OSError:
                    continue
                if mtime >= latest_mtime:
                    latest_mtime = mtime
                    latest_file = path
        except OSError:
            return None

        return latest_file

    def _find_session_file(self) -> Optional[Path]:
        preferred = self._resolve_preferred_session()
        if preferred is not None:
            return preferred

        project_chats = self._project_chats_dir()
        if project_chats is not None:
            latest = self._latest_session_in_dir(project_chats)
            if latest is not None:
                return latest

        root = self.projects_root
        if not root.exists():
            return None

        latest_file: Optional[Path] = None
        latest_mtime = -1.0

        try:
            for path in root.glob("*/chats/*.jsonl"):
                if not path.is_file():
                    continue
                try:
                    mtime = path.stat().st_mtime
                except OSError:
                    continue
                if mtime >= latest_mtime:
                    latest_mtime = mtime
                    latest_file = path
        except OSError:
            return None

        return latest_file

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
            if item_type in {"think", "thinking", "tool_use"}:
                continue

            text = item.get("text")
            if isinstance(text, str) and text.strip():
                texts.append(text.strip())

        return "\n".join(texts).strip()

    def _extract_message(self, entry: dict, role: str) -> Optional[str]:
        if not isinstance(entry, dict):
            return None

        entry_role = str(entry.get("role") or "").strip().lower()
        if entry_role == role:
            content_text = self._extract_content_text(entry.get("content"))
            return content_text or None

        entry_type = str(entry.get("type") or "").strip().lower()
        if entry_type == "assistant" and role == "assistant":
            message = entry.get("message")
            if isinstance(message, dict):
                parts = message.get("parts")
                if isinstance(parts, list):
                    texts = []
                    for part in parts:
                        if not isinstance(part, dict):
                            continue
                        text = part.get("text")
                        if isinstance(text, str) and text.strip():
                            texts.append(text.strip())
                    merged = "\n".join(texts).strip()
                    return merged or None

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
            text: Optional[str] = self._extract_message(entry, "assistant")
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
