"""Legacy compatibility layer for Droid communication.

The canonical implementation now lives in ``lib.providers.droid``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

try:
    from lib.providers.droid import DroidCommReader as ProviderDroidCommReader
    from lib.providers.legacy_compat import LegacyCommunicator, LegacyLogReaderAdapter, load_session_hint
except ImportError:  # pragma: no cover - flat import mode
    from providers.droid import DroidCommReader as ProviderDroidCommReader
    from providers.legacy_compat import LegacyCommunicator, LegacyLogReaderAdapter, load_session_hint


DEFAULT_ROOT = Path.home() / ".factory" / "sessions"


class DroidLogReader(LegacyLogReaderAdapter):
    """Legacy Droid log reader facade."""

    def __init__(self, root: Path = DEFAULT_ROOT, work_dir: Optional[Path] = None):
        reader = ProviderDroidCommReader(home_dir=str(Path(root).expanduser()), work_dir=work_dir)
        super().__init__(reader, path_key="session_path", count_key="message_count")


class DroidCommunicator(LegacyCommunicator):
    """Legacy communicator retained for ``dping`` compatibility."""

    def __init__(self, root: Optional[Path] = None, work_dir: Optional[Path] = None):
        log_reader = DroidLogReader(root=root or DEFAULT_ROOT, work_dir=work_dir)
        hint = load_session_hint("droid")
        if hint:
            log_reader.set_session_id_hint(hint)
        super().__init__("Droid", log_reader)


__all__ = ["DroidLogReader", "DroidCommunicator"]

