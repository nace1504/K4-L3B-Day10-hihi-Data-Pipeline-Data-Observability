from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from core.config import Settings
from core.utils import safe_slug, write_json


_SUMMARY_MIN_LENGTH = 20
_SUMMARY_MAX_LENGTH = 10_000
_MAX_STALE_RATIO = 0.25


def _quality_report_path(settings: Settings, report_name: str) -> Path:
    """Use the named report paths when available; otherwise stay in quality_dir."""
    name = safe_slug(report_name)
    if name == "baseline":
        return settings.paths.baseline_quality_report
    if name == "corrupted":
        return settings.paths.corrupted_quality_report
    return settings.paths.quality_dir / f"{name}_quality_report.json"


def _result_payload(result: Any) -> dict[str, Any]:
    """Keep GX validation output useful while ensuring it is JSON serializable."""
    if hasattr(result, "to_json_dict"):
        payload = result.to_json_dict()
    else:
        payload = {
            "success": bool(getattr(result, "success", False)),
            "result": getattr(result, "result", {}),
        }
    return payload if isinstance(payload, dict) else {"success": False, "result": {}}


def _run_expectation(batch: Any, expectation: Any) -> dict[str, Any]:
    try:
        return _result_payload(batch.validate(expectation))
    except Exception as exc:
        # Missing columns and invalid dtypes are quality failures, not pipeline crashes.
        return {"success": False, "exception": str(exc)}


def build_freshness_report(df: pd.DataFrame, settings: Settings, report_path) -> dict[str, Any]:
    """Summarize the freshness SLA and persist a JSON report.

    The dataset is stale when more than 25% of rows exceed the configured age
    threshold. Invalid or missing ``age_days`` values are counted as stale so
    freshness cannot be reported as healthy from incomplete metadata.
    """
    target_path = Path(report_path)
    total_rows = int(len(df))
    ages = (
        pd.to_numeric(df["age_days"], errors="coerce")
        if "age_days" in df.columns
        else pd.Series(index=df.index, dtype="float64")
    )
    stale_mask = ages.isna() | (ages > settings.freshness_threshold_days)
    stale_rows = int(stale_mask.sum())
    stale_ratio = stale_rows / total_rows if total_rows else 0.0

    published = (
        pd.to_datetime(df["published"], errors="coerce", utc=True)
        if "published" in df.columns
        else pd.Series(dtype="datetime64[ns, UTC]")
    )
    valid_published = published.dropna()
    latest_published = valid_published.max().date().isoformat() if not valid_published.empty else None
    oldest_published = valid_published.min().date().isoformat() if not valid_published.empty else None

    report = {
        "success": stale_ratio <= _MAX_STALE_RATIO,
        "is_fresh": stale_ratio <= _MAX_STALE_RATIO,
        "freshness_threshold_days": settings.freshness_threshold_days,
        "max_stale_ratio": _MAX_STALE_RATIO,
        "stale_rows": stale_rows,
        "total_rows": total_rows,
        "stale_ratio": stale_ratio,
        "latest_published": latest_published,
        "oldest_published": oldest_published,
    }
    write_json(target_path, report)
    return report


def run_data_quality_checks(df: pd.DataFrame, settings: Settings, report_name: str) -> dict[str, Any]:
    """Run Great Expectations 1.x checks and the project's freshness SLA."""
    try:
        import great_expectations as gx
    except ImportError as exc:  # pragma: no cover - depends on environment setup
        raise RuntimeError(
            "great_expectations is required for data quality checks. Install project dependencies first."
        ) from exc

    # GX 1.x ephemeral context: no on-disk GX project or datasource is created.
    context = gx.get_context(mode="ephemeral")
    data_source = context.data_sources.add_pandas(name="papers_source")
    data_asset = data_source.add_dataframe_asset(name="papers_asset")
    batch_definition = data_asset.add_batch_definition_whole_dataframe("papers_batch")
    batch = batch_definition.get_batch(batch_parameters={"dataframe": df})

    checks = {
        "row_count": _run_expectation(
            batch,
            gx.expectations.ExpectTableRowCountToBeBetween(
                min_value=1,
                max_value=max(1, settings.max_results),
            ),
        ),
        "paper_id_not_null": _run_expectation(
            batch,
            gx.expectations.ExpectColumnValuesToNotBeNull(column="paper_id"),
        ),
        "paper_id_unique": _run_expectation(
            batch,
            gx.expectations.ExpectColumnValuesToBeUnique(column="paper_id"),
        ),
        "title_not_null": _run_expectation(
            batch,
            gx.expectations.ExpectColumnValuesToNotBeNull(column="title"),
        ),
        "summary_length": _run_expectation(
            batch,
            gx.expectations.ExpectColumnValueLengthsToBeBetween(
                column="summary",
                min_value=_SUMMARY_MIN_LENGTH,
                max_value=_SUMMARY_MAX_LENGTH,
            ),
        ),
    }
    freshness = build_freshness_report(df, settings, settings.paths.freshness_report)
    checks_success = all(bool(result.get("success", False)) for result in checks.values())
    report_path = _quality_report_path(settings, report_name)
    report = {
        "success": checks_success and freshness["is_fresh"],
        "report_name": report_name,
        "checks": checks,
        "freshness": freshness,
    }
    write_json(report_path, report)
    return report
