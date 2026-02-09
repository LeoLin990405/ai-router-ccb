# Hivemind v1.1 Implementation Guide

**For: Codex (o3)**
**Date: 2026-02-10**
**Scope: Shared Knowledge Layer + Skill/MCP Unified Router**
**Estimated New Code: ~1,500 lines across ~15 files**

---

## 0. Context & Constraints

### 0.1 What v1.0 Already Provides

| Component | Location | Key Class/Function |
|-----------|----------|-------------------|
| Memory V2 | `lib/memory/memory_v2.py` | `CCBMemoryV2` (6 mixins) |
| Heuristic Retriever | `lib/memory/heuristic_retriever.py` | `HeuristicRetriever` — αR+βI+γT scoring |
| Knowledge API | `lib/gateway/knowledge_api.py` | NotebookLM + Obsidian routes |
| Skills Discovery | `lib/skills/skills_discovery.py` | `SkillsDiscoveryService` (4 mixins) |
| Smart Router | `lib/gateway/router.py` | `SmartRouter` with keyword rules |
| State Store | `lib/gateway/state_store.py` | SQLite WAL, 8 tables |
| App Factory | `lib/gateway/app.py` | `create_app()` registers all routes |
| Memory Middleware | `lib/gateway/middleware/memory_middleware_core.py` | pre_request/post_response hooks |

### 0.2 Current Database Layout (3 isolated SQLite files)

```
~/.ccb_config/ccb_memory.db     ← Memory V2 (13 tables + 2 FTS5)
~/.ccb_config/knowledge_index.db ← Knowledge (notebooks, query_cache)
~/.ccb_config/gateway.db        ← Gateway (requests, responses, metrics, discussions, costs)
```

### 0.3 Architecture Rules (MUST follow)

1. **Mixin pattern** — new functionality goes into `*Mixin` classes, composed into service class
2. **Route files ≤ 500 lines** — split if larger
3. **Source files ≤ 500 lines** — split into `*_core.py` / `*_shared.py` if needed
4. **SQLite WAL mode** — all DB connections use `PRAGMA journal_mode=WAL`
5. **Imports** — use `from lib.xxx import ...` (relative), with `try/except` fallback to `from xxx import ...` for script mode
6. **Logging** — use `from lib.common.logging import get_logger`, never `print()`
7. **Exceptions** — use specific exception types from `lib.common.errors`, never bare `except Exception`
8. **FTS5** — use `trigram` tokenizer for Chinese text support
9. **Tests** — add tests to `tests/` directory, use existing `conftest.py` pattern
10. **App registration** — new routers must be added to `lib/gateway/app.py` via `_include_router_if_available()`

---

## 1. Module A: Shared Knowledge Layer

### 1.1 Goal

Enable cross-agent knowledge sharing. Any agent can **publish** knowledge (findings, code patterns, solutions), and any agent can **query** across all knowledge sources (Memory V2 + NotebookLM + Obsidian + shared pool) in one unified call.

### 1.2 New Files to Create

| File | Lines | Purpose |
|------|-------|---------|
| `lib/knowledge/shared_knowledge.py` | ~120 | `SharedKnowledgeService` main class |
| `lib/knowledge/shared_knowledge_db.py` | ~200 | Database mixin (schema + CRUD) |
| `lib/knowledge/shared_knowledge_query.py` | ~180 | Unified query mixin |
| `lib/knowledge/schema_shared.sql` | ~60 | SQL schema file |
| `lib/gateway/routes/shared_knowledge.py` | ~200 | FastAPI routes (7 endpoints) |
| `tests/test_shared_knowledge.py` | ~150 | Unit tests |

### 1.3 Files to Modify

| File | Change |
|------|--------|
| `lib/gateway/app.py` | Add `shared_knowledge` routes import + registration |
| `lib/gateway/middleware/memory_middleware_core.py` | Add auto-publish hook in `post_response()` |

### 1.4 SQL Schema

Create file `lib/knowledge/schema_shared.sql`:

```sql
-- Shared Knowledge Layer v1.1
-- Database: ~/.ccb_config/gateway.db (extend existing)

CREATE TABLE IF NOT EXISTS agents (
    agent_id    TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    provider    TEXT,
    role        TEXT DEFAULT 'general',
    created_at  REAL DEFAULT (strftime('%s', 'now')),
    last_active REAL,
    metadata    TEXT DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS shared_knowledge (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_id    TEXT NOT NULL,
    category    TEXT NOT NULL CHECK(category IN (
        'code_pattern', 'solution', 'architecture',
        'debugging', 'api_usage', 'best_practice',
        'config', 'learning', 'other'
    )),
    title       TEXT NOT NULL,
    content     TEXT NOT NULL,
    tags        TEXT DEFAULT '[]',           -- JSON array
    source_request_id TEXT,                  -- link to gateway request
    confidence  REAL DEFAULT 0.5,
    created_at  REAL DEFAULT (strftime('%s', 'now')),
    updated_at  REAL DEFAULT (strftime('%s', 'now')),
    access_count INTEGER DEFAULT 0,
    metadata    TEXT DEFAULT '{}',
    FOREIGN KEY (agent_id) REFERENCES agents(agent_id)
);

CREATE VIRTUAL TABLE IF NOT EXISTS shared_knowledge_fts
USING fts5(title, content, tags, tokenize='trigram');

-- Keep FTS in sync
CREATE TRIGGER IF NOT EXISTS shared_knowledge_ai
AFTER INSERT ON shared_knowledge BEGIN
    INSERT INTO shared_knowledge_fts(rowid, title, content, tags)
    VALUES (new.id, new.title, new.content, new.tags);
END;

CREATE TRIGGER IF NOT EXISTS shared_knowledge_ad
AFTER DELETE ON shared_knowledge BEGIN
    DELETE FROM shared_knowledge_fts WHERE rowid = old.id;
END;

CREATE TRIGGER IF NOT EXISTS shared_knowledge_au
AFTER UPDATE OF title, content, tags ON shared_knowledge BEGIN
    DELETE FROM shared_knowledge_fts WHERE rowid = old.id;
    INSERT INTO shared_knowledge_fts(rowid, title, content, tags)
    VALUES (new.id, new.title, new.content, new.tags);
END;

CREATE TABLE IF NOT EXISTS knowledge_votes (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    knowledge_id INTEGER NOT NULL,
    agent_id    TEXT NOT NULL,
    vote        TEXT NOT NULL CHECK(vote IN ('agree', 'disagree', 'cite')),
    comment     TEXT,
    created_at  REAL DEFAULT (strftime('%s', 'now')),
    FOREIGN KEY (knowledge_id) REFERENCES shared_knowledge(id) ON DELETE CASCADE,
    UNIQUE(knowledge_id, agent_id, vote)
);

CREATE TABLE IF NOT EXISTS knowledge_access_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    knowledge_id INTEGER NOT NULL,
    agent_id    TEXT,
    query       TEXT,
    relevance_score REAL,
    accessed_at REAL DEFAULT (strftime('%s', 'now')),
    FOREIGN KEY (knowledge_id) REFERENCES shared_knowledge(id) ON DELETE CASCADE
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_sk_agent ON shared_knowledge(agent_id);
CREATE INDEX IF NOT EXISTS idx_sk_category ON shared_knowledge(category);
CREATE INDEX IF NOT EXISTS idx_sk_created ON shared_knowledge(created_at);
CREATE INDEX IF NOT EXISTS idx_sk_confidence ON shared_knowledge(confidence DESC);
CREATE INDEX IF NOT EXISTS idx_kv_knowledge ON knowledge_votes(knowledge_id);
CREATE INDEX IF NOT EXISTS idx_kal_knowledge ON knowledge_access_log(knowledge_id);
CREATE INDEX IF NOT EXISTS idx_kal_accessed ON knowledge_access_log(accessed_at);
```

