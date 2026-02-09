"""Shared Knowledge database operations mixin."""
from __future__ import annotations

import json
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

try:
    from lib.common.logging import get_logger
    from lib.common.paths import default_gateway_db_path
except ImportError:  # pragma: no cover - script mode fallback
    from common.logging import get_logger  # type: ignore
    from common.paths import default_gateway_db_path  # type: ignore

logger = get_logger("knowledge.shared")
SCHEMA_FILE = Path(__file__).parent / "schema_shared.sql"


class SharedKnowledgeDBMixin:
    """Database layer for shared knowledge."""

    def _init_shared_db(self, db_path: Optional[str] = None) -> None:
        if db_path:
            self._db_path = Path(db_path)
        else:
            self._db_path = Path(default_gateway_db_path())
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    @contextmanager
    def _get_conn(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(str(self._db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        try:
            yield conn
            conn.commit()
        except (sqlite3.DatabaseError, OSError, RuntimeError, ValueError, TypeError):
            conn.rollback()
            raise
        finally:
            conn.close()

    def _ensure_schema(self) -> None:
        schema_sql = SCHEMA_FILE.read_text(encoding="utf-8")
        with self._get_conn() as conn:
            conn.executescript(schema_sql)

    def register_agent(
        self,
        agent_id: str,
        name: str,
        provider: Optional[str] = None,
        role: str = "general",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        now = time.time()
        with self._get_conn() as conn:
            conn.execute(
                """
                INSERT INTO agents (agent_id, name, provider, role, last_active, metadata)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(agent_id) DO UPDATE SET
                  name = excluded.name,
                  provider = COALESCE(excluded.provider, agents.provider),
                  role = COALESCE(excluded.role, agents.role),
                  last_active = excluded.last_active,
                  metadata = COALESCE(excluded.metadata, agents.metadata)
                """,
                (agent_id, name, provider, role, now, json.dumps(metadata or {})),
            )
        return {"agent_id": agent_id, "name": name, "provider": provider, "role": role}

    def get_agent(self, agent_id: str) -> Optional[Dict[str, Any]]:
        with self._get_conn() as conn:
            row = conn.execute("SELECT * FROM agents WHERE agent_id = ?", (agent_id,)).fetchone()

        if not row:
            return None

        result = dict(row)
        raw_metadata = result.get("metadata")
        if isinstance(raw_metadata, str) and raw_metadata:
            try:
                result["metadata"] = json.loads(raw_metadata)
            except (json.JSONDecodeError, TypeError):
                result["metadata"] = {}
        return result

    def publish(
        self,
        agent_id: str,
        category: str,
        title: str,
        content: str,
        tags: Optional[List[str]] = None,
        source_request_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> int:
        """Publish a knowledge entry and return new entry ID."""
        self.register_agent(agent_id=agent_id, name=agent_id)

        now = time.time()
        with self._get_conn() as conn:
            cursor = conn.execute(
                """
                INSERT INTO shared_knowledge
                    (agent_id, category, title, content, tags, source_request_id, metadata, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    agent_id,
                    category,
                    title,
                    content,
                    json.dumps(tags or []),
                    source_request_id,
                    json.dumps(metadata or {}),
                    now,
                ),
            )
            entry_id = cursor.lastrowid

        return int(entry_id)

    def get_entry(self, entry_id: int) -> Optional[Dict[str, Any]]:
        with self._get_conn() as conn:
            row = conn.execute("SELECT * FROM shared_knowledge WHERE id = ?", (entry_id,)).fetchone()

        if not row:
            return None

        return self._row_to_dict(row)

    def delete_entry(self, entry_id: int) -> bool:
        with self._get_conn() as conn:
            cursor = conn.execute("DELETE FROM shared_knowledge WHERE id = ?", (entry_id,))
        return cursor.rowcount > 0

    def search_fts(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Full-text search in shared knowledge with FTS5 trigram."""
        with self._get_conn() as conn:
            rows = conn.execute(
                """
                SELECT sk.*, bm25(shared_knowledge_fts) AS rank
                FROM shared_knowledge_fts
                JOIN shared_knowledge sk ON sk.id = shared_knowledge_fts.rowid
                WHERE shared_knowledge_fts MATCH ?
                ORDER BY rank
                LIMIT ?
                """,
                (query, limit),
            ).fetchall()

        return [self._row_to_dict(row) for row in rows]

    def list_entries(
        self,
        category: Optional[str] = None,
        agent_id: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        conditions: List[str] = []
        params: List[Any] = []

        if category:
            conditions.append("category = ?")
            params.append(category)
        if agent_id:
            conditions.append("agent_id = ?")
            params.append(agent_id)

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        params.extend([limit, offset])

        with self._get_conn() as conn:
            rows = conn.execute(
                f"""
                SELECT * FROM shared_knowledge {where}
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
                """,
                params,
            ).fetchall()

        return [self._row_to_dict(row) for row in rows]

    def vote(
        self,
        knowledge_id: int,
        agent_id: str,
        vote: str,
        comment: Optional[str] = None,
    ) -> Dict[str, Any]:
        self.register_agent(agent_id=agent_id, name=agent_id)

        with self._get_conn() as conn:
            conn.execute(
                """
                INSERT INTO knowledge_votes (knowledge_id, agent_id, vote, comment)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(knowledge_id, agent_id, vote) DO UPDATE SET
                    comment = excluded.comment,
                    created_at = strftime('%s', 'now')
                """,
                (knowledge_id, agent_id, vote, comment),
            )
            self._update_confidence(conn, knowledge_id)

        return {"knowledge_id": knowledge_id, "agent_id": agent_id, "vote": vote}

    def _update_confidence(self, conn: sqlite3.Connection, knowledge_id: int) -> None:
        row = conn.execute(
            """
            SELECT
                SUM(CASE WHEN vote='agree' THEN 1 ELSE 0 END) AS agrees,
                SUM(CASE WHEN vote='disagree' THEN 1 ELSE 0 END) AS disagrees,
                SUM(CASE WHEN vote='cite' THEN 1 ELSE 0 END) AS cites
            FROM knowledge_votes
            WHERE knowledge_id = ?
            """,
            (knowledge_id,),
        ).fetchone()

        agrees = row[0] if row and row[0] else 0
        disagrees = row[1] if row and row[1] else 0
        cites = row[2] if row and row[2] else 0

        created_row = conn.execute(
            "SELECT created_at FROM shared_knowledge WHERE id = ?",
            (knowledge_id,),
        ).fetchone()
        if not created_row:
            return

        created_at = float(created_row[0])
        age_days = max(0.0, (time.time() - created_at) / 86400.0)

        vote_factor = agrees * 0.1 - disagrees * 0.2
        cite_factor = min(cites * 0.05, 0.3)
        decay_factor = max(-0.5, -(age_days // 30) * 0.05)

        confidence = max(0.0, min(1.0, 0.5 + vote_factor + cite_factor + decay_factor))
        conn.execute(
            "UPDATE shared_knowledge SET confidence = ?, updated_at = ? WHERE id = ?",
            (confidence, time.time(), knowledge_id),
        )

    def log_access(
        self,
        knowledge_id: int,
        agent_id: Optional[str] = None,
        query: Optional[str] = None,
        relevance: Optional[float] = None,
    ) -> None:
        with self._get_conn() as conn:
            conn.execute(
                """
                INSERT INTO knowledge_access_log (knowledge_id, agent_id, query, relevance_score)
                VALUES (?, ?, ?, ?)
                """,
                (knowledge_id, agent_id, query, relevance),
            )
            conn.execute(
                "UPDATE shared_knowledge SET access_count = access_count + 1 WHERE id = ?",
                (knowledge_id,),
            )

    def get_shared_stats(self) -> Dict[str, Any]:
        with self._get_conn() as conn:
            total_entries = conn.execute("SELECT COUNT(*) FROM shared_knowledge").fetchone()[0]
            total_agents = conn.execute("SELECT COUNT(*) FROM agents").fetchone()[0]
            total_votes = conn.execute("SELECT COUNT(*) FROM knowledge_votes").fetchone()[0]
            rows = conn.execute(
                """
                SELECT category, COUNT(*) AS cnt
                FROM shared_knowledge
                GROUP BY category
                ORDER BY cnt DESC
                """,
            ).fetchall()

        return {
            "total_entries": total_entries,
            "total_agents": total_agents,
            "total_votes": total_votes,
            "by_category": {str(row[0]): int(row[1]) for row in rows},
        }

    @staticmethod
    def _row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
        data = dict(row)

        for key in ("tags", "metadata"):
            raw = data.get(key)
            if isinstance(raw, str) and raw:
                try:
                    data[key] = json.loads(raw)
                except (json.JSONDecodeError, TypeError):
                    data[key] = [] if key == "tags" else {}
            elif raw is None:
                data[key] = [] if key == "tags" else {}

        return data
