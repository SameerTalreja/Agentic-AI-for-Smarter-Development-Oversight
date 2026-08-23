"""
backend/routes/review_board.py
Track C - Multi-Agent Review Board endpoint.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from backend.schemas import ReviewBoardRequest, AgentRunResponse
from agents.review_board import run_review_board, DEFAULT_TASK
from fastapi.responses import StreamingResponse
from backend.streaming import stream_run, sse, _SENTINEL

router = APIRouter(prefix="/api/review-board", tags=["review-board"])


@router.post("", response_model=AgentRunResponse)
def run_review_board_endpoint(request: ReviewBoardRequest) -> AgentRunResponse:
    task = request.task or DEFAULT_TASK
    try:
        result = run_review_board(task=task, dataset_id=request.dataset_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return AgentRunResponse(
        query_id=result["query_id"],
        final_answer=result["final_answer"],
        steps=result["steps"],
        stopped_reason=result["stopped_reason"],
        plan=result["specialist_findings"],
    )

@router.post("/stream")
def run_review_board_stream(request: ReviewBoardRequest):
    task = request.task or DEFAULT_TASK

    def run_fn(cancel_event, q):
        try:
            def on_step(step):
                q.put(sse("step", step))

            def on_specialist_done(name, finding):
                q.put(sse("specialist_done", {"agent": name, "finding": finding}))

            result = run_review_board(
                task=task,
                dataset_id=request.dataset_id,
                on_specialist_done=on_specialist_done,
                on_step=on_step,
                cancel_event=cancel_event,
            )
            q.put(sse("done", result))
        except Exception as e:
            q.put(sse("error", {"error": str(e)}))
        finally:
            q.put(_SENTINEL)

    return StreamingResponse(stream_run(run_fn), media_type="text/event-stream")