"""
Request Queue for CCB Gateway.

Priority-based request queue with concurrent processing support.
"""
from __future__ import annotations

import asyncio
import threading
import time
from dataclasses import dataclass
from typing import Optional, List, Dict, Callable, Awaitable, Any
from queue import PriorityQueue, Empty
import heapq

from .models import GatewayRequest, RequestStatus
from .state_store import StateStore


@dataclass(order=True)
class PrioritizedRequest:
    """Wrapper for priority queue ordering."""
    priority: int  # Negative for max-heap behavior
    created_at: float
    request: GatewayRequest

    def __init__(self, request: GatewayRequest):
        # Higher priority = lower number for min-heap
        self.priority = -request.priority
        self.created_at = request.created_at
        self.request = request


class RequestQueue:
    """
    Priority-based request queue with persistence.

    Features:
    - Priority ordering (higher priority first)
    - FIFO within same priority
    - Persistence via StateStore
    - Concurrent processing with limits
    - Timeout handling
    """

    def __init__(
        self,
        store: StateStore,
        max_size: int = 1000,
        max_concurrent: int = 10,
    ):
        """
        Initialize the request queue.

        Args:
            store: StateStore for persistence
            max_size: Maximum queue size
            max_concurrent: Maximum concurrent requests
        """
        self.store = store
        self.max_size = max_size
        self.max_concurrent = max_concurrent

        # In-memory priority queue
        self._queue: List[PrioritizedRequest] = []
        self._lock = threading.Lock()

        # Processing tracking
        self._processing: Dict[str, GatewayRequest] = {}
        self._processing_lock = threading.Lock()

        # Callbacks
        self._on_request_ready: Optional[Callable[[GatewayRequest], Awaitable[None]]] = None

        # Load pending requests from store
        self._load_pending()

    def _load_pending(self) -> None:
        """Load pending requests from store on startup."""
        pending = self.store.list_requests(status=RequestStatus.QUEUED, limit=self.max_size)
        with self._lock:
            for request in pending:
                heapq.heappush(self._queue, PrioritizedRequest(request))

    def enqueue(self, request: GatewayRequest) -> bool:
        """
        Add a request to the queue.

        Args:
            request: The request to enqueue

        Returns:
            True if enqueued, False if queue is full
        """
        with self._lock:
            if len(self._queue) >= self.max_size:
                return False

            # Persist to store
            self.store.create_request(request)

            # Add to in-memory queue
            heapq.heappush(self._queue, PrioritizedRequest(request))
            return True

    def dequeue(self) -> Optional[GatewayRequest]:
        """
        Get the next request from the queue.

        Returns:
            Next request or None if queue is empty or at capacity
        """
        with self._processing_lock:
            if len(self._processing) >= self.max_concurrent:
                return None

        with self._lock:
            while self._queue:
                item = heapq.heappop(self._queue)
                request = item.request

                # Verify still queued in store
                stored = self.store.get_request(request.id)
                if stored and stored.status == RequestStatus.QUEUED:
                    with self._processing_lock:
                        self._processing[request.id] = request
                    return request

        return None

    def batch_dequeue(self, max_batch: int = 5) -> List[GatewayRequest]:
        """
        Get multiple requests from the queue in a single operation.

        This reduces lock contention when processing multiple requests.

        Args:
            max_batch: Maximum number of requests to dequeue at once

        Returns:
            List of requests (may be fewer than max_batch if queue is low or at capacity)
        """
        result = []

        with self._processing_lock:
            available_slots = self.max_concurrent - len(self._processing)
            if available_slots <= 0:
                return result
            max_to_dequeue = min(max_batch, available_slots)

        with self._lock:
            while self._queue and len(result) < max_to_dequeue:
                item = heapq.heappop(self._queue)
                request = item.request

                # Verify still queued in store
                stored = self.store.get_request(request.id)
                if stored and stored.status == RequestStatus.QUEUED:
                    result.append(request)

            # Add all successfully dequeued requests to processing
            if result:
                with self._processing_lock:
                    for request in result:
                        self._processing[request.id] = request

        return result

    def mark_processing(self, request_id: str) -> bool:
        """Mark a request as processing."""
        return self.store.update_request_status(request_id, RequestStatus.PROCESSING)

    def mark_completed(
        self,
        request_id: str,
        response: Optional[str] = None,
        error: Optional[str] = None,
    ) -> bool:
        """Mark a request as completed or failed."""
        with self._processing_lock:
            self._processing.pop(request_id, None)

        if error:
            return self.store.update_request_status(request_id, RequestStatus.FAILED)
        return self.store.update_request_status(request_id, RequestStatus.COMPLETED)

    def cancel(self, request_id: str) -> bool:
        """Cancel a request."""
        with self._processing_lock:
            self._processing.pop(request_id, None)

        # Remove from in-memory queue
        with self._lock:
            self._queue = [
                item for item in self._queue
                if item.request.id != request_id
            ]
            heapq.heapify(self._queue)

        return self.store.cancel_request(request_id)

    def get_queue_depth(self, provider: Optional[str] = None) -> int:
        """Get current queue depth, optionally filtered by provider."""
        with self._lock:
            if provider:
                return sum(
                    1 for item in self._queue
                    if item.request.provider == provider
                )
            return len(self._queue)

    def get_processing_count(self) -> int:
        """Get number of requests currently processing."""
        with self._processing_lock:
            return len(self._processing)

    def get_processing_requests(self) -> List[GatewayRequest]:
        """Get list of currently processing requests."""
        with self._processing_lock:
            return list(self._processing.values())

    def check_timeouts(self) -> List[str]:
        """Check for timed out requests and mark them."""
        now = time.time()
        timed_out = []

        with self._processing_lock:
            for request_id, request in list(self._processing.items()):
                if request.started_at:
                    elapsed = now - request.started_at
                    if elapsed > request.timeout_s:
                        timed_out.append(request_id)
                        self._processing.pop(request_id, None)
                        # Update DB while holding lock to prevent race conditions
                        self.store.update_request_status(request_id, RequestStatus.TIMEOUT)

        return timed_out

    def peek(self, count: int = 10) -> List[GatewayRequest]:
        """Peek at the next N requests without removing them."""
        with self._lock:
            items = heapq.nsmallest(count, self._queue)
            return [item.request for item in items]

    def clear(self) -> int:
        """Clear all queued requests."""
        with self._lock:
            count = len(self._queue)
            for item in self._queue:
                self.store.cancel_request(item.request.id)
            self._queue.clear()
            return count

    def stats(self) -> Dict[str, Any]:
        """Get queue statistics."""
        with self._lock:
            queue_depth = len(self._queue)
            by_provider: Dict[str, int] = {}
            by_priority: Dict[int, int] = {}

            for item in self._queue:
                provider = item.request.provider
                priority = item.request.priority
                by_provider[provider] = by_provider.get(provider, 0) + 1
                by_priority[priority] = by_priority.get(priority, 0) + 1

        with self._processing_lock:
            processing_count = len(self._processing)

        return {
            "queue_depth": queue_depth,
            "processing_count": processing_count,
            "max_size": self.max_size,
            "max_concurrent": self.max_concurrent,
            "by_provider": by_provider,
            "by_priority": by_priority,
        }


