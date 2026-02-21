"""
HTTP API Backend for CCB Gateway.

Supports OpenAI-compatible APIs (Anthropic, OpenAI, etc.)
"""
from __future__ import annotations

import asyncio
import os
import time
from typing import Any, AsyncGenerator, Dict, Optional

from lib.common.errors import BackendError
from lib.common.logging import get_logger
from .base_backend import BaseBackend, BackendResult
from ..gateway_config import ProviderConfig
from ..models import GatewayRequest
from ..streaming import StreamChunk
from .executors.http_request import (
    execute_anthropic_request,
    execute_gemini_request,
    execute_openai_compatible_request,
)
from .executors.http_stream import (
    stream_anthropic_response,
    stream_openai_compatible_response,
)
from .extractors import AnthropicExtractor, GeminiExtractor, OpenAIExtractor
from .http_profile import HTTPExecutionProfile, resolve_http_profile


logger = get_logger("gateway.backends.http_backend")


class HTTPBackend(BaseBackend):
    """HTTP API backend for providers with REST APIs."""

    def __init__(self, config: ProviderConfig):
        super().__init__(config)
        self._session = None
        self._api_key: Optional[str] = None
        self._extractors = {
            "anthropic": AnthropicExtractor(),
            "gemini": GeminiExtractor(),
            "openai": OpenAIExtractor(),
        }

    def _get_api_key(self) -> Optional[str]:
        """Get API key from environment or direct value."""
        if self._api_key:
            return self._api_key

        if self.config.api_key_env:
            env_value = os.environ.get(self.config.api_key_env)
            if env_value:
                self._api_key = env_value
            elif self.config.api_key_env.startswith(("sk-", "sess-", "key-", "api-")):
                self._api_key = self.config.api_key_env
            else:
                self._api_key = env_value
        return self._api_key

    async def _get_session(self):
        """Get or create aiohttp session."""
        if self._session is None:
            try:
                import aiohttp

                timeout = aiohttp.ClientTimeout(total=self.config.timeout_s)
                self._session = aiohttp.ClientSession(timeout=timeout)
            except ImportError:
                raise ImportError("aiohttp is required for HTTP backend. Install with: pip install aiohttp")
        return self._session

    def _detect_api_kind(self) -> str:
        """Detect provider API format family."""
        base_url = (self.config.api_base_url or "").lower()
        provider_name = (self.config.name or "").lower()

        if "anthropic" in base_url or provider_name == "anthropic":
            return "anthropic"

        if "generativelanguage.googleapis" in base_url or provider_name == "gemini":
            return "gemini"

        return "openai"

    def _extract_response_and_tokens(self, api_kind: str, data: Dict[str, Any]) -> tuple[str, Optional[int]]:
        """Extract response text and token usage using provider strategy."""
        extractor = self._extractors.get(api_kind, self._extractors["openai"])
        response_text = extractor.extract_response(data)
        tokens_used = extractor.extract_tokens(data)
        return response_text, tokens_used

    def _resolve_profile(self, api_kind: str) -> HTTPExecutionProfile:
        """Resolve effective settings for the requested API kind."""
        return resolve_http_profile(self.config, api_kind)

    async def _execute_by_api_kind(
        self,
        api_kind: str,
        request: GatewayRequest,
        api_key: str,
    ) -> BackendResult:
        """Dispatch request execution by detected API kind."""
        normalized_kind = self._resolve_profile(api_kind).api_kind
        handler_map = {
            "anthropic": self._execute_anthropic,
            "gemini": self._execute_gemini,
            "openai": self._execute_openai_compatible,
        }
        handler = handler_map.get(normalized_kind, self._execute_openai_compatible)
        return await handler(request, api_key)

    async def execute(self, request: GatewayRequest) -> BackendResult:
        """Execute request via HTTP API."""
        start_time = time.time()

        api_key = self._get_api_key()
        if not api_key:
            error_msg = f"API key not found in environment variable: {self.config.api_key_env}"
            logger.debug("%s", error_msg)
            return BackendResult.fail(
                error_msg,
                latency_ms=(time.time() - start_time) * 1000,
            )

        try:
            api_kind = self._detect_api_kind()
            result = await self._execute_by_api_kind(api_kind, request, api_key)
            result.latency_ms = (time.time() - start_time) * 1000
            return result

        except asyncio.TimeoutError:
            return BackendResult.fail(
                f"Request timed out after {self.config.timeout_s}s",
                latency_ms=(time.time() - start_time) * 1000,
            )
        except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError) as exc:
            logger.exception("Unexpected HTTP backend error for %s", self.config.name)
            return BackendResult.fail(
                str(BackendError(f"Unexpected HTTP backend error: {exc}")),
                latency_ms=(time.time() - start_time) * 1000,
            )

    async def _execute_anthropic(
        self,
        request: GatewayRequest,
        api_key: str,
    ) -> BackendResult:
        """Execute request using Anthropic API format."""
        profile = self._resolve_profile("anthropic")
        session = await self._get_session()
        return await execute_anthropic_request(
            session=session,
            request=request,
            api_key=api_key,
            api_base_url=profile.api_base_url,
            model=profile.model,
            max_tokens=profile.max_tokens,
            extract_response_and_tokens=self._extract_response_and_tokens,
        )

    async def _execute_gemini(
        self,
        request: GatewayRequest,
        api_key: str,
    ) -> BackendResult:
        """Execute request using Google Gemini API format."""
        profile = self._resolve_profile("gemini")
        session = await self._get_session()
        return await execute_gemini_request(
            session=session,
            request=request,
            api_key=api_key,
            api_base_url=profile.api_base_url,
            model=profile.model,
            max_tokens=profile.max_tokens,
            extract_response_and_tokens=self._extract_response_and_tokens,
        )

    async def _execute_openai_compatible(
        self,
        request: GatewayRequest,
        api_key: str,
    ) -> BackendResult:
        """Execute request using OpenAI-compatible API format."""
        profile = self._resolve_profile("openai")
        session = await self._get_session()
        return await execute_openai_compatible_request(
            session=session,
            request=request,
            api_key=api_key,
            api_base_url=profile.api_base_url,
            model=profile.model,
            max_tokens=profile.max_tokens,
            extract_response_and_tokens=self._extract_response_and_tokens,
        )

    async def health_check(self) -> bool:
        """Check if the API is accessible."""
        api_key = self._get_api_key()
        if not api_key:
            return False

        try:
            if "anthropic" in (self.config.api_base_url or "").lower():
                return True

            import aiohttp

            session = await self._get_session()
            url = f"{self.config.api_base_url}/models"
            headers = {"Authorization": f"Bearer {api_key}"}

            async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                return resp.status == 200

        except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError):
            logger.debug("HTTP health check failed for %s", self.config.name, exc_info=True)
            return False

    async def shutdown(self) -> None:
        """Close the HTTP session."""
        if self._session:
            await self._session.close()
            self._session = None

    async def _execute_stream_by_api_kind(
        self,
        api_kind: str,
        request: GatewayRequest,
        api_key: str,
    ) -> AsyncGenerator[StreamChunk, None]:
        """Dispatch streaming execution by detected API kind."""
        normalized_kind = self._resolve_profile(api_kind).api_kind

        if normalized_kind == "anthropic":
            async for chunk in self._stream_anthropic(request, api_key):
                yield chunk
            return

        if normalized_kind == "gemini":
            result = await self._execute_gemini(request, api_key)
            yield StreamChunk(
                request_id=request.id,
                content=result.response or "",
                chunk_index=0,
                is_final=True,
                tokens_used=result.tokens_used,
                provider=self.config.name,
            )
            return

        async for chunk in self._stream_openai_compatible(request, api_key):
            yield chunk

    async def execute_stream(
        self,
        request: GatewayRequest,
    ) -> AsyncGenerator[StreamChunk, None]:
        """Execute request with streaming response."""
        api_key = self._get_api_key()
        if not api_key:
            yield StreamChunk(
                request_id=request.id,
                content="",
                chunk_index=0,
                is_final=True,
                metadata={"error": f"API key not found: {self.config.api_key_env}"},
            )
            return

        try:
            api_kind = self._detect_api_kind()
            async for chunk in self._execute_stream_by_api_kind(api_kind, request, api_key):
                yield chunk

        except asyncio.TimeoutError:
            yield StreamChunk(
                request_id=request.id,
                content="",
                chunk_index=0,
                is_final=True,
                metadata={"error": f"Request timed out after {self.config.timeout_s}s"},
            )
        except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError) as exc:
            logger.exception("Unexpected HTTP stream error for %s", self.config.name)
            yield StreamChunk(
                request_id=request.id,
                content="",
                chunk_index=0,
                is_final=True,
                metadata={"error": str(BackendError(f"Unexpected HTTP stream error: {exc}"))},
            )

    async def _stream_anthropic(
        self,
        request: GatewayRequest,
        api_key: str,
    ) -> AsyncGenerator[StreamChunk, None]:
        """Stream response from Anthropic API."""
        profile = self._resolve_profile("anthropic")
        session = await self._get_session()
        async for chunk in stream_anthropic_response(
            session=session,
            request=request,
            api_key=api_key,
            api_base_url=profile.api_base_url,
            model=profile.model,
            max_tokens=profile.max_tokens,
            timeout_s=profile.timeout_s,
            provider_name=profile.provider_name,
        ):
            yield chunk

    async def _stream_openai_compatible(
        self,
        request: GatewayRequest,
        api_key: str,
    ) -> AsyncGenerator[StreamChunk, None]:
        """Stream response from OpenAI-compatible API."""
        profile = self._resolve_profile("openai")
        session = await self._get_session()
        async for chunk in stream_openai_compatible_response(
            session=session,
            request=request,
            api_key=api_key,
            api_base_url=profile.api_base_url,
            model=profile.model,
            max_tokens=profile.max_tokens,
            timeout_s=profile.timeout_s,
            provider_name=profile.provider_name,
        ):
            yield chunk
