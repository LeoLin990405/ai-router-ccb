"""CC Switch integration routes for gateway API."""
from __future__ import annotations

from typing import Any, Dict

try:
    from fastapi import APIRouter, HTTPException

    HAS_FASTAPI = True
except ImportError:  # pragma: no cover - optional FastAPI dependency
    HAS_FASTAPI = False

from ..cc_switch import CCSwitch
from ..models import CCParallelTestRequest

if HAS_FASTAPI:
    router = APIRouter()
else:  # pragma: no cover - API unavailable without FastAPI
    router = None


if HAS_FASTAPI:
    @router.get("/api/cc-switch/status")
    async def get_cc_switch_status() -> Dict[str, Any]:
        """
        Get CC Switch provider status and failover queue.

        Returns information about all providers, active status, and failover order.
        """
        try:
            cc_switch = CCSwitch()
            return cc_switch.get_status()
        except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError) as e:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to get CC Switch status: {str(e)}",
            )


    @router.post("/api/cc-switch/reload")
    async def reload_cc_switch() -> Dict[str, Any]:
        """
        Reload CC Switch providers from database.

        Useful after updating provider configurations.
        """
        try:
            cc_switch = CCSwitch()
            cc_switch.reload()
            status = cc_switch.get_status()
            return {
                "reloaded": True,
                "total_providers": status["total_providers"],
                "active_providers": status["active_providers"],
            }
        except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError) as e:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to reload CC Switch: {str(e)}",
            )


    @router.post("/api/cc-switch/parallel-test")
    async def cc_switch_parallel_test(test_request: CCParallelTestRequest) -> Dict[str, Any]:
        """
        Test multiple CC Switch providers in parallel.

        Sends the same message to multiple providers and returns all responses
        with timing information.

        Useful for:
        - Testing provider availability
        - Comparing response quality across providers
        - Finding the fastest provider
        """
        try:
            cc_switch = CCSwitch()

            result = await cc_switch.parallel_test(
                message=test_request.message,
                providers=test_request.providers,
                timeout_s=test_request.timeout_s,
            )

            return result.to_dict()

        except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError) as e:
            raise HTTPException(
                status_code=500,
                detail=f"Parallel test failed: {str(e)}",
            )


    @router.get("/api/cc-switch/failover-queue")
    async def get_failover_queue() -> Dict[str, Any]:
        """
        Get the current failover queue.

        Returns providers in priority order for failover scenarios.
        """
        try:
            cc_switch = CCSwitch()
            queue = cc_switch.get_failover_queue()
            return {
                "failover_queue": queue,
                "count": len(queue),
            }
        except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError) as e:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to get failover queue: {str(e)}",
            )
