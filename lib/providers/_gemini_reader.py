"""Gemini provider communication reader."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, List, Optional

from .base import BaseCommReader, CommMessage


class GeminiCommReader(BaseCommReader):
    """Reader for Gemini CLI session files."""

    def __init__(self, home_dir: Optional[str] = None, work_dir: Optional[Path] = None):
        super().__init__("gemini", home_dir=home_dir)
        self.work_dir = Path(work_dir).expanduser() if work_dir else Path.cwd()
        forced_hash = os.environ.get("GEMINI_PROJECT_HASH", "").strip()
        self._project_hash = forced_hash or self._compute_project_hash()

    def _default_home(self) -> str:
        return "~/.gemini/tmp"

    def _compute_project_hash(self) -> str:
        try:
            normalized = str(self.work_dir.expanduser().absolute())
        except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError):
            normalized = str(self.work_dir)
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    def _project_chats_dir(self) -> Optional[Path]:
        chats_dir = self.home_dir / self._project_hash / "chats"
        if chats_dir.exists():
            return chats_dir
        return None

    def _latest_session_in_chats(self, chats_dir: Path) -> Optional[Path]:
        try:
            sessions = sorted(
                (path for path in chats_dir.glob("session-*.json") if path.is_file() and not path.name.startswith(".")),
                key=lambda path: path.stat().st_mtime,
            )
        except OSError:
            return None

        return sessions[-1] if sessions else None

    def _find_session_file(self) -> Optional[Path]:
        if self._preferred_session:
            preferred = Path(self._preferred_session).expanduser()
            if preferred.exists() and preferred.is_file():
                return preferred

            chats_dir = self._project_chats_dir()
            if chats_dir is not None:
                preferred_in_project = chats_dir / self._preferred_session
                if preferred_in_project.exists() and preferred_in_project.is_file():
                    return preferred_in_project

        chats_dir = self._project_chats_dir()
        if chats_dir is not None:
            latest = self._latest_session_in_chats(chats_dir)
            if latest is not None:
                return latest

        if os.environ.get("GEMINI_ALLOW_ANY_PROJECT_SCAN", "").lower() in {"1", "true", "yes"}:
            try:
                sessions = sorted(
                    (path for path in self.home_dir.glob("*/chats/session-*.json") if path.is_file()),
                    key=lambda path: path.stat().st_mtime,
                )
            except OSError:
                sessions = []

            if sessions:
                return sessions[-1]

        return None

    def _parse_messages(self, content: str) -> List[CommMessage]:
        try:
            payload = json.loads(content)
        except json.JSONDecodeError:
            return []

        if not isinstance(payload, dict):
            return []

        raw_messages = payload.get("messages", [])
        if not isinstance(raw_messages, list):
            return []

        parsed: List[CommMessage] = []

        for item in raw_messages:
            if not isinstance(item, dict):
                continue

            msg_type = str(item.get("type") or "unknown").strip().lower()
            role = "assistant" if msg_type == "gemini" else ("user" if msg_type == "user" else msg_type)

            raw_content: Any = item.get("content", "")
            if isinstance(raw_content, str):
                text = raw_content.strip()
            else:
                text = str(raw_content).strip()

            if not text:
                continue

            timestamp_raw = item.get("timestamp")
            if timestamp_raw is None:
                timestamp_raw = item.get("createdAt", 0)
            try:
                timestamp = float(timestamp_raw)
            except (TypeError, ValueError):
                timestamp = 0.0

            parsed.append(
                CommMessage(
                    role=role,
                    content=text,
                    timestamp=timestamp,
                    metadata={
                        "id": item.get("id"),
                    },
                )
            )

        return parsed
