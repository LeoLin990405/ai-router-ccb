from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    from .vector_search_backends import ChromaBackend, InMemoryBackend, QdrantBackend
    from .vector_search_embeddings import EmbeddingProvider
    from .vector_search_models import VectorConfig, VectorSearchResult
    from .vector_search_shared import logger
except ImportError:  # pragma: no cover - script mode
    from vector_search_backends import ChromaBackend, InMemoryBackend, QdrantBackend
    from vector_search_embeddings import EmbeddingProvider
    from vector_search_models import VectorConfig, VectorSearchResult
    from vector_search_shared import logger


class VectorSearch:
    """
    Main vector search interface for CCB Memory System.

    Provides:
    - Automatic embedding generation
    - Multiple backend support (Qdrant, ChromaDB, in-memory)
    - Hybrid search combining vector + BM25
    - Batch indexing for efficiency
    """

    def __init__(self, config: Optional[VectorConfig] = None):
        """Initialize vector search.

        Args:
            config: Vector search configuration
        """
        self.config = config or VectorConfig.from_file()
        self.embedding_provider = EmbeddingProvider(self.config.embedding_model)
        self.backend: Optional[VectorBackend] = None

        if self.config.enabled:
            self._init_backend()

    def _init_backend(self):
        """Initialize the vector backend."""
        try:
            if self.config.backend == "qdrant":
                self.backend = QdrantBackend(self.config)
            elif self.config.backend == "chroma":
                self.backend = ChromaBackend(self.config)
            else:
                self.backend = InMemoryBackend(self.config)

            logger.info("Initialized %s backend", self.config.backend)
        except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError) as e:
            logger.warning("Backend init failed: %s, falling back to in-memory", e)
            self.backend = InMemoryBackend(self.config)

    def index_memory(
        self,
        memory_id: str,
        memory_type: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Index a single memory.

        Args:
            memory_id: Unique memory identifier
            memory_type: 'message' or 'observation'
            content: Text content to index
            metadata: Additional metadata

        Returns:
            True if successful
        """
        if not self.config.enabled or not self.backend:
            return False

        # Generate embedding
        embedding = self.embedding_provider.embed(content)
        if embedding is None:
            return False

        return self.backend.index(
            memory_id=memory_id,
            memory_type=memory_type,
            content=content,
            embedding=embedding,
            metadata=metadata or {}
        )

    def index_batch(
        self,
        memories: List[Dict[str, Any]]
    ) -> Tuple[int, int]:
        """
        Index multiple memories in batch.

        Args:
            memories: List of dicts with keys: memory_id, memory_type, content, metadata

        Returns:
            Tuple of (success_count, failure_count)
        """
        if not self.config.enabled or not self.backend:
            return 0, len(memories)

        # Extract texts for batch embedding
        texts = [m.get("content", "") for m in memories]
        embeddings = self.embedding_provider.embed_batch(texts)

        if embeddings is None:
            return 0, len(memories)

        success = 0
        failure = 0

        for i, memory in enumerate(memories):
            if self.backend.index(
                memory_id=memory.get("memory_id", ""),
                memory_type=memory.get("memory_type", ""),
                content=memory.get("content", ""),
                embedding=embeddings[i],
                metadata=memory.get("metadata", {})
            ):
                success += 1
            else:
                failure += 1

        return success, failure

    def search(
        self,
        query: str,
        limit: int = 10,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[VectorSearchResult]:
        """
        Search for similar memories.

        Args:
            query: Search query text
            limit: Maximum results
            filters: Optional filters (e.g., {"memory_type": "message"})

        Returns:
            List of VectorSearchResult
        """
        if not self.config.enabled or not self.backend:
            return []

        # Generate query embedding
        embedding = self.embedding_provider.embed(query)
        if embedding is None:
            return []

        return self.backend.search(embedding, limit=limit, filters=filters)

    def delete_memory(self, memory_id: str) -> bool:
        """Delete a memory from the vector index."""
        if not self.backend:
            return False
        return self.backend.delete(memory_id)

    def get_stats(self) -> Dict[str, Any]:
        """Get vector search statistics."""
        return {
            "enabled": self.config.enabled,
            "backend": self.config.backend,
            "indexed_count": self.backend.count() if self.backend else 0,
            "embedding_model": self.config.embedding_model,
            "embedding_dim": self.config.embedding_dim,
            "vector_weight": self.config.vector_weight,
            "bm25_weight": self.config.bm25_weight,
        }

    def sync_from_database(
        self,
        db_path: Optional[Path] = None,
        memory_types: Optional[List[str]] = None,
        limit: Optional[int] = None
    ) -> Tuple[int, int]:
        """
        Sync memories from SQLite database to vector index.

        Args:
            db_path: Path to SQLite database
            memory_types: Types to sync ('message', 'observation')
            limit: Maximum memories to sync

        Returns:
            Tuple of (success_count, failure_count)
        """
        if db_path is None:
            db_path = Path.home() / ".ccb" / "ccb_memory.db"

        memory_types = memory_types or ['message', 'observation']

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        memories = []

        try:
            # Sync messages
            if 'message' in memory_types:
                sql = "SELECT message_id, content, provider, timestamp FROM messages"
                if limit:
                    sql += f" ORDER BY timestamp DESC LIMIT {limit}"

                cursor.execute(sql)
                for row in cursor.fetchall():
                    if row[1]:  # Has content
                        memories.append({
                            "memory_id": row[0],
                            "memory_type": "message",
                            "content": row[1],
                            "metadata": {
                                "provider": row[2],
                                "timestamp": row[3]
                            }
                        })

            # Sync observations
            if 'observation' in memory_types:
                sql = "SELECT observation_id, content, category, created_at FROM observations"
                if limit:
                    sql += f" ORDER BY created_at DESC LIMIT {limit}"

                cursor.execute(sql)
                for row in cursor.fetchall():
                    if row[1]:  # Has content
                        memories.append({
                            "memory_id": row[0],
                            "memory_type": "observation",
                            "content": row[1],
                            "metadata": {
                                "category": row[2],
                                "timestamp": row[3]
                            }
                        })
        finally:
            conn.close()

        if not memories:
            return 0, 0

        # Batch index
        return self.index_batch(memories)



# Singleton instance
_vector_search: Optional[VectorSearch] = None


def get_vector_search(config: Optional[VectorConfig] = None) -> VectorSearch:
    """Get or create the global VectorSearch instance."""
    global _vector_search
    if _vector_search is None:
        _vector_search = VectorSearch(config)
    return _vector_search


