"""Legacy compatibility layer for Codex communication.

The canonical implementation now lives in ``lib.providers.codex``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

try:
    from lib.providers.codex import CodexCommReader as ProviderCodexCommReader
    from lib.providers.legacy_compat import LegacyCommunicator, LegacyLogReaderAdapter, load_session_hint
except ImportError:  # pragma: no cover - flat import mode
    from providers.codex import CodexCommReader as ProviderCodexCommReader
    from providers.legacy_compat import LegacyCommunicator, LegacyLogReaderAdapter, load_session_hint


DEFAULT_ROOT = Path.home() / ".codex" / "sessions"


class CodexLogReader(LegacyLogReaderAdapter):
    """Legacy Codex log reader facade."""

    def __init__(
        self,
        root: Path = DEFAULT_ROOT,
        log_path: Optional[Path] = None,
        session_id_filter: Optional[str] = None,
        work_dir: Optional[Path] = None,
    ):
        reader = ProviderCodexCommReader(home_dir=str(Path(root).expanduser()), work_dir=work_dir)
        super().__init__(reader, path_key="log_path", count_key="message_count")

        if log_path:
            self.set_session_id_hint(str(log_path))
        elif session_id_filter:
            self.set_session_id_hint(session_id_filter)

    def set_preferred_log(self, log_path: Optional[Path]) -> None:
        if log_path:
            self.set_session_id_hint(str(log_path))


class CodexCommunicator(LegacyCommunicator):
    """Legacy communicator retained for ``cping`` compatibility."""

    def __init__(self, root: Optional[Path] = None, work_dir: Optional[Path] = None):
        log_reader = CodexLogReader(root=root or DEFAULT_ROOT, work_dir=work_dir)
        hint = load_session_hint("codex")
        if hint:
            log_reader.set_session_id_hint(hint)
        super().__init__("Codex", log_reader)


__all__ = ["CodexLogReader", "CodexCommunicator"]

