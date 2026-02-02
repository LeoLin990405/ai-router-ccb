"""
Gateway API - FastAPI Routes for CCB Gateway.

Provides REST and WebSocket endpoints for the gateway.
"""
from __future__ import annotations

import asyncio
import json
import time
from typing import Optional, List, Dict, Any, Set

import os
from pathlib import Path

try:
    from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Query, Request, Depends
    from fastapi.responses import JSONResponse, StreamingResponse, Response, PlainTextResponse, FileResponse, HTMLResponse
    from starlette.middleware.base import BaseHTTPMiddleware
    from fastapi.staticfiles import StaticFiles
    from pydantic import BaseModel, Field
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False

# Web UI directory
WEB_UI_DIR = Path(__file__).parent / "web"

from .models import (
    RequestStatus,
    GatewayRequest,
    GatewayResponse,
    GatewayStats,
    WebSocketEvent,
)
from .state_store import StateStore
from .request_queue import RequestQueue
from .gateway_config import GatewayConfig


# Pydantic models for API
if HAS_FASTAPI:
    class AskRequest(BaseModel):
        """Request body for /api/ask endpoint."""
        message: str = Field(..., description="The message to send to the provider")
        provider: Optional[str] = Field(None, description="Provider name, @group, or auto-routed if not specified")
        timeout_s: float = Field(300.0, description="Request timeout in seconds")
        priority: int = Field(50, description="Request priority (higher = more urgent)")
        cache_bypass: bool = Field(False, description="Bypass cache for this request")
        aggregation_strategy: Optional[str] = Field(None, description="Strategy for parallel queries: first_success, fastest, all, consensus")

    class AskResponse(BaseModel):
        """Response body for /api/ask endpoint."""
        request_id: str
        provider: str
        status: str
        cached: bool = False
        parallel: bool = False

    class ReplyResponse(BaseModel):
        """Response body for /api/reply endpoint."""
        request_id: str
        status: str
        response: Optional[str] = None
        error: Optional[str] = None
        latency_ms: Optional[float] = None
        cached: bool = False
        retry_info: Optional[Dict[str, Any]] = None

    class StatusResponse(BaseModel):
        """Response body for /api/status endpoint."""
        gateway: Dict[str, Any]
        providers: List[Dict[str, Any]]

    class CacheStatsResponse(BaseModel):
        """Response body for /api/cache/stats endpoint."""
        hits: int
        misses: int
        hit_rate: float
        total_entries: int
        expired_entries: int
        total_tokens_saved: int

    class ParallelResponse(BaseModel):
        """Response body for parallel query results."""
        request_id: str
        strategy: str
        selected_provider: Optional[str] = None
        selected_response: Optional[str] = None
        all_responses: Dict[str, Any] = {}
        latency_ms: float = 0.0
        success: bool = False
        error: Optional[str] = None

    class CreateAPIKeyRequest(BaseModel):
        """Request body for creating an API key."""
        name: str = Field(..., description="Human-readable name for the key")
        rate_limit_rpm: Optional[int] = Field(None, description="Per-key rate limit override")

    class CreateAPIKeyResponse(BaseModel):
        """Response body for creating an API key."""
        key_id: str
        api_key: str  # Only returned once!
        name: str
        created_at: float

    class APIKeyInfo(BaseModel):
        """API key information (without the actual key)."""
        key_id: str
        name: str
        created_at: float
        last_used_at: Optional[float] = None
        rate_limit_rpm: Optional[int] = None
        enabled: bool = True


class WebSocketManager:
    """Manages WebSocket connections for real-time updates."""

    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket) -> None:
        """Accept a new WebSocket connection."""
        await websocket.accept()
        async with self._lock:
            self.active_connections.add(websocket)

    async def disconnect(self, websocket: WebSocket) -> None:
        """Remove a WebSocket connection."""
        async with self._lock:
            self.active_connections.discard(websocket)

    async def broadcast(self, event: WebSocketEvent) -> None:
        """Broadcast an event to all connected clients."""
        if not self.active_connections:
            return

        message = event.to_dict()
        async with self._lock:
            dead_connections = set()
            for connection in self.active_connections:
                try:
                    await connection.send_json(message)
                except Exception:
                    dead_connections.add(connection)

            # Clean up dead connections
            self.active_connections -= dead_connections

    async def send_to(self, websocket: WebSocket, event: WebSocketEvent) -> None:
        """Send an event to a specific client."""
        try:
            await websocket.send_json(event.to_dict())
        except Exception:
            await self.disconnect(websocket)


