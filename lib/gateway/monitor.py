"""
Monitor Service for CCB Gateway.

Provides real-time monitoring of gateway activity for human observation.
This is the "视窗层" (view layer) that displays AI work status without
participating in message passing.
"""
from __future__ import annotations

import asyncio
import time
from datetime import datetime
from typing import Optional, Dict, Any, List

from lib.common.logging import get_logger

from .models import RequestStatus, WebSocketEvent
from .state_store import StateStore
from .request_queue import RequestQueue


logger = get_logger("gateway.monitor")


class MonitorService:
    """
    Monitor service for observing gateway activity.

    Features:
    - Real-time request/response logging
    - Provider status display
    - Queue depth monitoring
    - Performance metrics
    """

    def __init__(
        self,
        store: StateStore,
        queue: RequestQueue,
        refresh_interval: float = 1.0,
    ):
        """
        Initialize the monitor service.

        Args:
            store: State store instance
            queue: Request queue instance
            refresh_interval: How often to refresh display (seconds)
        """
        self.store = store
        self.queue = queue
        self.refresh_interval = refresh_interval
        self._running = False
        self._last_events: List[Dict[str, Any]] = []
        self._max_events = 50

    def add_event(self, event: WebSocketEvent) -> None:
        """Add an event to the event log."""
        self._last_events.append({
            "type": event.type,
            "data": event.data,
            "timestamp": event.timestamp,
            "time_str": datetime.fromtimestamp(event.timestamp).strftime("%H:%M:%S"),
        })
        # Keep only recent events
        if len(self._last_events) > self._max_events:
            self._last_events = self._last_events[-self._max_events:]

    def get_dashboard_data(self) -> Dict[str, Any]:
        """Get data for dashboard display."""
        stats = self.store.get_stats()
        queue_stats = self.queue.stats()
        providers = self.store.list_provider_status()

        return {
            "timestamp": time.time(),
            "time_str": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "requests": {
                "total": stats["total_requests"],
                "active": stats["active_requests"],
                "queued": queue_stats["queue_depth"],
                "processing": queue_stats["processing_count"],
                "by_status": stats["status_counts"],
            },
            "queue": {
                "depth": queue_stats["queue_depth"],
                "max_size": queue_stats["max_size"],
                "by_provider": queue_stats["by_provider"],
                "by_priority": queue_stats["by_priority"],
            },
            "providers": [
                {
                    "name": p.name,
                    "status": p.status.value,
                    "queue_depth": p.queue_depth,
                    "avg_latency_ms": p.avg_latency_ms,
                    "success_rate": p.success_rate,
                    "enabled": p.enabled,
                }
                for p in providers
            ],
            "recent_events": self._last_events[-10:],
        }

    def format_terminal_display(self) -> str:
        """Format dashboard data for terminal display."""
        data = self.get_dashboard_data()

        lines = [
            "=" * 60,
            f"  CCB Gateway Monitor - {data['time_str']}",
            "=" * 60,
            "",
            "  REQUESTS",
            f"    Total: {data['requests']['total']:>6}  |  Active: {data['requests']['active']:>4}",
            f"    Queued: {data['requests']['queued']:>5}  |  Processing: {data['requests']['processing']:>3}",
            "",
            "  QUEUE",
            f"    Depth: {data['queue']['depth']}/{data['queue']['max_size']}",
        ]

        # Provider breakdown
        if data['queue']['by_provider']:
            lines.append("    By Provider:")
            for provider, count in data['queue']['by_provider'].items():
                lines.append(f"      {provider}: {count}")

        lines.extend([
            "",
            "  PROVIDERS",
        ])

        for p in data['providers']:
            status_icon = "●" if p['status'] == 'healthy' else "○"
            lines.append(
                f"    {status_icon} {p['name']:<12} "
                f"Q:{p['queue_depth']:>2}  "
                f"Lat:{p['avg_latency_ms']:>6.0f}ms  "
                f"OK:{p['success_rate']*100:>5.1f}%"
            )

        lines.extend([
            "",
            "  RECENT EVENTS",
        ])

        for event in data['recent_events'][-5:]:
            lines.append(f"    [{event['time_str']}] {event['type']}: {event['data']}")

        lines.append("")
        lines.append("=" * 60)

        return "\n".join(lines)

    async def run_terminal_monitor(self) -> None:
        """Run the terminal-based monitor display."""
        self._running = True

        try:
            while self._running:
                # Clear screen and print dashboard
                logger.info("\033[2J\033[H%s", self.format_terminal_display())

                await asyncio.sleep(self.refresh_interval)

        except KeyboardInterrupt:
            self._running = False

    def stop(self) -> None:
        """Stop the monitor service."""
        self._running = False


class WebSocketMonitor:
    """
    WebSocket-based monitor that connects to the gateway.

    Useful for remote monitoring or integration with other tools.
    """

    def __init__(self, gateway_url: str = "ws://localhost:8765/api/ws"):
        """
        Initialize the WebSocket monitor.

        Args:
            gateway_url: WebSocket URL of the gateway
        """
        self.gateway_url = gateway_url
        self._running = False
        self._events: List[Dict[str, Any]] = []

    async def connect(self) -> None:
        """Connect to the gateway WebSocket."""
        try:
            import websockets
        except ImportError:
            logger.error("websockets is required. Install with: pip install websockets")
            return

        self._running = True

        async with websockets.connect(self.gateway_url) as ws:
            # Subscribe to all events
            await ws.send('{"type": "subscribe", "channels": ["requests", "providers"]}')

            while self._running:
                try:
                    message = await asyncio.wait_for(ws.recv(), timeout=30.0)
                    import json
                    event = json.loads(message)
                    self._events.append(event)
                    self._on_event(event)
                except asyncio.TimeoutError:
                    # Send ping to keep connection alive
                    await ws.send('{"type": "ping"}')
                except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError) as e:
                    logger.error("WebSocket error: %s", e)
                    break

    def _on_event(self, event: Dict[str, Any]) -> None:
        """Handle incoming event."""
        event_type = event.get("type", "unknown")
        data = event.get("data", {})
        timestamp = datetime.fromtimestamp(event.get("timestamp", time.time()))

        logger.info("[%s] %s: %s", timestamp.strftime('%H:%M:%S'), event_type, data)

    def stop(self) -> None:
        """Stop the monitor."""
        self._running = False


async def run_monitor(
    gateway_url: str = "ws://localhost:8765/api/ws",
    mode: str = "websocket",
) -> None:
    """
    Run the monitor service.

    Args:
        gateway_url: Gateway WebSocket URL
        mode: Monitor mode ("websocket" or "terminal")
    """
    if mode == "websocket":
        monitor = WebSocketMonitor(gateway_url)
        await monitor.connect()
    else:
        # For terminal mode, we need direct access to store/queue
        # This would typically be run in the same process as the gateway
        logger.info("Terminal mode requires running in the gateway process")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="CCB Gateway Monitor")
    parser.add_argument(
        "--url",
        default="ws://localhost:8765/api/ws",
        help="Gateway WebSocket URL",
    )
    parser.add_argument(
        "--mode",
        choices=["websocket", "terminal"],
        default="websocket",
        help="Monitor mode",
    )

    args = parser.parse_args()

    asyncio.run(run_monitor(args.url, args.mode))