### 1.5 SharedKnowledgeService Implementation

#### File: `lib/knowledge/shared_knowledge_db.py`

```python
"""Shared Knowledge database operations mixin."""
from __future__ import annotations

import json
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from lib.common.logging import get_logger
    from lib.common.paths import default_gateway_db_path
except ImportError:
    from common.logging import get_logger
    from common.paths import default_gateway_db_path

logger = get_logger("knowledge.shared")

SCHEMA_FILE = Path(__file__).parent / "schema_shared.sql"


class SharedKnowledgeDBMixin:
    """Database layer for shared knowledge."""

    def _init_shared_db(self, db_path: Optional[str] = None) -> None:
        self._db_path = db_path or default_gateway_db_path()
        self._ensure_schema()

    @contextmanager
    def _get_conn(self):
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _ensure_schema(self) -> None:
        schema_sql = SCHEMA_FILE.read_text(encoding="utf-8")
        with self._get_conn() as conn:
            conn.executescript(schema_sql)

    # --- Agent CRUD ---

    def register_agent(self, agent_id: str, name: str,
                       provider: Optional[str] = None,
                       role: str = "general") -> Dict:
        with self._get_conn() as conn:
            conn.execute(
                """INSERT INTO agents (agent_id, name, provider, role)
                   VALUES (?, ?, ?, ?)
                   ON CONFLICT(agent_id) DO UPDATE SET
                     last_active = strftime('%s', 'now'),
                     provider = COALESCE(excluded.provider, agents.provider)""",
                (agent_id, name, provider, role),
            )
        return {"agent_id": agent_id, "name": name}

    def get_agent(self, agent_id: str) -> Optional[Dict]:
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM agents WHERE agent_id = ?", (agent_id,)
            ).fetchone()
        return dict(row) if row else None

    # --- Knowledge CRUD ---

    def publish(self, agent_id: str, category: str, title: str,
                content: str, tags: Optional[List[str]] = None,
                source_request_id: Optional[str] = None,
                metadata: Optional[Dict] = None) -> int:
        """Publish a knowledge entry. Returns the new entry ID."""
        self.register_agent(agent_id, agent_id)  # auto-register
        with self._get_conn() as conn:
            cursor = conn.execute(
                """INSERT INTO shared_knowledge
                   (agent_id, category, title, content, tags,
                    source_request_id, metadata)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (agent_id, category, title, content,
                 json.dumps(tags or []),
                 source_request_id,
                 json.dumps(metadata or {})),
            )
        return cursor.lastrowid

    def get_entry(self, entry_id: int) -> Optional[Dict]:
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM shared_knowledge WHERE id = ?", (entry_id,)
            ).fetchone()
        if not row:
            return None
        result = dict(row)
        result["tags"] = json.loads(result.get("tags", "[]"))
        result["metadata"] = json.loads(result.get("metadata", "{}"))
        return result

    def delete_entry(self, entry_id: int) -> bool:
        with self._get_conn() as conn:
            cursor = conn.execute(
                "DELETE FROM shared_knowledge WHERE id = ?", (entry_id,)
            )
        return cursor.rowcount > 0

    def search_fts(self, query: str, limit: int = 10) -> List[Dict]:
        """Full-text search in shared knowledge using FTS5."""
        with self._get_conn() as conn:
            rows = conn.execute(
                """SELECT sk.*, rank
                   FROM shared_knowledge_fts fts
                   JOIN shared_knowledge sk ON sk.id = fts.rowid
                   WHERE shared_knowledge_fts MATCH ?
                   ORDER BY rank
                   LIMIT ?""",
                (query, limit),
            ).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def list_entries(self, category: Optional[str] = None,
                     agent_id: Optional[str] = None,
                     limit: int = 20, offset: int = 0) -> List[Dict]:
        conditions, params = [], []
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
                f"""SELECT * FROM shared_knowledge {where}
                    ORDER BY created_at DESC LIMIT ? OFFSET ?""",
                params,
            ).fetchall()
        return [self._row_to_dict(r) for r in rows]

    # --- Votes ---

    def vote(self, knowledge_id: int, agent_id: str, vote: str,
             comment: Optional[str] = None) -> Dict:
        """Cast a vote (agree/disagree/cite). Updates confidence."""
        self.register_agent(agent_id, agent_id)
        with self._get_conn() as conn:
            conn.execute(
                """INSERT INTO knowledge_votes
                   (knowledge_id, agent_id, vote, comment)
                   VALUES (?, ?, ?, ?)
                   ON CONFLICT(knowledge_id, agent_id, vote) DO UPDATE SET
                     comment = excluded.comment,
                     created_at = strftime('%s', 'now')""",
                (knowledge_id, agent_id, vote, comment),
            )
            # Recalculate confidence
            self._update_confidence(conn, knowledge_id)
        return {"knowledge_id": knowledge_id, "vote": vote}

    def _update_confidence(self, conn: sqlite3.Connection, knowledge_id: int) -> None:
        """Recalculate confidence score based on votes and usage.

        Formula:
          vote_factor  = agree * 0.1 - disagree * 0.2
          cite_factor  = min(cite_count * 0.05, 0.3)
          age_days     = (now - created_at) / 86400
          decay_factor = max(-0.5, -(age_days // 30) * 0.05)
          confidence   = clamp(0.5 + vote_factor + cite_factor + decay_factor, 0, 1)
        """
        row = conn.execute(
            """SELECT
                 SUM(CASE WHEN vote='agree' THEN 1 ELSE 0 END) as agrees,
                 SUM(CASE WHEN vote='disagree' THEN 1 ELSE 0 END) as disagrees,
                 SUM(CASE WHEN vote='cite' THEN 1 ELSE 0 END) as cites
               FROM knowledge_votes WHERE knowledge_id = ?""",
            (knowledge_id,),
        ).fetchone()
        agrees = row[0] or 0
        disagrees = row[1] or 0
        cites = row[2] or 0

        created_row = conn.execute(
            "SELECT created_at FROM shared_knowledge WHERE id = ?",
            (knowledge_id,),
        ).fetchone()
        if not created_row:
            return

        age_days = (time.time() - created_row[0]) / 86400
        vote_factor = agrees * 0.1 - disagrees * 0.2
        cite_factor = min(cites * 0.05, 0.3)
        decay_factor = max(-0.5, -(age_days // 30) * 0.05)
        confidence = max(0.0, min(1.0, 0.5 + vote_factor + cite_factor + decay_factor))

        conn.execute(
            "UPDATE shared_knowledge SET confidence = ?, updated_at = ? WHERE id = ?",
            (confidence, time.time(), knowledge_id),
        )

    # --- Access log ---

    def log_access(self, knowledge_id: int, agent_id: Optional[str] = None,
                   query: Optional[str] = None, relevance: Optional[float] = None) -> None:
        with self._get_conn() as conn:
            conn.execute(
                """INSERT INTO knowledge_access_log
                   (knowledge_id, agent_id, query, relevance_score)
                   VALUES (?, ?, ?, ?)""",
                (knowledge_id, agent_id, query, relevance),
            )
            conn.execute(
                "UPDATE shared_knowledge SET access_count = access_count + 1 WHERE id = ?",
                (knowledge_id,),
            )

    # --- Stats ---

    def get_shared_stats(self) -> Dict:
        with self._get_conn() as conn:
            total = conn.execute("SELECT COUNT(*) FROM shared_knowledge").fetchone()[0]
            agents_count = conn.execute("SELECT COUNT(*) FROM agents").fetchone()[0]
            votes_count = conn.execute("SELECT COUNT(*) FROM knowledge_votes").fetchone()[0]
            categories = conn.execute(
                """SELECT category, COUNT(*) as cnt
                   FROM shared_knowledge GROUP BY category
                   ORDER BY cnt DESC"""
            ).fetchall()
        return {
            "total_entries": total,
            "total_agents": agents_count,
            "total_votes": votes_count,
            "by_category": {r[0]: r[1] for r in categories},
        }

    @staticmethod
    def _row_to_dict(row) -> Dict:
        d = dict(row)
        for key in ("tags", "metadata"):
            if key in d and isinstance(d[key], str):
                try:
                    d[key] = json.loads(d[key])
                except (json.JSONDecodeError, TypeError):
                    pass
        return d
```

