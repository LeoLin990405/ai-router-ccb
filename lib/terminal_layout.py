from __future__ import annotations
import os
import shutil
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

try:
    from .terminal_tmux_backend import TmuxBackend
    from .terminal_wezterm_backend import WeztermBackend
    from .terminal_utils import HANDLED_EXCEPTIONS, TerminalBackend, _get_wezterm_bin, _run
except ImportError:  # pragma: no cover - script mode
    from terminal_tmux_backend import TmuxBackend
    from terminal_wezterm_backend import WeztermBackend
    from terminal_utils import HANDLED_EXCEPTIONS, TerminalBackend, _get_wezterm_bin, _run


def _current_tty() -> str | None:
    for fd in (0, 1, 2):
        try:
            return os.ttyname(fd)
        except HANDLED_EXCEPTIONS:
            continue
    return None


def _inside_tmux() -> bool:
    if not (os.environ.get("TMUX") or os.environ.get("TMUX_PANE")):
        return False
    if not shutil.which("tmux"):
        return False

    tty = _current_tty()
    pane = (os.environ.get("TMUX_PANE") or "").strip()

    if pane:
        try:
            cp = _run(
                ["tmux", "display-message", "-p", "-t", pane, "#{pane_tty}"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=0.5,
            )
            pane_tty = (cp.stdout or "").strip()
            if cp.returncode == 0 and tty and pane_tty == tty:
                return True
        except HANDLED_EXCEPTIONS:
            pass

    if tty:
        try:
            cp = _run(
                ["tmux", "display-message", "-p", "#{client_tty}"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=0.5,
            )
            client_tty = (cp.stdout or "").strip()
            if cp.returncode == 0 and client_tty == tty:
                return True
        except HANDLED_EXCEPTIONS:
            pass

    if not tty and pane:
        try:
            cp = _run(
                ["tmux", "display-message", "-p", "-t", pane, "#{pane_id}"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=0.5,
            )
            pane_id = (cp.stdout or "").strip()
            if cp.returncode == 0 and pane_id.startswith("%"):
                return True
        except HANDLED_EXCEPTIONS:
            pass

    return False


def _inside_wezterm() -> bool:
    return bool((os.environ.get("WEZTERM_PANE") or "").strip())


def detect_terminal() -> Optional[str]:
    # Priority 1: detect *current* terminal session from env vars.
    # Check tmux first - it's the "inner" environment when running WezTerm with tmux.
    if _inside_tmux():
        return "tmux"
    if _inside_wezterm():
        return "wezterm"

    return None


def _wezterm_cli_is_alive(*, timeout_s: float = 0.8) -> bool:
    """
    Best-effort probe to see if `wezterm cli` can reach a running WezTerm instance.

    Uses `--no-auto-start` so it won't pop up a new terminal window.
    """
    wez = _get_wezterm_bin()
    if not wez:
        return False
    try:
        cp = _run(
            [wez, "cli", "--no-auto-start", "list"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=max(0.1, float(timeout_s)),
        )
        return cp.returncode == 0
    except HANDLED_EXCEPTIONS:
        return False


def get_backend(terminal_type: Optional[str] = None) -> Optional[TerminalBackend]:
    global _backend_cache
    if _backend_cache:
        return _backend_cache
    t = terminal_type or detect_terminal()
    if t == "wezterm":
        _backend_cache = WeztermBackend()
    elif t == "tmux":
        _backend_cache = TmuxBackend()
    return _backend_cache


def get_backend_for_session(session_data: dict) -> Optional[TerminalBackend]:
    terminal = session_data.get("terminal", "tmux")
    if terminal == "wezterm":
        return WeztermBackend()
    return TmuxBackend()


def get_pane_id_from_session(session_data: dict) -> Optional[str]:
    terminal = session_data.get("terminal", "tmux")
    if terminal == "wezterm":
        return session_data.get("pane_id")
    # tmux legacy: older session files used `tmux_session` as a pseudo pane_id.
    # New tmux refactor stores real tmux pane IDs (`%12`) in `pane_id`.
    return session_data.get("pane_id") or session_data.get("tmux_session")


@dataclass(frozen=True)
class LayoutResult:
    panes: dict[str, str]      # provider -> pane_id
    root_pane_id: str
    needs_attach: bool
    created_panes: list[str]


def create_auto_layout(
    providers: list[str],
    *,
    cwd: str,
    root_pane_id: str | None = None,
    tmux_session_name: str | None = None,
    percent: int = 50,
    set_markers: bool = True,
    marker_prefix: str = "CCB",
) -> LayoutResult:
    """
    Create tmux split layout for 1–4 providers, returning a provider->pane_id mapping.

    Layout rules (matches docs/tmux-refactor-plan.md):
    - 1 AI: no split
    - 2 AI: left/right
    - 3 AI: left 1 + right top/bottom 2
    - 4 AI: 2x2 grid

    Notes:
    - This function only allocates panes (no provider commands launched).
    - If `set_markers` is True, it sets pane titles to `{marker_prefix}-{provider}`.
      Callers can pass a richer `marker_prefix` (e.g. include session_id) to avoid collisions.
    """
    if not providers:
        raise ValueError("providers must not be empty")
    if len(providers) > 4:
        raise ValueError("providers max is 4 for auto layout")

    backend = TmuxBackend()
    created: list[str] = []
    panes: dict[str, str] = {}

    needs_attach = False

    # Resolve/allocate root pane.
    if root_pane_id:
        root = root_pane_id
    else:
        # Prefer current pane when called from inside tmux.
        try:
            root = backend.get_current_pane_id()
        except HANDLED_EXCEPTIONS:
            # Daemon/outside tmux: create a detached session as a container.
            session_name = (tmux_session_name or f"ccb-{Path(cwd).name}-{int(time.time()) % 100000}-{os.getpid()}").strip()
            if session_name:
                # Reuse if already exists; else create.
                if not backend.is_alive(session_name):
                    backend._tmux_run(["new-session", "-d", "-s", session_name, "-c", cwd], check=True)
                cp = backend._tmux_run(["list-panes", "-t", session_name, "-F", "#{pane_id}"], capture=True, check=True)
                root = (cp.stdout or "").splitlines()[0].strip() if (cp.stdout or "").strip() else ""
            else:
                root = backend.create_pane("", cwd)
            if not root or not root.startswith("%"):
                raise RuntimeError("failed to allocate tmux root pane")
            created.append(root)
            needs_attach = (os.environ.get("TMUX") or "").strip() == ""

    panes[providers[0]] = root

    # Helper to set pane marker title
    def _mark(provider: str, pane_id: str) -> None:
        if not set_markers:
            return
        backend.set_pane_title(pane_id, f"{marker_prefix}-{provider}")

    _mark(providers[0], root)

    if len(providers) == 1:
        return LayoutResult(panes=panes, root_pane_id=root, needs_attach=needs_attach, created_panes=created)

    pct = max(1, min(99, int(percent)))

    if len(providers) == 2:
        right = backend.split_pane(root, "right", pct)
        created.append(right)
        panes[providers[1]] = right
        _mark(providers[1], right)
        return LayoutResult(panes=panes, root_pane_id=root, needs_attach=needs_attach, created_panes=created)

    if len(providers) == 3:
        right_top = backend.split_pane(root, "right", pct)
        created.append(right_top)
        right_bottom = backend.split_pane(right_top, "bottom", pct)
        created.append(right_bottom)
        panes[providers[1]] = right_top
        panes[providers[2]] = right_bottom
        _mark(providers[1], right_top)
        _mark(providers[2], right_bottom)
        return LayoutResult(panes=panes, root_pane_id=root, needs_attach=needs_attach, created_panes=created)

    # 4 providers: 2x2 grid
    right_top = backend.split_pane(root, "right", pct)
    created.append(right_top)
    left_bottom = backend.split_pane(root, "bottom", pct)
    created.append(left_bottom)
    right_bottom = backend.split_pane(right_top, "bottom", pct)
    created.append(right_bottom)

    panes[providers[1]] = right_top
    panes[providers[2]] = left_bottom
    panes[providers[3]] = right_bottom
    _mark(providers[1], right_top)
    _mark(providers[2], left_bottom)
    _mark(providers[3], right_bottom)

    return LayoutResult(panes=panes, root_pane_id=root, needs_attach=needs_attach, created_panes=created)
