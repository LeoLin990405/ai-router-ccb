"""Legacy compatibility layer for iFlow communication.

The canonical implementation now lives in ``lib.providers.iflow``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

try:
    from lib.providers.iflow import IFlowCommReader as ProviderIFlowCommReader
    from lib.providers.legacy_compat import LegacyCommunicator, LegacyLogReaderAdapter, load_session_hint
except ImportError:  # pragma: no cover - flat import mode
    from providers.iflow import IFlowCommReader as ProviderIFlowCommReader
    from providers.legacy_compat import LegacyCommunicator, LegacyLogReaderAdapter, load_session_hint


DEFAULT_ROOT = Path.home() / ".iflow" / "projects"


def _normalize_iflow_home(root: Path) -> Path:
    expanded = root.expanduser()
    return expanded.parent if expanded.name == "projects" else expanded


def _path_to_iflow_slug(path: str) -> str:
    """Legacy helper kept for test and script compatibility."""
    slug = str(path).replace("/", "-")
    if not slug.startswith("-"):
        slug = f"-{slug}"
    return slug


class IFlowLogReader(LegacyLogReaderAdapter):
    """Legacy iFlow log reader facade."""

    def __init__(self, root: Path = DEFAULT_ROOT, work_dir: Optional[Path] = None):
        reader = ProviderIFlowCommReader(
            home_dir=str(_normalize_iflow_home(Path(root))),
            work_dir=work_dir,
        )
        super().__init__(reader, path_key="session_path", count_key="message_count")


class IFlowCommunicator(LegacyCommunicator):
    """Legacy communicator retained for ``iping`` compatibility."""

    def __init__(self, root: Optional[Path] = None, work_dir: Optional[Path] = None):
        log_reader = IFlowLogReader(root=root or DEFAULT_ROOT, work_dir=work_dir)
        hint = load_session_hint("iflow")
        if hint:
            log_reader.set_session_id_hint(hint)
        super().__init__("IFlow", log_reader)


__all__ = ["_path_to_iflow_slug", "IFlowLogReader", "IFlowCommunicator"]

