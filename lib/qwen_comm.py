"""Legacy compatibility layer for Qwen communication.

The canonical implementation now lives in ``lib.providers.qwen``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

try:
    from lib.providers.qwen import QwenCommReader as ProviderQwenCommReader
    from lib.providers.legacy_compat import LegacyCommunicator, LegacyLogReaderAdapter, load_session_hint
except ImportError:  # pragma: no cover - flat import mode
    from providers.qwen import QwenCommReader as ProviderQwenCommReader
    from providers.legacy_compat import LegacyCommunicator, LegacyLogReaderAdapter, load_session_hint


DEFAULT_ROOT = Path.home() / ".qwen" / "projects"


def _normalize_qwen_home(root: Path) -> Path:
    expanded = root.expanduser()
    return expanded.parent if expanded.name == "projects" else expanded


class QwenLogReader(LegacyLogReaderAdapter):
    """Legacy Qwen log reader facade."""

    def __init__(self, root: Path = DEFAULT_ROOT, work_dir: Optional[Path] = None):
        reader = ProviderQwenCommReader(
            home_dir=str(_normalize_qwen_home(Path(root))),
            work_dir=work_dir,
        )
        super().__init__(reader, path_key="session_path", count_key="message_count")


class QwenCommunicator(LegacyCommunicator):
    """Legacy communicator retained for ``qping`` compatibility."""

    def __init__(self, root: Optional[Path] = None, work_dir: Optional[Path] = None):
        log_reader = QwenLogReader(root=root or DEFAULT_ROOT, work_dir=work_dir)
        hint = load_session_hint("qwen")
        if hint:
            log_reader.set_session_id_hint(hint)
        super().__init__("Qwen", log_reader)


__all__ = ["QwenLogReader", "QwenCommunicator"]

