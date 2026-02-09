"""OpenCode provider communication reader."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Dict, List, Optional

from .base import BaseCommReader, CommMessage


class OpenCodeCommReader(BaseCommReader):
    """Reader for OpenCode storage-backed session logs."""

    def __init__(self, home_dir: Optional[str] = None, work_dir: Optional[Path] = None):
        super().__init__("opencode", home_dir=home_dir)
        self.work_dir = Path(work_dir).expanduser() if work_dir else Path.cwd()

    def _default_home(self) -> str:
        xdg_data_home = (os.environ.get("XDG_DATA_HOME") or "").strip()
        if xdg_data_home:
            return str(Path(xdg_data_home) / "opencode" / "storage")
        return str(Path.home() / ".local" / "share" / "opencode" / "storage")

    def _normalize_path_for_match(self, path: str) -> str:
        normalized = str(path or "").replace("\\", "/").rstrip("/")
        if os.name == "nt":
            normalized = normalized.lower()
        return normalized

    def _path_matches(self, base: str, candidate: str) -> bool:
        base_norm = self._normalize_path_for_match(base)
        cand_norm = self._normalize_path_for_match(candidate)
        if not base_norm or not cand_norm:
            return False
        if base_norm == cand_norm:
            return True
        return cand_norm.startswith(base_norm + "/") or base_norm.startswith(cand_norm + "/")

    @property
    def project_dir(self) -> Path:
        return self.home_dir / "project"

    @property
    def session_root(self) -> Path:
        return self.home_dir / "session"

    @property
    def message_root(self) -> Path:
        return self.home_dir / "message"

    @property
    def part_root(self) -> Path:
        return self.home_dir / "part"

    def _load_json(self, path: Path) -> Dict:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            return payload if isinstance(payload, dict) else {}
        except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError):
            return {}

    def _detect_project_id(self) -> Optional[str]:
        forced_project_id = (os.environ.get("OPENCODE_PROJECT_ID") or "").strip()
        if forced_project_id:
            return forced_project_id

        if not self.project_dir.exists():
            return None

        try:
            project_paths = [path for path in self.project_dir.glob("*.json") if path.is_file()]
        except OSError:
            return None

        work_dir_norm = self._normalize_path_for_match(str(self.work_dir))

        best_project_id: Optional[str] = None
        best_score = (-1, -1.0)

        for path in project_paths:
            payload = self._load_json(path)
            project_id = payload.get("id") if isinstance(payload.get("id"), str) else path.stem
            worktree = payload.get("worktree")
            if not isinstance(project_id, str) or not project_id:
                continue
            if not isinstance(worktree, str) or not worktree:
                continue

            if not self._path_matches(worktree, work_dir_norm):
                continue

            try:
                mtime = path.stat().st_mtime
            except OSError:
                mtime = 0.0

            score = (len(worktree), mtime)
            if score > best_score:
                best_score = score
                best_project_id = project_id

        return best_project_id

    def _session_dir(self) -> Optional[Path]:
        project_id = self._detect_project_id() or "global"
        session_dir = self.session_root / project_id
        if session_dir.exists():
            return session_dir
        return None

    def _resolve_preferred_session(self) -> Optional[Path]:
        if not self._preferred_session:
            return None

        preferred = Path(self._preferred_session).expanduser()
        if preferred.exists() and preferred.is_file():
            return preferred

        session_dir = self._session_dir()
        if session_dir is None:
            return None

        if preferred.suffix:
            candidate = session_dir / preferred.name
            if candidate.exists() and candidate.is_file():
                return candidate
        else:
            candidate = session_dir / f"ses_{preferred.name}.json"
            if candidate.exists() and candidate.is_file():
                return candidate

        return None

    def _find_session_file(self) -> Optional[Path]:
        preferred = self._resolve_preferred_session()
        if preferred is not None:
            return preferred

        session_dir = self._session_dir()
        if session_dir is not None:
            try:
                sessions = [path for path in session_dir.glob("ses_*.json") if path.is_file()]
            except OSError:
                sessions = []
            if sessions:
                sessions.sort(key=lambda path: path.stat().st_mtime)
                return sessions[-1]

        if not self.session_root.exists():
            return None

        latest: Optional[Path] = None
        latest_mtime = -1.0
        try:
            for path in self.session_root.glob("*/ses_*.json"):
                if not path.is_file():
                    continue
                try:
                    mtime = path.stat().st_mtime
                except OSError:
                    continue
                if mtime >= latest_mtime:
                    latest_mtime = mtime
                    latest = path
        except OSError:
            return None

        return latest

    def _read_messages(self, session_id: str) -> List[Dict]:
        nested_dir = self.message_root / session_id
        candidates = []

        if nested_dir.exists():
            try:
                candidates.extend([path for path in nested_dir.glob("msg_*.json") if path.is_file()])
            except OSError:
                pass

        if not candidates and self.message_root.exists():
            try:
                candidates.extend([path for path in self.message_root.glob("msg_*.json") if path.is_file()])
            except OSError:
                pass

        messages = []
        for path in candidates:
            payload = self._load_json(path)
            if payload.get("sessionID") != session_id:
                continue
            payload["_path"] = str(path)
            messages.append(payload)

        def _sort_key(item: Dict):
            start = (item.get("time") or {}).get("start", -1)
            try:
                start_i = int(start)
            except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError):
                start_i = -1
            return (start_i, item.get("id", ""))

        messages.sort(key=_sort_key)
        return messages

    def _read_parts(self, message_id: str) -> List[Dict]:
        nested_dir = self.part_root / message_id
        candidates = []

        if nested_dir.exists():
            try:
                candidates.extend([path for path in nested_dir.glob("prt_*.json") if path.is_file()])
            except OSError:
                pass

        if not candidates and self.part_root.exists():
            try:
                candidates.extend([path for path in self.part_root.glob("prt_*.json") if path.is_file()])
            except OSError:
                pass

        parts = []
        for path in candidates:
            payload = self._load_json(path)
            if payload.get("messageID") != message_id:
                continue
            payload["_path"] = str(path)
            parts.append(payload)

        def _sort_key(item: Dict):
            start = (item.get("time") or {}).get("start", -1)
            try:
                start_i = int(start)
            except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError):
                start_i = -1
            return (start_i, item.get("id", ""))

        parts.sort(key=_sort_key)
        return parts

    def _extract_text(self, parts: List[Dict]) -> str:
        text_segments = []
        reasoning_segments = []

        for part in parts:
            ptype = part.get("type")
            text = part.get("text")
            if not isinstance(text, str) or not text:
                continue

            if ptype == "text":
                text_segments.append(text)
            elif ptype == "reasoning":
                reasoning_segments.append(text)

        joined_text = "".join(text_segments).strip()
        if joined_text:
            return joined_text

        return "".join(reasoning_segments).strip()

    def _parse_messages(self, content: str) -> List[CommMessage]:
        # Not used: OpenCode messages are resolved from message/part stores.
        return []

    def _read_session_messages(self, session_file: Path) -> List[CommMessage]:
        session_payload = self._load_json(session_file)
        session_info = session_payload.get("payload") if isinstance(session_payload.get("payload"), dict) else session_payload

        session_id = session_info.get("id") if isinstance(session_info, dict) else None
        if not isinstance(session_id, str) or not session_id:
            return []

        messages = []
        for message in self._read_messages(session_id):
            role = message.get("role")
            if role not in {"assistant", "user"}:
                continue

            message_id = message.get("id")
            if not isinstance(message_id, str) or not message_id:
                continue

            parts = self._read_parts(message_id)
            content_text = self._extract_text(parts)
            if not content_text:
                continue

            timestamp_raw = (message.get("time") or {}).get("start", 0)
            try:
                timestamp = float(timestamp_raw)
            except (TypeError, ValueError):
                timestamp = 0.0

            messages.append(
                CommMessage(
                    role=role,
                    content=content_text,
                    timestamp=timestamp,
                    metadata={"id": message_id},
                )
            )

        return messages
