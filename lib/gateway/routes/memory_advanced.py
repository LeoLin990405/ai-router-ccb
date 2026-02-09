"""Advanced memory and stream-introspection routes."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

try:
    from fastapi import Depends, HTTPException, Query
    from fastapi.responses import JSONResponse

    HAS_FASTAPI = True
except ImportError:  # pragma: no cover - optional FastAPI dependency
    HAS_FASTAPI = False

from ..error_handlers import (
    raise_consolidator_unavailable,
    raise_memory_module_unavailable,
    raise_memory_unavailable,
)


def register_memory_advanced_routes(*, router, get_memory_middleware):
    """Attach advanced memory endpoints to the shared memory router."""
    if not HAS_FASTAPI or router is None:  # pragma: no cover
        return {}

    @router.get("/api/memory/consolidated")
    async def get_consolidated_memories(
        days: int = Query(30, ge=1, le=365),
        limit: int = Query(20, ge=1, le=100),
    ):
        """Get consolidated memories from System 2."""
        try:
            from lib.memory.consolidator import NightlyConsolidator

            consolidator = NightlyConsolidator()
            memories = consolidator.get_consolidated_memories(days=days, limit=limit)
            return JSONResponse(content={"memories": memories, "total": len(memories), "days": days})
        except ImportError:
            raise_consolidator_unavailable()
        except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError) as exc:
            raise HTTPException(status_code=500, detail=f"Failed to get consolidated memories: {str(exc)}")

    @router.post("/api/memory/consolidate")
    async def trigger_consolidation(
        hours: int = Query(24, ge=1, le=168),
        llm_enhanced: bool = Query(True),
    ):
        """Trigger System 2 consolidation."""
        try:
            from lib.memory.consolidator import NightlyConsolidator

            consolidator = NightlyConsolidator()
            if llm_enhanced:
                result = await consolidator.consolidate_with_llm(hours=hours)
            else:
                result = consolidator.consolidate(hours=hours)

            return JSONResponse(
                content={
                    "message": "Consolidation completed",
                    "result": result,
                    "llm_enhanced": llm_enhanced,
                    "hours_processed": hours,
                }
            )
        except ImportError:
            raise_consolidator_unavailable()
        except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError) as exc:
            raise HTTPException(status_code=500, detail=f"Consolidation failed: {str(exc)}")

    @router.post("/api/memory/decay")
    async def apply_memory_decay(
        batch_size: int = Query(1000, ge=100, le=10000),
    ):
        """Apply Ebbinghaus decay to tracked memories."""
        try:
            from lib.memory.consolidator import NightlyConsolidator

            consolidator = NightlyConsolidator()
            stats = consolidator.apply_decay_to_all(batch_size=batch_size)
            return JSONResponse(content={"message": "Decay applied successfully", "stats": stats})
        except ImportError:
            raise_consolidator_unavailable()
        except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError) as exc:
            raise HTTPException(status_code=500, detail=f"Decay application failed: {str(exc)}")

    @router.post("/api/memory/merge")
    async def merge_similar_memories(
        similarity_threshold: float = Query(0.9, ge=0.5, le=1.0),
    ):
        """Merge memories with high similarity."""
        try:
            from lib.memory.consolidator import NightlyConsolidator

            consolidator = NightlyConsolidator()
            stats = await consolidator.merge_similar_memories(similarity_threshold=similarity_threshold)
            return JSONResponse(content={"message": "Merge completed", "stats": stats, "threshold": similarity_threshold})
        except ImportError:
            raise_consolidator_unavailable()
        except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError) as exc:
            raise HTTPException(status_code=500, detail=f"Merge failed: {str(exc)}")

    @router.post("/api/memory/forget")
    async def forget_expired_memories(
        max_age_days: int = Query(90, ge=7, le=365),
    ):
        """Clean up expired memories."""
        try:
            from lib.memory.consolidator import NightlyConsolidator

            consolidator = NightlyConsolidator()
            stats = consolidator.forget_expired_memories(max_age_days=max_age_days)
            return JSONResponse(
                content={
                    "message": "Forget operation completed",
                    "stats": stats,
                    "max_age_days": max_age_days,
                }
            )
        except ImportError:
            raise_consolidator_unavailable()
        except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError) as exc:
            raise HTTPException(status_code=500, detail=f"Forget operation failed: {str(exc)}")

    @router.get("/api/memory/consolidation/stats")
    async def get_consolidation_stats():
        """Get consolidation statistics."""
        try:
            from lib.memory.consolidator import NightlyConsolidator

            consolidator = NightlyConsolidator()
            stats = consolidator.get_consolidation_stats()
            return JSONResponse(content=stats)
        except ImportError:
            raise_consolidator_unavailable()
        except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError) as exc:
            raise HTTPException(status_code=500, detail=f"Failed to get stats: {str(exc)}")

    @router.get("/api/memory/heuristic/config")
    async def get_heuristic_config():
        """Get heuristic retrieval configuration."""
        try:
            from lib.memory.heuristic_retriever import RetrievalConfig

            config = RetrievalConfig.from_file()
            return JSONResponse(
                content={
                    "retrieval": {
                        "alpha": config.alpha,
                        "beta": config.beta,
                        "gamma": config.gamma,
                        "candidate_pool_size": config.candidate_pool_size,
                        "final_limit": config.final_limit,
                        "min_relevance_threshold": config.min_relevance_threshold,
                    },
                    "decay": {
                        "lambda": config.decay_lambda,
                        "min_score": config.min_recency,
                    },
                    "importance": {
                        "default_score": config.default_importance,
                        "access_boost": config.access_boost,
                    },
                }
            )
        except ImportError:
            raise HTTPException(status_code=503, detail="Heuristic retriever not available")
        except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError) as exc:
            raise HTTPException(status_code=500, detail=f"Failed to get config: {str(exc)}")

    @router.post("/api/memory/heuristic/config")
    async def update_heuristic_config(
        alpha: Optional[float] = Query(None, ge=0.0, le=1.0),
        beta: Optional[float] = Query(None, ge=0.0, le=1.0),
        gamma: Optional[float] = Query(None, ge=0.0, le=1.0),
        decay_lambda: Optional[float] = Query(None, ge=0.01, le=1.0),
        default_importance: Optional[float] = Query(None, ge=0.0, le=1.0),
    ):
        """Update heuristic retrieval configuration."""
        try:
            config_path = Path.home() / ".ccb" / "heuristic_config.json"

            if config_path.exists():
                config = json.loads(config_path.read_text(encoding="utf-8"))
            else:
                config = {
                    "retrieval": {
                        "relevance_weight": 0.4,
                        "importance_weight": 0.3,
                        "recency_weight": 0.3,
                    },
                    "decay": {"lambda": 0.1, "min_score": 0.01},
                    "importance": {"default_score": 0.5, "access_boost_amount": 0.01},
                }

            config.setdefault("retrieval", {})
            config.setdefault("decay", {})
            config.setdefault("importance", {})

            if alpha is not None:
                config["retrieval"]["relevance_weight"] = alpha
            if beta is not None:
                config["retrieval"]["importance_weight"] = beta
            if gamma is not None:
                config["retrieval"]["recency_weight"] = gamma
            if decay_lambda is not None:
                config["decay"]["lambda"] = decay_lambda
            if default_importance is not None:
                config["importance"]["default_score"] = default_importance

            config_path.parent.mkdir(parents=True, exist_ok=True)
            config_path.write_text(json.dumps(config, indent=2), encoding="utf-8")

            return JSONResponse(content={"message": "Configuration updated", "config": config})
        except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError) as exc:
            raise HTTPException(status_code=500, detail=f"Failed to update config: {str(exc)}")

    @router.get("/api/memory/stats/detailed")
    async def get_detailed_memory_stats(
        memory_middleware=Depends(get_memory_middleware),
    ):
        """Get detailed memory statistics with distributions."""
        try:
            from lib.memory.heuristic_retriever import HeuristicRetriever

            retriever = HeuristicRetriever()
            heuristic_stats = retriever.get_statistics()

            if memory_middleware and hasattr(memory_middleware, "memory"):
                basic_stats = memory_middleware.memory.v2.get_stats()
            else:
                basic_stats = {}

            return JSONResponse(
                content={
                    "basic": basic_stats,
                    "heuristic": heuristic_stats,
                    "retrieval": {
                        "config": heuristic_stats.get("config", {}),
                        "importance_distribution": heuristic_stats.get("importance_distribution", {}),
                        "total_accesses": heuristic_stats.get("total_accesses", 0),
                        "accesses_24h": heuristic_stats.get("accesses_24h", 0),
                    },
                }
            )
        except ImportError:
            if memory_middleware and hasattr(memory_middleware, "memory"):
                basic_stats = memory_middleware.memory.v2.get_stats()
                return JSONResponse(content={"basic": basic_stats, "heuristic": None, "retrieval": None})
            raise_memory_unavailable()
        except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError) as exc:
            raise HTTPException(status_code=500, detail=f"Failed to get stats: {str(exc)}")

    @router.get("/api/memory/stats/health")
    async def get_memory_health():
        """Get memory system health metrics."""
        try:
            from lib.memory.consolidator import NightlyConsolidator
            from lib.memory.heuristic_retriever import HeuristicRetriever

            retriever = HeuristicRetriever()
            consolidator = NightlyConsolidator()

            heuristic_stats = retriever.get_statistics()
            consolidation_stats = consolidator.get_consolidation_stats()

            importance_dist = heuristic_stats.get("importance_distribution", {})
            total_tracked = heuristic_stats.get("tracked_memories", 0)

            health = {
                "overall_score": 0.0,
                "importance_health": {
                    "high": importance_dist.get("high", 0),
                    "medium": importance_dist.get("medium", 0),
                    "low": importance_dist.get("low", 0),
                    "distribution_healthy": True,
                },
                "access_health": {
                    "total_accesses": heuristic_stats.get("total_accesses", 0),
                    "recent_accesses_24h": heuristic_stats.get("accesses_24h", 0),
                    "avg_access_count": heuristic_stats.get("avg_access_count", 0),
                },
                "consolidation_health": {
                    "total_consolidations": consolidation_stats.get("total_consolidations", 0),
                    "recent_7d": consolidation_stats.get("recent_7d", 0),
                    "last_consolidation": consolidation_stats.get("last_consolidation"),
                },
                "total_tracked_memories": total_tracked,
            }

            score = 50
            if total_tracked > 0:
                high_ratio = importance_dist.get("high", 0) / max(total_tracked, 1)
                if high_ratio > 0.1:
                    score += 20
                if heuristic_stats.get("accesses_24h", 0) > 0:
                    score += 15
                if consolidation_stats.get("recent_7d", 0) > 0:
                    score += 15

            health["overall_score"] = min(100, score)
            return JSONResponse(content=health)
        except ImportError:
            return JSONResponse(
                content={
                    "overall_score": 0,
                    "error": "Heuristic retriever or consolidator not available",
                    "importance_health": None,
                    "access_health": None,
                    "consolidation_health": None,
                }
            )
        except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError) as exc:
            raise HTTPException(status_code=500, detail=f"Failed to get health: {str(exc)}")

    @router.get("/api/stream/{request_id}/db")
    async def get_stream_from_db(
        request_id: str,
        entry_type: Optional[str] = None,
        limit: int = 1000,
    ):
        """Get stream entries from database."""
        try:
            from lib.memory.memory_v2 import CCBMemoryV2

            memory = CCBMemoryV2()
            entries = memory.get_stream_entries(request_id, entry_type=entry_type, limit=limit)
            return JSONResponse(
                content={
                    "request_id": request_id,
                    "entries": entries,
                    "count": len(entries),
                    "source": "database",
                }
            )
        except ImportError:
            raise_memory_module_unavailable()
        except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError) as exc:
            raise HTTPException(status_code=500, detail=f"Failed to get stream entries: {str(exc)}")

    @router.get("/api/thinking/{request_id}")
    async def get_thinking_chain(request_id: str):
        """Get thinking chain content for a request."""
        try:
            from lib.memory.memory_v2 import CCBMemoryV2

            memory = CCBMemoryV2()
            thinking = memory.get_thinking_chain(request_id)
            if thinking is None:
                return JSONResponse(content={"request_id": request_id, "thinking": None, "found": False})
            return JSONResponse(
                content={
                    "request_id": request_id,
                    "thinking": thinking,
                    "found": True,
                    "length": len(thinking),
                }
            )
        except ImportError:
            raise_memory_module_unavailable()
        except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError) as exc:
            raise HTTPException(status_code=500, detail=f"Failed to get thinking chain: {str(exc)}")

    @router.get("/api/memory/thinking/search")
    async def search_thinking_chains(
        query: str = Query(..., min_length=1),
        limit: int = 10,
    ):
        """Search thinking chain content across all requests."""
        try:
            from lib.memory.memory_v2 import CCBMemoryV2

            memory = CCBMemoryV2()
            results = memory.search_thinking(query, limit=limit)
            return JSONResponse(content={"query": query, "results": results, "count": len(results)})
        except ImportError:
            raise_memory_module_unavailable()
        except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError) as exc:
            raise HTTPException(status_code=500, detail=f"Search failed: {str(exc)}")

    @router.get("/api/timeline/{request_id}")
    async def get_request_timeline(request_id: str):
        """Get complete execution timeline for a request."""
        try:
            from lib.memory.memory_v2 import CCBMemoryV2

            memory = CCBMemoryV2()
            timeline = memory.get_request_timeline(request_id)
            return JSONResponse(content={"request_id": request_id, "timeline": timeline, "entry_count": len(timeline)})
        except ImportError:
            raise_memory_module_unavailable()
        except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError) as exc:
            raise HTTPException(status_code=500, detail=f"Failed to get timeline: {str(exc)}")

    @router.get("/api/memory/streams/stats")
    async def get_stream_stats():
        """Get statistics about stream entries in database."""
        try:
            from lib.memory.memory_v2 import CCBMemoryV2

            memory = CCBMemoryV2()
            stats = memory.get_stream_stats()
            return JSONResponse(content=stats)
        except ImportError:
            raise_memory_module_unavailable()
        except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError) as exc:
            raise HTTPException(status_code=500, detail=f"Failed to get stream stats: {str(exc)}")

    @router.post("/api/memory/streams/sync")
    async def sync_streams(force: bool = False):
        """Sync stream files to database."""
        try:
            from lib.memory.memory_v2 import CCBMemoryV2

            memory = CCBMemoryV2()
            stats = memory.sync_all_streams(force=force)
            return JSONResponse(content={"message": "Stream sync completed", "stats": stats})
        except ImportError:
            raise_memory_module_unavailable()
        except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError) as exc:
            raise HTTPException(status_code=500, detail=f"Sync failed: {str(exc)}")

    return {
        "get_consolidated_memories": get_consolidated_memories,
        "trigger_consolidation": trigger_consolidation,
        "apply_memory_decay": apply_memory_decay,
        "merge_similar_memories": merge_similar_memories,
        "forget_expired_memories": forget_expired_memories,
        "get_consolidation_stats": get_consolidation_stats,
        "get_heuristic_config": get_heuristic_config,
        "update_heuristic_config": update_heuristic_config,
        "get_detailed_memory_stats": get_detailed_memory_stats,
        "get_memory_health": get_memory_health,
        "get_stream_from_db": get_stream_from_db,
        "get_thinking_chain": get_thinking_chain,
        "search_thinking_chains": search_thinking_chains,
        "get_request_timeline": get_request_timeline,
        "get_stream_stats": get_stream_stats,
        "sync_streams": sync_streams,
    }
