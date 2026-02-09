"""Lifecycle helpers for ``GatewayServer``."""

from __future__ import annotations

import asyncio
import time
from typing import Optional

from lib.common.logging import get_logger

from .app import create_app as build_app
from .models import ProviderInfo
from .request_queue import AsyncRequestQueue

logger = get_logger("gateway.server")


async def health_check_loop(self) -> None:
    """Periodically check provider health."""
    while self._running:
        for name, backend in self.backends.items():
            try:
                status = await backend.check_health()
                provider_config = self.config.providers.get(name)
                if provider_config:
                    self.store.update_provider_status(
                        ProviderInfo(
                            name=name,
                            backend_type=provider_config.backend_type,
                            status=status,
                            queue_depth=self.queue.get_queue_depth(name),
                            last_check=time.time(),
                            enabled=provider_config.enabled,
                        )
                    )
            except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError):
                logger.debug("Provider health check loop error for %s", name, exc_info=True)

        await asyncio.sleep(60)


async def cleanup_loop(self) -> None:
    """Periodically clean up old data."""
    while self._running:
        try:
            self.store.cleanup_old_requests(self.config.request_ttl_hours)
            self.store.cleanup_old_metrics(168)
            if self.cache_manager:
                self.cache_manager.cleanup_expired()
        except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError):
            logger.exception("Cleanup loop error")

        await asyncio.sleep(3600)


def create_app(self):
    """Create the FastAPI application."""
    self._app = build_app(
        config=self.config,
        store=self.store,
        queue=self.queue,
        router_func=self.route,
        cache_manager=self.cache_manager,
        stream_manager=self.stream_manager,
        parallel_executor=self.parallel_executor,
        retry_executor=self.retry_executor,
        auth_middleware=self.auth_middleware,
        rate_limiter=self.rate_limiter,
        metrics=self.metrics,
        api_key_store=self.api_key_store,
        discussion_executor=self.discussion_executor,
        reliability_tracker=self.reliability_tracker,
        memory_middleware=self.memory_middleware,
        health_checker=self.health_checker,
        backpressure=self.backpressure,
        shared_knowledge=self.shared_knowledge,
        tool_index=self.tool_index,
    )

    self._app.state.backends = self.backends

    if self.discussion_executor and hasattr(self._app.state, "ws_manager"):
        self.discussion_executor.ws_broadcast = self._app.state.ws_manager.broadcast

    return self._app


async def start(self) -> None:
    """Start the gateway server."""
    self._running = True
    self._start_time = time.time()

    self.async_queue = AsyncRequestQueue(self.queue)
    await self.async_queue.start(self.process_request)

    asyncio.create_task(self.health_check_loop())
    asyncio.create_task(self.cleanup_loop())

    if self.health_checker:
        await self.health_checker.start()

    if self.backpressure:
        await self.backpressure.start()

    logger.info("Gateway server started")
    logger.info("Retry: %s", "enabled" if self.config.retry.enabled else "disabled")
    logger.info("Cache: %s", "enabled" if self.config.cache.enabled else "disabled")
    logger.info("Streaming: %s", "enabled" if self.config.streaming.enabled else "disabled")
    logger.info("Parallel: %s", "enabled" if self.config.parallel.enabled else "disabled")
    logger.info("Discussion: %s", "enabled" if self.discussion_executor else "disabled")
    logger.info("Auth: %s", "enabled" if self.config.auth and self.config.auth.enabled else "disabled")
    logger.info("Rate Limit: %s", "enabled" if self.config.rate_limit and self.config.rate_limit.enabled else "disabled")
    logger.info("Health Checker: %s", "enabled" if self.health_checker else "disabled")
    logger.info("Backpressure: %s", "enabled" if self.backpressure else "disabled")
    logger.info("Shared Knowledge: %s", "enabled" if self.shared_knowledge else "disabled")
    logger.info("Tool Index: %s", "enabled" if self.tool_index else "disabled")
    logger.info("Metrics: enabled")


async def stop(self) -> None:
    """Stop the gateway server."""
    self._running = False

    if self.async_queue:
        await self.async_queue.stop()

    if self.health_checker:
        await self.health_checker.stop()

    if self.backpressure:
        await self.backpressure.stop()

    for backend in self.backends.values():
        try:
            await backend.shutdown()
        except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError):
            logger.debug("Backend shutdown failed", exc_info=True)

    logger.info("Gateway server stopped")


def run(self, host: Optional[str] = None, port: Optional[int] = None) -> int:
    """Run the gateway server."""
    try:
        import uvicorn
    except ImportError:
        logger.error("uvicorn is required. Install with: pip install uvicorn")
        return 1

    host = host or self.config.host
    port = port or self.config.port

    app = self.create_app()

    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def lifespan(_app):
        await self.start()
        yield
        await self.stop()

    app.router.lifespan_context = lifespan

    logger.info("Starting CCB Gateway at http://%s:%s", host, port)
    logger.info("Web UI: http://%s:%s/", host, port)
    logger.info("API docs: http://%s:%s/docs", host, port)
    logger.info("Metrics: http://%s:%s/metrics", host, port)

    uvicorn.run(app, host=host, port=port, log_level=self.config.log_level.lower())
    return 0
