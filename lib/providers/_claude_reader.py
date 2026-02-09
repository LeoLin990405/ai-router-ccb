"""Claude provider communication reader."""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, List, Optional

from .base import BaseCommReader, CommMessage


class ClaudeCommReader(BaseCommReader):
    """Reader for Claude CLI session logs."""

    def __init__(self, home_dir: Optional[str] = None, work_dir: Optional[Path] = None):
        super().__init__("claude", home_dir=home_dir)
        self.work_dir = Path(work_dir).expanduser() if work_dir else Path.cwd()

    def _default_home(self) -> str:
        return "~/.claude/projects"

    def _project_key_for_path(self, path: Path) -> str:
        return re.sub(r"[^A-Za-z0-9]", "-", str(path))

    def _candidate_project_dirs(self) -> List[Path]:
        candidates: List[Path] = []

        env_pwd = os.environ.get("PWD")
        if env_pwd:
            try:
                candidates.append(Path(env_pwd))
            except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError):
                pass

        candidates.append(self.work_dir)

        try:
            candidates.append(self.work_dir.resolve())
        except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError):
            pass

        project_dirs: List[Path] = []
        seen = set()
        for candidate in candidates:
            key = self._project_key_for_path(candidate)
            if key in seen:
                continue
            seen.add(key)
            project_dirs.append(self.home_dir / key)

        return project_dirs

    def _project_dir(self) -> Path:
        candidates = self._candidate_project_dirs()
        for candidate in candidates:
            if candidate.exists():
                return candidate

        if candidates:
            return candidates[-1]

        return self.home_dir / self._project_key_for_path(self.work_dir)

    def _resolve_preferred_session(self) -> Optional[Path]:
        if not self._preferred_session:
            return None

        preferred = Path(self._preferred_session).expanduser()
        if preferred.exists() and preferred.is_file():
            return preferred

        project_dir = self._project_dir()
        if not preferred.suffix:
            candidate = project_dir / f"{preferred.name}.jsonl"
        else:
            candidate = project_dir / preferred.name
        if candidate.exists() and candidate.is_file():
            return candidate

        return None

    def _scan_latest_session(self) -> Optional[Path]:
        project_dir = self._project_dir()
        if not project_dir.exists():
            return None

        try:
            sessions = sorted(
                (path for path in project_dir.glob("*.jsonl") if path.is_file() and not path.name.startswith(".")),
                key=lambda path: path.stat().st_mtime,
            )
        except OSError:
            return None

        return sessions[-1] if sessions else None

    def _scan_latest_session_any_project(self) -> Optional[Path]:
        if not self.home_dir.exists():
            return None

        try:
            sessions = sorted(
                (path for path in self.home_dir.glob("*/*.jsonl") if path.is_file() and not path.name.startswith(".")),
                key=lambda path: path.stat().st_mtime,
            )
        except OSError:
            return None

        return sessions[-1] if sessions else None

    def _find_session_file(self) -> Optional[Path]:
        preferred = self._resolve_preferred_session()
        if preferred is not None:
            return preferred

        latest = self._scan_latest_session()
        if latest is not None:
            return latest

        if os.environ.get("CLAUDE_ALLOW_ANY_PROJECT_SCAN", "").lower() in {"1", "true", "yes"}:
            return self._scan_latest_session_any_project()

        return None

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
            if item_type in {"thinking", "thinking_delta"}:
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

        if entry_type == "response_item":
            payload = entry.get("payload")
            if not isinstance(payload, dict) or payload.get("type") != "message":
                return None
            if str(payload.get("role") or "").strip().lower() != role:
                return None

            content_text = self._extract_content_text(payload.get("content"))
            return content_text or None

        if entry_type == "event_msg":
            payload = entry.get("payload")
            if not isinstance(payload, dict):
                return None

            payload_type = str(payload.get("type") or "").strip().lower()
            if payload_type in {"agent_message", "assistant_message", "assistant"}:
                if str(payload.get("role") or "").strip().lower() != role:
                    return None
                message_text = payload.get("message") or payload.get("content") or payload.get("text")
                if isinstance(message_text, str) and message_text.strip():
                    return message_text.strip()
            return None

        message = entry.get("message")
        if isinstance(message, dict):
            msg_role = str(message.get("role") or entry_type).strip().lower()
            if msg_role != role:
                return None
            content_text = self._extract_content_text(message.get("content"))
            return content_text or None

        if entry_type != role:
            return None

        content_text = self._extract_content_text(entry.get("content"))
        return content_text or None

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
            if isinstance(entry.get("payload"), dict) and timestamp_raw == 0:
                timestamp_raw = entry["payload"].get("timestamp", 0)

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
