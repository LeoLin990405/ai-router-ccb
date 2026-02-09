"""Compatibility helpers for legacy ``*_comm.py`` modules."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .base import BaseCommReader, CommMessage, CommState


def _emit(message: str) -> None:
    sys.stdout.write(f"{message}\n")


def load_session_hint(provider: str) -> Optional[str]:
    """Load preferred session path/id from ``CCB_SESSION_FILE`` or ``.ccb_config``."""
    provider_key = (provider or "").strip().lower()
    candidates: List[Path] = []

    explicit = (os.environ.get("CCB_SESSION_FILE") or "").strip()
    if explicit:
        candidates.append(Path(explicit).expanduser())

    candidates.append(Path(".ccb_config") / f".{provider_key}-session")

    for session_file in candidates:
        if not session_file.exists() or not session_file.is_file():
            continue
        try:
            payload = json.loads(session_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(payload, dict):
            continue

        ordered_keys = [
            f"{provider_key}_session_path",
            f"{provider_key}_session_id",
            "session_path",
            "session_id",
            "log_path",
        ]
        for key in ordered_keys:
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()

        for key, value in payload.items():
            if not isinstance(value, str) or not value.strip():
                continue
            if key.endswith("_session_path") or key.endswith("_session_id"):
                return value.strip()

    return None


def _pair_messages(messages: List[CommMessage], n: int) -> List[Tuple[str, str]]:
    pairs: List[Tuple[str, str]] = []
    latest_user: Optional[str] = None

    for message in messages:
        role = (message.role or "").strip().lower()
        content = (message.content or "").strip()
        if role == "user":
            latest_user = content
            continue
        if role == "assistant":
            pairs.append((latest_user or "", content))
            latest_user = None

    if n <= 0:
        return []
    return pairs[-n:]


class LegacyLogReaderAdapter:
    """Adapter that exposes legacy log-reader methods over ``BaseCommReader``."""

    def __init__(
        self,
        reader: BaseCommReader,
        *,
        path_key: str = "session_path",
        count_key: str = "message_count",
    ):
        self._reader = reader
        self._path_key = path_key
        self._count_key = count_key

    def _session_file(self) -> Optional[Path]:
        session_file = self._reader._find_session_file()
        if session_file and session_file.exists() and session_file.is_file():
            return session_file
        return None

    def _all_messages(self) -> List[CommMessage]:
        session_file = self._session_file()
        if not session_file:
            return []
        return self._reader._read_session_messages(session_file)

    def set_session_id_hint(self, session_id: str) -> None:
        if session_id:
            self._reader.set_preferred_session(session_id)

    def capture_state(self) -> Dict[str, Any]:
        session_file = self._session_file()
        messages = self._all_messages()

        offset = 0
        if session_file:
            try:
                offset = session_file.stat().st_size
            except OSError:
                offset = 0

        state: Dict[str, Any] = {
            self._path_key: session_file,
            self._count_key: len(messages),
            "message_count": len(messages),
            "offset": offset,
            "session_path": session_file,
            "session_id": session_file.stem if session_file else None,
        }
        return state

    def latest_message(self) -> Optional[str]:
        return self._reader.latest_message()

    def latest_conversations(self, n: int = 5) -> List[Tuple[str, str]]:
        return _pair_messages(self._all_messages(), n)

    def _state_message_count(self, state: Dict[str, Any]) -> int:
        for key in (self._count_key, "message_count", "msg_count"):
            value = state.get(key)
            if isinstance(value, int):
                return max(0, value)
        return 0

    def try_get_message(self, state: Dict[str, Any]) -> Tuple[Optional[str], Dict[str, Any]]:
        baseline = CommState(message_count=self._state_message_count(state))
        message = self._reader.try_get_message(baseline)
        return message, self.capture_state()

    def wait_for_message(
        self,
        state: Dict[str, Any],
        timeout: float = 300.0,
        poll_interval: float = 1.0,
    ) -> Tuple[Optional[str], Dict[str, Any]]:
        baseline = CommState(message_count=self._state_message_count(state))
        message = self._reader.wait_for_message(
            baseline,
            timeout=timeout,
            poll_interval=poll_interval,
        )
        return message, self.capture_state()


class LegacyCommunicator:
    """Small compatibility communicator used by ``*ping`` commands."""

    def __init__(
        self,
        provider_label: str,
        log_reader: LegacyLogReaderAdapter,
    ):
        self.provider_label = provider_label
        self._log_reader = log_reader

    @property
    def log_reader(self) -> LegacyLogReaderAdapter:
        return self._log_reader

    def ping(self, *, display: bool = True) -> Tuple[bool, str]:
        state = self.log_reader.capture_state()
        session_ref = state.get("session_path") or state.get("log_path") or state.get("session_id")
        healthy = bool(session_ref)

        if healthy:
            message = f"✅ {self.provider_label} session detected"
        else:
            message = f"No active {self.provider_label} session found"

        if display:
            _emit(message)
        return healthy, message

    def latest_message(self) -> Optional[str]:
        return self.log_reader.latest_message()

    def wait_for_reply(self, timeout: float = 300.0) -> Optional[str]:
        state = self.log_reader.capture_state()
        message, _ = self.log_reader.wait_for_message(state, timeout=timeout)
        return message

