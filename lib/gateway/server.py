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

from lib.common.errors import AuthError, BackendError, ProviderError
from lib.common.logging import get_logger

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
from .backends import BaseBackend, HTTPBackend, CLIBackend
from .backends.base_backend import BackendResult
from .server_requests import (
    process_request as process_request_impl,
    _process_single_request as process_single_request_impl,
    _process_parallel_request as process_parallel_request_impl,
    _handle_success as handle_success_impl,
    _handle_failure as handle_failure_impl,
)
from .server_runtime import (
    health_check_loop as health_check_loop_impl,
    cleanup_loop as cleanup_loop_impl,
    create_app as create_app_impl,
    start as start_impl,
    stop as stop_impl,
    run as run_impl,
)

# Import new modules
from .retry import RetryExecutor, RetryConfig, RetryState, ReliabilityTracker
from .cache import CacheManager, CacheConfig
from .streaming import StreamManager, StreamConfig
from .parallel import ParallelExecutor, ParallelConfig, AggregationStrategy
from .auth import AuthMiddleware, APIKeyStore
from .rate_limiter import RateLimiter, RateLimitMiddleware
from .metrics import GatewayMetrics
from .discussion import DiscussionExecutor

logger = get_logger("gateway.server")

# Import new v0.23 modules
try:
    from .health_checker import HealthChecker
    HEALTH_CHECKER_AVAILABLE = True
except ImportError:
    HEALTH_CHECKER_AVAILABLE = False

try:
    from .backpressure import BackpressureController, BackpressureConfig
    BACKPRESSURE_AVAILABLE = True
except ImportError:
    BACKPRESSURE_AVAILABLE = False

# Import Memory Middleware
try:
    from .middleware.memory_middleware import MemoryMiddleware
    MEMORY_MIDDLEWARE_AVAILABLE = True
except ImportError as e:
    logger.warning("Memory Middleware not available: %s", e)
    MEMORY_MIDDLEWARE_AVAILABLE = False

# Import v1.1 modules
try:
    from lib.knowledge.shared_knowledge import SharedKnowledgeService
    SHARED_KNOWLEDGE_AVAILABLE = True
except ImportError:
    SHARED_KNOWLEDGE_AVAILABLE = False

try:
    from lib.skills.tool_index import ToolIndex
    from lib.skills.tool_index_builder import build_index
    TOOL_INDEX_AVAILABLE = True
