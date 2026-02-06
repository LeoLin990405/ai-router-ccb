#!/usr/bin/env python3
"""
CCB Memory System v2.1 - Vector Search Integration

Provides hybrid retrieval combining:
1. BM25 (FTS5) for keyword matching
2. Vector similarity for semantic search
3. Heuristic scoring (αR + βI + γT)

Supports multiple vector backends:
- Qdrant (recommended for production)
- ChromaDB (lightweight alternative)
- In-memory FAISS (for testing)
"""

import json
import hashlib
import numpy as np
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
import sqlite3

# Optional imports for vector backends
try:
    from qdrant_client import QdrantClient
    from qdrant_client.models import Distance, VectorParams, PointStruct, Filter, FieldCondition, MatchValue
    HAS_QDRANT = True
except ImportError:
    HAS_QDRANT = False

try:
    import chromadb
    from chromadb.config import Settings
    HAS_CHROMA = True
except ImportError:
    HAS_CHROMA = False

# Embedding model options
try:
    from sentence_transformers import SentenceTransformer
    HAS_SENTENCE_TRANSFORMERS = True
except ImportError:
    HAS_SENTENCE_TRANSFORMERS = False


@dataclass
class VectorConfig:
    """Configuration for vector search."""
    enabled: bool = True
    backend: str = "qdrant"  # "qdrant", "chroma", "memory"

    # Qdrant settings
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    qdrant_collection: str = "ccb_memories"

    # ChromaDB settings
    chroma_persist_dir: str = "~/.ccb/chroma"

    # Embedding settings
    embedding_model: str = "all-MiniLM-L6-v2"  # Fast, good quality
    embedding_dim: int = 384

    # Hybrid search settings
    vector_weight: float = 0.5  # Weight for vector similarity in hybrid search
    bm25_weight: float = 0.5   # Weight for BM25 in hybrid search

    # Indexing settings
    batch_size: int = 100
    auto_index: bool = True

    @classmethod
    def from_file(cls, config_path: Optional[Path] = None) -> 'VectorConfig':
        """Load configuration from JSON file."""
        if config_path is None:
            config_path = Path.home() / ".ccb" / "vector_config.json"

        if not config_path.exists():
            return cls()

        try:
            with open(config_path) as f:
                data = json.load(f)
            return cls(**data)
        except Exception as e:
            print(f"[VectorSearch] Config load error: {e}, using defaults")
            return cls()

    def save(self, config_path: Optional[Path] = None):
        """Save configuration to JSON file."""
        if config_path is None:
            config_path = Path.home() / ".ccb" / "vector_config.json"

        config_path.parent.mkdir(parents=True, exist_ok=True)

        with open(config_path, 'w') as f:
            json.dump({
                'enabled': self.enabled,
                'backend': self.backend,
                'qdrant_host': self.qdrant_host,
                'qdrant_port': self.qdrant_port,
                'qdrant_collection': self.qdrant_collection,
                'chroma_persist_dir': self.chroma_persist_dir,
                'embedding_model': self.embedding_model,
                'embedding_dim': self.embedding_dim,
                'vector_weight': self.vector_weight,
                'bm25_weight': self.bm25_weight,
                'batch_size': self.batch_size,
                'auto_index': self.auto_index,
            }, f, indent=2)


@dataclass
class VectorSearchResult:
    """Result from vector search."""
    memory_id: str
    memory_type: str
    content: str
    vector_score: float  # Cosine similarity (0-1)
    metadata: Dict[str, Any] = field(default_factory=dict)


class EmbeddingProvider:
    """Provides text embeddings using sentence-transformers."""

    _instance = None
    _model = None

    def __new__(cls, model_name: str = "all-MiniLM-L6-v2"):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        if self._model is None and HAS_SENTENCE_TRANSFORMERS:
            try:
                self._model = SentenceTransformer(model_name)
                print(f"[EmbeddingProvider] Loaded model: {model_name}")
            except Exception as e:
                print(f"[EmbeddingProvider] Failed to load model: {e}")
                self._model = None

    def embed(self, text: str) -> Optional[List[float]]:
        """Generate embedding for a single text."""
        if self._model is None:
            return None

        try:
            embedding = self._model.encode(text, convert_to_numpy=True)
            return embedding.tolist()
        except Exception as e:
            print(f"[EmbeddingProvider] Embedding error: {e}")
            return None

    def embed_batch(self, texts: List[str]) -> Optional[List[List[float]]]:
        """Generate embeddings for multiple texts."""
        if self._model is None:
            return None

        try:
            embeddings = self._model.encode(texts, convert_to_numpy=True)
            return embeddings.tolist()
        except Exception as e:
            print(f"[EmbeddingProvider] Batch embedding error: {e}")
            return None

    @property
    def dimension(self) -> int:
        """Get embedding dimension."""
        if self._model is None:
            return 384  # Default for all-MiniLM-L6-v2
        return self._model.get_sentence_embedding_dimension()


