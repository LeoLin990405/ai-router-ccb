"""Gateway FastAPI app factory."""
from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Optional

try:
    from fastapi import FastAPI, Request
    from fastapi.staticfiles import StaticFiles

    HAS_FASTAPI = True
except ImportError:  # pragma: no cover - optional FastAPI dependency
    HAS_FASTAPI = False

from .gateway_config import GatewayConfig
from .knowledge_api import get_knowledge_api_router
from .request_queue import RequestQueue
from .retry import ReliabilityTracker
from .routes import admin as admin_routes
from .routes import batch as batch_routes
from .routes import cc_switch as cc_switch_routes
from .routes import core as core_routes
from .routes import discussion as discussion_routes
from .routes import export as export_routes
from .routes import health as health_routes
from .routes import memory as memory_routes
from .routes import runtime as runtime_routes
from .routes import shared_knowledge as shared_knowledge_routes
from .routes import skills as skills_routes
from .routes import tool_router as tool_router_routes
from .routes import web as web_routes
from .routes import websocket as websocket_routes
from .routes.websocket import WebSocketManager
from .state_store import StateStore

WEB_UI_DIR = Path(__file__).parent / "web"


def _include_router_if_available(
    app: "FastAPI",
    router,
    *,
    prefix: Optional[str] = None,
    tags: Optional[list[str]] = None,
):
    if router is None:
        return

    include_kwargs = {}
    if prefix is not None:
        include_kwargs["prefix"] = prefix
    if tags is not None:
        include_kwargs["tags"] = tags

    app.include_router(router, **include_kwargs)


def create_app(
    config: GatewayConfig,
    *,
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
    health_checker=None,
    backpressure=None,
    shared_knowledge: Optional[Any] = None,
    tool_index: Optional[Any] = None,
):
    """Create FastAPI application and register all routes/middleware."""
    if not HAS_FASTAPI:
        raise ImportError("FastAPI is required. Install with: pip install fastapi uvicorn")

    app = FastAPI(
        title="CCB Gateway",
        description="Unified API Gateway for Multi-Provider AI Communication",
        version="2.1.0",
    )

    ws_manager = WebSocketManager()
    start_time = time.time()

    app.state.config = config
    app.state.store = store
    app.state.queue = queue
    app.state.router_func = router_func
    app.state.cache_manager = cache_manager
    app.state.stream_manager = stream_manager
    app.state.parallel_executor = parallel_executor
    app.state.retry_executor = retry_executor
    app.state.auth_middleware = auth_middleware
    app.state.rate_limiter = rate_limiter
    app.state.metrics = metrics
    app.state.api_key_store = api_key_store
    app.state.discussion_executor = discussion_executor
    app.state.reliability_tracker = reliability_tracker
    app.state.memory_middleware = memory_middleware
    app.state.health_checker = health_checker
    app.state.backpressure = backpressure
    app.state.shared_knowledge = shared_knowledge
    app.state.tool_index = tool_index
    app.state.start_time = start_time
    app.state.web_ui_dir = WEB_UI_DIR
    app.state.ws_manager = ws_manager

    knowledge_router = get_knowledge_api_router()
    if knowledge_router is not None:
        app.include_router(knowledge_router)

    _include_router_if_available(app, batch_routes.router, prefix="/api/batch", tags=["batch"])
    _include_router_if_available(app, admin_routes.router, prefix="/api/admin", tags=["admin"])
    _include_router_if_available(app, admin_routes.cache_router, prefix="/api/cache", tags=["cache"])
    _include_router_if_available(app, health_routes.router, tags=["health"])
    _include_router_if_available(app, discussion_routes.router, tags=["discussion"])
    _include_router_if_available(app, core_routes.router, tags=["core"])
    _include_router_if_available(app, memory_routes.router, tags=["memory"])
    _include_router_if_available(app, runtime_routes.router, tags=["runtime"])
    _include_router_if_available(app, websocket_routes.router, tags=["websocket"])
    _include_router_if_available(app, web_routes.router, tags=["web"])
    _include_router_if_available(app, skills_routes.router, tags=["skills"])
    _include_router_if_available(app, shared_knowledge_routes.router, tags=["shared-knowledge"])
    _include_router_if_available(app, tool_router_routes.router, tags=["tools"])
    _include_router_if_available(app, export_routes.router, tags=["export"])
    _include_router_if_available(app, cc_switch_routes.router, tags=["cc-switch"])

    if auth_middleware and config.auth.enabled:

        @app.middleware("http")
        async def auth_middleware_handler(request: Request, call_next):
            return await auth_middleware(request, call_next)

    if rate_limiter and config.rate_limit.enabled:
        from .rate_limiter import RateLimitMiddleware

        rate_limit_middleware = RateLimitMiddleware(rate_limiter)

        @app.middleware("http")
        async def rate_limit_middleware_handler(request: Request, call_next):
            return await rate_limit_middleware(request, call_next)

    if WEB_UI_DIR.exists():
        app.mount("/static", StaticFiles(directory=str(WEB_UI_DIR)), name="static")

    return app
