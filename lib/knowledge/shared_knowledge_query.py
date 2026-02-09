"""Unified cross-source knowledge query mixin."""
from __future__ import annotations

import asyncio
import inspect
import time
from typing import Any, Dict, List, Optional

try:
    from lib.common.logging import get_logger
except ImportError:  # pragma: no cover - script mode fallback
    from common.logging import get_logger  # type: ignore

logger = get_logger("knowledge.query")


class SharedKnowledgeQueryMixin:
    """Unified query across memory/shared/notebook/obsidian sources."""

    async def unified_query(
        self,
        query: str,
        sources: Optional[List[str]] = None,
        limit: int = 10,
        agent_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        selected = sources or ["memory", "shared", "notebooklm", "obsidian"]
        start = time.time()

        tasks: Dict[str, asyncio.Future] = {}
        if "memory" in selected:
            tasks["memory"] = asyncio.ensure_future(self._query_memory(query, limit))
        if "shared" in selected:
            tasks["shared"] = asyncio.ensure_future(self._query_shared(query, limit, agent_id))
        if "notebooklm" in selected:
            tasks["notebooklm"] = asyncio.ensure_future(self._query_notebooklm(query, limit))
        if "obsidian" in selected:
            tasks["obsidian"] = asyncio.ensure_future(self._query_obsidian(query, limit))

        result_map: Dict[str, List[Dict[str, Any]]] = {}
        if tasks:
            gathered = await asyncio.gather(*tasks.values(), return_exceptions=True)
            for source_name, source_result in zip(tasks.keys(), gathered):
                if isinstance(source_result, BaseException):
                    logger.debug("Source query failed for %s", source_name, exc_info=True)
                    result_map[source_name] = []
                else:
                    result_map[source_name] = source_result

        merged: List[Dict[str, Any]] = []
        for source_name, items in result_map.items():
            for item in items:
                merged.append({**item, "source": source_name})

        merged.sort(key=lambda row: float(row.get("relevance", 0.0)), reverse=True)
        merged = merged[: limit * 2]

        return {
            "query": query,
            "results": merged,
            "sources_queried": list(result_map.keys()),
            "total_results": len(merged),
            "query_time_ms": round((time.time() - start) * 1000, 2),
        }

    async def _query_memory(self, query: str, limit: int) -> List[Dict[str, Any]]:
        memory = getattr(self, "_memory", None)
        if memory is None or not hasattr(memory, "search_conversations"):
            return []

        try:
            results = memory.search_conversations(query, limit=limit)
        except (RuntimeError, ValueError, TypeError, OSError, AttributeError, KeyError):
            logger.debug("Memory query failed", exc_info=True)
            return []

        normalized: List[Dict[str, Any]] = []
        for row in results if isinstance(results, list) else []:
            normalized.append(
                {
                    "title": (row.get("question") or "Memory conversation")[:120],
                    "content": row.get("answer") or row.get("content") or "",
                    "relevance": float(row.get("score") or row.get("relevance_score") or 0.5),
                    "metadata": {
                        "provider": row.get("provider"),
                        "timestamp": row.get("timestamp"),
                        "memory_id": row.get("id") or row.get("message_id"),
                    },
                }
            )

        return normalized

    async def _query_shared(
        self,
        query: str,
        limit: int,
        agent_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        try:
            rows = self.search_fts(query, limit=limit)
        except (RuntimeError, ValueError, TypeError, OSError, AttributeError, KeyError):
            logger.debug("Shared knowledge query failed", exc_info=True)
            return []

        results: List[Dict[str, Any]] = []
        for row in rows:
            rank = row.get("rank")
            if agent_id and row.get("id") is not None:
                try:
                    self.log_access(int(row["id"]), agent_id=agent_id, query=query, relevance=rank)
                except (RuntimeError, ValueError, TypeError, OSError, AttributeError, KeyError):
                    logger.debug("Failed to log shared knowledge access", exc_info=True)

            results.append(
                {
                    "title": row.get("title", ""),
                    "content": row.get("content", ""),
                    "relevance": self._fts_to_relevance(rank),
                    "metadata": {
                        "entry_id": row.get("id"),
                        "agent_id": row.get("agent_id"),
                        "category": row.get("category"),
                        "confidence": row.get("confidence"),
                    },
                }
            )

        return results

    async def _query_notebooklm(self, query: str, limit: int) -> List[Dict[str, Any]]:
        del limit
        client = getattr(self, "_knowledge_client", None)
        if client is None or not hasattr(client, "query"):
            return []

        try:
            result = client.query(query)
            if inspect.isawaitable(result):
                result = await result
        except (RuntimeError, ValueError, TypeError, OSError, AttributeError, KeyError):
            logger.debug("NotebookLM query failed", exc_info=True)
            return []

        if not isinstance(result, dict):
            return []

        answer = result.get("answer")
        if not answer:
            return []

        return [
            {
                "title": f"NotebookLM: {query[:80]}",
                "content": answer,
                "relevance": 0.8,
                "metadata": {
                    "notebook_id": result.get("notebook_id"),
                    "references": result.get("references") or result.get("sources") or [],
                },
            }
        ]

    async def _query_obsidian(self, query: str, limit: int) -> List[Dict[str, Any]]:
        obsidian = getattr(self, "_obsidian_search", None)
        if obsidian is None or not hasattr(obsidian, "search"):
            return []

        try:
            rows = obsidian.search(query, limit=limit)
        except (RuntimeError, ValueError, TypeError, OSError, AttributeError, KeyError):
            logger.debug("Obsidian query failed", exc_info=True)
            return []

        results: List[Dict[str, Any]] = []
        for row in rows if isinstance(rows, list) else []:
            results.append(
                {
                    "title": row.get("title") or row.get("path") or row.get("file") or "Obsidian Note",
                    "content": row.get("snippet") or row.get("content") or row.get("excerpt") or "",
                    "relevance": float(row.get("score") or 0.5),
                    "metadata": {
                        "path": row.get("path") or row.get("file"),
                    },
                }
            )

        return results

    @staticmethod
    def _fts_to_relevance(rank: Any) -> float:
        try:
            value = float(rank)
        except (TypeError, ValueError):
            return 0.5

        if value <= 0:
            return 1.0
        return max(0.0, min(1.0, 1.0 / (1.0 + value)))
