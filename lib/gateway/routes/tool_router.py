"""Tool Router API routes — unified tool discovery."""
from __future__ import annotations

from typing import Optional

try:
    from fastapi import APIRouter, HTTPException, Query, Request
    from fastapi.responses import JSONResponse

    HAS_FASTAPI = True
except ImportError:  # pragma: no cover - optional FastAPI dependency
    HAS_FASTAPI = False

if HAS_FASTAPI:
    router = APIRouter()
else:  # pragma: no cover
    router = None


if HAS_FASTAPI:
    def _get_index(request: Request):
        from lib.skills.tool_index import ToolIndex

        index = getattr(request.app.state, "tool_index", None)
        if index is None:
            index = ToolIndex()
            request.app.state.tool_index = index
        return index


    @router.get("/api/tools/search")
    async def search_tools(
        request: Request,
        q: str = Query(..., min_length=1, description="Search query"),
        limit: int = Query(10, ge=1, le=50),
        installed_only: bool = Query(False),
        types: Optional[str] = Query(None, description="Comma-separated: skill,mcp-tool,mcp-server,remote-skill"),
    ):
        """Search unified tool index."""
        index = _get_index(request)
        type_list = [item.strip() for item in types.split(",") if item.strip()] if types else None
        try:
            results = index.search(q, limit=limit, installed_only=installed_only, types=type_list)
            return JSONResponse(content={"query": q, "results": results, "total": len(results)})
        except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError) as exc:
            raise HTTPException(status_code=500, detail=f"Tool search failed: {exc}")


    @router.get("/api/tools/index")
    async def get_tool_index(request: Request):
        """Get tool index stats."""
        index = _get_index(request)
        return JSONResponse(content=index.stats)


    @router.post("/api/tools/rebuild")
    async def rebuild_tool_index(request: Request):
        """Rebuild tool index from all configured sources."""
        try:
            from lib.skills.tool_index_builder import build_index
        except ImportError:
            from skills.tool_index_builder import build_index  # type: ignore

        index = _get_index(request)
        try:
            entries = build_index()
            index.set_entries(entries)
            return JSONResponse(content={"status": "rebuilt", "stats": index.stats})
        except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError) as exc:
            raise HTTPException(status_code=500, detail=f"Rebuild failed: {exc}")


    @router.get("/api/tools/{entry_id:path}")
    async def get_tool_entry(request: Request, entry_id: str):
        """Get details of a specific tool entry by id."""
        index = _get_index(request)
        entry = index.get_entry(entry_id)
        if not entry:
            raise HTTPException(status_code=404, detail="Tool not found")
        return JSONResponse(content=entry)


    @router.get("/api/tools")
    async def list_tools(
        request: Request,
        type: Optional[str] = Query(None, description="Filter by entry type"),
        installed: Optional[bool] = Query(None, description="Filter by installation status"),
    ):
        """List all tools with optional type and installed filters."""
        index = _get_index(request)
        results = index.list_entries()

        if type:
            results = [entry for entry in results if entry.get("type") == type]
        if installed is not None:
            results = [entry for entry in results if bool(entry.get("installed")) is installed]

        return JSONResponse(content={"tools": results, "total": len(results)})
