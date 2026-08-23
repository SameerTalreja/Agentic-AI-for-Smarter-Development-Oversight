"""
backend/routes/history.py
Browse/search past agent runs.
"""

from __future__ import annotations

from typing import Optional
from fastapi import APIRouter, HTTPException, Query

from backend.schemas import HistoryListResponse, QueryRunSummary
from core.history_tools import lookup_query, list_recent_queries
from fastapi.responses import Response
from backend.pdf_export import build_run_pdf
from fastapi.responses import Response as ImageResponse
from core.chart_generator import render_bar_chart_png , infer_top_n
from datetime import datetime, timedelta
from collections import defaultdict

router = APIRouter(prefix="/api/history", tags=["history"])


@router.get("", response_model=HistoryListResponse)
def get_history(
    dataset_id: Optional[str] = Query(default=None),
    track: Optional[str] = Query(default=None),
    limit: int = Query(default=20),
) -> HistoryListResponse:
    result = list_recent_queries(dataset_id=dataset_id, track=track, limit=limit)
    return HistoryListResponse(
        count=result["count"],
        runs=[QueryRunSummary(**r) for r in result["runs"]],
    )


@router.get("/{query_id}")
def get_query_detail(query_id: str) -> dict:
    result = lookup_query(query_id)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result

@router.get("/{query_id}/pdf")
def download_query_pdf(query_id: str) -> Response:
    """Public/user report -- no raw tool trace, charts only."""
    result = lookup_query(query_id)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])

    pdf_bytes = build_run_pdf(result, include_trace=False)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{query_id}.pdf"'},
    )


@router.get("/{query_id}/pdf")
def download_query_pdf(query_id: str) -> Response:
    """Public/user report -- no raw tool trace, charts only."""
    result = lookup_query(query_id)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])

    pdf_bytes = build_run_pdf(result, include_trace=False)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{query_id}.pdf"'},
    )


@router.get("/{query_id}/pdf/admin")
def download_query_pdf_admin(query_id: str) -> Response:
    """Admin report -- includes the full raw tool trace."""
    result = lookup_query(query_id)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])

    pdf_bytes = build_run_pdf(result, include_trace=True)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{query_id}_admin.pdf"'},
    )

@router.get("/stats/daily")
def get_daily_stats(days: int = 14) -> dict:
    """
    Real counts of agent runs per day per track, computed directly from
    QueryRun rows -- used to power the admin dashboard chart. Never
    estimated or fabricated; days with zero runs show 0, not omitted.
    """
    from db.database import session_scope
    from db.models import QueryRun

    cutoff = datetime.utcnow() - timedelta(days=days)

    with session_scope() as db:
        runs = db.query(QueryRun.track, QueryRun.created_at, QueryRun.status).filter(
            QueryRun.created_at >= cutoff
        ).all()

    counts = defaultdict(lambda: {"A": 0, "B": 0, "C": 0})
    total_by_track = {"A": 0, "B": 0, "C": 0}
    total_completed = 0
    total_failed = 0

    for track, created_at, status in runs:
        day_key = created_at.strftime("%Y-%m-%d") if created_at else "unknown"
        if track in counts[day_key]:
            counts[day_key][track] += 1
        if track in total_by_track:
            total_by_track[track] += 1
        if status == "completed":
            total_completed += 1
        elif status == "failed":
            total_failed += 1

    # Fill in every day in the range, even zero-run days, so the chart
    # doesn't silently skip gaps.
    days_list = []
    for i in range(days - 1, -1, -1):
        day = (datetime.utcnow() - timedelta(days=i)).strftime("%Y-%m-%d")
        days_list.append({
            "date": day,
            "A": counts.get(day, {}).get("A", 0),
            "B": counts.get(day, {}).get("B", 0),
            "C": counts.get(day, {}).get("C", 0),
        })

    return {
        "days": days_list,
        "total_by_track": total_by_track,
        "total_runs": sum(total_by_track.values()),
        "total_completed": total_completed,
        "total_failed": total_failed,
    }

@router.get("/{query_id}/chart/{step_number}")
def get_chart_image(query_id: str, step_number: int) -> ImageResponse:
    result = lookup_query(query_id)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])

    step = next(
        (s for s in result["tool_calls"] if s["step_number"] == step_number),
        None,
    )
    if step is None or not step.get("result", {}).get("groups"):
        raise HTTPException(status_code=404, detail="No chartable data for this step.")

    top_n = infer_top_n(result.get("question", ""))
    title = f"{step['result'].get('operation')} by {step['result'].get('group_by')}"
    png_bytes = render_bar_chart_png(title, step["result"]["groups"], max_bars=top_n)

    return ImageResponse(content=png_bytes, media_type="image/png")

@router.delete("/{query_id}")
def delete_query(query_id: str) -> dict:
    from db.database import session_scope
    from db.models import QueryRun

    with session_scope() as db:
        run = db.query(QueryRun).filter(QueryRun.id == query_id).first()
        if run is None:
            raise HTTPException(status_code=404, detail=f"No query found with id '{query_id}'")
        db.delete(run)  # cascade="all, delete-orphan" on ToolCall handles the child rows

    return {"deleted": query_id}

