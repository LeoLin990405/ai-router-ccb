"""Base communication reader abstractions for provider session files."""
from __future__ import annotations

import hashlib
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from lib.common.logging import get_logger


@dataclass
class CommState:
    """Snapshot of provider communication state."""

    session_id: Optional[str] = None
    last_mtime: float = 0.0
    last_size: int = 0
    message_count: int = 0


@dataclass
class CommMessage:
    """Unified provider message model."""

    role: str
    content: str
    timestamp: float
    metadata: Dict[str, Any] = field(default_factory=dict)


class BaseCommReader(ABC):
    """Base class for provider communication log readers."""

    def __init__(self, provider_name: str, home_dir: Optional[str] = None):
        self.provider = provider_name
        self.home_dir = Path(home_dir or self._default_home()).expanduser()
        self.logger = get_logger(f"providers.{provider_name}")
        self._preferred_session: Optional[str] = None

    @abstractmethod
    def _default_home(self) -> str:
        """Return default home directory for this provider."""

    @abstractmethod
    def _find_session_file(self) -> Optional[Path]:
        """Return session file path for current context."""

    @abstractmethod
    def _parse_messages(self, content: str) -> List[CommMessage]:
        """Parse provider session content into unified messages."""

    def _read_session_messages(self, session_file: Path) -> List[CommMessage]:
        try:
            content = session_file.read_text(encoding="utf-8")
            return self._parse_messages(content)
        except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError) as exc:
            self.logger.debug("Failed reading session file %s: %s", session_file, exc)
            return []

    def project_hash(self, path: str) -> str:
        """Compute stable project hash (SHA256/16)."""
        return hashlib.sha256(path.encode("utf-8")).hexdigest()[:16]

    def set_preferred_session(self, session_id: str) -> None:
        """Set preferred session id/path hint."""
        self._preferred_session = session_id

    def capture_state(self) -> CommState:
        """Capture current communication state."""
        session_file = self._find_session_file()
        if not session_file or not session_file.exists():
            return CommState()

        try:
            stat = session_file.stat()
        except OSError:
            return CommState()

        messages = self._read_session_messages(session_file)
        return CommState(
            session_id=session_file.stem,
            last_mtime=stat.st_mtime,
            last_size=stat.st_size,
            message_count=len(messages),
        )

    def latest_message(self) -> Optional[str]:
        """Return latest assistant message if available."""
        session_file = self._find_session_file()
        if not session_file or not session_file.exists():
            return None

        messages = self._read_session_messages(session_file)
        assistant_messages = [message for message in messages if message.role.lower() == "assistant"]
        if not assistant_messages:
            return None

        content = assistant_messages[-1].content.strip()
        return content or None

    def latest_conversations(self, n: int = 5) -> List[CommMessage]:
        """Return the latest n messages."""
        session_file = self._find_session_file()
        if not session_file or not session_file.exists():
            return []

        messages = self._read_session_messages(session_file)
        if n <= 0:
            return []
        return messages[-n:]

    def try_get_message(self, state: CommState) -> Optional[str]:
        """Non-blocking check for newly appended message."""
        new_state = self.capture_state()
        if new_state.message_count > state.message_count:
            return self.latest_message()
        return None

    def wait_for_message(
        self,
        state: CommState,
        timeout: float = 300.0,
        poll_interval: float = 2.0,
    ) -> Optional[str]:
        """Wait until a new message arrives or timeout."""
        deadline = time.time() + max(0.0, timeout)
        effective_poll = max(0.02, poll_interval)

        while time.time() < deadline:
            new_message = self.try_get_message(state)
            if new_message:
                return new_message
            time.sleep(effective_poll)

        return None
