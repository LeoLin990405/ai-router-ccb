#!/usr/bin/env python3
"""
CCB Memory System v2.0 - Heuristic Retriever

Implements the Stanford Generative Agents style retrieval scoring:
    final_score = α × relevance + β × importance + γ × recency

Where:
    - relevance: FTS5 or vector similarity score
    - importance: User-marked or LLM-evaluated importance (0-1)
    - recency: Ebbinghaus forgetting curve decay (exp(-λ × hours))

Reference:
    - Stanford Generative Agents: https://arxiv.org/pdf/2304.03442
    - Ebbinghaus Forgetting Curve
"""

import json
import math
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class ScoredMemory:
    """A memory item with its computed heuristic scores."""
    memory_id: str
    memory_type: str  # 'message' | 'observation'
    content: str

    # Individual scores
    relevance_score: float = 0.0
    importance_score: float = 0.5
    recency_score: float = 0.5

    # Combined final score
    final_score: float = 0.0

    # Metadata
    provider: Optional[str] = None
    timestamp: Optional[str] = None
    role: Optional[str] = None
    session_id: Optional[str] = None
    category: Optional[str] = None
    tags: List[str] = field(default_factory=list)

    # Access tracking
    access_count: int = 0
    last_accessed_at: Optional[str] = None

    # Raw data
    raw_data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RetrievalConfig:
    """Configuration for heuristic retrieval."""
    # Scoring weights (should sum to 1.0)
    alpha: float = 0.4  # Relevance weight
    beta: float = 0.3   # Importance weight
    gamma: float = 0.3  # Recency weight

    # Decay parameters
    decay_lambda: float = 0.1  # Decay rate per hour
    min_recency: float = 0.01  # Minimum recency score

    # Search parameters
    candidate_pool_size: int = 50
    final_limit: int = 5
    min_relevance_threshold: float = 0.1

    # Importance defaults
    default_importance: float = 0.5
    access_boost: float = 0.01

    @classmethod
    def from_file(cls, config_path: Optional[Path] = None) -> 'RetrievalConfig':
        """Load configuration from JSON file."""
        if config_path is None:
            config_path = Path.home() / ".ccb" / "heuristic_config.json"

        if not config_path.exists():
            return cls()

        try:
            with open(config_path) as f:
                data = json.load(f)

            retrieval = data.get("retrieval", {})
            importance = data.get("importance", {})
            decay = data.get("decay", {})

            return cls(
                alpha=retrieval.get("relevance_weight", 0.4),
                beta=retrieval.get("importance_weight", 0.3),
                gamma=retrieval.get("recency_weight", 0.3),
                decay_lambda=decay.get("lambda", 0.1),
                min_recency=decay.get("min_score", 0.01),
                candidate_pool_size=retrieval.get("candidate_pool_size", 50),
                final_limit=retrieval.get("final_limit", 5),
                min_relevance_threshold=retrieval.get("min_relevance_threshold", 0.1),
                default_importance=importance.get("default_score", 0.5),
                access_boost=importance.get("access_boost_amount", 0.01)
            )
        except Exception as e:
            print(f"[HeuristicRetriever] Config load error: {e}, using defaults")
            return cls()


