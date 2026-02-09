"""Legacy compatibility layer for Gemini communication.

The canonical implementation now lives in ``lib.providers.gemini``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

try:
    from lib.providers.gemini import GeminiCommReader as ProviderGeminiCommReader
    from lib.providers.legacy_compat import LegacyCommunicator, LegacyLogReaderAdapter, load_session_hint
except ImportError:  # pragma: no cover - flat import mode
    from providers.gemini import GeminiCommReader as ProviderGeminiCommReader
    from providers.legacy_compat import LegacyCommunicator, LegacyLogReaderAdapter, load_session_hint


DEFAULT_ROOT = Path.home() / ".gemini" / "tmp"


class GeminiLogReader(LegacyLogReaderAdapter):
    """Legacy Gemini log reader facade."""

    def __init__(self, root: Path = DEFAULT_ROOT, work_dir: Optional[Path] = None):
        reader = ProviderGeminiCommReader(home_dir=str(Path(root).expanduser()), work_dir=work_dir)
        super().__init__(reader, path_key="session_path", count_key="msg_count")


class GeminiCommunicator(LegacyCommunicator):
    """Legacy communicator retained for ``gping`` compatibility."""

    def __init__(self, root: Optional[Path] = None, work_dir: Optional[Path] = None):
        log_reader = GeminiLogReader(root=root or DEFAULT_ROOT, work_dir=work_dir)
        hint = load_session_hint("gemini")
        if hint:
            log_reader.set_session_id_hint(hint)
        super().__init__("Gemini", log_reader)


__all__ = ["GeminiLogReader", "GeminiCommunicator"]

