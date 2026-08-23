"""
core/audit_tools.py

Tools specific to Track B (the Audit Agent) -- things that aren't
expressible as a simple filter/aggregate, like "cost outliers within
their own category" (a school priced far above its peers).
"""

from __future__ import annotations

from typing import Any, Optional

import pandas as pd

from core.tools import _get_dataframe


def find_outliers(
    dataset_id: str,
    column: str,
    group_by: Optional[str] = None,
    method: str = "iqr",
    threshold: float = 1.5,
    min_group_size: int = 5,
    limit: int = 5,
) -> dict[str, Any]:
    """
    Find statistical outliers in `column`, optionally computed separately
    within each `group_by` group. IQR method (Tukey fence).
    Groups smaller than `min_group_size` are skipped.
    """
    df, _ = _get_dataframe(dataset_id)

    if column not in df.columns:
        return {"error": f"Unknown column '{column}'"}
    if group_by and group_by not in df.columns:
        return {"error": f"Unknown group_by column '{group_by}'"}
    if method != "iqr":
        return {"error": f"Unsupported method '{method}'. Only 'iqr' is currently supported."}

    def _iqr_bounds(series):
        q1, q3 = series.quantile(0.25), series.quantile(0.75)
        iqr = q3 - q1
        return q1 - threshold * iqr, q3 + threshold * iqr, q1, q3

    outliers: list[dict[str, Any]] = []
    skipped_groups: list[str] = []

    if group_by:
        for key, group_df in df.groupby(group_by, dropna=False):
            key_label = "(missing)" if key is None else str(key)
            data = group_df[column].dropna()
            if len(data) < min_group_size:
                skipped_groups.append(key_label)
                continue
            lower, upper, q1, q3 = _iqr_bounds(data)
            flagged = group_df[(group_df[column] > upper) | (group_df[column] < lower)]
            for _, row in flagged.iterrows():
                row_dict = row.to_dict()
                outliers.append({
                    "group": key_label,
                    "value": float(row[column]) if pd.notna(row[column]) else None,
                    "group_q1": float(q1),
                    "group_q3": float(q3),
                    "group_normal_range": [round(float(lower), 2), round(float(upper), 2)],
                    "row": {
                        k: (None if isinstance(row_dict.get(k), float) and (row_dict.get(k) != row_dict.get(k)) else row_dict.get(k))
                        for k in ["Global ID", "Description", "District", "Category", "Status", column]
                        if k in row_dict
                    },
                })
    else:
        data = df[column].dropna()
        if len(data) < min_group_size:
            return {"error": f"Not enough non-missing values in '{column}' to compute outliers."}
        lower, upper, q1, q3 = _iqr_bounds(data)
        flagged = df[(df[column] > upper) | (df[column] < lower)]
        for _, row in flagged.iterrows():
            row_dict = row.to_dict()
            outliers.append({
                "group": None,
                "value": float(row[column]) if pd.notna(row[column]) else None,
                "group_q1": float(q1),
                "group_q3": float(q3),
                "group_normal_range": [round(float(lower), 2), round(float(upper), 2)],
                "row": {
                    k: (None if isinstance(row_dict.get(k), float) and (row_dict.get(k) != row_dict.get(k)) else row_dict.get(k))
                    for k in ["Global ID", "Description", "District", "Category", "Status", column]
                    if k in row_dict
                    },
            })

    total_found = len(outliers)
    outliers_sorted = sorted(
        outliers,
        key=lambda o: abs(o["value"] - ((o["group_q1"] + o["group_q3"]) / 2)) if o["value"] is not None else 0,
        reverse=True,
    )

    return {
        "dataset_id": dataset_id,
        "column": column,
        "group_by": group_by,
        "method": "iqr",
        "threshold": threshold,
        "total_outliers_found": total_found,
        "outliers_returned": min(total_found, limit),
        "truncated": total_found > limit,
        "skipped_groups_insufficient_data": skipped_groups,
        "outliers": outliers_sorted[:limit],
    }


AUDIT_TOOL_SCHEMAS = [
    {
        "name": "find_outliers",
        "description": "Find statistical outliers (IQR method) in a numeric column, optionally computed separately within each group of another column (e.g. cost outliers within each Category, rather than across the whole dataset). Use this for checks like 'a school priced far above its peers'.",
        "input_schema": {
            "type": "object",
            "properties": {
                "dataset_id": {"type": "string"},
                "column": {"type": "string", "description": "Numeric column to check, e.g. 'Cost (M)'"},
                "group_by": {"type": "string", "description": "Optional column to compute outliers within, e.g. 'Category'"},
                "threshold": {"type": "number", "default": 1.5, "description": "IQR multiplier for outlier fence (1.5 is standard)"},
                "min_group_size": {"type": "integer", "default": 5},
                "limit": {"type": "integer", "default": 5},
            },
            "required": ["column"],
        },
    },
]

AUDIT_TOOL_FUNCTIONS = {
    "find_outliers": find_outliers,
}