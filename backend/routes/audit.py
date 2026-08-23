"""
backend/routes/audit.py
Track B - Audit Agent endpoint.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from backend.schemas import AuditRequest, AgentRunResponse
from agents.audit_agent import run_audit, DEFAULT_GOAL
from fastapi.responses import StreamingResponse
from backend.streaming import stream_run, sse, _SENTINEL

router = APIRouter(prefix="/api/audit", tags=["audit"])


@router.post("", response_model=AgentRunResponse)
def run_audit_endpoint(request: AuditRequest) -> AgentRunResponse:
    goal = request.goal or DEFAULT_GOAL
    try:
        result = run_audit(goal=goal, dataset_id=request.dataset_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return AgentRunResponse(
        query_id=result["query_id"],
        final_answer=result["final_answer"],
        steps=result["steps"],
        stopped_reason=result["stopped_reason"],
        plan=result["plan"],
    )

@router.post("/stream")
def run_audit_stream(request: AuditRequest):
    goal = request.goal or DEFAULT_GOAL

    def run_fn(cancel_event, q):
        try:
            def on_step(step):
                q.put(sse("step", step))

            def on_plan(plan):
                q.put(sse("plan", {"plan": plan}))

            result = run_audit(
                goal=goal,
                dataset_id=request.dataset_id,
                on_plan=on_plan,
                on_step=on_step,
                cancel_event=cancel_event,
            )
            q.put(sse("done", result))
        except Exception as e:
            q.put(sse("error", {"error": str(e)}))
        finally:
            q.put(_SENTINEL)

    return StreamingResponse(stream_run(run_fn), media_type="text/event-stream")