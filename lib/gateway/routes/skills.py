"""Skills discovery and feedback routes for gateway API."""
from __future__ import annotations

from typing import Optional

try:
    from fastapi import APIRouter, Depends, HTTPException, Query, Request
    from fastapi.responses import JSONResponse

    HAS_FASTAPI = True
except ImportError:  # pragma: no cover - optional FastAPI dependency
    HAS_FASTAPI = False

from ..error_handlers import raise_skills_unavailable
from ..models import SkillFeedbackRequest

if HAS_FASTAPI:
    router = APIRouter()
else:  # pragma: no cover - API unavailable without FastAPI
    router = None


def get_memory_middleware(request: Request):
    return getattr(request.app.state, "memory_middleware", None)


if HAS_FASTAPI:
    @router.get("/api/skills/recommendations")
    async def get_skill_recommendations(
        query: str = Query(..., min_length=1),
        memory_middleware=Depends(get_memory_middleware),
    ):
        """Get skill recommendations for a task."""
        if not memory_middleware or not hasattr(memory_middleware, "skills_discovery"):
            raise_skills_unavailable()

        try:
            recommendations = memory_middleware.skills_discovery.get_recommendations(query)
            return JSONResponse(content=recommendations)
        except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError) as e:
            raise HTTPException(status_code=500, detail=f"Skills discovery failed: {str(e)}")


    @router.get("/api/skills/stats")
    async def get_skills_stats(
        memory_middleware=Depends(get_memory_middleware),
    ):
        """Get skills usage statistics."""
        if not memory_middleware or not hasattr(memory_middleware, "skills_discovery"):
            raise_skills_unavailable()

        try:
            stats = memory_middleware.skills_discovery.get_usage_stats()
            return JSONResponse(content=stats)
        except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError) as e:
            raise HTTPException(status_code=500, detail=f"Failed to fetch skills stats: {str(e)}")


    @router.get("/api/skills/list")
    async def list_skills(
        installed_only: bool = Query(False),
        memory_middleware=Depends(get_memory_middleware),
    ):
        """List all available skills."""
        if not memory_middleware or not hasattr(memory_middleware, "skills_discovery"):
            raise_skills_unavailable()

        try:
            skills = memory_middleware.skills_discovery.list_all_skills()
            if installed_only:
                skills = [skill for skill in skills if skill.get("installed", False)]
            return JSONResponse(content={"skills": skills})
        except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError) as e:
            raise HTTPException(status_code=500, detail=f"Failed to list skills: {str(e)}")


    @router.post("/api/skills/{skill_name}/feedback")
    async def submit_skill_feedback(
        skill_name: str,
        request: SkillFeedbackRequest,
        memory_middleware=Depends(get_memory_middleware),
    ):
        """Submit feedback for a skill (Phase 5: Feedback Loop)."""
        if not memory_middleware or not hasattr(memory_middleware, "skills_discovery"):
            raise_skills_unavailable()

        try:
            task_keywords: Optional[str] = None
            if request.task_description:
                words = request.task_description.lower().split()
                task_keywords = " ".join([word for word in words if len(word) > 2][:10])

            success = memory_middleware.skills_discovery.record_feedback(
                skill_name=skill_name,
                rating=request.rating,
                task_keywords=task_keywords,
                task_description=request.task_description,
                helpful=request.helpful,
                comment=request.comment,
            )

            if not success:
                raise HTTPException(status_code=400, detail="Invalid feedback data")

            return JSONResponse(
                content={
                    "skill_name": skill_name,
                    "message": "Feedback recorded successfully",
                }
            )
        except HTTPException:
            raise
        except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError) as e:
            raise HTTPException(status_code=500, detail=f"Failed to record feedback: {str(e)}")


    @router.get("/api/skills/{skill_name}/feedback")
    async def get_skill_feedback(
        skill_name: str,
        memory_middleware=Depends(get_memory_middleware),
    ):
        """Get feedback statistics for a skill (Phase 5)."""
        if not memory_middleware or not hasattr(memory_middleware, "skills_discovery"):
            raise_skills_unavailable()

        try:
            stats = memory_middleware.skills_discovery.get_skill_feedback_stats(skill_name)
            return JSONResponse(content=stats)
        except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError) as e:
            raise HTTPException(status_code=500, detail=f"Failed to get feedback: {str(e)}")


    @router.get("/api/skills/feedback/all")
    async def get_all_skill_feedback(
        memory_middleware=Depends(get_memory_middleware),
    ):
        """Get feedback statistics for all skills (Phase 5)."""
        if not memory_middleware or not hasattr(memory_middleware, "skills_discovery"):
            raise_skills_unavailable()

        try:
            stats = memory_middleware.skills_discovery.get_all_feedback_stats()
            return JSONResponse(content={"skills_feedback": stats})
        except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError) as e:
            raise HTTPException(status_code=500, detail=f"Failed to get feedback: {str(e)}")
