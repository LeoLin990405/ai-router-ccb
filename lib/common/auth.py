"""Shared auth utilities for provider CLIs."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import webbrowser
from typing import Optional

from .logging import get_logger

logger = get_logger("common.auth")

AUTH_INDICATORS = {
    "codex": ["sign in", "not authenticated", "authentication required"],
    "gemini": ["authenticate", "login required", "gcloud auth"],
    "kimi": ["login", "认证", "token expired"],
    "qwen": ["qwen-oauth", "login"],
    "iflow": ["not authenticated"],
    "opencode": ["authenticate"],
    "claude": ["login", "auth", "not authenticated"],
    "droid": ["login", "auth", "not authenticated"],
}

GENERIC_AUTH_INDICATORS = [
    "authorization",
    "authenticate",
    "login required",
    "not logged in",
    "credentials",
    "token expired",
    "unauthorized",
]

AUTH_URL_PATTERN = re.compile(
    r"https?://[^\s\"'<>]+(?:auth|login|oauth|sign-in|authorize)[^\s\"'<>]*",
    re.IGNORECASE,
)


def should_auto_open_auth() -> bool:
    """Check whether auth URLs/terminals should be auto-opened."""
    val = os.environ.get("CCB_AUTO_OPEN_AUTH", "1").lower()
    return val in ("1", "true", "yes", "on")


def open_auth_url(url: str) -> bool:
    """Open authentication URL in browser."""
    open_cmd = shutil.which("open")
    if open_cmd:
        try:
            subprocess.run([open_cmd, url], check=True, capture_output=True)
            return True
        except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError):
            logger.exception("Failed to open auth URL with system open command: %s", url)

    try:
        return bool(webbrowser.open(url))
    except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError):
        logger.exception("Failed to open auth URL with webbrowser: %s", url)

    return False


def open_auth_terminal(provider: str) -> bool:
    """Open a terminal window to run provider auth command."""
    auth_commands = {
        "gemini": "gemini -i 'Please authenticate'",
        "claude": "claude auth login",
        "codex": "codex auth login",
    }

    cmd = auth_commands.get(provider)
    if not cmd:
        return False

    wezterm_path = shutil.which("wezterm")
    if wezterm_path:
        try:
            subprocess.Popen(
                [wezterm_path, "cli", "spawn", "--", "bash", "-c", f"{cmd}; echo 'Press Enter to close'; read"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return True
        except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError):
            logger.debug("Failed to open auth command via wezterm", exc_info=True)

    osascript_path = shutil.which("osascript")
    if osascript_path:
        script = f'''
        tell application "Terminal"
            activate
            do script "{cmd}"
        end tell
        '''
        try:
            subprocess.run([osascript_path, "-e", script], check=True, capture_output=True)
            return True
        except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError):
            logger.debug("Failed to open auth command via osascript", exc_info=True)

    return False


def extract_auth_url(output: str) -> Optional[str]:
    """Extract an authentication URL from command output."""
    if not output:
        return None
    match = AUTH_URL_PATTERN.search(output)
    return match.group(0) if match else None


def is_auth_required(output: str, provider: str) -> bool:
    """Check whether output indicates auth is required."""
    if not output:
        return False
    output_lower = output.lower()
    indicators = AUTH_INDICATORS.get(provider, [])
    if any(keyword in output_lower for keyword in indicators):
        return True
    return any(keyword in output_lower for keyword in GENERIC_AUTH_INDICATORS)


def handle_auth(output: str, provider: str, auto_open: bool = True) -> Optional[str]:
    """Handle auth-needed output and optionally open browser URL."""
    if not is_auth_required(output, provider):
        return None

    url = extract_auth_url(output)
    if url and auto_open:
        logger.info("Opening auth URL for %s: %s", provider, url)
        try:
            webbrowser.open(url)
        except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError):
            logger.exception("Failed to open auth URL for %s", provider)
    elif url:
        logger.info("Auth required for %s: %s", provider, url)
    else:
        logger.info("Auth required for %s but no URL found", provider)

    return url
