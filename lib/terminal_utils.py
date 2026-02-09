from __future__ import annotations
import json
import os
import platform
import re
import shlex
import shutil
import subprocess
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        value = float(raw)
    except ValueError:
        return default
    return max(0.0, value)


def is_windows() -> bool:
    return platform.system() == "Windows"


def _subprocess_kwargs() -> dict:
    """
    返回适合当前平台的subprocess参数，避免Windows上创建可见窗口

    在Windows上使用CREATE_NO_WINDOW标志，确保subprocess调用不会弹出CMD窗口。
    注意：不使用DETACHED_PROCESS，以保留控制台继承能力。
    """
    if os.name == "nt":
        # CREATE_NO_WINDOW (0x08000000): 创建无窗口的进程
        # 这允许子进程继承父进程的隐藏控制台，而不是创建新的可见窗口
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
        return {"creationflags": flags}
    return {}


def _run(*args, **kwargs):
    """Wrapper for subprocess.run that adds hidden window on Windows."""
    kwargs.update(_subprocess_kwargs())
    import subprocess as _sp
    return _sp.run(*args, **kwargs)


def is_wsl() -> bool:
    try:
        return "microsoft" in Path("/proc/version").read_text().lower()
    except HANDLED_EXCEPTIONS:
        return False


def _choose_wezterm_cli_cwd() -> str | None:
    """
    Pick a safe cwd for launching Windows `wezterm.exe` from inside WSL.

    When a Windows binary is launched via WSL interop from a WSL cwd (e.g. /home/...),
    Windows may treat the process cwd as a UNC path like \\\\wsl.localhost\\...,
    which can confuse WezTerm's WSL relay and produce noisy `chdir(/wsl.localhost/...) failed 2`.
    Using a Windows-mounted path like /mnt/c avoids that.
    """
    override = (os.environ.get("CCB_WEZTERM_CLI_CWD") or "").strip()
    candidates = [override] if override else []
    candidates.extend(["/mnt/c", "/mnt/d", "/mnt"])
    for candidate in candidates:
        if not candidate:
            continue
        try:
            p = Path(candidate)
            if p.is_dir():
                return str(p)
        except HANDLED_EXCEPTIONS:
            continue
    return None


def _extract_wsl_path_from_unc_like_path(raw: str) -> str | None:
    """
    Convert UNC-like WSL paths into a WSL-internal absolute path.

    Supports forms commonly seen in Git Bash/MSYS and Windows:
      - /wsl.localhost/Ubuntu-24.04/home/user/...
      - \\\\wsl.localhost\\Ubuntu-24.04\\home\\user\\...
      - /wsl$/Ubuntu-24.04/home/user/...
    Returns a POSIX absolute path like: /home/user/...
    """
    if not raw:
        return None

    m = re.match(r'^(?:[/\\]{1,2})(?:wsl\.localhost|wsl\$)[/\\]([^/\\]+)(.*)$', raw, re.IGNORECASE)
    if not m:
        return None
    remainder = m.group(2).replace("\\", "/")
    if not remainder:
        return "/"
    if not remainder.startswith("/"):
        remainder = "/" + remainder
    return remainder


def _load_cached_wezterm_bin() -> str | None:
    """Load cached WezTerm path from installation"""
    candidates: list[Path] = []
    xdg = (os.environ.get("XDG_CONFIG_HOME") or "").strip()
    if xdg:
        candidates.append(Path(xdg) / "ccb" / "env")
    if os.name == "nt":
        localappdata = (os.environ.get("LOCALAPPDATA") or "").strip()
        if localappdata:
            candidates.append(Path(localappdata) / "ccb" / "env")
        appdata = (os.environ.get("APPDATA") or "").strip()
        if appdata:
            candidates.append(Path(appdata) / "ccb" / "env")
    candidates.append(Path.home() / ".config" / "ccb" / "env")

    for config in candidates:
        try:
            if not config.exists():
                continue
            for line in config.read_text(encoding="utf-8", errors="replace").splitlines():
                if line.startswith("CODEX_WEZTERM_BIN="):
                    path = line.split("=", 1)[1].strip()
                    if path and Path(path).exists():
                        return path
        except HANDLED_EXCEPTIONS:
            continue
    return None


_cached_wezterm_bin: str | None = None


def _get_wezterm_bin() -> str | None:
    """Get WezTerm path (with cache)"""
    global _cached_wezterm_bin
    if _cached_wezterm_bin:
        return _cached_wezterm_bin
    # Priority: env var > install cache > PATH > hardcoded paths
    override = os.environ.get("CODEX_WEZTERM_BIN") or os.environ.get("WEZTERM_BIN")
    if override and Path(override).exists():
        _cached_wezterm_bin = override
        return override
    cached = _load_cached_wezterm_bin()
    if cached:
        _cached_wezterm_bin = cached
        return cached
    found = shutil.which("wezterm") or shutil.which("wezterm.exe")
    if found:
        _cached_wezterm_bin = found
        return found
    if is_wsl():
        for drive in "cdefghijklmnopqrstuvwxyz":
            for path in [f"/mnt/{drive}/Program Files/WezTerm/wezterm.exe",
                         f"/mnt/{drive}/Program Files (x86)/WezTerm/wezterm.exe"]:
                if Path(path).exists():
                    _cached_wezterm_bin = path
                    return path
    return None


def _is_windows_wezterm() -> bool:
    """Detect if WezTerm is running on Windows"""
    override = os.environ.get("CODEX_WEZTERM_BIN") or os.environ.get("WEZTERM_BIN")
    if override:
        if ".exe" in override.lower() or "/mnt/" in override:
            return True
    if shutil.which("wezterm.exe"):
        return True
    if is_wsl():
        for drive in "cdefghijklmnopqrstuvwxyz":
            for path in [f"/mnt/{drive}/Program Files/WezTerm/wezterm.exe",
                         f"/mnt/{drive}/Program Files (x86)/WezTerm/wezterm.exe"]:
                if Path(path).exists():
                    return True
    return False


def _default_shell() -> tuple[str, str]:
    if is_wsl():
        return "bash", "-c"
    if is_windows():
        for shell in ["pwsh", "powershell"]:
            if shutil.which(shell):
                return shell, "-Command"
        return "powershell", "-Command"
    return "bash", "-c"


def get_shell_type() -> str:
    if is_windows() and os.environ.get("CCB_BACKEND_ENV", "").lower() == "wsl":
        return "bash"
    shell, _ = _default_shell()
    if shell in ("pwsh", "powershell"):
        return "powershell"
    return "bash"


HANDLED_EXCEPTIONS = (Exception,)


class TerminalBackend(ABC):
    @abstractmethod
    def send_text(self, pane_id: str, text: str) -> None: ...
    @abstractmethod
    def is_alive(self, pane_id: str) -> bool: ...
    @abstractmethod
    def kill_pane(self, pane_id: str) -> None: ...
    @abstractmethod
    def activate(self, pane_id: str) -> None: ...
    @abstractmethod
    def create_pane(self, cmd: str, cwd: str, direction: str = "right", percent: int = 50, parent_pane: Optional[str] = None) -> str: ...


