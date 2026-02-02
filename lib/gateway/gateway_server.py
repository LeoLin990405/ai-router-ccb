"""
Gateway Server - Main Entry Point for CCB Gateway.

Orchestrates all gateway components and runs the server.
"""
from __future__ import annotations

import asyncio
import signal
import sys
import time
from pathlib import Path
from typing import Optional, Dict, Any

from .models import (
    RequestStatus,
    GatewayRequest,
    GatewayResponse,
    ProviderInfo,
    ProviderStatus,
    WebSocketEvent,
)
from .state_store import StateStore
from .request_queue import RequestQueue, AsyncRequestQueue
from .gateway_config import GatewayConfig
from .gateway_api import create_api
from .backends import BaseBackend, BackendResult, HTTPBackend, CLIBackend
from .backends.base_backend import BackendResult

# Import new modules
from .retry import RetryExecutor, RetryConfig, RetryState
from .cache import CacheManager, CacheConfig
from .streaming import StreamManager, StreamConfig
from .parallel import ParallelExecutor, ParallelConfig, AggregationStrategy
from .auth import AuthMiddleware, APIKeyStore
from .rate_limiter import RateLimiter, RateLimitMiddleware
from .metrics import GatewayMetrics


class GatewayServer:
    """
    Main Gateway Server.

    Coordinates:
    - FastAPI application for REST/WebSocket
    - Request queue processing
    - Backend management
    - Health monitoring
    - Retry and fallback logic
    - Response caching
    - Streaming support
    - Parallel execution
    """

    def __init__(self, config: Optional[GatewayConfig] = None):
        """
        Initialize the gateway server.

        Args:
            config: Gateway configuration. Loads from default if not provided.
        """
        self.config = config or GatewayConfig.load()
        self.store = StateStore(str(self.config.get_db_path()))
        self.queue = RequestQueue(
            self.store,
            max_size=self.config.max_queue_size,
            max_concurrent=self.config.max_concurrent_requests,
        )
        self.async_queue: Optional[AsyncRequestQueue] = None

        # Backend instances
        self.backends: Dict[str, BaseBackend] = {}
        self._init_backends()

        # Advanced feature managers
        self.cache_manager: Optional[CacheManager] = None
        self.stream_manager: Optional[StreamManager] = None
        self.parallel_executor: Optional[ParallelExecutor] = None
        self.retry_executor: Optional[RetryExecutor] = None

        # Security and observability
        self.auth_middleware: Optional[AuthMiddleware] = None
        self.api_key_store: Optional[APIKeyStore] = None
        self.rate_limiter: Optional[RateLimiter] = None
        self.metrics: Optional[GatewayMetrics] = None

        self._init_advanced_features()
        self._init_security_features()

        # Router (lazy import to avoid circular deps)
        self._router = None

        # Server state
        self._running = False
        self._start_time: Optional[float] = None
        self._app = None

    def _init_backends(self) -> None:
        """Initialize backend instances for each provider."""
        from .models import BackendType

        for name, pconfig in self.config.providers.items():
            if not pconfig.enabled:
                continue

            try:
                if pconfig.backend_type == BackendType.HTTP_API:
                    self.backends[name] = HTTPBackend(pconfig)
                elif pconfig.backend_type == BackendType.CLI_EXEC:
                    self.backends[name] = CLIBackend(pconfig)
                # FIFO and Terminal backends can be added later
            except Exception as e:
                print(f"Warning: Failed to initialize backend for {name}: {e}")

    def _init_advanced_features(self) -> None:
        """Initialize advanced feature managers."""
        # Cache manager
        if self.config.cache.enabled:
            self.cache_manager = CacheManager(self.store, self.config.cache)

        # Stream manager
        if self.config.streaming.enabled:
            self.stream_manager = StreamManager(self.config.streaming)

        # Parallel executor
        if self.config.parallel.enabled:
            parallel_config = ParallelConfig(
                enabled=self.config.parallel.enabled,
                default_strategy=AggregationStrategy(self.config.parallel.default_strategy),
                timeout_s=self.config.parallel.timeout_s,
                max_concurrent=self.config.parallel.max_concurrent,
            )
            self.parallel_executor = ParallelExecutor(parallel_config, self.backends)

        # Retry executor
        if self.config.retry.enabled:
            retry_config = RetryConfig(
                enabled=self.config.retry.enabled,
                max_retries=self.config.retry.max_retries,
                base_delay_s=self.config.retry.base_delay_s,
                max_delay_s=self.config.retry.max_delay_s,
                fallback_enabled=self.config.retry.fallback_enabled,
                fallback_chains=self.config.retry.fallback_chains,
            )
            self.retry_executor = RetryExecutor(
                retry_config,
                self.backends,
                list(self.backends.keys()),
            )

    def _init_security_features(self) -> None:
        """Initialize security and observability features."""
        # Metrics (always enabled for observability)
        self.metrics = GatewayMetrics()

        # API Key store (always created, auth can be toggled)
        self.api_key_store = APIKeyStore(self.store)

        # Auth middleware
        if self.config.auth:
            self.auth_middleware = AuthMiddleware(
                self.config.auth,
                self.api_key_store,
            )

        # Rate limiter
        if self.config.rate_limit:
            self.rate_limiter = RateLimiter(self.config.rate_limit)

    def _get_router(self):
        """Get or create the router instance."""
        if self._router is None:
            try:
                # Import from parent lib directory
                import sys
                lib_dir = Path(__file__).parent.parent
                if str(lib_dir) not in sys.path:
                    sys.path.insert(0, str(lib_dir))
                from unified_router import UnifiedRouter
                self._router = UnifiedRouter()
            except ImportError:
                self._router = None
        return self._router

    def route(self, message: str) -> Any:
        """Route a message to determine the best provider."""
        router = self._get_router()
        if router:
            return router.route(message)
        # Fallback: return a simple object with default provider
        class SimpleDecision:
            def __init__(self, provider):
                self.provider = provider
        return SimpleDecision(self.config.default_provider)

    async def process_request(self, request: GatewayRequest) -> None:
        """
        Process a single request.

        Called by the async queue processor.
        Handles retry, fallback, caching, and parallel execution.
        """
        # Check if this is a parallel request
        is_parallel = request.metadata and request.metadata.get("parallel", False)

        if is_parallel:
            await self._process_parallel_request(request)
        else:
            await self._process_single_request(request)

    async def _process_single_request(self, request: GatewayRequest) -> None:
        """Process a single (non-parallel) request with retry and fallback."""
        provider = request.provider
        start_time = time.time()

        # Broadcast processing started event (wrapped in try-except)
        try:
            if self._app and hasattr(self._app.state, 'ws_manager'):
                await self._app.state.ws_manager.broadcast(WebSocketEvent(
                    type="request_processing",
                    data={
                        "request_id": request.id,
                        "provider": provider,
                    },
                ))
        except Exception:
            pass  # Don't let WebSocket errors affect request processing

        # Use retry executor if available
        if self.retry_executor and self.config.retry.enabled:
            result, retry_state = await self.retry_executor.execute_with_retry(request)
            latency_ms = (time.time() - start_time) * 1000

            # Build retry info for metadata
            retry_info = retry_state.get_summary() if retry_state.total_attempts > 1 else None

            if result.success:
                await self._handle_success(request, result, latency_ms, retry_info)
            else:
                await self._handle_failure(request, result, latency_ms, retry_info)
        else:
            # Direct execution without retry
            backend = self.backends.get(provider)

            if not backend:
                self.store.update_request_status(request.id, RequestStatus.FAILED)
                self.store.save_response(GatewayResponse(
                    request_id=request.id,
                    status=RequestStatus.FAILED,
                    error=f"No backend available for provider: {provider}",
                ))
                return

            try:
                result = await backend.execute(request)
                latency_ms = (time.time() - start_time) * 1000

                if result.success:
                    await self._handle_success(request, result, latency_ms)
                else:
                    await self._handle_failure(request, result, latency_ms)

            except Exception as e:
                latency_ms = (time.time() - start_time) * 1000
                await self._handle_failure(
                    request,
                    BackendResult.fail(str(e)),
                    latency_ms,
                )

    async def _process_parallel_request(self, request: GatewayRequest) -> None:
        """Process a parallel request across multiple providers."""
        if not self.parallel_executor:
            self.store.update_request_status(request.id, RequestStatus.FAILED)
            self.store.save_response(GatewayResponse(
                request_id=request.id,
                status=RequestStatus.FAILED,
                error="Parallel execution not enabled",
            ))
            return

        providers = request.metadata.get("providers", [])
        strategy_str = request.metadata.get("aggregation_strategy", "first_success")

        try:
            strategy = AggregationStrategy(strategy_str)
        except ValueError:
            strategy = AggregationStrategy.FIRST_SUCCESS

        start_time = time.time()

        # Broadcast parallel processing started (wrapped in try-except)
        try:
            if self._app and hasattr(self._app.state, 'ws_manager'):
                await self._app.state.ws_manager.broadcast(WebSocketEvent(
                    type="request_processing",
                    data={
                        "request_id": request.id,
                        "providers": providers,
                        "parallel": True,
                        "strategy": strategy.value,
                    },
                ))
        except Exception:
            pass  # Don't let WebSocket errors affect request processing

        # Execute in parallel
        result = await self.parallel_executor.execute_parallel(request, providers, strategy)
        latency_ms = (time.time() - start_time) * 1000

        if result.success:
            self.store.update_request_status(request.id, RequestStatus.COMPLETED)
            self.store.save_response(GatewayResponse(
                request_id=request.id,
                status=RequestStatus.COMPLETED,
                response=result.selected_response,
                provider=result.selected_provider,
                latency_ms=latency_ms,
                metadata={
                    "parallel": True,
                    "strategy": strategy.value,
                    "all_responses": {k: v.to_dict() for k, v in result.all_responses.items()},
                },
            ))
            self.queue.mark_completed(request.id, response=result.selected_response)

            # Cache the selected response
            if self.cache_manager and result.selected_provider:
                self.cache_manager.put(
                    result.selected_provider,
                    request.message,
                    result.selected_response,
                )
        else:
            self.store.update_request_status(request.id, RequestStatus.FAILED)
            self.store.save_response(GatewayResponse(
                request_id=request.id,
                status=RequestStatus.FAILED,
                error=result.error,
                latency_ms=latency_ms,
                metadata={
                    "parallel": True,
                    "strategy": strategy.value,
                    "all_responses": {k: v.to_dict() for k, v in result.all_responses.items()},
                },
            ))
            self.queue.mark_completed(request.id, error=result.error)

        # Broadcast completion (wrapped in try-except to prevent status overwrite)
        try:
            if self._app and hasattr(self._app.state, 'ws_manager'):
                await self._app.state.ws_manager.broadcast(WebSocketEvent(
                    type="request_completed" if result.success else "request_failed",
                    data={
                        "request_id": request.id,
                        "success": result.success,
                        "parallel": True,
                        "selected_provider": result.selected_provider,
                        "latency_ms": latency_ms,
                    },
                ))
        except Exception:
            pass  # Don't let WebSocket errors affect request status

    async def _handle_success(
        self,
        request: GatewayRequest,
        result: BackendResult,
        latency_ms: float,
        retry_info: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Handle successful request completion."""
        provider = request.provider

        self.store.update_request_status(request.id, RequestStatus.COMPLETED)

        metadata = result.metadata or {}
        if retry_info:
            metadata["retry_info"] = retry_info

        self.store.save_response(GatewayResponse(
            request_id=request.id,
            status=RequestStatus.COMPLETED,
            response=result.response,
            provider=provider,
            latency_ms=latency_ms,
            tokens_used=result.tokens_used,
            metadata=metadata,
            thinking=result.thinking,
            raw_output=result.raw_output,
        ))
        self.queue.mark_completed(request.id, response=result.response)

        # Cache the response
        if self.cache_manager and result.response:
            self.cache_manager.put(
                provider,
                request.message,
                result.response,
                tokens_used=result.tokens_used,
            )

        # Record success metric
        self.store.record_metric(
            provider=provider,
            event_type="request_completed",
            request_id=request.id,
            latency_ms=latency_ms,
            success=True,
        )

        # Broadcast WebSocket event (wrapped in try-except to prevent status overwrite)
        try:
            if self._app and hasattr(self._app.state, 'ws_manager'):
                resp_preview = result.response[:100] if result.response and len(result.response) > 100 else result.response
                await self._app.state.ws_manager.broadcast(WebSocketEvent(
                    type="request_completed",
                    data={
                        "request_id": request.id,
                        "provider": provider,
                        "success": True,
                        "latency_ms": latency_ms,
                        "response": resp_preview,
                        "retry_info": retry_info,
                    },
                ))
        except Exception:
            pass  # Don't let WebSocket errors affect request status

    async def _handle_failure(
        self,
        request: GatewayRequest,
        result: BackendResult,
        latency_ms: float,
        retry_info: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Handle request failure."""
        provider = request.provider

        self.store.update_request_status(request.id, RequestStatus.FAILED)

        metadata = result.metadata or {}
        if retry_info:
            metadata["retry_info"] = retry_info

        self.store.save_response(GatewayResponse(
            request_id=request.id,
            status=RequestStatus.FAILED,
            error=result.error,
            provider=provider,
            latency_ms=latency_ms,
            metadata=metadata,
        ))
        self.queue.mark_completed(request.id, error=result.error)

        # Record failure metric
        self.store.record_metric(
            provider=provider,
            event_type="request_failed",
            request_id=request.id,
            latency_ms=latency_ms,
            success=False,
            error=result.error,
        )

        # Broadcast WebSocket event (wrapped in try-except to prevent status overwrite)
        try:
            if self._app and hasattr(self._app.state, 'ws_manager'):
                error_preview = result.error[:100] if result.error and len(result.error) > 100 else result.error
                await self._app.state.ws_manager.broadcast(WebSocketEvent(
                    type="request_failed",
                    data={
                        "request_id": request.id,
                        "provider": provider,
                        "success": False,
                        "latency_ms": latency_ms,
                        "error": error_preview,
                        "retry_info": retry_info,
                    },
                ))
        except Exception:
            pass  # Don't let WebSocket errors affect request status

    async def health_check_loop(self) -> None:
        """Periodically check provider health."""
        while self._running:
            for name, backend in self.backends.items():
                try:
                    status = await backend.check_health()
                    pconfig = self.config.providers.get(name)
                    if pconfig:
                        self.store.update_provider_status(ProviderInfo(
                            name=name,
                            backend_type=pconfig.backend_type,
                            status=status,
                            queue_depth=self.queue.get_queue_depth(name),
                            last_check=time.time(),
                            enabled=pconfig.enabled,
                        ))
                except Exception:
                    pass

            await asyncio.sleep(60)  # Check every minute

    async def cleanup_loop(self) -> None:
        """Periodically clean up old data."""
        while self._running:
            try:
                # Clean up old requests
                self.store.cleanup_old_requests(self.config.request_ttl_hours)
                # Clean up old metrics
                self.store.cleanup_old_metrics(168)  # 7 days
                # Clean up expired cache entries
                if self.cache_manager:
                    self.cache_manager.cleanup_expired()
            except Exception:
                pass

            await asyncio.sleep(3600)  # Run every hour

    def create_app(self):
        """Create the FastAPI application."""
        self._app = create_api(
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
        )
        # Store backends on app for streaming access
        self._app.state.backends = self.backends
        return self._app

    async def start(self) -> None:
        """Start the gateway server."""
        self._running = True
        self._start_time = time.time()

        # Start async queue processor
        self.async_queue = AsyncRequestQueue(self.queue)
        await self.async_queue.start(self.process_request)

        # Start background tasks
        asyncio.create_task(self.health_check_loop())
        asyncio.create_task(self.cleanup_loop())

        print(f"Gateway server started")
        print(f"  Retry: {'enabled' if self.config.retry.enabled else 'disabled'}")
        print(f"  Cache: {'enabled' if self.config.cache.enabled else 'disabled'}")
        print(f"  Streaming: {'enabled' if self.config.streaming.enabled else 'disabled'}")
        print(f"  Parallel: {'enabled' if self.config.parallel.enabled else 'disabled'}")
        print(f"  Auth: {'enabled' if self.config.auth and self.config.auth.enabled else 'disabled'}")
        print(f"  Rate Limit: {'enabled' if self.config.rate_limit and self.config.rate_limit.enabled else 'disabled'}")
        print(f"  Metrics: enabled")

    async def stop(self) -> None:
        """Stop the gateway server."""
        self._running = False

        # Stop queue processor
        if self.async_queue:
            await self.async_queue.stop()

        # Shutdown backends
        for backend in self.backends.values():
            try:
                await backend.shutdown()
            except Exception:
                pass

        print("Gateway server stopped")

    def run(self, host: Optional[str] = None, port: Optional[int] = None) -> int:
        """
        Run the gateway server.

        Args:
            host: Override host from config
            port: Override port from config

        Returns:
            Exit code
        """
        try:
            import uvicorn
        except ImportError:
            print("Error: uvicorn is required. Install with: pip install uvicorn")
            return 1

        host = host or self.config.host
        port = port or self.config.port

        app = self.create_app()

        # Use lifespan context manager for startup/shutdown
        from contextlib import asynccontextmanager

        @asynccontextmanager
        async def lifespan(app):
            # Startup
            await self.start()
            yield
            # Shutdown
            await self.stop()

        # Replace app's lifespan
        app.router.lifespan_context = lifespan

        print(f"Starting CCB Gateway at http://{host}:{port}")
        print(f"  Web UI: http://{host}:{port}/")
        print(f"  API docs: http://{host}:{port}/docs")
        print(f"  Metrics: http://{host}:{port}/metrics")

        uvicorn.run(app, host=host, port=port, log_level=self.config.log_level.lower())
        return 0


def run_gateway(
    config_path: Optional[str] = None,
    host: Optional[str] = None,
    port: Optional[int] = None,
) -> int:
    """
    Run the gateway server.

    Args:
        config_path: Path to configuration file
        host: Override host
        port: Override port

    Returns:
        Exit code
    """
    config = GatewayConfig.load(config_path)
    server = GatewayServer(config)
    return server.run(host, port)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="CCB Gateway Server")
    parser.add_argument("--config", "-c", help="Path to configuration file")
    parser.add_argument("--host", "-H", help="Host to bind to")
    parser.add_argument("--port", "-p", type=int, help="Port to bind to")

    args = parser.parse_args()

    sys.exit(run_gateway(
        config_path=args.config,
        host=args.host,
        port=args.port,
    ))