def create_api(
    config: GatewayConfig,
    store: StateStore,
    queue: RequestQueue,
    router_func=None,
    cache_manager=None,
    stream_manager=None,
    parallel_executor=None,
    retry_executor=None,
    auth_middleware=None,
    rate_limiter=None,
    metrics=None,
    api_key_store=None,
) -> "FastAPI":
    """
    Create the FastAPI application with all routes.

    Args:
        config: Gateway configuration
        store: State store instance
        queue: Request queue instance
        router_func: Optional routing function for auto-routing
        cache_manager: Optional cache manager instance
        stream_manager: Optional stream manager instance
        parallel_executor: Optional parallel executor instance
        retry_executor: Optional retry executor instance
        auth_middleware: Optional authentication middleware
        rate_limiter: Optional rate limiter instance
        metrics: Optional metrics collector instance
        api_key_store: Optional API key store instance

    Returns:
        Configured FastAPI application
    """
    if not HAS_FASTAPI:
        raise ImportError("FastAPI is required. Install with: pip install fastapi uvicorn")

    app = FastAPI(
        title="CCB Gateway",
        description="Unified API Gateway for Multi-Provider AI Communication",
        version="2.0.0",
    )

    ws_manager = WebSocketManager()
    start_time = time.time()

    # ==================== Middleware Setup ====================

    # Add authentication middleware if provided
    if auth_middleware and config.auth.enabled:
        @app.middleware("http")
        async def auth_middleware_handler(request: Request, call_next):
            return await auth_middleware(request, call_next)

    # Add rate limiting middleware if provided
    if rate_limiter and config.rate_limit.enabled:
        from .rate_limiter import RateLimitMiddleware
        rate_limit_middleware = RateLimitMiddleware(rate_limiter)

        @app.middleware("http")
        async def rate_limit_middleware_handler(request: Request, call_next):
            return await rate_limit_middleware(request, call_next)

    # ==================== Helper Functions ====================

    def parse_provider_spec(spec: str) -> tuple[List[str], bool]:
        """Parse provider specification (single, @group, or @all)."""
        if spec.startswith("@"):
            providers = config.parallel.get_provider_group(spec)
            return providers, len(providers) > 1
        return [spec], False

    # ==================== REST Endpoints ====================

    @app.post("/api/ask", response_model=AskResponse)
    async def ask(request: AskRequest) -> AskResponse:
        """
        Submit a request to an AI provider.

        Supports:
        - Single provider: provider="claude"
        - Provider groups: provider="@all", "@fast", "@coding"
        - Auto-routing: provider=None (uses router or default)
        - Cache bypass: cache_bypass=True
        """
        # Determine provider(s)
        provider_spec = request.provider
        if not provider_spec:
            if router_func:
                decision = router_func(request.message)
                provider_spec = decision.provider
            else:
                provider_spec = config.default_provider

        # Parse provider specification
        providers, is_parallel = parse_provider_spec(provider_spec)

        if not providers:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown provider or group: {provider_spec}",
            )

        # Check cache first (only for single provider, non-parallel)
        if not is_parallel and cache_manager and config.cache.enabled and not request.cache_bypass:
            cached = cache_manager.get(providers[0], request.message)
            if cached:
                # Return cached response immediately
                gw_request = GatewayRequest.create(
                    provider=providers[0],
                    message=request.message,
                    priority=request.priority,
                    timeout_s=request.timeout_s,
                    metadata={"cached": True, "cache_key": cached.cache_key},
                )
                # Save to store for consistency
                store.create_request(gw_request)
                store.update_request_status(gw_request.id, RequestStatus.COMPLETED)
                store.save_response(GatewayResponse(
                    request_id=gw_request.id,
                    status=RequestStatus.COMPLETED,
                    response=cached.response,
                    provider=providers[0],
                    latency_ms=0.0,
                    tokens_used=cached.tokens_used,
                    metadata={"cached": True},
                ))

                return AskResponse(
                    request_id=gw_request.id,
                    provider=providers[0],
                    status="completed",
                    cached=True,
                    parallel=False,
                )

        # Validate providers
        for p in providers:
            if p not in config.providers:
                raise HTTPException(
                    status_code=400,
                    detail=f"Unknown provider: {p}. Available: {list(config.providers.keys())}",
                )

        # Create request
        gw_request = GatewayRequest.create(
            provider=providers[0] if not is_parallel else provider_spec,
            message=request.message,
            priority=request.priority,
            timeout_s=request.timeout_s,
            metadata={
                "parallel": is_parallel,
                "providers": providers if is_parallel else None,
                "aggregation_strategy": request.aggregation_strategy,
            },
        )

        # Enqueue
        if not queue.enqueue(gw_request):
            raise HTTPException(
                status_code=503,
                detail="Request queue is full. Try again later.",
            )

        # Broadcast event
        msg_preview = request.message[:100] if len(request.message) > 100 else request.message
        await ws_manager.broadcast(WebSocketEvent(
            type="request_submitted",
            data={
                "request_id": gw_request.id,
                "provider": provider_spec,
                "message": msg_preview,
                "parallel": is_parallel,
            },
        ))

        return AskResponse(
            request_id=gw_request.id,
            provider=provider_spec,
            status=gw_request.status.value,
            cached=False,
            parallel=is_parallel,
        )

    @app.get("/api/reply/{request_id}", response_model=ReplyResponse)
    async def get_reply(
        request_id: str,
        wait: bool = Query(False, description="Wait for completion"),
        timeout: float = Query(30.0, description="Wait timeout in seconds"),
    ) -> ReplyResponse:
        """
        Get the response for a request.

        If wait=true, blocks until the request completes or times out.
        """
        # Get request
        request = store.get_request(request_id)
        if not request:
            raise HTTPException(status_code=404, detail="Request not found")

        # If waiting and not complete, poll
        if wait and request.status in (RequestStatus.QUEUED, RequestStatus.PROCESSING, RequestStatus.RETRYING):
            deadline = time.time() + timeout
            while time.time() < deadline:
                await asyncio.sleep(0.5)
                request = store.get_request(request_id)
                if not request or request.status not in (RequestStatus.QUEUED, RequestStatus.PROCESSING, RequestStatus.RETRYING):
                    break

        # Get response if available
        response = store.get_response(request_id)

        return ReplyResponse(
            request_id=request_id,
            status=request.status.value if request else "unknown",
            response=response.response if response else None,
            error=response.error if response else None,
            latency_ms=response.latency_ms if response else None,
            cached=response.metadata.get("cached", False) if response and response.metadata else False,
            retry_info=response.metadata.get("retry_info") if response and response.metadata else None,
        )

    @app.post("/api/ask/stream")
    async def ask_stream(request: AskRequest):
        """
        Submit a request and stream the response via SSE.

        Returns Server-Sent Events with chunks of the response.
        """
        if not config.streaming.enabled:
            raise HTTPException(status_code=400, detail="Streaming is disabled")

        # Determine provider
        provider = request.provider
        if not provider:
            if router_func:
                decision = router_func(request.message)
                provider = decision.provider
            else:
                provider = config.default_provider

        # Validate provider
        if provider not in config.providers:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown provider: {provider}",
            )

        # Create request
        gw_request = GatewayRequest.create(
            provider=provider,
            message=request.message,
            priority=request.priority,
            timeout_s=request.timeout_s,
        )

        async def generate_stream():
            """Generate SSE stream."""
            if stream_manager:
                backend = app.state.backends.get(provider) if hasattr(app.state, 'backends') else None
                if backend:
                    async for chunk in stream_manager.stream_response(
                        gw_request.id, provider, backend, gw_request
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

    @app.get("/api/status", response_model=StatusResponse)
    async def get_status() -> StatusResponse:
        """Get gateway and provider status."""
        uptime = time.time() - start_time
        stats = store.get_stats()
        queue_stats = queue.stats()

        # Get cache stats if available
        cache_stats = None
        if cache_manager:
            cache_stats = cache_manager.get_stats().to_dict()

        providers = []
        for name, pconfig in config.providers.items():
            pstatus = store.get_provider_status(name)
            metrics = store.get_provider_metrics(name, hours=24)

            providers.append({
                "name": name,
                "enabled": pconfig.enabled,
                "status": pstatus.status.value if pstatus else "unknown",
                "queue_depth": queue_stats["by_provider"].get(name, 0),
                "avg_latency_ms": metrics.get("avg_latency_ms", 0),
                "success_rate": metrics.get("success_rate", 1.0),
            })

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

    @app.delete("/api/request/{request_id}")
    async def cancel_request(request_id: str) -> Dict[str, Any]:
        """Cancel a pending or processing request."""
        success = queue.cancel(request_id)
        if not success:
            raise HTTPException(
                status_code=404,
                detail="Request not found or already completed",
            )

        await ws_manager.broadcast(WebSocketEvent(
            type="request_cancelled",
            data={"request_id": request_id},
        ))

        return {"success": True, "request_id": request_id}

    @app.get("/api/requests")
    async def list_requests(
        status: Optional[str] = None,
        provider: Optional[str] = None,
        limit: int = Query(50, le=100),
        offset: int = Query(0, ge=0),
        order_by: str = Query("created_at", description="Field to order by: created_at, updated_at, priority"),
        order_desc: bool = Query(True, description="Order descending if true"),
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
        return [r.to_dict() for r in requests]

    @app.get("/api/queue")
    async def get_queue_status() -> Dict[str, Any]:
        """Get detailed queue status."""
        return queue.stats()

    @app.get("/api/providers")
    async def list_providers() -> List[Dict[str, Any]]:
        """List all configured providers."""
        providers = []
        for name, pconfig in config.providers.items():
            providers.append({
                "name": name,
                "backend_type": pconfig.backend_type.value,
                "enabled": pconfig.enabled,
                "priority": pconfig.priority,
                "timeout_s": pconfig.timeout_s,
                "supports_streaming": pconfig.supports_streaming,
            })
        return providers

    @app.get("/api/provider-groups")
    async def list_provider_groups() -> Dict[str, List[str]]:
        """List all configured provider groups for parallel queries."""
        return config.parallel.provider_groups

    @app.post("/api/admin/providers/{provider_name}/enable")
    async def enable_provider(provider_name: str) -> Dict[str, Any]:
        """Enable a provider."""
        if provider_name not in config.providers:
            raise HTTPException(status_code=404, detail=f"Provider '{provider_name}' not found")
        config.providers[provider_name].enabled = True
        return {"status": "ok", "provider": provider_name, "enabled": True}

    @app.post("/api/admin/providers/{provider_name}/disable")
    async def disable_provider(provider_name: str) -> Dict[str, Any]:
        """Disable a provider."""
        if provider_name not in config.providers:
            raise HTTPException(status_code=404, detail=f"Provider '{provider_name}' not found")
        config.providers[provider_name].enabled = False
        return {"status": "ok", "provider": provider_name, "enabled": False}

    @app.get("/api/health")
    async def health_check() -> Dict[str, str]:
        """Simple health check endpoint."""
        return {"status": "ok"}

    # ==================== Cache Endpoints ====================

    @app.get("/api/cache/stats", response_model=CacheStatsResponse)
    async def get_cache_stats() -> CacheStatsResponse:
        """Get cache statistics."""
        if not cache_manager:
            raise HTTPException(status_code=400, detail="Cache not enabled")

        stats = cache_manager.get_stats()
        return CacheStatsResponse(
            hits=stats.hits,
            misses=stats.misses,
            hit_rate=stats.hit_rate,
            total_entries=stats.total_entries,
            expired_entries=stats.expired_entries,
            total_tokens_saved=stats.total_tokens_saved,
        )

    @app.get("/api/cache/stats/detailed")
    async def get_cache_stats_detailed() -> Dict[str, Any]:
        """Get detailed cache statistics including per-provider breakdown."""
        if not cache_manager:
            raise HTTPException(status_code=400, detail="Cache not enabled")

        stats = cache_manager.get_stats()
        provider_stats = cache_manager.get_provider_stats()
        top_entries = cache_manager.get_top_entries(10)

        return {
            "summary": stats.to_dict(),
            "by_provider": provider_stats,
            "top_entries": [
                {
                    "cache_key": e.cache_key,
                    "provider": e.provider,
                    "hit_count": e.hit_count,
                    "response_preview": e.response[:100] if e.response else None,
                }
                for e in top_entries
            ],
        }

    @app.delete("/api/cache")
    async def clear_cache(
        provider: Optional[str] = Query(None, description="Clear cache for specific provider"),
    ) -> Dict[str, Any]:
        """Clear cache entries."""
        if not cache_manager:
            raise HTTPException(status_code=400, detail="Cache not enabled")

        cleared = cache_manager.clear(provider)
        return {"cleared": cleared, "provider": provider}

    @app.post("/api/cache/cleanup")
    async def cleanup_cache() -> Dict[str, Any]:
        """Remove expired cache entries and enforce max entries limit."""
        if not cache_manager:
            raise HTTPException(status_code=400, detail="Cache not enabled")

        expired_removed = cache_manager.cleanup_expired()
        excess_removed = cache_manager.enforce_max_entries()
        return {
            "expired_removed": expired_removed,
            "excess_removed": excess_removed,
            "total_removed": expired_removed + excess_removed,
        }

    # ==================== Request Cleanup Endpoints ====================

    @app.post("/api/requests/cleanup")
    async def cleanup_requests(
        max_age_hours: int = Query(24, description="Remove requests older than this many hours"),
    ) -> Dict[str, Any]:
        """Remove old requests and their responses."""
        removed = store.cleanup_old_requests(max_age_hours)
        return {
            "removed": removed,
            "max_age_hours": max_age_hours,
        }

    @app.delete("/api/requests/{request_id}")
    async def delete_request(request_id: str) -> Dict[str, Any]:
        """Delete a specific request and its response."""
        # Check if request exists
        request = store.get_request(request_id)
        if not request:
            raise HTTPException(status_code=404, detail="Request not found")

        # Delete from database
        with store._get_connection() as conn:
            conn.execute("DELETE FROM responses WHERE request_id = ?", (request_id,))
            conn.execute("DELETE FROM requests WHERE id = ?", (request_id,))

        return {"deleted": True, "request_id": request_id}

    # ==================== Retry/Fallback Endpoints ====================

    @app.get("/api/retry/config")
    async def get_retry_config() -> Dict[str, Any]:
        """Get retry and fallback configuration."""
        return {
            "enabled": config.retry.enabled,
            "max_retries": config.retry.max_retries,
            "base_delay_s": config.retry.base_delay_s,
            "max_delay_s": config.retry.max_delay_s,
            "fallback_enabled": config.retry.fallback_enabled,
            "fallback_chains": config.retry.fallback_chains,
        }

    # ==================== Metrics Endpoint ====================

    @app.get("/metrics")
    async def get_metrics():
        """
        Export Prometheus metrics.

        Returns metrics in Prometheus text format.
        """
        if not metrics:
            return PlainTextResponse(
                content="# Metrics not enabled\n",
                media_type="text/plain",
            )

        return Response(
            content=metrics.export(),
            media_type=metrics.get_content_type(),
        )

    # ==================== Admin API Key Endpoints ====================

    @app.post("/api/admin/keys", response_model=CreateAPIKeyResponse)
    async def create_api_key(request: CreateAPIKeyRequest) -> CreateAPIKeyResponse:
        """
        Create a new API key.

        The raw API key is only returned once - store it securely!
        """
        if not api_key_store:
            raise HTTPException(
                status_code=400,
                detail="API key management not enabled",
            )

        api_key, raw_key = api_key_store.create_key(
            name=request.name,
            rate_limit_rpm=request.rate_limit_rpm,
        )

        return CreateAPIKeyResponse(
            key_id=api_key.key_id,
            api_key=raw_key,
            name=api_key.name,
            created_at=api_key.created_at,
        )

    @app.get("/api/admin/keys", response_model=List[APIKeyInfo])
    async def list_api_keys() -> List[APIKeyInfo]:
        """List all API keys (without the actual key values)."""
        if not api_key_store:
            raise HTTPException(
                status_code=400,
                detail="API key management not enabled",
            )

        keys = api_key_store.list_keys()
        return [
            APIKeyInfo(
                key_id=k.key_id,
                name=k.name,
                created_at=k.created_at,
                last_used_at=k.last_used_at,
                rate_limit_rpm=k.rate_limit_rpm,
                enabled=k.enabled,
            )
            for k in keys
        ]

    @app.delete("/api/admin/keys/{key_id}")
    async def delete_api_key(key_id: str) -> Dict[str, Any]:
        """Delete an API key."""
        if not api_key_store:
            raise HTTPException(
                status_code=400,
                detail="API key management not enabled",
            )

        deleted = api_key_store.delete_key(key_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="API key not found")

        return {"deleted": True, "key_id": key_id}

    @app.post("/api/admin/keys/{key_id}/disable")
    async def disable_api_key(key_id: str) -> Dict[str, Any]:
        """Disable an API key."""
        if not api_key_store:
            raise HTTPException(
                status_code=400,
                detail="API key management not enabled",
            )

        disabled = api_key_store.disable_key(key_id)
        if not disabled:
            raise HTTPException(status_code=404, detail="API key not found")

        return {"disabled": True, "key_id": key_id}

    @app.post("/api/admin/keys/{key_id}/enable")
    async def enable_api_key(key_id: str) -> Dict[str, Any]:
        """Enable an API key."""
        if not api_key_store:
            raise HTTPException(
                status_code=400,
                detail="API key management not enabled",
            )

        enabled = api_key_store.enable_key(key_id)
        if not enabled:
            raise HTTPException(status_code=404, detail="API key not found")

        return {"enabled": True, "key_id": key_id}

    # ==================== Rate Limit Endpoints ====================

    @app.get("/api/admin/rate-limit/stats")
    async def get_rate_limit_stats() -> Dict[str, Any]:
        """Get rate limiter statistics."""
        if not rate_limiter:
            return {"enabled": False}

        return rate_limiter.get_stats()

    @app.get("/api/admin/rate-limit/config")
    async def get_rate_limit_config() -> Dict[str, Any]:
        """Get rate limit configuration."""
        return {
            "enabled": config.rate_limit.enabled,
            "requests_per_minute": config.rate_limit.requests_per_minute,
            "burst_size": config.rate_limit.burst_size,
            "by_api_key": config.rate_limit.by_api_key,
            "by_ip": config.rate_limit.by_ip,
            "endpoint_limits": config.rate_limit.endpoint_limits,
        }

    # ==================== Auth Config Endpoints ====================

    @app.get("/api/admin/auth/config")
    async def get_auth_config() -> Dict[str, Any]:
        """Get authentication configuration."""
        return {
            "enabled": config.auth.enabled,
            "header_name": config.auth.header_name,
            "allow_localhost": config.auth.allow_localhost,
            "public_paths": config.auth.public_paths,
        }

    # ==================== WebSocket Endpoint ====================

    @app.websocket("/api/ws")
    async def websocket_endpoint(websocket: WebSocket):
        """
        WebSocket endpoint for real-time updates.

        Events:
        - request_queued: New request added to queue
        - request_started: Request processing started
        - request_completed: Request completed successfully
        - request_failed: Request failed
        - request_cancelled: Request was cancelled
        - request_retrying: Request is being retried
        - request_fallback: Request switched to fallback provider
        - provider_status: Provider status changed
        - stream_chunk: Streaming response chunk
        """
        await ws_manager.connect(websocket)
        try:
            while True:
                # Wait for messages from client
                data = await websocket.receive_json()

                # Handle subscription messages
                if data.get("type") == "subscribe":
                    channels = data.get("channels", [])
                    await ws_manager.send_to(websocket, WebSocketEvent(
                        type="subscribed",
                        data={"channels": channels},
                    ))

                elif data.get("type") == "ping":
                    await ws_manager.send_to(websocket, WebSocketEvent(
                        type="pong",
                        data={},
                    ))

        except WebSocketDisconnect:
            await ws_manager.disconnect(websocket)
        except Exception:
            await ws_manager.disconnect(websocket)

    # Store ws_manager on app for external access
    app.state.ws_manager = ws_manager

    # ==================== Web UI Static Files ====================

    @app.get("/", response_class=HTMLResponse)
    async def serve_dashboard():
        """Serve the Web UI dashboard."""
        index_path = WEB_UI_DIR / "index.html"
        if index_path.exists():
            return FileResponse(index_path, media_type="text/html")
        return HTMLResponse(
            content="<h1>CCB Gateway</h1><p>Web UI not found. API is running at /api/</p>",
            status_code=200
        )

    # Mount static files if web directory exists
    if WEB_UI_DIR.exists():
        app.mount("/static", StaticFiles(directory=str(WEB_UI_DIR)), name="static")

    return app
