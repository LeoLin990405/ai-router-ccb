"""Request processing helpers for ``GatewayServer``."""

from __future__ import annotations

import time
from typing import Any, Dict, Optional

from lib.common.errors import AuthError, BackendError, ProviderError
from lib.common.logging import get_logger

from .backends.base_backend import BackendResult
from .models import GatewayRequest, GatewayResponse, RequestStatus, WebSocketEvent
from .parallel import AggregationStrategy

logger = get_logger("gateway.server")


async def process_request(self, request: GatewayRequest) -> None:
    """
    Process a single request.

    Called by the async queue processor.
    Handles retry, fallback, caching, and parallel execution.
    """
    if request.metadata is None:
        request.metadata = {}
    request.metadata.setdefault("original_message", request.message)

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

    # === Memory Middleware: Pre-Request Hook ===
    if self.memory_middleware:
        try:
            # Convert GatewayRequest to dict for middleware
            request_dict = {
                "provider": request.provider,
                "message": request.message,
                "model": request.metadata.get("model"),
                "user_id": request.metadata.get("user_id", "default")
            }

            # Apply pre-request hook (context injection)
            enhanced_dict = await self.memory_middleware.pre_request(request_dict)

            # Fix Issue #8: Check if enhanced_dict is None
            if enhanced_dict is None:
                logger.warning("Memory pre_request returned None, using original request")
                enhanced_dict = request_dict

            # Update request message if context was injected
            if enhanced_dict.get("_memory_injected"):
                request.message = enhanced_dict["message"]
                request.metadata["_memory_injected"] = True
                request.metadata["_memory_count"] = enhanced_dict.get("_memory_count", 0)
                request.metadata["_system_context_injected"] = enhanced_dict.get("_system_context_injected", False)

        except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError):
            logger.exception("Memory pre-request hook error")

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
    except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError):
        logger.debug("Failed to broadcast request_processing event", exc_info=True)

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

        except AuthError as exc:
            logger.warning("Authentication failed for provider %s: %s", provider, exc)
            latency_ms = (time.time() - start_time) * 1000
            await self._handle_failure(
                request,
                BackendResult.fail(
                    str(exc),
                    metadata={"auth_error": True, "retryable": False},
                ),
                latency_ms,
            )
        except ProviderError as exc:
            if exc.retryable:
                logger.info("Retryable provider error for %s: %s", provider, exc)
            else:
                logger.error("Non-retryable provider error for %s: %s", provider, exc)
            latency_ms = (time.time() - start_time) * 1000
            await self._handle_failure(
                request,
                BackendResult.fail(
                    str(exc),
                    metadata={"retryable": exc.retryable},
                ),
                latency_ms,
            )
        except BackendError as exc:
            logger.error("Backend execution error for provider %s: %s", provider, exc)
            latency_ms = (time.time() - start_time) * 1000
            await self._handle_failure(
                request,
                BackendResult.fail(str(exc)),
                latency_ms,
            )
        except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError) as exc:
            logger.exception("Unexpected backend execution failure for provider %s", provider)
            latency_ms = (time.time() - start_time) * 1000
            error = BackendError(f"Unexpected backend execution error: {exc}")
            await self._handle_failure(
                request,
                BackendResult.fail(str(error)),
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
    except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError):
        logger.debug("Failed to broadcast request_processing event", exc_info=True)

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
            cache_message = request.message
            if request.metadata:
                cache_message = request.metadata.get("original_message", request.message)
            logger.debug("Saving parallel result to cache provider=%s message_hash=%s", result.selected_provider, hash(cache_message))
            self.cache_manager.put(
                result.selected_provider,
                cache_message,
                result.selected_response,
            )
            logger.debug("Saved parallel result to cache")
        else:
            logger.debug("Skipping parallel cache save cache_manager=%s provider=%s", self.cache_manager is not None, result.selected_provider)
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
    except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError):
        logger.debug("Failed to broadcast request status event", exc_info=True)
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

    # === Memory Middleware: Post-Response Hook ===
    if self.memory_middleware:
        try:
            # Reconstruct request dict for post-response hook
            request_dict = {
                "provider": request.provider,
                "message": request.metadata.get("original_message", request.message),
                "model": request.metadata.get("model"),
                "request_id": request.id,
                "_memory_injected": request.metadata.get("_memory_injected", False),
                "_memory_count": request.metadata.get("_memory_count", 0),
            }

            response_dict = {
                "response": result.response,
                "latency_ms": latency_ms,
                "tokens": result.tokens_used
            }

            # Apply post-response hook (conversation recording)
            await self.memory_middleware.post_response(request_dict, response_dict)

        except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError):
            logger.exception("Memory post-response hook error")

    # Cache the response
    if self.cache_manager and result.response:
        cache_message = request.message
        if request.metadata:
            cache_message = request.metadata.get("original_message", request.message)
        self.cache_manager.put(
            provider,
            cache_message,
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

    # Record token cost if tokens are available
    if result.tokens_used or (metadata and metadata.get("input_tokens")):
        input_tokens = metadata.get("input_tokens", 0) if metadata else 0
        output_tokens = metadata.get("output_tokens", 0) if metadata else 0
        # If only total tokens available, assume 30% input / 70% output ratio
        if result.tokens_used and not input_tokens:
            input_tokens = int(result.tokens_used * 0.3)
            output_tokens = result.tokens_used - input_tokens
        self.store.record_token_cost(
            provider=provider,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            request_id=request.id,
            model=request.metadata.get("model") if request.metadata else None,
        )

    # Broadcast WebSocket event (wrapped in try-except to prevent status overwrite)
    try:
        if self._app and hasattr(self._app.state, 'ws_manager'):
            # Send more content for monitoring (up to 1000 chars)
            resp_preview = result.response[:1000] if result.response and len(result.response) > 1000 else result.response
            thinking_preview = result.thinking[:500] if result.thinking and len(result.thinking) > 500 else result.thinking
            raw_preview = result.raw_output[:500] if result.raw_output and len(result.raw_output) > 500 else result.raw_output
            await self._app.state.ws_manager.broadcast(WebSocketEvent(
                type="request_completed",
                data={
                    "request_id": request.id,
                    "provider": provider,
                    "success": True,
                    "latency_ms": latency_ms,
                    "response": resp_preview,
                    "thinking": thinking_preview,
                    "raw_output": raw_preview,
                    "has_thinking": bool(result.thinking),
                    "has_raw_output": bool(result.raw_output),
                    "retry_info": retry_info,
                },
            ))
    except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError):
        logger.debug("Failed to broadcast request status event", exc_info=True)
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
    except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError):
        logger.debug("Failed to broadcast request status event", exc_info=True)
