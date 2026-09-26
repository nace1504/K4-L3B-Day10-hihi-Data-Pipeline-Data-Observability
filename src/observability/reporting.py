from __future__ import annotations

from numbers import Real
from pathlib import Path
from typing import Any

from core.utils import write_text


_METRIC_KEYS = (
    "retrieval_hit_rate",
    "mean_token_f1",
    "judge_accuracy",
    "mean_judge_score",
)


def _value(mapping: dict[str, Any] | None, key: str) -> Any:
    return mapping.get(key) if isinstance(mapping, dict) and key in mapping else None


def _display(value: Any) -> str:
    """Render absent or non-scalar report values safely for Markdown."""
    if value is None or value == "":
        return "N/A"
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, Real) and not isinstance(value, bool):
        return f"{value:.4f}"
    return str(value).replace("|", "\\|").replace("\n", " ")


def _nested_value(mapping: dict[str, Any], section: str, key: str) -> Any:
    nested = mapping.get(section)
    return _value(nested, key) if isinstance(nested, dict) else None


def _metric_table(metrics: dict[str, Any]) -> list[str]:
    lines = ["| Metric | Value |", "| --- | ---: |"]
    lines.extend(f"| {key} | {_display(_value(metrics, key))} |" for key in _METRIC_KEYS)
    return lines


def generate_phase1_report(
    report_path,
    source_summary: dict[str, Any],
    metrics: dict[str, Any],
    quality: dict[str, Any],
    freshness: dict[str, Any],
) -> None:
    """Write a resilient Markdown summary for the Phase 1 baseline run."""
    lines = ["# Phase 1 Baseline Report", "", "## Source Summary", ""]
    if source_summary:
        lines.extend(f"- **{key}:** {_display(value)}" for key, value in source_summary.items())
    else:
        lines.append("- N/A")

    lines.extend(["", "## Baseline Metrics", ""])
    lines.extend(_metric_table(metrics))

    lines.extend(["", "## Data Quality", "", f"- **success:** {_display(_value(quality, 'success'))}"])
    checks = _value(quality, "checks")
    if isinstance(checks, dict) and checks:
        lines.extend(["", "| Check | Success |", "| --- | --- |"])
        for check_name, result in checks.items():
            result_value = _value(result, "success") if isinstance(result, dict) else result
            lines.append(f"| {check_name} | {_display(result_value)} |")
    else:
        lines.append("- Check details: N/A")

    lines.extend(["", "## Freshness", "", "| Field | Value |", "| --- | --- |"])
    for key in ("latest_published", "oldest_published", "stale_rows", "total_rows", "is_fresh"):
        lines.append(f"| {key} | {_display(_value(freshness, key))} |")

    lines.extend(
        [
            "",
            "## Generated artifacts",
            "",
            "This report summarizes the supplied baseline metrics, data-quality checks, and freshness results.",
        ]
    )
    write_text(Path(report_path), "\n".join(lines) + "\n")


def _automatic_observations(
    baseline: dict[str, Any], corrupted: dict[str, Any], repaired: dict[str, Any]
) -> list[str]:
    observations: list[str] = []
    degraded: list[str] = []
    improved: list[str] = []
    not_recovered: list[str] = []

    for key in _METRIC_KEYS:
        base_value = _value(baseline, key)
        corrupted_value = _value(corrupted, key)
        repaired_value = _value(repaired, key)
        if isinstance(base_value, Real) and isinstance(corrupted_value, Real):
            if corrupted_value < base_value:
                degraded.append(key)
            if isinstance(repaired_value, Real):
                if abs(repaired_value - base_value) < abs(corrupted_value - base_value):
                    improved.append(key)
                else:
                    not_recovered.append(key)

    if degraded:
        observations.append("Corrupted performance decreased for: " + ", ".join(degraded) + ".")
    elif any(isinstance(_value(baseline, key), Real) and isinstance(_value(corrupted, key), Real) for key in _METRIC_KEYS):
        observations.append("No supplied numeric metric decreased from baseline to corrupted.")
    else:
        observations.append("N/A: insufficient numeric baseline and corrupted metrics for a degradation comparison.")

    if improved:
        observations.append("Repaired moved closer to baseline for: " + ", ".join(improved) + ".")
    if not_recovered:
        observations.append("Repaired did not move closer to baseline for: " + ", ".join(not_recovered) + ".")
    if not improved and not not_recovered:
        observations.append("N/A: insufficient numeric repaired metrics for a recovery comparison.")
    return observations


def generate_corruption_report(
    report_path,
    baseline_metrics: dict[str, Any],
    corrupted_metrics: dict[str, Any],
    repaired_metrics: dict[str, Any],
    corrupted_quality: dict[str, Any],
    repaired_quality: dict[str, Any],
    corrupted_freshness: dict[str, Any],
    repaired_freshness: dict[str, Any],
) -> None:
    """Write a baseline/corruption/repair comparison without inventing values."""
    baseline_quality = _nested_value(baseline_metrics, "quality", "success")
    baseline_freshness = _nested_value(baseline_metrics, "freshness", "is_fresh")
    rows = [(key, _value(baseline_metrics, key), _value(corrupted_metrics, key), _value(repaired_metrics, key)) for key in _METRIC_KEYS]
    rows.extend(
        (
            ("quality_success", baseline_quality, _value(corrupted_quality, "success"), _value(repaired_quality, "success")),
            ("freshness_is_fresh", baseline_freshness, _value(corrupted_freshness, "is_fresh"), _value(repaired_freshness, "is_fresh")),
        )
    )

    lines = [
        "# Baseline vs Corrupted vs Repaired",
        "",
        "## Comparison",
        "",
        "| Measure | Baseline | Corrupted | Repaired |",
        "| --- | ---: | ---: | ---: |",
    ]
    lines.extend(f"| {name} | {_display(base)} | {_display(corrupted)} | {_display(repaired)} |" for name, base, corrupted, repaired in rows)
    lines.extend(["", "## Automatic observations", ""])
    lines.extend(f"- {observation}" for observation in _automatic_observations(baseline_metrics, corrupted_metrics, repaired_metrics))
    write_text(Path(report_path), "\n".join(lines) + "\n")
