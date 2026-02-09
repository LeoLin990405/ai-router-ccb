"""Knowledge Hub package."""

from .index_manager import IndexManager
from .notebooklm_client import NotebookLMClient
from .obsidian_search import ObsidianSearch
from .router import KnowledgeRouter
from .shared_knowledge import SharedKnowledgeService

__all__ = [
    "KnowledgeRouter",
    "NotebookLMClient",
    "ObsidianSearch",
    "IndexManager",
    "SharedKnowledgeService",
]

__version__ = "0.1.0"
