"""Discussion and discussion-memory routes for gateway API."""
from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional

try:
    from fastapi import APIRouter, Depends, HTTPException, Query, Request
    from fastapi.responses import Response

    HAS_FASTAPI = True
except ImportError:  # pragma: no cover - optional FastAPI dependency
    HAS_FASTAPI = False

from ..discussion import DiscussionExporter, ObsidianExporter
from ..error_handlers import raise_discussion_not_found
from ..models import (
    ContinueDiscussionRequest,
    CreateTemplateRequest,
    DiscussionConfig,
    DiscussionResponse,
    DiscussionStatus,
    ExportObsidianRequest,
    StartDiscussionRequest,
    UseTemplateRequest,
)
from .discussion_memory import register_discussion_memory_routes

if HAS_FASTAPI:
    router = APIRouter()
else:  # pragma: no cover - API unavailable without FastAPI
    router = None


def get_config(request: Request):
    return request.app.state.config


def get_store(request: Request):
    return request.app.state.store


def get_discussion_executor(request: Request):
    return getattr(request.app.state, "discussion_executor", None)


def get_memory_middleware(request: Request):
    return getattr(request.app.state, "memory_middleware", None)


if HAS_FASTAPI:
    @router.post("/api/discussion/{session_id}/export-obsidian")
    async def export_to_obsidian(
        session_id: str,
        request: ExportObsidianRequest,
        store=Depends(get_store),
    ) -> Dict[str, Any]:
        """
        Export a discussion to an Obsidian vault.

        Creates a markdown file with YAML frontmatter, tags, and callouts
        compatible with Obsidian's features.
        """
        exporter = ObsidianExporter(store)

        try:
            file_path = exporter.export_to_vault(
                session_id=session_id,
                vault_path=request.vault_path,
                folder=request.folder,
            )
            return {
                "success": True,
                "file_path": file_path,
                "session_id": session_id,
            }
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))
        except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError) as e:
            raise HTTPException(status_code=500, detail=f"Export failed: {e}")


    @router.post("/api/discussion/start", response_model=DiscussionResponse)
    async def start_discussion(
        request: StartDiscussionRequest,
        discussion_executor=Depends(get_discussion_executor),
    ) -> DiscussionResponse:
        """
        Start a new multi-AI discussion session.

        Supports:
        - Explicit provider list: providers=["kimi", "qwen", "iflow"]
        - Provider groups: provider_group="@all", "@fast", "@coding"
        """
        if not discussion_executor:
            raise HTTPException(
                status_code=400,
                detail="Discussion feature not enabled",
            )

        providers = request.providers
        if not providers and request.provider_group:
            providers = discussion_executor.resolve_provider_group(request.provider_group)

        if not providers:
            providers = list(discussion_executor.backends.keys())

        if len(providers) < 2:
            raise HTTPException(
                status_code=400,
                detail=f"Need at least 2 providers for discussion, got {len(providers)}",
            )

        disc_config = DiscussionConfig(
            max_rounds=min(request.max_rounds, 3),
            round_timeout_s=request.round_timeout_s,
            provider_timeout_s=request.provider_timeout_s,
        )

        try:
            session = await discussion_executor.start_discussion(
                topic=request.topic,
                providers=providers,
                config=disc_config,
            )

            if request.run_async:
                asyncio.create_task(discussion_executor.run_full_discussion(session.id))

            return DiscussionResponse(
                session_id=session.id,
                topic=session.topic,
                status=session.status.value,
                current_round=session.current_round,
                providers=session.providers,
                created_at=session.created_at,
                summary=session.summary,
            )

        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError) as e:
            raise HTTPException(status_code=500, detail=f"Failed to start discussion: {e}")


    @router.get("/api/discussion/{session_id}", response_model=DiscussionResponse)
    async def get_discussion(
        session_id: str,
        store=Depends(get_store),
    ) -> DiscussionResponse:
        """Get discussion session status and details."""
        session = store.get_discussion_session(session_id)
        if not session:
            raise_discussion_not_found()

        return DiscussionResponse(
            session_id=session.id,
            topic=session.topic,
            status=session.status.value,
            current_round=session.current_round,
            providers=session.providers,
            created_at=session.created_at,
            summary=session.summary,
        )


    @router.get("/api/discussion/{session_id}/messages")
    async def get_discussion_messages(
        session_id: str,
        round_number: Optional[int] = Query(None, description="Filter by round number"),
        provider: Optional[str] = Query(None, description="Filter by provider"),
        store=Depends(get_store),
    ) -> List[Dict[str, Any]]:
        """Get messages from a discussion session."""
        session = store.get_discussion_session(session_id)
        if not session:
            raise_discussion_not_found()

        message_type = None
        messages = store.get_discussion_messages(
            session_id=session_id,
            round_number=round_number,
            provider=provider,
            message_type=message_type,
        )

        return [m.to_dict() for m in messages]


    @router.delete("/api/discussion/{session_id}")
    async def cancel_discussion(
        session_id: str,
        discussion_executor=Depends(get_discussion_executor),
    ) -> Dict[str, Any]:
        """Cancel an ongoing discussion."""
        if not discussion_executor:
            raise HTTPException(
                status_code=400,
                detail="Discussion feature not enabled",
            )

        success = await discussion_executor.cancel_discussion(session_id)
        if not success:
            raise HTTPException(
                status_code=404,
                detail="Discussion not found or already completed",
            )

        return {"cancelled": True, "session_id": session_id}


    @router.get("/api/discussions")
    async def list_discussions(
        status: Optional[str] = Query(None, description="Filter by status"),
        limit: int = Query(50, le=100),
        offset: int = Query(0, ge=0),
        store=Depends(get_store),
    ) -> List[Dict[str, Any]]:
        """List discussion sessions."""
        status_enum = DiscussionStatus(status) if status else None
        sessions = store.list_discussion_sessions(
            status=status_enum,
            limit=limit,
            offset=offset,
        )
        return [s.to_dict() for s in sessions]


    @router.get("/api/discussion-groups")
    async def get_discussion_groups(
        config=Depends(get_config),
        discussion_executor=Depends(get_discussion_executor),
    ) -> Dict[str, List[str]]:
        """Get available provider groups for discussions."""
        if not discussion_executor:
            return {"all": list(config.providers.keys())}
        return discussion_executor.get_provider_groups()


    @router.get("/api/discussion/{session_id}/export")
    async def export_discussion(
        session_id: str,
        format: str = Query("md", description="Export format: md, json, or html"),
        include_metadata: bool = Query(True, description="Include metadata in export"),
        store=Depends(get_store),
    ):
        """
        Export a discussion to Markdown, JSON, or HTML format.

        Formats:
        - md: Markdown with YAML frontmatter
        - json: Full JSON export with all data
        - html: Styled HTML document
        """
        exporter = DiscussionExporter(store)

        try:
            content = exporter.export(session_id, format=format, include_metadata=include_metadata)
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))

        content_types = {
            "md": "text/markdown",
            "json": "application/json",
            "html": "text/html",
            "html": "text/html",
        }
        content_type = content_types.get(format, "text/plain")

        session = store.get_discussion_session(session_id)
        topic_slug = session.topic[:30].replace(" ", "_").replace("/", "-") if session else session_id
        filename = f"discussion_{topic_slug}.{format}"

        return Response(
            content=content,
            media_type=content_type,
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
            },
        )


    @router.post("/api/discussion/templates")
    async def create_template(
        request: CreateTemplateRequest,
        store=Depends(get_store),
    ) -> Dict[str, Any]:
        """Create a new discussion template."""
        try:
            template = store.create_discussion_template(
                name=request.name,
                topic_template=request.topic_template,
                description=request.description,
                default_providers=request.default_providers,
                default_config=request.default_config,
                category=request.category,
            )
            return template
        except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError) as e:
            raise HTTPException(status_code=400, detail=str(e))


    @router.get("/api/discussion/templates")
    async def list_templates(
        category: Optional[str] = Query(None, description="Filter by category"),
        include_builtin: bool = Query(True, description="Include built-in templates"),
        store=Depends(get_store),
    ) -> List[Dict[str, Any]]:
        """List all discussion templates."""
        return store.list_discussion_templates(
            category=category,
            include_builtin=include_builtin,
        )


    @router.get("/api/discussion/templates/{template_id}")
    async def get_template(
        template_id: str,
        store=Depends(get_store),
    ) -> Dict[str, Any]:
        """Get a specific discussion template."""
        template = store.get_discussion_template(template_id)
        if not template:
            raise HTTPException(status_code=404, detail="Template not found")
        return template


    @router.put("/api/discussion/templates/{template_id}")
    async def update_template(
        template_id: str,
        request: CreateTemplateRequest,
        store=Depends(get_store),
    ) -> Dict[str, Any]:
        """Update a discussion template (non-builtin only)."""
        success = store.update_discussion_template(
            template_id=template_id,
            name=request.name,
            topic_template=request.topic_template,
            description=request.description,
            default_providers=request.default_providers,
            default_config=request.default_config,
            category=request.category,
        )
        if not success:
            raise HTTPException(
                status_code=404,
                detail="Template not found or is a built-in template",
            )
        return store.get_discussion_template(template_id)


    @router.delete("/api/discussion/templates/{template_id}")
    async def delete_template(
        template_id: str,
        store=Depends(get_store),
    ) -> Dict[str, Any]:
        """Delete a discussion template (non-builtin only)."""
        success = store.delete_discussion_template(template_id)
        if not success:
            raise HTTPException(
                status_code=404,
                detail="Template not found or is a built-in template",
            )
        return {"deleted": True, "template_id": template_id}


    @router.post("/api/discussion/templates/{template_id}/use")
    async def use_template(
        template_id: str,
        request: UseTemplateRequest,
        store=Depends(get_store),
        discussion_executor=Depends(get_discussion_executor),
    ) -> DiscussionResponse:
        """
        Use a template to start a new discussion.

        Variables in the template (like {subject}, {context}) will be replaced
        with values from the request.
        """
        if not discussion_executor:
            raise HTTPException(
                status_code=400,
                detail="Discussion feature not enabled",
            )

        template = store.get_discussion_template(template_id)
        if not template:
            raise HTTPException(status_code=404, detail="Template not found")

        topic = template["topic_template"]
        for key, value in request.variables.items():
            topic = topic.replace(f"{{{key}}}", value)

        providers = request.providers or template.get("default_providers")
        if not providers:
            providers = list(discussion_executor.backends.keys())

        default_config = template.get("default_config") or {}
        override_config = request.config or {}
        merged_config = {**default_config, **override_config}

        disc_config = DiscussionConfig(
            max_rounds=merged_config.get("max_rounds", 3),
            round_timeout_s=merged_config.get("round_timeout_s", 120.0),
            provider_timeout_s=merged_config.get("provider_timeout_s", 120.0),
        )

        try:
            store.increment_template_usage(template_id)

            session = await discussion_executor.start_discussion(
                topic=topic,
                providers=providers,
                config=disc_config,
            )

            store.update_discussion_session(
                session.id,
                metadata={"template_id": template_id, "template_name": template["name"]},
            )

            if request.run_async:
                asyncio.create_task(discussion_executor.run_full_discussion(session.id))

            return DiscussionResponse(
                session_id=session.id,
                topic=session.topic,
                status=session.status.value,
                current_round=session.current_round,
                providers=session.providers,
                created_at=session.created_at,
                summary=session.summary,
            )

        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))


    @router.post("/api/discussion/{session_id}/continue")
    async def continue_discussion_endpoint(
        session_id: str,
        request: ContinueDiscussionRequest,
        discussion_executor=Depends(get_discussion_executor),
    ) -> DiscussionResponse:
        """
        Continue a completed discussion with a follow-up topic.

        Creates a new discussion session linked to the parent,
        with context from the previous discussion.
        """
        if not discussion_executor:
            raise HTTPException(
                status_code=400,
                detail="Discussion feature not enabled",
            )

        try:
            session = await discussion_executor.continue_discussion(
                session_id=session_id,
                follow_up_topic=request.follow_up_topic,
                additional_context=request.additional_context,
                max_rounds=request.max_rounds,
            )

            asyncio.create_task(discussion_executor.run_full_discussion(session.id))

            return DiscussionResponse(
                session_id=session.id,
                topic=request.follow_up_topic,
                status=session.status.value,
                current_round=session.current_round,
                providers=session.providers,
                created_at=session.created_at,
                summary=None,
            )

        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))


_discussion_memory_funcs = register_discussion_memory_routes(
    router=router,
    get_store=get_store,
    get_memory_middleware=get_memory_middleware,
)
globals().update(_discussion_memory_funcs)
