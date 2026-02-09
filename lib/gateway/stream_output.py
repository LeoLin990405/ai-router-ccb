"""
Stream Output Manager for CCB Gateway.

Provides real-time output streaming for async tasks.
Each request gets a dedicated log file that can be tailed for live output.
Supports dual-write to both file and SQLite database for persistence.
"""
from __future__ import annotations

import asyncio
import os
import time
import json
import sqlite3
from pathlib import Path
from typing import Optional, Dict, Any, Callable, List
from dataclasses import dataclass, field
from datetime import datetime

from lib.common.logging import get_logger

# Default stream directory
STREAM_DIR = Path(os.path.expanduser("~/.ccb/streams"))

# Default database path
DB_PATH = Path(os.path.expanduser("~/.ccb/ccb_memory.db"))


logger = get_logger("gateway.stream_output")


@dataclass
class StreamEntry:
    """A single entry in the stream log."""
    timestamp: float
    type: str  # 'status', 'thinking', 'output', 'chunk', 'error', 'complete'
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> str:
        return json.dumps({
            "ts": self.timestamp,
            "time": datetime.fromtimestamp(self.timestamp).strftime("%H:%M:%S.%f")[:-3],
            "type": self.type,
            "content": self.content,
            "meta": self.metadata,
        }, ensure_ascii=False)


class StreamOutput:
    """
    Manages streaming output for a single request.

    Writes to a log file that can be tailed for real-time updates.
    Also syncs entries to SQLite database for persistence.
    """

    def __init__(self, request_id: str, provider: str, stream_dir: Optional[Path] = None,
                 db_path: Optional[Path] = None, buffer_size: int = 10):
        self.request_id = request_id
        self.provider = provider
        self.stream_dir = stream_dir or STREAM_DIR
        self.stream_dir.mkdir(parents=True, exist_ok=True)

        # Log file path: ~/.ccb/streams/{request_id}.jsonl
        self.log_path = self.stream_dir / f"{request_id}.jsonl"
        self.started_at = time.time()
        self._closed = False

        # Database sync configuration
        self._db_path = db_path or DB_PATH
        self._entries_buffer: List[StreamEntry] = []
        self._buffer_size = buffer_size
        self._db_enabled = self._db_path.exists()

        # Write initial entry
        self._write_entry(StreamEntry(
            timestamp=time.time(),
            type="start",
            content=f"Request started for provider: {provider}",
            metadata={"provider": provider, "request_id": request_id}
        ))

    def _write_entry(self, entry: StreamEntry) -> None:
        """Write an entry to the log file and buffer for DB sync."""
        if self._closed:
            return
        try:
            # 1. Write to JSONL file (original behavior)
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(entry.to_json() + "\n")
                f.flush()

            # 2. Buffer for database sync
            if self._db_enabled:
                self._entries_buffer.append(entry)
                if len(self._entries_buffer) >= self._buffer_size:
                    self._flush_to_db()
        except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError) as e:
            logger.error("Error writing to %s: %s", self.log_path, e)

    def _flush_to_db(self) -> None:
        """Batch write buffered entries to database."""
        if not self._entries_buffer or not self._db_enabled:
            return
        try:
            conn = sqlite3.connect(str(self._db_path), timeout=5.0)
            cursor = conn.cursor()
            cursor.executemany(
                """INSERT INTO stream_entries
                   (request_id, entry_type, timestamp, content, metadata)
                   VALUES (?, ?, ?, ?, ?)""",
                [(self.request_id, e.type, e.timestamp, e.content,
                  json.dumps(e.metadata, ensure_ascii=False)) for e in self._entries_buffer]
            )
            conn.commit()
            conn.close()
            self._entries_buffer = []
        except sqlite3.OperationalError as e:
            # Table might not exist yet, disable DB sync
            if "no such table" in str(e):
                logger.warning("stream_entries table not found, disabling DB sync")
                self._db_enabled = False
            else:
                logger.error("DB sync error: %s", e)
        except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError) as e:
            logger.error("DB sync error: %s", e)

    def status(self, message: str, **meta) -> None:
        """Write a status update."""
        self._write_entry(StreamEntry(
            timestamp=time.time(),
            type="status",
            content=message,
            metadata=meta
        ))

    def thinking(self, content: str, **meta) -> None:
        """Write thinking/reasoning chain content."""
        self._write_entry(StreamEntry(
            timestamp=time.time(),
            type="thinking",
            content=content,
            metadata=meta
        ))

    def chunk(self, content: str, **meta) -> None:
        """Write a streaming chunk of output."""
        self._write_entry(StreamEntry(
            timestamp=time.time(),
            type="chunk",
            content=content,
            metadata=meta
        ))

    def output(self, content: str, **meta) -> None:
        """Write output content."""
        self._write_entry(StreamEntry(
            timestamp=time.time(),
            type="output",
            content=content,
            metadata=meta
        ))

    def error(self, message: str, **meta) -> None:
        """Write an error message."""
        self._write_entry(StreamEntry(
            timestamp=time.time(),
            type="error",
            content=message,
            metadata=meta
        ))

    def complete(self, response: Optional[str] = None, error: Optional[str] = None, **meta) -> None:
        """Mark the stream as complete."""
        elapsed = time.time() - self.started_at
        self._write_entry(StreamEntry(
            timestamp=time.time(),
            type="complete",
            content=response or error or "Completed",
            metadata={
                "success": error is None,
                "elapsed_s": round(elapsed, 2),
                "response_length": len(response) if response else 0,
                "error": error,
                **meta
            }
        ))
        # Force flush remaining entries to DB on completion
        self._flush_to_db()
        self._closed = True

    def close(self) -> None:
        """Close the stream without completion marker."""
        # Flush any remaining entries before closing
        self._flush_to_db()
        self._closed = True


