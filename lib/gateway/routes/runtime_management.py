"""Management and listing routes for runtime API."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

try:
    from fastapi import Depends, HTTPException, Query

    HAS_FASTAPI = True
except ImportError:  # pragma: no cover - optional FastAPI dependency
    HAS_FASTAPI = False

from ..error_handlers import raise_request_not_found, raise_stream_not_found
from ..models import RequestStatus


def register_runtime_management_routes(*, router, get_config, get_store, get_queue) -> Dict[str, Any]:
    """Attach runtime management endpoints to a shared router."""
    if not HAS_FASTAPI or router is None:  # pragma: no cover - FastAPI unavailable
        return {}

    @router.get("/api/requests")
    async def list_requests(
        status: Optional[str] = None,
        provider: Optional[str] = None,
        limit: int = Query(50, le=100),
        offset: int = Query(0, ge=0),
        order_by: str = Query("created_at", description="Field to order by: created_at, updated_at, priority"),
        order_desc: bool = Query(True, description="Order descending if true"),
        store=Depends(get_store),
    ) -> List[Dict[str, Any]]:
        """List requests with optional filtering."""
        status_enum = RequestStatus(status) if status else None
        requests = store.list_requests(
            status=status_enum,
            provider=provider,
            limit=limit,
            offset=offset,
            order_by=order_by,
            order_desc=order_desc,
        )
        return [request.to_dict() for request in requests]

    @router.get("/api/queue")
    async def get_queue_status(
        queue=Depends(get_queue),
    ) -> Dict[str, Any]:
        """Get detailed queue status."""
        return queue.stats()

    @router.get("/api/providers")
    async def list_providers(
        config=Depends(get_config),
    ) -> List[Dict[str, Any]]:
        """List all configured providers."""
        providers = []
        for name, pconfig in config.providers.items():
            providers.append(
                {
                    "name": name,
                    "backend_type": pconfig.backend_type.value,
                    "enabled": pconfig.enabled,
                    "priority": pconfig.priority,
                    "timeout_s": pconfig.timeout_s,
                    "supports_streaming": pconfig.supports_streaming,
                }
            )
        return providers

    @router.get("/api/provider-groups")
    async def list_provider_groups(
        config=Depends(get_config),
    ) -> Dict[str, List[str]]:
        """List all configured provider groups for parallel queries."""
        return config.parallel.provider_groups

    @router.get("/api/stream/{request_id}")
    async def get_stream_output(
        request_id: str,
        from_line: int = Query(0, ge=0, description="Start reading from this line"),
    ) -> Dict[str, Any]:
        """Get stream output for a request."""
        from ..stream_output import get_stream_manager as get_runtime_stream_manager

        stream_manager = get_runtime_stream_manager()

        status = stream_manager.get_stream_status(request_id)
        if not status.get("exists"):
            raise_stream_not_found()

        entries = stream_manager.read_stream(request_id, from_line)
        return {
            "request_id": request_id,
            "status": status,
            "from_line": from_line,
            "entries": entries,
            "entry_count": len(entries),
            "next_line": from_line + len(entries),
        }

    @router.get("/api/stream/{request_id}/tail")
    async def tail_stream(
        request_id: str,
        lines: int = Query(20, ge=1, le=100, description="Number of lines to return"),
    ) -> Dict[str, Any]:
        """Get the last N entries from a stream."""
        from ..stream_output import get_stream_manager as get_runtime_stream_manager

        stream_manager = get_runtime_stream_manager()

        status = stream_manager.get_stream_status(request_id)
        if not status.get("exists"):
            raise_stream_not_found()

        all_entries = stream_manager.read_stream(request_id)
        tail_entries = all_entries[-lines:] if len(all_entries) > lines else all_entries

        return {
            "request_id": request_id,
            "status": status,
            "total_entries": len(all_entries),
            "entries": tail_entries,
        }

    @router.get("/api/streams")
    async def list_streams(
        limit: int = Query(20, ge=1, le=100),
    ) -> Dict[str, Any]:
        """List recent stream logs."""
        from ..stream_output import get_stream_manager as get_runtime_stream_manager

        stream_manager = get_runtime_stream_manager()

        streams = stream_manager.list_recent_streams(limit)
        return {
            "streams": streams,
            "count": len(streams),
        }

    @router.delete("/api/streams/cleanup")
    async def cleanup_streams() -> Dict[str, Any]:
        """Clean up old stream logs."""
        from ..stream_output import get_stream_manager as get_runtime_stream_manager

        stream_manager = get_runtime_stream_manager()

        removed = stream_manager.cleanup_old_streams()
        return {
            "removed": removed,
            "status": "ok",
        }

    @router.post("/api/requests/cleanup")
    async def cleanup_requests(
        max_age_hours: int = Query(24, description="Remove requests older than this many hours"),
        store=Depends(get_store),
    ) -> Dict[str, Any]:
        """Remove old requests and their responses."""
        removed = store.cleanup_old_requests(max_age_hours)
        return {
            "removed": removed,
            "max_age_hours": max_age_hours,
        }

    @router.delete("/api/requests/{request_id}")
    async def delete_request(
        request_id: str,
        store=Depends(get_store),
    ) -> Dict[str, Any]:
        """Delete a specific request and its response."""
        request = store.get_request(request_id)
        if not request:
            raise_request_not_found()

        with store._get_connection() as conn:
            conn.execute("DELETE FROM responses WHERE request_id = ?", (request_id,))
            conn.execute("DELETE FROM requests WHERE id = ?", (request_id,))

        return {"deleted": True, "request_id": request_id}

    @router.get("/api/results")
    async def get_latest_results(
        provider: Optional[str] = Query(None, description="Filter by provider"),
        limit: int = Query(10, le=50, description="Maximum results to return"),
        include_discussions: bool = Query(True, description="Include discussion summaries"),
        store=Depends(get_store),
    ) -> List[Dict[str, Any]]:
        """Get latest results from requests and discussions."""
        return store.get_latest_results(
            provider=provider,
            limit=limit,
            include_discussions=include_discussions,
        )

    @router.get("/api/results/{result_id}")
    async def get_result_by_id(
        result_id: str,
        store=Depends(get_store),
    ) -> Dict[str, Any]:
        """Get a specific result by ID."""
        result = store.get_result_by_id(result_id)
        if not result:
            raise HTTPException(status_code=404, detail="Result not found")
        return result

    @router.get("/api/results/provider/{provider_name}")
    async def get_provider_results(
        provider_name: str,
        limit: int = Query(10, le=50),
        store=Depends(get_store),
    ) -> List[Dict[str, Any]]:
        """Get latest results from a specific provider."""
        return store.get_latest_results(
            provider=provider_name,
            limit=limit,
            include_discussions=False,
        )

    return {
        "list_requests": list_requests,
        "get_queue_status": get_queue_status,
        "list_providers": list_providers,
        "list_provider_groups": list_provider_groups,
        "get_stream_output": get_stream_output,
        "tail_stream": tail_stream,
        "list_streams": list_streams,
        "cleanup_streams": cleanup_streams,
        "cleanup_requests": cleanup_requests,
        "delete_request": delete_request,
        "get_latest_results": get_latest_results,
        "get_result_by_id": get_result_by_id,
        "get_provider_results": get_provider_results,
    }
