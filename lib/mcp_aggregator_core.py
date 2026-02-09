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


class MCPAggregatorCoreMixin:
    """Mixin methods extracted from MCPAggregator."""

    def __init__(
        self,
        db_path: Optional[str] = None,
        config: Optional[Dict[str, MCPServerConfig]] = None,
    ):
        """
        Initialize the MCP aggregator.

        Args:
            db_path: Path to SQLite database for persistent state
            config: Optional custom server configurations
        """
        if db_path is None:
            db_path = str(Path.home() / ".ccb_config" / "mcp_aggregator.db")

        self.db_path = db_path
        self.servers: Dict[str, MCPServerConfig] = {}
        self._tools: Dict[str, ToolCapability] = {}
        self._server_health: Dict[str, ServerHealth] = {}
        self._processes: Dict[str, subprocess.Popen] = {}
        self._lock = threading.Lock()

        # Initialize database
        self._init_db()

        # Load servers from config
        if config:
            for name, server_config in config.items():
                self.servers[name] = server_config
        else:
            self._load_servers_from_db()

    def _init_db(self) -> None:
        """Initialize the SQLite database."""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS mcp_servers (
                    name TEXT PRIMARY KEY,
                    command TEXT NOT NULL,
                    transport TEXT NOT NULL,
                    args TEXT,
                    env TEXT,
                    enabled INTEGER DEFAULT 1,
                    timeout_s REAL DEFAULT 30.0
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS mcp_tools (
                    name TEXT PRIMARY KEY,
                    server TEXT NOT NULL,
                    description TEXT,
                    input_schema TEXT,
                    tags TEXT,
                    discovered_at REAL
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS mcp_health_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    server TEXT NOT NULL,
                    status TEXT NOT NULL,
                    latency_ms REAL,
                    error TEXT,
                    timestamp REAL
                )
            """)

            conn.commit()

    def _load_servers_from_db(self) -> None:
        """Load server configurations from database."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT name, command, transport, args, env, enabled, timeout_s FROM mcp_servers"
            )
            for row in cursor:
                name, command, transport, args_json, env_json, enabled, timeout_s = row
                self.servers[name] = MCPServerConfig(
                    name=name,
                    command=command,
                    transport=MCPTransport(transport),
                    args=json.loads(args_json) if args_json else [],
                    env=json.loads(env_json) if env_json else {},
                    enabled=bool(enabled),
                    timeout_s=timeout_s,
                )

    def register_server(self, config: MCPServerConfig) -> None:
        """
        Register an MCP server.

        Args:
            config: Server configuration
        """
        with self._lock:
            self.servers[config.name] = config

            # Save to database
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO mcp_servers
                    (name, command, transport, args, env, enabled, timeout_s)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    config.name,
                    config.command,
                    config.transport.value,
                    json.dumps(config.args),
                    json.dumps(config.env),
                    int(config.enabled),
                    config.timeout_s,
                ))
                conn.commit()

    def unregister_server(self, name: str) -> bool:
        """
        Unregister an MCP server.

        Args:
            name: Server name

        Returns:
            True if server was removed
        """
        with self._lock:
            if name not in self.servers:
                return False

            # Stop server if running
            self._stop_server(name)

            del self.servers[name]

            # Remove from database
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("DELETE FROM mcp_servers WHERE name = ?", (name,))
                conn.execute("DELETE FROM mcp_tools WHERE server = ?", (name,))
                conn.commit()

            return True

    def _start_server(self, name: str) -> bool:
        """Start an MCP server process."""
        if name not in self.servers:
            return False

        config = self.servers[name]
        if not config.enabled:
            return False

        try:
            cmd = [config.command] + config.args
            env = {**dict(subprocess.os.environ), **config.env}

            process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
            )

            self._processes[name] = process
            return True

        except HANDLED_EXCEPTIONS as e:
            self._server_health[name] = ServerHealth(
                server=name,
                status=ServerStatus.UNAVAILABLE,
                error=str(e),
                last_check=time.time(),
            )
            return False

    def _stop_server(self, name: str) -> None:
        """Stop an MCP server process."""
        if name in self._processes:
            try:
                self._processes[name].terminate()
                self._processes[name].wait(timeout=5)
            except HANDLED_EXCEPTIONS:
                self._processes[name].kill()
            finally:
                del self._processes[name]

    def discover_tools(self, server: Optional[str] = None) -> List[ToolCapability]:
        """
        Discover tools from MCP servers.

        Args:
            server: Optional specific server to query

        Returns:
            List of discovered tool capabilities
        """
        tools = []
        servers_to_query = [server] if server else list(self.servers.keys())

        for server_name in servers_to_query:
            if server_name not in self.servers:
                continue

            config = self.servers[server_name]
            if not config.enabled:
                continue

            try:
                # For stdio transport, we need to send a tools/list request
                server_tools = self._query_server_tools(server_name)
                tools.extend(server_tools)

                # Cache tools
                for tool in server_tools:
                    self._tools[tool.name] = tool

            except HANDLED_EXCEPTIONS as e:
                self._server_health[server_name] = ServerHealth(
                    server=server_name,
                    status=ServerStatus.UNAVAILABLE,
                    error=str(e),
                    last_check=time.time(),
                )

        return tools

    def _query_server_tools(self, server_name: str) -> List[ToolCapability]:
        """Query tools from a specific server."""
        config = self.servers[server_name]
        tools = []

        try:
            # Start server if not running
            if server_name not in self._processes:
                if not self._start_server(server_name):
                    return []

            process = self._processes.get(server_name)
            if not process:
                return []

            # Send tools/list request (JSON-RPC)
            request = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/list",
                "params": {},
            }

            process.stdin.write((json.dumps(request) + "\n").encode())
            process.stdin.flush()

            # Read response with timeout
            import select
            ready, _, _ = select.select([process.stdout], [], [], config.timeout_s)

            if ready:
                response_line = process.stdout.readline().decode()
                response = json.loads(response_line)

                if "result" in response and "tools" in response["result"]:
                    for tool_data in response["result"]["tools"]:
                        tool = ToolCapability(
                            name=tool_data.get("name", ""),
                            server=server_name,
                            description=tool_data.get("description", ""),
                            input_schema=tool_data.get("inputSchema", {}),
                        )
                        tools.append(tool)

                        # Save to database
                        self._save_tool(tool)

        except HANDLED_EXCEPTIONS as e:
            self._server_health[server_name] = ServerHealth(
                server=server_name,
                status=ServerStatus.DEGRADED,
                error=str(e),
                last_check=time.time(),
            )

        return tools

    def _save_tool(self, tool: ToolCapability) -> None:
        """Save a tool to the database."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO mcp_tools
                (name, server, description, input_schema, tags, discovered_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                tool.name,
                tool.server,
                tool.description,
                json.dumps(tool.input_schema),
                json.dumps(tool.tags),
                time.time(),
            ))
            conn.commit()

