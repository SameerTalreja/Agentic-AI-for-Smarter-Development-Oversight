"""
backend/schemas.py

Pydantic request/response models for the API. Kept separate from
db/models.py -- these are the HTTP contract, not the DB schema (though
they're structurally similar for simplicity here).
"""

from __future__ import annotations

from typing import Any, Optional
from pydantic import BaseModel


class QueryRequest(BaseModel):
    question: str
    dataset_id: str = "default"


class AuditRequest(BaseModel):
    goal: Optional[str] = None
    dataset_id: str = "default"


class ReviewBoardRequest(BaseModel):
    task: Optional[str] = None
    dataset_id: str = "default"


class ToolCallOut(BaseModel):
    step_number: int
    agent_role: Optional[str] = None
    tool_name: str
    arguments: dict[str, Any]
    result: Any


class AgentRunResponse(BaseModel):
    query_id: str
    final_answer: str
    steps: list[dict[str, Any]]
    stopped_reason: str
    plan: Optional[Any] = None


class QueryRunSummary(BaseModel):
    query_id: str
    track: str
    dataset_id: str
    question: str
    final_answer: Optional[str] = None
    created_at: Optional[str] = None


class HistoryListResponse(BaseModel):
    count: int
    runs: list[QueryRunSummary]


class DatasetOut(BaseModel):
    id: str
    name: str
    type: str
    filename: str
    protected: bool
    detected_schema: Optional[str] = None
    uploaded_at: Optional[str] = None


class DatasetListResponse(BaseModel):
    datasets: list[DatasetOut]


class DataQualityReportOut(BaseModel):
    dataset_id: str
    total_rows: Optional[int] = None
    missing_by_column: Optional[dict[str, Any]] = None
    format_issues: Optional[dict[str, Any]] = None
    near_duplicate_categories: Optional[dict[str, Any]] = None
    anomalies: Optional[dict[str, Any]] = None