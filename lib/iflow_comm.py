"""
iFlow communication module.

Reads replies from ~/.iflow/projects/<project-slug>/session-<uuid>.jsonl and
sends prompts by injecting text into the iFlow pane via the configured backend.
"""

from __future__ import annotations

import heapq
import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from ccb_config import apply_backend_env
from pane_registry import upsert_registry
from project_id import compute_ccb_project_id
from session_utils import find_project_session_file, safe_write_session
from terminal import get_backend_for_session, get_pane_id_from_session

apply_backend_env()


def _default_projects_root() -> Path:
    override = (os.environ.get("IFLOW_PROJECTS_ROOT") or "").strip()
    if override:
        return Path(override).expanduser()
    iflow_home = (os.environ.get("IFLOW_HOME") or "").strip()
    base = Path(iflow_home).expanduser() if iflow_home else (Path.home() / ".iflow")
    return base / "projects"


IFLOW_PROJECTS_ROOT = _default_projects_root()


def _normalize_path_for_match(value: str) -> str:
    s = (value or "").strip()
    if os.name == "nt":
        if len(s) >= 4 and s[0] == "/" and s[2] == "/" and s[1].isalpha():
            s = f"{s[1].lower()}:/{s[3:]}"
        if s.startswith("/mnt/") and len(s) > 6:
            drive = s[5]
            if drive.isalpha() and s[6:7] == "/":
                s = f"{drive.lower()}:/{s[7:]}"
    try:
        path = Path(s).expanduser()
        normalized = str(path.absolute())
    except Exception:
        normalized = str(value or "")
    normalized = normalized.replace("\\", "/").rstrip("/")
    if os.name == "nt":
        normalized = normalized.lower()
    return normalized


def _path_is_same_or_parent(parent: str, child: str) -> bool:
    parent_norm = _normalize_path_for_match(parent)
    child_norm = _normalize_path_for_match(child)
    if not parent_norm or not child_norm:
        return False
    if parent_norm == child_norm:
        return True
    if not child_norm.startswith(parent_norm):
        return False
    return child_norm == parent_norm or child_norm[len(parent_norm) :].startswith("/")


def _path_to_iflow_slug(path: str) -> str:
    """Convert a path to iFlow's project slug format (e.g., -Users-leo-Desktop-AI)."""
    normalized = path.replace("/", "-").replace("\\", "-")
    if normalized.startswith("-"):
        return normalized
    return "-" + normalized


def read_iflow_session_start(session_path: Path, *, max_lines: int = 30) -> Tuple[Optional[str], Optional[str]]:
    """
    Best-effort read of the first entry for (cwd, session_id).
    iFlow stores sessionId in each entry.
    """
    try:
        with session_path.open("r", encoding="utf-8", errors="replace") as handle:
            for _ in range(max_lines):
                line = handle.readline()
                if not line:
                    break
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except Exception:
                    continue
                if not isinstance(entry, dict):
                    continue
                session_id = entry.get("sessionId")
                sid_str = str(session_id).strip() if isinstance(session_id, str) else None
                # iFlow doesn't store cwd in session, derive from path
                return None, sid_str or None
    except OSError:
        return None, None
    return None, None


def _extract_content_text(content: Any) -> Optional[str]:
    if content is None:
        return None
    if isinstance(content, str):
        return content.strip() or None
    if not isinstance(content, list):
        return None
    texts: List[str] = []
    for item in content:
        if not isinstance(item, dict):
            continue
        item_type = str(item.get("type") or "").strip().lower()
        if item_type in ("thinking", "thinking_delta", "tool_use"):
            continue
        text = item.get("text")
        if not text and item_type == "text":
            text = item.get("content")
        if isinstance(text, str) and text.strip():
            texts.append(text.strip())
    if not texts:
        return None
    return "\n".join(texts).strip()


def _extract_message(entry: dict, role: str) -> Optional[str]:
    if not isinstance(entry, dict):
        return None
    entry_type = str(entry.get("type") or "").strip().lower()

    # iFlow format: {"type": "assistant", "message": {"role": "assistant", "content": [...]}}
    if entry_type == role:
        message = entry.get("message")
        if isinstance(message, dict):
            return _extract_content_text(message.get("content"))

    # Alternative format
    if entry_type == "message":
        message = entry.get("message")
        if isinstance(message, dict):
            msg_role = str(message.get("role") or "").strip().lower()
            if msg_role == role:
                return _extract_content_text(message.get("content"))

    msg_role = str(entry.get("role") or entry_type).strip().lower()
    if msg_role == role:
        return _extract_content_text(entry.get("content") or entry.get("message"))
    return None


