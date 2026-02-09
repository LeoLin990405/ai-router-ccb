from __future__ import annotations
import json
import os
import shlex
import subprocess
import time
from typing import Optional

try:
    from .terminal_utils import (
        HANDLED_EXCEPTIONS,
        TerminalBackend,
        _choose_wezterm_cli_cwd,
        _default_shell,
        _env_float,
        _extract_wsl_path_from_unc_like_path,
        _get_wezterm_bin,
        _is_windows_wezterm,
        _run,
        is_windows,
        is_wsl,
    )
except ImportError:  # pragma: no cover - script mode
    from terminal_utils import (
        HANDLED_EXCEPTIONS,
        TerminalBackend,
        _choose_wezterm_cli_cwd,
        _default_shell,
        _env_float,
        _extract_wsl_path_from_unc_like_path,
        _get_wezterm_bin,
        _is_windows_wezterm,
        _run,
        is_windows,
        is_wsl,
    )


class WeztermBackend(TerminalBackend):
    _wezterm_bin: Optional[str] = None
    CCB_TITLE_MARKER = "CCB"

    @classmethod
    def _cli_base_args(cls) -> list[str]:
        args = [cls._bin(), "cli"]
        wezterm_class = os.environ.get("CODEX_WEZTERM_CLASS") or os.environ.get("WEZTERM_CLASS")
        if wezterm_class:
            args.extend(["--class", wezterm_class])
        if os.environ.get("CODEX_WEZTERM_PREFER_MUX", "").lower() in {"1", "true", "yes", "on"}:
            args.append("--prefer-mux")
        if os.environ.get("CODEX_WEZTERM_NO_AUTO_START", "").lower() in {"1", "true", "yes", "on"}:
            args.append("--no-auto-start")
        return args

    @classmethod
    def _bin(cls) -> str:
        if cls._wezterm_bin:
            return cls._wezterm_bin
        found = _get_wezterm_bin()
        cls._wezterm_bin = found or "wezterm"
        return cls._wezterm_bin

    def _send_key_cli(self, pane_id: str, key: str) -> bool:
        """
        Send a key to the target pane using `wezterm cli send-key`.

        WezTerm CLI syntax differs across versions; try a couple variants.
        """
        key = (key or "").strip()
        if not key:
            return False

        variants = [key]
        if key.lower() == "enter":
            variants = ["Enter", "Return", key]
        elif key.lower() in {"escape", "esc"}:
            variants = ["Escape", "Esc", key]

        for variant in variants:
            # Variant A: `send-key --pane-id <id> --key <KeyName>`
            result = _run(
                [*self._cli_base_args(), "send-key", "--pane-id", pane_id, "--key", variant],
                capture_output=True,
                timeout=2.0,
            )
            if result.returncode == 0:
                return True

            # Variant B: `send-key --pane-id <id> <KeyName>`
            result = _run(
                [*self._cli_base_args(), "send-key", "--pane-id", pane_id, variant],
                capture_output=True,
                timeout=2.0,
            )
            if result.returncode == 0:
                return True

        return False

    def _send_enter(self, pane_id: str) -> None:
        """
        Send Enter to submit the current input in a TUI.

        Some TUIs in raw mode may ignore a pasted newline byte and require a real key event;
        prefer `wezterm cli send-key` when available.
        """
        # Windows needs longer delay
        default_delay = 0.05 if os.name == "nt" else 0.01
        enter_delay = _env_float("CCB_WEZTERM_ENTER_DELAY", default_delay)
        if enter_delay:
            time.sleep(enter_delay)

        env_method_raw = os.environ.get("CCB_WEZTERM_ENTER_METHOD")
        # Default behavior: try real key event first for better TUI compatibility,
        # then fall back to a CR byte. Override via CCB_WEZTERM_ENTER_METHOD=text|key.
        default_method = "auto"
        method = (env_method_raw or default_method).strip().lower()
        if method not in {"auto", "key", "text"}:
            method = default_method

        # Retry mechanism for reliability (Windows native occasionally drops Enter)
        max_retries = 3
        for attempt in range(max_retries):
            # Prefer key injection in auto/key mode; fall back to CR byte if needed.
            if method in {"auto", "key"}:
                if self._send_key_cli(pane_id, "Enter"):
                    return

            # Fallback: send CR byte; works for shells/readline, but not for all raw-mode TUIs.
            if method in {"auto", "text", "key"}:
                result = _run(
                    [*self._cli_base_args(), "send-text", "--pane-id", pane_id, "--no-paste"],
                    input=b"\r",
                    capture_output=True,
                )
                if result.returncode == 0:
                    return

            if attempt < max_retries - 1:
                time.sleep(0.05)

    def send_text(self, pane_id: str, text: str) -> None:
        sanitized = text.replace("\r", "").strip()
        if not sanitized:
            return

        has_newlines = "\n" in sanitized

        # Single-line: always avoid paste mode (prevents Codex showing "[Pasted Content ...]").
        # Use argv for short text; stdin for long text to avoid command-line length/escaping issues.
        if not has_newlines:
            if len(sanitized) <= 200:
                _run(
                    [*self._cli_base_args(), "send-text", "--pane-id", pane_id, "--no-paste", sanitized],
                    check=True,
                )
            else:
                _run(
                    [*self._cli_base_args(), "send-text", "--pane-id", pane_id, "--no-paste"],
                    input=sanitized.encode("utf-8"),
                    check=True,
                )
            self._send_enter(pane_id)
            return

        # Slow path: multiline or long text -> use paste mode (bracketed paste)
        _run(
            [*self._cli_base_args(), "send-text", "--pane-id", pane_id],
            input=sanitized.encode("utf-8"),
            check=True,
        )

        # Wait for TUI to process bracketed paste content
        paste_delay = _env_float("CCB_WEZTERM_PASTE_DELAY", 0.1)
        if paste_delay:
            time.sleep(paste_delay)

        self._send_enter(pane_id)

    def _list_panes(self) -> list[dict]:
        try:
            result = _run(
                [*self._cli_base_args(), "list", "--format", "json"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            if result.returncode != 0:
                return []
            panes = json.loads(result.stdout)
            return panes if isinstance(panes, list) else []
        except HANDLED_EXCEPTIONS:
            return []

    def _pane_id_by_title_marker(self, panes: list[dict], marker: str) -> Optional[str]:
        if not marker:
            return None
        for pane in panes:
            title = pane.get("title") or ""
            if title.startswith(marker):
                pane_id = pane.get("pane_id")
                if pane_id is not None:
                    return str(pane_id)
        return None

    def find_pane_by_title_marker(self, marker: str) -> Optional[str]:
        panes = self._list_panes()
        return self._pane_id_by_title_marker(panes, marker)

    def is_alive(self, pane_id: str) -> bool:
        panes = self._list_panes()
        if not panes:
            return False
        if any(str(p.get("pane_id")) == str(pane_id) for p in panes):
            return True
        return self._pane_id_by_title_marker(panes, pane_id) is not None

    def get_text(self, pane_id: str, lines: int = 20) -> Optional[str]:
        """Get text content from pane (last N lines)."""
        try:
            result = _run(
                [*self._cli_base_args(), "get-text", "--pane-id", pane_id],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=2.0,
            )
            if result.returncode != 0:
                return None
            text = result.stdout
            if lines and text:
                text_lines = text.splitlines()
                return "\n".join(text_lines[-lines:])
            return text
        except HANDLED_EXCEPTIONS:
            return None

    def send_key(self, pane_id: str, key: str) -> bool:
        """Send a special key (e.g., 'Escape', 'Enter') to pane."""
        try:
            if self._send_key_cli(pane_id, key):
                return True
            result = _run(
                [*self._cli_base_args(), "send-text", "--pane-id", pane_id, "--no-paste"],
                input=key.encode("utf-8"),
                capture_output=True,
                timeout=2.0,
            )
            return result.returncode == 0
        except HANDLED_EXCEPTIONS:
            return False

    def kill_pane(self, pane_id: str) -> None:
        _run([*self._cli_base_args(), "kill-pane", "--pane-id", pane_id], stderr=subprocess.DEVNULL)

    def activate(self, pane_id: str) -> None:
        _run([*self._cli_base_args(), "activate-pane", "--pane-id", pane_id])

    def create_pane(self, cmd: str, cwd: str, direction: str = "right", percent: int = 50, parent_pane: Optional[str] = None) -> str:
        args = [*self._cli_base_args(), "split-pane"]
        force_wsl = os.environ.get("CCB_BACKEND_ENV", "").lower() == "wsl"
        wsl_unc_cwd = _extract_wsl_path_from_unc_like_path(cwd)
        # If the caller is in a WSL UNC path (e.g. Git Bash `/wsl.localhost/...`),
        # default to launching via wsl.exe so the new pane lands in the real WSL path.
        if is_windows() and wsl_unc_cwd and not force_wsl:
            force_wsl = True
        use_wsl_launch = (is_wsl() and _is_windows_wezterm()) or (force_wsl and is_windows())
        if use_wsl_launch:
            in_wsl_pane = bool(os.environ.get("WSL_DISTRO_NAME") or os.environ.get("WSL_INTEROP"))
            wsl_cwd = wsl_unc_cwd or cwd
            if wsl_unc_cwd is None and ("\\" in cwd or (len(cwd) > 2 and cwd[1] == ":")):
                try:
                    wslpath_cmd = ["wslpath", "-a", cwd] if is_wsl() else ["wsl.exe", "wslpath", "-a", cwd]
                    result = _run(wslpath_cmd, capture_output=True, text=True, check=True, encoding="utf-8", errors="replace")
                    wsl_cwd = result.stdout.strip()
                except HANDLED_EXCEPTIONS:
                    pass
            if direction == "right":
                args.append("--right")
            elif direction == "bottom":
                args.append("--bottom")
            elif direction == "top":
                args.append("--top")
            elif direction == "left":
                args.append("--left")
            args.extend(["--percent", str(percent)])
            if parent_pane:
                args.extend(["--pane-id", parent_pane])
            # Do not `exec` here: `cmd` may be a compound shell snippet (e.g. keep-open wrappers).
            startup_script = f"cd {shlex.quote(wsl_cwd)} && {cmd}"
            if in_wsl_pane:
                args.extend(["--", "bash", "-l", "-i", "-c", startup_script])
            else:
                args.extend(["--", "wsl.exe", "bash", "-l", "-i", "-c", startup_script])
        else:
            args.extend(["--cwd", cwd])
            if direction == "right":
                args.append("--right")
            elif direction == "bottom":
                args.append("--bottom")
            elif direction == "top":
                args.append("--top")
            elif direction == "left":
                args.append("--left")
            args.extend(["--percent", str(percent)])
            if parent_pane:
                args.extend(["--pane-id", parent_pane])
            shell, flag = _default_shell()
            args.extend(["--", shell, flag, cmd])
        try:
            run_cwd = None
            if is_wsl() and _is_windows_wezterm():
                run_cwd = _choose_wezterm_cli_cwd()
            result = _run(
                args,
                capture_output=True,
                text=True,
                check=True,
                encoding="utf-8",
                errors="replace",
                cwd=run_cwd,
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"WezTerm split-pane failed:\nCommand: {' '.join(args)}\nStderr: {e.stderr}") from e


_backend_cache: Optional[TerminalBackend] = None


