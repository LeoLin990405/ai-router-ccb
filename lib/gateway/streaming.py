"""
Streaming Support for CCB Gateway.

Provides SSE (Server-Sent Events) streaming for real-time AI response delivery.
"""
from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, AsyncIterator, List, TYPE_CHECKING

if TYPE_CHECKING:
    from .models import GatewayRequest

@dataclass
class StreamChunk:
    """A chunk of streamed response."""
    request_id: str
    content: str
    chunk_index: int
    is_final: bool = False
    tokens_used: Optional[int] = None
    provider: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

    def to_sse(self) -> str:
        """Convert to SSE format."""
        data = {
            "type": "chunk" if not self.is_final else "done",
            "request_id": self.request_id,
            "content": self.content,
            "chunk_index": self.chunk_index,
        }
        if self.is_final:
            if self.tokens_used:
                data["tokens_used"] = self.tokens_used
            if self.provider:
                data["provider"] = self.provider
        if self.metadata:
            data["metadata"] = self.metadata
        return f"data: {json.dumps(data)}\n\n"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "request_id": self.request_id,
            "content": self.content,
            "chunk_index": self.chunk_index,
            "is_final": self.is_final,
            "tokens_used": self.tokens_used,
            "provider": self.provider,
            "metadata": self.metadata,
        }

@dataclass
class StreamError:
    """An error during streaming."""
    request_id: str
    error: str
    error_type: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

    def to_sse(self) -> str:
        """Convert to SSE format."""
        data = {
            "type": "error",
            "request_id": self.request_id,
            "error": self.error,
        }
        if self.error_type:
            data["error_type"] = self.error_type
        if self.metadata:
            data["metadata"] = self.metadata
        return f"data: {json.dumps(data)}\n\n"

@dataclass
class StreamConfig:
    """Configuration for streaming."""
    enabled: bool = True
    chunk_size: int = 50  # Characters per chunk for simulated streaming
    chunk_delay_ms: float = 50.0  # Delay between chunks for simulated streaming
    heartbeat_interval_s: float = 15.0  # SSE heartbeat interval
    timeout_s: float = 300.0  # Stream timeout

class StreamBuffer:
    """
    Buffer for accumulating and chunking streamed content.

    Used when backends provide streaming but we need to process/transform chunks.
    """

    def __init__(self, request_id: str, chunk_size: int = 50):
        self.request_id = request_id
        self.chunk_size = chunk_size
        self.buffer = ""
        self.chunk_index = 0
        self.total_content = ""

    def add(self, content: str) -> List[StreamChunk]:
        """
        Add content to buffer and return any complete chunks.

        Args:
            content: New content to add

        Returns:
            List of complete chunks
        """
        self.buffer += content
        self.total_content += content
        chunks = []

        while len(self.buffer) >= self.chunk_size:
            chunk_content = self.buffer[:self.chunk_size]
            self.buffer = self.buffer[self.chunk_size:]
            chunks.append(StreamChunk(
                request_id=self.request_id,
                content=chunk_content,
                chunk_index=self.chunk_index,
            ))
            self.chunk_index += 1

        return chunks

    def flush(self, tokens_used: Optional[int] = None, provider: Optional[str] = None) -> StreamChunk:
        """
        Flush remaining buffer and return final chunk.

        Args:
            tokens_used: Total tokens used
            provider: Provider name

        Returns:
            Final chunk with remaining content
        """
        chunk = StreamChunk(
            request_id=self.request_id,
            content=self.buffer,
            chunk_index=self.chunk_index,
            is_final=True,
            tokens_used=tokens_used,
            provider=provider,
        )
        self.buffer = ""
        return chunk

async def simulate_streaming(
    request_id: str,
    content: str,
    config: StreamConfig,
    provider: Optional[str] = None,
    tokens_used: Optional[int] = None,
) -> AsyncIterator[StreamChunk]:
    """
    Simulate streaming for backends that don't support native streaming.

    Breaks content into chunks and yields them with delays.

    Args:
        request_id: Request ID
        content: Full content to stream
        config: Stream configuration
        provider: Provider name
        tokens_used: Total tokens used

    Yields:
        StreamChunk objects
    """
    chunk_size = config.chunk_size
    delay_s = config.chunk_delay_ms / 1000.0
    chunk_index = 0

    for i in range(0, len(content), chunk_size):
        chunk_content = content[i:i + chunk_size]
        is_final = i + chunk_size >= len(content)

        yield StreamChunk(
            request_id=request_id,
            content=chunk_content,
            chunk_index=chunk_index,
            is_final=is_final,
            tokens_used=tokens_used if is_final else None,
            provider=provider if is_final else None,
        )

        chunk_index += 1

        if not is_final:
            await asyncio.sleep(delay_s)

