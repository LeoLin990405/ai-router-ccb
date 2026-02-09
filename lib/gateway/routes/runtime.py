"""Runtime request, stream, and results routes for gateway API."""
from __future__ import annotations

import asyncio
import json
import time
from typing import Any, Dict, List, Optional

from lib.common.logging import get_logger

try:
    from fastapi import APIRouter, Depends, HTTPException, Query, Request
    from fastapi.responses import StreamingResponse

    HAS_FASTAPI = True
except ImportError:  # pragma: no cover - optional FastAPI dependency
    HAS_FASTAPI = False

from ..error_handlers import raise_request_not_found
from ..models import (
    AskRequest,
    AskResponse,
    GatewayRequest,
    GatewayResponse,
    ReplyResponse,
    RequestStatus,
    StatusResponse,
    WebSocketEvent,
)
from .runtime_management import register_runtime_management_routes

if HAS_FASTAPI:
    router = APIRouter()
else:  # pragma: no cover - API unavailable without FastAPI
    router = None


logger = get_logger("gateway.routes.runtime")


def get_config(request: Request):
    return request.app.state.config


def get_store(request: Request):
    return request.app.state.store


def get_queue(request: Request):
    return request.app.state.queue


def get_router_func(request: Request):
    return getattr(request.app.state, "router_func", None)


def get_cache_manager(request: Request):
    return getattr(request.app.state, "cache_manager", None)


def get_stream_manager(request: Request):
    return getattr(request.app.state, "stream_manager", None)


def get_backends(request: Request):
    return getattr(request.app.state, "backends", {})


def get_ws_manager(request: Request):
    return getattr(request.app.state, "ws_manager", None)


def get_start_time(request: Request):
    return getattr(request.app.state, "start_time", time.time())


def parse_provider_spec(config, spec: str) -> tuple[List[str], bool]:
    """Parse provider specification (single, @group, or @all)."""
    if spec.startswith("@"):
        providers = config.parallel.get_provider_group(spec)
        return providers, len(providers) > 1
    return [spec], False


