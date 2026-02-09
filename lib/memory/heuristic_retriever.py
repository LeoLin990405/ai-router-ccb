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

try:
    from lib.common.logging import get_logger
except ImportError:  # pragma: no cover - script mode
    try:
        from common.logging import get_logger  # type: ignore
    except ImportError:  # pragma: no cover - fallback
        import logging

        def get_logger(name: str):
            return logging.getLogger(name)


logger = get_logger("memory.heuristic_retriever")


def _emit(message: str = "") -> None:
    sys.stdout.write(f"{message}\n")


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
        except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError) as e:
            logger.warning("Config load error: %s, using defaults", e)
            return cls()



try:
    from .heuristic_retriever_core import HeuristicRetrieverCoreMixin
    from .heuristic_retriever_ops import HeuristicRetrieverOpsMixin
    from .heuristic_retriever_search import HeuristicRetrieverSearchMixin
except ImportError:  # pragma: no cover - script mode
    from heuristic_retriever_core import HeuristicRetrieverCoreMixin
    from heuristic_retriever_ops import HeuristicRetrieverOpsMixin
    from heuristic_retriever_search import HeuristicRetrieverSearchMixin


class HeuristicRetriever(
    HeuristicRetrieverCoreMixin,
    HeuristicRetrieverSearchMixin,
    HeuristicRetrieverOpsMixin,
):
    """Heuristic Memory Retriever implementing αR + βI + γT scoring."""


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
        _emit("Usage: python heuristic_retriever.py <query>")
        sys.exit(1)

    query = " ".join(sys.argv[1:])
    _emit(f"Searching for: {query}\n")

    retriever = HeuristicRetriever()
    results = retriever.retrieve(query, limit=5)

    if not results:
        _emit("No results found.")
    else:
        for i, mem in enumerate(results, 1):
            _emit(f"{i}. [{mem.memory_type}] {mem.content[:80]}...")
            _emit(f"   Score: {mem.final_score:.3f} (R={mem.relevance_score:.2f}, I={mem.importance_score:.2f}, T={mem.recency_score:.2f})")
            _emit()

    _emit("\nStatistics:")
    stats = retriever.get_statistics()
    _emit(json.dumps(stats, indent=2, default=str))
