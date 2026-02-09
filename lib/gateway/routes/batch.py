"""Batch operation routes for gateway API."""
from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Tuple

try:
    from fastapi import APIRouter, Depends, Query, Request

    HAS_FASTAPI = True
except ImportError:  # pragma: no cover - optional FastAPI dependency
    HAS_FASTAPI = False

from ..models import (
    GatewayRequest,
    RequestStatus,
    BatchAskRequest,
    BatchCancelRequest,
    BatchStatusRequest,
    BatchReplyRequest,
)

if HAS_FASTAPI:
    router = APIRouter()
else:  # pragma: no cover - API unavailable without FastAPI
    router = None


def get_config(request: Request):
    return request.app.state.config


def get_store(request: Request):
    return request.app.state.store


def get_queue(request: Request):
    return request.app.state.queue


def get_router_func(request: Request):
    return getattr(request.app.state, "router_func", None)


def parse_provider_spec(config: Any, spec: str) -> Tuple[List[str], bool]:
    """Parse provider specification (single provider or @group)."""
    if spec.startswith("@"):
        providers = config.parallel.get_provider_group(spec)
        return providers, len(providers) > 1
    return [spec], False


if HAS_FASTAPI:
    @router.post("/ask")
    async def batch_ask(
        batch_request: BatchAskRequest,
        config=Depends(get_config),
        queue=Depends(get_queue),
        router_func: Optional[Callable[[str], Any]] = Depends(get_router_func),
    ) -> Dict[str, Any]:
        """
        Submit multiple requests in a single API call.

        Returns request IDs for all submitted requests.
        More efficient than multiple individual /api/ask calls.
        """
        results: List[Dict[str, Any]] = []
        errors: List[Dict[str, Any]] = []

        for i, req in enumerate(batch_request.requests):
            try:
                provider_spec = req.provider
                if not provider_spec:
                    if router_func:
                        decision = router_func(req.message)
                        provider_spec = decision.provider
                    else:
                        provider_spec = config.default_provider

                providers, is_parallel = parse_provider_spec(config, provider_spec)

                if not providers:
                    errors.append(
                        {
                            "index": i,
                            "error": f"Unknown provider: {provider_spec}",
                        }
                    )
                    continue

                invalid_providers = [p for p in providers if p not in config.providers]
                if invalid_providers:
                    errors.append(
                        {
                            "index": i,
                            "error": f"Unknown providers: {invalid_providers}",
                        }
                    )
                    continue

                gw_request = GatewayRequest.create(
                    provider=providers[0] if not is_parallel else provider_spec,
                    message=req.message,
                    priority=req.priority,
                    timeout_s=req.timeout_s,
                    metadata={
                        "parallel": is_parallel,
                        "providers": providers if is_parallel else None,
                        "aggregation_strategy": req.aggregation_strategy,
                        "agent": req.agent,
                        "batch_index": i,
                    },
                )

                if queue.enqueue(gw_request):
                    results.append(
                        {
                            "index": i,
                            "request_id": gw_request.id,
                            "provider": provider_spec,
                            "status": "queued",
                        }
                    )
                else:
                    errors.append(
                        {
                            "index": i,
                            "error": "Queue is full",
                        }
                    )

            except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError) as exc:
                errors.append(
                    {
                        "index": i,
                        "error": str(exc),
                    }
                )

        return {
            "submitted": len(results),
            "failed": len(errors),
            "total": len(batch_request.requests),
            "results": results,
            "errors": errors,
        }


    @router.post("/cancel")
    async def batch_cancel(
        batch_request: BatchCancelRequest,
        queue=Depends(get_queue),
    ) -> Dict[str, Any]:
        """
        Cancel multiple requests in a single API call.

        Returns status for each cancellation attempt.
        """
        results = []

        for request_id in batch_request.request_ids:
            success = queue.cancel(request_id)
            results.append(
                {
                    "request_id": request_id,
                    "cancelled": success,
                    "error": None if success else "Not found or already completed",
                }
            )

        cancelled_count = sum(1 for r in results if r["cancelled"])

        return {
            "cancelled": cancelled_count,
            "failed": len(results) - cancelled_count,
            "total": len(results),
            "results": results,
        }


    @router.post("/status")
    async def batch_status(
        batch_request: BatchStatusRequest,
        store=Depends(get_store),
    ) -> Dict[str, Any]:
        """
        Query status of multiple requests in a single API call.

        More efficient than multiple individual /api/reply calls.
        """
        results = []

        for request_id in batch_request.request_ids:
            request = store.get_request(request_id)

            if not request:
                results.append(
                    {
                        "request_id": request_id,
                        "found": False,
                        "status": None,
                        "response": None,
                        "error": "Request not found",
                    }
                )
                continue

            response = store.get_response(request_id)

            results.append(
                {
                    "request_id": request_id,
                    "found": True,
                    "status": request.status.value,
                    "provider": request.provider,
                    "response": response.response if response else None,
                    "error": response.error if response else None,
                    "latency_ms": response.latency_ms if response else None,
                    "created_at": request.created_at,
                    "completed_at": request.completed_at,
                }
            )

        found_count = sum(1 for r in results if r["found"])
        completed_count = sum(
            1
            for r in results
            if r["found"] and r["status"] in ("completed", "failed", "timeout")
        )

        return {
            "found": found_count,
            "not_found": len(results) - found_count,
            "completed": completed_count,
            "pending": found_count - completed_count,
            "total": len(results),
            "results": results,
        }


    @router.post("/reply")
    async def batch_reply(
        batch_request: BatchReplyRequest,
        store=Depends(get_store),
    ) -> Dict[str, Any]:
        """
        Fetch replies for multiple requests in a single API call.

        Similar to /api/reply but accepts multiple request IDs.
        """
        results = []

        for request_id in batch_request.request_ids:
            request = store.get_request(request_id)

            if not request:
                results.append(
                    {
                        "request_id": request_id,
                        "found": False,
                        "status": None,
                        "response": None,
                        "error": "Request not found",
                    }
                )
                continue

            response = store.get_response(request_id)

            results.append(
                {
                    "request_id": request_id,
                    "found": True,
                    "status": request.status.value,
                    "provider": request.provider,
                    "response": response.response if response else None,
                    "error": response.error if response else None,
                    "latency_ms": response.latency_ms if response else None,
                    "cached": response.metadata.get("cached", False)
                    if response and response.metadata
                    else False,
                    "retry_info": response.metadata.get("retry_info")
                    if response and response.metadata
                    else None,
                    "thinking": response.thinking if response else None,
                    "raw_output": response.raw_output if response else None,
                    "created_at": request.created_at,
                    "completed_at": request.completed_at,
                }
            )

        found_count = sum(1 for r in results if r["found"])
        completed_count = sum(
            1
            for r in results
            if r["found"] and r["status"] in ("completed", "failed", "timeout")
        )

        return {
            "found": found_count,
            "not_found": len(results) - found_count,
            "completed": completed_count,
            "pending": found_count - completed_count,
            "total": len(results),
            "results": results,
        }


    @router.get("/pending")
    async def get_batch_pending(
        batch_id: Optional[str] = Query(None, description="Filter by batch metadata"),
        limit: int = Query(100, le=500),
        store=Depends(get_store),
    ) -> Dict[str, Any]:
        """
        Get all pending requests, optionally filtered by batch metadata.
        """
        pending = store.list_requests(
            status=RequestStatus.QUEUED,
            limit=limit,
        )
        processing = store.list_requests(
            status=RequestStatus.PROCESSING,
            limit=limit,
        )

        all_pending = pending + processing

        if batch_id:
            all_pending = [
                r
                for r in all_pending
                if r.metadata and r.metadata.get("batch_id") == batch_id
            ]

        return {
            "count": len(all_pending),
            "requests": [
                {
                    "request_id": r.id,
                    "provider": r.provider,
                    "status": r.status.value,
                    "created_at": r.created_at,
                    "priority": r.priority,
                }
                for r in all_pending
            ],
        }
