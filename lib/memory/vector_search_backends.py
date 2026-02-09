from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

try:
    from .vector_search_models import VectorConfig, VectorSearchResult
    from .vector_search_shared import (
        HAS_CHROMA,
        HAS_QDRANT,
        ChromaClient,
        Distance,
        FieldCondition,
        Filter,
        MatchValue,
        PointStruct,
        QdrantClient,
        Settings,
        VectorParams,
        chromadb,
        logger,
    )
except ImportError:  # pragma: no cover - script mode
    from vector_search_models import VectorConfig, VectorSearchResult
    from vector_search_shared import (
        HAS_CHROMA,
        HAS_QDRANT,
        ChromaClient,
        Distance,
        FieldCondition,
        Filter,
        MatchValue,
        PointStruct,
        QdrantClient,
        Settings,
        VectorParams,
        chromadb,
        logger,
    )


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
            logger.info("Created Qdrant collection: %s", self.config.qdrant_collection)

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
        except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError) as e:
            logger.warning("Qdrant index error: %s", e)
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
        except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError) as e:
            logger.warning("Qdrant search error: %s", e)
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
        except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError) as e:
            logger.warning("Qdrant delete error: %s", e)
            return False

    def count(self) -> int:
        """Get total indexed vectors."""
        try:
            info = self.client.get_collection(self.config.qdrant_collection)
            return info.points_count
        except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError):
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
        except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError) as e:
            logger.warning("Chroma index error: %s", e)
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
        except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError) as e:
            logger.warning("Chroma search error: %s", e)
            return []

    def delete(self, memory_id: str) -> bool:
        """Delete a memory from the index."""
        try:
            self.collection.delete(ids=[memory_id])
            return True
        except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError) as e:
            logger.warning("Chroma delete error: %s", e)
            return False

    def count(self) -> int:
        """Get total indexed vectors."""
        try:
            return self.collection.count()
        except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError):
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


