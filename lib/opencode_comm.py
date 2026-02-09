"""Legacy compatibility layer for OpenCode communication.

The canonical implementation now lives in ``lib.providers.opencode``.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

try:
    from lib.providers.legacy_compat import LegacyCommunicator, LegacyLogReaderAdapter, load_session_hint
    from lib.providers.opencode import OpenCodeCommReader as ProviderOpenCodeCommReader
except ImportError:  # pragma: no cover - flat import mode
    from providers.legacy_compat import LegacyCommunicator, LegacyLogReaderAdapter, load_session_hint
    from providers.opencode import OpenCodeCommReader as ProviderOpenCodeCommReader


def _default_storage_root() -> Path:
    xdg_data_home = (os.environ.get("XDG_DATA_HOME") or "").strip()
    if xdg_data_home:
        return Path(xdg_data_home) / "opencode" / "storage"
    return Path.home() / ".local" / "share" / "opencode" / "storage"


DEFAULT_ROOT = _default_storage_root()


class _CompatOpenCodeReader(ProviderOpenCodeCommReader):
    def __init__(self, *args, project_id: Optional[str] = None, **kwargs):
        self._forced_project_id = project_id
        super().__init__(*args, **kwargs)

    def _detect_project_id(self) -> Optional[str]:
        if self._forced_project_id:
            return self._forced_project_id
        return super()._detect_project_id()


class OpenCodeLogReader(LegacyLogReaderAdapter):
    """Legacy OpenCode log reader facade."""

    def __init__(
        self,
        root: Path = DEFAULT_ROOT,
        work_dir: Optional[Path] = None,
        project_id: Optional[str] = None,
    ):
        reader = _CompatOpenCodeReader(
            home_dir=str(Path(root).expanduser()),
            work_dir=work_dir,
            project_id=project_id,
        )
        super().__init__(reader, path_key="session_path", count_key="message_count")

    def capture_state(self):
        state = super().capture_state()
        session_file = state.get("session_path")
        if isinstance(session_file, Path):
            payload = self._reader._load_json(session_file)
            session_data = payload.get("payload") if isinstance(payload.get("payload"), dict) else payload
            if isinstance(session_data, dict):
                session_id = session_data.get("id")
                if isinstance(session_id, str) and session_id:
                    state["session_id"] = session_id
        return state


class OpenCodeCommunicator(LegacyCommunicator):
    """Legacy communicator retained for ``oping`` compatibility."""

    def __init__(
        self,
        root: Optional[Path] = None,
        work_dir: Optional[Path] = None,
        project_id: Optional[str] = None,
    ):
        log_reader = OpenCodeLogReader(
            root=root or DEFAULT_ROOT,
            work_dir=work_dir,
            project_id=project_id,
        )
        hint = load_session_hint("opencode")
        if hint:
            log_reader.set_session_id_hint(hint)
        super().__init__("OpenCode", log_reader)


__all__ = ["OpenCodeLogReader", "OpenCodeCommunicator"]

