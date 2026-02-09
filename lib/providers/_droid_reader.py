"""Droid provider communication reader."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, List, Optional

from .base import BaseCommReader, CommMessage


class DroidCommReader(BaseCommReader):
    """Reader for Droid CLI session logs."""

    def __init__(self, home_dir: Optional[str] = None, work_dir: Optional[Path] = None):
        super().__init__("droid", home_dir=home_dir)
        self.work_dir = Path(work_dir).expanduser() if work_dir else Path.cwd()

    def _default_home(self) -> str:
        return "~/.factory/sessions"

    def _normalize_path_for_match(self, value: str) -> str:
        normalized = str(value or "").strip().replace("\\", "/").rstrip("/")
        if os.name == "nt":
            normalized = normalized.lower()
        return normalized

    def _path_is_same_or_parent(self, parent: str, child: str) -> bool:
        parent_norm = self._normalize_path_for_match(parent)
        child_norm = self._normalize_path_for_match(child)
        if not parent_norm or not child_norm:
            return False
        if parent_norm == child_norm:
            return True
        if not child_norm.startswith(parent_norm):
            return False
        return child_norm == parent_norm or child_norm[len(parent_norm) :].startswith("/")

    def _extract_session_cwd(self, session_file: Path) -> Optional[str]:
        try:
            with session_file.open("r", encoding="utf-8", errors="replace") as handle:
                for _ in range(30):
                    line = handle.readline()
                    if not line:
                        break
                    line = line.strip()
                    if not line:
                        continue

                    try:
                        entry = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    if not isinstance(entry, dict):
                        continue

                    if str(entry.get("type") or "").strip().lower() == "session_start":
                        cwd = entry.get("cwd")
                        if isinstance(cwd, str) and cwd.strip():
                            return cwd.strip()
        except OSError:
            return None

        return None

    def _resolve_preferred_session(self) -> Optional[Path]:
        if not self._preferred_session:
            return None

        preferred = Path(self._preferred_session).expanduser()
        if preferred.exists() and preferred.is_file():
            return preferred

        if not self.home_dir.exists():
            return None

        session_id = preferred.stem if preferred.suffix else preferred.name
        if not session_id:
            return None

        try:
            candidates = list(self.home_dir.glob(f"**/{session_id}.jsonl"))
        except OSError:
            return None

        candidates = [path for path in candidates if path.is_file()]
        if not candidates:
            return None

        candidates.sort(key=lambda path: path.stat().st_mtime)
        return candidates[-1]

    def _find_session_file(self) -> Optional[Path]:
        preferred = self._resolve_preferred_session()
        if preferred is not None:
            return preferred

        if not self.home_dir.exists():
            return None

        work_dir_str = str(self.work_dir)
        best_match: Optional[Path] = None
        best_match_mtime = -1.0

        latest_any: Optional[Path] = None
        latest_any_mtime = -1.0

        try:
            for path in self.home_dir.glob("**/*.jsonl"):
                if not path.is_file() or path.name.startswith("."):
                    continue

                try:
                    mtime = path.stat().st_mtime
                except OSError:
                    continue

                if mtime >= latest_any_mtime:
                    latest_any_mtime = mtime
                    latest_any = path

                cwd = self._extract_session_cwd(path)
                if not cwd:
                    continue

                if self._path_is_same_or_parent(work_dir_str, cwd) or self._path_is_same_or_parent(cwd, work_dir_str):
                    if mtime >= best_match_mtime:
                        best_match_mtime = mtime
                        best_match = path
        except OSError:
            return latest_any

        return best_match or latest_any

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
