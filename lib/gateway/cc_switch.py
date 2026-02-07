"""
CC Switch Integration Module for CCB Gateway.

Integrates CC Switch provider management and parallel testing capabilities.
"""
from __future__ import annotations

import asyncio
import json
import sqlite3
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Dict, Any, List
import os

import aiohttp


@dataclass
class CCProvider:
    """CC Switch Provider configuration."""
    id: int
    provider_name: str
    api_base: str
    api_key: str
    priority: int
    status: int  # 1 = active, 0 = inactive
    last_success: Optional[str] = None
    fail_count: int = 0


@dataclass
class CCTestResult:
    """Result from CC Switch parallel test."""
    provider_name: str
    success: bool
    response: Optional[str] = None
    error: Optional[str] = None
    latency_ms: float = 0.0
    tokens_used: Optional[int] = None
    timestamp: float = field(default_factory=time.time)


@dataclass
class CCParallelResult:
    """Aggregated results from parallel CC Switch testing."""
    request_id: str
    message: str
    providers: List[str]
    results: Dict[str, CCTestResult] = field(default_factory=dict)
    total_latency_ms: float = 0.0
    success_count: int = 0
    failure_count: int = 0
    fastest_provider: Optional[str] = None
    fastest_latency_ms: float = float('inf')

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "request_id": self.request_id,
            "message": self.message,
            "providers": self.providers,
            "results": {k: {
                "provider_name": v.provider_name,
                "success": v.success,
                "response": v.response,
                "error": v.error,
                "latency_ms": v.latency_ms,
                "tokens_used": v.tokens_used,
                "timestamp": v.timestamp,
            } for k, v in self.results.items()},
            "total_latency_ms": self.total_latency_ms,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "fastest_provider": self.fastest_provider,
            "fastest_latency_ms": self.fastest_latency_ms,
        }


