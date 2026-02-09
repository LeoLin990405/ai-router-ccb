from __future__ import annotations
import os
import re
import subprocess
from pathlib import Path
from typing import Optional

try:
    from .terminal_utils import HANDLED_EXCEPTIONS, TerminalBackend, _run
except ImportError:  # pragma: no cover - script mode
    from terminal_utils import HANDLED_EXCEPTIONS, TerminalBackend, _run


class TmuxBackend(TerminalBackend):
    """
    tmux backend (pane-oriented).

    Compatibility note:
    - New API prefers tmux pane IDs like `%12`.
    - Legacy CCB code may still pass a tmux *session name* as `pane_id` (pure tmux mode).
      For backward compatibility, methods accept both:
        - If target starts with `%` or contains `:`/`.` it is treated as a tmux target (pane/window/session:win.pane).
        - Otherwise it is treated as a tmux session name (single-pane session legacy behavior).
    - Uses tmux pane_id (`%xx`) + pane title marker for daemon rediscovery.
    """

    _ANSI_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")

    def __init__(self, *, socket_name: str | None = None):
        # Optional tmux server socket isolation (like `tmux -L <name>`). Useful for daemon mode.
        self._socket_name = (socket_name or os.environ.get("CCB_TMUX_SOCKET") or "").strip() or None

    def _tmux_base(self) -> list[str]:
        cmd = ["tmux"]
        if self._socket_name:
            cmd.extend(["-L", self._socket_name])
        return cmd

    def _tmux_run(self, args: list[str], *, check: bool = False, capture: bool = False, input_bytes: bytes | None = None,
                  timeout: float | None = None) -> subprocess.CompletedProcess:
        kwargs: dict = {}
        if capture:
            kwargs.update({
                "capture_output": True,
                "text": True,
                "encoding": "utf-8",
                "errors": "replace",
            })
        if input_bytes is not None:
            kwargs["input"] = input_bytes
        if timeout is not None:
            kwargs["timeout"] = timeout
        return _run([*self._tmux_base(), *args], check=check, **kwargs)

    @staticmethod
    def _looks_like_pane_id(value: str) -> bool:
        v = (value or "").strip()
        return v.startswith("%")

    def pane_exists(self, pane_id: str) -> bool:
        """
        Return True if the tmux pane target exists.

        A pane can exist even if its process has exited (`#{pane_dead} == 1`).
        """
        if not self._looks_like_pane_id(pane_id):
            return False
        try:
            cp = self._tmux_run(["display-message", "-p", "-t", pane_id, "#{pane_id}"], capture=True, timeout=0.5)
            return cp.returncode == 0 and (cp.stdout or "").strip().startswith("%")
        except HANDLED_EXCEPTIONS:
            return False

    @staticmethod
    def _looks_like_tmux_target(value: str) -> bool:
        v = (value or "").strip()
        if not v:
            return False
        return v.startswith("%") or (":" in v) or ("." in v)

    def get_current_pane_id(self) -> str:
        """
        Return current tmux pane id in `%xx` format.

        Notes:
        - Prefer `$TMUX_PANE` because it refers to the pane where this process runs; it stays
          stable even if splits change the client's focused pane.
        - `$TMUX_PANE` can become stale if that pane was killed/replaced; fall back to querying tmux.
        """
        env_pane = (os.environ.get("TMUX_PANE") or "").strip()
        if self._looks_like_pane_id(env_pane) and self.pane_exists(env_pane):
            return env_pane

        try:
            cp = self._tmux_run(["display-message", "-p", "#{pane_id}"], capture=True, timeout=0.5)
            out = (cp.stdout or "").strip()
            if self._looks_like_pane_id(out) and self.pane_exists(out):
                return out
        except HANDLED_EXCEPTIONS:
            pass

        raise RuntimeError("tmux current pane id not available")

    def split_pane(self, parent_pane_id: str, direction: str, percent: int) -> str:
        """
        Split `parent_pane_id` and return the created tmux pane id (`%xx`), using `-P -F`.
        """
        if not parent_pane_id:
            raise ValueError("parent_pane_id is required")

        # tmux cannot split a zoomed pane; unzoom automatically for a smoother UX.
        try:
            if self._looks_like_pane_id(parent_pane_id):
                zoom_cp = self._tmux_run(
                    ["display-message", "-p", "-t", parent_pane_id, "#{window_zoomed_flag}"],
                    capture=True,
                    timeout=0.5,
                )
                if zoom_cp.returncode == 0 and (zoom_cp.stdout or "").strip() in ("1", "on", "yes", "true"):
                    self._tmux_run(["resize-pane", "-Z", "-t", parent_pane_id], check=False, timeout=0.5)
        except HANDLED_EXCEPTIONS:
            pass

        # Allow splitting a "dead" pane (remain-on-exit); only fail if the pane target doesn't exist.
        if self._looks_like_pane_id(parent_pane_id) and not self.pane_exists(parent_pane_id):
            raise RuntimeError(f"Cannot split: pane {parent_pane_id} does not exist")

        size_cp = self._tmux_run(
            ["display-message", "-p", "-t", parent_pane_id, "#{pane_width}x#{pane_height}"],
            capture=True,
        )
        pane_size = (size_cp.stdout or "").strip() if size_cp.returncode == 0 else "unknown"

        direction_norm = (direction or "").strip().lower()
        if direction_norm in ("right", "h", "horizontal"):
            flag = "-h"
        elif direction_norm in ("bottom", "v", "vertical"):
            flag = "-v"
        else:
            raise ValueError(f"unsupported direction: {direction!r} (use 'right' or 'bottom')")

        # NOTE: Do not pass `-p <percent>` here.
        #
        # tmux 3.4 can error with `size missing` when splitting panes by percentage in detached
        # sessions (e.g. auto-created sessions before any client is attached). Using tmux's default
        # 50% split avoids that class of failures and is what CCB uses for its layouts anyway.
        try:
            cp = self._tmux_run(
                ["split-window", flag, "-t", parent_pane_id, "-P", "-F", "#{pane_id}"],
                check=True,
                capture=True,
            )
        except subprocess.CalledProcessError as e:
            out = (getattr(e, "stdout", "") or "").strip()
            err = (getattr(e, "stderr", "") or "").strip()
            msg = err or out
            raise RuntimeError(
                f"tmux split-window failed (exit {e.returncode}): {msg or 'no stdout/stderr'}\n"
                f"Pane: {parent_pane_id}, size: {pane_size}, direction: {direction_norm}\n"
                f"Command: {' '.join(e.cmd)}\n"
                f"Hint: If the pane is zoomed, press Prefix+z to unzoom; also try enlarging terminal window."
            ) from e
        pane_id = (cp.stdout or "").strip()
        if not self._looks_like_pane_id(pane_id):
            raise RuntimeError(f"tmux split-window did not return pane_id: {pane_id!r}")
        return pane_id

    def set_pane_title(self, pane_id: str, title: str) -> None:
        if not pane_id:
            return
        self._tmux_run(["select-pane", "-t", pane_id, "-T", title or ""], check=False)

    def set_pane_user_option(self, pane_id: str, name: str, value: str) -> None:
        """
        Set a tmux user option (e.g. `@ccb_agent`) at pane scope.

        This is used to keep UI labeling stable even if programs modify `pane_title`.
        """
        if not pane_id:
            return
        opt = (name or "").strip()
        if not opt:
            return
        if not opt.startswith("@"):
            opt = "@" + opt
        self._tmux_run(["set-option", "-p", "-t", pane_id, opt, value or ""], check=False)

    def find_pane_by_title_marker(self, marker: str) -> Optional[str]:
        marker = (marker or "").strip()
        if not marker:
            return None
        cp = self._tmux_run(["list-panes", "-a", "-F", "#{pane_id}\t#{pane_title}"], capture=True)
        if cp.returncode != 0:
            return None
        for line in (cp.stdout or "").splitlines():
            if not line.strip():
                continue
            if "\t" in line:
                pid, title = line.split("\t", 1)
            else:
                parts = line.split(" ", 1)
                pid, title = (parts[0], parts[1] if len(parts) > 1 else "")
            if (title or "").startswith(marker):
                pid = pid.strip()
                if self._looks_like_pane_id(pid):
                    return pid
        return None

    def get_pane_content(self, pane_id: str, lines: int = 20) -> Optional[str]:
        if not pane_id:
            return None
        n = max(1, int(lines))
        cp = self._tmux_run(["capture-pane", "-t", pane_id, "-p", "-S", f"-{n}"], capture=True)
        if cp.returncode != 0:
            return None
        text = cp.stdout or ""
        return self._ANSI_RE.sub("", text)

    # Keep compatibility with existing daemon code
    def get_text(self, pane_id: str, lines: int = 20) -> Optional[str]:
        return self.get_pane_content(pane_id, lines=lines)

    def is_pane_alive(self, pane_id: str) -> bool:
        if not pane_id:
            return False
        cp = self._tmux_run(["display-message", "-p", "-t", pane_id, "#{pane_dead}"], capture=True)
        if cp.returncode != 0:
            return False
        return (cp.stdout or "").strip() == "0"

    def _ensure_not_in_copy_mode(self, pane_id: str) -> None:
        try:
            cp = self._tmux_run(["display-message", "-p", "-t", pane_id, "#{pane_in_mode}"], capture=True, timeout=1.0)
            if cp.returncode == 0 and (cp.stdout or "").strip() in ("1", "on", "yes"):
                self._tmux_run(["send-keys", "-t", pane_id, "-X", "cancel"], check=False)
        except HANDLED_EXCEPTIONS:
            pass

    def send_text(self, pane_id: str, text: str) -> None:
        sanitized = (text or "").replace("\r", "").strip()
        if not sanitized:
            return

        # Legacy: treat `pane_id` as a tmux session name for pure-tmux mode.
        if not self._looks_like_tmux_target(pane_id):
            session = pane_id
            if "\n" not in sanitized and len(sanitized) <= 200:
                self._tmux_run(["send-keys", "-t", session, "-l", sanitized], check=True)
                self._tmux_run(["send-keys", "-t", session, "Enter"], check=True)
                return
            buffer_name = f"ccb-tb-{os.getpid()}-{int(time.time() * 1000)}"
            self._tmux_run(["load-buffer", "-b", buffer_name, "-"], check=True, input_bytes=sanitized.encode("utf-8"))
            try:
                self._tmux_run(["paste-buffer", "-t", session, "-b", buffer_name, "-p"], check=True)
                enter_delay = _env_float("CCB_TMUX_ENTER_DELAY", 0.5)
                if enter_delay:
                    time.sleep(enter_delay)
                self._tmux_run(["send-keys", "-t", session, "Enter"], check=True)
            finally:
                self._tmux_run(["delete-buffer", "-b", buffer_name], check=False)
            return

        # Pane-oriented: bracketed paste + unique tmux buffer + cleanup
        self._ensure_not_in_copy_mode(pane_id)
        buffer_name = f"ccb-tb-{os.getpid()}-{int(time.time() * 1000)}"
        self._tmux_run(["load-buffer", "-b", buffer_name, "-"], check=True, input_bytes=sanitized.encode("utf-8"))
        try:
            self._tmux_run(["paste-buffer", "-p", "-t", pane_id, "-b", buffer_name], check=True)
            enter_delay = _env_float("CCB_TMUX_ENTER_DELAY", 0.5)
            if enter_delay:
                time.sleep(enter_delay)
            self._tmux_run(["send-keys", "-t", pane_id, "Enter"], check=True)
        finally:
            self._tmux_run(["delete-buffer", "-b", buffer_name], check=False)

    def send_key(self, pane_id: str, key: str) -> bool:
        key = (key or "").strip()
        if not pane_id or not key:
            return False
        try:
            cp = self._tmux_run(["send-keys", "-t", pane_id, key], capture=True, timeout=2.0)
            return cp.returncode == 0
        except HANDLED_EXCEPTIONS:
            return False

    def is_alive(self, pane_id: str) -> bool:
        # Backward-compatible: pane_id may be a session name.
        if not pane_id:
            return False
        if self._looks_like_tmux_target(pane_id):
            return self.is_pane_alive(pane_id)
        cp = self._tmux_run(["has-session", "-t", pane_id], capture=True)
        return cp.returncode == 0

    def kill_pane(self, pane_id: str) -> None:
        if not pane_id:
            return
        if self._looks_like_tmux_target(pane_id):
            self._tmux_run(["kill-pane", "-t", pane_id], check=False)
        else:
            # Legacy: treat as session name.
            self._tmux_run(["kill-session", "-t", pane_id], check=False)

    def activate(self, pane_id: str) -> None:
        # Best-effort: focus pane if inside tmux; otherwise attach its session if resolvable.
        if not pane_id:
            return
        if self._looks_like_tmux_target(pane_id):
            self._tmux_run(["select-pane", "-t", pane_id], check=False)
            if not os.environ.get("TMUX"):
                try:
                    cp = self._tmux_run(["display-message", "-p", "-t", pane_id, "#{session_name}"], capture=True)
                    sess = (cp.stdout or "").strip()
                    if sess:
                        self._tmux_run(["attach", "-t", sess], check=False)
                except HANDLED_EXCEPTIONS:
                    pass
            return
        self._tmux_run(["attach", "-t", pane_id], check=False)

    def respawn_pane(self, pane_id: str, *, cmd: str, cwd: str | None = None,
                     stderr_log_path: str | None = None, remain_on_exit: bool = True) -> None:
        """
        Respawn a pane process (`respawn-pane -k`) to (re)mount an AI CLI session.

        This is daemon-friendly: pane stays stable; only the process is replaced.
        """
        if not pane_id:
            raise ValueError("pane_id is required")

        cmd_body = (cmd or "").strip()
        if not cmd_body:
            raise ValueError("cmd is required")

        start_dir = (cwd or "").strip()
        if start_dir in ("", "."):
            start_dir = ""

        if stderr_log_path:
            log_path = str(Path(stderr_log_path).expanduser().resolve())
            Path(log_path).parent.mkdir(parents=True, exist_ok=True)
            cmd_body = f"{cmd_body} 2>> {shlex.quote(log_path)}"

        shell = (os.environ.get("CCB_TMUX_SHELL") or "").strip()
        if not shell:
            # Prefer tmux's configured default shell when available.
            try:
                cp = self._tmux_run(["show-option", "-gqv", "default-shell"], capture=True, timeout=1.0)
                shell = (cp.stdout or "").strip()
            except HANDLED_EXCEPTIONS:
                shell = ""
        if not shell:
            shell = (os.environ.get("SHELL") or "").strip()
        if not shell:
            shell = _default_shell()[0]

        flags_raw = (os.environ.get("CCB_TMUX_SHELL_FLAGS") or "").strip()
        if flags_raw:
            flags = shlex.split(flags_raw)
        else:
            shell_name = Path(shell).name.lower()
            # Avoid assuming bash-style combined flags on shells like fish.
            if shell_name in {"bash", "zsh", "ksh"}:
                flags = ["-l", "-i", "-c"]
            elif shell_name == "fish":
                flags = ["-l", "-i", "-c"]
            elif shell_name in {"sh", "dash"}:
                flags = ["-c"]
            else:
                # Unknown shell: keep it minimal for compatibility.
                flags = ["-c"]

        full_argv = [shell, *flags, cmd_body]
        full = " ".join(shlex.quote(a) for a in full_argv)

        # Prevent a race where a fast-exiting command closes the pane before we can set remain-on-exit.
        if remain_on_exit:
            self._tmux_run(["set-option", "-p", "-t", pane_id, "remain-on-exit", "on"], check=False)

        tmux_args = ["respawn-pane", "-k", "-t", pane_id]
        if start_dir:
            tmux_args.extend(["-c", start_dir])
        tmux_args.append(full)
        self._tmux_run(tmux_args, check=True)
        if remain_on_exit:
            self._tmux_run(["set-option", "-p", "-t", pane_id, "remain-on-exit", "on"], check=False)

    def save_crash_log(self, pane_id: str, crash_log_path: str, *, lines: int = 1000) -> None:
        text = self.get_pane_content(pane_id, lines=lines) or ""
        p = Path(crash_log_path).expanduser()
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")

    def create_pane(self, cmd: str, cwd: str, direction: str = "right", percent: int = 50,
                    parent_pane: Optional[str] = None) -> str:
        """
        Create a new pane and run `cmd` inside it.

        - If `parent_pane` is provided (or we are inside tmux), split that pane.
        - If called outside tmux without `parent_pane`, create a detached session and return its root pane id.
        """
        cmd = (cmd or "").strip()
        cwd = (cwd or ".").strip() or "."

        base: str | None = (parent_pane or "").strip() or None
        if not base:
            try:
                base = self.get_current_pane_id()
            except HANDLED_EXCEPTIONS:
                base = None

        if base:
            new_pane = self.split_pane(base, direction=direction, percent=percent)
            if cmd:
                self.respawn_pane(new_pane, cmd=cmd, cwd=cwd)
            return new_pane

        # Outside tmux: create a new detached tmux session as a root container.
        session_name = f"ccb-{Path(cwd).name}-{int(time.time()) % 100000}-{os.getpid()}"
        self._tmux_run(["new-session", "-d", "-s", session_name, "-c", cwd], check=True)
        cp = self._tmux_run(["list-panes", "-t", session_name, "-F", "#{pane_id}"], capture=True, check=True)
        pane_id = (cp.stdout or "").splitlines()[0].strip() if (cp.stdout or "").strip() else ""
        if not self._looks_like_pane_id(pane_id):
            raise RuntimeError(f"tmux failed to resolve root pane_id for session {session_name!r}")
        if cmd:
            self.respawn_pane(pane_id, cmd=cmd, cwd=cwd)
        return pane_id


