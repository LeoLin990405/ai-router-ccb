from __future__ import annotations

from typing import List, Optional

try:
    from .vector_search_shared import HAS_SENTENCE_TRANSFORMERS, SentenceTransformer, logger
except ImportError:  # pragma: no cover - script mode
    from vector_search_shared import HAS_SENTENCE_TRANSFORMERS, SentenceTransformer, logger


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
                logger.info("Loaded embedding model: %s", model_name)
            except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError) as e:
                logger.warning("Failed to load embedding model: %s", e)
                self._model = None

    def embed(self, text: str) -> Optional[List[float]]:
        """Generate embedding for a single text."""
        if self._model is None:
            return None

        try:
            embedding = self._model.encode(text, convert_to_numpy=True)
            return embedding.tolist()
        except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError) as e:
            logger.warning("Embedding error: %s", e)
            return None

    def embed_batch(self, texts: List[str]) -> Optional[List[List[float]]]:
        """Generate embeddings for multiple texts."""
        if self._model is None:
            return None

        try:
            embeddings = self._model.encode(texts, convert_to_numpy=True)
            return embeddings.tolist()
        except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError) as e:
            logger.warning("Batch embedding error: %s", e)
            return None

    @property
    def dimension(self) -> int:
        """Get embedding dimension."""
        if self._model is None:
            return 384  # Default for all-MiniLM-L6-v2
        return self._model.get_sentence_embedding_dimension()


