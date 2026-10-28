# HireRight Screening: technical documentation (AI Act Art. 11, Annex IV)

## 1. General description
* **Intended purpose:** ranking job applications per requisition to support recruiters at ACME.
  Provider and deployer: ACME Corp, Talent Technology. System version 2.4.1 (model `ranker-2.4.1`),
  previous version 2.3.0 used a logistic-regression scorer.
* **Interaction with other systems:** consumes parsed CVs from the ATS (Workday) through the
  `ats-bridge` service; returns rankings to the recruiter dashboard. No other AI systems are called.
* **Software versions:** Python 3.12, LightGBM 4.3, SHAP 0.45, FastAPI 0.111.
* **Forms of deployment:** internal REST API on EKS (eu-central-1); not sold externally.
* **Hardware:** 2x c7g.xlarge pods; no GPU required.
* **User interface:** recruiter dashboard (`web/`) showing ranking, main reasons and actions.

## 2. Development process and design
* **Methods:** supervised learning-to-rank (LambdaRank) on historical shortlisting decisions;
  hyper-parameters tuned with 5-fold group CV by requisition.
* **Design choices:** decision support only; protected attributes and identity fields removed
  before feature extraction; per-candidate SHAP explanations exposed to recruiters; failures yield
  an unranked application rather than a low score.
* **Architecture:** `api.py` (FastAPI) → `model.py` (feature builder + LightGBM + SHAP) →
  `journal.py` (append-only DecisionJournal on S3 Object Lock) ; recruiter UI reads rankings via the
  API; `retention.py` CronJob enforces the retention schedule.
* **Data:** see `DATASHEET.md`.
* **Human oversight:** recruiter decision and override endpoints; admin suspend switch
  (`/admin/ranking/suspend`); see `docs/instructions-for-use.md`.
* **Validation and testing:** offline evaluation on hold-out (see `MODEL_CARD.md`), CI quality gate
  `tests/test_model_quality.py`, shadow deployment for two weeks before every release.

## 3. Monitoring and control
Weekly performance report and PSI-based drift alerts (`config/app.yaml: monitoring`).

## 4. Risk management
See `docs/risk-assessment.md`.