class IFlowLogReader:
    """Reads iFlow session logs from ~/.iflow/projects"""

    def __init__(self, root: Path = IFLOW_PROJECTS_ROOT, work_dir: Optional[Path] = None):
        self.root = Path(root).expanduser()
        self.work_dir = work_dir or Path.cwd()
        self._preferred_session: Optional[Path] = None
        self._session_id_hint: Optional[str] = None
        try:
            poll = float(os.environ.get("IFLOW_POLL_INTERVAL", "0.05"))
        except Exception:
            poll = 0.05
        self._poll_interval = min(0.5, max(0.02, poll))
        try:
            limit = int(os.environ.get("IFLOW_SESSION_SCAN_LIMIT", "200"))
        except Exception:
            limit = 200
        self._scan_limit = max(1, limit)

    def set_preferred_session(self, session_path: Optional[Path]) -> None:
        if not session_path:
            return
        try:
            candidate = session_path if isinstance(session_path, Path) else Path(str(session_path)).expanduser()
        except Exception:
            return
        if candidate.exists():
            self._preferred_session = candidate

    def set_session_id_hint(self, session_id: Optional[str]) -> None:
        if not session_id:
            return
        self._session_id_hint = str(session_id).strip()

    def current_session_path(self) -> Optional[Path]:
        return self._latest_session()

    def _find_session_by_id(self) -> Optional[Path]:
        session_id = (self._session_id_hint or "").strip()
        if not session_id or not self.root.exists():
            return None
        latest: Optional[Path] = None
        latest_mtime = -1.0
        try:
            for path in self.root.glob(f"**/session-{session_id}.jsonl"):
                if not path.is_file():
                    continue
                try:
                    mtime = path.stat().st_mtime
                except OSError:
                    continue
                if mtime >= latest_mtime:
                    latest_mtime = mtime
                    latest = path
        except Exception:
            return None
        return latest

    def _find_project_dir(self) -> Optional[Path]:
        """Find the iFlow project directory for current work_dir."""
        work_dir_str = str(self.work_dir.absolute())
        slug = _path_to_iflow_slug(work_dir_str)
        project_dir = self.root / slug
        if project_dir.exists():
            return project_dir
        return None

    def _scan_latest_session(self) -> Optional[Path]:
        if not self.root.exists():
            return None

        # First try to find project-specific directory
        project_dir = self._find_project_dir()
        if project_dir and project_dir.exists():
            latest: Optional[Path] = None
            latest_mtime = -1.0
            try:
                for path in project_dir.glob("session-*.jsonl"):
                    if not path.is_file():
                        continue
                    try:
                        mtime = path.stat().st_mtime
                    except OSError:
                        continue
                    if mtime >= latest_mtime:
                        latest_mtime = mtime
                        latest = path
            except Exception:
                pass
            if latest:
                return latest

        # Fallback: scan all projects
        heap: List[Tuple[float, str]] = []
        try:
            for path in self.root.glob("*/session-*.jsonl"):
                if not path.is_file() or path.name.startswith("."):
                    continue
                try:
                    mtime = path.stat().st_mtime
                except OSError:
                    continue
                item = (mtime, str(path))
                if len(heap) < self._scan_limit:
                    heapq.heappush(heap, item)
                else:
                    if item[0] > heap[0][0]:
                        heapq.heapreplace(heap, item)
        except Exception:
            return None

        if heap:
            candidates = sorted(heap, key=lambda x: x[0], reverse=True)
            return Path(candidates[0][1]) if candidates else None
        return None

    def _latest_session(self) -> Optional[Path]:
        preferred = self._preferred_session
        scanned = self._scan_latest_session()

        if preferred and preferred.exists():
            if scanned and scanned.exists():
                try:
                    pref_mtime = preferred.stat().st_mtime
                    scan_mtime = scanned.stat().st_mtime
                    if scan_mtime > pref_mtime:
                        self._preferred_session = scanned
                        return scanned
                except OSError:
                    pass
            return preferred

        by_id = self._find_session_by_id()
        if by_id:
            self._preferred_session = by_id
            return by_id

        if scanned:
            self._preferred_session = scanned
            return scanned

        return None

    def capture_state(self) -> Dict[str, Any]:
        session = self._latest_session()
        offset = 0
        if session and session.exists():
            try:
                offset = session.stat().st_size
            except OSError:
                offset = 0
        return {"session_path": session, "offset": offset, "carry": b""}

    def wait_for_message(self, state: Dict[str, Any], timeout: float) -> Tuple[Optional[str], Dict[str, Any]]:
        return self._read_since(state, timeout=timeout, block=True)

    def try_get_message(self, state: Dict[str, Any]) -> Tuple[Optional[str], Dict[str, Any]]:
        return self._read_since(state, timeout=0.0, block=False)

    def latest_message(self) -> Optional[str]:
        session = self._latest_session()
        if not session or not session.exists():
            return None
        last: Optional[str] = None
        try:
            with session.open("r", encoding="utf-8", errors="replace") as handle:
                for line in handle:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                    except Exception:
                        continue
                    msg = _extract_message(entry, "assistant")
                    if msg:
                        last = msg
        except OSError:
            return None
        return last

    def latest_conversations(self, n: int = 1) -> List[Tuple[str, str]]:
        session = self._latest_session()
        if not session or not session.exists():
            return []
        pairs: List[Tuple[str, str]] = []
        last_user: Optional[str] = None
        try:
            with session.open("r", encoding="utf-8", errors="replace") as handle:
                for line in handle:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                    except Exception:
                        continue
                    user_msg = _extract_message(entry, "user")
                    if user_msg:
                        last_user = user_msg
                        continue
                    assistant_msg = _extract_message(entry, "assistant")
                    if assistant_msg:
                        pairs.append((last_user or "", assistant_msg))
                        last_user = None
        except OSError:
            return []
        return pairs[-max(1, int(n)) :]

    def _read_since(self, state: Dict[str, Any], timeout: float, block: bool) -> Tuple[Optional[str], Dict[str, Any]]:
        deadline = time.time() + max(0.0, float(timeout)) if block else time.time()
        current_state = dict(state or {})

        while True:
            session = self._latest_session()
            if session is None or not session.exists():
                if not block or time.time() >= deadline:
                    return None, current_state
                time.sleep(self._poll_interval)
                continue

            if current_state.get("session_path") != session:
                current_state["session_path"] = session
                current_state["offset"] = 0
                current_state["carry"] = b""

            message, current_state = self._read_new_messages(session, current_state)
            if message:
                return message, current_state

            if not block or time.time() >= deadline:
                return None, current_state
            time.sleep(self._poll_interval)

    def _read_new_messages(self, session: Path, state: Dict[str, Any]) -> Tuple[Optional[str], Dict[str, Any]]:
        offset = int(state.get("offset") or 0)
        carry = state.get("carry") or b""
        try:
            size = session.stat().st_size
        except OSError:
            return None, state

        if size < offset:
            offset = 0
            carry = b""

        try:
            with session.open("rb") as handle:
                handle.seek(offset)
                data = handle.read()
        except OSError:
            return None, state

        new_offset = offset + len(data)
        buf = carry + data
        lines = buf.split(b"\n")
        if buf and not buf.endswith(b"\n"):
            carry = lines.pop()
        else:
            carry = b""

        latest: Optional[str] = None
        for raw in lines:
            line = raw.strip()
            if not line:
                continue
            try:
                entry = json.loads(line.decode("utf-8", errors="replace"))
            except Exception:
                continue
            msg = _extract_message(entry, "assistant")
            if msg:
                latest = msg

        new_state = {"session_path": session, "offset": new_offset, "carry": carry}
        return latest, new_state


