"""
CCB Gateway Memory Middleware
在 Gateway 层自动处理记忆的记录和注入

v2.0 Enhancement: Heuristic Retrieval with αR + βI + γT scoring
"""

import asyncio
import json
from datetime import datetime
from typing import Dict, Any, Optional, List
from pathlib import Path
import sys

from lib.common.logging import get_logger

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from lib.memory.memory_v2 import CCBLightMemory
from lib.memory.registry import CCBRegistry
from lib.skills.skills_discovery import SkillsDiscoveryService
from .system_context import SystemContextBuilder

# v2.0: Heuristic Retriever
try:
    from lib.memory.heuristic_retriever import HeuristicRetriever, ScoredMemory
    HAS_HEURISTIC = True
except ImportError:
    HAS_HEURISTIC = False


logger = get_logger("gateway.middleware.memory")


if not HAS_HEURISTIC:
    logger.warning("HeuristicRetriever not available, using basic search")



from .memory_middleware_core import MemoryMiddlewareCoreMixin
from .memory_middleware_post import MemoryMiddlewarePostMixin


class MemoryMiddleware(MemoryMiddlewareCoreMixin, MemoryMiddlewarePostMixin):
    """Gateway 记忆中间件 (v2.0: Heuristic Retrieval)"""


