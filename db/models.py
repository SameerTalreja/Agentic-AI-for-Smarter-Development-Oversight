"""
db/models.py
Dataset, DataQualityReport, QueryRun, ToolCall, DocumentChunk
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Column, String, Integer, Boolean, DateTime, ForeignKey, JSON, Text, LargeBinary
)
from sqlalchemy.orm import relationship

from db.database import Base


def _uuid() -> str:
    return uuid.uuid4().hex[:8]


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Dataset(Base):
    __tablename__ = "datasets"

    id = Column(String, primary_key=True, default=lambda: f"ds_{_uuid()}")
    name = Column(String, nullable=False)
    type = Column(String, nullable=False)          # "tabular" | "document"
    filename = Column(String, nullable=False)
    filepath = Column(String, nullable=False)
    uploaded_at = Column(DateTime, default=_now)
    protected = Column(Boolean, default=False)
    column_schema = Column(JSON, nullable=True)
    detected_schema = Column(String, nullable=True)

    quality_report = relationship(
        "DataQualityReport", back_populates="dataset", uselist=False,
        cascade="all, delete-orphan"
    )
    query_runs = relationship("QueryRun", back_populates="dataset", cascade="all, delete-orphan")
    document_chunks = relationship(
        "DocumentChunk", back_populates="dataset", cascade="all, delete-orphan"
    )


class DataQualityReport(Base):
    __tablename__ = "data_quality_reports"

    id = Column(Integer, primary_key=True, autoincrement=True)
    dataset_id = Column(String, ForeignKey("datasets.id"), nullable=False, unique=True)
    total_rows = Column(Integer, nullable=True)
    missing_by_column = Column(JSON, nullable=True)
    format_issues = Column(JSON, nullable=True)
    near_duplicate_categories = Column(JSON, nullable=True)
    anomalies = Column(JSON, nullable=True)
    generated_at = Column(DateTime, default=_now)

    dataset = relationship("Dataset", back_populates="quality_report")


class QueryRun(Base):
    __tablename__ = "query_runs"

    id = Column(String, primary_key=True, default=lambda: f"qry_{_uuid()}")
    track = Column(String, nullable=False)           # "A" | "B" | "C"
    dataset_id = Column(String, ForeignKey("datasets.id"), nullable=False)
    question = Column(Text, nullable=False)
    plan = Column(JSON, nullable=True)
    final_answer = Column(Text, nullable=True)
    status = Column(String, default="running")
    created_at = Column(DateTime, default=_now)
    completed_at = Column(DateTime, nullable=True)

    dataset = relationship("Dataset", back_populates="query_runs")
    tool_calls = relationship(
        "ToolCall", back_populates="query_run", cascade="all, delete-orphan",
        order_by="ToolCall.step_number"
    )


class ToolCall(Base):
    __tablename__ = "tool_calls"

    id = Column(Integer, primary_key=True, autoincrement=True)
    query_run_id = Column(String, ForeignKey("query_runs.id"), nullable=False)
    step_number = Column(Integer, nullable=False)
    agent_role = Column(String, nullable=True)
    tool_name = Column(String, nullable=False)
    arguments = Column(JSON, nullable=True)
    result = Column(JSON, nullable=True)
    reasoning = Column(Text, nullable=True)
    created_at = Column(DateTime, default=_now)

    query_run = relationship("QueryRun", back_populates="tool_calls")


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    dataset_id = Column(String, ForeignKey("datasets.id"), nullable=False)
    chunk_index = Column(Integer, nullable=False)
    page_number = Column(Integer, nullable=True)
    chunk_text = Column(Text, nullable=False)
    embedding = Column(LargeBinary, nullable=True)

    dataset = relationship("Dataset", back_populates="document_chunks")