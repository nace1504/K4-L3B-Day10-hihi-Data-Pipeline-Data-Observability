# Baseline vs Corrupted vs Repaired

## Comparison

| Measure | Baseline | Corrupted | Repaired |
| --- | ---: | ---: | ---: |
| retrieval_hit_rate | 1.0000 | 0.0000 | 1.0000 |
| mean_token_f1 | 0.8816 | 0.5537 | 0.8816 |
| judge_accuracy | 1.0000 | 0.6000 | 1.0000 |
| mean_judge_score | 4.4000 | 3.2000 | 4.4000 |
| quality_success | True | False | True |
| freshness_is_fresh | True | False | True |

## Automatic observations

- Corrupted performance decreased for: retrieval_hit_rate, mean_token_f1, judge_accuracy, mean_judge_score.
- Repaired moved closer to baseline for: retrieval_hit_rate, mean_token_f1, judge_accuracy, mean_judge_score.
