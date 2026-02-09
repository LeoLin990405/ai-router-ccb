"""Codex provider communication reader."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, List, Optional

from .base import BaseCommReader, CommMessage


class CodexCommReader(BaseCommReader):
    """Reader for Codex session logs."""

    def __init__(self, home_dir: Optional[str] = None, work_dir: Optional[Path] = None):
        super().__init__("codex", home_dir=home_dir)
        self.work_dir = Path(work_dir).expanduser() if work_dir else Path.cwd()

    def _default_home(self) -> str:
        return "~/.codex/sessions"

    def _normalize_work_dir(self) -> Optional[str]:
        try:
            return str(self.work_dir.resolve()).lower()
        except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError):
            return None

    def _extract_cwd_from_log(self, log_path: Path) -> Optional[str]:
        try:
            with log_path.open("r", encoding="utf-8", errors="replace") as handle:
                first_line = handle.readline()
            if not first_line:
                return None

            entry = json.loads(first_line)
            if not isinstance(entry, dict):
                return None

            if str(entry.get("type") or "") == "session_meta":
                payload = entry.get("payload")
                if isinstance(payload, dict):
                    cwd = payload.get("cwd")
                    if isinstance(cwd, str) and cwd.strip():
                        try:
                            return str(Path(cwd).resolve()).lower()
                        except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError):
                            return cwd.lower()
        except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError):
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
            candidates = [path for path in self.home_dir.glob(f"**/*{session_id}*.jsonl") if path.is_file()]
        except OSError:
            return None

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

        expected_cwd = self._normalize_work_dir()
        latest_match: Optional[Path] = None
        latest_match_mtime = -1.0

        latest_any: Optional[Path] = None
        latest_any_mtime = -1.0

        try:
            for path in self.home_dir.glob("**/*.jsonl"):
                if not path.is_file():
                    continue

                try:
                    mtime = path.stat().st_mtime
                except OSError:
                    continue

                if mtime >= latest_any_mtime:
                    latest_any_mtime = mtime
                    latest_any = path

                if expected_cwd:
                    cwd = self._extract_cwd_from_log(path)
                    if cwd and cwd == expected_cwd and mtime >= latest_match_mtime:
                        latest_match_mtime = mtime
                        latest_match = path
        except OSError:
            return latest_any

        return latest_match or latest_any

    def _extract_assistant_message(self, entry: dict) -> Optional[str]:
        entry_type = entry.get("type")
        payload = entry.get("payload", {})

        if entry_type == "response_item":
            if not isinstance(payload, dict) or payload.get("type") != "message":
                return None
            if payload.get("role") == "user":
                return None

            content = payload.get("content") or []
            if isinstance(content, list):
                texts: List[str] = []
                for item in content:
                    if not isinstance(item, dict):
                        continue
                    if item.get("type") in ("output_text", "text"):
                        text = item.get("text")
                        if isinstance(text, str) and text.strip():
                            texts.append(text.strip())
                merged = "\n".join(texts).strip()
                if merged:
                    return merged
            elif isinstance(content, str) and content.strip():
                return content.strip()

            message = payload.get("message")
            if isinstance(message, str) and message.strip():
                return message.strip()
            return None

        if entry_type == "event_msg":
            if not isinstance(payload, dict):
                return None
            payload_type = payload.get("type")
            if payload_type in ("agent_message", "assistant_message", "assistant", "assistant_response", "message"):
                if payload.get("role") == "user":
                    return None
                msg = payload.get("message") or payload.get("content") or payload.get("text")
                if isinstance(msg, str) and msg.strip():
                    return msg.strip()
            return None

        if isinstance(payload, dict) and payload.get("role") == "assistant":
            msg = payload.get("message") or payload.get("content") or payload.get("text")
            if isinstance(msg, str) and msg.strip():
                return msg.strip()

        return None

    def _extract_user_message(self, entry: dict) -> Optional[str]:
        entry_type = entry.get("type")
        payload = entry.get("payload", {})

        if entry_type == "event_msg" and isinstance(payload, dict) and payload.get("type") == "user_message":
            msg = payload.get("message")
            if isinstance(msg, str) and msg.strip():
                return msg.strip()

        if entry_type == "response_item":
            if isinstance(payload, dict) and payload.get("type") == "message" and payload.get("role") == "user":
                content = payload.get("content") or []
                if isinstance(content, list):
                    texts = []
                    for item in content:
                        if not isinstance(item, dict):
                            continue
                        if item.get("type") == "input_text":
                            text = item.get("text", "")
                            if isinstance(text, str) and text.strip():
                                texts.append(text.strip())
                    merged = "\n".join(texts).strip()
                    if merged:
                        return merged

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
            text = self._extract_assistant_message(entry)
            if text:
                role = "assistant"
            else:
                text = self._extract_user_message(entry)
                if text:
                    role = "user"

            if not role or not text:
                continue

            timestamp_raw = entry.get("timestamp", 0)
            if isinstance(entry.get("payload"), dict) and not timestamp_raw:
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
