"""
Centralized error handlers for CCB Gateway API.

Provides reusable HTTPException helpers to reduce code duplication
and ensure consistent error responses across all endpoints.
"""

from fastapi import HTTPException


# ==================== 503 Service Unavailable ====================

def raise_memory_unavailable():
    """Raise when memory system is not available."""
    raise HTTPException(status_code=503, detail="Memory system not available")


def raise_memory_module_unavailable():
    """Raise when memory module is not available."""
    raise HTTPException(status_code=503, detail="Memory module not available")


def raise_memory_config_unavailable():
    """Raise when memory config module is not available."""
    raise HTTPException(status_code=503, detail="Memory config module not available")


def raise_skills_unavailable():
    """Raise when skills discovery is not available."""
    raise HTTPException(status_code=503, detail="Skills Discovery not available")


def raise_consolidator_unavailable():
    """Raise when consolidator module is not available."""
    raise HTTPException(status_code=503, detail="Consolidator module not available")


def raise_health_checker_unavailable():
    """Raise when health checker is not available."""
    raise HTTPException(status_code=503, detail="Health checker not available")


def raise_queue_full():
    """Raise when request queue is full."""
    raise HTTPException(status_code=503, detail="Request queue is full. Try again later.")


def raise_service_unavailable(detail: str):
    """Raise generic 503 with custom detail."""
    raise HTTPException(status_code=503, detail=detail)


# ==================== 404 Not Found ====================

def raise_request_not_found(request_id: str = None):
    """Raise when request is not found."""
    detail = f"Request '{request_id}' not found" if request_id else "Request not found"
    raise HTTPException(status_code=404, detail=detail)


def raise_provider_not_found(provider_name: str):
    """Raise when provider is not found."""
    raise HTTPException(status_code=404, detail=f"Provider not found: {provider_name}")


def raise_provider_not_in_health_checker(provider_name: str):
    """Raise when provider is not found in health checker."""
    raise HTTPException(status_code=404, detail=f"Provider {provider_name} not found in health checker")


def raise_api_key_not_found():
    """Raise when API key is not found."""
    raise HTTPException(status_code=404, detail="API key not found")


def raise_stream_not_found():
    """Raise when stream is not found."""
    raise HTTPException(status_code=404, detail="Stream not found")


def raise_discussion_not_found():
    """Raise when discussion is not found."""
    raise HTTPException(status_code=404, detail="Discussion not found")


def raise_template_not_found():
    """Raise when template is not found."""
    raise HTTPException(status_code=404, detail="Template not found")


def raise_observation_not_found(observation_id: int):
    """Raise when observation is not found."""
    raise HTTPException(status_code=404, detail=f"Observation {observation_id} not found")


def raise_not_found(detail: str):
    """Raise generic 404 with custom detail."""
    raise HTTPException(status_code=404, detail=detail)


# ==================== 400 Bad Request ====================

def raise_cache_not_enabled():
    """Raise when cache is not enabled."""
    raise HTTPException(status_code=400, detail="Cache not enabled")


def raise_invalid_request(detail: str):
    """Raise for invalid request with custom detail."""
    raise HTTPException(status_code=400, detail=detail)


def raise_bad_request(error: Exception):
    """Raise 400 with exception message."""
    raise HTTPException(status_code=400, detail=str(error))


# ==================== 500 Internal Server Error ====================

def raise_search_failed(error: Exception):
    """Raise when search operation fails."""
    raise HTTPException(status_code=500, detail=f"Search failed: {str(error)}")


def raise_config_update_failed(error: Exception):
    """Raise when config update fails."""
    raise HTTPException(status_code=500, detail=f"Failed to update config: {str(error)}")


def raise_stats_failed(error: Exception):
    """Raise when getting stats fails."""
    raise HTTPException(status_code=500, detail=f"Failed to get stats: {str(error)}")


def raise_feedback_failed(error: Exception):
    """Raise when getting feedback fails."""
    raise HTTPException(status_code=500, detail=f"Failed to get feedback: {str(error)}")


def raise_config_get_failed(error: Exception):
    """Raise when getting config fails."""
    raise HTTPException(status_code=500, detail=f"Failed to get config: {str(error)}")


def raise_internal_error(detail: str):
    """Raise generic 500 with custom detail."""
    raise HTTPException(status_code=500, detail=detail)


# ==================== 401/403 Auth Errors ====================

def raise_unauthorized(detail: str = "Unauthorized"):
    """Raise 401 unauthorized."""
    raise HTTPException(status_code=401, detail=detail)


def raise_forbidden(detail: str = "Forbidden"):
    """Raise 403 forbidden."""
    raise HTTPException(status_code=403, detail=detail)
