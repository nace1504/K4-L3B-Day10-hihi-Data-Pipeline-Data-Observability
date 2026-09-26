from __future__ import annotations

from datetime import UTC, datetime
from math import ceil
from pathlib import Path
from typing import Any

import pandas as pd

from core.utils import normalize_whitespace, write_json


def _sample_indices(df: pd.DataFrame, count: int, offset: int) -> list[int]:
    """Select stable, well-spread rows so a run is reproducible."""
    if df.empty or count <= 0:
        return []
    positions = [((offset + step * 7) % len(df)) for step in range(count)]
    return list(dict.fromkeys(df.index[position] for position in positions))


def _paper_ids(df: pd.DataFrame, indices: list[int]) -> list[str]:
    return [str(df.at[index, "paper_id"]) for index in indices]


def _rebuild_embedding_text(df: pd.DataFrame) -> None:
    """Rebuild the five-part document text after corrupting source columns."""
    def value(row: pd.Series, column: str) -> str:
        raw = row.get(column, "")
        return "" if pd.isna(raw) else normalize_whitespace(str(raw))

    df["text_for_embedding"] = df.apply(
        lambda row: "\n".join(
            [
                f"Title: {value(row, 'title')}",
                f"Summary: {value(row, 'summary')}",
                f"Authors: {value(row, 'authors_joined')}",
                f"Categories: {value(row, 'categories_joined')}",
                f"Published: {value(row, 'published')}",
            ]
        ),
        axis=1,
    )


def corrupt_clean_dataframe(df: pd.DataFrame, output_log_path: Path | str) -> pd.DataFrame:
    """Inject six deterministic production-like failures and write an audit log.

    The input dataframe is never mutated. Deterministic row selection makes the
    experiment repeatable for baseline/corrupted comparisons and live demos.
    """
    required = {
        "paper_id", "title", "summary", "published", "age_days",
        "authors_joined", "categories_joined", "text_for_embedding",
    }
    missing = sorted(required.difference(df.columns))
    if missing:
        raise ValueError(f"Cannot corrupt dataframe; missing columns: {', '.join(missing)}")
    if df.empty:
        raise ValueError("Cannot corrupt an empty dataframe.")

    corrupted = df.copy(deep=True).reset_index(drop=True)
    input_rows = len(corrupted)
    scenarios: list[dict[str, Any]] = []

    published = pd.to_datetime(corrupted["published"], errors="coerce", utc=True)
    drop_count = max(1, round(input_rows * 0.20))
    drop_indices = published.sort_values(ascending=False, na_position="last").index[:drop_count].tolist()
    scenarios.append({
        "type": "drop_latest_records",
        "count": len(drop_indices),
        "paper_ids": _paper_ids(corrupted, drop_indices),
        "details": "Dropped the newest 20% of records.",
    })
    corrupted = corrupted.drop(index=drop_indices).reset_index(drop=True)

    mutation_count = max(1, round(len(corrupted) * 0.15))

    blank_indices = _sample_indices(corrupted, mutation_count, offset=0)
    corrupted.loc[blank_indices, "summary"] = ""
    if "summary_chars" in corrupted.columns:
        corrupted.loc[blank_indices, "summary_chars"] = 0
    scenarios.append({
        "type": "blank_summary",
        "count": len(blank_indices),
        "paper_ids": _paper_ids(corrupted, blank_indices),
        "details": "Replaced summaries with empty strings.",
    })

    noise_indices = _sample_indices(corrupted, mutation_count, offset=2)
    noise = " CORRUPTED_NOISE ### ??? " * 8
    for index in noise_indices:
        corrupted.at[index, "summary"] = noise + str(corrupted.at[index, "summary"])
    if "summary_chars" in corrupted.columns:
        corrupted.loc[noise_indices, "summary_chars"] = corrupted.loc[noise_indices, "summary"].str.len()
    scenarios.append({
        "type": "inject_noise",
        "count": len(noise_indices),
        "paper_ids": _paper_ids(corrupted, noise_indices),
        "details": "Prepended repeated garbage tokens to summaries.",
    })

    title_indices = _sample_indices(corrupted, mutation_count, offset=4)
    corrupted.loc[title_indices, "title"] = "BAD"
    scenarios.append({
        "type": "truncate_title",
        "count": len(title_indices),
        "paper_ids": _paper_ids(corrupted, title_indices),
        "details": "Truncated titles to fewer than eight characters.",
    })

    # Corrupt enough dates to cross the observability SLA (>25% stale), rather
    # than merely making individual dates old while the dataset still passes.
    stale_count = max(mutation_count, ceil(len(corrupted) * 0.30))
    stale_indices = _sample_indices(corrupted, stale_count, offset=6)
    corrupted.loc[stale_indices, "published"] = "2000-01-01"
    now = pd.Timestamp(datetime.now(UTC))
    corrupted.loc[stale_indices, "age_days"] = (now - pd.Timestamp("2000-01-01", tz="UTC")).days
    scenarios.append({
        "type": "stale_date",
        "count": len(stale_indices),
        "paper_ids": _paper_ids(corrupted, stale_indices),
        "details": "Made at least 30% of remaining rows stale to breach the 25% freshness SLA.",
    })

    _rebuild_embedding_text(corrupted)

    duplicate_indices = _sample_indices(corrupted, mutation_count, offset=1)
    duplicates = corrupted.loc[duplicate_indices].copy(deep=True)
    scenarios.append({
        "type": "duplicate_rows",
        "count": len(duplicates),
        "paper_ids": duplicates["paper_id"].astype(str).tolist(),
        "details": "Appended exact rows while preserving paper_id.",
    })
    corrupted = pd.concat([corrupted, duplicates], ignore_index=True)

    write_json(Path(output_log_path), {
        "generated_at": datetime.now(UTC).isoformat(),
        "deterministic": True,
        "input_rows": input_rows,
        "output_rows": len(corrupted),
        "scenario_count": len(scenarios),
        "scenarios": scenarios,
    })
    return corrupted
