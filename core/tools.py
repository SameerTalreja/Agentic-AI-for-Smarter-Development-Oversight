"""
core/tools.py

The tools the LLM agents actually call during the plan -> act -> observe
loop. Every function here:
  - takes a dataset_id and simple arguments (JSON-serializable, since
    they come straight from an LLM tool-call)
  - returns plain dict/list structures (again JSON-serializable)
  - never invents a number: aggregates report how many rows they're
    based on, and missing data is reported, not silently dropped
    without a trace
"""

from __future__ import annotations

from typing import Any, Optional

import pandas as pd

from db.database import session_scope
from db.models import Dataset, DataQualityReport
from core.data_loader import load_dataset


_CACHE: dict[str, dict[str, Any]] = {}


def _get_dataframe(dataset_id: str) -> tuple[pd.DataFrame, str]:
    import os

    with session_scope() as db:
        dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
        if dataset is None:
            raise ValueError(f"No dataset found with id '{dataset_id}'")
        filepath = dataset.filepath
        detected_schema = dataset.detected_schema or "generic"

    mtime = os.path.getmtime(filepath)
    cached = _CACHE.get(dataset_id)
    if cached and cached["mtime"] == mtime:
        return cached["df"], detected_schema

    result = load_dataset(filepath)
    _CACHE[dataset_id] = {"df": result.df, "mtime": mtime}
    return result.df, detected_schema


def describe_schema(dataset_id: str) -> dict[str, Any]:
    df, detected_schema = _get_dataframe(dataset_id)

    columns_info = []
    for col in df.columns:
        dtype = str(df[col].dtype)
        entry: dict[str, Any] = {"name": col, "dtype": dtype}

        if dtype == "object" or dtype == "str" or "string" in dtype:
            uniques = df[col].dropna().unique()
            if len(uniques) <= 50:
                entry["distinct_values"] = sorted(map(str, uniques))
            else:
                entry["distinct_value_count"] = int(len(uniques))
        else:
            non_null = df[col].dropna()
            if len(non_null) > 0:
                entry["min"] = float(non_null.min())
                entry["max"] = float(non_null.max())

        columns_info.append(entry)

    return {
        "dataset_id": dataset_id,
        "detected_schema": detected_schema,
        "row_count": int(len(df)),
        "columns": columns_info,
    }


def filter_rows(
    dataset_id: str,
    filters: Optional[dict[str, Any]] = None,
    sort_by: Optional[str] = None,
    sort_order: str = "desc",
    limit: int = 5,
) -> dict[str, Any]:
    """
    Generic row filter. `filters` is a dict of {column_name: value_or_condition}.

    Supported value shapes per column:
      - exact match:            {"District": "Kech"}
      - list (IN):               {"Status": ["Completed", "In Progress"]}
      - range dict:               {"Cost (M)": {"gte": 10, "lte": 50}}
      - text contains (case-insensitive): {"Description": {"contains": "water"}}

    sort_by / sort_order: optionally sort matches before truncating, so
    "top N by cost" only returns N rows instead of the whole matched set.

    Returns matching rows (capped at `limit`) plus the true total match
    count, so the agent knows if it's seeing a partial result.
    """
    df, _ = _get_dataframe(dataset_id)
    filters = filters or {}

    matched = _apply_filters(df, filters)
    total_matches = int(len(matched))

    unknown_columns = [c for c in filters if c not in df.columns]

    if sort_by:
        if sort_by not in df.columns:
            return {
                "dataset_id": dataset_id,
                "filters_applied": filters,
                "unknown_columns": unknown_columns + [sort_by],
                "total_matches": total_matches,
                "rows_returned": 0,
                "truncated": False,
                "rows": [],
                "error": f"Unknown sort_by column '{sort_by}'",
            }
        matched = matched.sort_values(by=sort_by, ascending=(sort_order == "asc"))

    limited = matched.head(limit)
    rows = limited.where(pd.notnull(limited), None).to_dict(orient="records")

    return {
        "dataset_id": dataset_id,
        "filters_applied": filters,
        "unknown_columns": unknown_columns,
        "total_matches": total_matches,
        "rows_returned": len(rows),
        "truncated": total_matches > limit,
        "rows": rows,
    }

