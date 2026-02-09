"""Shared Knowledge API routes."""
from __future__ import annotations

from typing import Any, Dict, Optional

try:
    from fastapi import APIRouter, Body, HTTPException, Query, Request
    from fastapi.responses import JSONResponse

    HAS_FASTAPI = True
except ImportError:  # pragma: no cover - optional FastAPI dependency
    HAS_FASTAPI = False

if HAS_FASTAPI:
    router = APIRouter()
else:  # pragma: no cover
    router = None


if HAS_FASTAPI:
    def _get_service(request: Request):
        service = getattr(request.app.state, "shared_knowledge", None)
        if service is None:
            raise HTTPException(status_code=503, detail="SharedKnowledgeService unavailable")
        return service


    @router.post("/api/shared-knowledge/publish")
    async def publish_knowledge(
        request: Request,
        body: Dict[str, Any] = Body(...),
    ):
        """Publish a knowledge entry."""
        service = _get_service(request)
        required = ["agent_id", "category", "title", "content"]
        missing = [field for field in required if not body.get(field)]
        if missing:
            raise HTTPException(status_code=400, detail=f"Missing required fields: {missing}")

        try:
            entry_id = service.publish(
                agent_id=str(body["agent_id"]),
                category=str(body["category"]),
                title=str(body["title"]),
                content=str(body["content"]),
                tags=body.get("tags"),
                source_request_id=body.get("source_request_id"),
                metadata=body.get("metadata"),
            )
            return JSONResponse(content={"id": entry_id, "status": "published"})
        except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError) as exc:
            raise HTTPException(status_code=500, detail=f"Failed to publish knowledge: {exc}")


    @router.get("/api/shared-knowledge/query")
    async def query_knowledge_unified(
        request: Request,
        q: str = Query(..., min_length=1, description="Search query"),
        sources: Optional[str] = Query(None, description="Comma-separated: memory,shared,notebooklm,obsidian"),
        limit: int = Query(10, ge=1, le=50),
        agent_id: Optional[str] = Query(None),
    ):
        """Unified query across memory/shared/notebook/obsidian."""
        service = _get_service(request)
        source_list = [part.strip() for part in sources.split(",") if part.strip()] if sources else None
        try:
            result = await service.unified_query(
                query=q,
                sources=source_list,
                limit=limit,
                agent_id=agent_id,
            )
            return JSONResponse(content=result)
        except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError) as exc:
            raise HTTPException(status_code=500, detail=f"Failed to query knowledge: {exc}")


    @router.post("/api/shared-knowledge/vote")
    async def vote_knowledge(
        request: Request,
        body: Dict[str, Any] = Body(...),
    ):
        """Vote on a knowledge entry."""
        service = _get_service(request)
        required = ["knowledge_id", "agent_id", "vote"]
        missing = [field for field in required if body.get(field) in (None, "")]
        if missing:
            raise HTTPException(status_code=400, detail=f"Missing required fields: {missing}")

        try:
            result = service.vote(
                knowledge_id=int(body["knowledge_id"]),
                agent_id=str(body["agent_id"]),
                vote=str(body["vote"]),
                comment=body.get("comment"),
            )
            return JSONResponse(content=result)
        except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError) as exc:
            raise HTTPException(status_code=500, detail=f"Failed to vote knowledge: {exc}")


    @router.get("/api/shared-knowledge/feed")
    async def knowledge_feed(
        request: Request,
        category: Optional[str] = Query(None),
        agent_id: Optional[str] = Query(None),
        limit: int = Query(20, ge=1, le=100),
        offset: int = Query(0, ge=0),
    ):
        """Browse shared knowledge entries with optional filters."""
        service = _get_service(request)
        try:
            entries = service.list_entries(
                category=category,
                agent_id=agent_id,
                limit=limit,
                offset=offset,
            )
            return JSONResponse(content={"entries": entries, "count": len(entries)})
        except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError) as exc:
            raise HTTPException(status_code=500, detail=f"Failed to fetch feed: {exc}")


    @router.get("/api/shared-knowledge/agent/{agent_id}")
    async def get_agent_info(request: Request, agent_id: str):
        """Get agent profile and recent contributions."""
        service = _get_service(request)
        try:
            agent = service.get_agent(agent_id)
            if not agent:
                raise HTTPException(status_code=404, detail="Agent not found")
            entries = service.list_entries(agent_id=agent_id, limit=10)
            return JSONResponse(content={"agent": agent, "recent_entries": entries})
        except HTTPException:
            raise
        except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError) as exc:
            raise HTTPException(status_code=500, detail=f"Failed to fetch agent info: {exc}")


    @router.get("/api/shared-knowledge/stats")
    async def shared_knowledge_stats(request: Request):
        """Get shared knowledge stats."""
        service = _get_service(request)
        try:
            return JSONResponse(content=service.get_shared_stats())
        except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError) as exc:
            raise HTTPException(status_code=500, detail=f"Failed to fetch stats: {exc}")


    @router.delete("/api/shared-knowledge/{entry_id}")
    async def delete_knowledge(request: Request, entry_id: int):
        """Delete a shared knowledge entry."""
        service = _get_service(request)
        try:
            deleted = service.delete_entry(entry_id)
            if not deleted:
                raise HTTPException(status_code=404, detail="Entry not found")
            return JSONResponse(content={"deleted": True, "id": entry_id})
        except HTTPException:
            raise
        except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError) as exc:
            raise HTTPException(status_code=500, detail=f"Failed to delete entry: {exc}")
