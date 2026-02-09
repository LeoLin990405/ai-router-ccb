
"""
Parallel Execution for CCB Gateway.

Provides parallel query execution across multiple providers.
"""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Dict, Any, List, TYPE_CHECKING

from .parallel_utils import compare_responses, parse_provider_spec

if TYPE_CHECKING:
    from .backends.base_backend import BackendResult
    from .models import GatewayRequest


class AggregationStrategy(Enum):
    """Strategy for aggregating parallel responses."""
    FIRST_SUCCESS = "first_success"  # Return first successful response
    FASTEST = "fastest"  # Return fastest response (success or fail)
    ALL = "all"  # Return all responses
    CONSENSUS = "consensus"  # Return most common response (by similarity)
    BEST_QUALITY = "best_quality"  # Return response with best quality indicators


@dataclass
class ParallelConfig:
    """Configuration for parallel execution."""
    enabled: bool = True
    default_strategy: AggregationStrategy = AggregationStrategy.FIRST_SUCCESS
    timeout_s: float = 60.0  # Timeout for parallel execution
    min_responses: int = 1  # Minimum responses before returning (for FIRST_SUCCESS)
    max_concurrent: int = 5  # Maximum concurrent requests


@dataclass
class ProviderResponse:
    """Response from a single provider in parallel execution."""
    provider: str
    success: bool
    response: Optional[str] = None
    error: Optional[str] = None
    latency_ms: float = 0.0
    tokens_used: Optional[int] = None
    metadata: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "provider": self.provider,
            "success": self.success,
            "response": self.response,
            "error": self.error,
            "latency_ms": self.latency_ms,
            "tokens_used": self.tokens_used,
            "metadata": self.metadata,
        }


@dataclass
class ParallelResult:
    """Result of parallel execution across multiple providers."""
    request_id: str
    strategy: AggregationStrategy
    selected_provider: Optional[str] = None
    selected_response: Optional[str] = None
    all_responses: Dict[str, ProviderResponse] = field(default_factory=dict)
    total_latency_ms: float = 0.0
    success: bool = False
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "request_id": self.request_id,
            "strategy": self.strategy.value,
            "selected_provider": self.selected_provider,
            "selected_response": self.selected_response,
            "all_responses": {k: v.to_dict() for k, v in self.all_responses.items()},
            "total_latency_ms": self.total_latency_ms,
            "success": self.success,
            "error": self.error,
        }


