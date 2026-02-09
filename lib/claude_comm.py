"""Legacy compatibility layer for Claude communication.

The canonical implementation now lives in ``lib.providers.claude``.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

try:
    from lib.providers.claude import ClaudeCommReader as ProviderClaudeCommReader
    from lib.providers.legacy_compat import LegacyCommunicator, LegacyLogReaderAdapter, load_session_hint
except ImportError:  # pragma: no cover - flat import mode
    from providers.claude import ClaudeCommReader as ProviderClaudeCommReader
    from providers.legacy_compat import LegacyCommunicator, LegacyLogReaderAdapter, load_session_hint


DEFAULT_ROOT = Path.home() / ".claude" / "projects"


def _project_key_for_path(path: Path) -> str:
    """Legacy helper kept for test and script compatibility."""
    return re.sub(r"[^A-Za-z0-9]", "-", str(path))


class ClaudeLogReader(LegacyLogReaderAdapter):
    """Legacy Claude log reader facade."""

    def __init__(
        self,
        root: Path = DEFAULT_ROOT,
        work_dir: Optional[Path] = None,
        use_sessions_index: bool = True,
    ):
        del use_sessions_index
        reader = ProviderClaudeCommReader(home_dir=str(Path(root).expanduser()), work_dir=work_dir)
        super().__init__(reader, path_key="session_path", count_key="message_count")


class ClaudeCommunicator(LegacyCommunicator):
    """Legacy communicator retained for ``lping`` compatibility."""

    def __init__(self, root: Optional[Path] = None, work_dir: Optional[Path] = None):
        log_reader = ClaudeLogReader(root=root or DEFAULT_ROOT, work_dir=work_dir)
        hint = load_session_hint("claude")
        if hint:
            log_reader.set_session_id_hint(hint)
        super().__init__("Claude", log_reader)


__all__ = ["_project_key_for_path", "ClaudeLogReader", "ClaudeCommunicator"]

