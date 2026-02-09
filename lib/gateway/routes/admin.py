"""Admin and cache routes for gateway API."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

try:
    from fastapi import APIRouter, Depends, HTTPException, Query, Request

    HAS_FASTAPI = True
except ImportError:  # pragma: no cover - optional FastAPI dependency
    HAS_FASTAPI = False

from ..error_handlers import raise_api_key_not_found, raise_cache_not_enabled
from ..models import (
    APIKeyInfo,
    CacheStatsResponse,
    CreateAPIKeyRequest,
    CreateAPIKeyResponse,
)

if HAS_FASTAPI:
    router = APIRouter()
    cache_router = APIRouter()
else:  # pragma: no cover - API unavailable without FastAPI
    router = None
    cache_router = None


def get_config(request: Request):
    return request.app.state.config


def get_cache_manager(request: Request):
    return getattr(request.app.state, "cache_manager", None)


def get_api_key_store(request: Request):
    return getattr(request.app.state, "api_key_store", None)


def get_rate_limiter(request: Request):
    return getattr(request.app.state, "rate_limiter", None)


if HAS_FASTAPI:
    @router.post("/providers/{provider_name}/enable")
    async def enable_provider(
        provider_name: str,
        config=Depends(get_config),
    ) -> Dict[str, Any]:
        """Enable a provider."""
        if provider_name not in config.providers:
            raise HTTPException(status_code=404, detail=f"Provider '{provider_name}' not found")
        config.providers[provider_name].enabled = True
        return {"status": "ok", "provider": provider_name, "enabled": True}


    @router.post("/providers/{provider_name}/disable")
    async def disable_provider(
        provider_name: str,
        config=Depends(get_config),
    ) -> Dict[str, Any]:
        """Disable a provider."""
        if provider_name not in config.providers:
            raise HTTPException(status_code=404, detail=f"Provider '{provider_name}' not found")
        config.providers[provider_name].enabled = False
        return {"status": "ok", "provider": provider_name, "enabled": False}


    @cache_router.get("/stats", response_model=CacheStatsResponse)
    async def get_cache_stats(
        cache_manager=Depends(get_cache_manager),
    ) -> CacheStatsResponse:
        """Get cache statistics."""
        if not cache_manager:
            raise_cache_not_enabled()

        stats = cache_manager.get_stats()
        return CacheStatsResponse(
            hits=stats.hits,
            misses=stats.misses,
            hit_rate=stats.hit_rate,
            total_entries=stats.total_entries,
            expired_entries=stats.expired_entries,
            total_tokens_saved=stats.total_tokens_saved,
            size_bytes=stats.size_bytes,
            valid_entries=stats.valid_entries,
            valid_size_bytes=stats.valid_size_bytes,
            oldest_entry=stats.oldest_entry,
            newest_entry=stats.newest_entry,
            next_expiration=stats.next_expiration,
            avg_ttl_remaining_s=stats.avg_ttl_remaining_s,
        )


    @cache_router.get("/stats/detailed")
    async def get_cache_stats_detailed(
        cache_manager=Depends(get_cache_manager),
    ) -> Dict[str, Any]:
        """Get detailed cache statistics including per-provider breakdown."""
        if not cache_manager:
            raise_cache_not_enabled()

        stats = cache_manager.get_stats()
        provider_stats = cache_manager.get_provider_stats()
        top_entries = cache_manager.get_top_entries(10)

        return {
            "summary": stats.to_dict(),
            "by_provider": provider_stats,
            "top_entries": [
                {
                    "cache_key": e.cache_key,
                    "provider": e.provider,
                    "hit_count": e.hit_count,
                    "response_preview": e.response[:100] if e.response else None,
                }
                for e in top_entries
            ],
        }


    @cache_router.delete("")
    async def clear_cache(
        provider: Optional[str] = Query(None, description="Clear cache for specific provider"),
        cache_manager=Depends(get_cache_manager),
    ) -> Dict[str, Any]:
        """Clear cache entries."""
        if not cache_manager:
            raise_cache_not_enabled()

        cleared = cache_manager.clear(provider)
        return {"cleared": cleared, "provider": provider}


    @cache_router.post("/cleanup")
    async def cleanup_cache(
        cache_manager=Depends(get_cache_manager),
    ) -> Dict[str, Any]:
        """Remove expired cache entries and enforce max entries limit."""
        if not cache_manager:
            raise_cache_not_enabled()

        expired_removed = cache_manager.cleanup_expired()
        excess_removed = cache_manager.enforce_max_entries()
        return {
            "expired_removed": expired_removed,
            "excess_removed": excess_removed,
            "total_removed": expired_removed + excess_removed,
        }


    @router.post("/keys", response_model=CreateAPIKeyResponse)
    async def create_api_key(
        request: CreateAPIKeyRequest,
        api_key_store=Depends(get_api_key_store),
    ) -> CreateAPIKeyResponse:
        """
        Create a new API key.

        The raw API key is only returned once - store it securely!
        """
        if not api_key_store:
            raise HTTPException(
                status_code=400,
                detail="API key management not enabled",
            )

        api_key, raw_key = api_key_store.create_key(
            name=request.name,
            rate_limit_rpm=request.rate_limit_rpm,
        )

        return CreateAPIKeyResponse(
            key_id=api_key.key_id,
            api_key=raw_key,
            name=api_key.name,
            created_at=api_key.created_at,
        )


    @router.get("/keys", response_model=List[APIKeyInfo])
    async def list_api_keys(
        api_key_store=Depends(get_api_key_store),
    ) -> List[APIKeyInfo]:
        """List all API keys (without the actual key values)."""
        if not api_key_store:
            raise HTTPException(
                status_code=400,
                detail="API key management not enabled",
            )

        keys = api_key_store.list_keys()
        return [
            APIKeyInfo(
                key_id=k.key_id,
                name=k.name,
                created_at=k.created_at,
                last_used_at=k.last_used_at,
                rate_limit_rpm=k.rate_limit_rpm,
                enabled=k.enabled,
            )
            for k in keys
        ]


    @router.delete("/keys/{key_id}")
    async def delete_api_key(
        key_id: str,
        api_key_store=Depends(get_api_key_store),
    ) -> Dict[str, Any]:
        """Delete an API key."""
        if not api_key_store:
            raise HTTPException(
                status_code=400,
                detail="API key management not enabled",
            )

        deleted = api_key_store.delete_key(key_id)
        if not deleted:
            raise_api_key_not_found()

        return {"deleted": True, "key_id": key_id}


    @router.post("/keys/{key_id}/disable")
    async def disable_api_key(
        key_id: str,
        api_key_store=Depends(get_api_key_store),
    ) -> Dict[str, Any]:
        """Disable an API key."""
        if not api_key_store:
            raise HTTPException(
                status_code=400,
                detail="API key management not enabled",
            )

        disabled = api_key_store.disable_key(key_id)
        if not disabled:
            raise_api_key_not_found()

        return {"disabled": True, "key_id": key_id}


    @router.post("/keys/{key_id}/enable")
    async def enable_api_key(
        key_id: str,
        api_key_store=Depends(get_api_key_store),
    ) -> Dict[str, Any]:
        """Enable an API key."""
        if not api_key_store:
            raise HTTPException(
                status_code=400,
                detail="API key management not enabled",
            )

        enabled = api_key_store.enable_key(key_id)
        if not enabled:
            raise_api_key_not_found()

        return {"enabled": True, "key_id": key_id}


    @router.get("/rate-limit/stats")
    async def get_rate_limit_stats(
        rate_limiter=Depends(get_rate_limiter),
    ) -> Dict[str, Any]:
        """Get rate limiter statistics."""
        if not rate_limiter:
            return {"enabled": False}

        return rate_limiter.get_stats()


    @router.get("/rate-limit/config")
    async def get_rate_limit_config(
        config=Depends(get_config),
    ) -> Dict[str, Any]:
        """Get rate limit configuration."""
        return {
            "enabled": config.rate_limit.enabled,
            "requests_per_minute": config.rate_limit.requests_per_minute,
            "burst_size": config.rate_limit.burst_size,
            "by_api_key": config.rate_limit.by_api_key,
            "by_ip": config.rate_limit.by_ip,
            "endpoint_limits": config.rate_limit.endpoint_limits,
        }


    @router.get("/auth/config")
    async def get_auth_config(
        config=Depends(get_config),
    ) -> Dict[str, Any]:
        """Get authentication configuration."""
        return {
            "enabled": config.auth.enabled,
            "header_name": config.auth.header_name,
            "allow_localhost": config.auth.allow_localhost,
            "public_paths": config.auth.public_paths,
        }