#### File: `lib/knowledge/shared_knowledge_query.py`

```python
"""Unified cross-source knowledge query mixin."""
from __future__ import annotations

import asyncio
import time
from typing import Any, Dict, List, Optional

try:
    from lib.common.logging import get_logger
except ImportError:
    from common.logging import get_logger

logger = get_logger("knowledge.query")


class SharedKnowledgeQueryMixin:
    """Unified query across Memory V2, NotebookLM, Obsidian, Shared Knowledge."""

    async def unified_query(
        self,
        query: str,
        sources: Optional[List[str]] = None,
        limit: int = 10,
        agent_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Query all knowledge sources in parallel, merge and rank results.

        Args:
            query: Search query string.
            sources: Which sources to query. Default: all.
                     Options: "memory", "notebooklm", "obsidian", "shared"
            limit: Max results per source.
            agent_id: Requesting agent (for access logging).

        Returns:
            {
                "query": str,
                "results": [{"source": str, "title": str, "content": str,
                             "relevance": float, "metadata": dict}],
                "sources_queried": [str],
                "total_results": int,
                "query_time_ms": float
            }
        """
        all_sources = sources or ["memory", "shared", "notebooklm", "obsidian"]
        start = time.time()

        tasks = {}
        if "memory" in all_sources:
            tasks["memory"] = self._query_memory(query, limit)
        if "shared" in all_sources:
            tasks["shared"] = self._query_shared(query, limit, agent_id)
        if "notebooklm" in all_sources:
            tasks["notebooklm"] = self._query_notebooklm(query, limit)
        if "obsidian" in all_sources:
            tasks["obsidian"] = self._query_obsidian(query, limit)

        results_by_source = {}
        gathered = await asyncio.gather(
            *tasks.values(), return_exceptions=True,
        )
        for source_name, result in zip(tasks.keys(), gathered):
            if isinstance(result, Exception):
                logger.warning("Query failed for source %s: %s", source_name, result)
                results_by_source[source_name] = []
            else:
                results_by_source[source_name] = result

        # Merge and sort by relevance
        merged = []
        for source_name, items in results_by_source.items():
            for item in items:
                item["source"] = source_name
                merged.append(item)

        merged.sort(key=lambda x: x.get("relevance", 0), reverse=True)
        merged = merged[:limit * 2]  # keep top results across all sources

        return {
            "query": query,
            "results": merged,
            "sources_queried": list(results_by_source.keys()),
            "total_results": len(merged),
            "query_time_ms": (time.time() - start) * 1000,
        }

    async def _query_memory(self, query: str, limit: int) -> List[Dict]:
        """Search Memory V2 via heuristic retriever."""
        try:
            if not hasattr(self, "_memory") or self._memory is None:
                return []
            results = self._memory.search_conversations(query, limit=limit)
            return [
                {
                    "title": r.get("question", "")[:80],
                    "content": r.get("answer", r.get("content", "")),
                    "relevance": r.get("score", r.get("relevance_score", 0.5)),
                    "metadata": {
                        "provider": r.get("provider"),
                        "timestamp": r.get("timestamp"),
                    },
                }
                for r in (results if isinstance(results, list) else [])
            ]
        except (RuntimeError, ValueError, TypeError, OSError) as exc:
            logger.debug("Memory query error: %s", exc)
            return []

    async def _query_shared(self, query: str, limit: int,
                            agent_id: Optional[str] = None) -> List[Dict]:
        """Search shared knowledge pool via FTS5."""
        try:
            results = self.search_fts(query, limit=limit)  # from DBMixin
            for r in results:
                if agent_id:
                    self.log_access(r["id"], agent_id, query, r.get("rank"))
            return [
                {
                    "title": r.get("title", ""),
                    "content": r.get("content", ""),
                    "relevance": self._fts_to_relevance(r.get("rank", 0)),
                    "metadata": {
                        "category": r.get("category"),
                        "confidence": r.get("confidence"),
                        "agent_id": r.get("agent_id"),
                        "entry_id": r.get("id"),
                    },
                }
                for r in results
            ]
        except (RuntimeError, ValueError, TypeError, OSError) as exc:
            logger.debug("Shared knowledge query error: %s", exc)
            return []

    async def _query_notebooklm(self, query: str, limit: int) -> List[Dict]:
        """Search NotebookLM via knowledge API client."""
        try:
            if not hasattr(self, "_knowledge_client") or self._knowledge_client is None:
                return []
            result = await self._knowledge_client.query(query)
            if not result or not result.get("answer"):
                return []
            return [{
                "title": f"NotebookLM: {query[:60]}",
                "content": result["answer"],
                "relevance": 0.8,  # NotebookLM results are generally relevant
                "metadata": {
                    "notebook_id": result.get("notebook_id"),
                    "sources": result.get("sources", []),
                },
            }]
        except (RuntimeError, ValueError, TypeError, OSError) as exc:
            logger.debug("NotebookLM query error: %s", exc)
            return []

    async def _query_obsidian(self, query: str, limit: int) -> List[Dict]:
        """Search Obsidian vault."""
        try:
            if not hasattr(self, "_obsidian_search") or self._obsidian_search is None:
                return []
            results = self._obsidian_search.search(query, limit=limit)
            return [
                {
                    "title": r.get("title", r.get("file", "")),
                    "content": r.get("content", r.get("excerpt", "")),
                    "relevance": r.get("score", 0.5),
                    "metadata": {"file": r.get("file"), "vault": r.get("vault")},
                }
                for r in (results if isinstance(results, list) else [])
            ]
        except (RuntimeError, ValueError, TypeError, OSError) as exc:
            logger.debug("Obsidian query error: %s", exc)
            return []

    @staticmethod
    def _fts_to_relevance(rank: float) -> float:
        """Convert FTS5 rank to 0-1 relevance. BM25 normalization."""
        return max(0.0, min(1.0, (25 + rank) / 25))
```