class StreamOutputManager:
    """
    Manages all active stream outputs.

    Provides methods to:
    - Create new streams for requests
    - Get stream status
    - Clean up old streams
    """

    def __init__(self, stream_dir: Optional[Path] = None, retention_hours: int = 24):
        self.stream_dir = stream_dir or STREAM_DIR
        self.stream_dir.mkdir(parents=True, exist_ok=True)
        self.retention_hours = retention_hours
        self._streams: Dict[str, StreamOutput] = {}

    def create_stream(self, request_id: str, provider: str) -> StreamOutput:
        """Create a new stream for a request."""
        stream = StreamOutput(request_id, provider, self.stream_dir)
        self._streams[request_id] = stream
        return stream

    def get_stream(self, request_id: str) -> Optional[StreamOutput]:
        """Get an existing stream by request ID."""
        return self._streams.get(request_id)

    def get_stream_path(self, request_id: str) -> Path:
        """Get the log file path for a request."""
        return self.stream_dir / f"{request_id}.jsonl"

    def stream_exists(self, request_id: str) -> bool:
        """Check if a stream log file exists."""
        return self.get_stream_path(request_id).exists()

    def read_stream(self, request_id: str, from_line: int = 0) -> list:
        """Read stream entries from a log file."""
        path = self.get_stream_path(request_id)
        if not path.exists():
            return []

        entries = []
        try:
            with open(path, "r", encoding="utf-8") as f:
                for i, line in enumerate(f):
                    if i < from_line:
                        continue
                    try:
                        entries.append(json.loads(line.strip()))
                    except json.JSONDecodeError:
                        continue
        except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError) as e:
            logger.error("Error reading %s: %s", path, e)

        return entries

    def get_stream_status(self, request_id: str) -> Dict[str, Any]:
        """Get status of a stream."""
        path = self.get_stream_path(request_id)
        if not path.exists():
            return {"exists": False}

        entries = self.read_stream(request_id)
        if not entries:
            return {"exists": True, "entries": 0}

        last_entry = entries[-1]
        return {
            "exists": True,
            "entries": len(entries),
            "completed": last_entry.get("type") == "complete",
            "success": last_entry.get("meta", {}).get("success") if last_entry.get("type") == "complete" else None,
            "last_type": last_entry.get("type"),
            "last_time": last_entry.get("time"),
        }

    def cleanup_old_streams(self) -> int:
        """Clean up streams older than retention period."""
        cutoff = time.time() - (self.retention_hours * 3600)
        removed = 0

        for path in self.stream_dir.glob("*.jsonl"):
            try:
                if path.stat().st_mtime < cutoff:
                    path.unlink()
                    removed += 1
            except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError):
                continue

        return removed

    def list_recent_streams(self, limit: int = 20) -> list:
        """List recent streams sorted by modification time."""
        streams = []
        for path in self.stream_dir.glob("*.jsonl"):
            try:
                stat = path.stat()
                request_id = path.stem
                streams.append({
                    "request_id": request_id,
                    "path": str(path),
                    "size": stat.st_size,
                    "mtime": stat.st_mtime,
                    "status": self.get_stream_status(request_id),
                })
            except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError):
                continue

        streams.sort(key=lambda x: x["mtime"], reverse=True)
        return streams[:limit]


# Global instance
_manager: Optional[StreamOutputManager] = None


def get_stream_manager() -> StreamOutputManager:
    """Get the global stream manager instance."""
    global _manager
    if _manager is None:
        _manager = StreamOutputManager()
    return _manager
