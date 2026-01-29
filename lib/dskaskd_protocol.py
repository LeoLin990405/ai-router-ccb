from __future__ import annotations

import re
from dataclasses import dataclass

from ccb_protocol import DONE_PREFIX, REQ_ID_PREFIX, strip_done_text, make_req_id


REPLY_BEGIN_PREFIX = "CCB_REPLY_BEGIN:"

_ANY_DONE_RE = re.compile(r"CCB_DONE:\s*[0-9a-fA-F]{32}")


def _marker_re(prefix: str, req_id: str) -> re.Pattern[str]:
    return re.compile(rf"{re.escape(prefix)}\s*{re.escape(req_id)}", re.IGNORECASE)


def wrap_deepseek_prompt(message: str, req_id: str) -> str:
    message = (message or "").rstrip()
    return (
        f"{REQ_ID_PREFIX} {req_id}\n\n"
        f"{message}\n\n"
        "IMPORTANT:\n"
        "- Start your reply with this exact first line (verbatim, on its own line):\n"
        f"{REPLY_BEGIN_PREFIX} {req_id}\n"
        "- End your reply with this exact final line (verbatim, on its own line):\n"
        f"{DONE_PREFIX} {req_id}\n"
    )


def is_done_text(text: str, req_id: str) -> bool:
    if not text:
        return False
    return bool(_marker_re(DONE_PREFIX, req_id).search(text))


def extract_reply_for_req(text: str, req_id: str) -> str:
    lines = [ln.rstrip("\n") for ln in (text or "").splitlines()]
    if not lines:
        return ""

    done_re = _marker_re(DONE_PREFIX, req_id)
    begin_re = _marker_re(REPLY_BEGIN_PREFIX, req_id)

    target_done: int | None = None
    for i in range(len(lines) - 1, -1, -1):
        if done_re.search(lines[i] or ""):
            target_done = i
            break

    if target_done is None:
        return strip_done_text(text, req_id)

    begin_idx: int | None = None
    for i in range(target_done - 1, -1, -1):
        if begin_re.search(lines[i] or ""):
            begin_idx = i
            break

    if begin_idx is not None:
        segment = lines[begin_idx + 1 : target_done]
    else:
        prev_done: int | None = None
        for i in range(target_done - 1, -1, -1):
            if _ANY_DONE_RE.search(lines[i] or ""):
                prev_done = i
                break
        start_idx = prev_done + 1 if prev_done is not None else 0
        segment = lines[start_idx:target_done]

    while segment and segment[0].strip() == "":
        segment = segment[1:]
    while segment and segment[-1].strip() == "":
        segment = segment[:-1]
    return "\n".join(segment).rstrip()


@dataclass(frozen=True)
class DskaskdRequest:
    client_id: str
    work_dir: str
    timeout_s: float
    quiet: bool
    message: str
    output_path: str | None = None


@dataclass(frozen=True)
class DskaskdResult:
    exit_code: int
    reply: str
    req_id: str
    session_key: str
    done_seen: bool
    done_ms: int | None = None
