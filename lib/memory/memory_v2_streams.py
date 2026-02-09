"""Auto-split mixins for Memory v2."""
from __future__ import annotations

import gzip
import json
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from .memory_v2_shared import MEMORY_V2_ERRORS, logger


class MemoryV2StreamMixin:
    """Mixin methods extracted from CCBMemoryV2."""

    def archive_session(self, session_id: str):
        """Archive old session to compressed storage

        Args:
            session_id: Session to archive
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Get session and messages
        cursor.execute("""
            SELECT s.*, COUNT(m.message_id) as message_count, SUM(m.tokens) as total_tokens
            FROM sessions s
            LEFT JOIN messages m ON s.session_id = m.session_id
            WHERE s.session_id = ?
            GROUP BY s.session_id
        """, (session_id,))

        session_data = cursor.fetchone()
        if not session_data:
            conn.close()
            return

        # Get all messages
        cursor.execute("""
            SELECT * FROM messages WHERE session_id = ?
            ORDER BY sequence
        """, (session_id,))

        messages = cursor.fetchall()

        # Compress and archive
        archive_data = {
            "session": session_data,
            "messages": messages
        }

        compressed = gzip.compress(json.dumps(archive_data).encode())

        cursor.execute("""
            INSERT INTO archived_sessions (
                session_id, user_id, created_at, archived_at,
                message_count, total_tokens, compressed_data
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            session_id,
            session_data[1],  # user_id
            session_data[2],  # created_at
            datetime.now().isoformat(),
            session_data[-2],  # message_count
            session_data[-1],  # total_tokens
            compressed
        ))

        # Delete from active tables
        cursor.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
        cursor.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))

        conn.commit()
        conn.close()

    # ========================================================================
    # Stream Entries (Phase 8: Stream Sync)
    # ========================================================================

    def get_stream_entries(
        self,
        request_id: str,
        entry_type: Optional[str] = None,
        limit: int = 1000
    ) -> List[Dict[str, Any]]:
        """Get stream entries for a request

        Args:
            request_id: Gateway request ID
            entry_type: Optional filter by entry type
            limit: Maximum entries to return

        Returns:
            List of stream entry dictionaries
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            if entry_type:
                cursor.execute("""
                    SELECT id, request_id, entry_type, timestamp, content, metadata, created_at
                    FROM stream_entries
                    WHERE request_id = ? AND entry_type = ?
                    ORDER BY timestamp ASC
                    LIMIT ?
                """, (request_id, entry_type, limit))
            else:
                cursor.execute("""
                    SELECT id, request_id, entry_type, timestamp, content, metadata, created_at
                    FROM stream_entries
                    WHERE request_id = ?
                    ORDER BY timestamp ASC
                    LIMIT ?
                """, (request_id, limit))

            columns = [desc[0] for desc in cursor.description]
            results = []
            for row in cursor.fetchall():
                result = dict(zip(columns, row))
                # Parse JSON metadata
                if result.get('metadata'):
                    try:
                        result['metadata'] = json.loads(result['metadata'])
                    except json.JSONDecodeError:
                        pass
                results.append(result)

            return results
        finally:
            conn.close()

    def get_thinking_chain(self, request_id: str) -> Optional[str]:
        """Get concatenated thinking chain content for a request

        Args:
            request_id: Gateway request ID

        Returns:
            Combined thinking content or None
        """
        entries = self.get_stream_entries(request_id, entry_type="thinking")
        if not entries:
            return None

        thinking_parts = [e.get('content', '') for e in entries if e.get('content')]
        return "\n\n".join(thinking_parts) if thinking_parts else None

    def search_thinking(
        self,
        query: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Search thinking chain content across all requests

        Args:
            query: Search query (substring match)
            limit: Maximum results

        Returns:
            List of matching entries with request context
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            # Use LIKE for simple substring search
            cursor.execute("""
                SELECT request_id, content, timestamp, metadata
                FROM stream_entries
                WHERE entry_type = 'thinking'
                  AND content LIKE ?
                ORDER BY timestamp DESC
                LIMIT ?
            """, (f"%{query}%", limit))

            columns = [desc[0] for desc in cursor.description]
            results = []
            for row in cursor.fetchall():
                result = dict(zip(columns, row))
                if result.get('metadata'):
                    try:
                        result['metadata'] = json.loads(result['metadata'])
                    except json.JSONDecodeError:
                        pass
                results.append(result)

            return results
        finally:
            conn.close()

    def get_request_timeline(self, request_id: str) -> List[Dict[str, Any]]:
        """Get complete execution timeline for a request

        Args:
            request_id: Gateway request ID

        Returns:
            List of timeline entries with human-readable timestamps
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            cursor.execute("""
                SELECT
                    entry_type,
                    content,
                    timestamp,
                    datetime(timestamp, 'unixepoch', 'localtime') as time_str,
                    metadata
                FROM stream_entries
                WHERE request_id = ?
                ORDER BY timestamp ASC
            """, (request_id,))

            columns = [desc[0] for desc in cursor.description]
            results = []
            for row in cursor.fetchall():
                result = dict(zip(columns, row))
                if result.get('metadata'):
                    try:
                        result['metadata'] = json.loads(result['metadata'])
                    except json.JSONDecodeError:
                        pass
                results.append(result)

            return results
        finally:
            conn.close()

    def get_stream_stats(self) -> Dict[str, Any]:
        """Get statistics about stream entries

        Returns:
            Statistics dictionary
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            # Total entries
            cursor.execute("SELECT COUNT(*) FROM stream_entries")
            total_entries = cursor.fetchone()[0]

            # Unique requests
            cursor.execute("SELECT COUNT(DISTINCT request_id) FROM stream_entries")
            unique_requests = cursor.fetchone()[0]

            # Entries by type
            cursor.execute("""
                SELECT entry_type, COUNT(*) as count
                FROM stream_entries
                GROUP BY entry_type
                ORDER BY count DESC
            """)
            entries_by_type = {row[0]: row[1] for row in cursor.fetchall()}

            # Recent activity (last 24 hours)
            cursor.execute("""
                SELECT COUNT(DISTINCT request_id)
                FROM stream_entries
                WHERE timestamp > ?
            """, (datetime.now().timestamp() - 86400,))
            recent_requests = cursor.fetchone()[0]

            return {
                "total_entries": total_entries,
                "unique_requests": unique_requests,
                "entries_by_type": entries_by_type,
                "recent_requests_24h": recent_requests
            }
        except sqlite3.OperationalError:
            # Table might not exist
            return {
                "total_entries": 0,
                "unique_requests": 0,
                "entries_by_type": {},
                "recent_requests_24h": 0,
                "error": "stream_entries table not found"
            }
        finally:
            conn.close()

    def sync_stream_file(self, request_id: str) -> int:
        """Sync a stream file to database

        Args:
            request_id: Request ID to sync

        Returns:
            Number of entries synced
        """
        stream_file = Path.home() / ".ccb" / "streams" / f"{request_id}.jsonl"
        if not stream_file.exists():
            return 0

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            # Check if already synced
            cursor.execute(
                "SELECT COUNT(*) FROM stream_entries WHERE request_id = ?",
                (request_id,)
            )
            existing = cursor.fetchone()[0]
            if existing > 0:
                return 0  # Already synced

            # Read and parse JSONL file
            entries = []
            with open(stream_file, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        entry = json.loads(line.strip())
                        entries.append((
                            request_id,
                            entry.get("type", "unknown"),
                            entry.get("ts", 0),
                            entry.get("content", ""),
                            json.dumps(entry.get("meta", {}), ensure_ascii=False)
                        ))
                    except json.JSONDecodeError:
                        continue

            if not entries:
                return 0

            # Batch insert
            cursor.executemany(
                """INSERT INTO stream_entries
                   (request_id, entry_type, timestamp, content, metadata)
                   VALUES (?, ?, ?, ?, ?)""",
                entries
            )
            conn.commit()
            return len(entries)
        except sqlite3.OperationalError as e:
            logger.warning("sync_stream_file error: %s", e)
            return 0
        finally:
            conn.close()

    def sync_all_streams(self, force: bool = False) -> Dict[str, int]:
        """Sync all stream files to database

        Args:
            force: If True, re-sync even if already in database

        Returns:
            Dict with sync statistics
        """
        stream_dir = Path.home() / ".ccb" / "streams"
        if not stream_dir.exists():
            return {"synced": 0, "skipped": 0, "errors": 0}

        stats = {"synced": 0, "skipped": 0, "errors": 0, "total_entries": 0}

        for stream_file in stream_dir.glob("*.jsonl"):
            request_id = stream_file.stem
            try:
                if force:
                    # Delete existing entries for force sync
                    conn = sqlite3.connect(self.db_path)
                    conn.execute(
                        "DELETE FROM stream_entries WHERE request_id = ?",
                        (request_id,)
                    )
                    conn.commit()
                    conn.close()

                count = self.sync_stream_file(request_id)
                if count > 0:
                    stats["synced"] += 1
                    stats["total_entries"] += count
                else:
                    stats["skipped"] += 1
            except MEMORY_V2_ERRORS as e:
                logger.warning("Error syncing %s: %s", request_id, e)
                stats["errors"] += 1

        return stats


    # ========================================================================
    # Heuristic Retrieval Support (v2.0)
    # ========================================================================