if HAS_FASTAPI:
    @router.post("/api/ask")
    async def ask(
        request: AskRequest,
        wait: bool = Query(False, description="Wait for completion before returning"),
        timeout: float = Query(300.0, description="Wait timeout in seconds (only used when wait=true)"),
        config=Depends(get_config),
        store=Depends(get_store),
        queue=Depends(get_queue),
        router_func=Depends(get_router_func),
        cache_manager=Depends(get_cache_manager),
        ws_manager=Depends(get_ws_manager),
    ):
        """
        Submit a request to an AI provider.

        Supports:
        - Single provider: provider="claude"
        - Provider groups: provider="@all", "@fast", "@coding"
        - Auto-routing: provider=None (uses router or default)
        - Cache bypass: cache_bypass=True
        - Synchronous wait: wait=true&timeout=300 (waits for completion)

        When wait=true, returns full response inline instead of just request_id.
        This is useful for CLI tools that want synchronous behavior.
        """
        provider_spec = request.provider
        logger.debug(
            "Received /api/ask provider_spec=%s message_preview=%s",
            provider_spec,
            request.message[:50] if len(request.message) > 50 else request.message,
        )
        if not provider_spec:
            if router_func:
                decision = router_func(request.message)
                provider_spec = decision.provider
                logger.debug("Router selected provider=%s", provider_spec)
            else:
                provider_spec = config.default_provider
                logger.debug("Using default provider=%s", provider_spec)

        providers, is_parallel = parse_provider_spec(config, provider_spec)
        logger.debug("Parsed providers=%s parallel=%s", providers, is_parallel)

        if not providers:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown provider or group: {provider_spec}",
            )

        effective_timeout_s = request.timeout_s
        if not is_parallel:
            pconfig = config.providers.get(providers[0])
            if pconfig and pconfig.timeout_s and effective_timeout_s < pconfig.timeout_s:
                effective_timeout_s = pconfig.timeout_s

        logger.debug(
            "Cache check parallel=%s cache_manager=%s enabled=%s bypass=%s",
            is_parallel,
            cache_manager is not None,
            config.cache.enabled if hasattr(config, "cache") else "N/A",
            request.cache_bypass,
        )
        if not is_parallel and cache_manager and config.cache.enabled and not request.cache_bypass:
            cached = cache_manager.get(providers[0], request.message)
            logger.debug(
                "Cache lookup provider=%s message_hash=%s hit=%s",
                providers[0],
                hash(request.message),
                cached is not None,
            )
            if cached:
                logger.debug("Cache hit; returning cached response")
                gw_request = GatewayRequest.create(
                    provider=providers[0],
                    message=request.message,
                    priority=request.priority,
                    timeout_s=effective_timeout_s,
                    metadata={"cached": True, "cache_key": cached.cache_key},
                )
                store.create_request(gw_request)
                store.update_request_status(gw_request.id, RequestStatus.COMPLETED)
                store.save_response(
                    GatewayResponse(
                        request_id=gw_request.id,
                        status=RequestStatus.COMPLETED,
                        response=cached.response,
                        provider=providers[0],
                        latency_ms=0.0,
                        tokens_used=cached.tokens_used,
                        metadata={"cached": True},
                    )
                )

                if wait:
                    return {
                        "request_id": gw_request.id,
                        "provider": providers[0],
                        "status": "completed",
                        "cached": True,
                        "parallel": False,
                        "response": cached.response,
                        "error": None,
                        "latency_ms": 0.0,
                    }

                return AskResponse(
                    request_id=gw_request.id,
                    provider=providers[0],
                    status="completed",
                    cached=True,
                    parallel=False,
                )

        for provider_name in providers:
            if provider_name not in config.providers:
                raise HTTPException(
                    status_code=400,
                    detail=f"Unknown provider: {provider_name}. Available: {list(config.providers.keys())}",
                )

        gw_request = GatewayRequest.create(
            provider=providers[0] if not is_parallel else provider_spec,
            message=request.message,
            priority=request.priority,
            timeout_s=effective_timeout_s,
            metadata={
                "original_message": request.message,
                "parallel": is_parallel,
                "providers": providers if is_parallel else None,
                "aggregation_strategy": request.aggregation_strategy,
                "agent": request.agent,
            },
        )

        if not queue.enqueue(gw_request):
            raise HTTPException(
                status_code=503,
                detail="Request queue is full. Try again later.",
            )

        msg_preview = request.message[:100] if len(request.message) > 100 else request.message
        if ws_manager:
            await ws_manager.broadcast(
                WebSocketEvent(
                    type="request_submitted",
                    data={
                        "request_id": gw_request.id,
                        "provider": provider_spec,
                        "message": msg_preview,
                        "parallel": is_parallel,
                    },
                )
            )

        if wait:
            deadline = time.time() + timeout
            poll_interval = 0.5
            max_poll_interval = 2.0

            while time.time() < deadline:
                await asyncio.sleep(poll_interval)
                stored_request = store.get_request(gw_request.id)

                if not stored_request:
                    break

                if stored_request.status in (
                    RequestStatus.COMPLETED,
                    RequestStatus.FAILED,
                    RequestStatus.TIMEOUT,
                ):
                    response = store.get_response(gw_request.id)
                    return {
                        "request_id": gw_request.id,
                        "provider": provider_spec,
                        "status": stored_request.status.value,
                        "cached": False,
                        "parallel": is_parallel,
                        "response": response.response if response else None,
                        "error": response.error if response else None,
                        "latency_ms": response.latency_ms if response else None,
                        "retry_info": response.metadata.get("retry_info") if response and response.metadata else None,
                        "thinking": response.thinking if response else None,
                        "raw_output": response.raw_output if response else None,
                    }

                poll_interval = min(poll_interval * 1.5, max_poll_interval)

            return {
                "request_id": gw_request.id,
                "provider": provider_spec,
                "status": "timeout",
                "cached": False,
                "parallel": is_parallel,
                "response": None,
                "error": f"Request did not complete within {timeout}s timeout",
                "latency_ms": None,
            }

        return AskResponse(
            request_id=gw_request.id,
            provider=provider_spec,
            status=gw_request.status.value,
            cached=False,
            parallel=is_parallel,
            agent=request.agent,
        )


    @router.get("/api/reply/{request_id}", response_model=ReplyResponse)
    async def get_reply(
        request_id: str,
        wait: bool = Query(False, description="Wait for completion"),
        timeout: float = Query(300.0, description="Wait timeout in seconds"),
        store=Depends(get_store),
    ) -> ReplyResponse:
        """
        Get the response for a request.

        If wait=true, blocks until the request completes or times out.
        """
        request = store.get_request(request_id)
        if not request:
            raise_request_not_found()

        if wait and request.status in (RequestStatus.QUEUED, RequestStatus.PROCESSING, RequestStatus.RETRYING):
            deadline = time.time() + timeout
            while time.time() < deadline:
                await asyncio.sleep(0.5)
                request = store.get_request(request_id)
                if not request or request.status not in (
                    RequestStatus.QUEUED,
                    RequestStatus.PROCESSING,
                    RequestStatus.RETRYING,
                ):
                    break

        response = store.get_response(request_id)

        return ReplyResponse(
            request_id=request_id,
            status=request.status.value if request else "unknown",
            response=response.response if response else None,
            error=response.error if response else None,
            latency_ms=response.latency_ms if response else None,
            cached=response.metadata.get("cached", False) if response and response.metadata else False,
            retry_info=response.metadata.get("retry_info") if response and response.metadata else None,
            thinking=response.thinking if response else None,
            raw_output=response.raw_output if response else None,
        )


    @router.post("/api/ask/stream")
    async def ask_stream(
        request: AskRequest,
        config=Depends(get_config),
        router_func=Depends(get_router_func),
        stream_manager=Depends(get_stream_manager),
        backends=Depends(get_backends),
    ):
        """
        Submit a request and stream the response via SSE.

        Returns Server-Sent Events with chunks of the response.
        """
        if not config.streaming.enabled:
            raise HTTPException(status_code=400, detail="Streaming is disabled")

        provider = request.provider
        if not provider:
            if router_func:
                decision = router_func(request.message)
                provider = decision.provider
            else:
                provider = config.default_provider

        if provider not in config.providers:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown provider: {provider}",
            )

        gw_request = GatewayRequest.create(
            provider=provider,
            message=request.message,
            priority=request.priority,
            timeout_s=request.timeout_s,
        )

        async def generate_stream():
            """Generate SSE stream."""
            if stream_manager:
                backend = backends.get(provider) if backends else None
                if backend:
                    async for chunk in stream_manager.stream_response(
                        gw_request.id,
                        provider,
                        backend,
                        gw_request,
                    ):
                        yield chunk
                else:
                    yield f"data: {json.dumps({'type': 'error', 'error': 'Backend not available'})}\n\n"
            else:
                yield f"data: {json.dumps({'type': 'error', 'error': 'Streaming not configured'})}\n\n"

        return StreamingResponse(
            generate_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )


    @router.get("/api/status", response_model=StatusResponse)
    async def get_status(
        config=Depends(get_config),
        store=Depends(get_store),
        queue=Depends(get_queue),
        cache_manager=Depends(get_cache_manager),
        start_time: float = Depends(get_start_time),
    ) -> StatusResponse:
        """Get gateway and provider status."""
        uptime = time.time() - start_time
        stats = store.get_stats()
        queue_stats = queue.stats()

        cache_stats = None
        if cache_manager:
            cache_stats = cache_manager.get_stats().to_dict()

        token_data = {provider_stats["provider"]: provider_stats for provider_stats in store.get_cost_by_provider(days=30)}

        providers = []
        for name, pconfig in config.providers.items():
            pstatus = store.get_provider_status(name)
            metrics = store.get_provider_metrics(name, hours=24)
            cost_info = token_data.get(name, {})

            providers.append(
                {
                    "name": name,
                    "enabled": pconfig.enabled,
                    "status": pstatus.status.value if pstatus else "unknown",
                    "queue_depth": queue_stats["by_provider"].get(name, 0),
                    "avg_latency_ms": metrics.get("avg_latency_ms", 0),
                    "success_rate": metrics.get("success_rate", 1.0),
                    "total_input_tokens": cost_info.get("total_input_tokens", 0),
                    "total_output_tokens": cost_info.get("total_output_tokens", 0),
                    "total_cost_usd": cost_info.get("total_cost_usd", 0.0),
                    "total_requests": cost_info.get("request_count", 0),
                    "last_check": pstatus.last_check if pstatus else None,
                    "last_error": pstatus.error if pstatus else None,
                }
            )

        return StatusResponse(
            gateway={
                "uptime_s": uptime,
                "total_requests": stats["total_requests"],
                "active_requests": stats["active_requests"],
                "queue_depth": queue_stats["queue_depth"],
                "processing_count": queue_stats["processing_count"],
                "cache": cache_stats,
                "features": {
                    "retry_enabled": config.retry.enabled,
                    "cache_enabled": config.cache.enabled,
                    "streaming_enabled": config.streaming.enabled,
                    "parallel_enabled": config.parallel.enabled,
                },
            },
            providers=providers,
        )


    @router.delete("/api/request/{request_id}")
    async def cancel_request(
        request_id: str,
        queue=Depends(get_queue),
        ws_manager=Depends(get_ws_manager),
    ) -> Dict[str, Any]:
        """Cancel a pending or processing request."""
        success = queue.cancel(request_id)
        if not success:
            raise HTTPException(
                status_code=404,
                detail="Request not found or already completed",
            )

        if ws_manager:
            await ws_manager.broadcast(
                WebSocketEvent(
                    type="request_cancelled",
                    data={"request_id": request_id},
                )
            )

        return {"success": True, "request_id": request_id}


_runtime_management_funcs = register_runtime_management_routes(
    router=router,
    get_config=get_config,
    get_store=get_store,
    get_queue=get_queue,
)
globals().update(_runtime_management_funcs)
