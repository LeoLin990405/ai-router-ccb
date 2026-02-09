"""Health checker backpressure and metrics routes."""
from __future__ import annotations

from typing import Any, Dict

try:
    from fastapi import Depends, HTTPException
    from fastapi.responses import PlainTextResponse, Response

    HAS_FASTAPI = True
except ImportError:  # pragma: no cover - optional FastAPI dependency
    HAS_FASTAPI = False


def register_health_ops_routes(*, router, get_backpressure, get_metrics_collector):
    """Attach ops and metrics endpoints to the shared health router."""
    if not HAS_FASTAPI or router is None:  # pragma: no cover
        return {}

    @router.get("/api/backpressure/status")
    async def get_backpressure_status(
        backpressure=Depends(get_backpressure),
    ) -> Dict[str, Any]:
        """Get backpressure controller status and metrics."""
        if not backpressure:
            return {
                "enabled": False,
                "message": "Backpressure controller not available",
            }

        return backpressure.get_stats()

    @router.get("/api/backpressure/should-accept")
    async def should_accept_request(
        backpressure=Depends(get_backpressure),
    ) -> Dict[str, Any]:
        """Check if new requests should be accepted."""
        if not backpressure:
            return {
                "should_accept": True,
                "reason": "Backpressure controller not available - accepting all",
            }

        should_accept = backpressure.should_accept_request()
        rejection_reason = backpressure.get_rejection_reason() if not should_accept else None

        return {
            "should_accept": should_accept,
            "load_level": backpressure.get_load_level().value,
            "current_max_concurrent": backpressure.get_max_concurrent(),
            "rejection_reason": rejection_reason,
        }

    @router.post("/api/backpressure/reset")
    async def reset_backpressure(
        backpressure=Depends(get_backpressure),
    ) -> Dict[str, Any]:
        """Reset backpressure controller to initial state."""
        if not backpressure:
            raise HTTPException(status_code=503, detail="Backpressure controller not available")

        backpressure.reset()
        return {
            "action": "reset",
            "success": True,
            "new_max_concurrent": backpressure.get_max_concurrent(),
        }

    @router.get("/metrics")
    async def get_metrics(
        metrics_collector=Depends(get_metrics_collector),
    ):
        """Export Prometheus metrics."""
        if not metrics_collector:
            return PlainTextResponse(
                content="# Metrics not enabled\n",
                media_type="text/plain",
            )

        return Response(
            content=metrics_collector.export(),
            media_type=metrics_collector.get_content_type(),
        )

    return {
        "get_backpressure_status": get_backpressure_status,
        "should_accept_request": should_accept_request,
        "reset_backpressure": reset_backpressure,
        "get_metrics": get_metrics,
    }

