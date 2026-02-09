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
import sys

# Optional imports for vector backends
try:
    from qdrant_client import QdrantClient
    from qdrant_client.models import Distance, VectorParams, PointStruct, Filter, FieldCondition, MatchValue
    HAS_QDRANT = True
except ImportError:
    QdrantClient = None
    Distance = None
    VectorParams = None
    PointStruct = None
    Filter = None
    FieldCondition = None
    MatchValue = None
    HAS_QDRANT = False

try:
    import chromadb
    ChromaClient = chromadb.PersistentClient
    from chromadb.config import Settings
    HAS_CHROMA = True
except ImportError:
    chromadb = None
    ChromaClient = None
    Settings = None
    HAS_CHROMA = False

# Embedding model options
try:
    from sentence_transformers import SentenceTransformer
    HAS_SENTENCE_TRANSFORMERS = True
except ImportError:
    SentenceTransformer = None
    HAS_SENTENCE_TRANSFORMERS = False

try:
    from lib.common.logging import get_logger
except ImportError:  # pragma: no cover - script mode
    try:
        from common.logging import get_logger  # type: ignore
    except ImportError:  # pragma: no cover - fallback
        import logging

        def get_logger(name: str):
            return logging.getLogger(name)


logger = get_logger("memory.vector_search")


def _emit(message: str = "") -> None:
    sys.stdout.write(f"{message}\n")
