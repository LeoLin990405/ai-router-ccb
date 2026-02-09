"""HTTP streaming helpers for provider-specific SSE formats."""

from __future__ import annotations

import json
from typing import AsyncGenerator


from ...models import GatewayRequest
from ...streaming import StreamChunk


async def stream_anthropic_response(
    *,
    session,
    request: GatewayRequest,
    api_key: str,
    api_base_url: str,
    model: str,
    max_tokens: int,
    timeout_s: float,
    provider_name: str,
) -> AsyncGenerator[StreamChunk, None]:
    """Stream response from Anthropic Messages API."""
    import aiohttp

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
        "stream": True,
    }

    chunk_index = 0
    total_tokens = 0

    timeout = aiohttp.ClientTimeout(total=timeout_s)

    async with session.post(url, json=payload, headers=headers, timeout=timeout) as resp:
        if resp.status != 200:
            error_text = await resp.text()
            yield StreamChunk(
                request_id=request.id,
                content="",
                chunk_index=0,
                is_final=True,
                metadata={"error": f"API error {resp.status}: {error_text}"},
            )
            return

        async for line in resp.content:
            line = line.decode("utf-8").strip()

            if not line or line.startswith(":"):
                continue

            if line.startswith("data: "):
                data_str = line[6:]

                if data_str == "[DONE]":
                    break

                try:
                    data = json.loads(data_str)
                    event_type = data.get("type", "")

                    if event_type == "content_block_delta":
                        delta = data.get("delta", {})
                        if delta.get("type") == "text_delta":
                            text = delta.get("text", "")
                            if text:
                                yield StreamChunk(
                                    request_id=request.id,
                                    content=text,
                                    chunk_index=chunk_index,
                                    provider=provider_name,
                                )
                                chunk_index += 1

                    elif event_type == "message_delta":
                        usage = data.get("usage", {})
                        total_tokens = usage.get("output_tokens", 0)

                    elif event_type == "message_stop":
                        yield StreamChunk(
                            request_id=request.id,
                            content="",
                            chunk_index=chunk_index,
                            is_final=True,
                            tokens_used=total_tokens,
                            provider=provider_name,
                        )
                        return

                except json.JSONDecodeError:
                    continue

    yield StreamChunk(
        request_id=request.id,
        content="",
        chunk_index=chunk_index,
        is_final=True,
        tokens_used=total_tokens,
        provider=provider_name,
    )


async def stream_openai_compatible_response(
    *,
    session,
    request: GatewayRequest,
    api_key: str,
    api_base_url: str,
    model: str,
    max_tokens: int,
    timeout_s: float,
    provider_name: str,
) -> AsyncGenerator[StreamChunk, None]:
    """Stream response from OpenAI-compatible chat completion API."""
    import aiohttp

    url = f"{api_base_url}/chat/completions"

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }

    payload = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": request.message}],
        "stream": True,
    }

    chunk_index = 0
    total_tokens = 0

    timeout = aiohttp.ClientTimeout(total=timeout_s)

    async with session.post(url, json=payload, headers=headers, timeout=timeout) as resp:
        if resp.status != 200:
            error_text = await resp.text()
            yield StreamChunk(
                request_id=request.id,
                content="",
                chunk_index=0,
                is_final=True,
                metadata={"error": f"API error {resp.status}: {error_text}"},
            )
            return

        async for line in resp.content:
            line = line.decode("utf-8").strip()

            if not line or line.startswith(":"):
                continue

            if line.startswith("data: "):
                data_str = line[6:]

                if data_str == "[DONE]":
                    yield StreamChunk(
                        request_id=request.id,
                        content="",
                        chunk_index=chunk_index,
                        is_final=True,
                        tokens_used=total_tokens if total_tokens else None,
                        provider=provider_name,
                    )
                    return

                try:
                    data = json.loads(data_str)
                    choices = data.get("choices", [])

                    if choices:
                        delta = choices[0].get("delta", {})
                        content = delta.get("content", "")

                        if content:
                            yield StreamChunk(
                                request_id=request.id,
                                content=content,
                                chunk_index=chunk_index,
                                provider=provider_name,
                            )
                            chunk_index += 1

                        if choices[0].get("finish_reason"):
                            usage = data.get("usage", {})
                            total_tokens = usage.get("total_tokens", 0)

                except json.JSONDecodeError:
                    continue

    yield StreamChunk(
        request_id=request.id,
        content="",
        chunk_index=chunk_index,
        is_final=True,
        tokens_used=total_tokens if total_tokens else None,
        provider=provider_name,
    )