class AsyncRequestQueue:
    """
    Async wrapper for RequestQueue with event-driven processing.

    Supports true concurrent processing of multiple requests up to max_concurrent.
    """

    def __init__(self, queue: RequestQueue):
        self.queue = queue
        self._event = asyncio.Event()
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._active_tasks: Dict[str, asyncio.Task] = {}
        self._tasks_lock = asyncio.Lock()

    async def start(
        self,
        handler: Callable[[GatewayRequest], Awaitable[None]],
    ) -> None:
        """Start the async queue processor."""
        self._running = True
        self._task = asyncio.create_task(self._process_loop(handler))

    async def stop(self) -> None:
        """Stop the async queue processor."""
        self._running = False
        self._event.set()

        # Cancel all active tasks
        async with self._tasks_lock:
            for task in self._active_tasks.values():
                task.cancel()
            self._active_tasks.clear()

        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    def notify(self) -> None:
        """Notify that new requests are available."""
        self._event.set()

    async def _process_loop(
        self,
        handler: Callable[[GatewayRequest], Awaitable[None]],
    ) -> None:
        """Main processing loop with true concurrent execution and batch dequeue support."""
        while self._running:
            # Check for timeouts
            self.queue.check_timeouts()

            # Clean up completed tasks
            await self._cleanup_completed_tasks()

            # Try batch dequeue for better efficiency
            requests = self.queue.batch_dequeue(max_batch=5)
            if requests:
                for request in requests:
                    self.queue.mark_processing(request.id)
                    # Spawn task for concurrent execution (don't await!)
                    task = asyncio.create_task(
                        self._handle_request(handler, request)
                    )
                    async with self._tasks_lock:
                        self._active_tasks[request.id] = task
            else:
                # No requests available, wait for notification or timeout
                self._event.clear()
                try:
                    await asyncio.wait_for(self._event.wait(), timeout=0.5)
                except asyncio.TimeoutError:
                    pass

    async def _handle_request(
        self,
        handler: Callable[[GatewayRequest], Awaitable[None]],
        request: GatewayRequest,
    ) -> None:
        """Handle a single request and clean up when done."""
        try:
            await handler(request)
        except Exception as e:
            self.queue.mark_completed(request.id, error=str(e))
        finally:
            # Remove from active tasks
            async with self._tasks_lock:
                self._active_tasks.pop(request.id, None)

    async def _cleanup_completed_tasks(self) -> None:
        """Remove completed tasks from tracking."""
        async with self._tasks_lock:
            completed = [
                rid for rid, task in self._active_tasks.items()
                if task.done()
            ]
            for rid in completed:
                self._active_tasks.pop(rid, None)