#### File: `lib/knowledge/shared_knowledge.py`

```python
"""Shared Knowledge Service — main composition class."""
from __future__ import annotations

from typing import Optional

from .shared_knowledge_db import SharedKnowledgeDBMixin
from .shared_knowledge_query import SharedKnowledgeQueryMixin


class SharedKnowledgeService(SharedKnowledgeDBMixin, SharedKnowledgeQueryMixin):
    """Cross-agent shared knowledge with unified query."""

    def __init__(
        self,
        db_path: Optional[str] = None,
        memory=None,
        knowledge_client=None,
        obsidian_search=None,
    ):
        self._init_shared_db(db_path)
        self._memory = memory
        self._knowledge_client = knowledge_client
        self._obsidian_search = obsidian_search
```

Ensure `lib/knowledge/__init__.py` exists (may already exist from v1.0):

```python
"""Knowledge subsystem."""
```

### 1.6 API Routes

Create file `lib/gateway/routes/shared_knowledge.py`:

```python
"""Shared Knowledge API routes."""
from __future__ import annotations

from typing import Optional

try:
    from fastapi import APIRouter, Query, Request
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False

router = APIRouter() if HAS_FASTAPI else None


if HAS_FASTAPI:

    @router.post("/api/shared-knowledge/publish")
    async def publish_knowledge(request: Request):
        """Publish a knowledge entry.

        Body JSON:
        {
            "agent_id": "claude-main",
            "category": "code_pattern",
            "title": "FastAPI middleware pattern",
            "content": "Use @app.middleware('http') ...",
            "tags": ["fastapi", "middleware"],
            "source_request_id": "abc-123"   // optional
        }
        """
        service = _get_service(request)
        body = await request.json()
        required = ["agent_id", "category", "title", "content"]
        missing = [f for f in required if f not in body]
        if missing:
            return {"error": f"Missing fields: {missing}"}, 400

        entry_id = service.publish(
            agent_id=body["agent_id"],
            category=body["category"],
            title=body["title"],
            content=body["content"],
            tags=body.get("tags"),
            source_request_id=body.get("source_request_id"),
            metadata=body.get("metadata"),
        )
        return {"id": entry_id, "status": "published"}

    @router.get("/api/shared-knowledge/query")
    async def query_knowledge_unified(
        request: Request,
        q: str = Query(..., description="Search query"),
        sources: Optional[str] = Query(None, description="Comma-separated: memory,shared,notebooklm,obsidian"),
        limit: int = Query(10, ge=1, le=50),
        agent_id: Optional[str] = Query(None),
    ):
        """Unified cross-source knowledge query."""
        service = _get_service(request)
        source_list = sources.split(",") if sources else None
        result = await service.unified_query(
            query=q,
            sources=source_list,
            limit=limit,
            agent_id=agent_id,
        )
        return result

    @router.post("/api/shared-knowledge/vote")
    async def vote_knowledge(request: Request):
        """Vote on a knowledge entry.

        Body JSON:
        {
            "knowledge_id": 42,
            "agent_id": "kimi-agent",
            "vote": "agree",         // agree | disagree | cite
            "comment": "Confirmed"   // optional
        }
        """
        service = _get_service(request)
        body = await request.json()
        result = service.vote(
            knowledge_id=body["knowledge_id"],
            agent_id=body["agent_id"],
            vote=body["vote"],
            comment=body.get("comment"),
        )
        return result

    @router.get("/api/shared-knowledge/feed")
    async def knowledge_feed(
        request: Request,
        category: Optional[str] = Query(None),
        agent_id: Optional[str] = Query(None),
        limit: int = Query(20, ge=1, le=100),
        offset: int = Query(0, ge=0),
    ):
        """Browse knowledge entries with optional filters."""
        service = _get_service(request)
        entries = service.list_entries(
            category=category,
            agent_id=agent_id,
            limit=limit,
            offset=offset,
        )
        return {"entries": entries, "count": len(entries)}

    @router.get("/api/shared-knowledge/agent/{agent_id}")
    async def get_agent_info(request: Request, agent_id: str):
        """Get agent profile and their knowledge contributions."""
        service = _get_service(request)
        agent = service.get_agent(agent_id)
        if not agent:
            return {"error": "Agent not found"}, 404
        entries = service.list_entries(agent_id=agent_id, limit=10)
        return {"agent": agent, "recent_entries": entries}

    @router.get("/api/shared-knowledge/stats")
    async def shared_knowledge_stats(request: Request):
        """Get shared knowledge statistics."""
        service = _get_service(request)
        return service.get_shared_stats()

    @router.delete("/api/shared-knowledge/{entry_id}")
    async def delete_knowledge(request: Request, entry_id: int):
        """Delete a knowledge entry."""
        service = _get_service(request)
        deleted = service.delete_entry(entry_id)
        if not deleted:
            return {"error": "Entry not found"}, 404
        return {"deleted": True, "id": entry_id}


def _get_service(request: Request):
    """Get SharedKnowledgeService from app state."""
    return request.app.state.shared_knowledge
```

### 1.7 App Factory Changes

In `lib/gateway/app.py`, add:

```python
# At top, add import:
from .routes import shared_knowledge as shared_knowledge_routes

# In create_app(), after existing route registrations, add:
_include_router_if_available(app, shared_knowledge_routes.router, tags=["shared-knowledge"])
```

Also in `create_app()`, add `shared_knowledge` parameter and initialization:

```python
# Add parameter:
def create_app(
    ...
    shared_knowledge=None,   # <-- NEW
):
    ...
    app.state.shared_knowledge = shared_knowledge   # <-- NEW
```

### 1.8 Gateway Server Changes

In `lib/gateway/gateway_server.py`, where services are initialized (the `_init_services()` or similar method), add:

```python
from lib.knowledge.shared_knowledge import SharedKnowledgeService

# After memory_middleware is created:
shared_knowledge = SharedKnowledgeService(
    db_path=store.db_path,  # reuse gateway.db
    memory=memory_middleware.memory if memory_middleware else None,
    knowledge_client=getattr(memory_middleware, '_knowledge_client', None),
    obsidian_search=getattr(memory_middleware, '_obsidian_search', None),
)

# Pass to create_app:
app = create_app(
    ...
    shared_knowledge=shared_knowledge,
)
```

---

## 2. Module B: Skill/MCP Unified Router

### 2.1 Goal

Build a unified index of **all tools** available to agents (local skills, MCP tools, MCP servers, remote skills). Provide a keyword-matching search API so agents can discover relevant tools.

### 2.2 New Files to Create

| File | Lines | Purpose |
|------|-------|---------|
| `lib/skills/tool_index.py` | ~250 | `ToolIndex` class — build/search unified index |
| `lib/skills/tool_index_builder.py` | ~150 | Index building logic (scan skills + MCP) |
| `lib/gateway/routes/tool_router.py` | ~120 | API routes (5 endpoints) |
| `bin/build-tool-index.sh` | ~80 | CLI script to rebuild index |
| `tests/test_tool_index.py` | ~120 | Unit tests |

### 2.3 Files to Modify

| File | Change |
|------|--------|
| `lib/gateway/app.py` | Register `tool_router` routes |
| `lib/skills/skills_discovery_core.py` | Wire `ToolIndex` into existing discovery |