except ImportError:
    TOOL_INDEX_AVAILABLE = False


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
        self.discussion_executor: Optional[DiscussionExecutor] = None
        self.reliability_tracker: Optional[ReliabilityTracker] = None

        # Security and observability
        self.auth_middleware: Optional[AuthMiddleware] = None
        self.api_key_store: Optional[APIKeyStore] = None
        self.rate_limiter: Optional[RateLimiter] = None
        self.metrics: Optional[GatewayMetrics] = None

        # Memory Middleware
        self.memory_middleware: Optional[MemoryMiddleware] = None

        # Health Checker (v0.23)
        self.health_checker: Optional["HealthChecker"] = None

        # Backpressure Controller (v0.23)
        self.backpressure: Optional["BackpressureController"] = None

        # v1.1 services
        self.shared_knowledge: Optional["SharedKnowledgeService"] = None
        self.tool_index: Optional["ToolIndex"] = None

        self._init_advanced_features()
        self._init_security_features()
        self._init_memory_features()  # 新增
        self._init_v11_services()
        self._init_health_and_backpressure()  # v0.23

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
            except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError):
                logger.exception("Failed to initialize backend for %s", name)

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

            # Reliability tracker powers /api/providers/reliability endpoints
            self.reliability_tracker = ReliabilityTracker()

        # Discussion executor (always enabled if backends available)
        if self.backends:
            self.discussion_executor = DiscussionExecutor(
                store=self.store,
                backends=self.backends,
                gateway_config=self.config,
            )

    def _init_security_features(self) -> None:
        """Initialize security and observability features."""
        # Metrics (always enabled for observability)
        self.metrics = GatewayMetrics()

    def _init_memory_features(self) -> None:
        """Initialize memory middleware for context injection and recording."""
        if MEMORY_MIDDLEWARE_AVAILABLE:
            try:
                self.memory_middleware = MemoryMiddleware()
                logger.info("Memory Middleware initialized successfully")
            except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError):
                logger.exception("Failed to initialize Memory Middleware")
                self.memory_middleware = None
        else:
            logger.info("Memory Middleware not available")

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


    def _init_v11_services(self) -> None:
        """Initialize Shared Knowledge and Tool Index services (v1.1)."""
        if SHARED_KNOWLEDGE_AVAILABLE:
            try:
                self.shared_knowledge = SharedKnowledgeService(
                    db_path=str(self.store.db_path),
                    memory=getattr(self.memory_middleware, "memory", None),
                    knowledge_client=getattr(self.memory_middleware, "_knowledge_client", None),
                    obsidian_search=getattr(self.memory_middleware, "_obsidian_search", None),
                )
                logger.info("Shared Knowledge service initialized successfully")

                if self.memory_middleware:
                    setattr(self.memory_middleware, "_shared_knowledge", self.shared_knowledge)
            except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError):
                logger.exception("Failed to initialize Shared Knowledge service")
                self.shared_knowledge = None
        else:
            logger.info("Shared Knowledge service not available")

        if TOOL_INDEX_AVAILABLE:
            try:
                self.tool_index = ToolIndex()
                if not self.tool_index._entries:
                    try:
                        entries = build_index()
                        self.tool_index.set_entries(entries)
                    except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError):
                        logger.exception("Failed to build tool index at startup")
                logger.info("Tool index initialized successfully")
            except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError):
                logger.exception("Failed to initialize Tool Index")
                self.tool_index = None
        else:
            logger.info("Tool Index not available")

    def _init_health_and_backpressure(self) -> None:
        """Initialize health checker and backpressure controller (v0.23)."""
        # Health Checker
        if HEALTH_CHECKER_AVAILABLE:
            try:
                health_cfg = self.config.health_check or {}
                enabled = health_cfg.get("enabled", True)
                if enabled is False:
                    self.health_checker = None
                    logger.info("Health Checker disabled by config")
                else:
                    def _num(value, default):
                        try:
                            return type(default)(value)
                        except (TypeError, ValueError):
                            return default

                    check_interval_s = _num(health_cfg.get("interval_s", 30.0), 30.0)
                    failure_threshold = _num(health_cfg.get("failure_threshold", 3), 3)
                    recovery_threshold = _num(health_cfg.get("recovery_threshold", 2), 2)
                    check_timeout_s = _num(health_cfg.get("timeout_s", 15.0), 15.0)

                    self.health_checker = HealthChecker(
                        check_interval_s=check_interval_s,
                        failure_threshold=failure_threshold,
                        recovery_threshold=recovery_threshold,
                        check_timeout_s=check_timeout_s,
                    )

                    provider_overrides = health_cfg.get("provider_overrides", {})
                    if not isinstance(provider_overrides, dict):
                        provider_overrides = {}

                    # Register all backends with overrides
                    for name, backend in self.backends.items():
                        override = provider_overrides.get(name, {})
                        if isinstance(override, dict):
                            if override.get("enabled") is False:
                                continue
                            if "timeout_s" in override:
                                try:
                                    self.health_checker.set_provider_timeout(name, float(override["timeout_s"]))
                                except (TypeError, ValueError):
                                    logger.debug("Invalid health-check timeout override for %s", name, exc_info=True)
                        self.health_checker.register_provider(name, backend)

                    logger.info("Health Checker initialized successfully")
            except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError):
                logger.exception("Failed to initialize Health Checker")
                self.health_checker = None
        else:
            logger.info("Health Checker not available")

        # Backpressure Controller
        if BACKPRESSURE_AVAILABLE:
            try:
                bp_config = BackpressureConfig(
                    min_concurrent=2,
                    max_concurrent=self.config.max_concurrent_requests * 2,
                    initial_concurrent=self.config.max_concurrent_requests,
                    queue_depth_low=10,
                    queue_depth_high=50,
                    queue_depth_critical=100,
                )
                self.backpressure = BackpressureController(
                    config=bp_config,
                    queue_getter=lambda: self.queue.get_queue_depth(),
                    processing_getter=lambda: self.queue.get_processing_count(),
                )

                # Set callback to adjust queue max_concurrent
                def on_limit_change(old_limit: int, new_limit: int):
                    self.queue.max_concurrent = new_limit
                    logger.info("Backpressure adjusted max_concurrent: %s -> %s", old_limit, new_limit)

                self.backpressure.set_limit_change_callback(on_limit_change)
                logger.info("Backpressure Controller initialized successfully")
            except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError):
                logger.exception("Failed to initialize Backpressure Controller")
                self.backpressure = None
        else:
            logger.info("Backpressure Controller not available")

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
        return await process_request_impl(self, request)

    async def _process_single_request(self, request: GatewayRequest) -> None:
        return await process_single_request_impl(self, request)

    async def _process_parallel_request(self, request: GatewayRequest) -> None:
        return await process_parallel_request_impl(self, request)

    async def _handle_success(
        self,
        request: GatewayRequest,
        result: BackendResult,
        latency_ms: float,
        retry_info: Optional[Dict[str, Any]] = None,
    ) -> None:
        return await handle_success_impl(self, request, result, latency_ms, retry_info)

    async def _handle_failure(
        self,
        request: GatewayRequest,
        result: BackendResult,
        latency_ms: float,
        retry_info: Optional[Dict[str, Any]] = None,
    ) -> None:
        return await handle_failure_impl(self, request, result, latency_ms, retry_info)

    async def health_check_loop(self) -> None:
        return await health_check_loop_impl(self)

    async def cleanup_loop(self) -> None:
        return await cleanup_loop_impl(self)

    def create_app(self):
        return create_app_impl(self)

    async def start(self) -> None:
        return await start_impl(self)

    async def stop(self) -> None:
        return await stop_impl(self)

    def run(self, host: Optional[str] = None, port: Optional[int] = None) -> int:
        return run_impl(self, host, port)


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
