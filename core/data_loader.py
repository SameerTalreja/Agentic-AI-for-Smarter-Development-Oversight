"""
core/data_loader.py

Loads the PMTS Projects dataset (or any similarly-structured tabular file),
cleans it without ever inventing values, and produces a Data Quality Report
that downstream agents/tools are required to consult before answering.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any

import pandas as pd


PMTS_EXPECTED_COLUMNS = {
    "#", "Global ID", "District", "Phase", "Category", "Description",
    "Executing Agency", "Cost (M)", "TSE", "Contractor", "NITs",
    "Progress %", "Status", "Work Started", "XEN Name", "XEN Contact",
}

NUMERIC_HINT_COLUMNS = {"Cost (M)", "Progress %", "#"}


@dataclass
class LoadResult:
    df: pd.DataFrame
    raw_df: pd.DataFrame
    header_row_index: int
    detected_schema: str
    quality_report: dict[str, Any] = field(default_factory=dict)
    column_types: dict[str, str] = field(default_factory=dict)


def _find_header_row(path: str, sheet_name: str | int = 0, max_scan_rows: int = 15) -> int:
    preview = pd.read_excel(path, sheet_name=sheet_name, header=None, nrows=max_scan_rows)
    best_row, best_score = 0, -1
    for i in range(len(preview)):
        row = preview.iloc[i]
        non_null = row.notna().sum()
        string_like = sum(1 for v in row if isinstance(v, str) and 0 < len(v.strip()) < 40)
        score = non_null + string_like
        if score > best_score:
            best_score, best_row = score, i
    return best_row


def _clean_contractor_name(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    v = value.strip()
    v = re.sub(r'^["\'\u201c\u201d]+', "", v)
    v = re.sub(r'["\'\u201c\u201d]+$', "", v)
    v = re.sub(r'^(M/S\s+)(M/s\s+)', r'\1', v, flags=re.IGNORECASE)
    v = re.sub(r'\s+', ' ', v).strip()
    return v if v else None


def _normalize_phone(value: Any) -> tuple[Any, str | None]:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None, None

    raw = str(value).strip()
    issue = None

    if re.match(r'^\d+(\.\d+)?[eE]\+\d+$', raw):
        try:
            digits = str(int(float(raw)))
            issue = "scientific_notation"
        except ValueError:
            return raw, "unparseable"
    else:
        digits = raw

    digits = re.sub(r'[,\-\s]', '', digits)
    if issue is None and (',' in raw or ' ' in raw or raw.count('-') > 0):
        issue = "mixed_separators"

    digits = re.sub(r'\D', '', digits)

    if digits.startswith("92") and len(digits) == 12:
        digits = "0" + digits[2:]
        issue = issue or "country_code_prefixed"
    elif len(digits) == 10 and not digits.startswith("0"):
        digits = "0" + digits
        issue = issue or "no_leading_zero"

    if len(digits) == 11 and digits.startswith("0"):
        normalized = f"{digits[:4]}-{digits[4:]}"
        return normalized, issue

    return raw, "unparseable"


def _normalize_agency(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    v = value.strip()
    v_lower = v.lower()

    groups = {
        "Local Government": {"lg", "local govt", "lgrd", "mc lg", "mc", "ad lg"},
        "PHE": {"phe", "phed"},
        "C&W": {"c&w", "cwpp&h", "c&wpp&h", "cw pp&h", "pp&h", "b&r"},
        "Agriculture": {"agricultural", "agriculture"},
        "QESCO": {"qesco"},
    }
    for canonical, variants in groups.items():
        if v_lower in variants:
            return canonical
    return v


def load_dataset(path: str, sheet_name: str | int = 0) -> LoadResult:
    header_row = _find_header_row(path, sheet_name=sheet_name)
    df = pd.read_excel(path, sheet_name=sheet_name, header=header_row)
    df = df.dropna(how="all").reset_index(drop=True)
    raw_df = df.copy(deep=True)

    detected_schema = "pmts" if PMTS_EXPECTED_COLUMNS.issubset(set(df.columns)) else "generic"

    for col in df.columns:
        if col in NUMERIC_HINT_COLUMNS or "cost" in col.lower() or "progress" in col.lower():
            df[col] = pd.to_numeric(df[col], errors="coerce")

    format_issues: dict[str, list[str]] = {}

    if "Contractor" in df.columns:
        df["Contractor"] = df["Contractor"].apply(_clean_contractor_name)

    if "XEN Contact" in df.columns:
        normalized = df["XEN Contact"].apply(_normalize_phone)
        df["XEN Contact"] = normalized.apply(lambda t: t[0])
        issues_found = sorted({t[1] for t in normalized if t[1]})
        if issues_found:
            format_issues["XEN Contact"] = issues_found

    if "Executing Agency" in df.columns:
        df["Executing Agency (raw)"] = raw_df["Executing Agency"]
        df["Executing Agency"] = df["Executing Agency"].apply(_normalize_agency)

    if "Contractor" in df.columns:
        multi_firm = df["Contractor"].dropna().apply(
            lambda v: isinstance(v, str) and v.count("M/S") + v.count("M/s") > 1
        )
        if multi_firm.any():
            format_issues.setdefault("Contractor", []).append("multiple_firms_in_one_field")

    quality_report = generate_quality_report(df, raw_df, format_issues)
    column_types = {col: str(dtype) for col, dtype in df.dtypes.items()}

    return LoadResult(
        df=df, raw_df=raw_df, header_row_index=header_row,
        detected_schema=detected_schema, quality_report=quality_report,
        column_types=column_types,
    )


def generate_quality_report(
    df: pd.DataFrame,
    raw_df: pd.DataFrame | None = None,
    known_format_issues: dict[str, list[str]] | None = None,
) -> dict[str, Any]:
    total_rows = len(df)
    known_format_issues = known_format_issues or {}

    missing_by_column = {}
    for col in df.columns:
        missing = int(df[col].isna().sum())
        if missing > 0:
            missing_by_column[col] = {
                "missing": missing,
                "pct": round(missing / total_rows * 100, 1) if total_rows else 0.0,
            }

    near_duplicates: dict[str, list[list[str]]] = {}
    if raw_df is not None:
        for col in ("Executing Agency",):
            if col in raw_df.columns:
                groups = _detect_near_duplicate_groups(raw_df[col].dropna().unique().tolist())
                if groups:
                    near_duplicates[col] = groups

    anomalies: dict[str, str] = {}
    if "Cost (M)" in df.columns:
        zero_cost = int((df["Cost (M)"] == 0).sum())
        if zero_cost > 0:
            anomalies["Cost (M)"] = f"{zero_cost} rows have Cost (M) = 0, which may indicate unrecorded budget rather than a genuinely free project."

    if "Global ID" in df.columns:
        dupes = int(df["Global ID"].duplicated().sum())
        if dupes > 0:
            anomalies["Global ID"] = f"{dupes} duplicate Global ID values found."

    return {
        "total_rows": total_rows,
        "missing_by_column": missing_by_column,
        "format_issues": known_format_issues,
        "near_duplicate_categories": near_duplicates,
        "anomalies": anomalies,
    }


def _detect_near_duplicate_groups(values: list[str], similarity_threshold: float = 0.55) -> list[list[str]]:
    def norm(s: str) -> set[str]:
        s = unicodedata.normalize("NFKD", s.lower())
        s = re.sub(r'[^a-z0-9\s]', '', s)
        return set(s.split())

    groups: list[list[str]] = []
    used = set()
    tokens = {v: norm(v) for v in values}

    for i, a in enumerate(values):
        if a in used:
            continue
        cluster = [a]
        for b in values[i + 1:]:
            if b in used:
                continue
            ta, tb = tokens[a], tokens[b]
            if not ta or not tb:
                continue
            overlap = len(ta & tb) / max(len(ta | tb), 1)
            if overlap >= similarity_threshold or ta.issubset(tb) or tb.issubset(ta):
                cluster.append(b)
                used.add(b)
        if len(cluster) > 1:
            groups.append(sorted(cluster))
            used.update(cluster)

    return groups


if __name__ == "__main__":
    import json, sys
    path = sys.argv[1] if len(sys.argv) > 1 else "data/default/Projects.xlsx"
    result = load_dataset(path)
    print(f"Detected schema: {result.detected_schema}")
    print(f"Shape: {result.df.shape}")
    print(json.dumps(result.quality_report, indent=2))