### 2.4 Index Data Structure

The unified index lives at `~/.ccb_config/tool_index.json`:

```json
{
  "version": "1.1.0",
  "built_at": "2026-02-10T12:00:00Z",
  "entries": [
    {
      "id": "skill:pdf",
      "type": "skill",
      "name": "pdf",
      "description": "PDF manipulation toolkit",
      "keywords": ["pdf", "extract", "merge", "split", "form"],
      "triggers": ["/pdf", "pdf file", "extract text"],
      "installed": true,
      "source": "local",
      "path": "~/.claude/skills/pdf",
      "usage_count": 42,
      "last_used": "2026-02-09T10:00:00Z"
    },
    {
      "id": "mcp-tool:github.create_pull_request",
      "type": "mcp-tool",
      "name": "create_pull_request",
      "description": "Create a new pull request in a GitHub repository",
      "keywords": ["github", "pull request", "pr", "create"],
      "server": "github",
      "installed": true,
      "source": "mcp-active"
    },
    {
      "id": "mcp-server:context7",
      "type": "mcp-server",
      "name": "context7",
      "description": "Up-to-date documentation and code examples",
      "keywords": ["documentation", "docs", "library", "api"],
      "installed": true,
      "source": "mcp-active",
      "tool_count": 2
    },
    {
      "id": "remote-skill:algorithmic-art",
      "type": "remote-skill",
      "name": "algorithmic-art",
      "description": "Creating algorithmic art using p5.js",
      "keywords": ["art", "generative", "p5js", "creative"],
      "installed": false,
      "source": "remote"
    }
  ]
}
```

### 2.5 ToolIndex Implementation

#### File: `lib/skills/tool_index.py`

```python
"""Unified Tool Index for skills, MCP tools, and MCP servers."""
from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from lib.common.logging import get_logger
except ImportError:
    from common.logging import get_logger

logger = get_logger("skills.tool_index")

INDEX_PATH = Path.home() / ".ccb_config" / "tool_index.json"

# Chinese → English keyword mapping for bilingual matching
ZH_EN_KEYWORDS = {
    "前端": ["frontend", "react", "vue", "css", "html", "ui"],
    "后端": ["backend", "server", "api", "database"],
    "数据库": ["database", "sql", "postgres", "mysql", "sqlite"],
    "测试": ["test", "testing", "unittest", "pytest"],
    "部署": ["deploy", "deployment", "docker", "ci", "cd"],
    "文档": ["doc", "documentation", "readme", "markdown"],
    "图表": ["chart", "graph", "visualization", "plot"],
    "安全": ["security", "auth", "encryption"],
    "爬虫": ["crawler", "scraper", "spider", "web scraping"],
    "机器学习": ["ml", "machine learning", "ai", "model"],
    "数据分析": ["data analysis", "analytics", "statistics"],
    "自动化": ["automation", "workflow", "pipeline"],
    "版本控制": ["git", "version control", "svn"],
    "演示": ["presentation", "slides", "pptx"],
    "表格": ["spreadsheet", "excel", "xlsx", "csv"],
    "PDF": ["pdf", "document"],
    "笔记": ["notes", "notebook", "obsidian"],
}


class ToolIndex:
    """Unified index for discovering tools across all sources."""

    def __init__(self, index_path: Optional[Path] = None):
        self._path = index_path or INDEX_PATH
        self._entries: List[Dict] = []
        self._built_at: Optional[str] = None
        self._load()

    def _load(self) -> None:
        """Load index from disk if available."""
        if not self._path.exists():
            logger.debug("No tool index found at %s", self._path)
            return
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            self._entries = data.get("entries", [])
            self._built_at = data.get("built_at")
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Failed to load tool index: %s", exc)

    def save(self) -> None:
        """Persist index to disk."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "version": "1.1.0",
            "built_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "entries": self._entries,
        }
        self._path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    def set_entries(self, entries: List[Dict]) -> None:
        """Replace all entries and save."""
        self._entries = entries
        self.save()

    def add_entry(self, entry: Dict) -> None:
        """Add or update a single entry by id."""
        existing = [e for e in self._entries if e.get("id") != entry.get("id")]
        existing.append(entry)
        self._entries = existing

    @property
    def stats(self) -> Dict:
        by_type = {}
        installed = 0
        for e in self._entries:
            t = e.get("type", "unknown")
            by_type[t] = by_type.get(t, 0) + 1
            if e.get("installed"):
                installed += 1
        return {
            "total": len(self._entries),
            "installed": installed,
            "by_type": by_type,
            "built_at": self._built_at,
        }

    def search(self, query: str, limit: int = 10,
               installed_only: bool = False,
               types: Optional[List[str]] = None) -> List[Dict]:
        """Search the index by query. Returns scored results.

        Scoring:
          +3  trigger match (exact)
          +2  keyword match
          +2  name match
          +1  description word match
          +0.5 installed bonus
          +usage_bonus (min(usage_count/100, 0.5))
        """
        query_lower = query.lower().strip()
        query_words = set(re.split(r'[\s,;/]+', query_lower))

        # Expand Chinese keywords to English equivalents
        expanded_words = set(query_words)
        for zh, en_list in ZH_EN_KEYWORDS.items():
            if zh in query_lower:
                expanded_words.update(en_list)

        results = []
        for entry in self._entries:
            if installed_only and not entry.get("installed"):
                continue
            if types and entry.get("type") not in types:
                continue

            score = self._score_entry(entry, query_lower, query_words, expanded_words)
            if score > 0:
                results.append({**entry, "_score": score})

        results.sort(key=lambda x: x["_score"], reverse=True)
        return results[:limit]

    def _score_entry(self, entry: Dict, query_lower: str,
                     query_words: set, expanded_words: set) -> float:
        score = 0.0
        name = (entry.get("name") or "").lower()
        desc = (entry.get("description") or "").lower()
        keywords = [k.lower() for k in entry.get("keywords", [])]
        triggers = [t.lower() for t in entry.get("triggers", [])]

        # Trigger match (+3)
        for trigger in triggers:
            if trigger in query_lower or query_lower in trigger:
                score += 3.0
                break

        # Keyword match (+2 each, max +6)
        kw_matches = sum(1 for kw in keywords if kw in expanded_words or kw in query_lower)
        score += min(kw_matches * 2.0, 6.0)

        # Name match (+2)
        if name in query_lower or any(w in name for w in query_words):
            score += 2.0

        # Description word match (+1 each, max +3)
        desc_words = set(re.split(r'[\s,;/]+', desc))
        desc_matches = len(expanded_words & desc_words)
        score += min(desc_matches * 1.0, 3.0)

        # Installed bonus
        if entry.get("installed"):
            score += 0.5

        # Usage bonus
        usage = entry.get("usage_count", 0)
        if usage > 0:
            score += min(usage / 100, 0.5)

        return score

    def get_entry(self, entry_id: str) -> Optional[Dict]:
        for e in self._entries:
            if e.get("id") == entry_id:
                return e
        return None
```

#### File: `lib/skills/tool_index_builder.py`

