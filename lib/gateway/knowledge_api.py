"""Knowledge Hub Gateway API endpoints."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

try:
    from fastapi import APIRouter, Query
    from pydantic import BaseModel, Field

    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False

try:
    from lib.knowledge import KnowledgeRouter

    KNOWLEDGE_AVAILABLE = True
    KNOWLEDGE_IMPORT_ERROR: Optional[str] = None
except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError) as exc:  # pragma: no cover - depends on runtime environment
    KNOWLEDGE_AVAILABLE = False
    KNOWLEDGE_IMPORT_ERROR = str(exc)
    KnowledgeRouter = None  # type: ignore[assignment]


if HAS_FASTAPI:
    router = APIRouter(prefix="/knowledge", tags=["knowledge"])
else:  # pragma: no cover - API unavailable without FastAPI
    router = None


_knowledge_router: Optional[KnowledgeRouter] = None


def get_knowledge_router() -> KnowledgeRouter:
    """Get a singleton KnowledgeRouter instance."""
    if not KNOWLEDGE_AVAILABLE:
        raise RuntimeError(f"Knowledge module unavailable: {KNOWLEDGE_IMPORT_ERROR}")

    global _knowledge_router
    if _knowledge_router is None:
        _knowledge_router = KnowledgeRouter()
    return _knowledge_router


if HAS_FASTAPI:
    # === Request/Response Models ===

    class QueryRequest(BaseModel):
        question: str
        source: str = "auto"
        notebook_id: Optional[str] = None
        use_cache: bool = True

    class QueryResponse(BaseModel):
        answer: Optional[str] = None
        source: str
        references: List[Dict[str, Any]] = Field(default_factory=list)
        cached: bool = False
        confidence: float = 0.0
        error: Optional[str] = None

    class SyncResponse(BaseModel):
        notebooks_synced: int
        success: bool
        message: str

    class StatsResponse(BaseModel):
        index: Dict[str, Any]
        notebooklm_available: bool
        obsidian_available: bool

    class CreateRequest(BaseModel):
        title: str

    class CreateResponse(BaseModel):
        notebook_id: Optional[str] = None
        title: str
        success: bool
        error: Optional[str] = None

    class AddSourceRequest(BaseModel):
        notebook_id: str
        file_or_url: str

    class AddSourceResponse(BaseModel):
        source_id: Optional[str] = None
        title: Optional[str] = None
        status: Optional[str] = None
        success: bool
        error: Optional[str] = None

    class AuthResponse(BaseModel):
        authenticated: bool

    # === Endpoints ===

    @router.post("/query", response_model=QueryResponse)
    async def query_knowledge(request: QueryRequest):
        """Query the unified knowledge hub."""
        try:
            kr = get_knowledge_router()
            result = kr.query(
                question=request.question,
                source=request.source,
                notebook_id=request.notebook_id,
                use_cache=request.use_cache,
            )
            return QueryResponse(**result)
        except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError) as exc:
            return QueryResponse(
                answer=None,
                source=request.source,
                references=[],
                cached=False,
                confidence=0.0,
                error=str(exc),
            )

    @router.post("/sync", response_model=SyncResponse)
    async def sync_knowledge():
        """Sync NotebookLM notebooks to local index."""
        try:
            kr = get_knowledge_router()
            synced_count = kr.sync_notebooklm()
            return SyncResponse(
                notebooks_synced=synced_count,
                success=True,
                message=f"Synced {synced_count} notebooks",
            )
        except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError) as exc:
            return SyncResponse(
                notebooks_synced=0,
                success=False,
                message=str(exc),
            )

    @router.get("/stats", response_model=StatsResponse)
    async def get_knowledge_stats():
        """Get knowledge hub stats."""
        kr = get_knowledge_router()
        return StatsResponse(**kr.get_stats())

    @router.get("/notebooks")
    async def list_notebooks(topic: Optional[str] = None):
        """List indexed notebooks, optionally filtered by topic."""
        kr = get_knowledge_router()
        if topic:
            return kr.index.search_notebooks(topic)
        return kr.index.list_notebooks()

    @router.post("/create", response_model=CreateResponse)
    async def create_notebook(request: CreateRequest):
        """Create a new NotebookLM notebook."""
        try:
            kr = get_knowledge_router()
            result = kr.create_notebook(request.title)
            return CreateResponse(
                notebook_id=result.get("id"),
                title=result.get("title", request.title),
                success=bool(result.get("id")),
                error=result.get("error"),
            )
        except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError) as exc:
            return CreateResponse(
                title=request.title,
                success=False,
                error=str(exc),
            )

    @router.post("/add-source", response_model=AddSourceResponse)
    async def add_source(request: AddSourceRequest):
        """Add a source (file or URL) to a notebook."""
        try:
            kr = get_knowledge_router()
            result = kr.add_source(request.notebook_id, request.file_or_url)
            return AddSourceResponse(
                source_id=result.get("id") or result.get("source_id"),
                title=result.get("title"),
                status=result.get("status", "processing"),
                success=not result.get("error"),
                error=result.get("error"),
            )
        except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError) as exc:
            return AddSourceResponse(
                success=False,
                error=str(exc),
            )

    @router.get("/auth", response_model=AuthResponse)
    async def check_auth():
        """Check NotebookLM authentication status."""
        try:
            kr = get_knowledge_router()
            return AuthResponse(authenticated=kr.check_auth())
        except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError):
            return AuthResponse(authenticated=False)

    @router.get("/search")
    async def search_notebooks(q: str = Query(..., description="Search query")):
        """Search notebooks by keyword."""
        try:
            kr = get_knowledge_router()
            return kr.search_notebooks_online(q)
        except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError) as exc:
            return {"error": str(exc), "results": []}


def get_knowledge_api_router() -> Optional[APIRouter]:
    """Return the APIRouter instance when available."""
    if not HAS_FASTAPI:
        return None
    return router
