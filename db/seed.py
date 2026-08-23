"""
db/seed.py
Loads data/default/Projects.xlsx as the protected default Dataset on startup.
Safe to run repeatedly.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.database import init_db, session_scope
from db.models import Dataset, DataQualityReport
from core.data_loader import load_dataset

DEFAULT_DATASET_ID = "default"
DEFAULT_FILE_PATH = os.path.join("data", "default", "Projects.xlsx")


def seed_default_dataset() -> None:
    init_db()

    with session_scope() as db:
        existing = db.query(Dataset).filter(Dataset.id == DEFAULT_DATASET_ID).first()
        if existing:
            print(f"[seed] Default dataset already present (id={existing.id}). Skipping.")
            return

        if not os.path.exists(DEFAULT_FILE_PATH):
            print(f"[seed] WARNING: {DEFAULT_FILE_PATH} not found.")
            return

        result = load_dataset(DEFAULT_FILE_PATH)

        dataset = Dataset(
            id=DEFAULT_DATASET_ID,
            name="PMTS Projects List (Balochistan, default)",
            type="tabular",
            filename="Projects.xlsx",
            filepath=DEFAULT_FILE_PATH,
            protected=True,
            column_schema=result.column_types,
            detected_schema=result.detected_schema,
        )
        db.add(dataset)
        db.flush()

        report = result.quality_report
        quality = DataQualityReport(
            dataset_id=dataset.id,
            total_rows=report["total_rows"],
            missing_by_column=report["missing_by_column"],
            format_issues=report["format_issues"],
            near_duplicate_categories=report["near_duplicate_categories"],
            anomalies=report["anomalies"],
        )
        db.add(quality)

        print(f"[seed] Inserted default dataset '{dataset.id}' "
              f"({report['total_rows']} rows, schema={result.detected_schema}).")


if __name__ == "__main__":
    seed_default_dataset()