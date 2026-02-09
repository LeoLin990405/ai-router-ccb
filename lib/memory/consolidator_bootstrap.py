"""Auto-split mixin methods for NightlyConsolidator."""
from __future__ import annotations

import asyncio
import json
import math
import re
import sqlite3
import uuid
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from .consolidator_models import SessionArchive
from .consolidator_shared import CONSOLIDATOR_ERRORS, HAS_HTTPX, httpx, logger


class ConsolidatorBootstrapMixin:
    """Mixin methods extracted from NightlyConsolidator."""

    def __init__(
        self,
        archive_dir: Optional[Path] = None,  # Kept for backward compatibility
        memory_dir: Optional[Path] = None,   # Kept for backward compatibility
        llm_provider: str = None,
        db_path: Optional[Path] = None
    ):
        # Keep these for backward compatibility
        self.archive_dir = archive_dir or Path.home() / ".ccb" / "context_archive"
        self.memory_dir = memory_dir or Path.home() / ".ccb" / "memories"
        self.memory_dir.mkdir(parents=True, exist_ok=True)

        self.llm_provider = llm_provider or self.DEFAULT_LLM_PROVIDER
        self.db_path = db_path or self.DB_PATH

        # v2.0: Load heuristic config
        self.config = self._load_heuristic_config()

        # Ensure database tables exist
        self._init_db()

    def _init_db(self):
        """Ensure consolidation tables exist."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Consolidated memories table (System 2 output)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS consolidated_memories (
                memory_id TEXT PRIMARY KEY,
                user_id TEXT DEFAULT 'default',
                date TEXT NOT NULL,
                time_range_hours INTEGER,
                sessions_processed INTEGER DEFAULT 0,
                models_used TEXT,           -- JSON array
                project_progress TEXT,      -- JSON object
                tool_usage_total TEXT,      -- JSON object
                files_touched TEXT,         -- JSON object
                all_learnings TEXT,         -- JSON array
                causal_chains TEXT,         -- JSON array
                cross_session_insights TEXT,-- JSON array
                llm_enhanced INTEGER DEFAULT 0,
                llm_learnings TEXT,         -- JSON array
                llm_preferences TEXT,       -- JSON array
                llm_patterns TEXT,          -- JSON array
                llm_summary TEXT,
                metadata TEXT,              -- JSON object
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(date, user_id)
            )
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_consolidated_date
            ON consolidated_memories(date DESC)
        """)

        conn.commit()
        conn.close()

