from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from worker_pool import BaseSessionWorker, PerSessionWorkerPool

from kaskd_protocol import (
    KaskdRequest,
    KaskdResult,
    extract_reply_for_req,
    wrap_kimi_prompt,
)
from kaskd_session import compute_session_key, load_project_session
from kimi_comm import KimiLogReader
from pane_registry import upsert_registry
from project_id import compute_ccb_project_id
from terminal import get_backend_for_session
from askd_runtime import state_file_path, log_path, write_log, random_token
import askd_rpc
from askd_server import AskDaemonServer
from providers import KASKD_SPEC
from ccb_protocol import is_done_text, make_req_id


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
    write_log(log_path(KASKD_SPEC.log_file_name), line)


def _capture_pane_text(backend, pane_id: str, lines: int = 200) -> str:
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


def _wait_for_kimi_ready(backend, pane_id: str, timeout_s: float) -> bool:
    """
    Best-effort wait for Kimi CLI to finish startup so we don't send the prompt too early.
    """
    deadline = time.time() + max(0.1, float(timeout_s))
    ready_markers = (
        "Welcome to Kimi Code CLI",
        "Send /help",
        "Session:",
        "Directory:",
    )
    while time.time() < deadline:
        text = _capture_pane_text(backend, pane_id, lines=200)
        if text:
            if any(m in text for m in ready_markers):
                return True
            # prompt often ends with a sparkle
            for line in text.splitlines()[-5:]:
                if line.strip().endswith("💫"):
                    return True
        time.sleep(0.2)
    return False


@dataclass
class _QueuedTask:
    request: KaskdRequest
    created_ms: int
    req_id: str
    done_event: threading.Event
    result: Optional[KaskdResult] = None


class _SessionWorker(BaseSessionWorker[_QueuedTask, KaskdResult]):
    def _handle_exception(self, exc: Exception, task: _QueuedTask) -> KaskdResult:
        _write_log(f"[ERROR] session={self.session_key} req_id={task.req_id} {exc}")
        return KaskdResult(
            exit_code=1,
            reply=str(exc),
            req_id=task.req_id,
            session_key=self.session_key,
            done_seen=False,
            done_ms=None,
        )

    def _handle_task(self, task: _QueuedTask) -> KaskdResult:
        started_ms = _now_ms()
        req = task.request
        work_dir = Path(req.work_dir)
        _write_log(f"[INFO] start session={self.session_key} req_id={task.req_id} work_dir={req.work_dir}")

        session = load_project_session(work_dir)
        if not session:
            return KaskdResult(
                exit_code=1,
                reply="❌ No active Kimi session found for work_dir. Run 'ccb kimi' (or add kimi to ccb.config) in that project first.",
                req_id=task.req_id,
                session_key=self.session_key,
                done_seen=False,
                done_ms=None,
            )

        ok, pane_or_err = session.ensure_pane()
        if not ok:
            return KaskdResult(
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
            return KaskdResult(
                exit_code=1,
                reply="❌ Terminal backend not available",
                req_id=task.req_id,
                session_key=self.session_key,
                done_seen=False,
                done_ms=None,
            )

        log_reader = KimiLogReader(work_dir=Path(session.work_dir))
        if session.kimi_session_path:
            try:
                log_reader.set_preferred_session(Path(session.kimi_session_path))
            except Exception:
                pass
        if session.kimi_session_id:
            log_reader.set_session_id_hint(session.kimi_session_id)
        state = log_reader.capture_state()

        try:
            session_path = state.get("session_path")
            session_id = session_path.parent.name if isinstance(session_path, Path) else ""
            session.update_kimi_binding(session_path=session_path if isinstance(session_path, Path) else None, session_id=session_id or None)
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
                            "kimi": {
                                "pane_id": session.pane_id or None,
                                "pane_title_marker": session.pane_title_marker or None,
                                "session_file": str(session.session_file),
                                "kimi_session_id": session.data.get("kimi_session_id"),
                                "kimi_session_path": session.data.get("kimi_session_path"),
                            }
                        },
                    }
                )
        except Exception:
            pass

        prompt = wrap_kimi_prompt(req.message, task.req_id)
        # Kimi TUI may require pane activation before sending text
        ready_timeout = _cli_ready_wait_s("CCB_KASKD_READY_TIMEOUT_S", 12.0)
        _wait_for_kimi_ready(backend, pane_id, ready_timeout)
        try:
            activate_fn = getattr(backend, "activate", None)
            if callable(activate_fn):
                activate_fn(pane_id)
                time.sleep(0.1)
        except Exception:
            pass
        backend.send_text(pane_id, prompt)

        deadline = None if float(req.timeout_s) < 0.0 else (time.time() + float(req.timeout_s))
        done_seen = False
        done_ms: int | None = None
        latest_reply = ""

        pane_check_interval = float(os.environ.get("CCB_KASKD_PANE_CHECK_INTERVAL", "2.0") or "2.0")
        last_pane_check = time.time()

        while True:
            if deadline is not None:
                remaining = deadline - time.time()
                if remaining <= 0:
                    break
                wait_step = min(remaining, 1.0)
            else:
                wait_step = 1.0

            if time.time() - last_pane_check >= pane_check_interval:
                try:
                    alive = bool(backend.is_alive(pane_id))
                except Exception:
                    alive = False
                if not alive:
                    _write_log(f"[ERROR] Pane {pane_id} died during request session={self.session_key} req_id={task.req_id}")
                    return KaskdResult(
                        exit_code=1,
                        reply="❌ Kimi pane died during request",
                        req_id=task.req_id,
                        session_key=self.session_key,
                        done_seen=False,
                        done_ms=None,
                    )
                last_pane_check = time.time()

            reply, state = log_reader.wait_for_message(state, wait_step)
            if not reply:
                continue
            latest_reply = str(reply)
            if is_done_text(latest_reply, task.req_id):
                done_seen = True
                done_ms = _now_ms() - started_ms
                break

        final_reply = extract_reply_for_req(latest_reply, task.req_id)
        return KaskdResult(
            exit_code=0 if done_seen else 2,
            reply=final_reply,
            req_id=task.req_id,
            session_key=self.session_key,
            done_seen=done_seen,
            done_ms=done_ms,
        )


