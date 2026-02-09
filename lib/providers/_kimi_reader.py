"""Kimi provider communication reader."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, List, Optional

from .base import BaseCommReader, CommMessage


class KimiCommReader(BaseCommReader):
    """Reader for Kimi CLI session logs."""

    def __init__(self, home_dir: Optional[str] = None, work_dir: Optional[Path] = None):
        super().__init__("kimi", home_dir=home_dir)
        self.work_dir = Path(work_dir).resolve() if work_dir else Path.cwd().resolve()

    def _default_home(self) -> str:
        return "~/.kimi"

    @property
    def sessions_root(self) -> Path:
        return self.home_dir / "sessions"

    def _compute_project_hash(self) -> str:
        abs_path = str(self.work_dir)
        return hashlib.md5(abs_path.encode("utf-8")).hexdigest()

    def _project_sessions_dir(self) -> Optional[Path]:
        root = self.sessions_root
        if not root.exists():
            return None

        project_dir = root / self._compute_project_hash()
        if project_dir.exists():
            return project_dir
        return None

    def _resolve_preferred_session(self) -> Optional[Path]:
        if not self._preferred_session:
            return None

        candidate = Path(self._preferred_session).expanduser()
        if candidate.exists() and candidate.is_file():
            return candidate

        project_dir = self._project_sessions_dir()
        if project_dir:
            candidate = project_dir / self._preferred_session / "context.jsonl"
            if candidate.exists():
                return candidate

        root = self.sessions_root
        if root.exists():
            candidate = root / self._preferred_session / "context.jsonl"
            if candidate.exists():
                return candidate

        return None

    def _latest_context_in_dir(self, directory: Path) -> Optional[Path]:
        latest_file: Optional[Path] = None
        latest_mtime = -1.0

        try:
            for session_dir in directory.iterdir():
                if not session_dir.is_dir():
                    continue
                context_file = session_dir / "context.jsonl"
                if not context_file.exists():
                    continue
                try:
                    mtime = context_file.stat().st_mtime
                except OSError:
                    continue
                if mtime >= latest_mtime:
                    latest_mtime = mtime
                    latest_file = context_file
        except OSError:
            return None

        return latest_file

    def _find_session_file(self) -> Optional[Path]:
        preferred = self._resolve_preferred_session()
        if preferred is not None:
            return preferred

        project_dir = self._project_sessions_dir()
        if project_dir is not None:
            latest = self._latest_context_in_dir(project_dir)
            if latest is not None:
                return latest

        root = self.sessions_root
        if not root.exists():
            return None

        latest_file: Optional[Path] = None
        latest_mtime = -1.0

        try:
            for context_file in root.glob("*/*/context.jsonl"):
                if not context_file.is_file():
                    continue
                try:
                    mtime = context_file.stat().st_mtime
                except OSError:
                    continue
                if mtime >= latest_mtime:
                    latest_mtime = mtime
                    latest_file = context_file
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

        chunks: List[str] = []
        for item in content:
            if not isinstance(item, dict):
                continue

            item_type = str(item.get("type") or "").strip().lower()
            if item_type in {"think", "thinking", "tool_use"}:
                continue

            text = item.get("text")
            if isinstance(text, str) and text.strip():
                chunks.append(text.strip())

        return "\n".join(chunks).strip()

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

            role = str(entry.get("role") or "unknown").strip().lower() or "unknown"
            content_text = self._extract_content_text(entry.get("content"))
            if not content_text:
                continue

            timestamp_raw = entry.get("timestamp", 0)
            try:
                timestamp = float(timestamp_raw)
            except (TypeError, ValueError):
                timestamp = 0.0

            metadata = {
                "id": entry.get("id"),
                "model": entry.get("model"),
            }

            messages.append(
                CommMessage(
                    role=role,
                    content=content_text,
                    timestamp=timestamp,
                    metadata=metadata,
                )
            )

        return messages