def aggregate(
    dataset_id: str,
    operation: str,
    column: Optional[str] = None,
    filters: Optional[dict[str, Any]] = None,
    group_by: Optional[str] = None,
    percentile: Optional[float] = None,
) -> dict[str, Any]:
    df, _ = _get_dataframe(dataset_id)
    filters = filters or {}

    subset = _apply_filters(df, filters)

    if operation not in {"count", "sum", "avg", "min", "max", "percentile"}:
        raise ValueError(f"Unsupported operation '{operation}'")

    def _agg_for(data: pd.DataFrame) -> dict[str, Any]:
        total_in_group = int(len(data))
        if operation == "count":
            return {"value": total_in_group, "based_on_rows": total_in_group, "excluded_missing": 0}

        if column is None:
            raise ValueError(f"'column' is required for operation '{operation}'")
        if column not in data.columns:
            raise ValueError(f"Unknown column '{column}'")

        col_data = data[column]
        non_null = col_data.dropna()
        excluded = int(col_data.isna().sum())

        if len(non_null) == 0:
            return {"value": None, "based_on_rows": 0, "excluded_missing": excluded,
                     "note": f"No non-missing values for '{column}' in this filtered set."}

        if operation == "percentile":
            if percentile is None:
                raise ValueError("'percentile' (0-100) is required for operation 'percentile'")
            value = round(float(non_null.quantile(percentile / 100)), 2)
        else:
            value = {
                "sum": float(non_null.sum()),
                "avg": round(float(non_null.mean()), 2),
                "min": float(non_null.min()),
                "max": float(non_null.max()),
            }[operation]

        return {"value": value, "based_on_rows": int(len(non_null)), "excluded_missing": excluded}

    if group_by:
        if group_by not in subset.columns:
            raise ValueError(f"Unknown group_by column '{group_by}'")

        distinct_count = subset[group_by].nunique(dropna=False)
        MAX_GROUPS = 40
        if distinct_count > MAX_GROUPS:
            return {
                "dataset_id": dataset_id,
                "operation": operation,
                "column": column,
                "group_by": group_by,
                "filters_applied": filters,
                "error": (
                    f"'{group_by}' has {distinct_count} distinct values, too many "
                    f"to group by directly (limit {MAX_GROUPS}). This column is "
                    f"likely free-text/high-cardinality (e.g. Description) rather "
                    f"than a category. Use filter_rows with a 'contains' or exact "
                    f"match instead, or group_by a categorical column like "
                    f"District/Category/Status."
                ),
            }

        groups = {}
        for key, group_df in subset.groupby(group_by, dropna=False):
            key_label = "(missing)" if pd.isna(key) else str(key)
            groups[key_label] = _agg_for(group_df)
        return {
            "dataset_id": dataset_id,
            "operation": operation,
            "column": column,
            "group_by": group_by,
            "filters_applied": filters,
            "groups": groups,
        }

    result = _agg_for(subset)
    return {
        "dataset_id": dataset_id,
        "operation": operation,
        "column": column,
        "filters_applied": filters,
        **result,
    }


def _apply_filters(df: pd.DataFrame, filters: dict[str, Any]) -> pd.DataFrame:
    """Shared filter-application logic used by both filter_rows and aggregate.
    Tolerates a few common syntax variants models tend to invent (e.g. Mongo-
    style $lt, or None meaning "is null") instead of failing silently."""
    mask = pd.Series(True, index=df.index)

    # Normalize alternate operator spellings to our canonical keys.
    OP_ALIASES = {
        "$gte": "gte", "$gt": "gt", "$lte": "lte", "$lt": "lt",
        "$eq": "eq", "$ne": "ne", "$in": "in", "$contains": "contains",
        "$is_null": "is_null", "$exists": "is_null",
    }

    for col, condition in filters.items():
        if col not in df.columns:
            continue
        series = df[col]

        if condition is None:
            # A bare null value is almost always intended as "is missing"
            mask &= series.isna()
            continue

        if isinstance(condition, dict):
            normalized = {OP_ALIASES.get(k, k): v for k, v in condition.items()}
            if "is_null" in normalized:
                is_null_flag = normalized["is_null"]
                # "$exists" has inverted meaning vs "is_null"/"$is_null"
                if "$exists" in condition:
                    is_null_flag = not is_null_flag
                mask &= series.isna() if is_null_flag else series.notna()
            if "gte" in normalized:
                mask &= series >= normalized["gte"]
            if "lte" in normalized:
                mask &= series <= normalized["lte"]
            if "gt" in normalized:
                mask &= series > normalized["gt"]
            if "lt" in normalized:
                mask &= series < normalized["lt"]
            if "eq" in normalized:
                mask &= series == normalized["eq"]
            if "ne" in normalized:
                mask &= series != normalized["ne"]
            if "in" in normalized and isinstance(normalized["in"], list):
                mask &= series.isin(normalized["in"])
            if "contains" in normalized:
                needle = str(normalized["contains"]).lower()
                mask &= series.astype(str).str.lower().str.contains(needle, na=False)
        elif isinstance(condition, list):
            mask &= series.isin(condition)
        else:
            mask &= series == condition

    return df[mask]


