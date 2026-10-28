# Model card: HireRight candidate ranker

| Field | Value |
|---|---|
| Model | `ranker-2.4.1` (LightGBM LambdaRank, 400 trees) |
| Owner | Talent Data Science (talent-ds@acme.example) |
| Released | 2026-06-30 |

## Intended use
Ordering applications for a single requisition so that recruiters review the most relevant CVs
first. Decision support only: the model does not accept or reject candidates.

## Out-of-scope uses
Ranking internal employees for promotion or termination; use outside ACME recruitment; any use
without a recruiter reviewing every candidate; use on video, audio or photos.

## Training data
512k historical (application, requisition, recruiter-shortlist) triples from ACME EU offices,
2021-2025. See `DATASHEET.md`.

## Evaluation (hold-out 2025-H2, 41k applications)
| Metric | Value |
|---|---|
| NDCG@10 | 0.71 |
| ROC-AUC (shortlisted vs not) | 0.87 |
| Precision@10 | 0.64 |
| Recall@50 | 0.82 |

## Limitations
* Learns from historical shortlisting decisions, which may carry human bias.
* Lower quality for requisitions with fewer than 20 applicants and for non-English CVs (AUC 0.79).
* CV parsing errors propagate to the score.

## Fairness
A group-level fairness evaluation has not been completed for this release; see risk R-03 in
`docs/risk-assessment.md`.
