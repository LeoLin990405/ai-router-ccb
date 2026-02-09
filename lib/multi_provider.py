"""
Multi-Provider Execution System for CCB

Executes queries across multiple AI providers in parallel and aggregates results.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Callable, Any
from enum import Enum
from concurrent.futures import ThreadPoolExecutor, as_completed
import subprocess
import time


HANDLED_EXCEPTIONS = (Exception,)


class AggregationStrategy(Enum):
    """Strategy for aggregating multi-provider results."""
    FIRST_SUCCESS = "first_success"  # Return first successful response
    ALL = "all"                      # Return all responses
    MERGE = "merge"                  # Merge all responses into one
    COMPARE = "compare"              # Show side-by-side comparison


@dataclass
class ProviderResult:
    """Result from a single provider."""
    provider: str
    success: bool
    response: Optional[str] = None
    error: Optional[str] = None
    latency_ms: float = 0.0


@dataclass
class MultiProviderResult:
    """Aggregated result from multiple providers."""
    providers: List[str]
    results: Dict[str, ProviderResult]
    aggregated: Optional[str] = None
    strategy: AggregationStrategy = AggregationStrategy.ALL
    total_latency_ms: float = 0.0
    successful_count: int = 0
    failed_count: int = 0


class MultiProviderExecutor:
    """
    Executes queries across multiple AI providers in parallel.

    Supports various aggregation strategies for combining results.
    """

    # Provider to ask command mapping
    PROVIDER_COMMANDS = {
        "claude": "lask",
        "codex": "cask",
        "gemini": "gask",
        "opencode": "oask",
        "droid": "dask",
        "iflow": "iask",
        "kimi": "kask",
        "qwen": "qask",
        "deepseek": "dskask",
    }

    def __init__(
        self,
        providers: Optional[List[str]] = None,
        strategy: AggregationStrategy = AggregationStrategy.ALL,
        timeout_s: float = 60.0,
        max_concurrent: int = 5,
    ):
        """
        Initialize the multi-provider executor.

        Args:
            providers: List of providers to query (default: claude, gemini, codex)
            strategy: Aggregation strategy
            timeout_s: Timeout for each provider in seconds
            max_concurrent: Maximum concurrent executions
        """
        self.providers = providers or ["claude", "gemini", "codex"]
        self.strategy = strategy
        self.timeout_s = timeout_s
        self.max_concurrent = max_concurrent

    def _get_ask_command(self, provider: str) -> str:
        """Get the ask command for a provider."""
        return self.PROVIDER_COMMANDS.get(provider, "lask")

    def _execute_single(self, provider: str, message: str) -> ProviderResult:
        """Execute query on a single provider."""
        ask_cmd = self._get_ask_command(provider)
        start_time = time.time()

        try:
            cmd = f"{ask_cmd} <<'EOF'\n{message}\nEOF"
            result = subprocess.run(
                ["bash", "-c", cmd],
                capture_output=True,
                text=True,
                timeout=self.timeout_s,
            )

            latency_ms = (time.time() - start_time) * 1000

            if result.returncode == 0:
                return ProviderResult(
                    provider=provider,
                    success=True,
                    response=result.stdout,
                    latency_ms=latency_ms,
                )
            else:
                return ProviderResult(
                    provider=provider,
                    success=False,
                    error=result.stderr or f"Exit code: {result.returncode}",
                    latency_ms=latency_ms,
                )

        except subprocess.TimeoutExpired:
            latency_ms = (time.time() - start_time) * 1000
            return ProviderResult(
                provider=provider,
                success=False,
                error="Timeout",
                latency_ms=latency_ms,
            )
        except HANDLED_EXCEPTIONS as e:
            latency_ms = (time.time() - start_time) * 1000
            return ProviderResult(
                provider=provider,
                success=False,
                error=str(e),
                latency_ms=latency_ms,
            )

    def execute_parallel(
        self,
        message: str,
        on_result: Optional[Callable[[ProviderResult], None]] = None,
    ) -> MultiProviderResult:
        """
        Execute query on all providers in parallel.

        Args:
            message: The message to send to all providers
            on_result: Optional callback called when each provider completes

        Returns:
            MultiProviderResult with all responses
        """
        start_time = time.time()
        results: Dict[str, ProviderResult] = {}

        with ThreadPoolExecutor(max_workers=self.max_concurrent) as executor:
            # Submit all tasks
            future_to_provider = {
                executor.submit(self._execute_single, provider, message): provider
                for provider in self.providers
            }

            # Collect results as they complete
            for future in as_completed(future_to_provider):
                provider = future_to_provider[future]
                try:
                    result = future.result()
                    results[provider] = result
                    if on_result:
                        on_result(result)

                    # For FIRST_SUCCESS strategy, return immediately on success
                    if self.strategy == AggregationStrategy.FIRST_SUCCESS and result.success:
                        # Cancel remaining futures
                        for f in future_to_provider:
                            f.cancel()
                        break

                except HANDLED_EXCEPTIONS as e:
                    results[provider] = ProviderResult(
                        provider=provider,
                        success=False,
                        error=str(e),
                    )

        total_latency_ms = (time.time() - start_time) * 1000
        successful_count = sum(1 for r in results.values() if r.success)
        failed_count = len(results) - successful_count

        # Aggregate results based on strategy
        aggregated = self._aggregate_results(results)

        return MultiProviderResult(
            providers=self.providers,
            results=results,
            aggregated=aggregated,
            strategy=self.strategy,
            total_latency_ms=total_latency_ms,
            successful_count=successful_count,
            failed_count=failed_count,
        )

    def _aggregate_results(self, results: Dict[str, ProviderResult]) -> Optional[str]:
        """Aggregate results based on strategy."""
        successful_results = {
            p: r for p, r in results.items() if r.success and r.response
        }

        if not successful_results:
            return None

        if self.strategy == AggregationStrategy.FIRST_SUCCESS:
            # Return first successful response
            for result in successful_results.values():
                return result.response
            return None

        elif self.strategy == AggregationStrategy.ALL:
            # Return all responses formatted
            lines = []
            for provider, result in successful_results.items():
                lines.append(f"=== {provider.upper()} ===")
                lines.append(result.response or "")
                lines.append("")
            return "\n".join(lines)

        elif self.strategy == AggregationStrategy.MERGE:
            # Merge responses with headers
            lines = ["# Multi-Provider Response\n"]
            for provider, result in successful_results.items():
                lines.append(f"## From {provider.capitalize()}\n")
                lines.append(result.response or "")
                lines.append("\n---\n")
            return "\n".join(lines)

        elif self.strategy == AggregationStrategy.COMPARE:
            # Side-by-side comparison format
            lines = ["# Provider Comparison\n"]
            lines.append(f"Providers queried: {', '.join(successful_results.keys())}\n")
            lines.append("-" * 60 + "\n")
            for provider, result in successful_results.items():
                lines.append(f"### {provider.upper()}")
                lines.append(f"Latency: {result.latency_ms:.0f}ms\n")
                lines.append("```")
                lines.append(result.response or "")
                lines.append("```\n")
            return "\n".join(lines)

        return None

    def execute_sequential(
        self,
        message: str,
        stop_on_success: bool = False,
    ) -> MultiProviderResult:
        """
        Execute query on providers sequentially.

        Args:
            message: The message to send
            stop_on_success: Stop after first successful response

        Returns:
            MultiProviderResult with all responses
        """
        start_time = time.time()
        results: Dict[str, ProviderResult] = {}

        for provider in self.providers:
            result = self._execute_single(provider, message)
            results[provider] = result

            if stop_on_success and result.success:
                break

        total_latency_ms = (time.time() - start_time) * 1000
        successful_count = sum(1 for r in results.values() if r.success)
        failed_count = len(results) - successful_count

        aggregated = self._aggregate_results(results)

        return MultiProviderResult(
            providers=list(results.keys()),
            results=results,
            aggregated=aggregated,
            strategy=self.strategy,
            total_latency_ms=total_latency_ms,
            successful_count=successful_count,
            failed_count=failed_count,
        )


def format_multi_result(result: MultiProviderResult, verbose: bool = False) -> str:
    """Format multi-provider result for display."""
    lines = []

    if verbose:
        lines.append("=" * 60)
        lines.append("Multi-Provider Execution Summary")
        lines.append("=" * 60)
        lines.append(f"Strategy:    {result.strategy.value}")
        lines.append(f"Providers:   {', '.join(result.providers)}")
        lines.append(f"Successful:  {result.successful_count}")
        lines.append(f"Failed:      {result.failed_count}")
        lines.append(f"Total Time:  {result.total_latency_ms:.0f}ms")
        lines.append("-" * 60)

        for provider, pr in result.results.items():
            status = "OK" if pr.success else "FAIL"
            lines.append(f"{provider:<12} {status:<6} {pr.latency_ms:.0f}ms")
            if pr.error:
                lines.append(f"             Error: {pr.error}")

        lines.append("=" * 60)
        lines.append("")

    if result.aggregated:
        lines.append(result.aggregated)

    return "\n".join(lines)