class ParallelExecutor:
    """
    Executes requests in parallel across multiple providers.

    Usage:
        executor = ParallelExecutor(config, backends)
        result = await executor.execute_parallel(request, providers, strategy)
    """

    def __init__(
        self,
        config: ParallelConfig,
        backends: Dict[str, Any],
    ):
        """
        Initialize the parallel executor.

        Args:
            config: Parallel execution configuration
            backends: Dict of provider name -> backend instance
        """
        self.config = config
        self.backends = backends

    async def execute_parallel(
        self,
        request: "GatewayRequest",
        providers: List[str],
        strategy: Optional[AggregationStrategy] = None,
    ) -> ParallelResult:
        """
        Execute request in parallel across multiple providers.

        Args:
            request: The request to execute
            providers: List of provider names
            strategy: Aggregation strategy (defaults to config default)

        Returns:
            ParallelResult with aggregated responses
        """
        strategy = strategy or self.config.default_strategy
        start_time = time.time()

        result = ParallelResult(
            request_id=request.id,
            strategy=strategy,
        )

        # Filter to available providers
        available_providers = [p for p in providers if p in self.backends]

        if not available_providers:
            result.error = f"No available providers from: {providers}"
            return result

        # Limit concurrent requests
        available_providers = available_providers[:self.config.max_concurrent]

        # Execute based on strategy
        if strategy == AggregationStrategy.FIRST_SUCCESS:
            result = await self._execute_first_success(request, available_providers, result)
        elif strategy == AggregationStrategy.FASTEST:
            result = await self._execute_fastest(request, available_providers, result)
        elif strategy == AggregationStrategy.ALL:
            result = await self._execute_all(request, available_providers, result)
        elif strategy == AggregationStrategy.CONSENSUS:
            result = await self._execute_consensus(request, available_providers, result)
        elif strategy == AggregationStrategy.BEST_QUALITY:
            result = await self._execute_best_quality(request, available_providers, result)

        result.total_latency_ms = (time.time() - start_time) * 1000
        return result

    async def _execute_single(
        self,
        request: "GatewayRequest",
        provider: str,
    ) -> ProviderResponse:
        """Execute request on a single provider."""
        from .backends.base_backend import BackendResult

        backend = self.backends.get(provider)
        if not backend:
            return ProviderResponse(
                provider=provider,
                success=False,
                error=f"Backend not found: {provider}",
            )

        start_time = time.time()

        try:
            # Create a copy of request with this provider
            request_copy = GatewayRequest(
                id=request.id,
                provider=provider,
                message=request.message,
                status=request.status,
                created_at=request.created_at,
                updated_at=request.updated_at,
                priority=request.priority,
                timeout_s=request.timeout_s,
                metadata=request.metadata,
            )

            result = await asyncio.wait_for(
                backend.execute(request_copy),
                timeout=self.config.timeout_s,
            )

            latency_ms = (time.time() - start_time) * 1000

            return ProviderResponse(
                provider=provider,
                success=result.success,
                response=result.response,
                error=result.error,
                latency_ms=latency_ms,
                tokens_used=result.tokens_used,
                metadata=result.metadata,
            )

        except asyncio.TimeoutError:
            return ProviderResponse(
                provider=provider,
                success=False,
                error=f"Timeout after {self.config.timeout_s}s",
                latency_ms=(time.time() - start_time) * 1000,
            )
        except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError) as e:
            return ProviderResponse(
                provider=provider,
                success=False,
                error=str(e),
                latency_ms=(time.time() - start_time) * 1000,
            )

    async def _execute_first_success(
        self,
        request: "GatewayRequest",
        providers: List[str],
        result: ParallelResult,
    ) -> ParallelResult:
        """Execute until first successful response."""
        # Create tasks for all providers
        tasks = {
            provider: asyncio.create_task(self._execute_single(request, provider))
            for provider in providers
        }

        pending = set(tasks.values())
        provider_by_task = {v: k for k, v in tasks.items()}

        try:
            while pending:
                done, pending = await asyncio.wait(
                    pending,
                    timeout=self.config.timeout_s,
                    return_when=asyncio.FIRST_COMPLETED,
                )

                for task in done:
                    provider = provider_by_task[task]
                    response = task.result()
                    result.all_responses[provider] = response

                    if response.success:
                        result.selected_provider = provider
                        result.selected_response = response.response
                        result.success = True

                        # Cancel remaining tasks
                        for p in pending:
                            p.cancel()

                        return result

        except asyncio.TimeoutError:
            pass

        # No successful response
        if result.all_responses:
            # Return first response even if failed
            first_provider = list(result.all_responses.keys())[0]
            first_response = result.all_responses[first_provider]
            result.selected_provider = first_provider
            result.error = first_response.error
        else:
            result.error = "All providers timed out"

        return result

    async def _execute_fastest(
        self,
        request: "GatewayRequest",
        providers: List[str],
        result: ParallelResult,
    ) -> ParallelResult:
        """Return the fastest response regardless of success."""
        tasks = {
            provider: asyncio.create_task(self._execute_single(request, provider))
            for provider in providers
        }

        provider_by_task = {v: k for k, v in tasks.items()}

        try:
            done, pending = await asyncio.wait(
                tasks.values(),
                timeout=self.config.timeout_s,
                return_when=asyncio.FIRST_COMPLETED,
            )

            if done:
                task = list(done)[0]
                provider = provider_by_task[task]
                response = task.result()

                result.all_responses[provider] = response
                result.selected_provider = provider
                result.selected_response = response.response
                result.success = response.success
                result.error = response.error

            # Cancel remaining tasks
            for task in pending:
                task.cancel()

        except asyncio.TimeoutError:
            result.error = "All providers timed out"

        return result

    async def _execute_all(
        self,
        request: "GatewayRequest",
        providers: List[str],
        result: ParallelResult,
    ) -> ParallelResult:
        """Execute on all providers and return all responses."""
        tasks = [
            self._execute_single(request, provider)
            for provider in providers
        ]

        responses = await asyncio.gather(*tasks, return_exceptions=True)

        for provider, response in zip(providers, responses):
            if isinstance(response, Exception):
                result.all_responses[provider] = ProviderResponse(
                    provider=provider,
                    success=False,
                    error=str(response),
                )
            else:
                result.all_responses[provider] = response

        # Select first successful response
        for provider, response in result.all_responses.items():
            if response.success:
                result.selected_provider = provider
                result.selected_response = response.response
                result.success = True
                break

        if not result.success:
            result.error = "No successful responses"

        return result

    async def _execute_consensus(
        self,
        request: "GatewayRequest",
        providers: List[str],
        result: ParallelResult,
    ) -> ParallelResult:
        """Execute on all providers and return most common response."""
        # First get all responses
        result = await self._execute_all(request, providers, result)

        if not result.success:
            return result

        # Find consensus among successful responses
        successful_responses = [
            (p, r) for p, r in result.all_responses.items()
            if r.success and r.response
        ]

        if not successful_responses:
            result.success = False
            result.error = "No successful responses for consensus"
            return result

        # Simple consensus: use response length similarity
        # In production, you might use semantic similarity
        responses_by_length = sorted(
            successful_responses,
            key=lambda x: len(x[1].response or ""),
        )

        # Pick median length response as "consensus"
        median_idx = len(responses_by_length) // 2
        provider, response = responses_by_length[median_idx]

        result.selected_provider = provider
        result.selected_response = response.response
        result.success = True

        return result

    async def _execute_best_quality(
        self,
        request: "GatewayRequest",
        providers: List[str],
        result: ParallelResult,
    ) -> ParallelResult:
        """Execute on all providers and return best quality response."""
        # First get all responses
        result = await self._execute_all(request, providers, result)

        if not result.success:
            return result

        # Score responses by quality indicators
        def score_response(response: ProviderResponse) -> float:
            if not response.success or not response.response:
                return 0.0

            score = 0.0
            text = response.response

            # Length score (prefer longer, more detailed responses)
            score += min(len(text) / 1000, 5.0)

            # Structure score (has paragraphs, lists, etc.)
            if "\n\n" in text:
                score += 1.0
            if "- " in text or "* " in text or "1." in text:
                score += 1.0

            # Latency penalty (prefer faster responses slightly)
            score -= response.latency_ms / 10000

            return score

        # Find best response
        best_provider = None
        best_score = -float("inf")

        for provider, response in result.all_responses.items():
            score = score_response(response)
            if score > best_score:
                best_score = score
                best_provider = provider

        if best_provider:
            result.selected_provider = best_provider
            result.selected_response = result.all_responses[best_provider].response
            result.success = True
        else:
            result.success = False
            result.error = "No quality responses found"

        return result

    def get_available_providers(self) -> List[str]:
        """Get list of available providers for parallel execution."""
        return list(self.backends.keys())

    def get_provider_groups(self) -> Dict[str, List[str]]:
        """Get configured provider groups."""
        from .gateway_config import DEFAULT_PROVIDER_GROUPS
        return DEFAULT_PROVIDER_GROUPS.copy()