```python
"""Build the unified tool index from all sources."""
from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path
from typing import Dict, List, Optional

try:
    from lib.common.logging import get_logger
except ImportError:
    from common.logging import get_logger

logger = get_logger("skills.tool_index_builder")

SKILLS_DIR = Path.home() / ".claude" / "skills"
MCP_CONFIG = Path.home() / ".claude" / "mcp_servers.json"


def build_index() -> List[Dict]:
    """Scan all sources and build unified entry list."""
    entries = []
    entries.extend(_scan_local_skills())
    entries.extend(_scan_mcp_servers())
    entries.extend(_scan_mcp_tools())
    logger.info("Built tool index: %d entries", len(entries))
    return entries


def _scan_local_skills() -> List[Dict]:
    """Scan ~/.claude/skills/ for local skill definitions."""
    entries = []
    if not SKILLS_DIR.exists():
        return entries

    for skill_dir in sorted(SKILLS_DIR.iterdir()):
        if not skill_dir.is_dir():
            continue
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.exists():
            continue

        name = skill_dir.name
        description, triggers, keywords = _parse_skill_md(skill_md)

        entries.append({
            "id": f"skill:{name}",
            "type": "skill",
            "name": name,
            "description": description,
            "keywords": keywords,
            "triggers": triggers,
            "installed": True,
            "source": "local",
            "path": str(skill_dir),
        })

    return entries


def _parse_skill_md(path: Path) -> tuple:
    """Parse SKILL.md frontmatter for description, triggers, keywords."""
    text = path.read_text(encoding="utf-8", errors="replace")
    description = ""
    triggers = []
    keywords = []

    in_frontmatter = False
    for line in text.split("\n"):
        stripped = line.strip()
        if stripped == "---":
            in_frontmatter = not in_frontmatter
            continue
        if not in_frontmatter:
            continue

        if stripped.startswith("description:"):
            description = stripped.split(":", 1)[1].strip().strip("'\"")
        elif stripped.startswith("- ") and triggers is not None:
            val = stripped[2:].strip().strip("'\"")
            if "trigger" in text[:text.index(stripped)].split("\n")[-2].lower():
                triggers.append(val)
            else:
                keywords.append(val)
        elif stripped.startswith("triggers:"):
            pass  # next lines will be triggers
        elif stripped.startswith("keywords:"):
            pass  # next lines will be keywords

    # Extract keywords from description if none found
    if not keywords and description:
        keywords = [w.lower() for w in description.split()
                    if len(w) > 3 and w.isalpha()][:5]

    return description, triggers, keywords


def _scan_mcp_servers() -> List[Dict]:
    """Read MCP server configuration and create entries."""
    entries = []
    if not MCP_CONFIG.exists():
        return entries

    try:
        config = json.loads(MCP_CONFIG.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return entries

    for server_name, server_config in config.items():
        entries.append({
            "id": f"mcp-server:{server_name}",
            "type": "mcp-server",
            "name": server_name,
            "description": f"MCP server: {server_name}",
            "keywords": [server_name],
            "installed": True,
            "source": "mcp-config",
        })

    return entries


def _scan_mcp_tools() -> List[Dict]:
    """Discover active MCP tools from running servers.

    This reads from the MCP tool manifest if available, or
    uses the mcp_servers.json to infer tool names.
    """
    entries = []
    manifest = Path.home() / ".ccb_config" / "mcp_tools_manifest.json"
    if not manifest.exists():
        return entries

    try:
        tools = json.loads(manifest.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return entries

    for tool in tools:
        server = tool.get("server", "unknown")
        name = tool.get("name", "unknown")
        entries.append({
            "id": f"mcp-tool:{server}.{name}",
            "type": "mcp-tool",
            "name": name,
            "description": tool.get("description", ""),
            "keywords": tool.get("keywords", [name, server]),
            "server": server,
            "installed": True,
            "source": "mcp-active",
        })

    return entries
```

#### File: `bin/build-tool-index.sh`

```bash
#!/usr/bin/env bash
# Build the unified tool index for Hivemind v1.1
set -euo pipefail

cd "$(dirname "$0")/.."
python3 -c "
from lib.skills.tool_index import ToolIndex
from lib.skills.tool_index_builder import build_index

entries = build_index()
idx = ToolIndex()
idx.set_entries(entries)
print(f'Tool index built: {idx.stats[\"total\"]} entries')
print(f'  By type: {idx.stats[\"by_type\"]}')
print(f'  Installed: {idx.stats[\"installed\"]}')
"
```

Make executable: `chmod +x bin/build-tool-index.sh`

### 2.6 API Routes

Create file `lib/gateway/routes/tool_router.py`:

```python
"""Tool Router API routes — unified tool discovery."""
from __future__ import annotations

from typing import Optional

try:
    from fastapi import APIRouter, Query, Request
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False

router = APIRouter() if HAS_FASTAPI else None


if HAS_FASTAPI:

    @router.get("/api/tools/search")
    async def search_tools(
        request: Request,
        q: str = Query(..., description="Search query"),
        limit: int = Query(10, ge=1, le=50),
        installed_only: bool = Query(False),
        types: Optional[str] = Query(None, description="Comma-separated: skill,mcp-tool,mcp-server,remote-skill"),
    ):
        """Search unified tool index."""
        index = _get_index(request)
        type_list = types.split(",") if types else None
        results = index.search(q, limit=limit, installed_only=installed_only, types=type_list)
        return {"query": q, "results": results, "total": len(results)}

    @router.get("/api/tools/index")
    async def get_tool_index(request: Request):
        """Get full tool index stats."""
        index = _get_index(request)
        return index.stats

    @router.post("/api/tools/rebuild")
    async def rebuild_tool_index(request: Request):
        """Rebuild the tool index from all sources."""
        from lib.skills.tool_index_builder import build_index

        index = _get_index(request)
        entries = build_index()
        index.set_entries(entries)
        return {"status": "rebuilt", "stats": index.stats}

    @router.get("/api/tools/{entry_id:path}")
    async def get_tool_entry(request: Request, entry_id: str):
        """Get details for a specific tool entry."""
        index = _get_index(request)
        entry = index.get_entry(entry_id)
        if not entry:
            return {"error": "Tool not found"}, 404
        return entry

    @router.get("/api/tools")
    async def list_tools(
        request: Request,
        type: Optional[str] = Query(None, description="Filter by type"),
        installed: Optional[bool] = Query(None),
    ):
        """List all tools with optional filters."""
        index = _get_index(request)
        results = index._entries
        if type:
            results = [e for e in results if e.get("type") == type]
        if installed is not None:
            results = [e for e in results if e.get("installed") == installed]
        return {"tools": results, "total": len(results)}


def _get_index(request: Request):
    """Get ToolIndex from app state."""
    return request.app.state.tool_index
```

### 2.7 App Factory Changes

In `lib/gateway/app.py`, add:

```python
# Import:
from .routes import tool_router as tool_router_routes

# In create_app(), add parameter:
def create_app(
    ...
    tool_index=None,          # <-- NEW
):
    ...
    app.state.tool_index = tool_index   # <-- NEW

# Register route:
_include_router_if_available(app, tool_router_routes.router, tags=["tools"])
```

### 2.8 Gateway Server Changes

In `lib/gateway/gateway_server.py`, add initialization:

```python
from lib.skills.tool_index import ToolIndex
from lib.skills.tool_index_builder import build_index

# Build tool index on startup
tool_index = ToolIndex()
if not tool_index._entries:
    try:
        entries = build_index()
        tool_index.set_entries(entries)
    except Exception as exc:
        logger.warning("Failed to build tool index: %s", exc)

# Pass to create_app:
app = create_app(
    ...
    tool_index=tool_index,
)
```

