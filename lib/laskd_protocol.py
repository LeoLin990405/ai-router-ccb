"""
laskd_protocol - Protocol utilities for Claude communication.

Contains prompt wrapping and parsing functions for the Claude provider.
"""

from __future__ import annotations

import re
from typing import Pattern


REQ_ID_PREFIX = "CCB_REQ_ID:"
DONE_PREFIX = "CCB_DONE:"

DONE_LINE_RE_TEMPLATE = r"^\s*CCB_DONE:\s*{req_id}\s*$"

_TRAILING_DONE_TAG_RE = re.compile(
    r"^\s*(?!CCB_DONE\s*:)[A-Z][A-Z0-9_]*_DONE(?:\s*:\s*[0-9a-fA-F]{32})?\s*$"
)
_ANY_CCB_DONE_LINE_RE = re.compile(r"^\s*CCB_DONE:\s*[0-9a-fA-F]{32}\s*$")


def _is_trailing_noise_line(line: str) -> bool:
    if (line or "").strip() == "":
        return True
    # Some harnesses append a generic completion tag after the requested CCB_DONE line.
    # Treat it as ignorable trailer, not as a completion marker for our protocol.
    return bool(_TRAILING_DONE_TAG_RE.match(line or ""))


def wrap_claude_prompt(message: str, req_id: str) -> str:
    """
    Wrap a prompt for Claude with CCB protocol markers.
    
    Args:
        message: The user's message/question
        req_id: Unique request identifier (hex string)
    
    Returns:
        Formatted prompt with protocol instructions
    """
    message = (message or "").rstrip()
    return (
        f"{REQ_ID_PREFIX} {req_id}\n\n"
        f"{message}\n\n"
        "IMPORTANT:\n"
        "- Reply normally, in English.\n"
        "- End your reply with this exact final line (verbatim, on its own line):\n"
        f"{DONE_PREFIX} {req_id}\n"
    )


def done_line_re(req_id: str) -> Pattern[str]:
    """Compile regex for matching the DONE line for a specific request ID."""
    return re.compile(DONE_LINE_RE_TEMPLATE.format(req_id=re.escape(req_id)))


def is_done_text(text: str, req_id: str) -> bool:
    """
    Check if text ends with the correct CCB_DONE line.
    
    Args:
        text: Text to check
        req_id: Request ID to look for
    
    Returns:
        True if the text ends with CCB_DONE: <req_id>
    """
    lines = [ln.rstrip() for ln in (text or "").splitlines()]
    for i in range(len(lines) - 1, -1, -1):
        if _is_trailing_noise_line(lines[i]):
            continue
        return bool(done_line_re(req_id).match(lines[i]))
    return False


def strip_done_text(text: str, req_id: str) -> str:
    """
    Remove the CCB_DONE line and any trailing noise from text.
    
    Args:
        text: Text containing reply and protocol markers
        req_id: Request ID of the DONE line to strip
    
    Returns:
        Clean reply text without protocol markers
    """
    lines = [ln.rstrip("\n") for ln in (text or "").splitlines()]
    if not lines:
        return ""

    while lines and _is_trailing_noise_line(lines[-1]):
        lines.pop()

    if lines and done_line_re(req_id).match(lines[-1] or ""):
        lines.pop()

    while lines and _is_trailing_noise_line(lines[-1]):
        lines.pop()

    return "\n".join(lines).rstrip()