class VectorBackend:
    """Abstract base class for vector backends."""

    def index(self, memory_id: str, memory_type: str, content: str,
              embedding: List[float], metadata: Dict[str, Any]) -> bool:
        raise NotImplementedError

    def search(self, embedding: List[float], limit: int = 10,
               filters: Optional[Dict[str, Any]] = None) -> List[VectorSearchResult]:
        raise NotImplementedError

    def delete(self, memory_id: str) -> bool:
        raise NotImplementedError

    def count(self) -> int:
        raise NotImplementedError


class QdrantBackend(VectorBackend):
    """Qdrant vector database backend."""

    def __init__(self, config: VectorConfig):
        if not HAS_QDRANT:
            raise ImportError("qdrant-client not installed. Run: pip install qdrant-client")

        self.config = config
        self.client = QdrantClient(host=config.qdrant_host, port=config.qdrant_port)
        self._ensure_collection()

    def _ensure_collection(self):
        """Ensure the collection exists."""
        collections = self.client.get_collections().collections
        collection_names = [c.name for c in collections]

        if self.config.qdrant_collection not in collection_names:
            self.client.create_collection(
                collection_name=self.config.qdrant_collection,
                vectors_config=VectorParams(
                    size=self.config.embedding_dim,
                    distance=Distance.COSINE
                )
            )
            print(f"[QdrantBackend] Created collection: {self.config.qdrant_collection}")

    def index(self, memory_id: str, memory_type: str, content: str,
              embedding: List[float], metadata: Dict[str, Any]) -> bool:
        """Index a memory in Qdrant."""
        try:
            # Generate numeric ID from memory_id hash
            point_id = int(hashlib.md5(memory_id.encode()).hexdigest()[:16], 16)

            self.client.upsert(
                collection_name=self.config.qdrant_collection,
                points=[
                    PointStruct(
                        id=point_id,
                        vector=embedding,
                        payload={
                            "memory_id": memory_id,
                            "memory_type": memory_type,
                            "content": content[:1000],  # Truncate for storage
                            **metadata
                        }
                    )
                ]
            )
            return True
        except Exception as e:
            print(f"[QdrantBackend] Index error: {e}")
            return False

    def search(self, embedding: List[float], limit: int = 10,
               filters: Optional[Dict[str, Any]] = None) -> List[VectorSearchResult]:
        """Search for similar vectors."""
        try:
            # Build filter if provided
            qdrant_filter = None
            if filters:
                conditions = []
                for key, value in filters.items():
                    conditions.append(
                        FieldCondition(key=key, match=MatchValue(value=value))
                    )
                if conditions:
                    qdrant_filter = Filter(must=conditions)

            results = self.client.search(
                collection_name=self.config.qdrant_collection,
                query_vector=embedding,
                limit=limit,
                query_filter=qdrant_filter
            )

            return [
                VectorSearchResult(
                    memory_id=r.payload.get("memory_id", ""),
                    memory_type=r.payload.get("memory_type", ""),
                    content=r.payload.get("content", ""),
                    vector_score=r.score,
                    metadata={k: v for k, v in r.payload.items()
                             if k not in ["memory_id", "memory_type", "content"]}
                )
                for r in results
            ]
        except Exception as e:
            print(f"[QdrantBackend] Search error: {e}")
            return []

    def delete(self, memory_id: str) -> bool:
        """Delete a memory from the index."""
        try:
            point_id = int(hashlib.md5(memory_id.encode()).hexdigest()[:16], 16)
            self.client.delete(
                collection_name=self.config.qdrant_collection,
                points_selector=[point_id]
            )
            return True
        except Exception as e:
            print(f"[QdrantBackend] Delete error: {e}")
            return False

    def count(self) -> int:
        """Get total indexed vectors."""
        try:
            info = self.client.get_collection(self.config.qdrant_collection)
            return info.points_count
        except Exception:
            return 0


