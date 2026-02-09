"""Shared Knowledge service composition class."""
from __future__ import annotations

from typing import Optional

from .shared_knowledge_db import SharedKnowledgeDBMixin
from .shared_knowledge_query import SharedKnowledgeQueryMixin


class SharedKnowledgeService(SharedKnowledgeDBMixin, SharedKnowledgeQueryMixin):
    """Cross-agent shared knowledge service with unified queries."""

    def __init__(
        self,
        db_path: Optional[str] = None,
        memory=None,
        knowledge_client=None,
        obsidian_search=None,
    ):
        self._init_shared_db(db_path)
        self._memory = memory
        self._knowledge_client = knowledge_client
        self._obsidian_search = obsidian_search
