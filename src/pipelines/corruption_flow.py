from __future__ import annotations

from datetime import UTC, datetime

import pandas as pd

from core.config import load_settings
from core.utils import read_json, write_csv
from evaluation.metrics import evaluate_pipeline
from ingestion.cleaning import build_clean_dataframe
from ingestion.corruption import corrupt_clean_dataframe
from ingestion.crossref import load_raw_records
from observability.quality import build_freshness_report, run_data_quality_checks
from observability.reporting import generate_corruption_report
from pipelines.phase1 import main as run_phase1
from retrieval.index import LocalEmbeddingIndex


def _write_dataframe(df: pd.DataFrame, csv_path, json_path) -> None:
    write_csv(df, csv_path)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_json(json_path, orient="records", indent=2, force_ascii=False, date_format="iso")


def _metric(value: object) -> str:
    return f"{float(value):.4f}" if isinstance(value, (int, float)) else str(value)


def main() -> None:
    """Run corruption, impact evaluation, raw-data repair and comparison."""
    settings = load_settings()
    paths = settings.paths

    baseline_required = [paths.clean_json, paths.eval_testset, paths.baseline_metrics]
    if any(not path.exists() for path in baseline_required):
        print("Baseline artifacts are incomplete; running phase 1 first...")
        run_phase1()

    baseline_df = pd.read_json(paths.clean_json)
    baseline_metrics = read_json(paths.baseline_metrics)
    if baseline_df.empty:
        raise RuntimeError("The baseline clean dataset is empty.")

    print("[1/5] Injecting six corruption scenarios...")
    corrupted_df = corrupt_clean_dataframe(baseline_df, paths.corruption_log)
    _write_dataframe(corrupted_df, paths.corrupted_clean_csv, paths.corrupted_clean_json)

    print("[2/5] Re-indexing and evaluating corrupted data...")
    corrupted_index = LocalEmbeddingIndex.build(
        corrupted_df, settings, paths.corrupted_embeddings_json
    )
    corrupted_evaluation = evaluate_pipeline(
        settings, corrupted_index, paths.eval_testset,
        paths.corrupted_metrics, paths.corrupted_answers,
    )
    corrupted_quality = run_data_quality_checks(corrupted_df, settings, "corrupted")
    corrupted_freshness = build_freshness_report(
        corrupted_df, settings, paths.quality_dir / "corrupted_freshness_report.json"
    )

    print("[3/5] Repairing idempotently from immutable raw records...")
    raw_records = load_raw_records(paths.raw_records_json)
    repaired_df = build_clean_dataframe(raw_records, datetime.now(UTC))
    if repaired_df.empty:
        raise RuntimeError("Repair produced an empty dataframe.")
    _write_dataframe(repaired_df, paths.repaired_clean_csv, paths.repaired_clean_json)

    print("[4/5] Re-indexing and evaluating repaired data...")
    repaired_index = LocalEmbeddingIndex.build(
        repaired_df, settings, paths.repaired_embeddings_json
    )
    repaired_evaluation = evaluate_pipeline(
        settings, repaired_index, paths.eval_testset,
        paths.repaired_metrics, paths.repaired_answers,
    )
    repaired_quality = run_data_quality_checks(repaired_df, settings, "repaired")
    repaired_freshness = build_freshness_report(
        repaired_df, settings, paths.quality_dir / "repaired_freshness_report.json"
    )

    print("[5/5] Writing the three-state comparison report...")
    generate_corruption_report(
        paths.comparison_report,
        baseline_metrics,
        corrupted_evaluation.summary,
        repaired_evaluation.summary,
        corrupted_quality,
        repaired_quality,
        corrupted_freshness,
        repaired_freshness,
    )

    print("\nBaseline vs Corrupted vs Repaired")
    print(f"{'Metric':<24} {'Baseline':>12} {'Corrupted':>12} {'Repaired':>12}")
    metric_names = (
        "retrieval_hit_rate", "mean_token_f1", "judge_accuracy", "mean_judge_score"
    )
    for name in metric_names:
        print(
            f"{name:<24} "
            f"{_metric(baseline_metrics.get(name)):>12} "
            f"{_metric(corrupted_evaluation.summary.get(name)):>12} "
            f"{_metric(repaired_evaluation.summary.get(name)):>12}"
        )
    print(f"\nComparison report: {paths.comparison_report}")
