"""HTTP request execution helpers for provider-specific payload formats."""

from __future__ import annotations

from typing import Any, Callable, Dict, Optional, Tuple

from ..base_backend import BackendResult
from ...models import GatewayRequest


ExtractFn = Callable[[str, Dict[str, Any]], Tuple[str, Optional[int]]]


async def execute_anthropic_request(
    *,
    session,
    request: GatewayRequest,
    api_key: str,
    api_base_url: str,
    model: str,
    max_tokens: int,
    extract_response_and_tokens: ExtractFn,
) -> BackendResult:
    """Execute request using Anthropic API format."""
    url = f"{api_base_url}/messages"

    headers = {
        "Content-Type": "application/json",
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
    }

    payload = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": request.message}],
    }

    async with session.post(url, json=payload, headers=headers) as resp:
        if resp.status != 200:
            error_text = await resp.text()
            return BackendResult.fail(f"API error {resp.status}: {error_text}")

        data = await resp.json()
        response_text, tokens_used = extract_response_and_tokens("anthropic", data)

        return BackendResult.ok(
            response=response_text,
            tokens_used=tokens_used,
            metadata={"model": data.get("model"), "stop_reason": data.get("stop_reason")},
        )


async def execute_gemini_request(
    *,
    session,
    request: GatewayRequest,
    api_key: str,
    api_base_url: str,
    model: str,
    max_tokens: int,
    extract_response_and_tokens: ExtractFn,
) -> BackendResult:
    """Execute request using Google Gemini API format."""
    base_url = api_base_url.rstrip("/")
    url = f"{base_url}/models/{model}:generateContent?key={api_key}"

    headers = {
        "Content-Type": "application/json",
    }

    payload = {
        "contents": [{"parts": [{"text": request.message}]}],
        "generationConfig": {
            "maxOutputTokens": max_tokens,
        },
    }

    async with session.post(url, json=payload, headers=headers) as resp:
        if resp.status != 200:
            error_text = await resp.text()
            return BackendResult.fail(f"Gemini API error {resp.status}: {error_text}")

        data = await resp.json()
        response_text, tokens_used = extract_response_and_tokens("gemini", data)
        candidates = data.get("candidates", [])

        return BackendResult.ok(
            response=response_text,
            tokens_used=tokens_used,
            metadata={
                "model": model,
                "finish_reason": candidates[0].get("finishReason") if candidates else None,
            },
        )


async def execute_openai_compatible_request(
    *,
    session,
    request: GatewayRequest,
    api_key: str,
    api_base_url: str,
    model: str,
    max_tokens: int,
    extract_response_and_tokens: ExtractFn,
) -> BackendResult:
    """Execute request using OpenAI-compatible API format."""
    url = f"{api_base_url}/chat/completions"

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }

    payload = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": request.message}],
    }

    async with session.post(url, json=payload, headers=headers) as resp:
        if resp.status != 200:
            error_text = await resp.text()
            return BackendResult.fail(f"API error {resp.status}: {error_text}")

        data = await resp.json()
        response_text, tokens_used = extract_response_and_tokens("openai", data)
        choices = data.get("choices", [])

        return BackendResult.ok(
            response=response_text,
            tokens_used=tokens_used,
            metadata={
                "model": data.get("model"),
                "finish_reason": choices[0].get("finish_reason") if choices else None,
            },
        )
