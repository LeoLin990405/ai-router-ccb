from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from worker_pool import BaseSessionWorker, PerSessionWorkerPool

from dskaskd_protocol import (
    DskaskdRequest,
    DskaskdResult,
    extract_reply_for_req,
    is_done_text,
    make_req_id,
    wrap_deepseek_prompt,
)
from dskaskd_session import compute_session_key, load_project_session
from pane_registry import upsert_registry
from project_id import compute_ccb_project_id
from terminal import get_backend_for_session
from askd_runtime import state_file_path, log_path, write_log, random_token
import askd_rpc
from askd_server import AskDaemonServer
from providers import DSKASKD_SPEC


_ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]")


def _now_ms() -> int:
    return int(time.time() * 1000)


def _cli_ready_wait_s(env_key: str, default: float = 12.0) -> float:
    raw = (os.environ.get(env_key) or os.environ.get("CCB_CLI_READY_WAIT_S") or "").strip()
    if raw:
        try:
            v = float(raw)
        except Exception:
            v = 0.0
        if v > 0:
            return v
    return float(default)


def _write_log(line: str) -> None:
    write_log(log_path(DSKASKD_SPEC.log_file_name), line)


def _strip_ansi(text: str) -> str:
    return _ANSI_RE.sub("", text or "")


def _sanitize_text(text: str) -> str:
    return _strip_ansi(text).replace("\r", "\n")




def _find_last_line_index(lines: list[str], needle: str) -> int:
    if not needle:
        return -1
    for i in range(len(lines) - 1, -1, -1):
        if needle in lines[i]:
            return i
    return -1


def _extract_reply_fallback(text: str, req_id: str) -> str:
    lines = [ln.rstrip("\n") for ln in (text or "").splitlines()]
    if not lines:
        return ""
    done_line = f"CCB_DONE: {req_id}"
    req_line = f"CCB_REQ_ID: {req_id}"

    start_idx = _find_last_line_index(lines, done_line)
    if start_idx < 0:
        start_idx = _find_last_line_index(lines, req_line)
    if start_idx < 0:
        return ""

    segment = lines[start_idx + 1 :]
    while segment and segment[0].strip() == "":
        segment = segment[1:]
    while segment and segment[-1].strip() == "":
        segment = segment[:-1]
    return "\n".join(segment).rstrip()



def _env_bool(name: str, default: bool = False) -> bool:
    raw = (os.environ.get(name) or '').strip().lower()
    if not raw:
        return bool(default)
    if raw in {'1', 'true', 'yes', 'y', 'on'}:
        return True
    if raw in {'0', 'false', 'no', 'n', 'off'}:
        return False
    return bool(default)

def _env_float(name: str, default: float, *, min_v: float | None = None, max_v: float | None = None) -> float:
    raw = (os.environ.get(name) or "").strip()
    try:
        value = float(raw) if raw else float(default)
    except Exception:
        value = float(default)
    if min_v is not None:
        value = max(min_v, value)
    if max_v is not None:
        value = min(max_v, value)
    return value


def _env_int(name: str, default: int, *, min_v: int | None = None, max_v: int | None = None) -> int:
    raw = (os.environ.get(name) or "").strip()
    try:
        value = int(raw) if raw else int(default)
    except Exception:
        value = int(default)
    if min_v is not None:
        value = max(min_v, value)
    if max_v is not None:
        value = min(max_v, value)
    return value




def _run_deepseek_quick(prompt: str, timeout_s: float | None) -> tuple[str, int]:
    deepseek_bin = (os.environ.get('DEEPSEEK_BIN') or '').strip() or shutil.which('deepseek')
    if not deepseek_bin:
        raise RuntimeError('deepseek binary not found in PATH')
    cmd = [deepseek_bin, '-q', prompt]
    timeout = None
    if timeout_s is not None and float(timeout_s) > 0:
        timeout = float(timeout_s)
    cp = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding='utf-8',
        errors='replace',
        timeout=timeout,
    )
    out = (cp.stdout or '').strip('\n')
    err = (cp.stderr or '').strip('\n')
    if not out and err:
        out = err
    return out, int(cp.returncode)

