"""
MCP Server Aggregation System for CCB

Aggregates multiple MCP servers into a unified interface with:
- Server registration and discovery
- Tool routing based on capabilities
- Health monitoring and failover
"""
from __future__ import annotations

import asyncio
import json
import subprocess
import time
import threading
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional, Dict, List, Any, Callable
import sqlite3


HANDLED_EXCEPTIONS = (Exception,)


class MCPTransport(Enum):
    """MCP transport types."""
    STDIO = "stdio"
    SSE = "sse"
    HTTP = "http"


class ServerStatus(Enum):
    """MCP server health status."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"
    UNKNOWN = "unknown"


@dataclass
class MCPServerConfig:
    """Configuration for an MCP server."""
    name: str
    command: str
    transport: MCPTransport = MCPTransport.STDIO
    args: List[str] = field(default_factory=list)
    env: Dict[str, str] = field(default_factory=dict)
    enabled: bool = True
    timeout_s: float = 30.0


@dataclass
class ToolCapability:
    """A tool capability from an MCP server."""
    name: str
    server: str
    description: str = ""
    input_schema: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)


@dataclass
class ServerHealth:
    """Health status of an MCP server."""
    server: str
    status: ServerStatus
    latency_ms: float = 0.0
    last_check: float = 0.0
    error: Optional[str] = None
    tool_count: int = 0


@dataclass
class ToolCallResult:
    """Result of a tool call."""
    success: bool
    server: str
    tool: str
    result: Any = None
    error: Optional[str] = None
    latency_ms: float = 0.0



try:
    from .mcp_aggregator_core import MCPAggregatorCoreMixin
    from .mcp_aggregator_routing import MCPAggregatorRoutingMixin
except ImportError:  # pragma: no cover - script mode
    from mcp_aggregator_core import MCPAggregatorCoreMixin
    from mcp_aggregator_routing import MCPAggregatorRoutingMixin


class MCPAggregator(MCPAggregatorCoreMixin, MCPAggregatorRoutingMixin):
    """Aggregates multiple MCP servers into a unified interface."""

    DEFAULT_SERVERS: Dict[str, MCPServerConfig] = {
        "github": MCPServerConfig(
            name="github",
            command="npx",
            args=["-y", "@modelcontextprotocol/server-github"],
            transport=MCPTransport.STDIO,
        ),
        "filesystem": MCPServerConfig(
            name="filesystem",
            command="npx",
            args=["-y", "@modelcontextprotocol/server-filesystem", "."],
            transport=MCPTransport.STDIO,
        ),
        "memory": MCPServerConfig(
            name="memory",
            command="npx",
            args=["-y", "@modelcontextprotocol/server-memory"],
            transport=MCPTransport.STDIO,
        ),
    }


def get_mcp_aggregator() -> MCPAggregator:
    """Get the global MCP aggregator instance."""
    global _mcp_aggregator
    if _mcp_aggregator is None:
        _mcp_aggregator = MCPAggregator()
    return _mcp_aggregator
