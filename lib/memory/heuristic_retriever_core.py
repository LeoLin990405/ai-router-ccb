"""Auto-split mixins for HeuristicRetriever."""
from __future__ import annotations

import json
import math
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .heuristic_retriever_shared import logger


try:
    from .heuristic_retriever import RetrievalConfig
except ImportError:  # pragma: no cover - script mode
    from heuristic_retriever import RetrievalConfig


class HeuristicRetrieverCoreMixin:
    """Mixin methods extracted from HeuristicRetriever."""

    def __init__(
        self,
        db_path: Optional[Path] = None,
        config: Optional[RetrievalConfig] = None
    ):
        """Initialize the heuristic retriever.

        Args:
            db_path: Path to SQLite database (default: ~/.ccb/ccb_memory.db)
            config: Retrieval configuration (loads from file if not provided)
        """
        if db_path is None:
            db_path = Path.home() / ".ccb" / "ccb_memory.db"

        self.db_path = Path(db_path)
        self.config = config or RetrievalConfig.from_file()

        # Ensure migration is applied
        self._ensure_schema()

    def _ensure_schema(self):
        """Ensure v2 schema tables exist."""
        migration_file = Path(__file__).parent / "schema_v2_migration.sql"

        if not migration_file.exists():
            return

        conn = sqlite3.connect(self.db_path)
        try:
            # Read and execute migration (idempotent with IF NOT EXISTS)
            with open(migration_file) as f:
                sql = f.read()

            # Execute statements one by one to handle errors gracefully
            for statement in sql.split(';'):
                statement = statement.strip()
                if statement and not statement.startswith('--'):
                    try:
                        conn.execute(statement)
                    except sqlite3.OperationalError:
                        # Likely already exists or column already added
                        pass

            # Try to add columns to messages table
            for col_sql in [
                "ALTER TABLE messages ADD COLUMN importance_score REAL DEFAULT 0.5",
                "ALTER TABLE messages ADD COLUMN last_accessed_at TEXT",
                "ALTER TABLE messages ADD COLUMN access_count INTEGER DEFAULT 0"
            ]:
                try:
                    conn.execute(col_sql)
                except sqlite3.OperationalError:
                    pass  # Column already exists

            # Try to add columns to observations table
            for col_sql in [
                "ALTER TABLE observations ADD COLUMN importance_score REAL DEFAULT 0.5",
                "ALTER TABLE observations ADD COLUMN last_accessed_at TEXT",
                "ALTER TABLE observations ADD COLUMN access_count INTEGER DEFAULT 0",
                "ALTER TABLE observations ADD COLUMN decay_rate REAL DEFAULT 0.05"
            ]:
                try:
                    conn.execute(col_sql)
                except sqlite3.OperationalError:
                    pass  # Column already exists

            conn.commit()
        finally:
            conn.close()

    def retrieve(
        self,
        query: str,
        limit: Optional[int] = None,
        memory_types: Optional[List[str]] = None,
        provider: Optional[str] = None,
        session_id: Optional[str] = None,
        min_importance: Optional[float] = None,
        request_id: Optional[str] = None,
        track_access: bool = True
    ) -> List[ScoredMemory]:
        """
        Perform heuristic retrieval with αR + βI + γT scoring.

        Args:
            query: Search query string
            limit: Maximum results to return (default from config)
            memory_types: Filter by types ['message', 'observation']
            provider: Filter by AI provider
            session_id: Filter by session
            min_importance: Minimum importance threshold
            request_id: Gateway request ID for access tracking
            track_access: Whether to log access (default True)

        Returns:
            List of ScoredMemory objects sorted by final_score descending
        """
        if not query or not query.strip():
            return []

        limit = limit or self.config.final_limit
        memory_types = memory_types or ['message', 'observation']

        candidates: List[ScoredMemory] = []

        # Step 1: FTS5 search for messages
        if 'message' in memory_types:
            message_candidates = self._search_messages_fts(
                query,
                limit=self.config.candidate_pool_size,
                provider=provider,
                session_id=session_id
            )
            candidates.extend(message_candidates)

        # Step 2: FTS5 search for observations
        if 'observation' in memory_types:
            observation_candidates = self._search_observations_fts(
                query,
                limit=self.config.candidate_pool_size
            )
            candidates.extend(observation_candidates)

        # Step 3: Calculate heuristic scores
        scored = []
        for memory in candidates:
            # Get importance and recency data
            importance_data = self._get_importance_data(memory.memory_id, memory.memory_type)

            # Update scores
            memory.importance_score = importance_data.get('importance_score', self.config.default_importance)
            memory.access_count = importance_data.get('access_count', 0)
            memory.last_accessed_at = importance_data.get('last_accessed_at')

            # Calculate recency
            memory.recency_score = self._calculate_recency(memory.last_accessed_at)

            # Calculate final score: αR + βI + γT
            memory.final_score = (
                self.config.alpha * memory.relevance_score +
                self.config.beta * memory.importance_score +
                self.config.gamma * memory.recency_score
            )

            # Apply minimum importance filter
            if min_importance is not None and memory.importance_score < min_importance:
                continue

            scored.append(memory)

        # Step 4: Sort by final score
        scored.sort(key=lambda x: x.final_score, reverse=True)

        # Step 5: Take top results
        results = scored[:limit]

        # Step 6: Track access for retrieved memories
        if track_access and results:
            self._log_access_batch(
                results,
                query=query,
                request_id=request_id,
                context='retrieval'
            )

        return results

