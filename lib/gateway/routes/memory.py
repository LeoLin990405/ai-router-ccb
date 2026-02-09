"""Memory routes for gateway API."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

try:
    from fastapi import APIRouter, Depends, HTTPException, Query, Request
    from fastapi.responses import JSONResponse

    HAS_FASTAPI = True
except ImportError:  # pragma: no cover - optional FastAPI dependency
    HAS_FASTAPI = False

from ..error_handlers import raise_memory_unavailable
from ..models import CreateObservationRequest, UpdateConfigRequest, UpdateObservationRequest
from .memory_advanced import register_memory_advanced_routes

if HAS_FASTAPI:
    router = APIRouter()
else:  # pragma: no cover - API unavailable without FastAPI
    router = None


def get_memory_middleware(request: Request):
    return getattr(request.app.state, "memory_middleware", None)


if HAS_FASTAPI:
    @router.get("/api/memory/sessions")
    async def get_memory_sessions(
        limit: int = Query(20, ge=1, le=100),
        memory_middleware=Depends(get_memory_middleware),
    ):
        """Get recent memory sessions."""
        if not memory_middleware or not hasattr(memory_middleware, "memory"):
            raise_memory_unavailable()

        try:
            sessions = memory_middleware.memory.v2.list_sessions(limit=limit)
            return JSONResponse(content={"sessions": sessions})
        except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError) as e:
            raise HTTPException(status_code=500, detail=f"Failed to fetch sessions: {str(e)}")


    @router.get("/api/memory/sessions/{session_id}")
    async def get_session_context(
        session_id: str,
        window_size: int = Query(20, ge=1, le=100),
        memory_middleware=Depends(get_memory_middleware),
    ):
        """Get conversation context for a specific session."""
        if not memory_middleware or not hasattr(memory_middleware, "memory"):
            raise_memory_unavailable()

        try:
            messages = memory_middleware.memory.v2.get_session_context(
                session_id=session_id,
                window_size=window_size,
            )
            return JSONResponse(content={"session_id": session_id, "messages": messages})
        except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError) as e:
            raise HTTPException(status_code=500, detail=f"Failed to fetch session context: {str(e)}")


    @router.get("/api/memory/search")
    async def search_memory(
        query: str = Query(..., min_length=1),
        limit: int = Query(10, ge=1, le=50),
        provider: Optional[str] = None,
        memory_middleware=Depends(get_memory_middleware),
    ):
        """Search memory messages using FTS5."""
        if not memory_middleware or not hasattr(memory_middleware, "memory"):
            raise_memory_unavailable()

        try:
            results = memory_middleware.memory.v2.search_messages(
                query=query,
                limit=limit,
                provider=provider,
            )
            return JSONResponse(content={"query": query, "results": results})
        except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError) as e:
            raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


    @router.get("/api/memory/stats")
    async def get_memory_stats(
        memory_middleware=Depends(get_memory_middleware),
    ):
        """Get memory system statistics."""
        if not memory_middleware or not hasattr(memory_middleware, "memory"):
            raise_memory_unavailable()

        try:
            stats = memory_middleware.memory.v2.get_stats()
            return JSONResponse(content=stats)
        except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError) as e:
            raise HTTPException(status_code=500, detail=f"Failed to fetch stats: {str(e)}")


    @router.get("/api/memory/request/{request_id}")
    async def get_request_memory(
        request_id: str,
        memory_middleware=Depends(get_memory_middleware),
    ):
        """Get injection details for a specific request (Phase 1: Transparency)."""
        if not memory_middleware or not hasattr(memory_middleware, "memory"):
            raise_memory_unavailable()

        try:
            injection = memory_middleware.memory.v2.get_request_injection(request_id)
            if not injection:
                raise HTTPException(status_code=404, detail=f"No injection record found for request {request_id}")

            memories = memory_middleware.memory.v2.get_injected_memories_for_request(request_id)

            return JSONResponse(
                content={
                    "request_id": request_id,
                    "injection": injection,
                    "injected_memories": memories,
                }
            )
        except HTTPException:
            raise
        except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError) as e:
            raise HTTPException(status_code=500, detail=f"Failed to fetch request memory: {str(e)}")


    @router.get("/api/memory/injections")
    async def get_recent_injections(
        limit: int = Query(20, ge=1, le=100),
        session_id: Optional[str] = None,
        memory_middleware=Depends(get_memory_middleware),
    ):
        """Get recent memory injections for debugging (Phase 1: Transparency)."""
        if not memory_middleware or not hasattr(memory_middleware, "memory"):
            raise_memory_unavailable()

        try:
            injections = memory_middleware.memory.v2.get_request_injections(
                limit=limit,
                session_id=session_id,
            )
            return JSONResponse(
                content={
                    "total": len(injections),
                    "injections": injections,
                }
            )
        except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError) as e:
            raise HTTPException(status_code=500, detail=f"Failed to fetch injections: {str(e)}")


    @router.post("/api/memory/add")
    async def create_observation(
        request: CreateObservationRequest,
        memory_middleware=Depends(get_memory_middleware),
    ):
        """Create a new observation (Phase 2: Write APIs)."""
        if not memory_middleware or not hasattr(memory_middleware, "memory"):
            raise_memory_unavailable()

        try:
            observation_id = memory_middleware.memory.v2.create_observation(
                content=request.content,
                category=request.category,
                tags=request.tags,
                source="manual",
                confidence=request.confidence,
            )
            return JSONResponse(
                content={
                    "observation_id": observation_id,
                    "message": "Observation created successfully",
                }
            )
        except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError) as e:
            raise HTTPException(status_code=500, detail=f"Failed to create observation: {str(e)}")


    @router.get("/api/memory/observations")
    async def list_observations(
        category: Optional[str] = None,
        query: Optional[str] = None,
        limit: int = Query(50, ge=1, le=200),
        memory_middleware=Depends(get_memory_middleware),
    ):
        """List observations with optional filtering."""
        if not memory_middleware or not hasattr(memory_middleware, "memory"):
            raise_memory_unavailable()

        try:
            observations = memory_middleware.memory.v2.search_observations(
                query=query,
                category=category,
                limit=limit,
            )
            return JSONResponse(content={"total": len(observations), "observations": observations})
        except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError) as e:
            raise HTTPException(status_code=500, detail=f"Failed to list observations: {str(e)}")


    @router.get("/api/memory/observations/{observation_id}")
    async def get_observation(
        observation_id: str,
        memory_middleware=Depends(get_memory_middleware),
    ):
        """Get a specific observation."""
        if not memory_middleware or not hasattr(memory_middleware, "memory"):
            raise_memory_unavailable()

        try:
            observation = memory_middleware.memory.v2.get_observation(observation_id)
            if not observation:
                raise HTTPException(status_code=404, detail=f"Observation {observation_id} not found")
            return JSONResponse(content=observation)
        except HTTPException:
            raise
        except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError) as e:
            raise HTTPException(status_code=500, detail=f"Failed to get observation: {str(e)}")


    @router.put("/api/memory/{observation_id}")
    async def update_observation(
        observation_id: str,
        request: UpdateObservationRequest,
        memory_middleware=Depends(get_memory_middleware),
    ):
        """Update an existing observation (Phase 2: Write APIs)."""
        if not memory_middleware or not hasattr(memory_middleware, "memory"):
            raise_memory_unavailable()

        try:
            success = memory_middleware.memory.v2.update_observation(
                observation_id=observation_id,
                content=request.content,
                category=request.category,
                tags=request.tags,
                confidence=request.confidence,
            )
            if not success:
                raise HTTPException(status_code=404, detail=f"Observation {observation_id} not found")
            return JSONResponse(
                content={
                    "observation_id": observation_id,
                    "message": "Observation updated successfully",
                }
            )
        except HTTPException:
            raise
        except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError) as e:
            raise HTTPException(status_code=500, detail=f"Failed to update observation: {str(e)}")


    @router.delete("/api/memory/{observation_id}")
    async def delete_observation(
        observation_id: str,
        memory_middleware=Depends(get_memory_middleware),
    ):
        """Delete an observation (Phase 2: Write APIs)."""
        if not memory_middleware or not hasattr(memory_middleware, "memory"):
            raise_memory_unavailable()

        try:
            success = memory_middleware.memory.v2.delete_observation(observation_id)
            if not success:
                raise HTTPException(status_code=404, detail=f"Observation {observation_id} not found")
            return JSONResponse(
                content={
                    "observation_id": observation_id,
                    "message": "Observation deleted successfully",
                }
            )
        except HTTPException:
            raise
        except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError) as e:
            raise HTTPException(status_code=500, detail=f"Failed to delete observation: {str(e)}")


    @router.get("/api/memory/config")
    async def get_memory_config_endpoint():
        """Get current memory system configuration (Phase 4)."""
        try:
            from lib.memory.memory_config import get_memory_config as load_memory_config

            config = load_memory_config()
            validation = config.validate()
            return JSONResponse(
                content={
                    "config": config.get_all(),
                    "valid": validation["valid"],
                    "errors": validation["errors"],
                }
            )
        except ImportError:
            raise HTTPException(status_code=503, detail="Memory config module not available")
        except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError) as e:
            raise HTTPException(status_code=500, detail=f"Failed to get config: {str(e)}")


    @router.post("/api/memory/config")
    async def update_memory_config(
        request: UpdateConfigRequest,
        memory_middleware=Depends(get_memory_middleware),
    ):
        """Update memory system configuration (Phase 4)."""
        try:
            from lib.memory.memory_config import get_memory_config as load_memory_config

            config = load_memory_config()

            updates = {}
            if request.enabled is not None:
                updates["enabled"] = request.enabled
            if request.auto_inject is not None:
                updates["auto_inject"] = request.auto_inject
            if request.max_injected_memories is not None:
                updates["max_injected_memories"] = request.max_injected_memories
            if request.injection_strategy is not None:
                updates["injection_strategy"] = request.injection_strategy
            if request.skills_auto_discover is not None:
                updates["skills.auto_discover"] = request.skills_auto_discover
            if request.skills_max_recommendations is not None:
                updates["skills.max_recommendations"] = request.skills_max_recommendations

            if not updates:
                raise HTTPException(status_code=400, detail="No updates provided")

            updated_config = config.update(updates)
            validation = config.validate()

            if memory_middleware:
                memory_middleware.config = config.get_all()
                memory_middleware.enabled = config.get("enabled", True)
                memory_middleware.auto_inject = config.get("auto_inject", True)
                memory_middleware.max_injected = config.get("max_injected_memories", 5)

            return JSONResponse(
                content={
                    "message": "Configuration updated",
                    "config": updated_config,
                    "valid": validation["valid"],
                    "errors": validation["errors"],
                }
            )
        except HTTPException:
            raise
        except ImportError:
            raise HTTPException(status_code=503, detail="Memory config module not available")
        except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError) as e:
            raise HTTPException(status_code=500, detail=f"Failed to update config: {str(e)}")


    @router.post("/api/memory/config/reset")
    async def reset_memory_config():
        """Reset memory configuration to defaults (Phase 4)."""
        try:
            from lib.memory.memory_config import get_memory_config as load_memory_config

            config = load_memory_config()
            default_config = config.reset()
            return JSONResponse(
                content={
                    "message": "Configuration reset to defaults",
                    "config": default_config,
                }
            )
        except ImportError:
            raise HTTPException(status_code=503, detail="Memory config module not available")
        except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError) as e:
            raise HTTPException(status_code=500, detail=f"Failed to reset config: {str(e)}")


_memory_advanced_funcs = register_memory_advanced_routes(
    router=router,
    get_memory_middleware=get_memory_middleware,
)
globals().update(_memory_advanced_funcs)
