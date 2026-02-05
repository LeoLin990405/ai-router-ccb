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
    DiscussionStatus,
    DiscussionSession,
    DiscussionMessage,
    DiscussionConfig,
    MessageType,
    AuthStatus,
)
from .state_store import StateStore
from .request_queue import RequestQueue
from .gateway_config import GatewayConfig
from .discussion import DiscussionExporter, ObsidianExporter
from .retry import detect_auth_failure, ProviderReliabilityScore, ReliabilityTracker
from .router import SmartRouter, auto_route, RoutingDecision


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
        agent: Optional[str] = Field(None, description="Agent role assigned by orchestrator (e.g., sisyphus, oracle, reviewer)")

    class AskResponse(BaseModel):
        """Response body for /api/ask endpoint."""
        request_id: str
        provider: str
        status: str
        cached: bool = False
        parallel: bool = False
        agent: Optional[str] = None

    class ReplyResponse(BaseModel):
        """Response body for /api/reply endpoint."""
        request_id: str
        status: str
        response: Optional[str] = None
        error: Optional[str] = None
        latency_ms: Optional[float] = None
        cached: bool = False
        retry_info: Optional[Dict[str, Any]] = None
        # Extended output fields for monitoring
        thinking: Optional[str] = None
        raw_output: Optional[str] = None

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

    # ==================== Discussion API Models ====================

    class StartDiscussionRequest(BaseModel):
        """Request body for starting a discussion."""
        topic: str = Field(..., description="The discussion topic")
        providers: Optional[List[str]] = Field(None, description="List of providers or None for default")
        provider_group: Optional[str] = Field(None, description="Provider group like @all, @fast, @coding")
        max_rounds: int = Field(3, description="Maximum discussion rounds (1-3)")
        round_timeout_s: float = Field(120.0, description="Timeout per round in seconds")
        provider_timeout_s: float = Field(120.0, description="Timeout per provider in seconds")
        run_async: bool = Field(True, description="Run discussion asynchronously")

    class DiscussionResponse(BaseModel):
        """Response body for discussion operations."""
        session_id: str
        topic: str
        status: str
        current_round: int
        providers: List[str]
        created_at: float
        summary: Optional[str] = None

    class DiscussionMessageResponse(BaseModel):
        """Response body for a discussion message."""
        id: str
        session_id: str
        round_number: int
        provider: str
        message_type: str
        content: Optional[str] = None
        status: str
        latency_ms: Optional[float] = None
        created_at: float

    class CreateTemplateRequest(BaseModel):
        """Request body for creating a discussion template."""
        name: str = Field(..., description="Unique template name")
        topic_template: str = Field(..., description="Template with placeholders like {subject}")
        description: Optional[str] = Field(None, description="Template description")
        default_providers: Optional[List[str]] = Field(None, description="Default providers list")
        default_config: Optional[Dict[str, Any]] = Field(None, description="Default discussion config")
        category: Optional[str] = Field(None, description="Template category")

    class UseTemplateRequest(BaseModel):
        """Request body for using a template to start a discussion."""
        variables: Dict[str, str] = Field(default_factory=dict, description="Variables to fill in template")
        providers: Optional[List[str]] = Field(None, description="Override default providers")
        config: Optional[Dict[str, Any]] = Field(None, description="Override default config")
        run_async: bool = Field(True, description="Run discussion asynchronously")

    class ContinueDiscussionRequest(BaseModel):
        """Request body for continuing a discussion."""
        follow_up_topic: str = Field(..., description="The follow-up topic to discuss")
        additional_context: Optional[str] = Field(None, description="Additional context")
        max_rounds: int = Field(2, description="Number of rounds for continuation")

    class ExportObsidianRequest(BaseModel):
        """Request body for exporting to Obsidian."""
        vault_path: str = Field(..., description="Path to Obsidian vault")
        folder: str = Field("CCB Discussions", description="Subfolder within vault")

    # ==================== Memory API Models (v0.21) ====================

    class SaveDiscussionMemoryRequest(BaseModel):
        """Request body for saving discussion to memory."""
        summary_override: Optional[str] = Field(None, description="Override auto-generated summary")
        tags: Optional[List[str]] = Field(None, description="Tags for the memory")

    class CreateObservationRequest(BaseModel):
        """Request body for creating an observation."""
        content: str = Field(..., min_length=1, description="Observation content")
        category: str = Field("note", description="Category: insight, preference, fact, note")
        tags: Optional[List[str]] = Field(None, description="Tags for the observation")
        confidence: float = Field(1.0, ge=0.0, le=1.0, description="Confidence score")

    class UpdateObservationRequest(BaseModel):
        """Request body for updating an observation."""
        content: Optional[str] = Field(None, description="New content")
        category: Optional[str] = Field(None, description="New category")
        tags: Optional[List[str]] = Field(None, description="New tags")
        confidence: Optional[float] = Field(None, ge=0.0, le=1.0, description="New confidence")

    class UpdateConfigRequest(BaseModel):
        """Request body for updating memory configuration."""
        enabled: Optional[bool] = Field(None, description="Enable/disable memory system")
        auto_inject: Optional[bool] = Field(None, description="Auto-inject memories")
        max_injected_memories: Optional[int] = Field(None, ge=0, le=50, description="Max memories to inject")
        injection_strategy: Optional[str] = Field(None, description="Injection strategy")
        skills_auto_discover: Optional[bool] = Field(None, description="Auto-discover skills")
        skills_max_recommendations: Optional[int] = Field(None, ge=0, le=10, description="Max skill recommendations")

    class SkillFeedbackRequest(BaseModel):
        """Request body for skill feedback."""
        rating: int = Field(..., ge=1, le=5, description="Rating 1-5")
        helpful: bool = Field(True, description="Was the skill helpful?")
        task_description: Optional[str] = Field(None, description="Task description")
        comment: Optional[str] = Field(None, description="Optional comment")


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
    discussion_executor=None,
    reliability_tracker: Optional[ReliabilityTracker] = None,
    memory_middleware=None,
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
        discussion_executor: Optional discussion executor instance

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

    @app.post("/api/ask")
    async def ask(
        request: AskRequest,
        wait: bool = Query(False, description="Wait for completion before returning"),
        timeout: float = Query(300.0, description="Wait timeout in seconds (only used when wait=true)"),
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

                # If wait=true, return full response with cached content
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
                "agent": request.agent,
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

        # If wait=true, poll until completion or timeout
        if wait:
            deadline = time.time() + timeout
            poll_interval = 0.5  # Start with 500ms
            max_poll_interval = 2.0  # Max 2s between polls

            while time.time() < deadline:
                await asyncio.sleep(poll_interval)
                req = store.get_request(gw_request.id)

                if not req:
                    break

                if req.status in (RequestStatus.COMPLETED, RequestStatus.FAILED, RequestStatus.TIMEOUT):
                    response = store.get_response(gw_request.id)
                    return {
                        "request_id": gw_request.id,
                        "provider": provider_spec,
                        "status": req.status.value,
                        "cached": False,
                        "parallel": is_parallel,
                        "response": response.response if response else None,
                        "error": response.error if response else None,
                        "latency_ms": response.latency_ms if response else None,
                        "thinking": response.thinking if response else None,
                        "raw_output": response.raw_output if response else None,
                    }

                # Exponential backoff for polling
                poll_interval = min(poll_interval * 1.5, max_poll_interval)

            # Timeout reached
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

    @app.get("/api/reply/{request_id}", response_model=ReplyResponse)
    async def get_reply(
        request_id: str,
        wait: bool = Query(False, description="Wait for completion"),
        timeout: float = Query(300.0, description="Wait timeout in seconds"),
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
            thinking=response.thinking if response else None,
            raw_output=response.raw_output if response else None,
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

        # Get token/cost data by provider for the last 30 days
        token_data = {p["provider"]: p for p in store.get_cost_by_provider(days=30)}

        providers = []
        for name, pconfig in config.providers.items():
            pstatus = store.get_provider_status(name)
            metrics = store.get_provider_metrics(name, hours=24)
            cost_info = token_data.get(name, {})

            providers.append({
                "name": name,
                "enabled": pconfig.enabled,
                "status": pstatus.status.value if pstatus else "unknown",
                "queue_depth": queue_stats["by_provider"].get(name, 0),
                "avg_latency_ms": metrics.get("avg_latency_ms", 0),
                "success_rate": metrics.get("success_rate", 1.0),
                # Token statistics from cost data
                "total_input_tokens": cost_info.get("total_input_tokens", 0),
                "total_output_tokens": cost_info.get("total_output_tokens", 0),
                "total_cost_usd": cost_info.get("total_cost_usd", 0.0),
                "total_requests": cost_info.get("request_count", 0),
                # Health check info
                "last_check": pstatus.last_check if pstatus else None,
                "last_error": pstatus.error if pstatus else None,
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

    # ==================== Provider Auth Status Endpoints ====================

    @app.get("/api/providers/{provider_name}/auth-status")
    async def get_provider_auth_status(provider_name: str) -> Dict[str, Any]:
        """
        Get authentication status for a provider.

        Returns auth status based on recent request history.
        """
        if provider_name not in config.providers:
            raise HTTPException(status_code=404, detail=f"Provider not found: {provider_name}")

        # Get reliability data if tracker is available
        if reliability_tracker:
            score = reliability_tracker.get_score(provider_name)
            if score.needs_reauth:
                auth_status = AuthStatus.NEEDS_REAUTH
            elif score.auth_failure_count > 0:
                auth_status = AuthStatus.INVALID
            elif score.total_requests == 0:
                auth_status = AuthStatus.UNKNOWN
            else:
                auth_status = AuthStatus.VALID

            return {
                "provider": provider_name,
                "auth_status": auth_status.value,
                "auth_failure_count": score.auth_failure_count,
                "last_auth_failure": score.last_auth_failure,
                "needs_reauth": score.needs_reauth,
                "reliability_score": score.reliability_score,
            }

        # Fallback: check metrics from store
        provider_metrics = store.get_provider_metrics(provider_name, hours=24)

        return {
            "provider": provider_name,
            "auth_status": AuthStatus.UNKNOWN.value,
            "success_rate": provider_metrics.get("success_rate", 1.0),
            "total_requests": provider_metrics.get("total_requests", 0),
        }

    @app.post("/api/providers/{provider_name}/check-auth")
    async def check_provider_auth(provider_name: str) -> Dict[str, Any]:
        """
        Actively check authentication status for a provider.

        Sends a test request to verify credentials.
        """
        if provider_name not in config.providers:
            raise HTTPException(status_code=404, detail=f"Provider not found: {provider_name}")

        # Create a simple test request
        test_request = GatewayRequest.create(
            provider=provider_name,
            message="ping",
            timeout_s=30.0,
            metadata={"auth_check": True},
        )

        # Try to execute via backend
        backend = getattr(app.state, 'backends', {}).get(provider_name)
        if not backend:
            return {
                "provider": provider_name,
                "auth_status": AuthStatus.UNKNOWN.value,
                "error": "Backend not available",
            }

        try:
            result = await asyncio.wait_for(
                backend.execute(test_request),
                timeout=30.0,
            )

            if result.success:
                # Update reliability tracker
                if reliability_tracker:
                    await reliability_tracker.record_success(provider_name)

                return {
                    "provider": provider_name,
                    "auth_status": AuthStatus.VALID.value,
                    "message": "Authentication successful",
                }
            else:
                is_auth_failure = detect_auth_failure(result.error or "")
                if reliability_tracker:
                    await reliability_tracker.record_failure(
                        provider_name,
                        result.error or "",
                    )

                return {
                    "provider": provider_name,
                    "auth_status": AuthStatus.INVALID.value if is_auth_failure else AuthStatus.UNKNOWN.value,
                    "error": result.error,
                    "is_auth_failure": is_auth_failure,
                }

        except asyncio.TimeoutError:
            return {
                "provider": provider_name,
                "auth_status": AuthStatus.UNKNOWN.value,
                "error": "Request timed out",
            }
        except Exception as e:
            return {
                "provider": provider_name,
                "auth_status": AuthStatus.UNKNOWN.value,
                "error": str(e),
            }

    @app.post("/api/providers/{provider_name}/reset-auth")
    async def reset_provider_auth(provider_name: str) -> Dict[str, Any]:
        """
        Reset auth failure count for a provider.

        Call this after re-authenticating with a provider.
        """
        if provider_name not in config.providers:
            raise HTTPException(status_code=404, detail=f"Provider not found: {provider_name}")

        if reliability_tracker:
            await reliability_tracker.reset_auth(provider_name)

        return {
            "provider": provider_name,
            "message": "Auth failures reset",
            "auth_status": AuthStatus.UNKNOWN.value,
        }

    @app.get("/api/providers/reliability")
    async def get_all_provider_reliability() -> Dict[str, Any]:
        """Get reliability scores for all providers."""
        if not reliability_tracker:
            return {"error": "Reliability tracking not enabled", "providers": {}}

        return {
            "providers": reliability_tracker.get_all_scores(),
        }

    # ==================== Cost Tracking Endpoints ====================

    @app.get("/api/costs/summary")
    async def get_cost_summary(
        days: int = Query(30, description="Number of days to include"),
    ) -> Dict[str, Any]:
        """
        Get cost summary for the specified period.

        Returns total tokens used and costs, plus today/week breakdowns.
        """
        return store.get_cost_summary(days=days)

    @app.get("/api/costs/by-provider")
    async def get_costs_by_provider(
        days: int = Query(30, description="Number of days to include"),
    ) -> List[Dict[str, Any]]:
        """Get cost breakdown by provider."""
        return store.get_cost_by_provider(days=days)

    @app.get("/api/costs/by-day")
    async def get_costs_by_day(
        days: int = Query(7, description="Number of days to include"),
    ) -> List[Dict[str, Any]]:
        """Get daily cost breakdown."""
        return store.get_cost_by_day(days=days)

    @app.get("/api/costs/pricing")
    async def get_provider_pricing() -> Dict[str, Any]:
        """Get pricing configuration per provider (per million tokens)."""
        return {
            "pricing": store.PROVIDER_PRICING,
            "unit": "USD per million tokens",
        }

    @app.post("/api/costs/record")
    async def record_token_cost(
        provider: str = Query(..., description="Provider name"),
        input_tokens: int = Query(0, description="Input token count"),
        output_tokens: int = Query(0, description="Output token count"),
        request_id: Optional[str] = Query(None, description="Associated request ID"),
        model: Optional[str] = Query(None, description="Model name"),
    ) -> Dict[str, Any]:
        """
        Record token usage for cost tracking.

        Usually called automatically by backends after request completion.
        """
        store.record_token_cost(
            provider=provider,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            request_id=request_id,
            model=model,
        )
        return {"recorded": True, "provider": provider}

    # ==================== Smart Routing Endpoints ====================

    @app.post("/api/route")
    async def route_message(
        message: str = Query(..., description="Message to route"),
    ) -> Dict[str, Any]:
        """
        Get routing recommendation for a message.

        Uses keyword matching to suggest the best provider.
        """
        available = list(config.providers.keys())
        decision = auto_route(message, available_providers=available)

        return {
            "provider": decision.provider,
            "model": decision.model,
            "confidence": decision.confidence,
            "matched_keywords": decision.matched_keywords,
            "rule_description": decision.rule_description,
        }

    @app.get("/api/route/rules")
    async def get_routing_rules() -> List[Dict[str, Any]]:
        """Get all configured routing rules."""
        available = list(config.providers.keys())
        router = SmartRouter(available_providers=available)
        return router.get_rules()

    # ==================== Obsidian Integration Endpoints ====================

    @app.post("/api/discussion/{session_id}/export-obsidian")
    async def export_to_obsidian(
        session_id: str,
        request: ExportObsidianRequest,
    ) -> Dict[str, Any]:
        """
        Export a discussion to an Obsidian vault.

        Creates a markdown file with YAML frontmatter, tags, and callouts
        compatible with Obsidian's features.
        """
        exporter = ObsidianExporter(store)

        try:
            file_path = exporter.export_to_vault(
                session_id=session_id,
                vault_path=request.vault_path,
                folder=request.folder,
            )
            return {
                "success": True,
                "file_path": file_path,
                "session_id": session_id,
            }
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Export failed: {e}")

    # ==================== Discussion Endpoints ====================

    @app.post("/api/discussion/start", response_model=DiscussionResponse)
    async def start_discussion(request: StartDiscussionRequest) -> DiscussionResponse:
        """
        Start a new multi-AI discussion session.

        Supports:
        - Explicit provider list: providers=["kimi", "qwen", "deepseek"]
        - Provider groups: provider_group="@all", "@fast", "@coding"
        """
        if not discussion_executor:
            raise HTTPException(
                status_code=400,
                detail="Discussion feature not enabled",
            )

        # Resolve providers
        providers = request.providers
        if not providers and request.provider_group:
            providers = discussion_executor.resolve_provider_group(request.provider_group)

        if not providers:
            # Default to all available providers
            providers = list(discussion_executor.backends.keys())

        if len(providers) < 2:
            raise HTTPException(
                status_code=400,
                detail=f"Need at least 2 providers for discussion, got {len(providers)}",
            )

        # Create config
        disc_config = DiscussionConfig(
            max_rounds=min(request.max_rounds, 3),
            round_timeout_s=request.round_timeout_s,
            provider_timeout_s=request.provider_timeout_s,
        )

        try:
            # Start session
            session = await discussion_executor.start_discussion(
                topic=request.topic,
                providers=providers,
                config=disc_config,
            )

            # Run discussion asynchronously if requested
            if request.run_async:
                asyncio.create_task(
                    discussion_executor.run_full_discussion(session.id)
                )

            return DiscussionResponse(
                session_id=session.id,
                topic=session.topic,
                status=session.status.value,
                current_round=session.current_round,
                providers=session.providers,
                created_at=session.created_at,
                summary=session.summary,
            )

        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to start discussion: {e}")

    @app.get("/api/discussion/{session_id}", response_model=DiscussionResponse)
    async def get_discussion(session_id: str) -> DiscussionResponse:
        """Get discussion session status and details."""
        session = store.get_discussion_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Discussion not found")

        return DiscussionResponse(
            session_id=session.id,
            topic=session.topic,
            status=session.status.value,
            current_round=session.current_round,
            providers=session.providers,
            created_at=session.created_at,
            summary=session.summary,
        )

    @app.get("/api/discussion/{session_id}/messages")
    async def get_discussion_messages(
        session_id: str,
        round_number: Optional[int] = Query(None, description="Filter by round number"),
        provider: Optional[str] = Query(None, description="Filter by provider"),
    ) -> List[Dict[str, Any]]:
        """Get messages from a discussion session."""
        session = store.get_discussion_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Discussion not found")

        message_type = None
        messages = store.get_discussion_messages(
            session_id=session_id,
            round_number=round_number,
            provider=provider,
            message_type=message_type,
        )

        return [m.to_dict() for m in messages]

    @app.delete("/api/discussion/{session_id}")
    async def cancel_discussion(session_id: str) -> Dict[str, Any]:
        """Cancel an ongoing discussion."""
        if not discussion_executor:
            raise HTTPException(
                status_code=400,
                detail="Discussion feature not enabled",
            )

        success = await discussion_executor.cancel_discussion(session_id)
        if not success:
            raise HTTPException(
                status_code=404,
                detail="Discussion not found or already completed",
            )

        return {"cancelled": True, "session_id": session_id}

    @app.get("/api/discussions")
    async def list_discussions(
        status: Optional[str] = Query(None, description="Filter by status"),
        limit: int = Query(50, le=100),
        offset: int = Query(0, ge=0),
    ) -> List[Dict[str, Any]]:
        """List discussion sessions."""
        status_enum = DiscussionStatus(status) if status else None
        sessions = store.list_discussion_sessions(
            status=status_enum,
            limit=limit,
            offset=offset,
        )
        return [s.to_dict() for s in sessions]

    @app.get("/api/discussion-groups")
    async def get_discussion_groups() -> Dict[str, List[str]]:
        """Get available provider groups for discussions."""
        if not discussion_executor:
            return {"all": list(config.providers.keys())}
        return discussion_executor.get_provider_groups()

    @app.get("/api/discussion/{session_id}/export")
    async def export_discussion(
        session_id: str,
        format: str = Query("md", description="Export format: md, json, or html"),
        include_metadata: bool = Query(True, description="Include metadata in export"),
    ):
        """
        Export a discussion to Markdown, JSON, or HTML format.

        Formats:
        - md: Markdown with YAML frontmatter
        - json: Full JSON export with all data
        - html: Styled HTML document
        """
        exporter = DiscussionExporter(store)

        try:
            content = exporter.export(session_id, format=format, include_metadata=include_metadata)
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))

        # Set appropriate content type
        content_types = {
            "md": "text/markdown",
            "json": "application/json",
            "html": "text/html",
        }
        content_type = content_types.get(format, "text/plain")

        # Generate filename
        session = store.get_discussion_session(session_id)
        topic_slug = session.topic[:30].replace(" ", "_").replace("/", "-") if session else session_id
        filename = f"discussion_{topic_slug}.{format}"

        return Response(
            content=content,
            media_type=content_type,
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
            },
        )

    # ==================== Discussion Template Endpoints ====================

    @app.post("/api/discussion/templates")
    async def create_template(request: CreateTemplateRequest) -> Dict[str, Any]:
        """Create a new discussion template."""
        try:
            template = store.create_discussion_template(
                name=request.name,
                topic_template=request.topic_template,
                description=request.description,
                default_providers=request.default_providers,
                default_config=request.default_config,
                category=request.category,
            )
            return template
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

    @app.get("/api/discussion/templates")
    async def list_templates(
        category: Optional[str] = Query(None, description="Filter by category"),
        include_builtin: bool = Query(True, description="Include built-in templates"),
    ) -> List[Dict[str, Any]]:
        """List all discussion templates."""
        return store.list_discussion_templates(
            category=category,
            include_builtin=include_builtin,
        )

    @app.get("/api/discussion/templates/{template_id}")
    async def get_template(template_id: str) -> Dict[str, Any]:
        """Get a specific discussion template."""
        template = store.get_discussion_template(template_id)
        if not template:
            raise HTTPException(status_code=404, detail="Template not found")
        return template

    @app.put("/api/discussion/templates/{template_id}")
    async def update_template(
        template_id: str,
        request: CreateTemplateRequest,
    ) -> Dict[str, Any]:
        """Update a discussion template (non-builtin only)."""
        success = store.update_discussion_template(
            template_id=template_id,
            name=request.name,
            topic_template=request.topic_template,
            description=request.description,
            default_providers=request.default_providers,
            default_config=request.default_config,
            category=request.category,
        )
        if not success:
            raise HTTPException(
                status_code=404,
                detail="Template not found or is a built-in template",
            )
        return store.get_discussion_template(template_id)

    @app.delete("/api/discussion/templates/{template_id}")
    async def delete_template(template_id: str) -> Dict[str, Any]:
        """Delete a discussion template (non-builtin only)."""
        success = store.delete_discussion_template(template_id)
        if not success:
            raise HTTPException(
                status_code=404,
                detail="Template not found or is a built-in template",
            )
        return {"deleted": True, "template_id": template_id}

    @app.post("/api/discussion/templates/{template_id}/use")
    async def use_template(
        template_id: str,
        request: UseTemplateRequest,
    ) -> DiscussionResponse:
        """
        Use a template to start a new discussion.

        Variables in the template (like {subject}, {context}) will be replaced
        with values from the request.
        """
        if not discussion_executor:
            raise HTTPException(
                status_code=400,
                detail="Discussion feature not enabled",
            )

        template = store.get_discussion_template(template_id)
        if not template:
            raise HTTPException(status_code=404, detail="Template not found")

        # Fill in template variables
        topic = template["topic_template"]
        for key, value in request.variables.items():
            topic = topic.replace(f"{{{key}}}", value)

        # Use provided or default providers
        providers = request.providers or template.get("default_providers")
        if not providers:
            providers = list(discussion_executor.backends.keys())

        # Merge configs
        default_config = template.get("default_config") or {}
        override_config = request.config or {}
        merged_config = {**default_config, **override_config}

        disc_config = DiscussionConfig(
            max_rounds=merged_config.get("max_rounds", 3),
            round_timeout_s=merged_config.get("round_timeout_s", 120.0),
            provider_timeout_s=merged_config.get("provider_timeout_s", 120.0),
        )

        try:
            # Increment usage count
            store.increment_template_usage(template_id)

            # Start session
            session = await discussion_executor.start_discussion(
                topic=topic,
                providers=providers,
                config=disc_config,
            )

            # Store template reference in metadata
            store.update_discussion_session(
                session.id,
                metadata={"template_id": template_id, "template_name": template["name"]},
            )

            # Run discussion asynchronously if requested
            if request.run_async:
                asyncio.create_task(
                    discussion_executor.run_full_discussion(session.id)
                )

            return DiscussionResponse(
                session_id=session.id,
                topic=session.topic,
                status=session.status.value,
                current_round=session.current_round,
                providers=session.providers,
                created_at=session.created_at,
                summary=session.summary,
            )

        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    @app.post("/api/discussion/{session_id}/continue")
    async def continue_discussion_endpoint(
        session_id: str,
        request: ContinueDiscussionRequest,
    ) -> DiscussionResponse:
        """
        Continue a completed discussion with a follow-up topic.

        Creates a new discussion session linked to the parent,
        with context from the previous discussion.
        """
        if not discussion_executor:
            raise HTTPException(
                status_code=400,
                detail="Discussion feature not enabled",
            )

        try:
            # Create continuation session
            session = await discussion_executor.continue_discussion(
                session_id=session_id,
                follow_up_topic=request.follow_up_topic,
                additional_context=request.additional_context,
                max_rounds=request.max_rounds,
            )

            # Run the discussion
            asyncio.create_task(
                discussion_executor.run_full_discussion(session.id)
            )

            return DiscussionResponse(
                session_id=session.id,
                topic=request.follow_up_topic,
                status=session.status.value,
                current_round=session.current_round,
                providers=session.providers,
                created_at=session.created_at,
                summary=None,
            )

        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    # ==================== Discussion Memory API (Phase 6) ====================

    @app.post("/api/discussion/{session_id}/save-to-memory")
    async def save_discussion_to_memory(
        session_id: str,
        request: SaveDiscussionMemoryRequest = None
    ):
        """Save a discussion to memory system (Phase 6: Discussion Memory)."""
        if not memory_middleware:
            raise HTTPException(status_code=503, detail="Memory middleware not available")

        try:
            # Get discussion session
            session = store.get_discussion_session(session_id)
            if not session:
                raise HTTPException(status_code=404, detail=f"Discussion {session_id} not found")

            # Get messages if requested
            messages = None
            if request and request.include_messages:
                messages_list = store.get_discussion_messages(session_id)
                messages = [
                    {
                        "provider": m.provider,
                        "content": m.content,
                        "round": m.round_number,
                        "message_type": m.message_type.value
                    }
                    for m in messages_list if m.content
                ]

            # Save to memory
            observation_id = await memory_middleware.post_discussion(
                session_id=session_id,
                topic=session.topic,
                providers=session.providers,
                summary=request.summary if request else session.summary,
                insights=request.insights if request else None,
                messages=messages
            )

            if not observation_id:
                raise HTTPException(status_code=500, detail="Failed to save discussion to memory")

            return JSONResponse(content={
                "session_id": session_id,
                "observation_id": observation_id,
                "message": "Discussion saved to memory successfully"
            })

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to save discussion: {str(e)}")

    @app.get("/api/memory/discussions")
    async def get_discussion_memories(
        limit: int = Query(10, ge=1, le=50)
    ):
        """Get discussions saved to memory (Phase 6)."""
        if not memory_middleware or not hasattr(memory_middleware, 'memory'):
            raise HTTPException(status_code=503, detail="Memory system not available")

        try:
            discussions = memory_middleware.memory.v2.get_discussion_memory(limit=limit)
            return JSONResponse(content={
                "total": len(discussions),
                "discussions": discussions
            })
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to get discussions: {str(e)}")

    # ==================== Unified Results Endpoints ====================

    @app.get("/api/results")
    async def get_latest_results(
        provider: Optional[str] = Query(None, description="Filter by provider"),
        limit: int = Query(10, le=50, description="Maximum results to return"),
        include_discussions: bool = Query(True, description="Include discussion summaries"),
    ) -> List[Dict[str, Any]]:
        """
        Get latest results from all sources (requests + discussions).

        This is the unified endpoint for Claude to read AI responses.
        Returns results sorted by creation time (newest first).
        """
        return store.get_latest_results(
            provider=provider,
            limit=limit,
            include_discussions=include_discussions,
        )

    @app.get("/api/results/{result_id}")
    async def get_result_by_id(result_id: str) -> Dict[str, Any]:
        """
        Get a specific result by ID.

        Works for both regular requests and discussion sessions.
        For discussions, includes all messages from the conversation.
        """
        result = store.get_result_by_id(result_id)
        if not result:
            raise HTTPException(status_code=404, detail="Result not found")
        return result

    @app.get("/api/results/provider/{provider_name}")
    async def get_provider_results(
        provider_name: str,
        limit: int = Query(10, le=50),
    ) -> List[Dict[str, Any]]:
        """Get latest results from a specific provider."""
        return store.get_latest_results(
            provider=provider_name,
            limit=limit,
            include_discussions=False,
        )

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

    # ==================== Memory v2.0 API ====================

    @app.get("/api/memory/sessions")
    async def get_memory_sessions(limit: int = Query(20, ge=1, le=100)):
        """Get recent memory sessions."""
        if not memory_middleware or not hasattr(memory_middleware, 'memory'):
            raise HTTPException(status_code=503, detail="Memory system not available")

        try:
            sessions = memory_middleware.memory.v2.list_sessions(limit=limit)
            return JSONResponse(content={"sessions": sessions})
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to fetch sessions: {str(e)}")

    @app.get("/api/memory/sessions/{session_id}")
    async def get_session_context(session_id: str, window_size: int = Query(20, ge=1, le=100)):
        """Get conversation context for a specific session."""
        if not memory_middleware or not hasattr(memory_middleware, 'memory'):
            raise HTTPException(status_code=503, detail="Memory system not available")

        try:
            messages = memory_middleware.memory.v2.get_session_context(
                session_id=session_id,
                window_size=window_size
            )
            return JSONResponse(content={"session_id": session_id, "messages": messages})
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to fetch session context: {str(e)}")

    @app.get("/api/memory/search")
    async def search_memory(
        query: str = Query(..., min_length=1),
        limit: int = Query(10, ge=1, le=50),
        provider: Optional[str] = None
    ):
        """Search memory messages using FTS5."""
        if not memory_middleware or not hasattr(memory_middleware, 'memory'):
            raise HTTPException(status_code=503, detail="Memory system not available")

        try:
            results = memory_middleware.memory.v2.search_messages(
                query=query,
                limit=limit,
                provider=provider
            )
            return JSONResponse(content={"query": query, "results": results})
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")

    @app.get("/api/memory/stats")
    async def get_memory_stats():
        """Get memory system statistics."""
        if not memory_middleware or not hasattr(memory_middleware, 'memory'):
            raise HTTPException(status_code=503, detail="Memory system not available")

        try:
            stats = memory_middleware.memory.v2.get_stats()
            return JSONResponse(content=stats)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to fetch stats: {str(e)}")

    # ==================== Memory Transparency API (Phase 1) ====================

    @app.get("/api/memory/request/{request_id}")
    async def get_request_memory(request_id: str):
        """Get injection details for a specific request (Phase 1: Transparency)."""
        if not memory_middleware or not hasattr(memory_middleware, 'memory'):
            raise HTTPException(status_code=503, detail="Memory system not available")

        try:
            injection = memory_middleware.memory.v2.get_request_injection(request_id)
            if not injection:
                raise HTTPException(status_code=404, detail=f"No injection record found for request {request_id}")

            # Also fetch the full memory details
            memories = memory_middleware.memory.v2.get_injected_memories_for_request(request_id)

            return JSONResponse(content={
                "request_id": request_id,
                "injection": injection,
                "injected_memories": memories
            })
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to fetch request memory: {str(e)}")

    @app.get("/api/memory/injections")
    async def get_recent_injections(
        limit: int = Query(20, ge=1, le=100),
        session_id: Optional[str] = None
    ):
        """Get recent memory injections for debugging (Phase 1: Transparency)."""
        if not memory_middleware or not hasattr(memory_middleware, 'memory'):
            raise HTTPException(status_code=503, detail="Memory system not available")

        try:
            injections = memory_middleware.memory.v2.get_request_injections(
                limit=limit,
                session_id=session_id
            )
            return JSONResponse(content={
                "total": len(injections),
                "injections": injections
            })
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to fetch injections: {str(e)}")

    # ==================== Memory Write API (Phase 2) ====================

    @app.post("/api/memory/add")
    async def create_observation(request: CreateObservationRequest):
        """Create a new observation (Phase 2: Write APIs)."""
        if not memory_middleware or not hasattr(memory_middleware, 'memory'):
            raise HTTPException(status_code=503, detail="Memory system not available")

        try:
            observation_id = memory_middleware.memory.v2.create_observation(
                content=request.content,
                category=request.category,
                tags=request.tags,
                source="manual",
                confidence=request.confidence
            )
            return JSONResponse(content={
                "observation_id": observation_id,
                "message": "Observation created successfully"
            })
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to create observation: {str(e)}")

    @app.get("/api/memory/observations")
    async def list_observations(
        category: Optional[str] = None,
        query: Optional[str] = None,
        limit: int = Query(50, ge=1, le=200)
    ):
        """List observations with optional filtering."""
        if not memory_middleware or not hasattr(memory_middleware, 'memory'):
            raise HTTPException(status_code=503, detail="Memory system not available")

        try:
            observations = memory_middleware.memory.v2.search_observations(
                query=query,
                category=category,
                limit=limit
            )
            return JSONResponse(content={
                "total": len(observations),
                "observations": observations
            })
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to list observations: {str(e)}")

    @app.get("/api/memory/observations/{observation_id}")
    async def get_observation(observation_id: str):
        """Get a specific observation."""
        if not memory_middleware or not hasattr(memory_middleware, 'memory'):
            raise HTTPException(status_code=503, detail="Memory system not available")

        try:
            observation = memory_middleware.memory.v2.get_observation(observation_id)
            if not observation:
                raise HTTPException(status_code=404, detail=f"Observation {observation_id} not found")
            return JSONResponse(content=observation)
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to get observation: {str(e)}")

    @app.put("/api/memory/{observation_id}")
    async def update_observation(observation_id: str, request: UpdateObservationRequest):
        """Update an existing observation (Phase 2: Write APIs)."""
        if not memory_middleware or not hasattr(memory_middleware, 'memory'):
            raise HTTPException(status_code=503, detail="Memory system not available")

        try:
            success = memory_middleware.memory.v2.update_observation(
                observation_id=observation_id,
                content=request.content,
                category=request.category,
                tags=request.tags,
                confidence=request.confidence
            )
            if not success:
                raise HTTPException(status_code=404, detail=f"Observation {observation_id} not found")
            return JSONResponse(content={
                "observation_id": observation_id,
                "message": "Observation updated successfully"
            })
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to update observation: {str(e)}")

    @app.delete("/api/memory/{observation_id}")
    async def delete_observation(observation_id: str):
        """Delete an observation (Phase 2: Write APIs)."""
        if not memory_middleware or not hasattr(memory_middleware, 'memory'):
            raise HTTPException(status_code=503, detail="Memory system not available")

        try:
            success = memory_middleware.memory.v2.delete_observation(observation_id)
            if not success:
                raise HTTPException(status_code=404, detail=f"Observation {observation_id} not found")
            return JSONResponse(content={
                "observation_id": observation_id,
                "message": "Observation deleted successfully"
            })
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to delete observation: {str(e)}")

    # ==================== Memory Configuration API (Phase 4) ====================

    @app.get("/api/memory/config")
    async def get_memory_config():
        """Get current memory system configuration (Phase 4)."""
        try:
            from lib.memory.memory_config import get_memory_config
            config = get_memory_config()
            validation = config.validate()
            return JSONResponse(content={
                "config": config.get_all(),
                "valid": validation["valid"],
                "errors": validation["errors"]
            })
        except ImportError:
            raise HTTPException(status_code=503, detail="Memory config module not available")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to get config: {str(e)}")

    @app.post("/api/memory/config")
    async def update_memory_config(request: UpdateConfigRequest):
        """Update memory system configuration (Phase 4)."""
        try:
            from lib.memory.memory_config import get_memory_config
            config = get_memory_config()

            # Build updates dict from non-None values
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

            # Reload middleware config if available
            if memory_middleware:
                memory_middleware.config = config.get_all()
                memory_middleware.enabled = config.get("enabled", True)
                memory_middleware.auto_inject = config.get("auto_inject", True)
                memory_middleware.max_injected = config.get("max_injected_memories", 5)

            return JSONResponse(content={
                "message": "Configuration updated",
                "config": updated_config,
                "valid": validation["valid"],
                "errors": validation["errors"]
            })
        except HTTPException:
            raise
        except ImportError:
            raise HTTPException(status_code=503, detail="Memory config module not available")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to update config: {str(e)}")

    @app.post("/api/memory/config/reset")
    async def reset_memory_config():
        """Reset memory configuration to defaults (Phase 4)."""
        try:
            from lib.memory.memory_config import get_memory_config
            config = get_memory_config()
            default_config = config.reset()
            return JSONResponse(content={
                "message": "Configuration reset to defaults",
                "config": default_config
            })
        except ImportError:
            raise HTTPException(status_code=503, detail="Memory config module not available")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to reset config: {str(e)}")

    # ==================== Skills Discovery API ====================

    @app.get("/api/skills/recommendations")
    async def get_skill_recommendations(query: str = Query(..., min_length=1)):
        """Get skill recommendations for a task."""
        if not memory_middleware or not hasattr(memory_middleware, 'skills_discovery'):
            raise HTTPException(status_code=503, detail="Skills Discovery not available")

        try:
            recommendations = memory_middleware.skills_discovery.get_recommendations(query)
            return JSONResponse(content=recommendations)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Skills discovery failed: {str(e)}")

    @app.get("/api/skills/stats")
    async def get_skills_stats():
        """Get skills usage statistics."""
        if not memory_middleware or not hasattr(memory_middleware, 'skills_discovery'):
            raise HTTPException(status_code=503, detail="Skills Discovery not available")

        try:
            stats = memory_middleware.skills_discovery.get_usage_stats()
            return JSONResponse(content=stats)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to fetch skills stats: {str(e)}")

    @app.get("/api/skills/list")
    async def list_skills(installed_only: bool = Query(False)):
        """List all available skills."""
        if not memory_middleware or not hasattr(memory_middleware, 'skills_discovery'):
            raise HTTPException(status_code=503, detail="Skills Discovery not available")

        try:
            skills = memory_middleware.skills_discovery.list_all_skills()
            if installed_only:
                skills = [s for s in skills if s.get('installed', False)]
            return JSONResponse(content={"skills": skills})
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to list skills: {str(e)}")

    # ==================== Skills Feedback API (Phase 5) ====================

    @app.post("/api/skills/{skill_name}/feedback")
    async def submit_skill_feedback(skill_name: str, request: SkillFeedbackRequest):
        """Submit feedback for a skill (Phase 5: Feedback Loop)."""
        if not memory_middleware or not hasattr(memory_middleware, 'skills_discovery'):
            raise HTTPException(status_code=503, detail="Skills Discovery not available")

        try:
            # Extract keywords from task description
            task_keywords = None
            if request.task_description:
                words = request.task_description.lower().split()
                task_keywords = " ".join([w for w in words if len(w) > 2][:10])

            success = memory_middleware.skills_discovery.record_feedback(
                skill_name=skill_name,
                rating=request.rating,
                task_keywords=task_keywords,
                task_description=request.task_description,
                helpful=request.helpful,
                comment=request.comment
            )

            if not success:
                raise HTTPException(status_code=400, detail="Invalid feedback data")

            return JSONResponse(content={
                "skill_name": skill_name,
                "message": "Feedback recorded successfully"
            })
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to record feedback: {str(e)}")

    @app.get("/api/skills/{skill_name}/feedback")
    async def get_skill_feedback(skill_name: str):
        """Get feedback statistics for a skill (Phase 5)."""
        if not memory_middleware or not hasattr(memory_middleware, 'skills_discovery'):
            raise HTTPException(status_code=503, detail="Skills Discovery not available")

        try:
            stats = memory_middleware.skills_discovery.get_skill_feedback_stats(skill_name)
            return JSONResponse(content=stats)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to get feedback: {str(e)}")

    @app.get("/api/skills/feedback/all")
    async def get_all_skill_feedback():
        """Get feedback statistics for all skills (Phase 5)."""
        if not memory_middleware or not hasattr(memory_middleware, 'skills_discovery'):
            raise HTTPException(status_code=503, detail="Skills Discovery not available")

        try:
            stats = memory_middleware.skills_discovery.get_all_feedback_stats()
            return JSONResponse(content={"skills_feedback": stats})
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to get feedback: {str(e)}")

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

    @app.get("/web", response_class=HTMLResponse)
    async def serve_dashboard_web():
        """Serve the Web UI dashboard at /web path."""
        index_path = WEB_UI_DIR / "index.html"
        if index_path.exists():
            return FileResponse(index_path, media_type="text/html")
        return HTMLResponse(
            content="<h1>CCB Gateway</h1><p>Web UI not found. API is running at /api/</p>",
            status_code=200
        )

    @app.get("/web/{file_path:path}")
    async def serve_web_files(file_path: str):
        """Serve static files from web directory."""
        # Security: Resolve to canonical path and validate it's within WEB_UI_DIR
        try:
            full_path = (WEB_UI_DIR / file_path).resolve()
            web_ui_resolved = WEB_UI_DIR.resolve()
            # Check path is within WEB_UI_DIR (prevent path traversal)
            if not str(full_path).startswith(str(web_ui_resolved) + "/") and full_path != web_ui_resolved:
                return HTMLResponse(content="Forbidden", status_code=403)
        except (ValueError, OSError):
            return HTMLResponse(content="Invalid path", status_code=400)

        if full_path.exists() and full_path.is_file():
            # Determine media type
            suffix = full_path.suffix.lower()
            media_types = {
                '.html': 'text/html',
                '.css': 'text/css',
                '.js': 'application/javascript',
                '.json': 'application/json',
                '.png': 'image/png',
                '.jpg': 'image/jpeg',
                '.svg': 'image/svg+xml',
            }
            media_type = media_types.get(suffix, 'application/octet-stream')
            return FileResponse(full_path, media_type=media_type)
        return HTMLResponse(content="Not Found", status_code=404)

    # Mount static files if web directory exists
    if WEB_UI_DIR.exists():
        app.mount("/static", StaticFiles(directory=str(WEB_UI_DIR)), name="static")

    return app