async def stream_anthropic_response(
    session,
    url: str,
    headers: Dict[str, str],
    payload: Dict[str, Any],
    request_id: str,
    timeout_s: float = 300.0,
) -> AsyncIterator[StreamChunk]:
    """
    Stream response from Anthropic API.

    Args:
        session: aiohttp session
        url: API URL
        headers: Request headers
        payload: Request payload
        request_id: Request ID
        timeout_s: Timeout in seconds

    Yields:
        StreamChunk objects
    """
    import aiohttp

    # Enable streaming in payload
    payload = payload.copy()
    payload["stream"] = True

    chunk_index = 0
    total_content = ""

    timeout = aiohttp.ClientTimeout(total=timeout_s)

    async with session.post(url, json=payload, headers=headers, timeout=timeout) as resp:
        if resp.status != 200:
            error_text = await resp.text()
            yield StreamChunk(
                request_id=request_id,
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
                                total_content += text
                                yield StreamChunk(
                                    request_id=request_id,
                                    content=text,
                                    chunk_index=chunk_index,
                                )
                                chunk_index += 1

                    elif event_type == "message_stop":
                        # Final message
                        usage = data.get("usage", {})
                        tokens_used = usage.get("input_tokens", 0) + usage.get("output_tokens", 0)
                        yield StreamChunk(
                            request_id=request_id,
                            content="",
                            chunk_index=chunk_index,
                            is_final=True,
                            tokens_used=tokens_used if tokens_used else None,
                        )
                        return

                except json.JSONDecodeError:
                    continue

    # If we get here without a message_stop, send final chunk
    yield StreamChunk(
        request_id=request_id,
        content="",
        chunk_index=chunk_index,
        is_final=True,
    )

async def stream_openai_response(
    session,
    url: str,
    headers: Dict[str, str],
    payload: Dict[str, Any],
    request_id: str,
    timeout_s: float = 300.0,
) -> AsyncIterator[StreamChunk]:
    """
    Stream response from OpenAI-compatible API.

    Args:
        session: aiohttp session
        url: API URL
        headers: Request headers
        payload: Request payload
        request_id: Request ID
        timeout_s: Timeout in seconds

    Yields:
        StreamChunk objects
    """
    import aiohttp

    # Enable streaming in payload
    payload = payload.copy()
    payload["stream"] = True

    chunk_index = 0
    total_tokens = 0

    timeout = aiohttp.ClientTimeout(total=timeout_s)

    async with session.post(url, json=payload, headers=headers, timeout=timeout) as resp:
        if resp.status != 200:
            error_text = await resp.text()
            yield StreamChunk(
                request_id=request_id,
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
                        request_id=request_id,
                        content="",
                        chunk_index=chunk_index,
                        is_final=True,
                        tokens_used=total_tokens if total_tokens else None,
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
                                request_id=request_id,
                                content=content,
                                chunk_index=chunk_index,
                            )
                            chunk_index += 1

                        # Check for finish reason
                        if choices[0].get("finish_reason"):
                            usage = data.get("usage", {})
                            total_tokens = usage.get("total_tokens", 0)

                except json.JSONDecodeError:
                    continue

    # If we get here without [DONE], send final chunk
    yield StreamChunk(
        request_id=request_id,
        content="",
        chunk_index=chunk_index,
        is_final=True,
    )

async def heartbeat_generator(
    interval_s: float = 15.0,
) -> AsyncIterator[str]:
    """
    Generate SSE heartbeat comments.

    Args:
        interval_s: Interval between heartbeats

    Yields:
        SSE comment strings
    """
    while True:
        await asyncio.sleep(interval_s)
        yield ": heartbeat\n\n"

class StreamManager:
    """
    Manages streaming responses for the gateway.

    Handles both native streaming backends and simulated streaming.
    """

    def __init__(self, config: Optional[StreamConfig] = None):
        """
        Initialize the stream manager.

        Args:
            config: Stream configuration
        """
        self.config = config or StreamConfig()
        self._active_streams: Dict[str, asyncio.Task] = {}

    async def stream_response(
        self,
        request_id: str,
        provider: str,
        backend,
        request: "GatewayRequest",
    ) -> AsyncIterator[str]:
        """
        Stream a response from a backend.

        Args:
            request_id: Request ID
            provider: Provider name
            backend: Backend instance
            request: Gateway request

        Yields:
            SSE formatted strings
        """
        try:
            # Check if backend supports native streaming
            if hasattr(backend, "execute_stream"):
                async for chunk in backend.execute_stream(request):
                    yield chunk.to_sse()
            else:
                # Fall back to simulated streaming
                result = await backend.execute(request)

                if result.success and result.response:
                    async for chunk in simulate_streaming(
                        request_id=request_id,
                        content=result.response,
                        config=self.config,
                        provider=provider,
                        tokens_used=result.tokens_used,
                    ):
                        yield chunk.to_sse()
                else:
                    # Error response
                    yield StreamError(
                        request_id=request_id,
                        error=result.error or "Unknown error",
                    ).to_sse()

        except asyncio.CancelledError:
            yield StreamError(
                request_id=request_id,
                error="Stream cancelled",
                error_type="cancelled",
            ).to_sse()
        except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError) as e:
            yield StreamError(
                request_id=request_id,
                error=str(e),
                error_type="exception",
            ).to_sse()

    def cancel_stream(self, request_id: str) -> bool:
        """
        Cancel an active stream.

        Args:
            request_id: Request ID to cancel

        Returns:
            True if stream was cancelled
        """
        task = self._active_streams.get(request_id)
        if task and not task.done():
            task.cancel()
            return True
        return False
