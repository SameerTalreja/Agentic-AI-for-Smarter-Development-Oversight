"""
backend/routes/query.py
Track A - Query Agent endpoint.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from backend.schemas import QueryRequest, AgentRunResponse
from agents.query_agent import ask
from fastapi.responses import StreamingResponse
from backend.streaming import stream_run, sse, _SENTINEL

router = APIRouter(prefix="/api/query", tags=["query"])


@router.post("", response_model=AgentRunResponse)
def run_query(request: QueryRequest) -> AgentRunResponse:
    try:
        result = ask(question=request.question, dataset_id=request.dataset_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return AgentRunResponse(
        query_id=result["query_id"],
        final_answer=result["final_answer"],
        steps=result["steps"],
        stopped_reason=result["stopped_reason"],
    )

@router.post("/stream")
def run_query_stream(request: QueryRequest):
    def run_fn(cancel_event, q):
        try:
            def on_step(step):
                q.put(sse("step", step))

            result = ask(
                question=request.question,
                dataset_id=request.dataset_id,
                on_step=on_step,
                cancel_event=cancel_event,
            )
            q.put(sse("done", result))
        except Exception as e:
            q.put(sse("error", {"error": str(e)}))
        finally:
            q.put(_SENTINEL)

    return StreamingResponse(stream_run(run_fn), media_type="text/event-stream")