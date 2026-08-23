"""
core/history_tools.py

Tools that let an agent look back at its own (or another) past run.
This is what makes "what did qry_a1b2c3d4 find about Kech?" possible,
and is also the data source for the frontend's History page.
"""

from __future__ import annotations

from typing import Any, Optional

from db.database import session_scope
from db.models import QueryRun, ToolCall


def lookup_query(query_id: str) -> dict[str, Any]:
    """
    Fetch a past agent run by its query_id: the original question, the
    full tool-call trace, and the final answer that was given.
    """
    with session_scope() as db:
        run = db.query(QueryRun).filter(QueryRun.id == query_id).first()
        if run is None:
            return {"error": f"No query found with id '{query_id}'"}

        tool_calls = db.query(ToolCall).filter(
            ToolCall.query_run_id == query_id
        ).order_by(ToolCall.step_number).all()

        return {
            "query_id": run.id,
            "track": run.track,
            "dataset_id": run.dataset_id,
            "question": run.question,
            "final_answer": run.final_answer,
            "status": run.status,
            "created_at": run.created_at.isoformat() if run.created_at else None,
            "tool_calls": [
                {
                    "step_number": tc.step_number,
                    "tool_name": tc.tool_name,
                    "arguments": tc.arguments,
                    "result": tc.result,
                }
                for tc in tool_calls
            ],
        }


def list_recent_queries(
    dataset_id: Optional[str] = None,
    track: Optional[str] = None,
    limit: int = 10,
) -> dict[str, Any]:
    """List recent past runs, optionally filtered by dataset or track."""
    with session_scope() as db:
        query = db.query(QueryRun)
        if dataset_id:
            query = query.filter(QueryRun.dataset_id == dataset_id)
        if track:
            query = query.filter(QueryRun.track == track)

        runs = query.order_by(QueryRun.created_at.desc()).limit(limit).all()

        return {
            "count": len(runs),
            "runs": [
                {
                    "query_id": r.id,
                    "track": r.track,
                    "dataset_id": r.dataset_id,
                    "question": r.question,
                    "final_answer": r.final_answer,
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                }
                for r in runs
            ],
        }


HISTORY_TOOL_SCHEMAS = [
    {
        "name": "lookup_query",
        "description": "Fetch a past agent run by its query_id (e.g. 'qry_a1b2c3d4'), including the original question, full tool-call trace, and final answer. Use this when the user references a previous query by ID or says something like 'those' / 'that result' referring to an earlier answer.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query_id": {"type": "string"},
            },
            "required": ["query_id"],
        },
    },
    {
        "name": "list_recent_queries",
        "description": "List recent past agent runs (question + answer + id), optionally filtered by dataset or track. Useful for finding a past query_id if the user doesn't remember the exact id.",
        "input_schema": {
            "type": "object",
            "properties": {
                "dataset_id": {"type": "string"},
                "track": {"type": "string", "enum": ["A", "B", "C"]},
                "limit": {"type": "integer", "default": 10},
            },
        },
    },
]

HISTORY_TOOL_FUNCTIONS = {
    "lookup_query": lookup_query,
    "list_recent_queries": list_recent_queries,
}