def _capture_pane_text(backend, pane_id: str, lines: int) -> str:
    getter = getattr(backend, "get_text", None)
    if callable(getter):
        try:
            return getter(pane_id, lines=lines) or ""
        except Exception:
            return ""
    getter = getattr(backend, "get_pane_content", None)
    if callable(getter):
        try:
            return getter(pane_id, lines=lines) or ""
        except Exception:
            return ""
    return ""


@dataclass
class _QueuedTask:
    request: DskaskdRequest
    created_ms: int
    req_id: str
    done_event: threading.Event
    result: Optional[DskaskdResult] = None


class _SessionWorker(BaseSessionWorker[_QueuedTask, DskaskdResult]):
    def _handle_exception(self, exc: Exception, task: _QueuedTask) -> DskaskdResult:
        _write_log(f"[ERROR] session={self.session_key} req_id={task.req_id} {exc}")
        return DskaskdResult(
            exit_code=1,
            reply=str(exc),
            req_id=task.req_id,
            session_key=self.session_key,
            done_seen=False,
            done_ms=None,
        )

    def _handle_task(self, task: _QueuedTask) -> DskaskdResult:
        started_ms = _now_ms()
        req = task.request
        work_dir = Path(req.work_dir)
        _write_log(f"[INFO] start session={self.session_key} req_id={task.req_id} work_dir={req.work_dir}")

        if _env_bool("CCB_DSKASKD_QUICK_MODE", True):
            try:
                quick_prompt = wrap_deepseek_prompt(req.message, task.req_id)
                ready_wait_s = _cli_ready_wait_s("CCB_DSKASKD_READY_WAIT_S", 12.0)
                if ready_wait_s > 0:
                    time.sleep(ready_wait_s)
                out, rc = _run_deepseek_quick(quick_prompt, req.timeout_s)
                if out:
                    reply = extract_reply_for_req(out, task.req_id) or out.strip()
                    done_seen = bool(is_done_text(out, task.req_id)) or bool(reply)
                    done_ms = _now_ms() - started_ms
                    return DskaskdResult(
                        exit_code=0 if reply else (rc or 2),
                        reply=reply,
                        req_id=task.req_id,
                        session_key=self.session_key,
                        done_seen=done_seen,
                        done_ms=done_ms,
                    )
            except Exception as exc:
                _write_log(f"[WARN] quick mode failed session={self.session_key} req_id={task.req_id}: {exc}")

        session = load_project_session(work_dir)
        if not session:
            return DskaskdResult(
                exit_code=1,
                reply="❌ No active DeepSeek session found for work_dir. Run 'ccb deepseek' (or add deepseek to ccb.config) in that project first.",
                req_id=task.req_id,
                session_key=self.session_key,
                done_seen=False,
                done_ms=None,
            )

        ok, pane_or_err = session.ensure_pane()
        if not ok:
            return DskaskdResult(
                exit_code=1,
                reply=f"❌ Session pane not available: {pane_or_err}",
                req_id=task.req_id,
                session_key=self.session_key,
                done_seen=False,
                done_ms=None,
            )
        pane_id = pane_or_err

        backend = get_backend_for_session(session.data)
        if not backend:
            return DskaskdResult(
                exit_code=1,
                reply="❌ Terminal backend not available",
                req_id=task.req_id,
                session_key=self.session_key,
                done_seen=False,
                done_ms=None,
            )

        try:
            ccb_pid = str(session.data.get("ccb_project_id") or "").strip()
            if not ccb_pid:
                ccb_pid = compute_ccb_project_id(Path(session.work_dir))
            ccb_session_id = str(session.data.get("ccb_session_id") or session.data.get("session_id") or "").strip()
            if ccb_session_id:
                upsert_registry(
                    {
                        "ccb_session_id": ccb_session_id,
                        "ccb_project_id": ccb_pid or None,
                        "work_dir": str(session.work_dir),
                        "terminal": session.terminal,
                        "providers": {
                            "deepseek": {
                                "pane_id": session.pane_id or None,
                                "pane_title_marker": session.pane_title_marker or None,
                                "session_file": str(session.session_file),
                            }
                        },
                    }
                )
        except Exception:
            pass

        prompt = wrap_deepseek_prompt(req.message, task.req_id)
        try:
            activate_fn = getattr(backend, "activate", None)
            if callable(activate_fn):
                activate_fn(pane_id)
                time.sleep(0.2)
        except Exception:
            pass
        ready_wait_s = _cli_ready_wait_s("CCB_DSKASKD_READY_WAIT_S", 12.0)
        if ready_wait_s > 0:
            time.sleep(ready_wait_s)
        backend.send_text(pane_id, prompt)

        deadline = None if float(req.timeout_s) < 0.0 else (time.time() + float(req.timeout_s))
        done_seen = False
        done_ms: int | None = None
        latest_text = ""

        poll_s = _env_float("CCB_DSKASKD_POLL_INTERVAL", 0.3, min_v=0.05, max_v=2.0)
        quiet_s = _env_float("CCB_DSKASKD_QUIET_S", 2.0, min_v=0.2, max_v=5.0)
        capture_lines = _env_int("CCB_DSKASKD_CAPTURE_LINES", 4000, min_v=200, max_v=20000)
        pane_check_interval = _env_float("CCB_DSKASKD_PANE_CHECK_INTERVAL", 2.0, min_v=0.5, max_v=10.0)
        last_pane_check = time.time()
        last_text = ""
        last_change = time.time()
        fallback_reply = ""
        saw_output_after_prompt = False

        while True:
            if deadline is not None and time.time() >= deadline:
                break

            if time.time() - last_pane_check >= pane_check_interval:
                try:
                    alive = bool(backend.is_alive(pane_id))
                except Exception:
                    alive = False
                if not alive:
                    _write_log(f"[ERROR] Pane {pane_id} died during request session={self.session_key} req_id={task.req_id}")
                    return DskaskdResult(
                        exit_code=1,
                        reply="❌ DeepSeek pane died during request",
                        req_id=task.req_id,
                        session_key=self.session_key,
                        done_seen=False,
                        done_ms=None,
                    )
                last_pane_check = time.time()

            text = _capture_pane_text(backend, pane_id, capture_lines)
            if text:
                sanitized = _sanitize_text(text)
                if sanitized != last_text:
                    last_text = sanitized
                    last_change = time.time()
                latest_text = sanitized
                if is_done_text(sanitized, task.req_id):
                    done_seen = True
                    done_ms = _now_ms() - started_ms
                    break
                fallback_reply = _extract_reply_fallback(sanitized, task.req_id)
                if fallback_reply.strip():
                    saw_output_after_prompt = True
                if saw_output_after_prompt and (time.time() - last_change) >= quiet_s:
                    break

            time.sleep(poll_s)

        if latest_text:
            reply = extract_reply_for_req(latest_text, task.req_id) if done_seen else _extract_reply_fallback(latest_text, task.req_id)
        else:
            reply = ""
        exit_code = 0 if reply or done_seen else 2
        try:
            _write_log(
                json.dumps(
                    {
                        "type": "reply",
                        "provider": "deepseek",
                        "req_id": task.req_id,
                        "session_key": self.session_key,
                        "work_dir": str(work_dir),
                        "message": req.message,
                        "reply": reply,
                        "exit_code": exit_code,
                        "done_seen": done_seen,
                        "done_ms": done_ms,
                        "ts": time.time(),
                    },
                    ensure_ascii=False,
                )
            )
        except Exception:
            pass
        return DskaskdResult(
            exit_code=exit_code,
            reply=reply,
            req_id=task.req_id,
            session_key=self.session_key,
            done_seen=done_seen,
            done_ms=done_ms,
        )


