from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional

try:
    from .vector_search_shared import logger
except ImportError:  # pragma: no cover - script mode
    from vector_search_shared import logger


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
        except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError) as e:
            logger.warning("Config load error: %s, using defaults", e)
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