def check_data_quality(dataset_id: str, column: Optional[str] = None) -> dict[str, Any]:
    with session_scope() as db:
        report = db.query(DataQualityReport).filter(
            DataQualityReport.dataset_id == dataset_id
        ).first()

        if report is None:
            return {"dataset_id": dataset_id, "error": "No quality report found for this dataset."}

        full = {
            "dataset_id": dataset_id,
            "total_rows": report.total_rows,
            "missing_by_column": report.missing_by_column,
            "format_issues": report.format_issues,
            "near_duplicate_categories": report.near_duplicate_categories,
            "anomalies": report.anomalies,
        }

    if column:
        return {
            "dataset_id": dataset_id,
            "column": column,
            "missing": full["missing_by_column"].get(column),
            "format_issues": full["format_issues"].get(column),
            "near_duplicates": full["near_duplicate_categories"].get(column),
            "anomalies": full["anomalies"].get(column),
        }

    return full


TOOL_SCHEMAS = [
    {
        "name": "describe_schema",
        "description": "Get the list of columns, their types, and (for categorical columns) their distinct values for a dataset. Call this first if unsure what columns/values exist.",
        "input_schema": {
            "type": "object",
            "properties": {
                "dataset_id": {"type": "string"},
            },
            "required": [],
        },
    },
    {
        "name": "filter_rows",
        "description": "Filter dataset rows by column conditions (exact match, list/IN, range with gte/lte/gt/lt, text contains, or is_null true/false for missing-value checks). Supports sort_by + sort_order to get top/bottom N results directly. Keep limit small (default 20) -- large limits can exceed token limits.",
        "input_schema": {
            "type": "object",
            "properties": {
                "dataset_id": {"type": "string"},
                "filters": {"type": "object", "description": "e.g. {\"District\": \"Kech\", \"Status\": [\"Completed\"]}"},
                "sort_by": {"type": "string", "description": "Column to sort by, e.g. 'Cost (M)'"},
                "sort_order": {"type": "string", "enum": ["asc", "desc"], "default": "desc"},
                "limit": {"type": "integer", "default": 20},
            },
            "required": ["dataset_id"],
        },
    },
    {
        "name": "aggregate",
        "description": "Compute count/sum/avg/min/max/percentile over a (optionally filtered, optionally grouped) set of rows. Always reports how many rows the result is based on and how many were excluded for missing data.",
        "input_schema": {
            "type": "object",
            "properties": {
                "dataset_id": {"type": "string"},
                "operation": {"type": "string", "enum": ["count", "sum", "avg", "min", "max", "percentile"]},
                "column": {"type": "string"},
                "filters": {"type": "object"},
                "group_by": {"type": "string"},
                "percentile": {"type": "number", "description": "0-100, required when operation is 'percentile'"},
            },
            "required": [ "operation"],
        },
    },
    {
        "name": "check_data_quality",
        "description": "Get the data quality report for a dataset (missing values, format issues, near-duplicate categories, anomalies). Call this before presenting any statistic on a column that might have significant missing data.",
        "input_schema": {
            "type": "object",
            "properties": {
                "dataset_id": {"type": "string"},
                "column": {"type": "string"},
            },
            "required": [],
        },
    },
]

TOOL_FUNCTIONS = {
    "describe_schema": describe_schema,
    "filter_rows": filter_rows,
    "aggregate": aggregate,
    "check_data_quality": check_data_quality,
}