---

## 3. Module C: Integration (A + B)

### 3.1 Memory Middleware Enhancement

In `lib/gateway/middleware/memory_middleware_core.py`, enhance `post_response()` to auto-publish to shared knowledge:

```python
# In the post_response method, after recording the conversation,
# add auto-publish logic:

async def _maybe_auto_publish(self, request_data: Dict, response_data: Dict) -> None:
    """Auto-publish high-quality responses to shared knowledge."""
    if not hasattr(self, '_shared_knowledge') or self._shared_knowledge is None:
        return

    # Only publish successful, non-trivial responses
    response_text = response_data.get("response", "")
    if not response_text or len(response_text) < 200:
        return

    provider = request_data.get("provider", "unknown")
    message = request_data.get("message", "")

    # Simple heuristic: publish if response is substantial
    # and contains code or structured content
    has_code = "```" in response_text
    has_structure = response_text.count("\n") > 10

    if not (has_code or has_structure):
        return

    try:
        self._shared_knowledge.publish(
            agent_id=f"{provider}-auto",
            category="solution" if has_code else "learning",
            title=message[:100],
            content=response_text[:2000],  # cap at 2000 chars
            tags=self._extract_tags(message),
            source_request_id=request_data.get("request_id"),
        )
    except (RuntimeError, ValueError, TypeError, OSError) as exc:
        logger.debug("Auto-publish failed: %s", exc)

def _extract_tags(self, text: str) -> List[str]:
    """Extract simple tags from text."""
    import re
    words = re.findall(r'\b[a-zA-Z]{3,15}\b', text.lower())
    # Keep only meaningful words, deduplicate
    stopwords = {"the", "and", "for", "this", "that", "with", "from", "have", "are", "was"}
    tags = list(dict.fromkeys(w for w in words if w not in stopwords))
    return tags[:5]
```

### 3.2 Tool Recommendations in Skills Discovery

In `lib/skills/skills_discovery_core.py`, add a method to use ToolIndex:

```python
def get_tool_recommendations(self, task: str, limit: int = 5) -> Dict:
    """Get unified tool recommendations using ToolIndex + skills cache.

    Falls back to existing match_skills() if ToolIndex unavailable.
    """
    try:
        from lib.skills.tool_index import ToolIndex
        index = ToolIndex()
        if index._entries:
            results = index.search(task, limit=limit)
            return {
                "source": "tool_index",
                "results": results,
                "count": len(results),
            }
    except (ImportError, RuntimeError, OSError):
        pass

    # Fallback to existing skills matching
    return self.get_recommendations(task)
```

---

## 4. Testing Requirements

Create file `tests/test_shared_knowledge.py`:

```python
"""Tests for Shared Knowledge Layer (v1.1 Module A)."""
import json
import os
import tempfile
import pytest

