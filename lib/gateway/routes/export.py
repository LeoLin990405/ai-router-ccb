"""Data export routes for gateway API."""
from __future__ import annotations

import time
from typing import Optional

try:
    from fastapi import APIRouter, Depends, Query, Request
    from fastapi.responses import JSONResponse, Response

    HAS_FASTAPI = True
except ImportError:  # pragma: no cover - optional FastAPI dependency
    HAS_FASTAPI = False

from ..models import DiscussionStatus, RequestStatus

if HAS_FASTAPI:
    router = APIRouter()
else:  # pragma: no cover - API unavailable without FastAPI
    router = None


def get_store(request: Request):
    return request.app.state.store


if HAS_FASTAPI:
    @router.get("/api/export/requests")
    async def export_requests(
        format: str = Query("json", description="Export format: json or csv"),
        status: Optional[str] = Query(None, description="Filter by status"),
        provider: Optional[str] = Query(None, description="Filter by provider"),
        days: int = Query(7, ge=1, le=90, description="Number of days to export"),
        store=Depends(get_store),
    ):
        """
        Export requests to JSON or CSV format.

        Useful for analytics, backup, and external processing.
        """
        import csv
        from datetime import datetime
        from io import StringIO

        since = time.time() - (days * 86400)

        status_enum = RequestStatus(status) if status else None
        all_requests = store.list_requests(
            status=status_enum,
            provider=provider,
            limit=10000,
            order_by="created_at",
            order_desc=True,
        )

        requests = [request for request in all_requests if request.created_at >= since]

        if format == "csv":
            output = StringIO()
            writer = csv.writer(output)

            writer.writerow(
                [
                    "id",
                    "provider",
                    "status",
                    "created_at",
                    "updated_at",
                    "priority",
                    "timeout_s",
                    "started_at",
                    "completed_at",
                    "message_preview",
                ]
            )

            for request in requests:
                writer.writerow(
                    [
                        request.id,
                        request.provider,
                        request.status.value,
                        datetime.fromtimestamp(request.created_at).isoformat(),
                        datetime.fromtimestamp(request.updated_at).isoformat() if request.updated_at else "",
                        request.priority,
                        request.timeout_s,
                        datetime.fromtimestamp(request.started_at).isoformat() if request.started_at else "",
                        datetime.fromtimestamp(request.completed_at).isoformat() if request.completed_at else "",
                        request.message[:100] if request.message else "",
                    ]
                )

            return Response(
                content=output.getvalue(),
                media_type="text/csv",
                headers={
                    "Content-Disposition": (
                        f'attachment; filename="requests_export_{datetime.now().strftime("%Y%m%d")}.csv"'
                    ),
                },
            )

        data = [
            {
                **request.to_dict(),
                "created_at_iso": datetime.fromtimestamp(request.created_at).isoformat(),
            }
            for request in requests
        ]

        return JSONResponse(
            content={
                "export_time": datetime.now().isoformat(),
                "total_count": len(data),
                "days": days,
                "filters": {"status": status, "provider": provider},
                "requests": data,
            },
        )


    @router.get("/api/export/metrics")
    async def export_metrics(
        format: str = Query("json", description="Export format: json or csv"),
        days: int = Query(7, ge=1, le=90, description="Number of days to export"),
        store=Depends(get_store),
    ):
        """
        Export metrics to JSON or CSV format.

        Exports provider performance metrics and cost data.
        """
        import csv
        from datetime import datetime
        from io import StringIO

        cost_by_provider = store.get_cost_by_provider(days=days)
        cost_by_day = store.get_cost_by_day(days=days)
        summary = store.get_cost_summary(days=days)

        if format == "csv":
            output = StringIO()
            writer = csv.writer(output)

            writer.writerow(["# Summary"])
            writer.writerow(["Metric", "Value"])
            writer.writerow(["Total Input Tokens", summary.get("total_input_tokens", 0)])
            writer.writerow(["Total Output Tokens", summary.get("total_output_tokens", 0)])
            writer.writerow(["Total Cost USD", summary.get("total_cost_usd", 0)])
            writer.writerow(["Total Requests", summary.get("total_requests", 0)])
            writer.writerow([])

            writer.writerow(["# By Provider"])
            writer.writerow(["Provider", "Input Tokens", "Output Tokens", "Cost USD", "Requests"])
            for provider_metrics in cost_by_provider:
                writer.writerow(
                    [
                        provider_metrics.get("provider"),
                        provider_metrics.get("total_input_tokens", 0),
                        provider_metrics.get("total_output_tokens", 0),
                        provider_metrics.get("total_cost_usd", 0),
                        provider_metrics.get("request_count", 0),
                    ]
                )
            writer.writerow([])

            writer.writerow(["# By Day"])
            writer.writerow(["Date", "Input Tokens", "Output Tokens", "Cost USD", "Requests"])
            for day_metrics in cost_by_day:
                writer.writerow(
                    [
                        day_metrics.get("date"),
                        day_metrics.get("total_input_tokens", 0),
                        day_metrics.get("total_output_tokens", 0),
                        day_metrics.get("total_cost_usd", 0),
                        day_metrics.get("request_count", 0),
                    ]
                )

            return Response(
                content=output.getvalue(),
                media_type="text/csv",
                headers={
                    "Content-Disposition": (
                        f'attachment; filename="metrics_export_{datetime.now().strftime("%Y%m%d")}.csv"'
                    ),
                },
            )

        return JSONResponse(
            content={
                "export_time": datetime.now().isoformat(),
                "days": days,
                "summary": summary,
                "by_provider": cost_by_provider,
                "by_day": cost_by_day,
            },
        )


    @router.get("/api/export/discussions")
    async def export_discussions(
        format: str = Query("json", description="Export format: json or md"),
        status: Optional[str] = Query(None, description="Filter by status"),
        days: int = Query(30, ge=1, le=365, description="Number of days to export"),
        store=Depends(get_store),
    ):
        """
        Export discussions to JSON or Markdown format.

        Exports all discussion sessions with their messages.
        """
        from datetime import datetime

        since = time.time() - (days * 86400)

        status_enum = DiscussionStatus(status) if status else None
        sessions = store.list_discussion_sessions(
            status=status_enum,
            limit=1000,
        )

        sessions = [session for session in sessions if session.created_at >= since]

        if format == "md":
            lines = [
                "# CCB Discussion Export",
                "",
                f"Export Date: {datetime.now().isoformat()}",
                f"Total Discussions: {len(sessions)}",
                "",
                "---",
                "",
            ]

            for session in sessions:
                lines.append(f"## {session.topic}")
                lines.append("")
                lines.append(f"- **ID**: {session.id}")
                lines.append(f"- **Status**: {session.status.value}")
                lines.append(f"- **Providers**: {', '.join(session.providers)}")
                lines.append(f"- **Created**: {datetime.fromtimestamp(session.created_at).isoformat()}")
                lines.append("")

                if session.summary:
                    lines.append("### Summary")
                    lines.append("")
                    lines.append(session.summary)
                    lines.append("")

                messages = store.get_discussion_messages(session.id)
                if messages:
                    lines.append("### Messages")
                    lines.append("")
                    for message in messages:
                        lines.append(
                            f"**{message.provider}** ({message.message_type.value}, Round {message.round_number}):"
                        )
                        lines.append("")
                        if message.content:
                            lines.append(message.content)
                        lines.append("")

                lines.append("---")
                lines.append("")

            return Response(
                content="\n".join(lines),
                media_type="text/markdown",
                headers={
                    "Content-Disposition": (
                        f'attachment; filename="discussions_export_{datetime.now().strftime("%Y%m%d")}.md"'
                    ),
                },
            )

        data = []
        for session in sessions:
            messages = store.get_discussion_messages(session.id)
            data.append(
                {
                    **session.to_dict(),
                    "created_at_iso": datetime.fromtimestamp(session.created_at).isoformat(),
                    "messages": [message.to_dict() for message in messages],
                }
            )

        return JSONResponse(
            content={
                "export_time": datetime.now().isoformat(),
                "total_count": len(data),
                "days": days,
                "filters": {"status": status},
                "discussions": data,
            },
        )
