"""
backend/routes/datasets.py
List datasets, view quality reports, upload new tabular files.
"""

from __future__ import annotations

import os
import shutil
import uuid

from fastapi import APIRouter, HTTPException, UploadFile, File

from backend.schemas import DatasetListResponse, DatasetOut, DataQualityReportOut
from db.database import session_scope
from db.models import Dataset, DataQualityReport
from core.data_loader import load_dataset
from core.document_tools import ingest_document

router = APIRouter(prefix="/api/datasets", tags=["datasets"])

UPLOAD_DIR = os.environ.get("UPLOAD_DIR", "/tmp/uploads")
ALLOWED_EXTENSIONS = {".csv", ".xlsx", ".xls", ".pdf", ".docx"}
DOCUMENT_EXTENSIONS = {".pdf", ".docx"}

@router.get("", response_model=DatasetListResponse)
def list_datasets() -> DatasetListResponse:
    with session_scope() as db:
        rows = db.query(Dataset).order_by(Dataset.uploaded_at.desc()).all()
        return DatasetListResponse(datasets=[
            DatasetOut(
                id=d.id, name=d.name, type=d.type, filename=d.filename,
                protected=d.protected, detected_schema=d.detected_schema,
                uploaded_at=d.uploaded_at.isoformat() if d.uploaded_at else None,
            )
            for d in rows
        ])


@router.get("/{dataset_id}/quality-report", response_model=DataQualityReportOut)
def get_quality_report(dataset_id: str) -> DataQualityReportOut:
    with session_scope() as db:
        report = db.query(DataQualityReport).filter(
            DataQualityReport.dataset_id == dataset_id
        ).first()
        if report is None:
            raise HTTPException(status_code=404, detail="No quality report for this dataset.")
        return DataQualityReportOut(
            dataset_id=dataset_id,
            total_rows=report.total_rows,
            missing_by_column=report.missing_by_column,
            format_issues=report.format_issues,
            near_duplicate_categories=report.near_duplicate_categories,
            anomalies=report.anomalies,
        )


@router.post("/upload", response_model=DatasetOut)
def upload_dataset(file: UploadFile = File(...)) -> DatasetOut:
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{ext}'. Allowed: {sorted(ALLOWED_EXTENSIONS)}",
        )

    dataset_id = f"ds_{uuid.uuid4().hex[:8]}"
    dataset_dir = os.path.join(UPLOAD_DIR, dataset_id)
    os.makedirs(dataset_dir, exist_ok=True)
    filepath = os.path.join(dataset_dir, file.filename)

    with open(filepath, "wb") as f:
        shutil.copyfileobj(file.file, f)

    is_document = ext in DOCUMENT_EXTENSIONS

    if is_document:
        with session_scope() as db:
            dataset = Dataset(
                id=dataset_id,
                name=file.filename,
                type="document",
                filename=file.filename,
                filepath=filepath,
                protected=False,
            )
            db.add(dataset)
            out = DatasetOut(
                id=dataset.id, name=dataset.name, type=dataset.type,
                filename=dataset.filename, protected=dataset.protected,
                detected_schema=None,
                uploaded_at=None,
            )

        try:
            ingest_document(dataset_id, filepath)
        except Exception as e:
            shutil.rmtree(dataset_dir, ignore_errors=True)
            with session_scope() as db:
                db.query(Dataset).filter(Dataset.id == dataset_id).delete()
            raise HTTPException(status_code=400, detail=f"Failed to process document: {e}")

        return out

    # Tabular path (existing behavior)
    try:
        result = load_dataset(filepath)
    except Exception as e:
        shutil.rmtree(dataset_dir, ignore_errors=True)
        raise HTTPException(status_code=400, detail=f"Failed to parse file: {e}")

    with session_scope() as db:
        dataset = Dataset(
            id=dataset_id,
            name=file.filename,
            type="tabular",
            filename=file.filename,
            filepath=filepath,
            protected=False,
            column_schema=result.column_types,
            detected_schema=result.detected_schema,
        )
        db.add(dataset)
        db.flush()

        report = result.quality_report
        db.add(DataQualityReport(
            dataset_id=dataset.id,
            total_rows=report["total_rows"],
            missing_by_column=report["missing_by_column"],
            format_issues=report["format_issues"],
            near_duplicate_categories=report["near_duplicate_categories"],
            anomalies=report["anomalies"],
        ))

        out = DatasetOut(
            id=dataset.id, name=dataset.name, type=dataset.type,
            filename=dataset.filename, protected=dataset.protected,
            detected_schema=dataset.detected_schema,
            uploaded_at=dataset.uploaded_at.isoformat() if dataset.uploaded_at else None,
        )

    return out

@router.delete("/{dataset_id}")
def delete_dataset(dataset_id: str) -> dict:
    with session_scope() as db:
        dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
        if dataset is None:
            raise HTTPException(status_code=404, detail=f"No dataset found with id '{dataset_id}'")
        if dataset.protected:
            raise HTTPException(status_code=400, detail="Cannot delete a protected dataset.")

        filepath = dataset.filepath
        db.delete(dataset)  # cascades to DataQualityReport / DocumentChunk / QueryRun via relationships

    if filepath and os.path.exists(filepath):
        try:
            shutil.rmtree(os.path.dirname(filepath), ignore_errors=True)
        except Exception:
            pass

    return {"deleted": dataset_id}


@router.patch("/{dataset_id}/protect")
def set_dataset_protected(dataset_id: str, protected: bool = True) -> DatasetOut:
    with session_scope() as db:
        dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
        if dataset is None:
            raise HTTPException(status_code=404, detail=f"No dataset found with id '{dataset_id}'")
        dataset.protected = protected

        out = DatasetOut(
            id=dataset.id, name=dataset.name, type=dataset.type,
            filename=dataset.filename, protected=dataset.protected,
            detected_schema=dataset.detected_schema,
            uploaded_at=dataset.uploaded_at.isoformat() if dataset.uploaded_at else None,
        )

    return out