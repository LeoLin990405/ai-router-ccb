"""Auto-split mixins for MCPAggregator."""
from __future__ import annotations

import asyncio
import json
import sqlite3
import subprocess
import threading
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

try:
    from .mcp_aggregator import (
        HANDLED_EXCEPTIONS,
        MCPServerConfig,
        MCPTransport,
        ServerHealth,
        ServerStatus,
        ToolCallResult,
        ToolCapability,
    )
except ImportError:  # pragma: no cover - script mode
    from mcp_aggregator import (
        HANDLED_EXCEPTIONS,
        MCPServerConfig,
        MCPTransport,
        ServerHealth,
        ServerStatus,
        ToolCallResult,
        ToolCapability,
    )


class MCPAggregatorRoutingMixin:
    """Mixin methods extracted from MCPAggregator."""

    def route_tool_call(
        self,
        tool_name: str,
        args: Dict[str, Any],
        timeout_s: Optional[float] = None,
    ) -> ToolCallResult:
        """
        Route a tool call to the appropriate server.

        Args:
            tool_name: Name of the tool to call
            args: Arguments for the tool
            timeout_s: Optional timeout override

        Returns:
            ToolCallResult with the response
        """
        start_time = time.time()

        # Find the server for this tool
        tool = self._tools.get(tool_name)
        if not tool:
            # Try to find in database
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    "SELECT server FROM mcp_tools WHERE name = ?",
                    (tool_name,)
                )
                row = cursor.fetchone()
                if row:
                    tool = ToolCapability(name=tool_name, server=row[0])
                    self._tools[tool_name] = tool

        if not tool:
            return ToolCallResult(
                success=False,
                server="unknown",
                tool=tool_name,
                error=f"Tool '{tool_name}' not found",
                latency_ms=(time.time() - start_time) * 1000,
            )

        server_name = tool.server
        config = self.servers.get(server_name)

        if not config or not config.enabled:
            return ToolCallResult(
                success=False,
                server=server_name,
                tool=tool_name,
                error=f"Server '{server_name}' not available",
                latency_ms=(time.time() - start_time) * 1000,
            )

        try:
            # Ensure server is running
            if server_name not in self._processes:
                if not self._start_server(server_name):
                    return ToolCallResult(
                        success=False,
                        server=server_name,
                        tool=tool_name,
                        error="Failed to start server",
                        latency_ms=(time.time() - start_time) * 1000,
                    )

            process = self._processes[server_name]

            # Send tools/call request
            request = {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": tool_name,
                    "arguments": args,
                },
            }

            process.stdin.write((json.dumps(request) + "\n").encode())
            process.stdin.flush()

            # Read response
            effective_timeout = timeout_s or config.timeout_s
            import select
            ready, _, _ = select.select([process.stdout], [], [], effective_timeout)

            if ready:
                response_line = process.stdout.readline().decode()
                response = json.loads(response_line)

                latency_ms = (time.time() - start_time) * 1000

                if "result" in response:
                    return ToolCallResult(
                        success=True,
                        server=server_name,
                        tool=tool_name,
                        result=response["result"],
                        latency_ms=latency_ms,
                    )
                elif "error" in response:
                    return ToolCallResult(
                        success=False,
                        server=server_name,
                        tool=tool_name,
                        error=response["error"].get("message", "Unknown error"),
                        latency_ms=latency_ms,
                    )

            return ToolCallResult(
                success=False,
                server=server_name,
                tool=tool_name,
                error="Timeout waiting for response",
                latency_ms=(time.time() - start_time) * 1000,
            )

        except HANDLED_EXCEPTIONS as e:
            return ToolCallResult(
                success=False,
                server=server_name,
                tool=tool_name,
                error=str(e),
                latency_ms=(time.time() - start_time) * 1000,
            )

    def get_server_health(self, server: Optional[str] = None) -> Dict[str, ServerHealth]:
        """
        Get health status of MCP servers.

        Args:
            server: Optional specific server to check

        Returns:
            Dict of server name to health status
        """
        servers_to_check = [server] if server else list(self.servers.keys())
        results = {}

        for server_name in servers_to_check:
            if server_name not in self.servers:
                continue

            config = self.servers[server_name]
            start_time = time.time()

            try:
                # Check if process is running
                if server_name in self._processes:
                    process = self._processes[server_name]
                    if process.poll() is None:
                        # Process is running, try a ping
                        latency_ms = (time.time() - start_time) * 1000
                        results[server_name] = ServerHealth(
                            server=server_name,
                            status=ServerStatus.HEALTHY,
                            latency_ms=latency_ms,
                            last_check=time.time(),
                            tool_count=len([t for t in self._tools.values() if t.server == server_name]),
                        )
                    else:
                        results[server_name] = ServerHealth(
                            server=server_name,
                            status=ServerStatus.UNAVAILABLE,
                            error="Process terminated",
                            last_check=time.time(),
                        )
                        del self._processes[server_name]
                else:
                    # Try to start server
                    if self._start_server(server_name):
                        latency_ms = (time.time() - start_time) * 1000
                        results[server_name] = ServerHealth(
                            server=server_name,
                            status=ServerStatus.HEALTHY,
                            latency_ms=latency_ms,
                            last_check=time.time(),
                        )
                    else:
                        results[server_name] = ServerHealth(
                            server=server_name,
                            status=ServerStatus.UNAVAILABLE,
                            error="Failed to start",
                            last_check=time.time(),
                        )

            except HANDLED_EXCEPTIONS as e:
                results[server_name] = ServerHealth(
                    server=server_name,
                    status=ServerStatus.UNAVAILABLE,
                    error=str(e),
                    last_check=time.time(),
                )

            # Log health check
            self._log_health(results[server_name])

        return results

    def _log_health(self, health: ServerHealth) -> None:
        """Log a health check result."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO mcp_health_log (server, status, latency_ms, error, timestamp)
                VALUES (?, ?, ?, ?, ?)
            """, (
                health.server,
                health.status.value,
                health.latency_ms,
                health.error,
                health.last_check,
            ))
            conn.commit()

    def list_tools(self) -> List[ToolCapability]:
        """List all discovered tools."""
        # Load from database if cache is empty
        if not self._tools:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    "SELECT name, server, description, input_schema, tags FROM mcp_tools"
                )
                for row in cursor:
                    name, server, description, input_schema_json, tags_json = row
                    self._tools[name] = ToolCapability(
                        name=name,
                        server=server,
                        description=description,
                        input_schema=json.loads(input_schema_json) if input_schema_json else {},
                        tags=json.loads(tags_json) if tags_json else [],
                    )

        return list(self._tools.values())

    def list_servers(self) -> List[MCPServerConfig]:
        """List all registered servers."""
        return list(self.servers.values())

    def shutdown(self) -> None:
        """Shutdown all MCP server processes."""
        for server_name in list(self._processes.keys()):
            self._stop_server(server_name)


# Singleton instance
_mcp_aggregator: Optional[MCPAggregator] = None


