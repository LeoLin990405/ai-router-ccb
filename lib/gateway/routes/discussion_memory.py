"""Discussion memory routes for gateway API."""
from __future__ import annotations

try:
    from fastapi import Depends, HTTPException, Query
    from fastapi.responses import JSONResponse

    HAS_FASTAPI = True
except ImportError:  # pragma: no cover - optional FastAPI dependency
    HAS_FASTAPI = False

from ..error_handlers import raise_memory_unavailable
from ..models import SaveDiscussionMemoryRequest


def register_discussion_memory_routes(*, router, get_store, get_memory_middleware):
    """Attach discussion-memory endpoints to the shared discussion router."""
    if not HAS_FASTAPI or router is None:  # pragma: no cover
        return {}

    @router.post("/api/discussion/{session_id}/save-to-memory")
    async def save_discussion_to_memory(
        session_id: str,
        request: SaveDiscussionMemoryRequest = None,
        store=Depends(get_store),
        memory_middleware=Depends(get_memory_middleware),
    ):
        """Save a discussion to memory system."""
        if not memory_middleware:
            raise HTTPException(status_code=503, detail="Memory middleware not available")

        try:
            session = store.get_discussion_session(session_id)
            if not session:
                raise HTTPException(status_code=404, detail=f"Discussion {session_id} not found")

            messages = None
            if request and request.include_messages:
                messages_list = store.get_discussion_messages(session_id)
                messages = [
                    {
                        "provider": message.provider,
                        "content": message.content,
                        "round": message.round_number,
                        "message_type": message.message_type.value,
                    }
                    for message in messages_list
                    if message.content
                ]

            observation_id = await memory_middleware.post_discussion(
                session_id=session_id,
                topic=session.topic,
                providers=session.providers,
                summary=request.summary if request else session.summary,
                insights=request.insights if request else None,
                messages=messages,
            )

            if not observation_id:
                raise HTTPException(status_code=500, detail="Failed to save discussion to memory")

            return JSONResponse(
                content={
                    "session_id": session_id,
                    "observation_id": observation_id,
                    "message": "Discussion saved to memory successfully",
                }
            )

        except HTTPException:
            raise
        except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError) as exc:
            raise HTTPException(status_code=500, detail=f"Failed to save discussion: {str(exc)}")

    @router.get("/api/memory/discussions")
    async def get_discussion_memories(
        limit: int = Query(10, ge=1, le=50),
        memory_middleware=Depends(get_memory_middleware),
    ):
        """Get discussions saved to memory."""
        if not memory_middleware or not hasattr(memory_middleware, "memory"):
            raise_memory_unavailable()

        try:
            discussions = memory_middleware.memory.v2.get_discussion_memory(limit=limit)
            return JSONResponse(
                content={
                    "total": len(discussions),
                    "discussions": discussions,
                }
            )
        except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError) as exc:
            raise HTTPException(status_code=500, detail=f"Failed to get discussions: {str(exc)}")

    return {
        "save_discussion_to_memory": save_discussion_to_memory,
        "get_discussion_memories": get_discussion_memories,
    }