class HeuristicRetriever:
    """
    Heuristic Memory Retriever implementing αR + βI + γT scoring.

    System 1 (Fast Path): Real-time retrieval with sub-100ms latency.

    Usage:
        retriever = HeuristicRetriever(db_path)
        results = retriever.retrieve("python error handling", limit=5)

        for memory in results:
            print(f"{memory.content[:50]}... (score: {memory.final_score:.3f})")
    """

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

    def _search_messages_fts(
        self,
        query: str,
        limit: int = 50,
        provider: Optional[str] = None,
        session_id: Optional[str] = None
    ) -> List[ScoredMemory]:
        """Search messages using FTS5."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            # Build query with optional filters
            sql = """
                SELECT
                    m.message_id,
                    m.session_id,
                    m.role,
                    m.content,
                    m.provider,
                    m.timestamp,
                    m.tokens,
                    bm25(messages_fts) as fts_rank
                FROM messages m
                JOIN messages_fts fts ON m.rowid = fts.rowid
                WHERE messages_fts MATCH ?
            """
            params = [query]

            if provider:
                sql += " AND m.provider = ?"
                params.append(provider)

            if session_id:
                sql += " AND m.session_id = ?"
                params.append(session_id)

            sql += " ORDER BY fts_rank LIMIT ?"
            params.append(limit)

            cursor.execute(sql, params)

            results = []
            for row in cursor.fetchall():
                # Normalize FTS rank to 0-1 (bm25 returns negative values, lower is better)
                fts_rank = row[7]
                # Convert BM25 score: higher negative means more relevant
                # Typical range is -25 to 0, so normalize
                relevance = min(1.0, max(0.0, (25 + fts_rank) / 25)) if fts_rank else 0.5

                memory = ScoredMemory(
                    memory_id=row[0],
                    memory_type='message',
                    content=row[3] or '',
                    relevance_score=relevance,
                    session_id=row[1],
                    role=row[2],
                    provider=row[4],
                    timestamp=row[5],
                    raw_data={
                        'tokens': row[6],
                        'fts_rank': fts_rank
                    }
                )
                results.append(memory)

            return results

        except sqlite3.OperationalError as e:
            print(f"[HeuristicRetriever] FTS search error: {e}")
            return []
        finally:
            conn.close()

    def _search_observations_fts(
        self,
        query: str,
        limit: int = 50
    ) -> List[ScoredMemory]:
        """Search observations using FTS5."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            sql = """
                SELECT
                    o.observation_id,
                    o.category,
                    o.content,
                    o.tags,
                    o.source,
                    o.confidence,
                    o.created_at,
                    bm25(observations_fts) as fts_rank
                FROM observations o
                JOIN observations_fts fts ON o.rowid = fts.rowid
                WHERE observations_fts MATCH ?
                ORDER BY fts_rank
                LIMIT ?
            """

            cursor.execute(sql, [query, limit])

            results = []
            for row in cursor.fetchall():
                fts_rank = row[7]
                relevance = min(1.0, max(0.0, (25 + fts_rank) / 25)) if fts_rank else 0.5

                # Parse tags
                try:
                    tags = json.loads(row[3]) if row[3] else []
                except json.JSONDecodeError:
                    tags = []

                memory = ScoredMemory(
                    memory_id=row[0],
                    memory_type='observation',
                    content=row[2] or '',
                    relevance_score=relevance,
                    category=row[1],
                    tags=tags,
                    timestamp=row[6],
                    raw_data={
                        'source': row[4],
                        'confidence': row[5],
                        'fts_rank': fts_rank
                    }
                )
                results.append(memory)

            return results

        except sqlite3.OperationalError as e:
            print(f"[HeuristicRetriever] Observations FTS error: {e}")
            return []
        finally:
            conn.close()

    def _get_importance_data(self, memory_id: str, memory_type: str) -> Dict[str, Any]:
        """Get importance and access data for a memory."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            cursor.execute("""
                SELECT importance_score, access_count, last_accessed_at, decay_rate
                FROM memory_importance
                WHERE memory_id = ? AND memory_type = ?
            """, (memory_id, memory_type))

            row = cursor.fetchone()
            if row:
                return {
                    'importance_score': row[0] or self.config.default_importance,
                    'access_count': row[1] or 0,
                    'last_accessed_at': row[2],
                    'decay_rate': row[3] or self.config.decay_lambda
                }

            return {
                'importance_score': self.config.default_importance,
                'access_count': 0,
                'last_accessed_at': None,
                'decay_rate': self.config.decay_lambda
            }

        except sqlite3.OperationalError:
            return {
                'importance_score': self.config.default_importance,
                'access_count': 0,
                'last_accessed_at': None,
                'decay_rate': self.config.decay_lambda
            }
        finally:
            conn.close()

    def _calculate_recency(self, last_accessed_at: Optional[str]) -> float:
        """
        Calculate recency score using Ebbinghaus forgetting curve.

        Formula: recency = exp(-λ × hours_since_access)

        Args:
            last_accessed_at: ISO 8601 timestamp of last access

        Returns:
            Recency score between min_recency and 1.0
        """
        if not last_accessed_at:
            # Never accessed - treat as 1 week old
            hours_since = 168
        else:
            try:
                # Parse timestamp
                if 'T' in last_accessed_at:
                    dt = datetime.fromisoformat(last_accessed_at.replace('Z', '+00:00'))
                else:
                    dt = datetime.strptime(last_accessed_at, "%Y-%m-%d %H:%M:%S")

                delta = datetime.now() - dt.replace(tzinfo=None)
                hours_since = delta.total_seconds() / 3600
            except (ValueError, TypeError):
                hours_since = 168  # Default to 1 week

        # Apply Ebbinghaus decay
        recency = math.exp(-self.config.decay_lambda * hours_since)

        # Clamp to minimum
        return max(self.config.min_recency, recency)

    def _log_access_batch(
        self,
        memories: List[ScoredMemory],
        query: str,
        request_id: Optional[str],
        context: str
    ):
        """Log access for a batch of memories."""
        if not memories:
            return

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            now = datetime.now().isoformat()

            for memory in memories:
                cursor.execute("""
                    INSERT INTO memory_access_log
                    (memory_id, memory_type, accessed_at, access_context, request_id, query_text, relevance_score)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    memory.memory_id,
                    memory.memory_type,
                    now,
                    context,
                    request_id,
                    query[:500] if query else None,  # Truncate long queries
                    memory.relevance_score
                ))

            conn.commit()
        except sqlite3.OperationalError as e:
            print(f"[HeuristicRetriever] Access logging error: {e}")
        finally:
            conn.close()

    def set_importance(
        self,
        memory_id: str,
        memory_type: str,
        importance: float,
        source: str = 'user'
    ) -> bool:
        """
        Set importance score for a memory.

        Args:
            memory_id: Memory UUID
            memory_type: 'message' or 'observation'
            importance: Score between 0.0 and 1.0
            source: 'user', 'llm', or 'heuristic'

        Returns:
            True if successful
        """
        importance = max(0.0, min(1.0, importance))  # Clamp to 0-1

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            now = datetime.now().isoformat()

            cursor.execute("""
                INSERT INTO memory_importance
                (memory_id, memory_type, importance_score, score_source, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(memory_id) DO UPDATE SET
                    importance_score = excluded.importance_score,
                    score_source = excluded.score_source,
                    updated_at = excluded.updated_at
            """, (memory_id, memory_type, importance, source, now, now))

            conn.commit()
            return True
        except sqlite3.OperationalError as e:
            print(f"[HeuristicRetriever] Set importance error: {e}")
            return False
        finally:
            conn.close()

    def boost_importance(
        self,
        memory_id: str,
        memory_type: str,
        boost: Optional[float] = None
    ) -> float:
        """
        Boost importance score for a memory (e.g., on user interaction).

        Args:
            memory_id: Memory UUID
            memory_type: 'message' or 'observation'
            boost: Amount to boost (default from config)

        Returns:
            New importance score
        """
        boost = boost or self.config.access_boost

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            # Get current importance
            cursor.execute("""
                SELECT importance_score FROM memory_importance
                WHERE memory_id = ? AND memory_type = ?
            """, (memory_id, memory_type))

            row = cursor.fetchone()
            current = row[0] if row else self.config.default_importance

            # Calculate new importance (capped at 1.0)
            new_importance = min(1.0, current + boost)

            # Update
            now = datetime.now().isoformat()
            cursor.execute("""
                INSERT INTO memory_importance
                (memory_id, memory_type, importance_score, score_source, updated_at)
                VALUES (?, ?, ?, 'heuristic', ?)
                ON CONFLICT(memory_id) DO UPDATE SET
                    importance_score = ?,
                    updated_at = ?
            """, (memory_id, memory_type, new_importance, now, new_importance, now))

            conn.commit()
            return new_importance
        except sqlite3.OperationalError as e:
            print(f"[HeuristicRetriever] Boost importance error: {e}")
            return self.config.default_importance
        finally:
            conn.close()

    def get_statistics(self) -> Dict[str, Any]:
        """Get retrieval system statistics."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            stats = {}

            # Total tracked memories
            cursor.execute("SELECT COUNT(*) FROM memory_importance")
            stats['tracked_memories'] = cursor.fetchone()[0]

            # By type
            cursor.execute("""
                SELECT memory_type, COUNT(*)
                FROM memory_importance
                GROUP BY memory_type
            """)
            stats['by_type'] = dict(cursor.fetchall())

            # Importance distribution
            cursor.execute("""
                SELECT
                    SUM(CASE WHEN importance_score >= 0.8 THEN 1 ELSE 0 END) as high,
                    SUM(CASE WHEN importance_score >= 0.5 AND importance_score < 0.8 THEN 1 ELSE 0 END) as medium,
                    SUM(CASE WHEN importance_score < 0.5 THEN 1 ELSE 0 END) as low
                FROM memory_importance
            """)
            row = cursor.fetchone()
            stats['importance_distribution'] = {
                'high': row[0] or 0,
                'medium': row[1] or 0,
                'low': row[2] or 0
            }

            # Recent accesses
            cursor.execute("""
                SELECT COUNT(*) FROM memory_access_log
                WHERE accessed_at > datetime('now', '-24 hours')
            """)
            stats['accesses_24h'] = cursor.fetchone()[0]

            # Total accesses
            cursor.execute("SELECT COUNT(*) FROM memory_access_log")
            stats['total_accesses'] = cursor.fetchone()[0]

            # Average access count
            cursor.execute("SELECT AVG(access_count) FROM memory_importance")
            stats['avg_access_count'] = cursor.fetchone()[0] or 0

            # Config
            stats['config'] = {
                'alpha': self.config.alpha,
                'beta': self.config.beta,
                'gamma': self.config.gamma,
                'decay_lambda': self.config.decay_lambda
            }

            return stats

        except sqlite3.OperationalError as e:
            return {'error': str(e)}
        finally:
            conn.close()


# Convenience function for quick retrieval
def retrieve_memories(
    query: str,
    limit: int = 5,
    db_path: Optional[Path] = None
) -> List[ScoredMemory]:
    """
    Quick function to retrieve memories with heuristic scoring.

    Args:
        query: Search query
        limit: Maximum results
        db_path: Database path (optional)

    Returns:
        List of ScoredMemory objects
    """
    retriever = HeuristicRetriever(db_path=db_path)
    return retriever.retrieve(query, limit=limit)


if __name__ == "__main__":
    # Quick test
    import sys

    if len(sys.argv) < 2:
        print("Usage: python heuristic_retriever.py <query>")
        sys.exit(1)

    query = " ".join(sys.argv[1:])
    print(f"Searching for: {query}\n")

    retriever = HeuristicRetriever()
    results = retriever.retrieve(query, limit=5)

    if not results:
        print("No results found.")
    else:
        for i, mem in enumerate(results, 1):
            print(f"{i}. [{mem.memory_type}] {mem.content[:80]}...")
            print(f"   Score: {mem.final_score:.3f} (R={mem.relevance_score:.2f}, I={mem.importance_score:.2f}, T={mem.recency_score:.2f})")
            print()

    print("\nStatistics:")
    stats = retriever.get_statistics()
    print(json.dumps(stats, indent=2, default=str))
