"""
Gateway Client for CCB.

Provides a simple client interface for sending requests to the gateway.
Used by CLI commands (cask, gask, etc.) when CCB_USE_GATEWAY=1 is set.
"""
from __future__ import annotations

import json
import os
import time
import urllib.request
import urllib.error
from typing import Optional, Tuple


HANDLED_EXCEPTIONS = (Exception,)


def get_gateway_url() -> str:
    """Get the gateway URL from environment or default."""
    return os.environ.get("CCB_GATEWAY_URL", "http://localhost:8765")


def is_gateway_enabled() -> bool:
    """Check if gateway mode is enabled."""
    val = os.environ.get("CCB_USE_GATEWAY", "").lower()
    return val in ("1", "true", "yes", "on")


def gateway_ask(
    message: str,
    provider: Optional[str] = None,
    timeout_s: float = 300.0,
    priority: int = 50,
    wait: bool = True,
) -> Tuple[Optional[str], int]:
    """
    Send a request to the gateway.

    Args:
        message: The message to send
        provider: Provider name (auto-routed if not specified)
        timeout_s: Request timeout in seconds
        priority: Request priority (higher = more urgent)
        wait: Whether to wait for the response

    Returns:
        Tuple of (response_text, exit_code)
        exit_code is 0 on success, non-zero on error
    """
    gateway_url = get_gateway_url()

    # Submit request
    ask_url = f"{gateway_url}/api/ask"
    data = {
        "message": message,
        "timeout_s": timeout_s,
        "priority": priority,
    }
    if provider:
        data["provider"] = provider

    try:
        req = urllib.request.Request(
            ask_url,
            data=json.dumps(data).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            result = json.loads(response.read().decode())

        request_id = result.get("request_id")
        if not request_id:
            return "Error: No request ID returned", 1

        if not wait:
            return f"Request submitted: {request_id}", 0

        # Wait for response
        reply_url = f"{gateway_url}/api/reply/{request_id}?wait=true&timeout={timeout_s}"
        with urllib.request.urlopen(reply_url, timeout=timeout_s + 30) as response:
            reply = json.loads(response.read().decode())

        status = reply.get("status")
        if status == "completed":
            return reply.get("response", ""), 0
        elif status == "failed":
            return f"Error: {reply.get('error', 'Unknown error')}", 1
        elif status == "timeout":
            return "Error: Request timed out", 1
        elif status == "cancelled":
            return "Error: Request was cancelled", 1
        elif status in ("processing", "queued", "retrying"):
            # Request is still in progress - this means the wait timeout was reached
            # but the backend is still working. Return a helpful message.
            return f"Error: Request still {status} after {timeout_s}s wait. The backend may need more time. Use *pend command to check later.", 1
        else:
            return f"Error: Unexpected status: {status}", 1

    except urllib.error.URLError as e:
        return f"Error: Cannot connect to gateway at {gateway_url}: {e}", 1
    except HANDLED_EXCEPTIONS as e:
        return f"Error: {e}", 1


def gateway_status() -> Tuple[Optional[dict], int]:
    """
    Get gateway status.

    Returns:
        Tuple of (status_dict, exit_code)
    """
    gateway_url = get_gateway_url()

    try:
        url = f"{gateway_url}/api/status"
        with urllib.request.urlopen(url, timeout=5) as response:
            data = json.loads(response.read().decode())
        return data, 0
    except urllib.error.URLError as e:
        return None, 1
    except HANDLED_EXCEPTIONS as e:
        return None, 1


def gateway_health() -> bool:
    """Check if gateway is healthy."""
    gateway_url = get_gateway_url()

    try:
        url = f"{gateway_url}/api/health"
        with urllib.request.urlopen(url, timeout=2) as response:
            data = json.loads(response.read().decode())
        return data.get("status") == "ok"
    except HANDLED_EXCEPTIONS:
        return False


# Convenience functions for specific providers
def gateway_ask_codex(message: str, timeout_s: float = 300.0, wait: bool = True) -> Tuple[Optional[str], int]:
    """Send request to Codex via gateway."""
    return gateway_ask(message, provider="codex", timeout_s=timeout_s, wait=wait)


def gateway_ask_gemini(message: str, timeout_s: float = 600.0, wait: bool = True) -> Tuple[Optional[str], int]:
    """Send request to Gemini via gateway."""
    return gateway_ask(message, provider="gemini", timeout_s=timeout_s, wait=wait)


def gateway_ask_claude(message: str, timeout_s: float = 300.0, wait: bool = True) -> Tuple[Optional[str], int]:
    """Send request to Claude via gateway."""
    return gateway_ask(message, provider="claude", timeout_s=timeout_s, wait=wait)


def gateway_ask_opencode(message: str, timeout_s: float = 300.0, wait: bool = True) -> Tuple[Optional[str], int]:
    """Send request to OpenCode via gateway."""
    return gateway_ask(message, provider="opencode", timeout_s=timeout_s, wait=wait)


def gateway_ask_iflow(message: str, timeout_s: float = 300.0, wait: bool = True) -> Tuple[Optional[str], int]:
    """Send request to iFlow via gateway."""
    return gateway_ask(message, provider="iflow", timeout_s=timeout_s, wait=wait)


def gateway_ask_kimi(message: str, timeout_s: float = 300.0, wait: bool = True) -> Tuple[Optional[str], int]:
    """Send request to Kimi via gateway."""
    return gateway_ask(message, provider="kimi", timeout_s=timeout_s, wait=wait)


def gateway_ask_qwen(message: str, timeout_s: float = 300.0, wait: bool = True) -> Tuple[Optional[str], int]:
    """Send request to Qwen via gateway."""
    return gateway_ask(message, provider="qwen", timeout_s=timeout_s, wait=wait)