class CCSwitch:
    """
    CC Switch Integration for CCB Gateway.

    Provides:
    - Provider status monitoring
    - Failover queue management
    - Parallel testing across providers
    """

    def __init__(self, db_path: Optional[str] = None):
        """Initialize CC Switch integration."""
        if db_path is None:
            db_path = os.path.expanduser("~/.cc-switch/cc-switch.db")
        self.db_path = db_path
        self.providers: Dict[int, CCProvider] = {}
        self._load_providers()

    def _load_providers(self):
        """Load providers from CC Switch database."""
        if not os.path.exists(self.db_path):
            print(f"⚠️  CC Switch database not found: {self.db_path}")
            return

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Load providers
            cursor.execute("""
                SELECT id, provider_name, api_base, api_key, priority, status,
                       last_success, fail_count
                FROM providers
                ORDER BY priority DESC
            """)

            for row in cursor.fetchall():
                provider = CCProvider(
                    id=row[0],
                    provider_name=row[1],
                    api_base=row[2],
                    api_key=row[3],
                    priority=row[4],
                    status=row[5],
                    last_success=row[6],
                    fail_count=row[7],
                )
                self.providers[provider.id] = provider

            conn.close()
            print(f"✓ Loaded {len(self.providers)} providers from CC Switch")

        except sqlite3.Error as e:
            print(f"✖ Failed to load CC Switch database: {e}")

    def get_active_providers(self) -> List[CCProvider]:
        """Get all active providers sorted by priority."""
        return sorted(
            [p for p in self.providers.values() if p.status == 1],
            key=lambda x: x.priority,
            reverse=True
        )

    def get_failover_queue(self) -> List[str]:
        """Get failover queue (active providers sorted by priority)."""
        return [p.provider_name for p in self.get_active_providers()]

    def get_provider_by_name(self, name: str) -> Optional[CCProvider]:
        """Get provider by name."""
        for p in self.providers.values():
            if p.provider_name == name:
                return p
        return None

    async def test_provider(
        self,
        provider: CCProvider,
        message: str,
        timeout_s: float = 30.0
    ) -> CCTestResult:
        """
        Test a single provider with a message.

        Args:
            provider: CC Provider to test
            message: Test message
            timeout_s: Timeout in seconds

        Returns:
            CCTestResult with test outcome
        """
        start_time = time.time()

        try:
            async with aiohttp.ClientSession() as session:
                headers = {
                    "Authorization": f"Bearer {provider.api_key}",
                    "Content-Type": "application/json",
                }

                payload = {
                    "model": "claude-sonnet-4-5-20250929",
                    "messages": [{"role": "user", "content": message}],
                    "max_tokens": 4096,
                }

                async with session.post(
                    f"{provider.api_base}/v1/messages",
                    headers=headers,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=timeout_s)
                ) as resp:
                    latency_ms = (time.time() - start_time) * 1000

                    if resp.status == 200:
                        data = await resp.json()
                        content = data.get("content", [{}])[0].get("text", "")
                        tokens = data.get("usage", {}).get("output_tokens", 0)

                        return CCTestResult(
                            provider_name=provider.provider_name,
                            success=True,
                            response=content,
                            latency_ms=latency_ms,
                            tokens_used=tokens,
                        )
                    else:
                        error_text = await resp.text()
                        return CCTestResult(
                            provider_name=provider.provider_name,
                            success=False,
                            error=f"HTTP {resp.status}: {error_text}",
                            latency_ms=latency_ms,
                        )

        except asyncio.TimeoutError:
            return CCTestResult(
                provider_name=provider.provider_name,
                success=False,
                error="Timeout",
                latency_ms=(time.time() - start_time) * 1000,
            )

        except Exception as e:
            return CCTestResult(
                provider_name=provider.provider_name,
                success=False,
                error=str(e),
                latency_ms=(time.time() - start_time) * 1000,
            )

    async def parallel_test(
        self,
        message: str,
        providers: Optional[List[str]] = None,
        timeout_s: float = 60.0,
        request_id: Optional[str] = None
    ) -> CCParallelResult:
        """
        Test multiple providers in parallel.

        Args:
            message: Test message
            providers: List of provider names (default: all active)
            timeout_s: Timeout in seconds
            request_id: Optional request ID for tracking

        Returns:
            CCParallelResult with aggregated results
        """
        if request_id is None:
            request_id = f"cc-parallel-{int(time.time() * 1000)}"

        # Get providers to test
        if providers is None:
            test_providers = self.get_active_providers()
        else:
            test_providers = [
                p for name in providers
                if (p := self.get_provider_by_name(name)) is not None
            ]

        if not test_providers:
            return CCParallelResult(
                request_id=request_id,
                message=message,
                providers=[],
                total_latency_ms=0.0,
            )

        # Test providers in parallel
        start_time = time.time()
        tasks = [
            self.test_provider(provider, message, timeout_s)
            for provider in test_providers
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)
        total_latency_ms = (time.time() - start_time) * 1000

        # Aggregate results
        result = CCParallelResult(
            request_id=request_id,
            message=message,
            providers=[p.provider_name for p in test_providers],
            total_latency_ms=total_latency_ms,
        )

        for test_result in results:
            if isinstance(test_result, CCTestResult):
                result.results[test_result.provider_name] = test_result

                if test_result.success:
                    result.success_count += 1
                    # Track fastest
                    if test_result.latency_ms < result.fastest_latency_ms:
                        result.fastest_latency_ms = test_result.latency_ms
                        result.fastest_provider = test_result.provider_name
                else:
                    result.failure_count += 1
            else:
                # Exception occurred
                result.failure_count += 1

        return result

    def get_status(self) -> Dict[str, Any]:
        """Get CC Switch status."""
        active_providers = self.get_active_providers()

        return {
            "total_providers": len(self.providers),
            "active_providers": len(active_providers),
            "failover_queue": [p.provider_name for p in active_providers],
            "providers": [
                {
                    "id": p.id,
                    "name": p.provider_name,
                    "priority": p.priority,
                    "status": "active" if p.status == 1 else "inactive",
                    "last_success": p.last_success,
                    "fail_count": p.fail_count,
                }
                for p in self.providers.values()
            ]
        }

    def reload(self):
        """Reload providers from database."""
        self.providers.clear()
        self._load_providers()
