#!/usr/bin/env python3
"""CCB Memory System v2 - modularized compatibility facade."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Optional

from .memory_v2_discussions import MemoryV2DiscussionMixin
from .memory_v2_importance import MemoryV2ImportanceMixin
from .memory_v2_messages import MemoryV2MessagesMixin
from .memory_v2_observations import MemoryV2ObservationMixin
from .memory_v2_sessions import MemoryV2SessionMixin
from .memory_v2_streams import MemoryV2StreamMixin


class CCBMemoryV2(
    MemoryV2SessionMixin,
    MemoryV2MessagesMixin,
    MemoryV2ObservationMixin,
    MemoryV2DiscussionMixin,
    MemoryV2StreamMixin,
    MemoryV2ImportanceMixin,
):
    """CCB Memory System v2.0"""

    def __init__(self, db_path: str = None, user_id: str = "default"):
        """Initialize CCB Memory v2."""
        if db_path is None:
            db_path = Path.home() / ".ccb" / "ccb_memory.db"
        else:
            db_path = Path(db_path)

        self.db_path = db_path
        self.user_id = user_id
        self.current_session_id = None

        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()


class CCBLightMemory:
    """Backward compatibility wrapper for old memory_lite API."""

    def __init__(self, user_id: str = "leo"):
        self.v2 = CCBMemoryV2(user_id=user_id)

    def record_conversation(self, provider: str, question: str, answer: str,
                          metadata: Optional[Dict] = None, tokens: int = 0):
        """Backward compatible conversation recording."""
        return self.v2.record_conversation(
            provider=provider,
            question=question,
            answer=answer,
            tokens=tokens,
            metadata=metadata
        )

    def search_conversations(self, query: str, limit: int = 5,
                            provider: Optional[str] = None):
        """Backward compatible search."""
        messages = self.v2.search_messages(query, limit=limit*2, provider=provider)

        results = []
        for msg in messages:
            if msg['role'] == 'assistant':
                results.append({
                    "id": msg['message_id'],
                    "timestamp": msg['timestamp'],
                    "provider": msg['provider'],
                    "question": "",
                    "answer": msg['content'][:300],
                    "metadata": {}
                })

        return results[:limit]

    def get_stats(self):
        """Backward compatible stats."""
        return self.v2.get_stats()
