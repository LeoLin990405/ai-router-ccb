"""Web UI static-file routes for gateway API."""
from __future__ import annotations

from pathlib import Path

try:
    from fastapi import APIRouter, Depends, Request
    from fastapi.responses import FileResponse, HTMLResponse

    HAS_FASTAPI = True
except ImportError:  # pragma: no cover - optional FastAPI dependency
    HAS_FASTAPI = False

if HAS_FASTAPI:
    router = APIRouter()
else:  # pragma: no cover - API unavailable without FastAPI
    router = None


def get_web_ui_dir(request: Request):
    return getattr(request.app.state, "web_ui_dir", None)


if HAS_FASTAPI:
    @router.get("/", response_class=HTMLResponse)
    async def serve_dashboard(
        web_ui_dir: Path = Depends(get_web_ui_dir),
    ):
        """Serve the Web UI dashboard."""
        index_path = web_ui_dir / "index.html" if web_ui_dir else None
        if index_path and index_path.exists():
            return FileResponse(index_path, media_type="text/html")
        return HTMLResponse(
            content="<h1>CCB Gateway</h1><p>Web UI not found. API is running at /api/</p>",
            status_code=200,
        )


    @router.get("/web", response_class=HTMLResponse)
    async def serve_dashboard_web(
        web_ui_dir: Path = Depends(get_web_ui_dir),
    ):
        """Serve the Web UI dashboard at /web path."""
        index_path = web_ui_dir / "index.html" if web_ui_dir else None
        if index_path and index_path.exists():
            return FileResponse(index_path, media_type="text/html")
        return HTMLResponse(
            content="<h1>CCB Gateway</h1><p>Web UI not found. API is running at /api/</p>",
            status_code=200,
        )


    @router.get("/web/{file_path:path}")
    async def serve_web_files(
        file_path: str,
        web_ui_dir: Path = Depends(get_web_ui_dir),
    ):
        """Serve static files from web directory."""
        if not web_ui_dir:
            return HTMLResponse(content="Not Found", status_code=404)

        try:
            full_path = (web_ui_dir / file_path).resolve()
            web_ui_resolved = web_ui_dir.resolve()
            if not str(full_path).startswith(str(web_ui_resolved) + "/") and full_path != web_ui_resolved:
                return HTMLResponse(content="Forbidden", status_code=403)
        except (ValueError, OSError):
            return HTMLResponse(content="Invalid path", status_code=400)

        if full_path.exists() and full_path.is_file():
            suffix = full_path.suffix.lower()
            media_types = {
                ".html": "text/html",
                ".css": "text/css",
                ".js": "application/javascript",
                ".json": "application/json",
                ".png": "image/png",
                ".jpg": "image/jpeg",
                ".svg": "image/svg+xml",
            }
            media_type = media_types.get(suffix, "application/octet-stream")
            return FileResponse(full_path, media_type=media_type)
        return HTMLResponse(content="Not Found", status_code=404)
