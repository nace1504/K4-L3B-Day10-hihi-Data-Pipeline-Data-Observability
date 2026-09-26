from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from core.utils import normalize_whitespace, write_json


_QUESTION_SPECS = (
    ("summary", "summary", 3, "What is the summary of '{title}'?"),
    ("authors", "authors_joined", 3, "Who authored '{title}'?"),
    ("date", "published", 2, "When was '{title}' published?"),
    ("categories", "categories_joined", 2, "What categories does '{title}' belong to?"),
)
_REQUIRED_COLUMNS = {
    "paper_id",
    "title",
    "summary",
    "authors_joined",
    "categories_joined",
    "published",
}


def _nonempty(value: object) -> str:
    """Return normalized text, treating NaN and non-string values safely."""
    if pd.isna(value) or not isinstance(value, str):
        return ""
    return normalize_whitespace(value)


def build_test_set(df: pd.DataFrame, output_path) -> list[dict[str, Any]]:
    """Build and persist ten deterministic, metadata-grounded evaluation questions.

    The fixed distribution is three summary, three author, two publication-date,
    and two category questions. Each group uses distinct eligible documents.
    """
    missing_columns = sorted(_REQUIRED_COLUMNS - set(df.columns))
    if missing_columns:
        raise ValueError(f"Cleaned dataframe is missing required columns: {', '.join(missing_columns)}.")

    base = df.copy()
    base["paper_id"] = base["paper_id"].map(_nonempty)
    base["title"] = base["title"].map(_nonempty)
    # The answer router identifies a title between single quotes.
    base = base[(base["paper_id"] != "") & (base["title"] != "")]
    base = base[~base["title"].str.contains("'", regex=False)]

    test_set: list[dict[str, Any]] = []
    next_id = 1
    for question_type, answer_column, count, template in _QUESTION_SPECS:
        eligible = base.copy()
        eligible[answer_column] = eligible[answer_column].map(_nonempty)
        eligible = eligible[eligible[answer_column] != ""]
        if len(eligible) < count:
            raise ValueError(
                f"Cannot create the required {count} {question_type} questions: "
                f"only {len(eligible)} eligible rows have non-empty {answer_column!r}."
            )

        for _, row in eligible.iloc[:count].iterrows():
            title = row["title"]
            test_set.append(
                {
                    "id": f"q{next_id:02d}",
                    "question_type": question_type,
                    "question": template.format(title=title),
                    "ground_truth": row[answer_column],
                    "ground_truth_doc_ids": [row["paper_id"]],
                }
            )
            next_id += 1

    if len(test_set) != 10:
        raise RuntimeError(f"Expected to create 10 test questions, created {len(test_set)}.")
    write_json(Path(output_path), test_set)
    return test_set
