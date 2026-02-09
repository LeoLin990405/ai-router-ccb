"""Legacy compatibility layer for Kimi communication.

The canonical implementation now lives in ``lib.providers.kimi``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

try:
    from lib.providers.kimi import KimiCommReader as ProviderKimiCommReader
    from lib.providers.legacy_compat import LegacyCommunicator, LegacyLogReaderAdapter, load_session_hint
except ImportError:  # pragma: no cover - flat import mode
    from providers.kimi import KimiCommReader as ProviderKimiCommReader
    from providers.legacy_compat import LegacyCommunicator, LegacyLogReaderAdapter, load_session_hint


DEFAULT_ROOT = Path.home() / ".kimi" / "sessions"


def _normalize_kimi_home(root: Path) -> Path:
    expanded = root.expanduser()
    return expanded.parent if expanded.name == "sessions" else expanded


class KimiLogReader(LegacyLogReaderAdapter):
    """Legacy Kimi log reader facade."""

    def __init__(self, root: Path = DEFAULT_ROOT, work_dir: Optional[Path] = None):
        reader = ProviderKimiCommReader(
            home_dir=str(_normalize_kimi_home(Path(root))),
            work_dir=work_dir,
        )
        super().__init__(reader, path_key="session_path", count_key="message_count")


class KimiCommunicator(LegacyCommunicator):
    """Legacy communicator retained for ``kping`` compatibility."""

    def __init__(self, root: Optional[Path] = None, work_dir: Optional[Path] = None):
        log_reader = KimiLogReader(root=root or DEFAULT_ROOT, work_dir=work_dir)
        hint = load_session_hint("kimi")
        if hint:
            log_reader.set_session_id_hint(hint)
        super().__init__("Kimi", log_reader)


__all__ = ["KimiLogReader", "KimiCommunicator"]