class _WorkerPool:
    def __init__(self):
        self._pool = PerSessionWorkerPool[_SessionWorker]()

    def submit(self, request: KaskdRequest) -> _QueuedTask:
        req_id = make_req_id()
        task = _QueuedTask(request=request, created_ms=_now_ms(), req_id=req_id, done_event=threading.Event())

        session = load_project_session(Path(request.work_dir))
        session_key = compute_session_key(session) if session else "kimi:unknown"

        worker = self._pool.get_or_create(session_key, _SessionWorker)
        worker.enqueue(task)
        return task


class KaskdServer:
    def __init__(self, host: str = "127.0.0.1", port: int = 0, *, state_file: Optional[Path] = None):
        self.host = host
        self.port = port
        self.state_file = state_file or state_file_path(KASKD_SPEC.state_file_name)
        self.token = random_token()
        self.pool = _WorkerPool()

    def serve_forever(self) -> int:
        def _handle_request(msg: dict) -> dict:
            try:
                req = KaskdRequest(
                    client_id=str(msg.get("id") or ""),
                    work_dir=str(msg.get("work_dir") or ""),
                    timeout_s=float(msg.get("timeout_s") or 300.0),
                    quiet=bool(msg.get("quiet") or False),
                    message=str(msg.get("message") or ""),
                    output_path=str(msg.get("output_path")) if msg.get("output_path") else None,
                )
            except Exception as exc:
                return {"type": "kask.response", "v": 1, "id": msg.get("id"), "exit_code": 1, "reply": f"Bad request: {exc}"}

            task = self.pool.submit(req)
            wait_timeout = None if float(req.timeout_s) < 0.0 else (float(req.timeout_s) + 5.0)
            task.done_event.wait(timeout=wait_timeout)
            result = task.result
            if not result:
                return {"type": "kask.response", "v": 1, "id": req.client_id, "exit_code": 2, "reply": ""}

            return {
                "type": "kask.response",
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
            spec=KASKD_SPEC,
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
    state_file = state_file or state_file_path(KASKD_SPEC.state_file_name)
    return askd_rpc.read_state(state_file)


def ping_daemon(timeout_s: float = 0.5, state_file: Optional[Path] = None) -> bool:
    state_file = state_file or state_file_path(KASKD_SPEC.state_file_name)
    return askd_rpc.ping_daemon("kask", timeout_s, state_file)


def shutdown_daemon(timeout_s: float = 1.0, state_file: Optional[Path] = None) -> bool:
    state_file = state_file or state_file_path(KASKD_SPEC.state_file_name)
    return askd_rpc.shutdown_daemon("kask", timeout_s, state_file)
