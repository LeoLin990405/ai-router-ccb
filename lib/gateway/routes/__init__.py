"""Route modules for gateway API."""

from . import admin
from . import batch
from . import cc_switch
from . import core
from . import discussion
from . import discussion_memory
from . import export
from . import health
from . import health_ops
from . import memory
from . import memory_advanced
from . import runtime
from . import runtime_management
from . import shared_knowledge
from . import skills
from . import tool_router
from . import web
from . import websocket
from .websocket import WebSocketManager

__all__ = [
    "admin",
    "batch",
    "cc_switch",
    "core",
    "discussion",
    "discussion_memory",
    "export",
    "health",
    "health_ops",
    "memory",
    "memory_advanced",
    "runtime",
    "runtime_management",
    "shared_knowledge",
    "skills",
    "tool_router",
    "web",
    "websocket",
    "WebSocketManager",
]
