"""Core provider/routing/cost routes for gateway API."""
from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional

try:
    from fastapi import APIRouter, Depends, HTTPException, Query, Request

    HAS_FASTAPI = True
except ImportError:  # pragma: no cover - optional FastAPI dependency
    HAS_FASTAPI = False

from ..models import AuthStatus, GatewayRequest
from ..retry import detect_auth_failure
from ..router import ProviderPerformance, SmartRouter, auto_route

if HAS_FASTAPI:
    router = APIRouter()
else:  # pragma: no cover - API unavailable without FastAPI
    router = None


def get_config(request: Request):
    return request.app.state.config


def get_store(request: Request):
    return request.app.state.store


def get_backends(request: Request):
    return getattr(request.app.state, "backends", {})


def get_reliability_tracker(request: Request):
    return getattr(request.app.state, "reliability_tracker", None)


if HAS_FASTAPI:
    @router.get("/api/retry/config")
    async def get_retry_config(
        config=Depends(get_config),
    ) -> Dict[str, Any]:
        """Get retry and fallback configuration."""
        return {
            "enabled": config.retry.enabled,
            "max_retries": config.retry.max_retries,
            "base_delay_s": config.retry.base_delay_s,
            "max_delay_s": config.retry.max_delay_s,
            "fallback_enabled": config.retry.fallback_enabled,
            "fallback_chains": config.retry.fallback_chains,
        }


    @router.get("/api/providers/{provider_name}/auth-status")
    async def get_provider_auth_status(
        provider_name: str,
        config=Depends(get_config),
        store=Depends(get_store),
        reliability_tracker=Depends(get_reliability_tracker),
    ) -> Dict[str, Any]:
        """
        Get authentication status for a provider.

        Returns auth status based on recent request history.
        """
        if provider_name not in config.providers:
            raise HTTPException(status_code=404, detail=f"Provider not found: {provider_name}")

        if reliability_tracker:
            score = reliability_tracker.get_score(provider_name)
            if score.needs_reauth:
                auth_status = AuthStatus.NEEDS_REAUTH
            elif score.auth_failure_count > 0:
                auth_status = AuthStatus.INVALID
            elif score.total_requests == 0:
                auth_status = AuthStatus.UNKNOWN
            else:
                auth_status = AuthStatus.VALID

            return {
                "provider": provider_name,
                "auth_status": auth_status.value,
                "auth_failure_count": score.auth_failure_count,
                "last_auth_failure": score.last_auth_failure,
                "needs_reauth": score.needs_reauth,
                "reliability_score": score.reliability_score,
            }

        provider_metrics = store.get_provider_metrics(provider_name, hours=24)

        return {
            "provider": provider_name,
            "auth_status": AuthStatus.UNKNOWN.value,
            "success_rate": provider_metrics.get("success_rate", 1.0),
            "total_requests": provider_metrics.get("total_requests", 0),
        }


    @router.post("/api/providers/{provider_name}/check-auth")
    async def check_provider_auth(
        provider_name: str,
        config=Depends(get_config),
        backends=Depends(get_backends),
        reliability_tracker=Depends(get_reliability_tracker),
    ) -> Dict[str, Any]:
        """
        Actively check authentication status for a provider.

        Sends a test request to verify credentials.
        """
        if provider_name not in config.providers:
            raise HTTPException(status_code=404, detail=f"Provider not found: {provider_name}")

        test_request = GatewayRequest.create(
            provider=provider_name,
            message="ping",
            timeout_s=30.0,
            metadata={"auth_check": True},
        )

        backend = backends.get(provider_name)
        if not backend:
            return {
                "provider": provider_name,
                "auth_status": AuthStatus.UNKNOWN.value,
                "error": "Backend not available",
            }

        try:
            result = await asyncio.wait_for(
                backend.execute(test_request),
                timeout=30.0,
            )

            if result.success:
                if reliability_tracker:
                    await reliability_tracker.record_success(provider_name)

                return {
                    "provider": provider_name,
                    "auth_status": AuthStatus.VALID.value,
                    "message": "Authentication successful",
                }

            is_auth_failure = detect_auth_failure(result.error or "")
            if reliability_tracker:
                await reliability_tracker.record_failure(
                    provider_name,
                    result.error or "",
                )

            return {
                "provider": provider_name,
                "auth_status": AuthStatus.INVALID.value if is_auth_failure else AuthStatus.UNKNOWN.value,
                "error": result.error,
                "is_auth_failure": is_auth_failure,
            }

        except asyncio.TimeoutError:
            return {
                "provider": provider_name,
                "auth_status": AuthStatus.UNKNOWN.value,
                "error": "Request timed out",
            }
        except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError) as e:
            return {
                "provider": provider_name,
                "auth_status": AuthStatus.UNKNOWN.value,
                "error": str(e),
            }


    @router.post("/api/providers/{provider_name}/reset-auth")
    async def reset_provider_auth(
        provider_name: str,
        config=Depends(get_config),
        reliability_tracker=Depends(get_reliability_tracker),
    ) -> Dict[str, Any]:
        """
        Reset auth failure count for a provider.

        Call this after re-authenticating with a provider.
        """
        if provider_name not in config.providers:
            raise HTTPException(status_code=404, detail=f"Provider not found: {provider_name}")

        if reliability_tracker:
            await reliability_tracker.reset_auth(provider_name)

        return {
            "provider": provider_name,
            "message": "Auth failures reset",
            "auth_status": AuthStatus.UNKNOWN.value,
        }


    @router.get("/api/providers/reliability")
    async def get_all_provider_reliability(
        reliability_tracker=Depends(get_reliability_tracker),
    ) -> Dict[str, Any]:
        """Get reliability scores for all providers."""
        if not reliability_tracker:
            return {"enabled": False, "providers": {}}

        return {
            "enabled": True,
            "providers": reliability_tracker.get_all_scores(),
        }


    @router.get("/api/costs/summary")
    async def get_cost_summary(
        days: int = Query(30, description="Number of days to include"),
        store=Depends(get_store),
    ) -> Dict[str, Any]:
        """
        Get cost summary for the specified period.

        Returns total tokens used and costs, plus today/week breakdowns.
        """
        return store.get_cost_summary(days=days)


    @router.get("/api/costs/by-provider")
    async def get_costs_by_provider(
        days: int = Query(30, description="Number of days to include"),
        store=Depends(get_store),
    ) -> List[Dict[str, Any]]:
        """Get cost breakdown by provider."""
        return store.get_cost_by_provider(days=days)


    @router.get("/api/costs/by-day")
    async def get_costs_by_day(
        days: int = Query(7, description="Number of days to include"),
        store=Depends(get_store),
    ) -> List[Dict[str, Any]]:
        """Get daily cost breakdown."""
        return store.get_cost_by_day(days=days)


    @router.get("/api/costs/pricing")
    async def get_provider_pricing(
        store=Depends(get_store),
    ) -> Dict[str, Any]:
        """Get pricing configuration per provider (per million tokens)."""
        return {
            "pricing": store.PROVIDER_PRICING,
            "unit": "USD per million tokens",
        }


    @router.post("/api/costs/record")
    async def record_token_cost(
        provider: str = Query(..., description="Provider name"),
        input_tokens: int = Query(0, description="Input token count"),
        output_tokens: int = Query(0, description="Output token count"),
        request_id: Optional[str] = Query(None, description="Associated request ID"),
        model: Optional[str] = Query(None, description="Model name"),
        store=Depends(get_store),
    ) -> Dict[str, Any]:
        """
        Record token usage for cost tracking.

        Usually called automatically by backends after request completion.
        """
        store.record_token_cost(
            provider=provider,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            request_id=request_id,
            model=model,
        )
        return {"recorded": True, "provider": provider}


    @router.post("/api/route")
    async def route_message(
        message: str = Query(..., description="Message to route"),
        config=Depends(get_config),
    ) -> Dict[str, Any]:
        """
        Get routing recommendation for a message.

        Uses keyword matching to suggest the best provider.
        """
        available = list(config.providers.keys())
        decision = auto_route(message, available_providers=available)

        return {
            "provider": decision.provider,
            "model": decision.model,
            "confidence": decision.confidence,
            "matched_keywords": decision.matched_keywords,
            "rule_description": decision.rule_description,
        }


    @router.get("/api/route/rules")
    async def get_routing_rules(
        config=Depends(get_config),
    ) -> List[Dict[str, Any]]:
        """Get all configured routing rules."""
        available = list(config.providers.keys())
        router = SmartRouter(available_providers=available)
        return router.get_rules()


    @router.get("/api/router/config")
    async def get_router_config(
        config=Depends(get_config),
    ) -> Dict[str, Any]:
        """Get smart-router configuration used by /api/route."""
        available = list(config.providers.keys())
        default_provider = getattr(config, "default_provider", "claude")

        try:
            router = SmartRouter(
                available_providers=available,
                default_provider=default_provider,
            )
        except TypeError:
            # Compatibility with lightweight test doubles.
            router = SmartRouter(available_providers=available)

        return {
            "default_provider": getattr(router, "default_provider", default_provider),
            "performance_weight": getattr(router, "performance_weight", 0.3),
            "available_providers": available,
            "rule_count": len(getattr(router, "rules", [])) if hasattr(router, "rules") else len(router.get_rules()),
            "rules": router.get_rules(),
        }


    @router.get("/api/router/scores")
    async def get_router_scores(
        hours: int = Query(24, ge=1, le=168, description="Metrics window in hours"),
        config=Depends(get_config),
        store=Depends(get_store),
        reliability_tracker=Depends(get_reliability_tracker),
    ) -> Dict[str, Any]:
        """Get per-provider routing scores with metrics and reliability inputs."""
        available = list(config.providers.keys())
        reliability_scores = reliability_tracker.get_all_scores() if reliability_tracker else {}

        scores: Dict[str, Any] = {}
        for provider in available:
            metrics = store.get_provider_metrics(provider, hours=hours)

            perf = ProviderPerformance(
                provider=provider,
                avg_latency_ms=float(metrics.get("avg_latency_ms", 0.0) or 0.0),
                success_rate=float(metrics.get("success_rate", 1.0) or 1.0),
                total_requests=int(metrics.get("total_requests", 0) or 0),
                is_healthy=True,
            )

            reliability = reliability_scores.get(provider) or {}
            if reliability:
                perf.is_healthy = bool(reliability.get("is_healthy", True))

            scores[provider] = {
                "score": round(perf.calculate_score(), 3),
                "metrics": metrics,
                "reliability": reliability,
                "is_healthy": perf.is_healthy,
            }

        return {
            "hours": hours,
            "default_provider": getattr(config, "default_provider", "claude"),
            "scores": scores,
        }
