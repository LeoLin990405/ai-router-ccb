#!/usr/bin/env python3
"""CCB Memory System v2.1 - Vector Search Integration (modularized)."""
from __future__ import annotations

try:
    from .vector_search_backends import ChromaBackend, InMemoryBackend, QdrantBackend, VectorBackend
    from .vector_search_embeddings import EmbeddingProvider
    from .vector_search_models import VectorConfig, VectorSearchResult
    from .vector_search_service import VectorSearch, get_vector_search
    from .vector_search_shared import _emit
except ImportError:  # pragma: no cover - script mode
    from vector_search_backends import ChromaBackend, InMemoryBackend, QdrantBackend, VectorBackend
    from vector_search_embeddings import EmbeddingProvider
    from vector_search_models import VectorConfig, VectorSearchResult
    from vector_search_service import VectorSearch, get_vector_search
    from vector_search_shared import _emit


if __name__ == "__main__":
    # Quick test
    import sys

    _emit("CCB Vector Search Test")
    _emit("=" * 50)

    # Initialize
    vs = VectorSearch()
    _emit(f"Stats: {vs.get_stats()}")

    # Test indexing
    test_memories = [
        {"memory_id": "test1", "memory_type": "message", "content": "Python error handling with try-except blocks"},
        {"memory_id": "test2", "memory_type": "message", "content": "React component lifecycle methods"},
        {"memory_id": "test3", "memory_type": "observation", "content": "User prefers TypeScript over JavaScript"},
    ]

    success, failure = vs.index_batch(test_memories)
    _emit(f"Indexed: {success} success, {failure} failure")

    # Test search
    if len(sys.argv) > 1:
        query = " ".join(sys.argv[1:])
    else:
        query = "error handling"

    _emit(f"\nSearching for: {query}")
    results = vs.search(query, limit=5)

    for i, r in enumerate(results, 1):
        _emit(f"{i}. [{r.memory_type}] {r.content[:60]}... (score: {r.vector_score:.3f})")
