"""Compatibility entrypoint for legacy `create_api` imports.

Route implementation and app composition now live in `lib.gateway.app`.
"""
from __future__ import annotations

from typing import Any, Optional

from .app import create_app
from .gateway_config import GatewayConfig
from .request_queue import RequestQueue
from .retry import ReliabilityTracker
from .state_store import StateStore


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
    health_checker=None,
    backpressure=None,
    shared_knowledge: Optional[Any] = None,
    tool_index: Optional[Any] = None,
):
    """Backward-compatible wrapper around `create_app`."""
    return create_app(
        config=config,
        store=store,
        queue=queue,
        router_func=router_func,
        cache_manager=cache_manager,
        stream_manager=stream_manager,
        parallel_executor=parallel_executor,
        retry_executor=retry_executor,
        auth_middleware=auth_middleware,
        rate_limiter=rate_limiter,
        metrics=metrics,
        api_key_store=api_key_store,
        discussion_executor=discussion_executor,
        reliability_tracker=reliability_tracker,
        memory_middleware=memory_middleware,
        health_checker=health_checker,
        backpressure=backpressure,
        shared_knowledge=shared_knowledge,
        tool_index=tool_index,
    )
