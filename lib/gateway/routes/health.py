"""Health, diagnostics, and metrics routes for gateway API."""
from __future__ import annotations

import asyncio
import time
from typing import Any, Dict, Optional

try:
    from fastapi import APIRouter, Depends, HTTPException, Query, Request

    HAS_FASTAPI = True
except ImportError:  # pragma: no cover - optional FastAPI dependency
    HAS_FASTAPI = False

from ..error_handlers import raise_health_checker_unavailable
from ..models import GatewayRequest
from ..retry import detect_auth_failure
from .health_ops import register_health_ops_routes

if HAS_FASTAPI:
    router = APIRouter()
else:  # pragma: no cover - API unavailable without FastAPI
    router = None


def get_config(request: Request):
    return request.app.state.config


def get_store(request: Request):
    return request.app.state.store


def get_queue(request: Request):
    return request.app.state.queue


def get_cache_manager(request: Request):
    return getattr(request.app.state, "cache_manager", None)


def get_memory_middleware(request: Request):
    return getattr(request.app.state, "memory_middleware", None)


def get_reliability_tracker(request: Request):
    return getattr(request.app.state, "reliability_tracker", None)


def get_start_time(request: Request):
    return getattr(request.app.state, "start_time", time.time())


def get_backends(request: Request):
    return getattr(request.app.state, "backends", {})


def get_health_checker(request: Request):
    return getattr(request.app.state, "health_checker", None)


def get_backpressure(request: Request):
    return getattr(request.app.state, "backpressure", None)


def get_metrics_collector(request: Request):
    return getattr(request.app.state, "metrics", None)