class IFlowCommunicator:
    """Communicate with iFlow via terminal and read replies from session logs."""

    def __init__(self, lazy_init: bool = False):
        self.session_info = self._load_session_info()
        if not self.session_info:
            raise RuntimeError("❌ No active iFlow session found. Run 'ccb iflow' (or add iflow to ccb.config) first")

        self.session_id = str(self.session_info.get("session_id") or "").strip()
        self.terminal = self.session_info.get("terminal", "tmux")
        self.pane_id = get_pane_id_from_session(self.session_info) or ""
        self.backend = get_backend_for_session(self.session_info)
        self.timeout = int(os.environ.get("IFLOW_SYNC_TIMEOUT", os.environ.get("CCB_SYNC_TIMEOUT", "3600")))
        self.marker_prefix = "iask"
        self.project_session_file = self.session_info.get("_session_file")

        self._log_reader: Optional[IFlowLogReader] = None
        self._log_reader_primed = False

        self._publish_registry()

        if not lazy_init:
            self._ensure_log_reader()
            healthy, msg = self._check_session_health()
            if not healthy:
                raise RuntimeError(f"❌ Session unhealthy: {msg}\nHint: run ccb iflow (or add iflow to ccb.config) to start a new session")

    @property
    def log_reader(self) -> IFlowLogReader:
        if self._log_reader is None:
            self._ensure_log_reader()
        return self._log_reader

    def _ensure_log_reader(self) -> None:
        if self._log_reader is not None:
            return
        work_dir_hint = self.session_info.get("work_dir")
        log_work_dir = Path(work_dir_hint) if isinstance(work_dir_hint, str) and work_dir_hint else None
        self._log_reader = IFlowLogReader(work_dir=log_work_dir)
        preferred_session = self.session_info.get("iflow_session_path")
        if preferred_session:
            self._log_reader.set_preferred_session(Path(str(preferred_session)))
        session_id = self.session_info.get("iflow_session_id")
        if session_id:
            self._log_reader.set_session_id_hint(session_id)
        if not self._log_reader_primed:
            self._prime_log_binding()
            self._log_reader_primed = True

    def _find_session_file(self) -> Optional[Path]:
        env_session = (os.environ.get("CCB_SESSION_FILE") or "").strip()
        if env_session:
            try:
                session_path = Path(os.path.expanduser(env_session))
                if session_path.name == ".iflow-session" and session_path.is_file():
                    return session_path
            except Exception:
                pass
        return find_project_session_file(Path.cwd(), ".iflow-session")

    def _load_session_info(self) -> Optional[dict]:
        project_session = self._find_session_file()
        if not project_session:
            return None
        try:
            with project_session.open("r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict) or data.get("active", False) is False:
                return None
            data["_session_file"] = str(project_session)
            return data
        except Exception:
            return None

    def _prime_log_binding(self) -> None:
        session_path = self.log_reader.current_session_path()
        if not session_path:
            return
        self._remember_iflow_session(session_path)

    def _publish_registry(self) -> None:
        try:
            wd = self.session_info.get("work_dir")
            ccb_pid = compute_ccb_project_id(Path(wd)) if isinstance(wd, str) and wd else ""
            upsert_registry(
                {
                    "ccb_session_id": self.session_id,
                    "ccb_project_id": ccb_pid or None,
                    "work_dir": wd,
                    "terminal": self.terminal,
                    "providers": {
                        "iflow": {
                            "pane_id": self.pane_id or None,
                            "pane_title_marker": self.session_info.get("pane_title_marker"),
                            "session_file": self.project_session_file,
                            "iflow_session_id": self.session_info.get("iflow_session_id"),
                            "iflow_session_path": self.session_info.get("iflow_session_path"),
                        }
                    },
                }
            )
        except Exception:
            pass

    def _check_session_health(self) -> Tuple[bool, str]:
        return self._check_session_health_impl(probe_terminal=True)

    def _check_session_health_impl(self, probe_terminal: bool) -> Tuple[bool, str]:
        try:
            if not self.pane_id:
                return False, "Session pane id not found"
            if probe_terminal and self.backend and not self.backend.is_alive(self.pane_id):
                return False, f"{self.terminal} session {self.pane_id} not found"
            return True, "Session OK"
        except Exception as exc:
            return False, f"Check failed: {exc}"

    def _remember_iflow_session(self, session_path: Path) -> None:
        if not self.project_session_file:
            return
        if not session_path or not isinstance(session_path, Path):
            return
        path = Path(self.project_session_file)
        try:
            with path.open("r", encoding="utf-8", errors="replace") as f:
                data = json.load(f)
        except Exception:
            data = {}
        if not isinstance(data, dict):
            data = {}

        updated = False
        session_path_str = str(session_path)
        if data.get("iflow_session_path") != session_path_str:
            data["iflow_session_path"] = session_path_str
            updated = True

        _cwd, session_id = read_iflow_session_start(session_path)
        if session_id and data.get("iflow_session_id") != session_id:
            data["iflow_session_id"] = session_id
            updated = True

        if not (data.get("ccb_project_id") or "").strip():
            try:
                wd = data.get("work_dir")
                if isinstance(wd, str) and wd.strip():
                    data["ccb_project_id"] = compute_ccb_project_id(Path(wd.strip()))
                    updated = True
            except Exception:
                pass

        if not updated:
            return

        payload = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
        safe_write_session(path, payload)

        try:
            wd = data.get("work_dir")
            ccb_pid = str(data.get("ccb_project_id") or "").strip()
            upsert_registry(
                {
                    "ccb_session_id": self.session_id,
                    "ccb_project_id": ccb_pid or None,
                    "work_dir": wd,
                    "terminal": self.terminal,
                    "providers": {
                        "iflow": {
                            "pane_id": self.pane_id or None,
                            "pane_title_marker": data.get("pane_title_marker"),
                            "session_file": str(path),
                            "iflow_session_id": data.get("iflow_session_id"),
                            "iflow_session_path": data.get("iflow_session_path"),
                        }
                    },
                }
            )
        except Exception:
            pass

    def ping(self, display: bool = True) -> Tuple[bool, str]:
        healthy, status = self._check_session_health()
        msg = f"✅ iFlow connection OK ({status})" if healthy else f"❌ iFlow connection error: {status}"
        if display:
            print(msg)
        return healthy, msg

    def get_status(self) -> Dict[str, Any]:
        healthy, status = self._check_session_health()
        return {
            "session_id": self.session_id,
            "terminal": self.terminal,
            "pane_id": self.pane_id,
            "healthy": healthy,
            "status": status,
        }