class _WorkerPool:
    def __init__(self):
        self._pool = PerSessionWorkerPool[_SessionWorker]()

    def submit(self, request: DskaskdRequest) -> _QueuedTask:
        req_id = make_req_id()
        task = _QueuedTask(request=request, created_ms=_now_ms(), req_id=req_id, done_event=threading.Event())

        session = load_project_session(Path(request.work_dir))
        session_key = compute_session_key(session) if session else "deepseek:unknown"

        worker = self._pool.get_or_create(session_key, _SessionWorker)
        worker.enqueue(task)
        return task


class DskaskdServer:
    def __init__(self, host: str = "127.0.0.1", port: int = 0, *, state_file: Optional[Path] = None):
        self.host = host
        self.port = port
        self.state_file = state_file or state_file_path(DSKASKD_SPEC.state_file_name)
        self.token = random_token()
        self.pool = _WorkerPool()

    def serve_forever(self) -> int:
        def _handle_request(msg: dict) -> dict:
            try:
                req = DskaskdRequest(
                    client_id=str(msg.get("id") or ""),
                    work_dir=str(msg.get("work_dir") or ""),
                    timeout_s=float(msg.get("timeout_s") or 300.0),
                    quiet=bool(msg.get("quiet") or False),
                    message=str(msg.get("message") or ""),
                    output_path=str(msg.get("output_path")) if msg.get("output_path") else None,
                )
            except Exception as exc:
                return {"type": "dskask.response", "v": 1, "id": msg.get("id"), "exit_code": 1, "reply": f"Bad request: {exc}"}

            task = self.pool.submit(req)
            wait_timeout = None if float(req.timeout_s) < 0.0 else (float(req.timeout_s) + 5.0)
            task.done_event.wait(timeout=wait_timeout)
            result = task.result
            if not result:
                return {"type": "dskask.response", "v": 1, "id": req.client_id, "exit_code": 2, "reply": ""}

            return {
                "type": "dskask.response",
                "v": 1,
                "id": req.client_id,
                "req_id": result.req_id,
                "exit_code": result.exit_code,
                "reply": result.reply,
                "meta": {
                    "session_key": result.session_key,
                    "done_seen": result.done_seen,
                    "done_ms": result.done_ms,
                },
            }

        server = AskDaemonServer(
            spec=DSKASKD_SPEC,
            host=self.host,
            port=self.port,
            token=self.token,
            state_file=self.state_file,
            request_handler=_handle_request,
            request_queue_size=128,
            on_stop=self._cleanup_state_file,
        )
        return server.serve_forever()

    def _cleanup_state_file(self) -> None:
        try:
            st = read_state(self.state_file)
        except Exception:
            st = None
        try:
            if isinstance(st, dict) and int(st.get("pid") or 0) == os.getpid():
                self.state_file.unlink(missing_ok=True)
        except TypeError:
            try:
                if isinstance(st, dict) and int(st.get("pid") or 0) == os.getpid() and self.state_file.exists():
                    self.state_file.unlink()
            except Exception:
                pass
        except Exception:
            pass


def read_state(state_file: Optional[Path] = None) -> Optional[dict]:
    state_file = state_file or state_file_path(DSKASKD_SPEC.state_file_name)
    return askd_rpc.read_state(state_file)


def ping_daemon(timeout_s: float = 0.5, state_file: Optional[Path] = None) -> bool:
    state_file = state_file or state_file_path(DSKASKD_SPEC.state_file_name)
    return askd_rpc.ping_daemon("dskask", timeout_s, state_file)


def shutdown_daemon(timeout_s: float = 1.0, state_file: Optional[Path] = None) -> bool:
    state_file = state_file or state_file_path(DSKASKD_SPEC.state_file_name)
    return askd_rpc.shutdown_daemon("dskask", timeout_s, state_file)
