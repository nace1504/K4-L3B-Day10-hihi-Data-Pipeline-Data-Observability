from __future__ import annotations

from datetime import UTC, datetime

import pandas as pd

from core.config import load_settings
from core.utils import read_json, write_csv
from evaluation.metrics import evaluate_pipeline
from evaluation.testset import build_test_set
from ingestion.cleaning import build_clean_dataframe
from ingestion.crossref import fetch_source_records, load_raw_records
from observability.quality import build_freshness_report, run_data_quality_checks
from observability.reporting import generate_phase1_report
from retrieval.index import LocalEmbeddingIndex


def _write_dataframe(df: pd.DataFrame, csv_path, json_path) -> None:
    write_csv(df, csv_path)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_json(json_path, orient="records", indent=2, force_ascii=False, date_format="iso")


def main() -> None:
    """Run ingestion, cleaning, indexing, evaluation and observability."""
    settings = load_settings()
    paths = settings.paths

    print("[1/6] Loading source records...")
    if settings.refresh_source or not paths.raw_records_json.exists():
        records = fetch_source_records(settings)
    else:
        records = load_raw_records(paths.raw_records_json)
    if not records:
        raise RuntimeError("No raw records are available for the baseline pipeline.")

    print("[2/6] Cleaning and saving datasets...")
    clean_df = build_clean_dataframe(records, datetime.now(UTC))
    if clean_df.empty:
        raise RuntimeError("Cleaning produced an empty dataframe.")
    _write_dataframe(clean_df, paths.clean_csv, paths.clean_json)

    print("[3/6] Building baseline Chroma index...")
    index = LocalEmbeddingIndex.build(clean_df, settings, paths.embeddings_json)

    print("[4/6] Preparing a shared evaluation set...")
    if settings.refresh_test_set or not paths.eval_testset.exists():
        test_set = build_test_set(clean_df, paths.eval_testset)
    else:
        test_set = read_json(paths.eval_testset)
    if not test_set:
        raise RuntimeError("The evaluation set is empty.")

    print("[5/6] Evaluating baseline and running quality gates...")
    evaluation = evaluate_pipeline(
        settings, index, paths.eval_testset,
        paths.baseline_metrics, paths.baseline_answers,
    )
    quality = run_data_quality_checks(clean_df, settings, "baseline")
    freshness = build_freshness_report(clean_df, settings, paths.freshness_report)

    print("[6/6] Writing baseline report...")
    source_summary = {
        "source": settings.source_api,
        "query": settings.source_query,
        "raw_records": len(records),
        "clean_records": len(clean_df),
        "evaluation_samples": len(test_set),
        "collection_name": settings.baseline_collection_name,
    }
    generate_phase1_report(
        paths.baseline_report, source_summary, evaluation.summary, quality, freshness
    )

    print("Baseline pipeline completed.")
    print(f"  documents: {len(clean_df)}")
    print(f"  retrieval_hit_rate: {evaluation.summary['retrieval_hit_rate']:.4f}")
    print(f"  mean_token_f1: {evaluation.summary['mean_token_f1']:.4f}")
    print(f"  report: {paths.baseline_report}")