class ChromaBackend(VectorBackend):
    """ChromaDB vector database backend."""

    def __init__(self, config: VectorConfig):
        if not HAS_CHROMA:
            raise ImportError("chromadb not installed. Run: pip install chromadb")

        self.config = config
        persist_dir = Path(config.chroma_persist_dir).expanduser()
        persist_dir.mkdir(parents=True, exist_ok=True)

        self.client = chromadb.PersistentClient(path=str(persist_dir))
        self.collection = self.client.get_or_create_collection(
            name=config.qdrant_collection,
            metadata={"hnsw:space": "cosine"}
        )

    def index(self, memory_id: str, memory_type: str, content: str,
              embedding: List[float], metadata: Dict[str, Any]) -> bool:
        """Index a memory in ChromaDB."""
        try:
            self.collection.upsert(
                ids=[memory_id],
                embeddings=[embedding],
                documents=[content[:1000]],
                metadatas=[{"memory_type": memory_type, **metadata}]
            )
            return True
        except Exception as e:
            print(f"[ChromaBackend] Index error: {e}")
            return False

    def search(self, embedding: List[float], limit: int = 10,
               filters: Optional[Dict[str, Any]] = None) -> List[VectorSearchResult]:
        """Search for similar vectors."""
        try:
            where_filter = filters if filters else None

            results = self.collection.query(
                query_embeddings=[embedding],
                n_results=limit,
                where=where_filter
            )

            search_results = []
            if results['ids'] and results['ids'][0]:
                for i, memory_id in enumerate(results['ids'][0]):
                    # ChromaDB returns distances, convert to similarity
                    distance = results['distances'][0][i] if results['distances'] else 0
                    similarity = 1 - distance  # Cosine distance to similarity

                    search_results.append(VectorSearchResult(
                        memory_id=memory_id,
                        memory_type=results['metadatas'][0][i].get('memory_type', '') if results['metadatas'] else '',
                        content=results['documents'][0][i] if results['documents'] else '',
                        vector_score=max(0, similarity),
                        metadata=results['metadatas'][0][i] if results['metadatas'] else {}
                    ))

            return search_results
        except Exception as e:
            print(f"[ChromaBackend] Search error: {e}")
            return []

    def delete(self, memory_id: str) -> bool:
        """Delete a memory from the index."""
        try:
            self.collection.delete(ids=[memory_id])
            return True
        except Exception as e:
            print(f"[ChromaBackend] Delete error: {e}")
            return False

    def count(self) -> int:
        """Get total indexed vectors."""
        try:
            return self.collection.count()
        except Exception:
            return 0


class InMemoryBackend(VectorBackend):
    """Simple in-memory vector backend for testing."""

    def __init__(self, config: VectorConfig):
        self.config = config
        self.vectors: Dict[str, Dict[str, Any]] = {}

    def index(self, memory_id: str, memory_type: str, content: str,
              embedding: List[float], metadata: Dict[str, Any]) -> bool:
        """Index a memory in memory."""
        self.vectors[memory_id] = {
            "memory_type": memory_type,
            "content": content,
            "embedding": np.array(embedding),
            "metadata": metadata
        }
        return True

    def search(self, embedding: List[float], limit: int = 10,
               filters: Optional[Dict[str, Any]] = None) -> List[VectorSearchResult]:
        """Search for similar vectors using cosine similarity."""
        query_vec = np.array(embedding)
        query_norm = np.linalg.norm(query_vec)

        if query_norm == 0:
            return []

        scores = []
        for memory_id, data in self.vectors.items():
            # Apply filters
            if filters:
                skip = False
                for key, value in filters.items():
                    if data.get("metadata", {}).get(key) != value and data.get(key) != value:
                        skip = True
                        break
                if skip:
                    continue

            # Calculate cosine similarity
            vec = data["embedding"]
            vec_norm = np.linalg.norm(vec)
            if vec_norm == 0:
                continue

            similarity = np.dot(query_vec, vec) / (query_norm * vec_norm)
            scores.append((memory_id, data, similarity))

        # Sort by similarity
        scores.sort(key=lambda x: x[2], reverse=True)

        return [
            VectorSearchResult(
                memory_id=memory_id,
                memory_type=data["memory_type"],
                content=data["content"],
                vector_score=float(score),
                metadata=data.get("metadata", {})
            )
            for memory_id, data, score in scores[:limit]
        ]

    def delete(self, memory_id: str) -> bool:
        """Delete a memory from the index."""
        if memory_id in self.vectors:
            del self.vectors[memory_id]
            return True
        return False

    def count(self) -> int:
        """Get total indexed vectors."""
        return len(self.vectors)


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

            print(f"[VectorSearch] Initialized {self.config.backend} backend")
        except Exception as e:
            print(f"[VectorSearch] Backend init failed: {e}, falling back to in-memory")
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


if __name__ == "__main__":
    # Quick test
    import sys

    print("CCB Vector Search Test")
    print("=" * 50)

    # Initialize
    vs = VectorSearch()
    print(f"Stats: {vs.get_stats()}")

    # Test indexing
    test_memories = [
        {"memory_id": "test1", "memory_type": "message", "content": "Python error handling with try-except blocks"},
        {"memory_id": "test2", "memory_type": "message", "content": "React component lifecycle methods"},
        {"memory_id": "test3", "memory_type": "observation", "content": "User prefers TypeScript over JavaScript"},
    ]

    success, failure = vs.index_batch(test_memories)
    print(f"Indexed: {success} success, {failure} failure")

    # Test search
    if len(sys.argv) > 1:
        query = " ".join(sys.argv[1:])
    else:
        query = "error handling"

    print(f"\nSearching for: {query}")
    results = vs.search(query, limit=5)

    for i, r in enumerate(results, 1):
        print(f"{i}. [{r.memory_type}] {r.content[:60]}... (score: {r.vector_score:.3f})")