if HAS_FASTAPI:
    @router.get("/api/health")
    async def health_check() -> Dict[str, str]:
        """Simple health check endpoint."""
        return {"status": "ok"}


    @router.get("/api/test/health")
    async def test_health(
        store=Depends(get_store),
        queue=Depends(get_queue),
        cache_manager=Depends(get_cache_manager),
        memory_middleware=Depends(get_memory_middleware),
    ) -> Dict[str, Any]:
        """
        Quick health check with component status.

        Returns basic health indicators for all major components.
        """
        components = {
            "gateway": "healthy",
            "store": "unknown",
            "queue": "unknown",
            "cache": "unknown" if not cache_manager else "healthy",
            "memory": "unknown" if not memory_middleware else "healthy",
        }

        try:
            store.get_stats()
            components["store"] = "healthy"
        except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError) as e:
            components["store"] = f"unhealthy: {str(e)[:50]}"

        try:
            queue.stats()
            components["queue"] = "healthy"
        except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError) as e:
            components["queue"] = f"unhealthy: {str(e)[:50]}"

        all_healthy = all(v == "healthy" for v in components.values())

        return {
            "status": "healthy" if all_healthy else "degraded",
            "components": components,
            "timestamp": time.time(),
        }


    @router.get("/api/test/full")
    async def test_full(
        config=Depends(get_config),
        store=Depends(get_store),
        queue=Depends(get_queue),
        cache_manager=Depends(get_cache_manager),
        memory_middleware=Depends(get_memory_middleware),
        reliability_tracker=Depends(get_reliability_tracker),
        start_time: float = Depends(get_start_time),
    ) -> Dict[str, Any]:
        """
        Comprehensive system test.

        Tests all major components and returns detailed diagnostics.
        """
        results = {
            "timestamp": time.time(),
            "uptime_s": time.time() - start_time,
            "tests": [],
        }

        test_result = {"name": "database_connectivity", "status": "unknown", "details": {}}
        try:
            stats = store.get_stats()
            test_result["status"] = "passed"
            test_result["details"] = {
                "total_requests": stats.get("total_requests", 0),
                "active_requests": stats.get("active_requests", 0),
            }
        except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError) as e:
            test_result["status"] = "failed"
            test_result["details"] = {"error": str(e)}
        results["tests"].append(test_result)

        test_result = {"name": "queue_operations", "status": "unknown", "details": {}}
        try:
            queue_stats = queue.stats()
            test_result["status"] = "passed"
            test_result["details"] = {
                "queue_depth": queue_stats.get("queue_depth", 0),
                "processing_count": queue_stats.get("processing_count", 0),
                "max_concurrent": queue_stats.get("max_concurrent", 0),
            }
        except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError) as e:
            test_result["status"] = "failed"
            test_result["details"] = {"error": str(e)}
        results["tests"].append(test_result)

        test_result = {"name": "cache_system", "status": "unknown", "details": {}}
        if cache_manager:
            try:
                cache_stats = cache_manager.get_stats()
                test_result["status"] = "passed"
                test_result["details"] = {
                    "hit_rate": cache_stats.hit_rate,
                    "total_entries": cache_stats.total_entries,
                }
            except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError) as e:
                test_result["status"] = "failed"
                test_result["details"] = {"error": str(e)}
        else:
            test_result["status"] = "skipped"
            test_result["details"] = {"reason": "Cache not enabled"}
        results["tests"].append(test_result)

        test_result = {"name": "provider_configuration", "status": "unknown", "details": {}}
        try:
            provider_count = len(config.providers)
            enabled_count = sum(1 for p in config.providers.values() if p.enabled)
            test_result["status"] = "passed" if enabled_count > 0 else "warning"
            test_result["details"] = {
                "total_providers": provider_count,
                "enabled_providers": enabled_count,
                "providers": list(config.providers.keys()),
            }
        except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError) as e:
            test_result["status"] = "failed"
            test_result["details"] = {"error": str(e)}
        results["tests"].append(test_result)

        test_result = {"name": "memory_middleware", "status": "unknown", "details": {}}
        if memory_middleware:
            try:
                if hasattr(memory_middleware, "memory") and hasattr(memory_middleware.memory, "v2"):
                    mem_stats = memory_middleware.memory.v2.get_stats()
                    test_result["status"] = "passed"
                    test_result["details"] = mem_stats
                else:
                    test_result["status"] = "passed"
                    test_result["details"] = {"note": "Memory middleware active"}
            except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError) as e:
                test_result["status"] = "failed"
                test_result["details"] = {"error": str(e)}
        else:
            test_result["status"] = "skipped"
            test_result["details"] = {"reason": "Memory middleware not enabled"}
        results["tests"].append(test_result)

        test_result = {"name": "reliability_tracker", "status": "unknown", "details": {}}
        if reliability_tracker:
            try:
                scores = reliability_tracker.get_all_scores()
                test_result["status"] = "passed"
                test_result["details"] = {
                    "tracked_providers": len(scores),
                    "scores": scores,
                }
            except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError) as e:
                test_result["status"] = "failed"
                test_result["details"] = {"error": str(e)}
        else:
            test_result["status"] = "skipped"
            test_result["details"] = {"reason": "Reliability tracker not enabled"}
        results["tests"].append(test_result)

        passed = sum(1 for t in results["tests"] if t["status"] == "passed")
        failed = sum(1 for t in results["tests"] if t["status"] == "failed")
        skipped = sum(1 for t in results["tests"] if t["status"] == "skipped")

        results["summary"] = {
            "total": len(results["tests"]),
            "passed": passed,
            "failed": failed,
            "skipped": skipped,
            "overall": "healthy" if failed == 0 else "unhealthy",
        }

        return results


    @router.get("/api/test/providers")
    async def test_providers(
        config=Depends(get_config),
        backends=Depends(get_backends),
    ) -> Dict[str, Any]:
        """
        Test provider connectivity.

        Performs lightweight connectivity check for each configured provider.
        """
        results = {
            "timestamp": time.time(),
            "providers": {},
        }

        for provider_name, pconfig in config.providers.items():
            provider_result = {
                "enabled": pconfig.enabled,
                "backend_type": pconfig.backend_type.value,
                "status": "unknown",
                "latency_ms": None,
                "error": None,
            }

            if not pconfig.enabled:
                provider_result["status"] = "disabled"
                results["providers"][provider_name] = provider_result
                continue

            backend = backends.get(provider_name)
            if not backend:
                provider_result["status"] = "no_backend"
                provider_result["error"] = "Backend not initialized"
                results["providers"][provider_name] = provider_result
                continue

            start_ts = time.time()
            try:
                test_req = GatewayRequest.create(
                    provider=provider_name,
                    message="ping",
                    timeout_s=15.0,
                    metadata={"connectivity_test": True},
                )

                result = await asyncio.wait_for(
                    backend.execute(test_req),
                    timeout=15.0,
                )

                latency_ms = (time.time() - start_ts) * 1000

                if result.success:
                    provider_result["status"] = "healthy"
                    provider_result["latency_ms"] = round(latency_ms, 2)
                else:
                    is_auth = detect_auth_failure(result.error or "")
                    provider_result["status"] = "auth_failed" if is_auth else "unhealthy"
                    provider_result["latency_ms"] = round(latency_ms, 2)
                    provider_result["error"] = result.error

            except asyncio.TimeoutError:
                provider_result["status"] = "timeout"
                provider_result["latency_ms"] = 15000
                provider_result["error"] = "Request timed out after 15s"
            except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError) as e:
                provider_result["status"] = "error"
                provider_result["error"] = str(e)

            results["providers"][provider_name] = provider_result

        healthy = sum(1 for p in results["providers"].values() if p["status"] == "healthy")
        total_enabled = sum(
            1
            for p in results["providers"].values()
            if p.get("enabled", True) and p["status"] != "disabled"
        )

        results["summary"] = {
            "total": len(results["providers"]),
            "healthy": healthy,
            "unhealthy": total_enabled - healthy,
            "disabled": sum(1 for p in results["providers"].values() if p["status"] == "disabled"),
        }

        return results


    @router.get("/api/health-checker/status")
    async def get_health_checker_status(
        health_checker=Depends(get_health_checker),
    ) -> Dict[str, Any]:
        """
        Get health checker status and all provider health.

        v0.23: Returns health status for all registered providers.
        """
        if not health_checker:
            return {
                "enabled": False,
                "message": "Health checker not available",
            }

        return health_checker.get_stats()


    @router.post("/api/health-checker/check")
    async def trigger_health_check(
        provider: Optional[str] = Query(None, description="Specific provider to check, or all if not specified"),
        health_checker=Depends(get_health_checker),
    ) -> Dict[str, Any]:
        """
        Trigger immediate health check for one or all providers.

        v0.23: Forces an immediate health check instead of waiting for the next scheduled check.
        """
        if not health_checker:
            raise_health_checker_unavailable()

        results = await health_checker.check_now(provider)
        return {
            "checked": len(results),
            "results": {p: h.to_dict() for p, h in results.items() if h},
        }


    @router.get("/api/health-checker/healthy")
    async def get_healthy_providers(
        config=Depends(get_config),
        health_checker=Depends(get_health_checker),
    ) -> Dict[str, Any]:
        """
        Get list of healthy providers.

        v0.23: Returns only providers that are currently healthy.
        """
        if not health_checker:
            return {
                "healthy": list(config.providers.keys()),
                "total": len(config.providers),
                "source": "config_fallback",
            }

        healthy = health_checker.get_healthy_providers()
        available = health_checker.get_available_providers()

        return {
            "healthy": healthy,
            "available": available,
            "total": len(config.providers),
            "source": "health_checker",
        }


    @router.post("/api/health-checker/providers/{provider_name}/enable")
    async def force_enable_provider(
        provider_name: str,
        health_checker=Depends(get_health_checker),
    ) -> Dict[str, Any]:
        """
        Force enable a provider that was auto-disabled.

        v0.23: Resets health status and re-enables the provider.
        """
        if not health_checker:
            raise_health_checker_unavailable()

        success = health_checker.force_enable(provider_name)
        if not success:
            raise HTTPException(status_code=404, detail=f"Provider {provider_name} not found in health checker")

        return {
            "provider": provider_name,
            "action": "force_enabled",
            "success": True,
        }


    @router.post("/api/health-checker/providers/{provider_name}/disable")
    async def force_disable_provider(
        provider_name: str,
        health_checker=Depends(get_health_checker),
    ) -> Dict[str, Any]:
        """
        Force disable a provider.

        v0.23: Marks provider as unavailable regardless of actual health.
        """
        if not health_checker:
            raise_health_checker_unavailable()

        success = health_checker.force_disable(provider_name)
        if not success:
            raise HTTPException(status_code=404, detail=f"Provider {provider_name} not found in health checker")

        return {
            "provider": provider_name,
            "action": "force_disabled",
            "success": True,
        }


_health_ops_funcs = register_health_ops_routes(
    router=router,
    get_backpressure=get_backpressure,
    get_metrics_collector=get_metrics_collector,
)
globals().update(_health_ops_funcs)