# Test setup
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestSharedKnowledgeDB:
    """Test SharedKnowledgeService database operations."""

    def setup_method(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()
        from lib.knowledge.shared_knowledge import SharedKnowledgeService
        self.service = SharedKnowledgeService(db_path=self.tmp.name)

    def teardown_method(self):
        os.unlink(self.tmp.name)

    def test_publish_and_get(self):
        entry_id = self.service.publish(
            agent_id="test-agent",
            category="code_pattern",
            title="Test Pattern",
            content="This is a test pattern for unit testing.",
            tags=["test", "pattern"],
        )
        assert entry_id > 0

        entry = self.service.get_entry(entry_id)
        assert entry is not None
        assert entry["title"] == "Test Pattern"
        assert entry["category"] == "code_pattern"
        assert "test" in entry["tags"]

    def test_search_fts(self):
        self.service.publish("a1", "solution", "React Hooks Guide",
                            "How to use useState and useEffect in React", ["react"])
        self.service.publish("a1", "solution", "Vue Composition API",
                            "How to use setup() and ref() in Vue 3", ["vue"])

        results = self.service.search_fts("React")
        assert len(results) >= 1
        assert any("React" in r["title"] for r in results)

    def test_vote_updates_confidence(self):
        entry_id = self.service.publish("a1", "learning", "Test", "Content")
        entry_before = self.service.get_entry(entry_id)
        assert entry_before["confidence"] == 0.5

        self.service.vote(entry_id, "a2", "agree")
        self.service.vote(entry_id, "a3", "agree")
        entry_after = self.service.get_entry(entry_id)
        assert entry_after["confidence"] > 0.5

    def test_vote_disagree_lowers_confidence(self):
        entry_id = self.service.publish("a1", "learning", "Bad", "Wrong info")
        self.service.vote(entry_id, "a2", "disagree")
        entry = self.service.get_entry(entry_id)
        assert entry["confidence"] < 0.5

    def test_delete(self):
        entry_id = self.service.publish("a1", "other", "Temp", "Temporary")
        assert self.service.delete_entry(entry_id) is True
        assert self.service.get_entry(entry_id) is None

    def test_list_entries_with_filters(self):
        self.service.publish("a1", "code_pattern", "P1", "Content 1")
        self.service.publish("a2", "solution", "P2", "Content 2")
        self.service.publish("a1", "code_pattern", "P3", "Content 3")

        # Filter by category
        patterns = self.service.list_entries(category="code_pattern")
        assert len(patterns) == 2

        # Filter by agent
        a1_entries = self.service.list_entries(agent_id="a1")
        assert len(a1_entries) == 2

    def test_stats(self):
        self.service.publish("a1", "code_pattern", "P1", "C1")
        self.service.publish("a2", "solution", "P2", "C2")
        self.service.vote(1, "a2", "agree")

        stats = self.service.get_shared_stats()
        assert stats["total_entries"] == 2
        assert stats["total_agents"] == 2
        assert stats["total_votes"] == 1

    def test_access_log(self):
        entry_id = self.service.publish("a1", "learning", "L1", "Content")
        self.service.log_access(entry_id, "a2", "test query", 0.8)
        entry = self.service.get_entry(entry_id)
        assert entry["access_count"] == 1


class TestToolIndex:
    """Test ToolIndex search and scoring."""

    def setup_method(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
        self.tmp.close()
        from lib.skills.tool_index import ToolIndex
        self.index = ToolIndex(index_path=self.tmp.name)
        self.index.set_entries([
            {"id": "skill:pdf", "type": "skill", "name": "pdf",
             "description": "PDF manipulation toolkit",
             "keywords": ["pdf", "extract", "merge"],
             "triggers": ["/pdf"], "installed": True},
            {"id": "skill:xlsx", "type": "skill", "name": "xlsx",
             "description": "Spreadsheet creation and analysis",
             "keywords": ["excel", "spreadsheet", "xlsx"],
             "triggers": ["/xlsx"], "installed": True},
            {"id": "mcp-tool:github.create_pr", "type": "mcp-tool",
             "name": "create_pull_request",
             "description": "Create a pull request on GitHub",
             "keywords": ["github", "pr", "pull request"],
             "installed": True, "server": "github"},
            {"id": "remote-skill:canvas-design", "type": "remote-skill",
             "name": "canvas-design",
             "description": "Create visual art and posters",
             "keywords": ["design", "art", "poster", "visual"],
             "installed": False},
        ])

    def teardown_method(self):
        os.unlink(self.tmp.name)

    def test_search_by_trigger(self):
        results = self.index.search("/pdf")
        assert results[0]["name"] == "pdf"
        assert results[0]["_score"] >= 3.0

    def test_search_by_keyword(self):
        results = self.index.search("spreadsheet excel")
        assert any(r["name"] == "xlsx" for r in results)

    def test_search_chinese(self):
        results = self.index.search("创建PDF文档")
        assert any(r["name"] == "pdf" for r in results)

    def test_installed_only(self):
        results = self.index.search("design art", installed_only=True)
        assert all(r.get("installed") for r in results)

    def test_type_filter(self):
        results = self.index.search("github", types=["mcp-tool"])
        assert all(r["type"] == "mcp-tool" for r in results)

    def test_stats(self):
        stats = self.index.stats
        assert stats["total"] == 4
        assert stats["installed"] == 3
        assert "skill" in stats["by_type"]
```

---

## 5. Implementation Phases

### Phase 1: Database Schema (30 min)
- Create `lib/knowledge/schema_shared.sql`
- Create `lib/knowledge/__init__.py` (if not exists)
- Verify schema loads correctly into gateway.db

### Phase 2: Shared Knowledge Service (60 min)
- Create `lib/knowledge/shared_knowledge_db.py`
- Create `lib/knowledge/shared_knowledge_query.py`
- Create `lib/knowledge/shared_knowledge.py`
- Run: `python3 -c "from lib.knowledge.shared_knowledge import SharedKnowledgeService; s = SharedKnowledgeService(); print('OK')"`

### Phase 3: Shared Knowledge API Routes (30 min)
- Create `lib/gateway/routes/shared_knowledge.py`
- Modify `lib/gateway/app.py` — add import + registration + parameter
- Modify `lib/gateway/gateway_server.py` — instantiate SharedKnowledgeService
- Verify: `curl http://localhost:8765/api/shared-knowledge/stats`

### Phase 4: Tool Index (45 min)
- Create `lib/skills/tool_index.py`
- Create `lib/skills/tool_index_builder.py`
- Create `bin/build-tool-index.sh` (make executable)
- Run: `bash bin/build-tool-index.sh`
- Verify index file exists: `cat ~/.ccb_config/tool_index.json | python3 -m json.tool | head -20`

### Phase 5: Tool Router API (30 min)
- Create `lib/gateway/routes/tool_router.py`
- Modify `lib/gateway/app.py` — add tool_router import + registration + parameter
- Modify `lib/gateway/gateway_server.py` — instantiate ToolIndex
- Verify: `curl http://localhost:8765/api/tools/search?q=pdf`

### Phase 6: Integration + Tests (45 min)
- Modify `lib/gateway/middleware/memory_middleware_core.py` — add auto-publish
- Add `get_tool_recommendations()` to `lib/skills/skills_discovery_core.py`
- Create `tests/test_shared_knowledge.py`
- Run: `python3 -m pytest tests/test_shared_knowledge.py -v`
- Run: `python3 -m pytest tests/ -x -q` (full regression)

---

## 6. Acceptance Criteria

### 6.1 Shared Knowledge (Module A)

| Test | Command | Expected |
|------|---------|----------|
| Publish | `curl -X POST /api/shared-knowledge/publish -d '{"agent_id":"test","category":"learning","title":"Test","content":"Hello"}'` | `{"id": N, "status": "published"}` |
| Query | `curl /api/shared-knowledge/query?q=test` | Results from shared + memory |
| Vote | `curl -X POST /api/shared-knowledge/vote -d '{"knowledge_id":1,"agent_id":"a2","vote":"agree"}'` | Confidence updated |
| Feed | `curl /api/shared-knowledge/feed` | List of entries |
| Stats | `curl /api/shared-knowledge/stats` | `{"total_entries": N, ...}` |
| Delete | `curl -X DELETE /api/shared-knowledge/1` | `{"deleted": true}` |

### 6.2 Tool Router (Module B)

| Test | Command | Expected |
|------|---------|----------|
| Search | `curl /api/tools/search?q=pdf` | Results with `_score` |
| Chinese search | `curl /api/tools/search?q=表格` | xlsx/spreadsheet results |
| Index stats | `curl /api/tools/index` | `{"total": N, "by_type": {...}}` |
| Rebuild | `curl -X POST /api/tools/rebuild` | `{"status": "rebuilt"}` |
| List by type | `curl /api/tools?type=skill` | Skills only |
| Installed only | `curl /api/tools/search?q=pdf&installed_only=true` | Only installed |

### 6.3 Integration

| Test | Expected |
|------|----------|
| `python3 -m pytest tests/ -x -q` | All tests pass (181+ pass) |
| Gateway restart | No startup errors |
| No file > 500 lines | All new files under limit |
| No `except Exception` | Use specific exceptions only |
| No `print()` | Use `get_logger()` |

### 6.4 New Endpoint Count

v1.1 adds **12 new API endpoints**:
- 7 shared knowledge endpoints (`/api/shared-knowledge/*`)
- 5 tool router endpoints (`/api/tools/*`)

Total after v1.1: **138 endpoints** (126 + 12)

---

## 7. File Summary

### New Files (10)

| File | Est. Lines |
|------|-----------|
| `lib/knowledge/schema_shared.sql` | 60 |
| `lib/knowledge/shared_knowledge.py` | 30 |
| `lib/knowledge/shared_knowledge_db.py` | 200 |
| `lib/knowledge/shared_knowledge_query.py` | 180 |
| `lib/gateway/routes/shared_knowledge.py` | 130 |
| `lib/skills/tool_index.py` | 200 |
| `lib/skills/tool_index_builder.py` | 150 |
| `lib/gateway/routes/tool_router.py` | 100 |
| `bin/build-tool-index.sh` | 15 |
| `tests/test_shared_knowledge.py` | 150 |
| **Total new** | **~1,215** |

### Modified Files (4)

| File | Change |
|------|--------|
| `lib/gateway/app.py` | +15 lines (2 route registrations + 2 params) |
| `lib/gateway/gateway_server.py` | +20 lines (service initialization) |
| `lib/gateway/middleware/memory_middleware_core.py` | +40 lines (auto-publish) |
| `lib/skills/skills_discovery_core.py` | +15 lines (tool recommendations) |
| **Total modified** | **~+90** |

### Grand Total: ~1,305 new lines

---

## 8. Architecture Rules Checklist

Before submitting, verify:

- [ ] All new files ≤ 500 lines
- [ ] No `except Exception` — use `(RuntimeError, ValueError, TypeError, OSError)`
- [ ] No `print()` — use `logger.info/debug/warning`
- [ ] Imports use `try: from lib.xxx except ImportError: from xxx` pattern
- [ ] SQLite connections use `PRAGMA journal_mode=WAL`
- [ ] FTS5 uses `trigram` tokenizer
- [ ] All API routes return JSON (no tuples — use `JSONResponse` for error status codes)
- [ ] Tests in `tests/` directory using existing `conftest.py`
- [ ] `bin/build-tool-index.sh` is executable (`chmod +x`)
- [ ] `python3 -m pytest tests/ -x -q` passes
- [ ] Gateway starts without errors
- [ ] All 12 new endpoints respond correctly

---

*End of v1.1 Implementation Guide*
