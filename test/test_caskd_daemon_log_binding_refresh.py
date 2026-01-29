from __future__ import annotations

import json
import os
import time
from pathlib import Path

import caskd_daemon
import caskd_session


def _write_jsonl_session_meta(path: Path, *, cwd: Path, session_id: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    entry = {"type": "session_meta", "payload": {"cwd": str(cwd), "id": session_id}}
    path.write_text(json.dumps(entry) + "\n", encoding="utf-8")


def test_refresh_codex_log_binding_prefers_start_cmd_session_id(tmp_path: Path) -> None:
    sessions_root = tmp_path / "sessions"
    new_id = "019bbf3e-0000-0000-0000-000000000000"
    old_id = "019bb1a1-0000-0000-0000-000000000000"

    old_log = sessions_root / f"codex-{old_id}.jsonl"
    new_log = sessions_root / f"codex-{new_id}.jsonl"
    _write_jsonl_session_meta(old_log, cwd=tmp_path, session_id=old_id)
    _write_jsonl_session_meta(new_log, cwd=tmp_path, session_id=new_id)

    # Ensure new_log is newer.
    now = time.time()
    os.utime(old_log, (now - 100, now - 100))
    os.utime(new_log, (now, now))

    session_file = tmp_path / ".codex-session"
    session_file.write_text(
        json.dumps(
            {
                "session_id": "ccb-session",
                "terminal": "tmux",
                "pane_id": "%1",
                "pane_title_marker": "CCB-codex-test",
                "runtime_dir": str(tmp_path),
                "work_dir": str(tmp_path),
                "active": True,
                "start_cmd": f"codex resume {new_id}",
                "codex_session_id": old_id,
                "codex_session_path": str(old_log),
            }
        ),
        encoding="utf-8",
    )

    sess = caskd_session.load_project_session(tmp_path)
    assert sess is not None

    updated = caskd_daemon._refresh_codex_log_binding(
        sess, session_root=sessions_root, scan_limit=400, force_scan=False
    )
    assert updated is True

    data = json.loads(session_file.read_text(encoding="utf-8"))
    assert data["codex_session_id"] == new_id
    assert Path(data["codex_session_path"]) == new_log


def test_refresh_codex_log_binding_fallback_scan_by_work_dir(tmp_path: Path) -> None:
    sessions_root = tmp_path / "sessions"
    sid = "019bbf3e-1111-2222-3333-444444444444"

    subdir = tmp_path / "subdir"
    subdir.mkdir()
    log_path = sessions_root / "nested" / f"codex-{sid}.jsonl"
    _write_jsonl_session_meta(log_path, cwd=subdir, session_id=sid)
    os.utime(log_path, None)

    session_file = tmp_path / ".codex-session"
    session_file.write_text(
        json.dumps(
            {
                "session_id": "ccb-session",
                "terminal": "tmux",
                "pane_id": "%1",
                "pane_title_marker": "CCB-codex-test",
                "runtime_dir": str(tmp_path),
                "work_dir": str(tmp_path),
                "active": True,
                "start_cmd": "codex",
            }
        ),
        encoding="utf-8",
    )

    sess = caskd_session.load_project_session(tmp_path)
    assert sess is not None

    updated = caskd_daemon._refresh_codex_log_binding(
        sess, session_root=sessions_root, scan_limit=50, force_scan=True
    )
    assert updated is True

    data = json.loads(session_file.read_text(encoding="utf-8"))
    assert data["codex_session_id"] == sid
    assert Path(data["codex_session_path"]) == log_path

