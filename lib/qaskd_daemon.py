from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from worker_pool import BaseSessionWorker, PerSessionWorkerPool

from qaskd_protocol import (
    QaskdRequest,
    QaskdResult,
    extract_reply_for_req,
    wrap_qwen_prompt,
)
from qaskd_session import compute_session_key, load_project_session
from qwen_comm import QwenLogReader
from pane_registry import upsert_registry
from project_id import compute_ccb_project_id
from terminal import get_backend_for_session
from askd_runtime import state_file_path, log_path, write_log, random_token
import askd_rpc
from askd_server import AskDaemonServer
from providers import QASKD_SPEC
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
    write_log(log_path(QASKD_SPEC.log_file_name), line)


@dataclass
class _QueuedTask:
    request: QaskdRequest
    created_ms: int
    req_id: str
    done_event: threading.Event
    result: Optional[QaskdResult] = None


class _SessionWorker(BaseSessionWorker[_QueuedTask, QaskdResult]):
    def _handle_exception(self, exc: Exception, task: _QueuedTask) -> QaskdResult:
        _write_log(f"[ERROR] session={self.session_key} req_id={task.req_id} {exc}")
        return QaskdResult(
            exit_code=1,
            reply=str(exc),
            req_id=task.req_id,
            session_key=self.session_key,
            done_seen=False,
            done_ms=None,
        )

    def _handle_task(self, task: _QueuedTask) -> QaskdResult:
        started_ms = _now_ms()
        req = task.request
        work_dir = Path(req.work_dir)
        _write_log(f"[INFO] start session={self.session_key} req_id={task.req_id} work_dir={req.work_dir}")

        session = load_project_session(work_dir)
        if not session:
            return QaskdResult(
                exit_code=1,
                reply="❌ No active Qwen session found for work_dir. Run 'ccb qwen' (or add qwen to ccb.config) in that project first.",
                req_id=task.req_id,
                session_key=self.session_key,
                done_seen=False,
                done_ms=None,
            )

        ok, pane_or_err = session.ensure_pane()
        if not ok:
            return QaskdResult(
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
            return QaskdResult(
                exit_code=1,
                reply="❌ Terminal backend not available",
                req_id=task.req_id,
                session_key=self.session_key,
                done_seen=False,
                done_ms=None,
            )

        log_reader = QwenLogReader(work_dir=Path(session.work_dir))
        if session.qwen_session_path:
            try:
                log_reader.set_preferred_session(Path(session.qwen_session_path))
            except Exception:
                pass
        if session.qwen_session_id:
            log_reader.set_session_id_hint(session.qwen_session_id)
        state = log_reader.capture_state()

        try:
            session_path = state.get("session_path")
            session_id = session_path.stem if isinstance(session_path, Path) else ""
            session.update_qwen_binding(session_path=session_path if isinstance(session_path, Path) else None, session_id=session_id or None)
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
                            "qwen": {
                                "pane_id": session.pane_id or None,
                                "pane_title_marker": session.pane_title_marker or None,
                                "session_file": str(session.session_file),
                                "qwen_session_id": session.data.get("qwen_session_id"),
                                "qwen_session_path": session.data.get("qwen_session_path"),
                            }
                        },
                    }
                )
        except Exception:
            pass

        prompt = wrap_qwen_prompt(req.message, task.req_id)
        # Qwen TUI requires pane activation before sending text for proper Enter key handling
        try:
            activate_fn = getattr(backend, "activate", None)
            if callable(activate_fn):
                activate_fn(pane_id)
                time.sleep(0.3)  # Longer delay for TUI to be ready
        except Exception:
            pass
        ready_wait_s = _cli_ready_wait_s("CCB_QASKD_READY_WAIT_S", 12.0)
        if ready_wait_s > 0:
            time.sleep(ready_wait_s)
        backend.send_text(pane_id, prompt)
        # Qwen TUI sometimes needs explicit activation + Enter after send_text
        try:
            import subprocess
            time.sleep(0.3)
            subprocess.run(["wezterm", "cli", "activate-pane", "--pane-id", pane_id], capture_output=True, timeout=2)
            time.sleep(0.2)
            subprocess.run(["wezterm", "cli", "send-text", "--pane-id", pane_id, "--no-paste"], input=b"\r", capture_output=True, timeout=2)
        except Exception:
            pass

        deadline = None if float(req.timeout_s) < 0.0 else (time.time() + float(req.timeout_s))
        done_seen = False
        done_ms: int | None = None
        latest_reply = ""

        pane_check_interval = float(os.environ.get("CCB_QASKD_PANE_CHECK_INTERVAL", "2.0") or "2.0")
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
                    return QaskdResult(
                        exit_code=1,
                        reply="❌ Qwen pane died during request",
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
        return QaskdResult(
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

    def submit(self, request: QaskdRequest) -> _QueuedTask:
        req_id = make_req_id()
        task = _QueuedTask(request=request, created_ms=_now_ms(), req_id=req_id, done_event=threading.Event())

        session = load_project_session(Path(request.work_dir))
        session_key = compute_session_key(session) if session else "qwen:unknown"

        worker = self._pool.get_or_create(session_key, _SessionWorker)
        worker.enqueue(task)
        return task


class QaskdServer:
    def __init__(self, host: str = "127.0.0.1", port: int = 0, *, state_file: Optional[Path] = None):
        self.host = host
        self.port = port
        self.state_file = state_file or state_file_path(QASKD_SPEC.state_file_name)
        self.token = random_token()
        self.pool = _WorkerPool()

    def serve_forever(self) -> int:
        def _handle_request(msg: dict) -> dict:
            try:
                req = QaskdRequest(
                    client_id=str(msg.get("id") or ""),
                    work_dir=str(msg.get("work_dir") or ""),
                    timeout_s=float(msg.get("timeout_s") or 300.0),
                    quiet=bool(msg.get("quiet") or False),
                    message=str(msg.get("message") or ""),
                    output_path=str(msg.get("output_path")) if msg.get("output_path") else None,
                )
            except Exception as exc:
                return {"type": "qask.response", "v": 1, "id": msg.get("id"), "exit_code": 1, "reply": f"Bad request: {exc}"}

            task = self.pool.submit(req)
            wait_timeout = None if float(req.timeout_s) < 0.0 else (float(req.timeout_s) + 5.0)
            task.done_event.wait(timeout=wait_timeout)
            result = task.result
            if not result:
                return {"type": "qask.response", "v": 1, "id": req.client_id, "exit_code": 2, "reply": ""}

            return {
                "type": "qask.response",
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
            spec=QASKD_SPEC,
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
    state_file = state_file or state_file_path(QASKD_SPEC.state_file_name)
    return askd_rpc.read_state(state_file)


def ping_daemon(timeout_s: float = 0.5, state_file: Optional[Path] = None) -> bool:
    state_file = state_file or state_file_path(QASKD_SPEC.state_file_name)
    return askd_rpc.ping_daemon("qask", timeout_s, state_file)


def shutdown_daemon(timeout_s: float = 1.0, state_file: Optional[Path] = None) -> bool:
    state_file = state_file or state_file_path(QASKD_SPEC.state_file_name)
    return askd_rpc.shutdown_daemon("qask", timeout_s, state_file)
