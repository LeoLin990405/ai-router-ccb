#!/usr/bin/env python3
"""
Context Saver - System 1: Instant Context Archiving

Automatically saves session context to DATABASE when /clear or /compact
is executed. This is the "fast, automatic" part of the dual-system memory.

v2.0: 改为保存到数据库，不再使用 Markdown 文件
"""

import json
import os
import re
import sqlite3
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from memory.jsonl_parser import ClaudeJsonlParser, SessionData, Message, ToolCall

try:
    from lib.common.logging import get_logger
except ImportError:  # pragma: no cover - script mode
    try:
        from common.logging import get_logger  # type: ignore
    except ImportError:  # pragma: no cover - fallback
        import logging

        def get_logger(name: str):
            return logging.getLogger(name)


logger = get_logger("memory.context_saver")


def _emit(message: str = "", err: bool = False) -> None:
    stream = sys.stderr if err else sys.stdout
    stream.write(f"{message}\n")



from .context_saver_core import ContextSaverCoreMixin
from .context_saver_markdown import ContextSaverMarkdownMixin


class ContextSaver(ContextSaverCoreMixin, ContextSaverMarkdownMixin):
    """System 1 context saver backed by SQLite."""

    DB_PATH = Path.home() / ".ccb" / "ccb_memory.db"


def find_current_session() -> Optional[Path]:
    """Find the most recent Claude session file for the current directory."""
    claude_dir = Path.home() / ".claude" / "projects"

    if not claude_dir.exists():
        return None

    # Get all session files
    sessions = list(claude_dir.glob("**/*.jsonl"))

    if not sessions:
        return None

    # Find most recently modified
    sessions.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return sessions[0]


def main():
    """CLI entry point for context saver."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Save Claude session context to Markdown archive"
    )
    parser.add_argument(
        "--session",
        type=Path,
        help="Path to session.jsonl file (default: auto-detect)"
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="Output directory (default: ~/.ccb/context_archive)"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Save even trivial sessions"
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress output"
    )

    args = parser.parse_args()

    # Determine session path
    session_path = args.session
    if not session_path:
        # Try to get from environment (set by hook)
        env_path = os.environ.get('CLAUDE_SESSION_PATH')
        if env_path:
            session_path = Path(env_path)
        else:
            session_path = find_current_session()

    if not session_path:
        if not args.quiet:
            _emit("No session file found", err=True)
        sys.exit(1)

    # Create saver and save
    saver = ContextSaver(archive_dir=args.output_dir)
    result = saver.save_session(session_path, force=args.force)

    if result:
        if not args.quiet:
            _emit(f"✓ Saved context to: {result}")
        sys.exit(0)
    else:
        if not args.quiet:
            _emit("Session too short, skipped saving", err=True)
        sys.exit(0)  # Not an error, just skipped


if __name__ == "__main__":
    main()
